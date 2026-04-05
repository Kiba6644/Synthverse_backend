import random
from datetime import datetime
from flask import Blueprint, request, jsonify
from flask_sqlalchemy import SQLAlchemy
from twilio.twiml.messaging_response import MessagingResponse

# Initialize db instance
db = SQLAlchemy()

# Models
class UserEvent(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    event_name = db.Column(db.String(255), nullable=False)
    location = db.Column(db.String(255), nullable=False)
    date = db.Column(db.String(100), nullable=False)
    expected_crowd = db.Column(db.Integer, nullable=False)
    traffic_score = db.Column(db.Integer, nullable=True)
    status = db.Column(db.String(20), default='pending')
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

def calculate_traffic_score(location, expected_crowd):
    """
    Simulates a traffic score using the location/pincode text and crowd size.
    """
    base_score = 15
    # Use sum of characters in location/pincode to create some pseudo-randomness
    location_hash_factor = sum(ord(c) for c in str(location)) % 30
    crowd_factor = expected_crowd / 100.0  # +1 score per 100 people
    
    raw_score = base_score + location_hash_factor + crowd_factor
    return int(max(1, min(100, raw_score)))

# Blueprint for Traffic routes
traffic_bp = Blueprint('traffic', __name__)

@traffic_bp.route("/api/events", methods=["GET"])
def get_approved_events():
    """
    Returns all approved user events.
    """
    approved_user_events = UserEvent.query.filter_by(status='approved').all()
    events = []
    for e in approved_user_events:
        events.append({
            "id": e.id,
            "event_name": e.event_name,
            "date": e.date,
            "venue_type": e.location,
            "expected_crowd": e.expected_crowd,
            "traffic_score": e.traffic_score
        })
    return jsonify({"status": "success", "route_type": "approved_events", "data": {"events": events}})

@traffic_bp.route("/api/whatsapp/webhook", methods=["POST"])
def whatsapp_webhook():
    """
    Twilio Webhook endpoint to mark new event to be reviewed.
    """
    incoming_msg = request.values.get('Body', '').strip()
    resp = MessagingResponse()
    msg = resp.message()
    
    parts = incoming_msg.split()
    if len(parts) >= 4:
        event_name = parts[0]
        location = parts[1]
        date = parts[2]
        try: 
            expected_crowd = int(parts[3])
        except ValueError: 
            expected_crowd = 100
            
        score = calculate_traffic_score(location, expected_crowd)
        new_event = UserEvent(
            event_name=event_name, 
            location=location, 
            date=date, 
            expected_crowd=expected_crowd, 
            traffic_score=score
        )
        db.session.add(new_event)
        db.session.commit()
        msg.body(f"Event '{event_name}' registered successfully and is pending review! The projected Traffic Severity Score is: {score}/100.")
    else:
        msg.body("Invalid format. Please send: <EventName> <Location_Pincode> <YYYY-MM-DD> <ExpectedCrowd> (e.g. 'TechFest 560070 2026-05-10 2000')")
    return str(resp)

@traffic_bp.route("/api/user_events", methods=["GET"])
def get_pending_user_events():
    """
    Returns all pending user events.
    """
    events = UserEvent.query.filter_by(status='pending').all()
    event_list = [{
        "id": e.id, 
        "event_name": e.event_name, 
        "location": e.location,
        "date": e.date, 
        "expected_crowd": e.expected_crowd,
        "traffic_score": e.traffic_score, 
        "created_at": e.created_at.strftime("%Y-%m-%d %H:%M:%S")
    } for e in events]
    return jsonify({"status": "success", "route_type": "pending_events", "data": event_list})

@traffic_bp.route("/api/user_events/<int:id>/status", methods=["POST"])
def update_user_event_status(id):
    """
    Updates the status of a user event (approved/rejected).
    """
    event = UserEvent.query.get(id)
    if not event: 
        return jsonify({"error": "Event not found"}), 404
        
    req_data = request.get_json(silent=True) or {}
    new_status = req_data.get("status")
    
    if new_status in ["approved", "rejected"]:
        event.status = new_status
        db.session.commit()
        return jsonify({"status": "success", "message": f"Event {new_status}"}), 200
    return jsonify({"error": "Invalid status payload. Use 'approved' or 'rejected'."}), 400
