import io
from unittest.mock import patch

import pytest
import torch
from PIL import Image

from ml.feature_extraction import FeatureExtractor, RawCreatorRecord
from ml.schema import BERT_DIM, CLIP_DIM, CREATOR_FEATURE_DIM


@pytest.fixture(scope="module")
def extractor():
    # Real CLIP + BERT models -- slow to load (~seconds once cached, ~60s
    # cold). Network is mocked per-test below; model inference itself is
    # real, since that's the actual integration point worth testing.
    return FeatureExtractor(max_thumbnails=2)


def _fake_jpeg_bytes() -> bytes:
    img = Image.new("RGB", (64, 64), color=(120, 50, 200))
    buf = io.BytesIO()
    img.save(buf, format="JPEG")
    return buf.getvalue()


class _FakeResponse:
    def __init__(self, content: bytes):
        self.content = content

    def raise_for_status(self):
        pass


def test_bert_embedding_shape(extractor):
    emb = extractor._bert_embedding("a real sentence about fitness training")
    assert emb.shape == (BERT_DIM,)


def test_bert_embedding_zero_for_empty_text(extractor):
    emb = extractor._bert_embedding("")
    assert torch.equal(emb, torch.zeros(BERT_DIM))


def test_clip_embedding_shape_with_mocked_thumbnail(extractor):
    with patch("ml.feature_extraction.requests.get", return_value=_FakeResponse(_fake_jpeg_bytes())):
        emb = extractor._clip_embedding(["https://example.com/fake.jpg"])
    assert emb.shape == (CLIP_DIM,)


def test_clip_embedding_zero_for_no_thumbnails(extractor):
    emb = extractor._clip_embedding([])
    assert torch.equal(emb, torch.zeros(CLIP_DIM))


def test_clip_embedding_skips_broken_url_without_crashing(extractor):
    # Regression guard for the exact real-world shape: a single bad
    # thumbnail URL must not take down the whole creator's feature vector.
    with patch("ml.feature_extraction.requests.get", side_effect=OSError("network down")):
        emb = extractor._clip_embedding(["https://example.com/broken.jpg"])
    assert torch.equal(emb, torch.zeros(CLIP_DIM))


def test_extract_full_pipeline_handles_real_stub_creator_shape(extractor):
    # Mirrors the real "lebron" row from the live feature-store API
    # (2026-08-09): a seed creator with no subscriber count, no text, no
    # thumbnails at all -- every optional field is None/empty.
    record = RawCreatorRecord(
        category_one_hot=[0, 0, 0, 0, 0, 1],
        log_subscriber_count=None,
        engagement_rate=None,
        reputation_score=None,
        raw_text="",
        thumbnail_urls=[],
    )
    vec = extractor.extract(record)
    assert vec.shape == (CREATOR_FEATURE_DIM,)
    assert not vec.isnan().any()


def test_extract_full_pipeline_with_populated_creator(extractor):
    record = RawCreatorRecord(
        category_one_hot=[0, 0, 0, 0, 0, 1],
        log_subscriber_count=16.47,
        engagement_rate=0.035,
        reputation_score=None,
        raw_text="Welcome to a fitness channel about strength training.",
        thumbnail_urls=["https://example.com/fake.jpg"],
    )
    with patch("ml.feature_extraction.requests.get", return_value=_FakeResponse(_fake_jpeg_bytes())):
        vec = extractor.extract(record)
    assert vec.shape == (CREATOR_FEATURE_DIM,)
    assert not vec.isnan().any()
    assert not torch.equal(vec, torch.zeros(CREATOR_FEATURE_DIM))
