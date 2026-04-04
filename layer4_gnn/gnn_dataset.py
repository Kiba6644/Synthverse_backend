import pandas as pd
import numpy as np
import networkx as nx
import torch
from torch_geometric.data import Data
import os

DATASET_PATH = os.path.join(os.path.dirname(__file__), '..', 'india_imports_dataset.csv')

def load_base_graph_state():
    """
    Parses the dataset and builds the foundational Graph structure.
    Returns:
        nodes_list: List of unique node names
        edges_list: List of dictionaries representing edges 
                    (source, target, base_distance, base_volume, is_alt_route)
    """
    df = pd.read_csv(DATASET_PATH)
    
    nodes = set()
    edges = []
    
    for _, row in df.iterrows():
        origin = row['origin']
        dest = row['destination']
        chokepoints = eval(row['chokepoints']) if isinstance(row['chokepoints'], str) else []
        alt_chokepoints = eval(row['alt_chokepoints']) if isinstance(row['alt_chokepoints'], str) else []
        
        val_usd = float(row['value_usd'])
        dist = float(row['primary_distance_nm'])
        alt_dist = float(row['alt_distance_nm'])
        
        nodes.add(origin)
        nodes.add(dest)
        
        # Primary Route
        if not chokepoints or 'None' in chokepoints[0] or chokepoints[0] == 'Direct Sea':
            edges.append({'src': origin, 'dst': dest, 'dist': dist, 'vol': val_usd, 'alt': False, 'commodity': row['commodity_name']})
        else:
            prev = origin
            seg_dist = dist / (len(chokepoints) + 1)
            for cp in chokepoints:
                nodes.add(cp)
                edges.append({'src': prev, 'dst': cp, 'dist': seg_dist, 'vol': val_usd, 'alt': False, 'commodity': row['commodity_name']})
                prev = cp
            edges.append({'src': prev, 'dst': dest, 'dist': seg_dist, 'vol': val_usd, 'alt': False, 'commodity': row['commodity_name']})
            
        # Alternate Route (starts with zero volume)
        if alt_chokepoints and 'None' not in alt_chokepoints[0]:
            prev = origin
            # Handle list strings properly
            seg_dist = alt_dist / (len(alt_chokepoints) + 1) if not np.isinf(alt_dist) else 10000
            for cp in alt_chokepoints:
                if 'None' in cp: continue
                nodes.add(cp)
                edges.append({'src': prev, 'dst': cp, 'dist': seg_dist, 'vol': 0.0, 'alt': True, 'commodity': row['commodity_name']})
                prev = cp
            edges.append({'src': prev, 'dst': dest, 'dist': seg_dist, 'vol': 0.0, 'alt': True, 'commodity': row['commodity_name']})

    # Deduplicate edges by summing volumes where paths overlap
    edge_dict = {}
    for e in edges:
        key = (e['src'], e['dst'])
        if key not in edge_dict:
            edge_dict[key] = {'dist': e['dist'], 'vol': e['vol'], 'alt': e['alt'], 'commodities': {e['commodity']}}
        else:
            edge_dict[key]['vol'] += e['vol']
            edge_dict[key]['commodities'].add(e['commodity'])
            
    # Convert sets to lists for JSON serialization later if needed
    for k in edge_dict:
        edge_dict[k]['commodities'] = list(edge_dict[k]['commodities'])
            
    # Compute base capacities (heuristic: normal capacity = 1.2 * normal volume, alt paths = max 2.0 * avg volume)
    avg_vol = np.mean([v['vol'] for v in edge_dict.values() if v['vol'] > 0])
    for k, v in edge_dict.items():
        v['capacity'] = v['vol'] * 1.5 if not v['alt'] else avg_vol * 1.5
        # Prevent zero capacity
        if v['capacity'] == 0: v['capacity'] = avg_vol * 0.5
            
    return list(nodes), edge_dict

