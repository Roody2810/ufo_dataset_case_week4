import os
import requests
import pandas as pd
import streamlit as st
import kaggle

from src.reverse_geocoding import fill_missing_countries


class KaggleDataLoader:
    def __init__(self, dataset_path, download_dir="./data"):
        self.dataset_path = dataset_path
        self.download_dir = download_dir

    def fetch_data(self, expected_filename):
        target_file_path = os.path.join(self.download_dir, expected_filename)
        
        if not os.path.exists(target_file_path):
            os.makedirs(self.download_dir, exist_ok=True)
            kaggle.api.dataset_download_files(
                self.dataset_path,
                path=self.download_dir,
                unzip=True,
            )

    def load_csv(self, filename):
        self.fetch_data(expected_filename=filename)
        file_path = os.path.join(self.download_dir, filename)
        return pd.read_csv(file_path, low_memory=False)


@st.cache_data
def load_ufo_dataset():
    loader = KaggleDataLoader("camnugent/ufo-sightings-around-the-world")
    df = loader.load_csv("ufo_sighting_data.csv")
    return fill_missing_countries(df)


@st.cache_data
def load_population_data():
    url = "https://statisticsoftheworld.com/api/v1/rankings/SP.POP.TOTL?format=json"
    try:
        response = requests.get(url, timeout=10)
        if response.status_code == 200:
            json_data = response.json()
            records = json_data.get("data", [])
            pop_df = pd.DataFrame(records)
            
            if 'value' in pop_df.columns:
                pop_df = pop_df.rename(columns={'value': 'population'})
            return pop_df
    except Exception as e:
        print(f"Fout bij ophalen populatiedata: {e}")
        
    return pd.DataFrame()


@st.cache_data
def load_combined_data():
    ufo_df = load_ufo_dataset()
    pop_df = load_population_data()
    
    if not pop_df.empty:
        if 'countryId' in pop_df.columns:
            pop_df['countryId_clean'] = pop_df['countryId'].astype(str).str.strip().str.upper()
        
        # Koppelen op ISO-3
        combined_df = pd.merge(
            ufo_df,
            pop_df[['countryId_clean', 'population']],
            left_on='iso3',
            right_on='countryId_clean',
            how='left'
        )
        
        # Fallback op ISO-2 voor rijen die geen match hadden
        unmatched_mask = combined_df['population'].isna()
        if unmatched_mask.any() and 'country_clean' in ufo_df.columns:
            pop_map = pop_df.set_index('countryId_clean')['population'].to_dict()
            combined_df.loc[unmatched_mask, 'population'] = (
                combined_df.loc[unmatched_mask, 'country_clean']
                .astype(str)
                .str.strip()
                .str.upper()
                .map(pop_map)
            )

        return combined_df.drop(columns=['countryId_clean'], errors='ignore')
            
    return ufo_df