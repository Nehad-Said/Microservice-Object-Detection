-- Create violations database schema
-- This script runs automatically when PostgreSQL container starts

-- Create violations table
CREATE TABLE IF NOT EXISTS violations (
    id SERIAL PRIMARY KEY,
    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    frame_number INTEGER NOT NULL,
    frame_path VARCHAR(255) NOT NULL,
    violation_type VARCHAR(100) NOT NULL,
    violation_description TEXT,
    confidence_score DECIMAL(5,4),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Create bounding_boxes table (one-to-many with violations)
CREATE TABLE IF NOT EXISTS bounding_boxes (
    id SERIAL PRIMARY KEY,
    violation_id INTEGER REFERENCES violations(id) ON DELETE CASCADE,
    x DECIMAL(10,4) NOT NULL,
    y DECIMAL(10,4) NOT NULL,
    width DECIMAL(10,4) NOT NULL,
    height DECIMAL(10,4) NOT NULL,
    class_name VARCHAR(100) NOT NULL,
    confidence DECIMAL(5,4) NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Create detection_labels table
CREATE TABLE IF NOT EXISTS detection_labels (
    id SERIAL PRIMARY KEY,
    violation_id INTEGER REFERENCES violations(id) ON DELETE CASCADE,
    label_name VARCHAR(100) NOT NULL,
    confidence DECIMAL(5,4) NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Create indexes for better performance
CREATE INDEX IF NOT EXISTS idx_violations_timestamp ON violations(timestamp);
CREATE INDEX IF NOT EXISTS idx_violations_frame_number ON violations(frame_number);
CREATE INDEX IF NOT EXISTS idx_violations_type ON violations(violation_type);
CREATE INDEX IF NOT EXISTS idx_bounding_boxes_violation_id ON bounding_boxes(violation_id);
CREATE INDEX IF NOT EXISTS idx_detection_labels_violation_id ON detection_labels(violation_id);

-- Create a view for easy violation queries with all related data
CREATE OR REPLACE VIEW violation_details AS
SELECT 
    v.id,
    v.timestamp,
    v.frame_number,
    v.frame_path,
    v.violation_type,
    v.violation_description,
    v.confidence_score,
    v.created_at,
    -- Aggregate bounding boxes
    COALESCE(
        JSON_AGG(
            JSON_BUILD_OBJECT(
                'x', bb.x,
                'y', bb.y,
                'width', bb.width,
                'height', bb.height,
                'class_name', bb.class_name,
                'confidence', bb.confidence
            )
        ) FILTER (WHERE bb.id IS NOT NULL), 
        '[]'::json
    ) AS bounding_boxes,
    -- Aggregate labels
    COALESCE(
        JSON_AGG(
            JSON_BUILD_OBJECT(
                'label_name', dl.label_name,
                'confidence', dl.confidence
            )
        ) FILTER (WHERE dl.id IS NOT NULL),
        '[]'::json
    ) AS labels
FROM violations v
LEFT JOIN bounding_boxes bb ON v.id = bb.violation_id
LEFT JOIN detection_labels dl ON v.id = dl.violation_id
GROUP BY v.id, v.timestamp, v.frame_number, v.frame_path, 
         v.violation_type, v.violation_description, v.confidence_score, v.created_at
ORDER BY v.timestamp DESC;

-- Insert some sample data for testing
INSERT INTO violations (frame_number, frame_path, violation_type, violation_description, confidence_score) 
VALUES 
    (1, '/app/violations/violation_20241215-120000_frame_1.jpg', 'hand_without_scooper', 'Hand detected taking ingredient without scooper', 0.9500),
    (156, '/app/violations/violation_20241215-120030_frame_156.jpg', 'hand_without_scooper', 'Hand detected placing ingredient on pizza without scooper', 0.8750);

-- Grant permissions (if needed for additional users)
GRANT ALL PRIVILEGES ON ALL TABLES IN SCHEMA public TO postgres;
GRANT ALL PRIVILEGES ON ALL SEQUENCES IN SCHEMA public TO postgres;

-- Create a function to update the updated_at timestamp
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = CURRENT_TIMESTAMP;
    RETURN NEW;
END;
$$ language 'plpgsql';

-- Create trigger to automatically update updated_at
CREATE TRIGGER update_violations_updated_at BEFORE UPDATE ON violations
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

-- Create a function to get violation statistics
CREATE OR REPLACE FUNCTION get_violation_stats()
RETURNS TABLE(
    total_violations BIGINT,
    violations_today BIGINT,
    violations_this_week BIGINT,
    most_common_violation VARCHAR(100),
    avg_confidence DECIMAL(5,4)
) AS $$
BEGIN
    RETURN QUERY
    SELECT 
        COUNT(*) as total_violations,
        COUNT(*) FILTER (WHERE DATE(timestamp) = CURRENT_DATE) as violations_today,
        COUNT(*) FILTER (WHERE timestamp >= DATE_TRUNC('week', CURRENT_DATE)) as violations_this_week,
        MODE() WITHIN GROUP (ORDER BY violation_type) as most_common_violation,
        AVG(confidence_score) as avg_confidence
    FROM violations;
END;
$$ LANGUAGE plpgsql;
