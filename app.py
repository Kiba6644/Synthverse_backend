from flask import Flask, jsonify
from traffic import traffic_bp, db
from layer_3 import layer_3_bp

app = Flask(__name__)

# Database Setup
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///hackathon.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
db.init_app(app)

# Create tables before first request or explicitly
with app.app_context():
    db.create_all()

# Register blueprints
app.register_blueprint(traffic_bp)
app.register_blueprint(layer_3_bp)

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
    
    # Generate random scores for hallway nodes (0 to 100)
    for node in NODES_DATA["hallway_nodes"]:
        sensor_data["hallway"].append({
            "id": node["id"],
            "score": random.randint(0, 100)
        })
        
    # Generate random scores for exits/lifts
    all_exits = NODES_DATA["exits"] + NODES_DATA["lifts"]
    for node in all_exits:
        sensor_data["exits"].append({
            "id": node["id"],
            "score": random.randint(0, 100)
        })
        
    # Ensure at least one exit is "open" (score < 100)
    # If all happen to be 100, force one to be 0
    all_exits_blocked = all(exit_node["score"] == 100 for exit_node in sensor_data["exits"])
    if all_exits_blocked and len(sensor_data["exits"]) > 0:
        sensor_data["exits"][0]["score"] = 0
        
    # Actually, to make it more realistic and ensure it works out well, let's explicitly pick one
    # exit/lift to be guaranteed < 100 (e.g., 0-50).
    guaranteed_open_idx = random.randint(0, len(sensor_data["exits"]) - 1)
    sensor_data["exits"][guaranteed_open_idx]["score"] = random.randint(0, 50)
    
    return jsonify(sensor_data)

if __name__ == '__main__':
    app.run(debug=True, port=5000)
