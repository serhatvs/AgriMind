"""CLI wrapper for the deterministic AgriMind demo seed."""

from app.seeds.data import SEED_TAG, build_crop_specs, build_field_specs, build_seed_dataset, build_soil_specs
from app.seeds.runner import main, run_seed, seed


if __name__ == "__main__":
    main()
