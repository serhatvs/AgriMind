from app.ml.mock_training_data import generate_mock_training_samples
from app.ml.yield_pipeline import YieldPredictionPipeline


def test_yield_pipeline_builds_feature_matrix_and_targets():
    samples = generate_mock_training_samples(sample_count=40)

    pipeline = YieldPredictionPipeline()
    dataset = pipeline.build_dataset(samples)

    assert len(dataset.X) == 40
    assert len(dataset.y) == 40
    assert len(dataset.feature_names) == len(dataset.X[0])
    assert dataset.y[0] > 0


def test_yield_pipeline_trains_and_predicts_range():
    samples = generate_mock_training_samples(sample_count=120)

    pipeline = YieldPredictionPipeline().fit(samples, random_seed=123)
    prediction = pipeline.predict(samples[0].features, field_id=11, crop_id=7)

    assert prediction.predicted_yield_per_hectare > 0
    assert prediction.predicted_yield_range.min <= prediction.predicted_yield_per_hectare
    assert prediction.predicted_yield_range.max >= prediction.predicted_yield_per_hectare
    assert 0 <= prediction.confidence_score <= 1
    assert prediction.model_version == "yield-xgb-v1"
