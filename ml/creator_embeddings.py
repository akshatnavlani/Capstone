"""Embedding helpers for the creator feature score (PendingWork S2).

Creators are embedded once, offline, by `scripts/compute_creator_embeddings.py`
using the existing `FeatureExtractor`: CLIP for thumbnails, and for text both
CLIP's text encoder and BERT (mean pooled).
At request time only the brand's product category has to be embedded, with the
same two models, and compared with the stored creator vectors.

`QueryEmbedder` takes its two encoders as plain callables so the scoring path
is testable with fakes; `QueryEmbedder.from_extractor` builds the real one from
an already loaded `FeatureExtractor`.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Callable

import numpy as np


def _as_vector(out) -> np.ndarray:
    """transformers 5 returns an output object with `.pooler_output` instead of
    a bare tensor for `get_*_features`; accept both."""
    t = out if hasattr(out, "detach") else out.pooler_output
    return t.detach().cpu().numpy().reshape(-1).astype(np.float32)


def clip_text_vector(extractor, text: str) -> np.ndarray:
    """CLIP text embedding (512-d). Lives in the same space as the CLIP image
    vectors, so it compares with thumbnails and with other CLIP text vectors."""
    import torch

    inputs = extractor.clip_processor(text=[text], return_tensors="pt", padding=True, truncation=True, max_length=77).to(extractor.device)
    with torch.no_grad():
        return _as_vector(extractor.clip_model.get_text_features(**inputs))


def bert_mean_vector(extractor, text: str) -> np.ndarray:
    """BERT text embedding (768-d): mean of the token vectors. Compares meaning
    better than BERT's pooled [CLS] output, which mostly reflects style and length
    (measured on the real creators in PendingWork S2)."""
    import torch

    inputs = extractor.bert_tokenizer(text, return_tensors="pt", truncation=True, max_length=256, padding=True).to(extractor.device)
    with torch.no_grad():
        return extractor.bert_model(**inputs).last_hidden_state[0].mean(dim=0).cpu().numpy().astype(np.float32)


@dataclass
class QueryEmbedder:
    clip_text: Callable[[str], np.ndarray]  # 512-d, same space as the CLIP image vectors and CLIP text vectors
    bert_text: Callable[[str], np.ndarray]  # 768-d, same space as the BERT text vectors

    @classmethod
    def from_extractor(cls, extractor) -> "QueryEmbedder":
        return cls(lambda q: clip_text_vector(extractor, q), lambda q: bert_mean_vector(extractor, q))
