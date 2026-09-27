"""Sanity check for the ML-Core environment (Weeks 1-2 objective #1).

Run with: .venv\\Scripts\\python.exe scripts\\verify_environment.py
Confirms torch, CUDA, and PyTorch Geometric actually work, not just import.
"""

import sys

import torch
import torch_geometric
from torch_geometric.data import HeteroData
from torch_geometric.nn import GATConv


def main() -> int:
    print(f"torch {torch.__version__}, torch_geometric {torch_geometric.__version__}")

    cuda_available = torch.cuda.is_available()
    device = torch.device("cuda" if cuda_available else "cpu")
    print(f"CUDA available: {cuda_available}" + (f" ({torch.cuda.get_device_name(0)})" if cuda_available else ""))

    # Trivial tensor op on the selected device.
    a = torch.randn(4, 4, device=device)
    b = torch.randn(4, 4, device=device)
    assert (a @ b).shape == (4, 4)

    # Trivial homogeneous GAT forward pass.
    x = torch.randn(5, 8, device=device)
    edge_index = torch.tensor([[0, 1, 2, 3], [1, 2, 3, 4]], device=device)
    conv = GATConv(8, 16).to(device)
    out = conv(x, edge_index)
    assert out.shape == (5, 16)

    # Trivial HeteroData construction, to confirm the API used by ml/schema.py works.
    data = HeteroData()
    data["a"].x = torch.randn(3, 4)
    data["b"].x = torch.randn(2, 4)
    data["a", "links", "b"].edge_index = torch.tensor([[0, 1], [0, 1]])
    assert data.node_types == ["a", "b"]

    print("OK: torch tensor ops, GATConv forward pass, and HeteroData construction all work.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
