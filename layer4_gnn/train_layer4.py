import torch
import torch.nn.functional as F
from torch_geometric.loader import DataLoader
from sklearn.model_selection import train_test_split
from gnn_dataset import generate_synthetic_scenarios
from gnn_model import MaritimeGAT
import os

def train():
    # 1. Generate the hackathon synthetic dataset
    print("Generating simulated maritime stress scenarios...")
    data_list = generate_synthetic_scenarios(num_scenarios=1000)
    
    # 2. Split into Train and Validation
    train_data, val_data = train_test_split(data_list, test_size=0.2, random_state=42)
    
    # Batch the graphs for faster execution
    train_loader = DataLoader(train_data, batch_size=32, shuffle=True)
    val_loader = DataLoader(val_data, batch_size=32, shuffle=False)
    
    # 3. Initialize Model and Optimizer
    device = torch.device('cuda' if torch.cuda.is_available() else 'cpu')
    model = MaritimeGAT().to(device)
    optimizer = torch.optim.Adam(model.parameters(), lr=0.01, weight_decay=5e-4)
    loss_fn = torch.nn.MSELoss()
    
    # 4. Training Loop
    epochs = 50
    print(f"Training on {device} for {epochs} epochs...")
    
    for epoch in range(epochs):
        model.train()
        total_loss = 0
        
        for batch in train_loader:
            batch = batch.to(device)
            optimizer.zero_grad()
            
            # Predict
            pred_congestion = model(batch.x, batch.edge_index, batch.edge_attr)
            
            # Calculate Loss against Ground Truth 'y'
            # Note: PyG batches graphs, so output is flattened across the batch's edges
            loss = loss_fn(pred_congestion, batch.y)
            loss.backward()
            optimizer.step()
            
            total_loss += loss.item()
            
        avg_train_loss = total_loss / len(train_loader)
        
        # Validation
        model.eval()
        val_loss = 0
        with torch.no_grad():
            for batch in val_loader:
                batch = batch.to(device)
                pred = model(batch.x, batch.edge_index, batch.edge_attr)
                v_loss = loss_fn(pred, batch.y)
                val_loss += v_loss.item()
                
        avg_val_loss = val_loss / len(val_loader)
        
        if (epoch + 1) % 5 == 0:
            print(f"Epoch {epoch+1:>3} | Train MSE: {avg_train_loss:.4f} | Val MSE: {avg_val_loss:.4f}")
            
    # 5. Save the weights
    save_path = os.path.join(os.path.dirname(__file__), 'maritime_gat.pth')
    torch.save(model.state_dict(), save_path)
    print(f"\nModel successfully saved to: {save_path}")

def run_test_inference():
    print("\n--- Running Quick Inference Test ---")
    data_list = generate_synthetic_scenarios(num_scenarios=1)
    test_graph = data_list[0]
    
    model = MaritimeGAT()
    model.load_state_dict(torch.load(os.path.join(os.path.dirname(__file__), 'maritime_gat.pth'), weights_only=True))
    model.eval()
    
    with torch.no_grad():
        preds = model(test_graph.x, test_graph.edge_index, test_graph.edge_attr)
        print(f"Sample ground truth congestions: \n{test_graph.y[:5].squeeze()}")
        print(f"Sample predicted congestions: \n{preds[:5].squeeze()}")
        print("Success! The GNN can infer the network pressure distribution dynamically.")

if __name__ == "__main__":
    train()
    run_test_inference()
