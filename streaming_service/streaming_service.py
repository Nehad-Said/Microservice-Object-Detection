import sys
import os
sys.path.append('/app/shared')

import asyncio
import json
import base64
import cv2
import numpy as np
from datetime import datetime
from confluent_kafka import Consumer
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse
import uvicorn
import logging
from database import db_manager

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(title="Food Safety Violation Monitoring API")

# Global variables
active_connections = []
latest_frame = None
violation_count = 0
kafka_consumer = None

# Initialize database
try:
    db_manager.connect()
    logger.info("Database connected successfully")
except Exception as e:
    logger.error(f"Database connection failed: {e}")

class ConnectionManager:
    def __init__(self):
        self.active_connections: list[WebSocket] = []

    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.active_connections.append(websocket)
        logger.info(f"WebSocket connected. Total connections: {len(self.active_connections)}")

    def disconnect(self, websocket: WebSocket):
        if websocket in self.active_connections:
            self.active_connections.remove(websocket)
        logger.info(f"WebSocket disconnected. Total connections: {len(self.active_connections)}")

    async def broadcast(self, message: str):
        disconnected = []
        for connection in self.active_connections:
            try:
                await connection.send_text(message)
            except Exception as e:
                logger.error(f"Error sending to WebSocket: {e}")
                disconnected.append(connection)
        
        # Remove disconnected clients
        for conn in disconnected:
            self.disconnect(conn)

manager = ConnectionManager()

# Kafka consumer setup
async def setup_kafka_consumer():
    global kafka_consumer
    kafka_servers = os.getenv('KAFKA_BOOTSTRAP_SERVERS', 'kafka:9092')
    
    for attempt in range(20):
        try:
            kafka_consumer = Consumer({
                'bootstrap.servers': kafka_servers,
                'group.id': 'streaming_service',
                'auto.offset.reset': 'latest',  # Only get new messages
                'enable.auto.commit': True,
            })
            kafka_consumer.subscribe(['detections'])
            logger.info("Kafka consumer connected successfully")
            return
        except Exception as e:
            logger.error(f"Kafka connection attempt {attempt + 1} failed: {e}")
            await asyncio.sleep(5)
    
    raise Exception("Failed to connect to Kafka after multiple attempts")

# Background task to consume Kafka messages
async def consume_detections():
    global latest_frame, violation_count
    
    while True:
        try:
            if kafka_consumer is None:
                await asyncio.sleep(1)
                continue
                
            # Poll for messages (non-blocking)
            msg = kafka_consumer.poll(1.0)
            
            if msg is None:
                await asyncio.sleep(0.1)
                continue
                
            if msg.error():
                logger.error(f"Kafka consumer error: {msg.error()}")
                continue
            
            # Parse detection data
            try:
                detection_data = json.loads(msg.value().decode('utf-8'))
                violation_count = detection_data.get('violation_count', 0)
                
                # Store latest detection data
                latest_frame = detection_data
                
                # Broadcast to all WebSocket clients
                await manager.broadcast(json.dumps(detection_data))
                
            except json.JSONDecodeError as e:
                logger.error(f"Error parsing detection data: {e}")
                continue
                
        except Exception as e:
            logger.error(f"Error in consume_detections: {e}")
            await asyncio.sleep(1)

# REST API Endpoints
@app.get("/")
async def root():
    return {"message": "Food Safety Violation Monitoring API", "status": "running"}

@app.get("/violations/count")
async def get_violation_count():
    """Get total violation count"""
    try:
        global violation_count
        # Also get from database for accuracy
        stats = db_manager.get_violation_stats()
        db_count = stats['total_violations'] if stats else 0
        
        return {
            "total_violations": max(violation_count, db_count),
            "current_session": violation_count,
            "database_total": db_count
        }
    except Exception as e:
        logger.error(f"Error getting violation count: {e}")
        return {"total_violations": violation_count, "error": str(e)}

@app.get("/violations/list")
async def get_violations(limit: int = 50):
    """Get list of violations"""
    try:
        violations = db_manager.get_violations(limit=limit)
        return {
            "violations": violations,
            "count": len(violations)
        }
    except Exception as e:
        logger.error(f"Error getting violations: {e}")
        return {"violations": [], "error": str(e)}

