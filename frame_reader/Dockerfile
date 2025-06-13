FROM python:3.9-slim

WORKDIR /app

COPY frame_reader.py .
COPY video/pizza_monitoring.mp4 ./pizza_monitoring.mp4

RUN pip install opencv-python-headless confluent-kafka

CMD ["python", "frame_reader.py"]

