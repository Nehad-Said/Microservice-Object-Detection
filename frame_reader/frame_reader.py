import cv2
import time
import sys
from confluent_kafka import Producer

# Retry Kafka connection
producer = None
for attempt in range(10):
    try:
        producer = Producer({'bootstrap.servers': 'kafka:9092'})
        # Try producing a test message to check connection
        producer.produce('frames', value=b'test', timestamp=int(time.time() * 1000))
        producer.flush()
        print("Connected to Kafka")
        break
    except Exception as e:
        print(f"Kafka connection failed: {e} — retrying in 5s")
        time.sleep(5)

if producer is None:
    raise Exception("Failed to connect to Kafka after multiple attempts")

# Open video (you mounted the file directly, not inside /video)
cap = cv2.VideoCapture("pizza_monitoring.mp4")

if not cap.isOpened():
    print("Error: Could not open video file pizza_monitoring.mp4")
    sys.exit(1)

print(f"Video opened successfully. FPS: {cap.get(cv2.CAP_PROP_FPS)}, Total frames: {cap.get(cv2.CAP_PROP_FRAME_COUNT)}")

def publish_frame(frame, ts):
    try:
        _, buf = cv2.imencode('.jpg', frame)
        producer.produce('frames', value=buf.tobytes(), timestamp=int(ts))
        producer.flush()
    except Exception as e:
        print(f"Error publishing frame: {e}")

frame_count = 0
fps = cap.get(cv2.CAP_PROP_FPS) or 30  # Default to 30 FPS if unable to get FPS
frame_delay = 1.0 / fps  # Delay between frames to maintain video speed

print("Starting frame processing...")

while cap.isOpened():
    ret, frame = cap.read()
    if not ret:
        print("End of video reached")
        break
    
    # Get current timestamp
    timestamp = cap.get(cv2.CAP_PROP_POS_MSEC)
    
    # Publish frame
    publish_frame(frame, timestamp)
    
    frame_count += 1
    if frame_count % 100 == 0:  # Print progress every 100 frames
        print(f"Processed {frame_count} frames")
    
    # Add delay to maintain video playback speed (optional)
    time.sleep(frame_delay)

print(f"Video processing completed. Total frames processed: {frame_count}")
cap.release()

# Keep the container running in a loop to continuously process the video
print("Restarting video processing...")
while True:
    cap = cv2.VideoCapture("pizza_monitoring.mp4")
    if not cap.isOpened():
        print("Error: Could not reopen video file")
        time.sleep(10)
        continue
    
    frame_count = 0
    print("Restarting frame processing...")
    
    while cap.isOpened():
        ret, frame = cap.read()
        if not ret:
            print("End of video reached, restarting...")
            break
        
        timestamp = cap.get(cv2.CAP_PROP_POS_MSEC)
        publish_frame(frame, timestamp)
        
        frame_count += 1
        if frame_count % 100 == 0:
            print(f"Processed {frame_count} frames")
        
        time.sleep(frame_delay)
    
    cap.release()
    print("Waiting 5 seconds before restarting video...")
    time.sleep(5)
