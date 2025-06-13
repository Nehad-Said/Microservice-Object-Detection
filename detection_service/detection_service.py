from confluent_kafka import Consumer, Producer
from ultralytics import YOLO
import cv2
import numpy as np
import json
import os
import time
from datetime import datetime

print("Starting detection service...")

# Load YOLO model
try:
    model = YOLO("models/best.pt")
    print("YOLO model loaded successfully")
except Exception as e:
    print(f"Error loading YOLO model: {e}")
    print("Using default YOLOv8 model...")
    model = YOLO("yolov8n.pt")  # Fallback to default model

# Kafka consumer setup with retry logic
consumer = None
for attempt in range(10):
    try:
        consumer = Consumer({
            'bootstrap.servers': 'kafka:9092',
            'group.id': 'detector',
            'auto.offset.reset': 'earliest',
            'enable.auto.commit': True,
            'auto.commit.interval.ms': 1000,
        })
        consumer.subscribe(['frames'])
        print("Connected to Kafka consumer")
        break
    except Exception as e:
        print(f"Kafka consumer connection failed: {e} — retrying in 5s")
        time.sleep(5)

if consumer is None:
    raise Exception("Failed to connect to Kafka consumer after multiple attempts")

# Kafka producer setup
producer = None
for attempt in range(10):
    try:
        producer = Producer({'bootstrap.servers': 'kafka:9092'})
        print("Connected to Kafka producer")
        break
    except Exception as e:
        print(f"Kafka producer connection failed: {e} — retrying in 5s")
        time.sleep(5)

if producer is None:
    raise Exception("Failed to connect to Kafka producer after multiple attempts")

# Create violations directory
os.makedirs('violations', exist_ok=True)
print("Violations directory created")

print("Starting frame processing loop...")
frame_count = 0

while True:
    try:
        # Poll for messages with a longer timeout
        msg = consumer.poll(5.0)
        
        if msg is None:
            print("No message received, continuing...")
            continue
            
        if msg.error():
            print(f"Consumer error: {msg.error()}")
            continue
        
        # Skip test messages
        if msg.value() == b'test':
            print("Received test message, skipping...")
            continue
        
        print(f"Received frame message, size: {len(msg.value())} bytes")
        
        # Decode frame from bytes
        try:
            nparr = np.frombuffer(msg.value(), np.uint8)
            frame = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
            
            if frame is None:
                print("Failed to decode frame, skipping...")
                continue
                
            print(f"Frame decoded successfully, shape: {frame.shape}")
            
        except Exception as e:
            print(f"Error decoding frame: {e}")
            continue
        
        # Run YOLO detection
        try:
            results = model(frame, verbose=False)  # Disable verbose output
            frame_count += 1
            print(f"Processed frame {frame_count}")
            
        except Exception as e:
            print(f"Error running YOLO detection: {e}")
            continue
        
        # Process detection results
        detections = []
        violation = False
        
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
                        
                        # Add your violation detection logic here
                        # For example, if detecting people in restricted areas:
                        if cls_name == 'person':  # Adjust based on your model classes
                            violation = True
                            print(f"Violation detected: {cls_name} at {[x1, y1, x2, y2]}")
                        
                    except Exception as e:
                        print(f"Error processing detection box: {e}")
                        continue
        
        print(f"Found {len(detections)} detections, violation: {violation}")
        
        # Save violation frame if needed
        if violation:
            try:
                timestamp = datetime.utcnow().isoformat().replace(':', '-')  # Windows-safe filename
                path = f"violations/{timestamp}.jpg"
                cv2.imwrite(path, frame)
                print(f"Violation frame saved to {path}")
            except Exception as e:
                print(f"Error saving violation frame: {e}")
        
        # Send detection results to Kafka
        try:
            detection_data = {
                'timestamp': datetime.utcnow().isoformat(),
                'detections': detections,
                'violation': violation,
                'frame_count': frame_count
            }
            
            producer.produce('detections', value=json.dumps(detection_data))
            producer.flush()
            print("Detection results sent to Kafka")
            
        except Exception as e:
            print(f"Error sending detection results: {e}")
    
    except KeyboardInterrupt:
        print("Shutting down detection service...")
        break
    except Exception as e:
        print(f"Unexpected error in main loop: {e}")
        time.sleep(1)  # Brief pause before continuing

# Cleanup
try:
    consumer.close()
    print("Consumer closed")
except:
    pass
