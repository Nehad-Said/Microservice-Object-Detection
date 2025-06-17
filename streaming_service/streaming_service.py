import os
import json
import asyncio
import cv2
import numpy as np
from fastapi import FastAPI, WebSocket
from fastapi.responses import StreamingResponse, JSONResponse
from confluent_kafka import Consumer
from starlette.middleware.cors import CORSMiddleware

app = FastAPI()

# CORS (if needed for frontends)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# Kafka config
KAFKA_SERVERS = os.getenv("KAFKA_BOOTSTRAP_SERVERS", "localhost:9092")
DETECTION_TOPIC = os.getenv("DETECTION_TOPIC", "frames.detections")

# Detection queue for WebSocket clients
detection_queue = asyncio.Queue()
latest_detection = None  # Store the latest detection for REST & MJPEG

# Kafka consumer setup
consumer_config = {
    'bootstrap.servers': KAFKA_SERVERS,
    'group.id': 'streaming-service-group',
    'auto.offset.reset': 'latest',
    'enable.auto.commit': True,
}
consumer = Consumer(consumer_config)
consumer.subscribe([DETECTION_TOPIC])

@app.on_event("startup")
async def start_kafka_consumer():
    async def consume():
        global latest_detection
        while True:
            msg = consumer.poll(1.0)
            if msg is None:
                continue
            if msg.error():
                print(f"[streaming_service] Kafka error: {msg.error()}")
                continue
            try:
                data = json.loads(msg.value().decode("utf-8"))
                await detection_queue.put(data)
                latest_detection = data
            except Exception as e:
                print(f"[streaming_service] Error processing message: {e}")
    asyncio.create_task(consume())
    print("[streaming_service] Kafka consumer started")

@app.get("/latest")
async def get_latest():
    """Return latest detection (JSON)"""
    if latest_detection:
        return JSONResponse(content=latest_detection)
    return JSONResponse(content={"message": "No detection yet"}, status_code=404)

@app.get("/video_feed")
async def video_feed():
    """MJPEG stream showing latest frame with bounding boxes"""
    async def stream():
        while True:
            if latest_detection and "detections" in latest_detection:
                # Simulate blank frame for example; replace with real frame source
                frame = np.zeros((480, 640, 3), dtype=np.uint8)

                for det in latest_detection["detections"]:
                    x1, y1, x2, y2 = map(int, det["bbox"])
                    label = det["label"]
                    confidence = det["confidence"]
                    cv2.rectangle(frame, (x1, y1), (x2, y2), (0, 255, 0), 2)
                    cv2.putText(frame, f"{label} {confidence:.2f}", (x1, y1 - 10),
                                cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 255, 255), 1)

                ret, buffer = cv2.imencode(".jpg", frame)
                frame_bytes = buffer.tobytes()

                yield (b"--frame\r\n"
                       b"Content-Type: image/jpeg\r\n\r\n" + frame_bytes + b"\r\n")
            await asyncio.sleep(0.1)
    return StreamingResponse(stream(), media_type="multipart/x-mixed-replace; boundary=frame")

@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await websocket.accept()
    print("[streaming_service] WebSocket connected")
    try:
        while True:
            data = await detection_queue.get()
            await websocket.send_json(data)
    except Exception as e:
        print(f"[streaming_service] WebSocket error: {e}")
    finally:
        print("[streaming_service] WebSocket disconnected")