@app.get("/violations/statistics")
async def get_violation_statistics():
    """Get violation statistics"""
    try:
        stats = db_manager.get_violation_stats()
        return stats if stats else {}
    except Exception as e:
        logger.error(f"Error getting violation statistics: {e}")
        return {"error": str(e)}

@app.get("/stream/metadata")
async def get_stream_metadata():
    """Get stream metadata"""
    return {
        "active_connections": len(manager.active_connections),
        "violation_count": violation_count,
        "kafka_status": "connected" if kafka_consumer else "disconnected"
    }

# WebSocket endpoint for live streaming
@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await manager.connect(websocket)
    try:
        # Send latest frame immediately if available
        if latest_frame:
            await websocket.send_text(json.dumps(latest_frame))
            
        while True:
            # Keep connection alive and handle client messages
            try:
                # Wait for client messages (ping/pong, etc.)
                await asyncio.wait_for(websocket.receive_text(), timeout=1.0)
            except asyncio.TimeoutError:
                # No message received, continue
                pass
            except WebSocketDisconnect:
                break
                
    except WebSocketDisconnect:
        pass
    finally:
        manager.disconnect(websocket)

# Serve static files (for frontend)
@app.get("/frontend")
async def get_frontend():
    """Serve the frontend HTML"""
    html_content = """
    <!DOCTYPE html>
    <html>
    <head>
        <title>Food Safety Violation Monitor</title>
        <style>
            body { font-family: Arial, sans-serif; margin: 20px; background-color: #f5f5f5; }
            .container { max-width: 1200px; margin: 0 auto; }
            .header { background: #2c3e50; color: white; padding: 20px; border-radius: 10px; margin-bottom: 20px; }
            .stats { display: flex; justify-content: space-around; margin: 20px 0; }
            .stat-box { background: white; padding: 20px; border-radius: 10px; text-align: center; box-shadow: 0 2px 10px rgba(0,0,0,0.1); }
            .stat-number { font-size: 2em; font-weight: bold; color: #e74c3c; }
            .canvas-container { background: white; padding: 20px; border-radius: 10px; box-shadow: 0 2px 10px rgba(0,0,0,0.1); }
            canvas { border: 2px solid #34495e; border-radius: 5px; max-width: 100%; }
            .status { margin: 10px 0; padding: 10px; border-radius: 5px; }
            .status.connected { background: #d4edda; color: #155724; }
            .status.disconnected { background: #f8d7da; color: #721c24; }
            .detection-list { background: white; margin-top: 20px; padding: 20px; border-radius: 10px; box-shadow: 0 2px 10px rgba(0,0,0,0.1); }
        </style>
    </head>
    <body>
        <div class="container">
            <div class="header">
                <h1>🍕 Food Safety Violation Monitor</h1>
                <p>Real-time hand hygiene compliance monitoring</p>
            </div>
            
            <div class="stats">
                <div class="stat-box">
                    <div class="stat-number" id="violation-count">0</div>
                    <div>Total Violations</div>
                </div>
                <div class="stat-box">
                    <div class="stat-number" id="frame-count">0</div>
                    <div>Frames Processed</div>
                </div>
                <div class="stat-box">
                    <div class="stat-number" id="detection-count">0</div>
                    <div>Objects Detected</div>
                </div>
            </div>
            
            <div id="connection-status" class="status disconnected">
                🔴 Disconnected from stream
            </div>
            
            <div class="canvas-container">
                <canvas id="video-canvas" width="640" height="480"></canvas>
            </div>
            
            <div class="detection-list">
                <h3>Recent Detections</h3>
                <div id="detections-log"></div>
            </div>
        </div>

        <script>
            const canvas = document.getElementById('video-canvas');
            const ctx = canvas.getContext('2d');
            const statusDiv = document.getElementById('connection-status');
            const violationCountEl = document.getElementById('violation-count');
            const frameCountEl = document.getElementById('frame-count');
            const detectionCountEl = document.getElementById('detection-count');
            const detectionsLog = document.getElementById('detections-log');
            
            let ws;
            let reconnectAttempts = 0;
            const maxReconnectAttempts = 5;
            
            function connectWebSocket() {
                const wsUrl = `ws://${window.location.host}/ws`;
                ws = new WebSocket(wsUrl);
                
                ws.onopen = function(event) {
                    console.log('WebSocket connected');
                    statusDiv.textContent = '🟢 Connected to live stream';
                    statusDiv.className = 'status connected';
                    reconnectAttempts = 0;
                };
                
                ws.onmessage = function(event) {
                    try {
                        const data = JSON.parse(event.data);
                        updateDisplay(data);
                    } catch (e) {
                        console.error('Error parsing WebSocket data:', e);
                    }
                };
                
                ws.onclose = function(event) {
                    console.log('WebSocket disconnected');
                    statusDiv.textContent = '🔴 Disconnected from stream';
                    statusDiv.className = 'status disconnected';
                    
                    // Attempt to reconnect
                    if (reconnectAttempts < maxReconnectAttempts) {
                        reconnectAttempts++;
                        setTimeout(connectWebSocket, 3000);
                    }
                };
                
                ws.onerror = function(error) {
                    console.error('WebSocket error:', error);
                };
            }
            
            function updateDisplay(data) {
                // Update counters
                violationCountEl.textContent = data.violation_count || 0;
                frameCountEl.textContent = data.frame_count || 0;
                detectionCountEl.textContent = data.detections ? data.detections.length : 0;
                
                // Draw detection info (since we don't have actual frame data)
                ctx.fillStyle = '#f8f9fa';
                ctx.fillRect(0, 0, canvas.width, canvas.height);
                
                ctx.fillStyle = '#2c3e50';
                ctx.font = '16px Arial';
                ctx.fillText(`Frame: ${data.frame_count || 0}`, 20, 30);
                ctx.fillText(`Violations: ${data.violation_count || 0}`, 20, 60);
                ctx.fillText(`Timestamp: ${new Date(data.timestamp).toLocaleTimeString()}`, 20, 90);
                
                // Draw detections info
                if (data.detections && data.detections.length > 0) {
                    ctx.fillText('Detected Objects:', 20, 130);
                    data.detections.forEach((detection, index) => {
                        const y = 160 + (index * 25);
                        ctx.fillText(`• ${detection.label} (${(detection.confidence * 100).toFixed(1)}%)`, 30, y);
                    });
                }
                
                // Show violation alert
                if (data.violation) {
                    ctx.fillStyle = '#e74c3c';
                    ctx.font = 'bold 20px Arial';
                    ctx.fillText('⚠️ VIOLATION DETECTED!', 20, canvas.height - 40);
                    ctx.fillText(data.violation_description || 'Food safety violation', 20, canvas.height - 15);
                }
                
                // Update detections log
                if (data.detections && data.detections.length > 0) {
                    const logEntry = document.createElement('div');
                    logEntry.innerHTML = `
                        <strong>${new Date(data.timestamp).toLocaleTimeString()}</strong>: 
                        ${data.detections.map(d => `${d.label} (${(d.confidence * 100).toFixed(1)}%)`).join(', ')}
                        ${data.violation ? '<span style="color: red;">⚠️ VIOLATION</span>' : ''}
                    `;
                    detectionsLog.insertBefore(logEntry, detectionsLog.firstChild);
                    
                    // Keep only last 20 entries
                    while (detectionsLog.children.length > 20) {
                        detectionsLog.removeChild(detectionsLog.lastChild);
                    }
                }
            }
            
            // Start WebSocket connection
            connectWebSocket();
        </script>
    </body>
    </html>
    """
    return HTMLResponse(content=html_content)

# Startup event
@app.on_event("startup")
async def startup_event():
    logger.info("Starting streaming service...")
    
    # Setup Kafka consumer
    await setup_kafka_consumer()
    
    # Start background task to consume detections
    asyncio.create_task(consume_detections())
    
    logger.info("Streaming service started successfully")

if __name__ == "__main__":
    uvicorn.run(
        "streaming_service:app",
        host="0.0.0.0",
        port=8001,
        reload=False,
        log_level="info"
    )
