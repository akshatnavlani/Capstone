"""Animated picture of OUR creator graph for the first slide of the deck (1 Nov 2026): the real creators and real links from the running backend
(collaboration, co-occurrence and @mention links), drifting gently, with a ripple travelling out hop by hop from the two best-connected creators.
The ripple shows how far a link chain reaches; it is an illustration of the pathways, not an effect (we find no detectable spillover).

Needs the backend running on port 8000. Output is a looping GIF (PowerPoint plays it in slideshow mode).

    python scripts/make_graph_animation.py [--out exports/creator_graph_animation.gif] [--api http://127.0.0.1:8000]
"""
import argparse
import json
import math
import urllib.request
from collections import deque
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402
from matplotlib import font_manager  # noqa: E402
from matplotlib.collections import LineCollection  # noqa: E402
from PIL import Image  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
ap = argparse.ArgumentParser()
ap.add_argument("--out", default=str(ROOT / "exports" / "creator_graph_animation.gif"))
ap.add_argument("--api", default="http://127.0.0.1:8000")
ap.add_argument("--frames", type=int, default=72)
ap.add_argument("--fps", type=int, default=18)
ap.add_argument("--width", type=int, default=1280)
args = ap.parse_args()

FD = Path(r"C:\Windows\Fonts")
font_manager.fontManager.addfont(str(FD / "segoeuib.ttf"))
BG, INK = "#f1efea", "#111111"
CAT = {"fitness_influencer": "#33cccc", "athlete": "#e0a020", "team": "#0033cc", "league": "#8a949e", "lifestyle_influencer": "#e0508a", "other": "#8a949e"}
HOP = ["#ffffff", "#e0a020", "#33cccc", "#0033cc"]  # the chosen creator, then one colour per hop


def get(path, timeout=120):
    with urllib.request.urlopen(args.api + path, timeout=timeout) as r:
        return json.loads(r.read().decode("utf-8"))


print("loading the graph from the backend (the @mention links take about 10 s)...")
creators = {c["creator_id"]: c for c in get("/feature-store/creators/summary")}
pairs = {}
for path in ("/feature-store/edges/collaborations", "/feature-store/edges/co-occurrence", "/feature-store/edges/mentions"):
    for e in get(path):
        a, b = e["source_creator_id"], e["target_creator_id"]
        if a != b:
            pairs[tuple(sorted((a, b)))] = max(pairs.get(tuple(sorted((a, b))), 0), e["weight"])
ids = sorted({i for p in pairs for i in p})
idx = {c: i for i, c in enumerate(ids)}
E = np.array([(idx[a], idx[b]) for a, b in pairs])
W = np.array(list(pairs.values()), dtype=float)
n = len(ids)
deg = np.bincount(E.ravel(), minlength=n)
print(f"{n} creators, {len(E)} links")

# --- layout: a plain force-directed layout (repulsion between all dots, springs along links), fixed seed so the picture is always the same ------------------
rng = np.random.default_rng(7)
pos = rng.normal(size=(n, 2))
k = 1.0 / math.sqrt(n) * 3.6
for it in range(600):
    d = pos[:, None, :] - pos[None, :, :]
    dist = np.linalg.norm(d, axis=2) + 1e-3
    force = (d / dist[..., None]) * ((k * k) / dist)[..., None]
    disp = force.sum(axis=1)
    dv = pos[E[:, 0]] - pos[E[:, 1]]
    dl = np.linalg.norm(dv, axis=1) + 1e-3
    pull = (dv / dl[:, None]) * ((dl * dl) / k * (0.22 + 0.06 * np.log1p(W)))[:, None]
    np.add.at(disp, E[:, 0], -pull)
    np.add.at(disp, E[:, 1], pull)
    disp -= pos * 0.5  # weak gravity keeps the isolated clusters in view
    step = 0.06 * (1 - it / 600) + 0.003
    norm = np.linalg.norm(disp, axis=1)[:, None] + 1e-9
    pos += disp / norm * np.minimum(norm, step)
pos -= pos.mean(axis=0)
span = np.abs(pos).max(axis=0)
pos = pos / span  # now within [-1, 1] on both axes

# --- hop distances from the two best-connected creators --------------------------------------------------------------------------------------------------------
adj = [[] for _ in range(n)]
for a, b in E:
    adj[a].append(b)
    adj[b].append(a)


def hops_from(src, limit=3):
    dist = np.full(n, 99)
    dist[src] = 0
    q = deque([src])
    while q:
        v = q.popleft()
        if dist[v] >= limit:
            continue
        for w in adj[v]:
            if dist[w] == 99:
                dist[w] = dist[v] + 1
                q.append(w)
    return dist


order = np.argsort(-deg)
first = int(order[0])
d_first = hops_from(first, limit=6)
# the second ripple starts from the best-connected creator that is far from the first, so the two ripples light up different parts of the graph
second = next(int(v) for v in order[1:] if d_first[v] >= 3)
hubs = [first, second]
hop = [hops_from(h) for h in hubs]
phase_off = [0.0, 0.5]  # the second ripple runs half a cycle behind


