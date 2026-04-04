from flask import Blueprint, request, jsonify
import torch
import os
import sys

# Ensure the layer4_gnn package is accessible for imports
sys.path.append(os.path.join(os.path.dirname(__file__), 'layer4_gnn'))
from gnn_dataset import load_base_graph_state, build_pyg_data, simulate_rerouting
from gnn_model import MaritimeGAT

layer_4_bp = Blueprint('layer_4_bp', __name__)

MODEL_PATH = os.path.join(os.path.dirname(__file__), 'layer4_gnn', 'maritime_gat.pth')

def get_model():
    model = MaritimeGAT()
    try:
        model.load_state_dict(torch.load(MODEL_PATH, map_location=torch.device('cpu'), weights_only=True))
    except Exception as e:
        print(f"Error loading model: {e}")
    model.eval()
    return model

# Global model loading for faster API response
gnn_model = get_model()
nodes_list, base_edges = load_base_graph_state()
node_to_idx = {n: i for i, n in enumerate(nodes_list)}
chokepoint_keywords = ['Strait', 'Canal', 'Hope', 'Bab-el-Mandeb']
is_chokepoint = [any(kw in n for kw in chokepoint_keywords) for n in nodes_list]

@layer_4_bp.route('/api/layer4/simulate', methods=['POST'])
def simulate_disruption():
    req_data = request.get_json() or {}
    # Default to Suez if none provided
    blocked_chokepoint = req_data.get('blocked_chokepoint', 'Suez Canal')
    
    # Handle variations in naming just in case
    available_chokepoints = [n for n, is_cp in zip(nodes_list, is_chokepoint) if is_cp]
    
    if blocked_chokepoint not in nodes_list:
        return jsonify({
            "error": f"Chokepoint '{blocked_chokepoint}' not found in network.",
            "available_chokepoints": available_chokepoints
        }), 400
        
    blocked_idxs = [node_to_idx[blocked_chokepoint]]
    
    # 1. Physics Engine Setup
    simulated_edges, displaced_commodities = simulate_rerouting(base_edges, [blocked_chokepoint])
    
    # 2. PyG Tensor Formatting
    pyg_data = build_pyg_data(nodes_list, node_to_idx, simulated_edges, blocked_idxs, is_chokepoint)
    
    # 3. GAT Inference
    with torch.no_grad():
        preds = gnn_model(pyg_data.x, pyg_data.edge_index, pyg_data.edge_attr)
        
    # 4. Result Formatting
    results = []
    edges_list = list(simulated_edges.items())
    for i, ((src, dst), attrs) in enumerate(edges_list):
        pred_congestion = float(preds[i][0])
        
        # Only highlight routes that actually faced stress or were directly blocked
        if pred_congestion > 1.05 or dst == blocked_chokepoint or src == blocked_chokepoint:
            status = "NORMAL"
            if src == blocked_chokepoint or dst == blocked_chokepoint:
                status = "BLOCKED"
                pred_congestion = 0.0
            elif pred_congestion >= 1.5:
                status = "CRITICAL (Overcapacity)"
            elif pred_congestion > 1.05:
                status = "WARNING (Congested)"
                
            percent_increase = max(0, int((pred_congestion - 1.0) * 100))
            
            # Dynamic Cost Impact: 
            # Non-linear increase - past 50% congestion, costs spike much faster
            if percent_increase > 50:
                item_cost_impact = round(5 + (percent_increase - 50) * 0.15, 1)
            else:
                item_cost_impact = round(percent_increase * 0.1, 1)
            
            affected_commodities = attrs.get('commodities', [])
            
            results.append({
                "route": f"{src} -> {dst}",
                "is_alternate_route": attrs['alt'],
                "affected_commodities": affected_commodities,
                "predicted_congestion_multiplier": round(pred_congestion, 2),
                "congestion_spike": f"+{percent_increase}%" if percent_increase > 0 else "N/A",
                "estimated_item_cost_increase": f"+{item_cost_impact}%" if item_cost_impact > 0 else "N/A",
                "status": status
            })
            
    # Sort by highest congestion severity
    results.sort(key=lambda x: x['predicted_congestion_multiplier'], reverse=True)
            
    response = {
        "event": "Disruption Simulation Triggered",
        "blocked_node": blocked_chokepoint,
        "displaced_commodities": displaced_commodities,
        "cascading_effects": results[:20] # Top 20 most impacted edges
    }
    
    return jsonify(response)
