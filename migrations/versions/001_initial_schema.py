"""Initial schema

Revision ID: 001
Revises: 
Create Date: 2024-01-01 00:00:00.000000

"""
from alembic import op
import sqlalchemy as sa

revision = '001'
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        'fields',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('name', sa.String(), nullable=False),
        sa.Column('location', sa.String(), nullable=False),
        sa.Column('area_hectares', sa.Float(), nullable=False),
        sa.Column('slope_percent', sa.Float(), nullable=True),
        sa.Column('irrigation_available', sa.Boolean(), nullable=True),
        sa.Column('drainage_quality', sa.String(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.Column('updated_at', sa.DateTime(), nullable=True),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index(op.f('ix_fields_id'), 'fields', ['id'], unique=False)

    op.create_table(
        'crop_profiles',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('name', sa.String(), nullable=False),
        sa.Column('variety', sa.String(), nullable=True),
        sa.Column('min_ph', sa.Float(), nullable=False),
        sa.Column('max_ph', sa.Float(), nullable=False),
        sa.Column('optimal_ph_min', sa.Float(), nullable=False),
        sa.Column('optimal_ph_max', sa.Float(), nullable=False),
        sa.Column('min_nitrogen_ppm', sa.Float(), nullable=False),
        sa.Column('min_phosphorus_ppm', sa.Float(), nullable=False),
        sa.Column('min_potassium_ppm', sa.Float(), nullable=False),
        sa.Column('water_requirement', sa.String(), nullable=False),
        sa.Column('drainage_requirement', sa.String(), nullable=False),
        sa.Column('preferred_soil_textures', sa.String(), nullable=False),
        sa.Column('min_area_hectares', sa.Float(), nullable=True),
        sa.Column('max_slope_percent', sa.Float(), nullable=True),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index(op.f('ix_crop_profiles_id'), 'crop_profiles', ['id'], unique=False)

    op.create_table(
        'soil_tests',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('field_id', sa.Integer(), nullable=False),
        sa.Column('ph_level', sa.Float(), nullable=False),
        sa.Column('nitrogen_ppm', sa.Float(), nullable=False),
        sa.Column('phosphorus_ppm', sa.Float(), nullable=False),
        sa.Column('potassium_ppm', sa.Float(), nullable=False),
        sa.Column('organic_matter_percent', sa.Float(), nullable=False),
        sa.Column('soil_texture', sa.String(), nullable=False),
        sa.Column('tested_at', sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(['field_id'], ['fields.id'], ),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index(op.f('ix_soil_tests_id'), 'soil_tests', ['id'], unique=False)

    op.create_table(
        'recommendations',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('field_id', sa.Integer(), nullable=False),
        sa.Column('crop_id', sa.Integer(), nullable=False),
        sa.Column('suitability_score', sa.Float(), nullable=False),
        sa.Column('rank', sa.Integer(), nullable=False),
        sa.Column('explanation', sa.Text(), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(['crop_id'], ['crop_profiles.id'], ),
        sa.ForeignKeyConstraint(['field_id'], ['fields.id'], ),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index(op.f('ix_recommendations_id'), 'recommendations', ['id'], unique=False)


def downgrade() -> None:
    op.drop_index(op.f('ix_recommendations_id'), table_name='recommendations')
    op.drop_table('recommendations')
    op.drop_index(op.f('ix_soil_tests_id'), table_name='soil_tests')
    op.drop_table('soil_tests')
    op.drop_index(op.f('ix_crop_profiles_id'), table_name='crop_profiles')
    op.drop_table('crop_profiles')
    op.drop_index(op.f('ix_fields_id'), table_name='fields')
    op.drop_table('fields')
