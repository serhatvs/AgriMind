"""Seed script to populate the database with sample data."""
from app.database import SessionLocal, Base, engine
from app.models.field import Field
from app.models.soil_test import SoilTest
from app.models.crop_profile import CropProfile
from datetime import datetime


def seed():
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()

    try:
        fields = [
            Field(name="North Valley Farm", location="North Valley", area_hectares=25.0, slope_percent=2.0,
                  irrigation_available=True, drainage_quality="excellent"),
            Field(name="South Meadow", location="South District", area_hectares=15.0, slope_percent=5.0,
                  irrigation_available=True, drainage_quality="good"),
            Field(name="East Ridge Plot", location="East Ridge", area_hectares=10.0, slope_percent=12.0,
                  irrigation_available=False, drainage_quality="moderate"),
            Field(name="West Flatlands", location="West Plains", area_hectares=30.0, slope_percent=1.0,
                  irrigation_available=False, drainage_quality="poor"),
            Field(name="Central Basin", location="Central Zone", area_hectares=20.0, slope_percent=3.0,
                  irrigation_available=True, drainage_quality="good"),
        ]
        db.add_all(fields)
        db.commit()
        for f in fields:
            db.refresh(f)

        soil_tests = [
            SoilTest(field_id=fields[0].id, ph_level=6.5, nitrogen_ppm=50.0, phosphorus_ppm=35.0,
                     potassium_ppm=220.0, organic_matter_percent=4.2, soil_texture="loamy"),
            SoilTest(field_id=fields[1].id, ph_level=6.8, nitrogen_ppm=40.0, phosphorus_ppm=28.0,
                     potassium_ppm=180.0, organic_matter_percent=3.5, soil_texture="silty"),
            SoilTest(field_id=fields[2].id, ph_level=5.8, nitrogen_ppm=20.0, phosphorus_ppm=15.0,
                     potassium_ppm=120.0, organic_matter_percent=2.1, soil_texture="sandy"),
            SoilTest(field_id=fields[3].id, ph_level=7.2, nitrogen_ppm=35.0, phosphorus_ppm=22.0,
                     potassium_ppm=160.0, organic_matter_percent=2.8, soil_texture="clay"),
            SoilTest(field_id=fields[4].id, ph_level=6.3, nitrogen_ppm=45.0, phosphorus_ppm=30.0,
                     potassium_ppm=200.0, organic_matter_percent=3.8, soil_texture="loamy"),
        ]
        db.add_all(soil_tests)
        db.commit()

        crops = [
            CropProfile(name="Wheat", variety="Winter Wheat", min_ph=5.5, max_ph=7.5, optimal_ph_min=6.0,
                        optimal_ph_max=7.0, min_nitrogen_ppm=30.0, min_phosphorus_ppm=20.0,
                        min_potassium_ppm=150.0, water_requirement="medium", drainage_requirement="good",
                        preferred_soil_textures="loamy,silty", min_area_hectares=1.0, max_slope_percent=10.0),
            CropProfile(name="Corn", variety="Sweet Corn", min_ph=5.8, max_ph=7.0, optimal_ph_min=6.0,
                        optimal_ph_max=6.8, min_nitrogen_ppm=40.0, min_phosphorus_ppm=25.0,
                        min_potassium_ppm=180.0, water_requirement="high", drainage_requirement="moderate",
                        preferred_soil_textures="loamy,silty", min_area_hectares=2.0, max_slope_percent=5.0),
            CropProfile(name="Soybeans", variety=None, min_ph=6.0, max_ph=7.0, optimal_ph_min=6.2,
                        optimal_ph_max=6.8, min_nitrogen_ppm=20.0, min_phosphorus_ppm=20.0,
                        min_potassium_ppm=150.0, water_requirement="medium", drainage_requirement="good",
                        preferred_soil_textures="loamy,clay", min_area_hectares=1.0, max_slope_percent=8.0),
            CropProfile(name="Rice", variety="Long Grain", min_ph=5.5, max_ph=6.5, optimal_ph_min=5.8,
                        optimal_ph_max=6.2, min_nitrogen_ppm=35.0, min_phosphorus_ppm=25.0,
                        min_potassium_ppm=160.0, water_requirement="high", drainage_requirement="poor",
                        preferred_soil_textures="clay,silty", min_area_hectares=2.0, max_slope_percent=2.0),
            CropProfile(name="Sunflower", variety=None, min_ph=6.0, max_ph=7.5, optimal_ph_min=6.5,
                        optimal_ph_max=7.2, min_nitrogen_ppm=25.0, min_phosphorus_ppm=15.0,
                        min_potassium_ppm=130.0, water_requirement="low", drainage_requirement="moderate",
                        preferred_soil_textures="loamy,sandy", min_area_hectares=1.0, max_slope_percent=12.0),
        ]
        db.add_all(crops)
        db.commit()
        print("Seed data created successfully.")
    finally:
        db.close()


if __name__ == "__main__":
    seed()
