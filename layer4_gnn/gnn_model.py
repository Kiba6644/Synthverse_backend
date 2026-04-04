import torch
import torch.nn.functional as F
from torch_geometric.nn import GATConv

class MaritimeGAT(torch.nn.Module):
    def __init__(self, node_in_dim=3, edge_in_dim=1, hidden_dim=16, edge_out_dim=1):
        """
        Graph Attention Network for predicting edge-level congestion.
        
        Args:
            node_in_dim: Dimension of node features [is_country, is_chokepoint, is_blocked] = 3
            edge_in_dim: Dimension of edge features [norm_distance] = 1
            hidden_dim: Hidden representation size for nodes
            edge_out_dim: Target prediction dimension (1 for congestion_multiplier)
        """
        super(MaritimeGAT, self).__init__()
        
        # We use PyG's GATConv which supports edge features in message passing
        self.conv1 = GATConv(node_in_dim, hidden_dim, edge_dim=edge_in_dim, add_self_loops=False)
        self.conv2 = GATConv(hidden_dim, hidden_dim, edge_dim=edge_in_dim, add_self_loops=False)
        
        # Edge Predictor Head
        # Concatenates the embeddings of the Source Node + Target Node + Original Edge Attr
        # To predict specifically what happens on that edge
        self.edge_predictor = torch.nn.Sequential(
            torch.nn.Linear(hidden_dim * 2 + edge_in_dim, hidden_dim),
            torch.nn.ReLU(),
            torch.nn.Linear(hidden_dim, edge_out_dim)
        )

    def forward(self, x, edge_index, edge_attr):
        """
        x: Node features [N, 3]
        edge_index: Graph connectivity [2, E]
        edge_attr: Edge features [E, 1]
        """
        
        # Pass 1: Nodes aggregate attention-weighted info from neighbors
        # (A blocked node will strongly influence its neighbor's embedding)
        h = self.conv1(x, edge_index, edge_attr)
        h = F.relu(h)
        
        # Pass 2: Deeper aggregation to capture second-order cascades
        h = self.conv2(h, edge_index, edge_attr)
        h = F.relu(h)
        
        # Edge Prediction
        # For every edge (u -> v), get the embedding of u and v
        src, dst = edge_index
        src_emb = h[src] # [E, hidden_dim]
        dst_emb = h[dst] # [E, hidden_dim]
        
        # Concatenate: [src_emb, dst_emb, original_edge_distance]
        edge_inputs = torch.cat([src_emb, dst_emb, edge_attr], dim=-1)
        
        # Predict the scalar congestion multiplier
        out = self.edge_predictor(edge_inputs)
        
        # We use ReLU to ensure congestion is non-negative
        return F.relu(out)
