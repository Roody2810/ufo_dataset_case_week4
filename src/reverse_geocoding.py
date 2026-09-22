import pandas as pd
import reverse_geocoder as rg
import pycountry

def add_iso3_and_names(df):
    """
    Zet landcodes om naar ISO-3 en landnamen via vectormapping.
    Bevat expliciete fixes voor US, CA, GB en AU om foute matches te voorkomen.
    """
    unique_codes = df['country_clean'].dropna().unique()
    
    mapping = {}
    for code in unique_codes:
        clean = str(code).strip().upper()
        
        # Expliciete uitzonderingen en hardcoded fixes voor veelvoorkomende codes
        if clean in ['US', 'USA']:
            mapping[code] = {'iso3': 'USA', 'country_name': 'United States'}
        elif clean in ['CA', 'CAN']:
            mapping[code] = {'iso3': 'CAN', 'country_name': 'Canada'}
        elif clean in ['GB', 'GBR', 'UK']:
            mapping[code] = {'iso3': 'GBR', 'country_name': 'United Kingdom'}
        elif clean in ['AU', 'AUS']:
            mapping[code] = {'iso3': 'AUS', 'country_name': 'Australia'}
        elif clean in ['AD', 'AND']:
            mapping[code] = {'iso3': 'AND', 'country_name': 'Andorra'}
        else:
            country = pycountry.countries.get(alpha_2=clean) or pycountry.countries.get(alpha_3=clean)
            if country:
                mapping[code] = {'iso3': country.alpha_3, 'country_name': country.name}
            else:
                mapping[code] = {
                    'iso3': clean if len(clean) == 3 else None, 
                    'country_name': clean
                }

    # Opzoek-dictionaries voor supersnelle Pandas mapping
    iso3_map = {k: v['iso3'] for k, v in mapping.items()}
    name_map = {k: v['country_name'] for k, v in mapping.items()}

    df['iso3'] = df['country_clean'].map(iso3_map)
    df['country_name'] = df['country_clean'].map(name_map)
    
    return df


def fill_missing_countries(df):
    """
    Vult ENKEL lege landen aan via reverse geocoding en mapt naar ISO-3/landnamen.
    Sluit valse Andorra-matches en ongeldige coördinaten uit.
    """
    df['latitude'] = pd.to_numeric(df['latitude'], errors='coerce')
    df['longitude'] = pd.to_numeric(df['longitude'], errors='coerce')
    
    # 1. Geldige coördinaten check (sluit 0,0 en ongeldige waarden uit)
    valid_coords_mask = (
        df['latitude'].notna() & 
        df['longitude'].notna() & 
        (df['latitude'] != 0) & 
        (df['longitude'] != 0) &
        (df['latitude'].between(-90, 90)) &
        (df['longitude'].between(-180, 180))
    )
    
    # 2. Selecteer UITSLUITEND rijen waar 'country' ontbreekt én coördinaten geldig zijn
    missing_country_mask = df['country'].isna() & valid_coords_mask
    missing_df = df[missing_country_mask]
    
    # Initialiseer 'country_clean'
    df['country_clean'] = df['country']
    
    # 3. Reverse geocoding alleen uitvoeren op ontbrekende rijen met geldige coördinaten
    if not missing_df.empty:
        coords = list(zip(missing_df['latitude'], missing_df['longitude']))
        results = rg.search(coords, mode=1)
        detected_iso2 = [r['cc'].lower() for r in results]
        
        # Wijs gedetecteerde landcodes toe aan de lege plekken
        df.loc[missing_country_mask, 'country_clean'] = detected_iso2

        # 🎯 EXTRA FIX: Filter valse Andorra matches uit reverse_geocoder.
        # Echte Andorra coördinaten liggen uitsluitend tussen Lat: [42.43, 42.66] en Lon: [1.41, 1.78]
        is_andorra_code = df['country_clean'].str.lower() == 'ad'
        is_outside_andorra_geo = ~(
            df['latitude'].between(42.43, 42.66) & 
            df['longitude'].between(1.41, 1.78)
        )
        
        # Zet valse Andorra matches terug op None (wordt bij stap 5 gefillna'd als UNK / Onbekend)
        df.loc[missing_country_mask & is_andorra_code & is_outside_andorra_geo, 'country_clean'] = None

    # 4. Voeg ISO-3 codes en landnamen toe
    df = add_iso3_and_names(df)
    
    # 5. Opvullen van de resterende lege/onbekende/nul-coördinaat rijen
    df['country_name'] = df['country_name'].fillna('Onbekend / Internationale wateren')
    df['iso3'] = df['iso3'].fillna('UNK')
    
    return df


# if __name__ == "__main__":
#     # Test-script om het bestand los uit te voeren
#     print("📂 Testdataset inladen...")
#     df_test = pd.read_csv("data/ufo_sighting_data.csv", low_memory=False)
    
#     print("🚀 Geocoding pijplijn uitvoeren...")
#     df_result = fill_missing_countries(df_test)


#     usa_sightings = df_result[df_result['country_name'] == 'United States']['iso3'].count()
#     print(f"🇺🇸 Aantal waarnemingen in de Verenigde Staten: {usa_sightings:,}")
    
#     print("\n✅ RESULTAAT CHECK:")
#     print(f"Totaal aantal rijen: {len(df_result):,}")
#     print(f"Aantal UNK (Onbekend / Geen land): {(df_result['iso3'] == 'UNK').sum():,}")
#     print("\nTop 5 landen in dataset:")
#     print(df_result['country_name'].value_counts().head(10))

#     df_result.to_csv("./output.csv", index=False)