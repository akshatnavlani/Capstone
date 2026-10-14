"""Tests for spoken_scan.scan_one with a fake caption source (no network, no database)."""
import shutil

_w = shutil.which
shutil.which = lambda n, *a, **k: "stub" if n == "opencli" else _w(n, *a, **k)
import spoken_scan as ss  # noqa: E402
shutil.which = _w


class _Seg:
    def __init__(self, text):
        self.text = text


class _Transcript:
    language_code = "hi"

    def __init__(self, text):
        self._text = text

    def fetch(self):
        return [_Seg(self._text)]


class _Listing:
    def __init__(self, transcript):
        self._t = transcript

    def find_transcript(self, languages):
        if self._t is None:
            raise LookupError("no transcript")
        return self._t

    def __iter__(self):
        return iter([] if self._t is None else [self._t])


class _Api:
    def __init__(self, transcript):
        self._t = transcript

    def list(self, video_id):
        return _Listing(self._t)


def test_scan_finds_a_spoken_brand_with_a_code():
    has, lang, n, ev = ss.scan_one(_Api(_Transcript("ये वेलकोर का क्रिएटीन है, डिस्क्रिप्शन में लिंक है और कोड ANAND30 यूज़ करो")), "v1")
    assert has and lang == "hi" and n > 0 and "spoken:brand:Wellcore(code)" in ev


def test_scan_of_a_video_without_captions_is_recorded_as_none():
    assert ss.scan_one(_Api(None), "v2") == (False, None, 0, [])


def test_scan_of_plain_talk_has_no_evidence():
    assert ss.scan_one(_Api(_Transcript("today we train chest and triceps")), "v3")[3] == []
