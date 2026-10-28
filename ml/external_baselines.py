"""Published baselines run on the semi-synthetic benchmark, from the authors' code.

TNet (Chen et al., ICML 2024; github.com/DMIRLAB-Group/TNet) is imported from a
local clone, never copied here: its repository has no licence file. Set
GAIL_TNET_DIR to the clone's root (the folder holding src/).

TNet hard-codes CUDA (device='cuda', .cuda(), torch.cuda.FloatTensor). The
`_cpu` context redirects those calls to the CPU while TNet runs and restores
torch afterwards; TNet's model code is used unmodified. Training reproduces
TargetedModel_DoubleBSpline's loop in its experiment.py (one base step, then 50
targeted-regularisation steps, for 160 epochs) with the defaults of its main.py.

TNet sees a single unweighted graph and an exposure z = share of ALL neighbours
treated; that is its design, so it receives the union of collaborates_with and
co_occurs_with. The per-creator effect read off it is the same estimand GAIL-R
is scored on: predicted outcome at the observed exposure minus at z = 0.
"""

from __future__ import annotations

import contextlib
import importlib
import os
import sys
from pathlib import Path

import torch
from torch import nn

TNET_DEFAULTS = dict(hidden=64, dropout=0.05, num_grid=20, tr_knots=0.1, alpha=0.5, gamma=1.0, beta=20.0,
                     lr_1step=1e-4, lr_2step=1e-2, weight_decay=1e-3, weight_decay_tr=1e-3,
                     epochs=160, iter_2step=50)


@contextlib.contextmanager
def _cpu():
    """Make CUDA-only code run on the CPU, for the duration of the block."""
    saved = {
        "module_cuda": nn.Module.cuda, "tensor_cuda": torch.Tensor.cuda,
        "linear_init": nn.Linear.__init__, "rand": torch.rand, "zeros": torch.zeros,
        "cuda_float": getattr(torch.cuda, "FloatTensor", None),
    }

    def no_cuda_device(kw):
        if str(kw.get("device", "")).startswith("cuda"):
            kw["device"] = "cpu"
        return kw

    def linear_init(self, *a, **kw):
        saved["linear_init"](self, *a, **no_cuda_device(kw))

    nn.Module.cuda = lambda self, *a, **k: self
    torch.Tensor.cuda = lambda self, *a, **k: self
    nn.Linear.__init__ = linear_init
    torch.rand = lambda *a, **kw: saved["rand"](*a, **no_cuda_device(kw))
    torch.zeros = lambda *a, **kw: saved["zeros"](*a, **no_cuda_device(kw))
    torch.cuda.FloatTensor = torch.FloatTensor
    try:
        yield
    finally:
        nn.Module.cuda = saved["module_cuda"]
        torch.Tensor.cuda = saved["tensor_cuda"]
        nn.Linear.__init__ = saved["linear_init"]
        torch.rand = saved["rand"]
        torch.zeros = saved["zeros"]
        if saved["cuda_float"] is not None:
            torch.cuda.FloatTensor = saved["cuda_float"]


def tnet_dir() -> Path | None:
    d = os.environ.get("GAIL_TNET_DIR")
    return Path(d) if d and (Path(d) / "src" / "targetedModel_DoubleBSpline.py").exists() else None


def _load_tnet_class(repo: Path):
    src = str(repo / "src")
    if src not in sys.path:
        sys.path.insert(0, src)
    with _cpu():
        return importlib.import_module("targetedModel_DoubleBSpline").TargetedModel_DoubleBSpline


def _row_normalize(x: torch.Tensor) -> torch.Tensor:
    """TNet's utils.normalize: divide each feature row by its sum (0 rows stay 0).
    Our features are z-scored and can be negative, so they are shifted to be
    non-negative first, as row normalisation assumes."""
    x = x - x.min(dim=0).values
    s = x.sum(dim=1, keepdim=True)
    return torch.where(s > 0, x / s.clamp(min=1e-12), x)


