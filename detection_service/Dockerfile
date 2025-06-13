FROM ultralytics/ultralytics:latest

WORKDIR /app

COPY detection_service.py .
COPY models ./models

# Install libgl1-mesa-glx and Python dependencies
RUN apt-get update && apt-get install -y libgl1-mesa-glx && \
    pip install --no-cache-dir confluent-kafka opencv-python-headless && \
    apt-get clean && rm -rf /var/lib/apt/lists/*

CMD ["python", "detection_service.py"]

