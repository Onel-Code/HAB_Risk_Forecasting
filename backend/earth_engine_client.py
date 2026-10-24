import ee

PROJECT_ID = "hab-risk-forecasting"


def initialize_earth_engine():
    """Initialize Earth Engine using previously authorized credentials."""
    ee.Initialize(project=PROJECT_ID)
