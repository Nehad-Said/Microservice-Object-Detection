# streaming_service/main.py
import os, time, json
from kafka import KafkaConsumer, KafkaProducer
import cv2
import numpy as np
# import your model runner module here

KAFKA_SERVERS = os.getenv("KAFKA_BOOTSTRAP_SERVERS", "localhost:9092")
INPUT_TOPIC = os.getenv("FRAME_TOPIC", "frames.raw")
OUTPUT_TOPIC = os.getenv("DETECTION_TOPIC", "frames.detections")

consumer = KafkaConsumer(
    INPUT_TOPIC,
    bootstrap_servers=KAFKA_SERVERS.split(","),
    value_deserializer=lambda m: json.loads(m.decode('utf-8')),
    auto_offset_reset='earliest',
    group_id="streaming-service-group"
)

producer = KafkaProducer(
    bootstrap_servers=KAFKA_SERVERS.split(","),
    value_serializer=lambda v: json.dumps(v).encode('utf-8')
)

print(f"[streaming_service] Listening on {INPUT_TOPIC}, publishing to {OUTPUT_TOPIC}")

for msg in consumer:
    data = msg.value
    img = cv2.imdecode(
        np.frombuffer(bytes.fromhex(data["image_bytes"]), dtype=np.uint8), cv2.IMREAD_COLOR
    )
    # run your model (e.g., YOLO) here
    detections = run_model_inference(img)

    out_msg = {
        "frame_id": data["frame_id"],
        "timestamp": data["timestamp"],
        "detections": detections,
    }
    producer.send(OUTPUT_TOPIC, out_msg)
    producer.flush()

