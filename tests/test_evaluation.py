import pytest
import torch

from ml.evaluation import evaluate_predictions


def test_perfect_predictions_give_ideal_metrics():
    predictions = torch.tensor([1.0, 2.0, 3.0, 4.0])
    targets = torch.tensor([1.0, 2.0, 3.0, 4.0])

    report = evaluate_predictions(predictions, targets)

    assert report.mae == pytest.approx(0.0, abs=1e-6)
    assert report.rmse == pytest.approx(0.0, abs=1e-6)
    assert report.r2 == pytest.approx(1.0, abs=1e-6)
    assert report.calibration_slope == pytest.approx(1.0, abs=1e-6)
    assert report.calibration_intercept == pytest.approx(0.0, abs=1e-6)
    assert report.n == 4


def test_known_mae_and_rmse_values():
    predictions = torch.tensor([0.0, 0.0])
    targets = torch.tensor([3.0, 4.0])
    # residuals: -3, -4 -> mae = 3.5, rmse = sqrt((9+16)/2) = sqrt(12.5)

    report = evaluate_predictions(predictions, targets)

    assert report.mae == pytest.approx(3.5)
    assert report.rmse == pytest.approx(12.5 ** 0.5)


def test_empty_inputs_return_nan_not_crash():
    predictions = torch.empty(0)
    targets = torch.empty(0)

    report = evaluate_predictions(predictions, targets)

    assert report.n == 0
    assert report.mae != report.mae  # NaN


def test_constant_targets_give_nan_r2_not_crash():
    # ss_tot == 0 would otherwise be a division by zero.
    predictions = torch.tensor([1.0, 2.0, 3.0])
    targets = torch.full((3,), 5.0)

    report = evaluate_predictions(predictions, targets)

    assert report.r2 != report.r2  # NaN
    assert report.mae == report.mae  # MAE is still well-defined


def test_constant_predictions_give_nan_calibration_not_crash():
    # Zero-variance predictions make the calibration-slope denominator 0.
    predictions = torch.full((3,), 2.0)
    targets = torch.tensor([1.0, 2.0, 3.0])

    report = evaluate_predictions(predictions, targets)

    assert report.calibration_slope != report.calibration_slope  # NaN
    assert report.calibration_intercept != report.calibration_intercept  # NaN


def test_shape_mismatch_raises():
    with pytest.raises(ValueError):
        evaluate_predictions(torch.zeros(3), torch.zeros(4))