def lit(h, u):
    """0..1 brightness of hop level h at cycle position u (0..1); the picture is dark at u = 0 and u = 1, so the loop is seamless."""
    centre = 0.12 + 0.2 * h
    return max(0.0, 1 - abs(u - centre) / 0.2)


# --- drawing -----------------------------------------------------------------------------------------------------------------------------------------------------
W_PX = args.width
H_PX = int(W_PX * 9 / 16)
fig = plt.figure(figsize=(W_PX / 100, H_PX / 100), dpi=100, facecolor=BG)
ax = fig.add_axes([0, 0, 1, 1], facecolor=BG)
ax.set_xlim(-1.2, 1.2)
ax.set_ylim(-0.675, 0.675)
ax.axis("off")
# stretch the layout to the 16:9 frame
scale = np.array([1.12, 0.64])
base = pos * scale
phi = rng.uniform(0, 2 * math.pi, size=(n, 2))
kx = rng.integers(1, 3, size=(n, 2))  # whole numbers of wiggles per loop, so the loop closes exactly
amp = 0.012

node_color = np.array([CAT.get(creators.get(c, {}).get("category") or "other", CAT["other"]) for c in ids])
size = 14 + 5.2 * np.sqrt(deg)
top_labels = []
for i in (int(v) for v in order[:40]):
    if all(np.linalg.norm(base[i] - base[j]) > 0.16 for j in top_labels):
        top_labels.append(i)
    if len(top_labels) == 7:
        break
names = [creators.get(c, {}).get("name", "") for c in ids]

frames = []
for f in range(args.frames):
    u = f / args.frames
    ax.clear()
    ax.set_xlim(-1.2, 1.2)
    ax.set_ylim(-0.675, 0.675)
    ax.axis("off")
    p = base + amp * np.stack([np.sin(2 * math.pi * kx[:, 0] * u + phi[:, 0]), np.cos(2 * math.pi * kx[:, 1] * u + phi[:, 1])], axis=1)

    # the level each dot and link has been lit to, from either ripple (the brighter one wins)
    node_level = np.zeros(n)
    node_hop = np.zeros(n, dtype=int)
    for r, h0 in enumerate(hubs):
        ur = (u + phase_off[r]) % 1.0
        for v in np.where(hop[r] <= 3)[0]:
            lv = 1.0 if hop[r][v] == 0 else lit(int(hop[r][v]), ur)
            if lv > node_level[v]:
                node_level[v], node_hop[v] = lv, int(hop[r][v])
    ea, eb = E[:, 0], E[:, 1]
    edge_level = np.minimum(node_level[ea], node_level[eb])
    edge_hop = np.maximum(node_hop[ea], node_hop[eb])

    segs = np.stack([p[ea], p[eb]], axis=1)
    ax.add_collection(LineCollection(segs, colors=INK, linewidths=0.5, alpha=0.10, zorder=1))
    on = edge_level > 0.05
    if on.any():
        cols = [HOP[min(h, 3)] if h > 0 else HOP[1] for h in edge_hop[on]]
        ax.add_collection(LineCollection(segs[on], colors=cols, linewidths=0.8 + 2.2 * edge_level[on], alpha=0.25 + 0.7 * edge_level[on], zorder=2))

    # ripple rings from the two hubs
    for r, h0 in enumerate(hubs):
        ur = (u + phase_off[r]) % 1.0
        radius = 0.02 + 0.85 * ur
        ax.add_patch(plt.Circle(p[h0], radius, fill=False, ec=HOP[1], lw=1.6, alpha=max(0.0, 0.55 * (1 - ur)), zorder=3))

    # glow for lit dots, then the dots
    glow = node_level > 0.05
    if glow.any():
        gc = [HOP[min(h, 3)] if h > 0 else HOP[1] for h in node_hop[glow]]
        ax.scatter(p[glow, 0], p[glow, 1], s=size[glow] * (3.5 + 6 * node_level[glow]), c=gc, alpha=0.18, linewidths=0, zorder=4)
    ax.scatter(p[:, 0], p[:, 1], s=size, c=node_color, edgecolors=BG, linewidths=0.8, zorder=5, alpha=0.95)
    for h0 in hubs:
        ax.scatter(p[h0, 0], p[h0, 1], s=size[h0] * 1.5, c=node_color[h0], edgecolors=INK, linewidths=2.0, zorder=6)
    for i in top_labels:
        ax.text(p[i, 0] + 0.018, p[i, 1] + 0.03, names[i], fontsize=9.5, fontfamily="Segoe UI", fontweight="bold", color=INK, zorder=7,
                bbox=dict(boxstyle="round,pad=0.12", fc=BG, ec="none", alpha=0.75))

    fig.canvas.draw()
    img = Image.fromarray(np.asarray(fig.canvas.buffer_rgba())).convert("RGB")
    frames.append(img.quantize(colors=128, method=Image.Quantize.MEDIANCUT, dither=Image.Dither.NONE))
    if f % 12 == 0:
        print("frame", f, "of", args.frames)

frames[0].save(args.out, save_all=True, append_images=frames[1:], duration=int(1000 / args.fps), loop=0, optimize=True, disposal=1)
print("saved", args.out, f"{Path(args.out).stat().st_size / 1e6:.1f} MB", f"{W_PX}x{H_PX}", f"{args.frames} frames at {args.fps} fps")
