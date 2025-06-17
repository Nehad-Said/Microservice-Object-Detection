FROM python:3.9-slim

WORKDIR /app

# Copy application files
COPY frame_reader/frame_reader.py .
COPY shared ./shared
# Install system dependencies for OpenCV
RUN apt-get update && apt-get install -y \
    libgl1-mesa-glx \
    libglib2.0-0 \
    && rm -rf /var/lib/apt/lists/*

# Install Python dependencies
RUN pip install --no-cache-dir \
    opencv-python-headless \
    confluent-kafka \
    python-dotenv \
    numpy

CMD ["python", "frame_reader.py"]