def run_tnet(x: torch.Tensor, edge_index: torch.Tensor, treatment: torch.Tensor, y: torch.Tensor,
             seed: int = 0, repo: Path | None = None, **overrides) -> dict:
    """Train TNet on one graph and return per-node effects of the observed exposure.

    Returns {"ate": mean effect, "tau": per-node effect} on the original y scale.
    """
    repo = repo or tnet_dir()
    if repo is None:
        raise RuntimeError("set GAIL_TNET_DIR to a clone of github.com/DMIRLAB-Group/TNet")
    hp = {**TNET_DEFAULTS, **overrides}
    n = x.size(0)
    A = torch.zeros(n, n)
    A[edge_index[0], edge_index[1]] = 1.0
    A = ((A + A.T) > 0).float()
    A.fill_diagonal_(0)
    X = _row_normalize(x.float())
    T = treatment.float()
    deg = A.sum(1)
    Z = torch.where(deg > 0, (A @ T) / deg.clamp(min=1), torch.zeros(n))   # isolated nodes: exposure 0
    ym, ys = y.mean(), y.std()
    Y = (y - ym) / ys                                                      # TNet's normy=1
    beta = hp["beta"] * n ** -0.5                                          # as in TNet's main.py

    Model = _load_tnet_class(repo)
    torch.manual_seed(seed)
    with _cpu():
        model = Model(Xshape=X.size(1), hidden=hp["hidden"], dropout=hp["dropout"],
                      num_grid=hp["num_grid"], tr_knots=hp["tr_knots"])
        opt1 = torch.optim.Adam(model.parameter_base(), lr=hp["lr_1step"], weight_decay=hp["weight_decay"])
        opt2 = torch.optim.Adam(model.parameters(), lr=hp["lr_2step"], weight_decay=hp["weight_decay_tr"])
        mse, bce = nn.MSELoss(), nn.BCELoss()

        def targeted(Q, eps, gT, gZ):
            return Q.reshape(-1) + eps.reshape(-1) * (1 / (gT.detach().reshape(-1) * gZ.detach().reshape(-1) + 1e-6))

        for _ in range(hp["epochs"]):
            model.train()
            opt1.zero_grad()
            gT, gZ, Q, eps, _, _ = model(A, X, T, Z)
            loss = (mse(Q.reshape(-1), Y) + hp["alpha"] * bce(gT.reshape(-1), T)
                    + hp["gamma"] * -torch.log(gZ + 1e-6).mean() + beta * mse(targeted(Q, eps, gT, gZ), Y))
            loss.backward()
            opt1.step()
            for _ in range(hp["iter_2step"]):
                opt2.zero_grad()
                gT, gZ, Q, eps, _, _ = model(A, X, T, Z)
                (beta * mse(targeted(Q, eps, gT, gZ), Y)).backward()
                opt2.step()

        model.eval()
        with torch.no_grad():
            y_obs = model.infer_potential_outcome(A, X, T, Z) * ys + ym
            y_zero = model.infer_potential_outcome(A, X, T, torch.zeros(n)) * ys + ym
    tau = (y_obs - y_zero).reshape(-1)
    return {"ate": float(tau.mean()), "tau": tau}


# --- Predictive baselines: DeepInf (KDD 2018) and INFLECT-DGNN (IEEE Access 2024) -------
#
# Both predict an outcome from a node's neighbourhood; neither estimates effects.
# They are given the creator features plus the creator's own sponsorship flag as
# node input (so neighbours' sponsorship reaches a node only through the model's
# own message passing), trained to predict the outcome, and asked per creator:
# "what if your neighbours had not been sponsored?" -- the difference is their
# implied spillover, the same estimand GAIL-R is scored on.
#
# DeepInf (github.com/xptree/DeepInf, MIT): its BatchMultiHeadGraphAttention layers
# on the whole graph as one batch, with the self-loops its ego networks include;
# sizes from its train.py defaults (hidden 16,8; heads 1,1,1; dropout 0.2; lr 1e-3;
# weight decay 5e-4). Output is one regression unit instead of its 2-class
# softmax, since our outcome is continuous. Set GAIL_DEEPINF_DIR.
#
# INFLECT-DGNN (github.com/Banking-Analytics-Lab/INFLECT, GPL-3): its GIN encoder
# (models/GNNs.py GINs) and LinFFN decoder, i.e. its GNN-only model; its RNN needs a
# sequence of snapshots and the benchmark has one. Sizes from its train.py defaults
# (embedding 200, 2 layers, dropout 0.2). Set GAIL_INFLECT_DIR.
#
# Both train full-batch for PRED_EPOCHS at lr 1e-3, like the other benchmark models.

PRED_EPOCHS = 300


class _Adj(torch.Tensor):
    """DeepInf masks attention with `1 - adj` on a byte tensor, which current torch
    rejects (masked_fill_ needs a bool mask). This adjacency makes `1 - adj` return
    the bool mask, so DeepInf's layer runs unmodified."""

    def __rsub__(self, other):
        return (other - self.as_subclass(torch.Tensor).to(torch.int64)).bool()


def _repo_dir(env: str, probe: str) -> Path | None:
    d = os.environ.get(env)
    return Path(d) if d and (Path(d) / probe).exists() else None


def deepinf_dir() -> Path | None:
    return _repo_dir("GAIL_DEEPINF_DIR", "src/gat_layers.py")


def inflect_dir() -> Path | None:
    return _repo_dir("GAIL_INFLECT_DIR", "models/GNNs.py")


def _import_from(path: Path, module: str):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))
    return importlib.import_module(module)


