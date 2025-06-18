from fastapi import FastAPI, WebSocket
from fastapi.responses import FileResponse
import os, cv2, asyncio, json, base64

app = FastAPI()

@app.get("/")
async def index():
    return FileResponse("frontend/index.html")

@app.websocket("/video_feed")
async def video_feed(ws: WebSocket):
    await ws.accept()

    cap = cv2.VideoCapture("video/pizza_monitoring.mp4")

    while cap.isOpened():
        ret, frame = cap.read()
        if not ret:
            break

        # Encode frame to base64
        _, buffer = cv2.imencode('.jpg', frame)
        frame_b64 = base64.b64encode(buffer).decode()

        # Just send the frame; detections can be streamed from Kafka later
        await ws.send_text(json.dumps({
            "frame_b64": frame_b64,
            "detections": [],
            "violation_count": 0
        }))
        await asyncio.sleep(0.1)

    cap.release()

