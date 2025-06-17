from fastapi import FastAPI, WebSocket
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
import os, cv2, asyncio, json, base64

app = FastAPI()


@app.get("/")
async def index():
    return FileResponse("frontend/index.html")

@app.websocket("/video_feed")
async def video_feed(ws: WebSocket):
    await ws.accept()
    cap = cv2.VideoCapture("video/pizza_monitoring.mp4")  # ensure path is correct

    while cap.isOpened():
        ret, frame = cap.read()
        if not ret:
            break

        _, buffer = cv2.imencode('.jpg', frame)
        frame_b64 = base64.b64encode(buffer).decode()

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

