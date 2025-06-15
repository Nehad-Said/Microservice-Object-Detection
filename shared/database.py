import os
import psycopg2
from psycopg2.extras import RealDictCursor
import logging

logger = logging.getLogger(__name__)

class DatabaseManager:
    def __init__(self):
        self.connection = None
        self.database_url = os.getenv('DATABASE_URL', 
            'postgresql://postgres:postgres123@postgres:5432/violations_db')
    
    def connect(self):
        """Establish database connection"""
        try:
            self.connection = psycopg2.connect(
                self.database_url,
                cursor_factory=RealDictCursor
            )
            logger.info("Database connection established")
            return self.connection
        except Exception as e:
            logger.error(f"Database connection failed: {e}")
            raise
    
    def get_connection(self):
        """Get database connection"""
        if not self.connection or self.connection.closed:
            self.connect()
        return self.connection
    
    def insert_violation(self, frame_number, frame_path, violation_type, 
                        violation_description, confidence_score, bounding_boxes=None, labels=None):
        """Insert a new violation record"""
        try:
            conn = self.get_connection()
            with conn.cursor() as cursor:
                # Insert violation
                cursor.execute("""
                    INSERT INTO violations (frame_number, frame_path, violation_type, 
                                          violation_description, confidence_score)
                    VALUES (%s, %s, %s, %s, %s)
                    RETURNING id
                """, (frame_number, frame_path, violation_type, violation_description, confidence_score))
                
                violation_id = cursor.fetchone()['id']
                
                # Insert bounding boxes if provided
                if bounding_boxes:
                    for bbox in bounding_boxes:
                        cursor.execute("""
                            INSERT INTO bounding_boxes (violation_id, x, y, width, height, class_name, confidence)
                            VALUES (%s, %s, %s, %s, %s, %s, %s)
                        """, (violation_id, bbox['x'], bbox['y'], bbox['width'], 
                             bbox['height'], bbox['class_name'], bbox['confidence']))
                
                # Insert labels if provided
                if labels:
                    for label in labels:
                        cursor.execute("""
                            INSERT INTO detection_labels (violation_id, label_name, confidence)
                            VALUES (%s, %s, %s)
                        """, (violation_id, label['label_name'], label['confidence']))
                
                conn.commit()
                logger.info(f"Violation inserted with ID: {violation_id}")
                return violation_id
                
        except Exception as e:
            logger.error(f"Failed to insert violation: {e}")
            if conn:
                conn.rollback()
            raise
    
    def get_violations(self, limit=100):
        """Get recent violations"""
        try:
            conn = self.get_connection()
            with conn.cursor() as cursor:
                cursor.execute("""
                    SELECT * FROM violation_details 
                    ORDER BY timestamp DESC 
                    LIMIT %s
                """, (limit,))
                return cursor.fetchall()
        except Exception as e:
            logger.error(f"Failed to get violations: {e}")
            raise
    
    def get_violation_stats(self):
        """Get violation statistics"""
        try:
            conn = self.get_connection()
            with conn.cursor() as cursor:
                cursor.execute("SELECT * FROM get_violation_stats()")
                return cursor.fetchone()
        except Exception as e:
            logger.error(f"Failed to get violation stats: {e}")
            raise
    
    def close(self):
        """Close database connection"""
        if self.connection:
            self.connection.close()
            logger.info("Database connection closed")

# Global database manager instance
db_manager = DatabaseManager()
