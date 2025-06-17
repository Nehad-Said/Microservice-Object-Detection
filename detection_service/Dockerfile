FROM ultralytics/ultralytics:latest
WORKDIR /app

# Copy application files
COPY detection_service/detection_service.py .
COPY detection_service/models ./models
COPY shared ./shared
# Install system dependencies and Python packages
RUN apt-get update && apt-get install -y libgl1-mesa-glx && \
    pip install --no-cache-dir \
        confluent-kafka \
        opencv-python-headless \
        psycopg2-binary \
        python-dotenv && \
    apt-get clean && rm -rf /var/lib/apt/lists/*

CMD ["python", "detection_service.py"]
