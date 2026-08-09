import torch

from ml.dummy_data import make_dummy_hetero_data
from ml.gail_model import GAILModel
from ml.training import TrainConfig, train, train_val_split


def test_train_val_split_basic():
    train_idx, val_idx = train_val_split(num_nodes=10, val_fraction=0.2, seed=0)
    assert train_idx.numel() + val_idx.numel() == 10
    assert set(train_idx.tolist()).isdisjoint(set(val_idx.tolist()))


def test_train_val_split_single_node_leaves_val_empty():
    train_idx, val_idx = train_val_split(num_nodes=1, val_fraction=0.5, seed=0)
    assert train_idx.numel() == 1
    assert val_idx.numel() == 0


def test_train_val_split_two_nodes_leaves_at_least_one_train():
    train_idx, val_idx = train_val_split(num_nodes=2, val_fraction=0.9, seed=0)
    assert train_idx.numel() >= 1


def _sponsored_neighbor_count_target(collab_edge_index, treatment, num_creators):
    src, dst = collab_edge_index
    target = torch.zeros(num_creators)
    mask = treatment[src] > 0
    if mask.any():
        target.index_add_(0, dst[mask], torch.ones(int(mask.sum().item())))
    return target


def test_training_loop_reduces_loss_on_synthetic_target():
    torch.manual_seed(0)
    data = make_dummy_hetero_data(num_creators=8, num_brands=3, seed=1)
    num_creators = data["creator"].x.size(0)
    treatment = torch.zeros(num_creators)
    treatment[[0, 3]] = 1.0

    collab_edge_index = data["creator", "collaborates_with", "creator"].edge_index
    target = _sponsored_neighbor_count_target(collab_edge_index, treatment, num_creators)

    model = GAILModel(creator_feature_dim=data["creator"].x.size(1), hidden_channels=16, heads=2)
    history = train(model, data, treatment, target, TrainConfig(epochs=80, lr=1e-2, val_fraction=0.25, seed=0))

    assert history[-1]["prediction"] < history[0]["prediction"] * 0.5
    assert not any(torch.isnan(torch.tensor(h["total"])) for h in history)


def test_training_loop_handles_zero_collaboration_edges():
    # Real current data state -- must not crash or NaN across a full
    # multi-epoch run, not just a single forward pass.
    torch.manual_seed(0)
    data = make_dummy_hetero_data(num_creators=5, num_brands=2, avg_degree=0, seed=2)
    treatment = torch.zeros(5)
    target = torch.zeros(5)

    model = GAILModel(creator_feature_dim=data["creator"].x.size(1), hidden_channels=8, heads=1)
    history = train(model, data, treatment, target, TrainConfig(epochs=5, val_fraction=0.2, seed=0))

    assert len(history) == 5
    assert all(not torch.isnan(torch.tensor(h["total"])) for h in history)


def test_training_loop_handles_single_node_graph():
    torch.manual_seed(0)
    data = make_dummy_hetero_data(num_creators=1, num_brands=0, avg_degree=0, seed=3)
    treatment = torch.zeros(1)
    target = torch.zeros(1)

    model = GAILModel(creator_feature_dim=data["creator"].x.size(1), hidden_channels=8, heads=1)
    history = train(model, data, treatment, target, TrainConfig(epochs=3, val_fraction=0.5, seed=0))

    assert len(history) == 3
    # val split is empty for a single node -- val_loss should be reported as NaN, not crash.
    assert all(h["val_loss"] != h["val_loss"] for h in history)  # NaN != NaN


def test_training_loop_on_fully_symmetric_dummy_graph():
    # A hand-built symmetric graph (not the random dummy generator) --
    # complete graph, identical features, one sponsored node -- confirms
    # the loop runs cleanly on a structurally uniform graph, not just
    # random asymmetric ones.
    torch.manual_seed(0)
    from ml.schema import empty_hetero_data

    data = empty_hetero_data()
    data["creator"].x = torch.zeros(4, data["creator"].x.size(1))
    pairs = [(i, j) for i in range(4) for j in range(4) if i != j]
    edge_index = torch.tensor(pairs).t()
    data["creator", "collaborates_with", "creator"].edge_index = edge_index
    data["creator", "collaborates_with", "creator"].edge_attr = torch.ones(edge_index.size(1), 1)

    treatment = torch.tensor([1.0, 0.0, 0.0, 0.0])
    target = torch.tensor([0.0, 1.0, 1.0, 1.0])  # every non-sponsored node has 1 sponsored neighbor

    model = GAILModel(creator_feature_dim=data["creator"].x.size(1), hidden_channels=8, heads=1)
    history = train(model, data, treatment, target, TrainConfig(epochs=20, val_fraction=0.0, seed=0))

    assert len(history) == 20
    assert all(not torch.isnan(torch.tensor(h["total"])) for h in history)
