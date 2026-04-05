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
nodes_list, base_edges, trade_flows = load_base_graph_state()
node_to_idx = {n: i for i, n in enumerate(nodes_list)}
chokepoint_keywords = ['Strait', 'Canal', 'Hope', 'Bab-el-Mandeb']
is_chokepoint = [any(kw in n for kw in chokepoint_keywords) for n in nodes_list]

@layer_4_bp.route('/api/layer4/simulate', methods=['POST'])
def simulate_disruption():
    req_data = request.get_json() or {}
    
    # Support both single and multiple blockades
    blocked_input = req_data.get('blocked_nodes', [])
    if not blocked_input:
        single = req_data.get('blocked_chokepoint')
        blocked_nodes = [single] if single else []
    else:
        blocked_nodes = blocked_input

    # Validate nodes - collect valid ones and log warnings for others
    valid_blocked = [n for n in blocked_nodes if n in nodes_list]
    if not valid_blocked and blocked_nodes:
        # If the user selected something valid in UI but not in dataset, 
        # let's not 400. Just treat as empty (no disruption).
        pass
        
    blocked_idxs = [node_to_idx[n] for n in valid_blocked]
    
    # 1. Physics Engine Setup: Pass the list of blocked nodes
    simulated_edges, displaced_commodities = simulate_rerouting(base_edges, valid_blocked)
    
    # 2. PyG Tensor Formatting
    pyg_data = build_pyg_data(nodes_list, node_to_idx, simulated_edges, blocked_idxs, is_chokepoint)
    
    # 3. GAT Inference
    with torch.no_grad():
        preds = gnn_model(pyg_data.x, pyg_data.edge_index, pyg_data.edge_attr)
        
    # 4. Result Formatting: INDIA-CENTRIC AGGREGATION
    edge_results = {}
    edges_list = list(simulated_edges.items())
    for i, ((src, dst), attrs) in enumerate(edges_list):
        edge_results[(src, dst)] = {
            "congestion": float(preds[i][0]),
            "is_alt": attrs['alt']
        }

    india_impacts = []
    for origin, flow in trade_flows.items():
        # Check if ANY node in primary path is blocked
        primary_path = flow['primary_path']
        primary_blocked = any(node in valid_blocked for node in primary_path)
        
        # Check if ANY node in alternate path is blocked
        alt_path = flow['alt_path']
        alt_blocked = any(node in valid_blocked for node in alt_path)
        
        max_congestion = 1.0
        status = "NORMAL"
        cost_impact = 0.0
        load_info = "Optimal"
        redirection_target = "None"
        
        # Unique Distance Metadata
        p_dist = flow.get('primary_dist', 5000)
        a_dist = flow.get('alt_dist', 12000)
        dist_overhead = (a_dist - p_dist) / p_dist if p_dist > 0 else 0.5

        if primary_blocked:
            if alt_blocked:
                status = "TOTAL FLOW COLLAPSE"
                cost_impact = 150.0 + (dist_overhead * 20) # Russia/Germany hit harder by total collapse
                max_congestion = 5.0 
                load_info = "CRITICAL FAILURE"
            else:
                status = "DIVERSION ACTIVE"
                # Identify the main chokepoint in the alternate path
                redirection_target = "Alternate Route"
                for node in alt_path:
                    if any(kw in node for kw in chokepoint_keywords):
                        redirection_target = node
                        break
                
                alt_congestions = []
                for j in range(len(alt_path)-1):
                    edge = (alt_path[j], alt_path[j+1])
                    if edge in edge_results:
                        alt_congestions.append(edge_results[edge]['congestion'])
                    else:
                        alt_congestions.append(1.2)
                
                raw_max = max(alt_congestions) if alt_congestions else 1.2
                max_congestion = max(1.15, raw_max * 1.5)
                
                load_increase = int((max_congestion - 1.0) * 100)
                load_info = f"+{load_increase}% Load on {redirection_target}"
                
                # UNIQUE ECONOMIC RISK: Factors in Congestion (35%) + Distance (25%) + Base (12%)
                cost_impact = (max_congestion - 1.0) * 35 + (dist_overhead * 25) + 12.0 
        else:
            congestions = []
            for j in range(len(primary_path)-1):
                edge = (primary_path[j], primary_path[j+1])
                if edge in edge_results:
                    congestions.append(edge_results[edge]['congestion'])
            
            raw_max = max(congestions) if congestions else 1.0
            max_congestion = max(1.0, raw_max)
            
            if max_congestion > 1.1:
                status = "HEAVY TRAFFIC"
                cost_impact = (max_congestion - 1.0) * 30 + (dist_overhead * 5)
                load_info = f"+{int((max_congestion-1)*100)}% Local Stress"
            else:
                cost_impact = (max_congestion - 1.0) * 12
                load_info = "Stable Flow"

        india_impacts.append({
            "origin": origin,
            "route": f"{origin} ➜ India",
            "status": status,
            "economic_risk": f"+{round(min(200, cost_impact), 1)}%",
            "redistribution_load": load_info,
            "commodity": flow['commodity'],
            "is_rerouted": primary_blocked and not alt_blocked,
            "is_collapsed": primary_blocked and alt_blocked,
            "severity": max_congestion,
            "primary_path": primary_path,
            "alt_path": alt_path if primary_blocked and not alt_blocked else [],
            "p_dist": p_dist,
            "a_dist": a_dist if primary_blocked else p_dist
        })

    india_impacts.sort(key=lambda x: (x['is_collapsed'], x['severity']), reverse=True)
            
    response = {
        "event": "Multi-Chokepoint Disruption Analysis",
        "blocked_nodes": valid_blocked,
        "total_displaced_value": sum(f['value'] for o, f in trade_flows.items() if any(n in valid_blocked for n in f['primary_path'])),
        "cascading_effects": [i for i in india_impacts if i['severity'] > 1.01 or i['is_rerouted'] or i['is_collapsed']]
    }
    
    return jsonify(response)
    
    return jsonify(response)
