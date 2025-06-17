import sys
import os
sys.path.append('/app/shared')

from confluent_kafka import Consumer, Producer
from ultralytics import YOLO
import cv2
import numpy as np
import json
import time
from datetime import datetime
from database import db_manager
import logging

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

print("Starting detection service...")

# Load YOLO model
model_path = "/app/models/best.pt"
if not os.path.exists(model_path):
    raise FileNotFoundError(f"YOLO model not found at: {model_path}")

try:
    model = YOLO(model_path)
    print("Custom YOLO model loaded successfully")
except Exception as e:
    raise RuntimeError(f"Failed to load YOLO model: {e}")

# Initialize database connection
try:
    db_manager.connect()
    print("Database connection established")
except Exception as e:
    print(f"Database connection failed: {e}")
    # Continue without database for now

# Kafka setup
kafka_servers = os.getenv('KAFKA_BOOTSTRAP_SERVERS', 'kafka:9092')

# Kafka consumer setup with retry logic
consumer = None
for attempt in range(20):  # Increased retry attempts
    try:
        consumer = Consumer({
            'bootstrap.servers': kafka_servers,
            'group.id': 'detector',
            'auto.offset.reset': 'earliest',
            'enable.auto.commit': True,
            'auto.commit.interval.ms': 1000,
        })
        consumer.subscribe(['frames.raw'])
        print("Connected to Kafka consumer")
        break
    except Exception as e:
        print(f"Kafka consumer connection failed (attempt {attempt + 1}): {e}")
        time.sleep(5)

if consumer is None:
    raise Exception("Failed to connect to Kafka consumer after multiple attempts")

# Kafka producer setup
producer = None
for attempt in range(20):
    try:
        producer = Producer({'bootstrap.servers': kafka_servers})
        print("Connected to Kafka producer")
        break
    except Exception as e:
        print(f"Kafka producer connection failed (attempt {attempt + 1}): {e}")
        time.sleep(5)

if producer is None:
    raise Exception("Failed to connect to Kafka producer after multiple attempts")

# Create violations directory
os.makedirs('/app/violations', exist_ok=True)
print("Violations directory created")

# Violation detection logic
def detect_violation(detections):
    """
    Implement your specific violation detection logic here
    For food safety: detect if hand touches ingredient without scooper
    """
    violation = False
    violation_type = None
    violation_description = None

    # Simple example logic - customize based on your model classes
    hand_detected = False
    scooper_detected = False
    ingredient_detected = False

    for detection in detections:
        label = detection['label'].lower()
        if 'hand' in label:
            hand_detected = True
        elif 'scoop' in label or 'utensil' in label:
            scooper_detected = True
        elif 'ingredient' in label or 'food' in label:
            ingredient_detected = True

    # Example violation logic
    if hand_detected and ingredient_detected and not scooper_detected:
        violation = True
        violation_type = "hand_without_scooper"
        violation_description = "Hand detected handling ingredient without proper scooper/utensil"

    return violation, violation_type, violation_description

print("Starting frame processing loop...")
frame_count = 0
violation_count = 0