class _DeepInfRegressor(nn.Module):
    def __init__(self, layer_cls, f_in, hidden=(16, 8), heads=(1, 1, 1), dropout=0.2):
        super().__init__()
        units = [f_in, *hidden, 1]
        self.layers = nn.ModuleList(
            layer_cls(heads[i], f_in=units[i] * (heads[i - 1] if i else 1), f_out=units[i + 1], attn_dropout=0.0)
            for i in range(len(units) - 1))
        self.dropout = dropout

    def forward(self, x, adj):                       # as DeepInf's BatchGAT.forward, batch of one graph
        x = x.unsqueeze(0)
        for i, layer in enumerate(self.layers):
            x = layer(x, adj)
            if i + 1 == len(self.layers):
                x = x.mean(dim=1)
            else:
                x = nn.functional.elu(x.transpose(1, 2).contiguous().view(1, x.size(2), -1))
                x = nn.functional.dropout(x, self.dropout, training=self.training)
        return x.reshape(-1)


class _InflectRegressor(nn.Module):
    def __init__(self, gnns, decoder, f_in, embedding=200, layers=2, dropout=0.2):
        super().__init__()
        self.enc = gnns.GINs(input_dim=f_in, embedding_dim=embedding, output_dim=embedding, edge_dim=1,
                             dropout_rate=dropout, n_layers=layers)
        self.dec = decoder.LinFFN(embedding, 1)

    def forward(self, x, edge_index, edge_attr):
        return self.dec(self.enc(x, edge_index, edge_attr)).reshape(-1)


def _fit_and_counterfact(model, predict, x, treatment, y, neighbours, seed: int) -> dict:
    """Train `predict(features)` on [x, T] -> y; effect_i = pred_i(observed T) -
    pred_i(T with i's neighbours set to 0)."""
    torch.manual_seed(seed)
    opt = torch.optim.Adam(model.parameters(), lr=1e-3, weight_decay=5e-4)
    feats = torch.cat([x.float(), treatment.float().unsqueeze(1)], dim=1)
    for _ in range(PRED_EPOCHS):
        model.train()
        opt.zero_grad()
        nn.functional.mse_loss(predict(feats), y.float()).backward()
        opt.step()
    model.eval()
    tau = torch.zeros(len(y))
    with torch.no_grad():
        observed = predict(feats)
        for i, nb in enumerate(neighbours):
            if not nb:
                continue                              # no neighbours: exposure is 0 already
            cf = feats.clone()
            cf[nb, -1] = 0.0
            tau[i] = observed[i] - predict(cf)[i]
    return {"ate": float(tau.mean()), "tau": tau}


def _neighbour_lists(edge_index: torch.Tensor, n: int) -> list[list[int]]:
    nb = [set() for _ in range(n)]
    for s, d in edge_index.t().tolist():
        if s != d:
            nb[d].add(s)
            nb[s].add(d)
    return [sorted(v) for v in nb]


def run_deepinf(x, edge_index, treatment, y, seed: int = 0, repo: Path | None = None) -> dict:
    repo = repo or deepinf_dir()
    if repo is None:
        raise RuntimeError("set GAIL_DEEPINF_DIR to a clone of github.com/xptree/DeepInf")
    layer_cls = _import_from(repo / "src", "gat_layers").BatchMultiHeadGraphAttention
    n = x.size(0)
    A = torch.zeros(n, n, dtype=torch.uint8)
    A[edge_index[0], edge_index[1]] = 1
    A = ((A + A.T) > 0).to(torch.uint8)
    A.fill_diagonal_(1)                                # ego networks include self
    adj = A.unsqueeze(0).as_subclass(_Adj)
    torch.manual_seed(seed)
    model = _DeepInfRegressor(layer_cls, x.size(1) + 1)
    return _fit_and_counterfact(model, lambda f: model(f, adj), x, treatment, y, _neighbour_lists(edge_index, n), seed)


def run_inflect(x, edge_index, treatment, y, seed: int = 0, repo: Path | None = None) -> dict:
    repo = repo or inflect_dir()
    if repo is None:
        raise RuntimeError("set GAIL_INFLECT_DIR to a clone of github.com/Banking-Analytics-Lab/INFLECT")
    gnns = _import_from(repo, "models.GNNs")
    decoder = _import_from(repo, "models.decoder")
    n = x.size(0)
    ei = torch.cat([edge_index, edge_index.flip(0)], dim=1).unique(dim=1)
    ea = torch.ones(ei.size(1), 1)
    torch.manual_seed(seed)
    model = _InflectRegressor(gnns, decoder, x.size(1) + 1)
    return _fit_and_counterfact(model, lambda f: model(f, ei, ea), x, treatment, y, _neighbour_lists(edge_index, n), seed)