def generate_synthetic_scenarios(num_scenarios=500):
    """
    Generates synthetic graph layouts representing different disruption scenarios.
    """
    nodes_list, base_edges = load_base_graph_state()
    node_to_idx = {n: i for i, n in enumerate(nodes_list)}
    num_nodes = len(nodes_list)
    
    # Identify chokepoints vs countries (heuristic: Countries don't have 'Strait', 'Canal', 'Hope' etc)
    chokepoint_keywords = ['Strait', 'Canal', 'Hope', 'Bab-el-Mandeb']
    is_chokepoint = [any(kw in n for kw in chokepoint_keywords) for n in nodes_list]
    chokepoint_indices = [i for i, is_cp in enumerate(is_chokepoint) if is_cp]
    
    data_list = []
    
    # Baseline Scenario (Nothing blocked)
    data_list.append(build_pyg_data(nodes_list, node_to_idx, base_edges, [], is_chokepoint))
    
    # Disruption Scenarios
    for _ in range(num_scenarios):
        # Pick 1 or 2 random chokepoints to "block"
        num_blocked = np.random.randint(1, 3)
        blocked_idxs = np.random.choice(chokepoint_indices, size=num_blocked, replace=False).tolist()
        blocked_nodes = [nodes_list[i] for i in blocked_idxs]
        
        simulated_edges, _ = simulate_rerouting(base_edges, blocked_nodes)
        
        pyg_data = build_pyg_data(nodes_list, node_to_idx, simulated_edges, blocked_idxs, is_chokepoint)
        data_list.append(pyg_data)
        
    return data_list

def simulate_rerouting(base_edges, blocked_nodes):
    """
    If an edge leads to a blocked node, its volume is set to 0.
    That volume is dynamically shifted to alternate routes, causing 'congestion_multiplier' to spike.
    """
    import copy
    edges = copy.deepcopy(base_edges)
    
    # 1. Zero out blocked edges and calculate spilled volume
    spilled_volume = 0
    displaced_commodities = set()
    for key, attrs in edges.items():
        src, dst = key
        # If the destination is blocked, the ship can't go there
        if dst in blocked_nodes or src in blocked_nodes:
            spilled_volume += attrs['vol']
            for c in attrs.get('commodities', []):
                displaced_commodities.add(c)
            attrs['vol'] = 0.0

    # 2. Distribute spilled volume to alternate routes (heuristic)
    alt_edges = [k for k, v in edges.items() if v['alt'] and k[0] not in blocked_nodes and k[1] not in blocked_nodes]
    if alt_edges and spilled_volume > 0:
        vol_per_alt = spilled_volume / len(alt_edges)
        for k in alt_edges:
            edges[k]['vol'] += vol_per_alt
            # Also add the displaced commodities to these alternate routes
            for c in displaced_commodities:
                if 'commodities' not in edges[k]: edges[k]['commodities'] = []
                if c not in edges[k]['commodities']:
                    edges[k]['commodities'].append(c)
            
    # 3. Calculate congestion multiplier = new_vol / capacity
    for k, v in edges.items():
        if v['capacity'] > 0:
            v['congestion'] = v['vol'] / v['capacity']
        else:
            v['congestion'] = 0.0
            
    return edges, list(displaced_commodities)

def build_pyg_data(nodes_list, node_to_idx, edges, blocked_idxs, is_chokepoint):
    num_nodes = len(nodes_list)
    
    # Node features: [is_country_flag, is_chokepoint_flag, is_blocked_flag]
    x = np.zeros((num_nodes, 3), dtype=np.float32)
    for i in range(num_nodes):
        if is_chokepoint[i]:
            x[i, 1] = 1.0
        else:
            x[i, 0] = 1.0
            
        if i in blocked_idxs:
            x[i, 2] = 1.0 # The "blocked" distress signal
            
    x_tensor = torch.tensor(x, dtype=torch.float)
    
    # Edge index and attributes
    edge_index = []
    edge_attr = [] # [distance_normalized]
    y_congestion = [] # Ground truth label we want to predict
    
    max_dist = 15000.0
    
    for (src, dst), attrs in edges.items():
        u = node_to_idx[src]
        v = node_to_idx[dst]
        
        edge_index.append([u, v])
        norm_dist = min(attrs['dist'] / max_dist, 1.0)
        edge_attr.append([norm_dist])
        y_congestion.append(attrs.get('congestion', 1.0))
        
    edge_index_tensor = torch.tensor(edge_index, dtype=torch.long).t().contiguous()
    edge_attr_tensor = torch.tensor(edge_attr, dtype=torch.float)
    y_tensor = torch.tensor(y_congestion, dtype=torch.float).view(-1, 1) # [NumEdges, 1]
    
    data = Data(x=x_tensor, edge_index=edge_index_tensor, edge_attr=edge_attr_tensor, y=y_tensor)
    return data

if __name__ == "__main__":
    dataset = generate_synthetic_scenarios(10)
    print(f"Generated {len(dataset)} mock graphs for testing.")
    print(f"Node Features Shape: {dataset[0].x.shape}")
    print(f"Edge Index Shape: {dataset[0].edge_index.shape}")
    print(f"Edge Labels Shape: {dataset[0].y.shape}")
