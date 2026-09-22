import os
import requests
import pandas as pd
import streamlit as st



import kaggle


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
    return loader.load_csv("ufo_sighting_data.csv")


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
@st.cache_data
def load_combined_data():
    ufo_df = load_ufo_dataset()
    pop_df = load_population_data()
    
    # Vertaling van de landcodes naar ISO-3 (voor API) én volledige landnaam
    country_map = {
        'us': {'iso3': 'USA', 'name': 'United States'},
        'gb': {'iso3': 'GBR', 'name': 'United Kingdom'},
        'ca': {'iso3': 'CAN', 'name': 'Canada'},
        'au': {'iso3': 'AUS', 'name': 'Australia'},
        'de': {'iso3': 'DEU', 'name': 'Germany'}
    }
    
    if 'country' in ufo_df.columns:
        # 1. Maak tijdelijke ISO-3 koppelkolom voor de API
        ufo_df['country_iso3'] = ufo_df['country'].str.lower().map(
            lambda x: country_map.get(x, {}).get('iso3')
        )
        
        # 2. Voeg de schone landnaam toe
        ufo_df['country_name'] = ufo_df['country'].str.lower().map(
            lambda x: country_map.get(x, {}).get('name')
        )
        
        # 3. Koppel de populatie uit de API
        if not pop_df.empty:
            combined_df = pd.merge(
                ufo_df,
                pop_df[['countryId', 'population']],
                left_on='country_iso3',
                right_on='countryId',
                how='left'
            )
            # Opruimen van tijdelijke koppelkolommen
            combined_df = combined_df.drop(columns=['country_iso3', 'countryId'], errors='ignore')
            return combined_df
            
    return ufo_df

if __name__ == "__main__":
    ufo_df = load_ufo_dataset()
    pop_df = load_population_data()

    print("=" * 60)
    print("UNIEKE LANDCODES IN UFO DATASET:")
    if 'country' in ufo_df.columns:
        print(ufo_df['country'].dropna().unique().tolist())
    else:
        print("Geen kolom 'country' gevonden in ufo_df")

    print("\n" + "=" * 60)
    print("UNIEKE LANDCODES / NAMEN IN API POPULATIEDATA:")
    if not pop_df.empty:
        # Hier printen we de relevante kolommen uit de API response
        cols = [col for col in ['countryId', 'country_name', 'name'] if col in pop_df.columns]
        print(pop_df[cols].drop_duplicates().to_string(index=False))
    else:
        print("API data is leeg")
    print("=" * 60)