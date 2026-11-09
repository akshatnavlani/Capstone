"""Final score with value for money (7 Nov 2026 formula)."""
import pytest


def test_value_score_formula():
    # 7 Nov 2026: 100 x (0.4 value + 0.3 mood + 0.3 fit), -10 if mood < 0.3
    from app.fusion import compute_value_score
    final, lo, hi, adj = compute_value_score(1.0, 0.5, 0.5, 10.0)
    assert final == pytest.approx(70.0) and adj == 0.0 and (lo, hi) == (pytest.approx(64.0), pytest.approx(76.0))
    final, _lo, _hi, adj = compute_value_score(0.5, 0.2, 0.6, 0.0)
    assert adj == -10.0 and final == pytest.approx(100 * (0.2 + 0.06 + 0.18) - 10)
    assert compute_value_score(0.0, 0.0, 0.0, 5.0)[0] == 0.0
