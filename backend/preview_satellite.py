import ee

PROJECT_ID = "hab-risk-forecasting"

# Temporary test location and radius.
TEST_LATITUDE = 14.30
TEST_LONGITUDE = 121.25
TEST_RADIUS_METRES = 500

IMAGE_ID = (
    "COPERNICUS/S2_SR_HARMONIZED/"
    "20261015T022131_20261015T023240_T51PUR"
)


def main():
    ee.Initialize(project=PROJECT_ID)

    area = ee.Geometry.Point(
        [TEST_LONGITUDE, TEST_LATITUDE]
    ).buffer(TEST_RADIUS_METRES)

    image = ee.Image(IMAGE_ID)

    rgb = (
        image.select(["B4", "B3", "B2"])
        .multiply(0.0001)
        .clip(area)
    )

    water_mask = image.select("SCL").eq(6)
    masked_rgb = rgb.updateMask(water_mask)

    options = {
        "region": area.bounds(),
        "dimensions": 600,
        "min": 0,
        "max": 0.15,
        "format": "png",
    }

    print("Original image preview:")
    print(rgb.getThumbURL(options))

    print("\nWater-masked image preview:")
    print(masked_rgb.getThumbURL(options))


if __name__ == "__main__":
    main()
