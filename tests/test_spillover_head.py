import torch

from ml.spillover_head import SpilloverPredictionHead


def test_output_shape_and_no_nans():
    torch.manual_seed(0)
    embeddings = torch.randn(5, 16)
    exposure = torch.rand(5)
    head = SpilloverPredictionHead(embedding_dim=16, hidden_dim=8)

    out = head(embeddings, exposure)

    assert out.shape == (5,)
    assert not out.isnan().any()


def test_handles_all_zero_exposure_without_crashing():
    # Every creator has zero exposure (no sponsored neighbors) -- a real
    # case once the consistency constraint is doing its job during
    # training, but the head itself shouldn't special-case it structurally.
    torch.manual_seed(0)
    embeddings = torch.randn(4, 16)
    exposure = torch.zeros(4)
    head = SpilloverPredictionHead(embedding_dim=16, hidden_dim=8)

    out = head(embeddings, exposure)

    assert out.shape == (4,)
    assert not out.isnan().any()


def test_handles_single_node_graph():
    embeddings = torch.randn(1, 16)
    exposure = torch.zeros(1)
    head = SpilloverPredictionHead(embedding_dim=16, hidden_dim=8)

    out = head(embeddings, exposure)

    assert out.shape == (1,)


def test_gradients_flow_back_to_embeddings_and_exposure():
    embeddings = torch.randn(3, 16, requires_grad=True)
    exposure = torch.rand(3, requires_grad=True)
    head = SpilloverPredictionHead(embedding_dim=16, hidden_dim=8)

    out = head(embeddings, exposure)
    out.sum().backward()

    assert embeddings.grad is not None and not embeddings.grad.isnan().any()
    assert exposure.grad is not None and not exposure.grad.isnan().any()
