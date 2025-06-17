FROM python:3.9-slim

WORKDIR /app

COPY streaming_service/streaming_service.py .
COPY shared ./shared
COPY streaming_service/app.py . 
COPY frontend ./frontend 

RUN apt-get update && apt-get install -y \
    libgl1-mesa-glx \
    libglib2.0-0 \
    && rm -rf /var/lib/apt/lists/*

RUN pip install --no-cache-dir \
    fastapi \
    uvicorn \
    confluent-kafka \
    opencv-python-headless \
    numpy \
    websockets \
    python-dotenv \
    psycopg2-binary

# Add if you rely on shared imports
ENV PYTHONPATH=/app

CMD ["uvicorn", "app:app", "--host", "0.0.0.0", "--port", "8000"]

