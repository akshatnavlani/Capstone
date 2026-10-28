import os
from pathlib import Path

import pytest
import torch
from torch import nn

from ml.external_baselines import _Adj, _cpu, _neighbour_lists


def test_cpu_context_restores_torch():
    before = (nn.Module.cuda, torch.Tensor.cuda, nn.Linear.__init__, torch.rand, torch.zeros)
    with _cpu():
        lin = nn.Linear(3, 2, device="cuda")      # would fail on a CPU-only machine without the context
        assert lin.weight.device.type == "cpu"
        assert torch.zeros(2, device="cuda").device.type == "cpu"
    assert (nn.Module.cuda, torch.Tensor.cuda, nn.Linear.__init__, torch.rand, torch.zeros) == before


def test_adj_mask_is_boolean_for_deepinf_masking():
    adj = torch.tensor([[1, 0], [1, 1]], dtype=torch.uint8).as_subclass(_Adj)
    mask = 1 - adj.unsqueeze(1)
    assert mask.dtype == torch.bool and mask.reshape(-1).tolist() == [False, True, False, False]


def test_neighbour_lists_symmetric_without_self():
    nb = _neighbour_lists(torch.tensor([[0, 1, 2], [1, 1, 0]]), 3)
    assert nb == [[1, 2], [0], [0]]


@pytest.mark.skipif(not os.environ.get("GAIL_DEEPINF_DIR"), reason="needs a DeepInf clone")
def test_deepinf_runs_on_small_world():
    from ml.external_baselines import run_deepinf
    from ml.semi_synthetic import fake_graph, make_world
    g = fake_graph(n=60, n_collab=40, n_coocc=60)
    w = make_world(g, "clean", 0)
    out = run_deepinf(w.data["creator"].x, torch.cat([g.collab, g.coocc], 1), w.treatment, w.y,
                      repo=Path(os.environ["GAIL_DEEPINF_DIR"]))
    assert torch.isfinite(out["tau"]).all()
