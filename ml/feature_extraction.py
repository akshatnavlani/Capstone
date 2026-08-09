"""CLIP + BERT feature extraction (Week 9-10 objective, prepped early per the
user's Weeks 7-8 direction: "better to find integration problems now with a
small real sample than at Week 9-10 with a large one").

Consumes exactly Track C's `/feature-store/creators` output shape
(`raw_text: str`, `thumbnail_urls: list[str]`) — checked against their real
`CreatorFeatureRecord` schema (origin/track-c-fusion-backend:backend/app/
schemas.py, 2026-08-09) rather than guessed.

Two real integration findings from testing against real scraped data
(3 real creators via the live feature-store API, 2026-08-09), both handled
here rather than left to surprise Weeks 9-10:

1. `transformers` 5.14.1's `CLIPModel.get_image_features()` does NOT return
   a plain tensor (as most tutorials/older versions show) — it returns a
   `BaseModelOutputWithPooling`, and the actual projected embedding is at
   `.pooler_output`. Verified empirically against a real YouTube thumbnail
   URL. Get this wrong and every CLIP embedding silently becomes a wrapper
   object, not a usable feature vector.
2. Real feature-store rows have partially-missing data: of 3 real creators
   fetched, one (`lebron`) is a fully empty stub (no subscriber count, no
   text, no thumbnails — a seed row with nothing scraped yet) and another
   (`kingjames`) has metadata but zero content. `log_subscriber_count`/
   `engagement_rate`/`reputation_score` can all be `None`. `ml/schema.py`'s
   tensor contract has no room for `None` — handled here by zero-filling,
   which is a real, debatable modeling choice (a creator with genuinely
   zero engagement becomes indistinguishable from a creator whose
   engagement was never measured), not a neutral default; revisit once real
   missing-data volume is large enough to justify a proper missing-value
   indicator instead.
"""

from __future__ import annotations

from dataclasses import dataclass
from io import BytesIO

import requests
import torch
from PIL import Image
from transformers import BertModel, BertTokenizer, CLIPModel, CLIPProcessor

from ml.schema import BERT_DIM, CLIP_DIM, NUM_CATEGORIES


@dataclass
class RawCreatorRecord:
    """Mirrors Track C's CreatorFeatureRecord (backend/app/schemas.py) —
    only the fields this module needs."""

    category_one_hot: list[int]
    log_subscriber_count: float | None
    engagement_rate: float | None
    reputation_score: float | None
    raw_text: str
    thumbnail_urls: list[str]


class FeatureExtractor:
    """Loads CLIP + BERT once; call `extract` per creator. Loading is slow
    (~60s each, real pretrained weights) — instantiate once, reuse.
    """

    def __init__(self, max_thumbnails: int = 5, device: str | None = None):
        self.device = torch.device(device or ("cuda" if torch.cuda.is_available() else "cpu"))
        self.max_thumbnails = max_thumbnails
        self.clip_model = CLIPModel.from_pretrained("openai/clip-vit-base-patch32").to(self.device).eval()
        self.clip_processor = CLIPProcessor.from_pretrained("openai/clip-vit-base-patch32")
        self.bert_tokenizer = BertTokenizer.from_pretrained("bert-base-uncased")
        self.bert_model = BertModel.from_pretrained("bert-base-uncased").to(self.device).eval()

    def _clip_embedding(self, thumbnail_urls: list[str]) -> torch.Tensor:
        images = []
        for url in thumbnail_urls[: self.max_thumbnails]:
            try:
                resp = requests.get(url, timeout=10)
                resp.raise_for_status()
                images.append(Image.open(BytesIO(resp.content)).convert("RGB"))
            except (requests.RequestException, OSError):
                continue  # a single bad/expired thumbnail URL shouldn't fail the whole creator
        if not images:
            return torch.zeros(CLIP_DIM)
        inputs = self.clip_processor(images=images, return_tensors="pt").to(self.device)
        with torch.no_grad():
            out = self.clip_model.get_image_features(**inputs)
        return out.pooler_output.mean(dim=0).cpu()  # mean-pool across thumbnails

    def _bert_embedding(self, raw_text: str) -> torch.Tensor:
        if not raw_text.strip():
            return torch.zeros(BERT_DIM)
        inputs = self.bert_tokenizer(
            raw_text, return_tensors="pt", truncation=True, max_length=512, padding=True
        ).to(self.device)
        with torch.no_grad():
            out = self.bert_model(**inputs)
        return out.pooler_output.squeeze(0).cpu()

    def extract(self, record: RawCreatorRecord) -> torch.Tensor:
        clip_vec = self._clip_embedding(record.thumbnail_urls)
        bert_vec = self._bert_embedding(record.raw_text)
        metadata = torch.tensor(
            [
                record.log_subscriber_count or 0.0,
                record.engagement_rate or 0.0,
                record.reputation_score or 0.0,
                *record.category_one_hot,
            ],
            dtype=torch.float32,
        )
        assert metadata.shape[0] == 3 + NUM_CATEGORIES
        return torch.cat([clip_vec, bert_vec, metadata])
