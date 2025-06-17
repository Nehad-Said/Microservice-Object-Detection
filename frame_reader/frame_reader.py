import os
import cv2
import time
import json
from confluent_kafka import Producer

VIDEO_SOURCE = os.getenv("VIDEO_SOURCE", "video/pizza_monitoring.mp4")
KAFKA_SERVERS = os.getenv("KAFKA_BOOTSTRAP_SERVERS", "localhost:9092")
FRAME_TOPIC = os.getenv("FRAME_TOPIC", "frames.raw")
FPS = float(os.getenv("FPS", 10.0))

# Configure Confluent Kafka Producer
producer_config = {
    'bootstrap.servers': KAFKA_SERVERS,
    'message.max.bytes': 10485760,
    'client.id': 'frame_reader',
    'delivery.timeout.ms': 30000,
    'request.timeout.ms': 10000
}
producer = Producer(producer_config)

def delivery_callback(err, msg):
    """Callback for message delivery confirmation"""
    if err:
        print(f"[frame_reader] Message delivery failed: {err}")
    # Uncomment below for debugging
    # else:
    #     print(f"[frame_reader] Message delivered to {msg.topic()} [{msg.partition()}]")

cap = cv2.VideoCapture(VIDEO_SOURCE)
print(f"[frame_reader] Streaming from {VIDEO_SOURCE} to Kafka {KAFKA_SERVERS} topic {FRAME_TOPIC}")

frame_id = 0
interval = 1.0 / FPS

while True:
    start = time.time()
    ret, frame = cap.read()
    if not ret:
        print("[frame_reader] End of video or cannot read frame")
        break

    _, buf = cv2.imencode('.jpg', frame)
    msg = {
        "frame_id": frame_id,
        "timestamp": time.time(),
        "image_bytes": buf.tobytes().hex()
    }

    # Send message with confluent-kafka
    producer.produce(
        FRAME_TOPIC, 
        key=str(frame_id),
        value=json.dumps(msg).encode('utf-8'),
        callback=delivery_callback
    )

    # Flush periodically to ensure delivery
    if frame_id % 30 == 0:
        producer.flush()

    frame_id += 1
    elapsed = time.time() - start
    time.sleep(max(0, interval - elapsed))

cap.release()
producer.flush()  # Final flush to ensure all messages are sent
print("[frame_reader] Finished streaming")
