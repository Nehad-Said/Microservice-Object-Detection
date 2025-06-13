import cv2
import base64
import json
import time
import os
import numpy as np
import requests
import websockets
import asyncio

VIDEO_PATH = "../video/Sah b3dha ghalt.mp4"
DETECTION_URL = "http://detection_service:5000/detect"
WS_CLIENTS = set()
VIOLATIONS_DIR = "../violations"

os.makedirs(VIOLATIONS_DIR, exist_ok=True)

def read_frames():
    cap = cv2.VideoCapture(VIDEO_PATH)
    while cap.isOpened():
        ret, frame = cap.read()
        if not ret:
            break
        yield frame
    cap.release()

def encode_frame(frame):
    _, buffer = cv2.imencode('.jpg', frame)
    return base64.b64encode(buffer).decode('utf-8')

def send_to_detection(frame):
    _, img_encoded = cv2.imencode('.jpg', frame)
    response = requests.post(
        DETECTION_URL,
        files={"image": ("frame.jpg", img_encoded.tobytes(), "image/jpeg")}
    )
    return response.json()

def save_violation(frame, detections):
    timestamp = time.strftime("%Y%m%d-%H%M%S")
    image_path = os.path.join(VIOLATIONS_DIR, f"violation_{timestamp}.jpg")
    json_path = os.path.join(VIOLATIONS_DIR, f"violation_{timestamp}.json")

    # Save image
    cv2.imwrite(image_path, frame)

    # Save metadata
    with open(json_path, "w") as f:
        json.dump(detections, f, indent=2)

async def stream():
    for frame in read_frames():
        detections = send_to_detection(frame)

        # If violations detected, save them
        if detections.get("violation_count", 0) > 0:
            save_violation(frame, detections)

        data = {
            "frame_b64": encode_frame(frame),
            "violation_count": detections.get("violation_count", 0),
            "detections": detections.get("detections", [])
        }
        for ws in WS_CLIENTS:
            await ws.send(json.dumps(data))
        await asyncio.sleep(0.03)

async def handler(websocket):
    WS_CLIENTS.add(websocket)
    try:
        while True:
            await asyncio.sleep(1)
    finally:
        WS_CLIENTS.remove(websocket)

async def main():
    async with websockets.serve(handler, "0.0.0.0", 8000):
        await stream()

if __name__ == "__main__":
    asyncio.run(main())

