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
    prediction = pipeline.predict(samples[0].features)

    assert prediction.predicted_yield > 0
    assert prediction.yield_range_min <= prediction.predicted_yield
    assert prediction.yield_range_max >= prediction.predicted_yield
    assert 0 <= prediction.confidence <= 1
    assert prediction.provider_version == "yield-xgb-v1"
    assert prediction.generated_at.tzinfo is not None
