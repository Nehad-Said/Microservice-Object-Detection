FROM python:3.9-slim

WORKDIR /app

COPY streaming_service.py .

RUN pip install fastapi uvicorn confluent-kafka opencv-python-headless numpy requests websockets

CMD ["python", "streaming_service.py"]
