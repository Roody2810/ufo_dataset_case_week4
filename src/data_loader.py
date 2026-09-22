import os
import requests
import pandas as pd
import streamlit as st
import kaggle

# Importeer de verrijkingsfunctie uit je reverse_geocoding module
from src.reverse_geocoding import fill_missing_countries


class kaggleDataLoader:
    def __init__(self, dataset_path, download_dir="./data"):
        self.dataset_path = dataset_path
        self.download_dir = download_dir

    def fetch_data(self, expected_filename):
        target_file_path = os.path.join(self.download_dir, expected_filename)
        
        # Check of het bestand er al staat, zo niet: download het
        if not os.path.exists(target_file_path):
            print(f"Downloading data: {self.dataset_path}")
            os.makedirs(self.download_dir, exist_ok=True)

            kaggle.api.dataset_download_files(
                self.dataset_path,
                path=self.download_dir,
                unzip=True,
            )
        else:
            print(f"Dataset bestaat al op: {target_file_path}")

    def load_csv(self, filename):
        self.fetch_data(expected_filename=filename)
        file_path = os.path.join(self.download_dir, filename)
        return pd.read_csv(file_path, low_memory=False)


@st.cache_data
def load_ufo_dataset():
    loader = kaggleDataLoader("camnugent/ufo-sightings-around-the-world")
    df = loader.load_csv("ufo_sighting_data.csv")
    
    # 🌟 STAP 1 & 2: Vul ontbrekende landen via reverse geocoding & zet om naar ISO-3 + landnaam
    df = fill_missing_countries(df)
    
    return df


# --- POPULATIEDATA OPHALEN VIA REST API ---
@st.cache_data
def load_population_data():
    url = "https://statisticsoftheworld.com/api/v1/rankings/SP.POP.TOTL?format=json"
    try:
        response = requests.get(url, timeout=10)
        if response.status_code == 200:
            json_data = response.json()
            records = json_data.get("data", [])
            pop_df = pd.DataFrame(records)
            
            # De API geeft het bevolkingsaantal als 'value' terug
            if 'value' in pop_df.columns:
                pop_df = pop_df.rename(columns={'value': 'population'})
            return pop_df
    except Exception as e:
        print(f"Fout bij ophalen populatiedata via API: {e}")
        
    return pd.DataFrame()


# --- COMBINEREN VAN UFO DATA EN API POPULATIEDATA ---
# @st.cache_data
def load_combined_data():
    ufo_df = load_ufo_dataset()
    pop_df = load_population_data()
    
    # 🌟 STAP 3: Koppel de populatiedata uit de API direct op ISO-3 (met ISO-2 fallback)
    if not pop_df.empty:
        # Maak schone koppelkolom aan uit de API data
        if 'countryId' in pop_df.columns:
            pop_df['countryId_clean'] = pop_df['countryId'].astype(str).str.strip().str.upper()
        
        # 1. Eerst proberen te matchen op ISO-3 codes
        combined_df = pd.merge(
            ufo_df,
            pop_df[['countryId_clean', 'population']],
            left_on='iso3',
            right_on='countryId_clean',
            how='left'
        )
        
        # 2. Fallback: Als 'population' nog leeg is (NaN), probeer te matchen op 'country_clean' (ISO-2)
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

        # Opruimen van tijdelijke koppelkolom
        combined_df = combined_df.drop(columns=['countryId_clean'], errors='ignore')
        return combined_df
            
    return ufo_df


if __name__ == "__main__":
    combined_df = load_combined_data()
    combined_df = load_combined_data()

    print("=" * 60)
    print("VERRIJKTE DATAFRAME OVERZICHT:")
    print(f"Totaal aantal rijen: {len(combined_df):,}")
    usa_sightings = combined_df[combined_df['country_name'] == 'United States']['iso3'].count()
    if 'country_name' in combined_df.columns:
        print("\nUNIEKE LANDEN IN VERRIJKTE DATASET:")
        print(combined_df['country_name'].value_counts().head(10))
        
    print("\nUNIEKE ISO-3 CODES MET BEVOLKINGAANTAL:")
    if 'population' in combined_df.columns:
        print(combined_df[['country_name', 'iso3', 'population']].drop_duplicates().dropna().head(10))
    print("=" * 60)