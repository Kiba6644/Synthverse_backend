import sys
import os
import torch
import json

# Ensure the layer4_gnn package is accessible for imports
sys.path.append(os.path.join(os.path.dirname(__file__), 'layer4_gnn'))
from gnn_dataset import load_base_graph_state, build_pyg_data, simulate_rerouting
from gnn_model import MaritimeGAT

MODEL_PATH = os.path.join(os.path.dirname(__file__), 'layer4_gnn', 'maritime_gat.pth')

def test_logic():
    model = MaritimeGAT()
    model.load_state_dict(torch.load(MODEL_PATH, map_location=torch.device('cpu'), weights_only=True))
    model.eval()

    nodes_list, base_edges = load_base_graph_state()
    node_to_idx = {n: i for i, n in enumerate(nodes_list)}
    chokepoint_keywords = ['Strait', 'Canal', 'Hope', 'Bab-el-Mandeb']
    is_chokepoint = [any(kw in n for kw in chokepoint_keywords) for n in nodes_list]

    blocked_chokepoint = 'Suez Canal'
    blocked_idxs = [node_to_idx[blocked_chokepoint]]

    simulated_edges, displaced_commodities = simulate_rerouting(base_edges, [blocked_chokepoint])
    pyg_data = build_pyg_data(nodes_list, node_to_idx, simulated_edges, blocked_idxs, is_chokepoint)

    with torch.no_grad():
        preds = model(pyg_data.x, pyg_data.edge_index, pyg_data.edge_attr)

    results = []
    edges_list = list(simulated_edges.items())
    for i, ((src, dst), attrs) in enumerate(edges_list):
        pred_congestion = float(preds[i][0])
        if pred_congestion > 1.05 or dst == blocked_chokepoint or src == blocked_chokepoint:
            status = "NORMAL"
            if src == blocked_chokepoint or dst == blocked_chokepoint:
                status = "BLOCKED"
                pred_congestion = 0.0
            elif pred_congestion >= 1.5:
                status = "CRITICAL"
            elif pred_congestion > 1.05:
                status = "WARNING"

            percent_increase = max(0, int((pred_congestion - 1.0) * 100))
            if percent_increase > 50:
                item_cost_impact = round(5 + (percent_increase - 50) * 0.15, 1)
            else:
                item_cost_impact = round(percent_increase * 0.1, 1)

            results.append({
                "route": f"{src} -> {dst}",
                "commodities": attrs.get('commodities', []),
                "congestion": f"+{percent_increase}%",
                "cost_impact": f"+{item_cost_impact}%",
                "status": status
            })

    print(json.dumps({
        "blocked": blocked_chokepoint,
        "displaced": displaced_commodities,
        "top_impacts": results[:5]
    }, indent=2))

if __name__ == "__main__":
    test_logic()