while True:
    try:
        # Poll for messages
        msg = consumer.poll(5.0)

        if msg is None:
            continue

        if msg.error():
            print(f"Consumer error: {msg.error()}")
            continue

        # Skip test messages
        if msg.value() == b'test':
            continue

        frame_count += 1
        print(f"Processing frame {frame_count}...")

        # Decode frame from bytes
        try:
            print(f"Raw message (first 100 chars): {msg.value()[:100]}...")
            print(f"Message type: {type(msg.value())}")
            print(f"Message length: {len(msg.value())}")

            # Try to parse JSON
            message_data = json.loads(msg.value())
            print(f"Parsed JSON keys: {list(message_data.keys())}")

            if 'image_bytes' in message_data:
                print(f"Image bytes type: {type(message_data['image_bytes'])}")
                print(f"Image bytes length: {len(message_data['image_bytes'])}")
                print(f"First 50 chars of image_bytes: {message_data['image_bytes'][:50]}")

                # Convert hex string back to bytes
                image_bytes = bytes.fromhex(message_data["image_bytes"])
                print(f"Decoded bytes length: {len(image_bytes)}")

                # Try to decode image
                nparr = np.frombuffer(image_bytes, np.uint8)
                print(f"Numpy array shape: {nparr.shape}")

                frame = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
                
                if frame is None:
                    print("ERROR: cv2.imdecode returned None - invalid image data")
                    continue
                else:
                    print(f"SUCCESS: Frame decoded with shape: {frame.shape}")
            else:
                print("ERROR: 'image_bytes' key not found in message")
                continue
                
        except json.JSONDecodeError as e:
            print(f"JSON decode error: {e}")
            print(f"Raw message was: {msg.value()}")
            continue
        except ValueError as e:
            print(f"Hex decode error: {e}")
            continue
        except Exception as e:
            print(f"Unexpected error: {e}")
            import traceback
            traceback.print_exc()
            continue

        # Run YOLO detection
        try:
            results = model(frame, verbose=False)

        except Exception as e:
            print(f"Error running YOLO detection: {e}")
            continue

        # Process detection results
        detections = []

        for r in results:
            if r.boxes is not None:
                for box in r.boxes:
                    try:
                        cls_id = int(box.cls[0])
                        cls_name = model.names[cls_id]
                        confidence = float(box.conf[0])
                        x1, y1, x2, y2 = map(int, box.xyxy[0])

                        detection = {
                            'label': cls_name,
                            'confidence': confidence,
                            'bbox': [x1, y1, x2, y2]
                        }
                        detections.append(detection)

                    except Exception as e:
                        print(f"Error processing detection box: {e}")
                        continue

        # Check for violations
        violation, violation_type, violation_description = detect_violation(detections)

        if violation:
            violation_count += 1
            print(f"VIOLATION DETECTED #{violation_count}: {violation_description}")

            # Save violation frame
            try:
                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")[:-3]  # Include milliseconds
                violation_filename = f"violation_{timestamp}_frame_{frame_count}.jpg"
                violation_path = f"/app/violations/{violation_filename}"
                cv2.imwrite(violation_path, frame)
                print(f"Violation frame saved: {violation_filename}")

                # Save to database
                try:
                    # Prepare bounding boxes for database
                    bounding_boxes = []
                    labels = []

                    for det in detections:
                        x1, y1, x2, y2 = det['bbox']
                        bounding_boxes.append({
                            'x': float(x1),
                            'y': float(y1),
                            'width': float(x2 - x1),
                            'height': float(y2 - y1),
                            'class_name': det['label'],
                            'confidence': float(det['confidence'])
                        })

                        labels.append({
                            'label_name': det['label'],
                            'confidence': float(det['confidence'])
                        })

                    # Insert violation into database
                    violation_id = db_manager.insert_violation(
                        frame_number=frame_count,
                        frame_path=violation_path,
                        violation_type=violation_type,
                        violation_description=violation_description,
                        confidence_score=max([det['confidence'] for det in detections]) if detections else 0.0,
                        bounding_boxes=bounding_boxes,
                        labels=labels
                    )
                    print(f"Violation saved to database with ID: {violation_id}")

                except Exception as e:
                    print(f"Error saving violation to database: {e}")

            except Exception as e:
                print(f"Error saving violation frame: {e}")

        # Send detection results to Kafka
        detection_topic = os.getenv('DETECTIONS', 'frames.detections')
        try:
            detection_data = {
                'timestamp': datetime.now().isoformat(),
                'frame_count': frame_count,
                'detections': detections,
                'violation': violation,
                'violation_type': violation_type,
                'violation_description': violation_description,
                'violation_count': violation_count
            }

            producer.produce('detections', value=json.dumps(detection_data))
            producer.flush()

            if frame_count % 100 == 0:  # Progress update every 100 frames
                print(f"Processed {frame_count} frames, {violation_count} violations detected")

        except Exception as e:
            print(f"Error sending detection results: {e}")

    except KeyboardInterrupt:
        print("Shutting down detection service...")
        break
    except Exception as e:
        print(f"Unexpected error in main loop: {e}")
        time.sleep(1)

# Cleanup
try:
    consumer.close()
    db_manager.close()
    print("Services closed gracefully")
except:
    pass
