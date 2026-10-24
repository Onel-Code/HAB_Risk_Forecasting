import ee

from earth_engine_client import initialize_earth_engine


def main():
    initialize_earth_engine()

    result = ee.Number(1).getInfo()

    print("Earth Engine connection successful.")
    print(f"API test result: {result}")


if __name__ == "__main__":
    main()
