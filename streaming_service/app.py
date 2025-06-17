# streaming_service/app.py
from fastapi import FastAPI, WebSocket
from fastapi.responses import HTMLResponse
import asyncio
import base64
import cv2
import json

app = FastAPI()

@app.get("/violations/count")
def get_violation_count():
    return {"violations": 42}

@app.websocket("/video_feed")
async def video_feed(ws: WebSocket):
    await ws.accept()
    
    cap = cv2.VideoCapture("video/pizza_monitoring.mp4")  # update path if needed
    while cap.isOpened():
        ret, frame = cap.read()
        if not ret:
            break

        # Encode frame to base64
        _, buffer = cv2.imencode('.jpg', frame)
        frame_b64 = base64.b64encode(buffer).decode()

        # Dummy detections
        result = {
            "frame_b64": frame_b64,
            "detections": [
                {"bbox": [100, 100, 200, 200], "label": "Pizza"}
            ],
            "violation_count": 1
        }

        await ws.send_text(json.dumps(result))
        await asyncio.sleep(0.1)

    cap.release()

