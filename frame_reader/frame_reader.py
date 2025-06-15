import os
import cv2
import time
import json
from kafka import KafkaProducer

VIDEO_SOURCE = os.getenv("VIDEO_SOURCE", 0)
KAFKA_SERVERS = os.getenv("KAFKA_BOOTSTRAP_SERVERS", "localhost:9092")
FRAME_TOPIC = os.getenv("FRAME_TOPIC", "frames.raw")
FPS = float(os.getenv("FPS", 10.0))

producer = KafkaProducer(
    bootstrap_servers=KAFKA_SERVERS.split(","),
    value_serializer=lambda v: json.dumps(v).encode('utf-8')
)

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
    producer.send(FRAME_TOPIC, msg)
    if frame_id % 30 == 0:
        producer.flush()

    frame_id += 1
    elapsed = time.time() - start
    time.sleep(max(0, interval - elapsed))

cap.release()
producer.flush()
producer.close()

