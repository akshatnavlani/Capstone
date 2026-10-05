"""Keep the backend tests fast and offline: the creator feature score loads CLIP
and BERT in a background thread, which tests must never trigger. Tests of that
service call its functions directly with fake embedders."""
import os

os.environ.setdefault("CREATOR_FEATURES_DISABLED", "1")
