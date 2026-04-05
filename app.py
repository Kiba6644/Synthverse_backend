from flask import Flask, jsonify
from flask_cors import CORS

from traffic import traffic_bp, db
from layer_3 import layer_3_bp
from layer_4_api import layer_4_bp

app = Flask(__name__)
CORS(app)

app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///hackathon.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
db.init_app(app)
with app.app_context():
    db.create_all()

# Register blueprints
app.register_blueprint(traffic_bp)
app.register_blueprint(layer_3_bp)
app.register_blueprint(layer_4_bp)

# Data based on the provided JSON
NODES_DATA = {
  "map_metadata": {
    "units": "normalized_percentage",
    "origin": "top-left",
    "total_width": 100,
    "total_height": 100
  },
  "exits": [
    { "id": "exit_top_center", "label": "Exit (Near Lab-02)", "x": 58.8, "y": 8.5 },
    { "id": "exit_mid_left", "label": "Exit (Near Restrooms)", "x": 12.5, "y": 33.2 },
    { "id": "exit_bottom_left", "label": "Exit (Near Lab-03)", "x": 11.5, "y": 83.8 }
  ],
  "lifts": [
    { "id": "lift_01_left", "label": "Lift-01 (Bottom Left)", "x": 18.5, "y": 83.8 },
    { "id": "lift_02_left", "label": "Lift-02 (Bottom Left)", "x": 24.2, "y": 83.8 },
    { "id": "lift_01_right", "label": "Lift-01 (Bottom Right)", "x": 74.8, "y": 95.1 },
    { "id": "lift_02_right", "label": "Lift-02 (Bottom Right)", "x": 83.1, "y": 95.1 }
  ],
  "hallway_nodes": [
    { "id": "node_entrance", "label": "You Are Here / Entrance", "x": 36.2, "y": 89.2 },
    { "id": "node_bottom_left_corner", "label": "Junction Bottom Left", "x": 31.0, "y": 89.2 },
    { "id": "node_mid_left_corridor", "label": "Mid Corridor Left", "x": 31.0, "y": 55.0 },
    { "id": "node_top_left_corner", "label": "Junction Top Left", "x": 31.0, "y": 21.8 },
    { "id": "node_top_mid_corridor", "label": "Top Corridor Mid", "x": 44.5, "y": 21.8 },
    { "id": "node_top_junction_exit", "label": "Junction Top Exit", "x": 58.8, "y": 21.8 },
    { "id": "node_top_right_corner", "label": "Junction Top Right", "x": 66.5, "y": 21.8 },
    { "id": "node_mid_right_corridor", "label": "Mid Corridor Right", "x": 66.5, "y": 55.0 },
    { "id": "node_bottom_right_junction", "label": "Junction Bottom Right", "x": 66.5, "y": 91.5 }
  ]
}

import random

import serial
import time
import atexit

# Serial Configuration
SERIAL_PORT = 'COM10'
BAUD_RATE = 9600
ser = None

def cleanup():
    global ser
    if ser and ser.is_open:
        print(f"Releasing {SERIAL_PORT}...")
        ser.close()

# Register the cleanup handler
atexit.register(cleanup)

try:
    ser = serial.Serial(SERIAL_PORT, BAUD_RATE, timeout=2)
    time.sleep(2) # Wait for Arduino to reset
    print(f"CONNECTED TO CONTROL MATRIX ON {SERIAL_PORT}")
except Exception as e:
    print(f"CRITICAL: Failed to link with {SERIAL_PORT}. {e}")

@app.route('/api/nodes', methods=['GET'])
def get_all_nodes():    
    return jsonify({
        "exits": NODES_DATA["exits"] + NODES_DATA["lifts"],
        "hallway": NODES_DATA["hallway_nodes"]
    })

@app.route('/api/sensors', methods=['GET'])
def get_sensor_data():
    sensor_data = {
        "hallway": [],
        "exits": []
    }
    
    # 1. Fetch Real-time data from Arduino for the specific junction node
    arduino_value = 50 # Default baseline
    if ser and ser.is_open:
        try:
            ser.write(b"dat\n")
            line = ser.readline().decode('utf-8').strip()
            if line:
                arduino_value = int(float(line))
        except Exception as e:
            print(f"Serial Error: {e}")

    for node in NODES_DATA["hallway_nodes"]:
        score = 31
        if node["id"] == "node_bottom_left_corner":
            score = arduino_value
            
        sensor_data["hallway"].append({
            "id": node["id"],
            "score": score
        })
        
    for node in NODES_DATA["exits"] + NODES_DATA["lifts"]:
        sensor_data["exits"].append({
            "id": node["id"],
            "score": 31
        })
        
    return jsonify(sensor_data)

@app.route('/api/<id>', methods=['POST'])
def authorize_egress_node(id):
    """
    Triggers physical LED indicators for safe egress paths.
    """
    if not ser or not ser.is_open:
        return jsonify({"error": "No physical link to control matrix available."}), 503
        
    try:
        # Define high-priority egress targets
        pin_8_targets = ['lift_01_left', 'lift_02_left', 'exit_bottom_left']
        pin_9_targets = ["Lift-01 (Bottom Right)", "Lift-02 (Bottom Right)" ]
        
        target_cmd = "off\n"
        if id in pin_8_targets:
            target_cmd = "cmd_8\n"
        elif id in pin_9_targets:
            target_cmd = "cmd_9\n"
            
        ser.write(target_cmd.encode())
        response = ser.readline().decode('utf-8').strip()
        
        return jsonify({
            "status": "success",
            "authorized_id": id,
            "physical_signal": response
        }), 200
    except Exception as e:
        return jsonify({"error": f"Authorization signal interrupt: {e}"}), 500

if __name__ == '__main__':
    app.run(debug=True, port=5000, host="0.0.0.0", use_reloader=False)
