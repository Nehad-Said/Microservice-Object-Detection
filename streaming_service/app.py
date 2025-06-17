# app.py
from fastapi import FastAPI, WebSocket
from fastapi.responses import HTMLResponse

app = FastAPI()

@app.get("/violations/count")
def get_violation_count():
    # Dummy value or fetch from DB
    return {"violations": 42}

@app.websocket("/video_feed")
async def video_feed(ws: WebSocket):
    await ws.accept()
    while True:
        # send dummy or real video frame from Kafka or local queue
        await ws.send_text("frame or encoded image")

