import os
import pandas as pd
from dotenv import load_dotenv
load_dotenv()

KAGGLE_API_KEY = os.getenv("KAGGLE_API_token")
KAGGLE_USERNAME = os.getenv("KAGGLE_USERNAME")

import kaggle

class kaggleDataLoader:
    def __init__(self, dataset_path, download_dir= "../data"):
        self.dataset_path = dataset_path
        self.download_dir = download_dir

    def fetch_data(self, expected_filename):

        target_file_path = os.path.join(self.download_dir, expected_filename)
        if not os.path.exists(target_file_path):
            print(f"Downloading data self{self.dataset_path}")
            os.makedirs(self.download_dir, exist_ok=True)

            kaggle.api.dataset_download_files(
                self.dataset_path,
                path=self.download_dir,
                unzip=True,
            )
        else:
            print(f"dataset already exists at {target_file_path}")

    def load_csv(self, filename):
        self.fetch_data(expected_filename = filename)
        file_path = os.path.join(self.download_dir, filename)
        return pd.read_csv(file_path)

loader = kaggleDataLoader("camnugent/ufo-sightings-around-the-world")
df = loader.load_csv("ufo_sighting_data.csv")










