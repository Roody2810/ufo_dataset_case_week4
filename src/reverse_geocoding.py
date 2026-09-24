import pandas as pd
import reverse_geocoder as rg
import pycountry


def add_iso3_and_names(df):
    """Zet landcodes om naar ISO-3 en landnamen met specifieke uitzonderingen voor veelvoorkomende landen."""
    unique_codes = df['country_clean'].dropna().unique()
    
    mapping = {}
    for code in unique_codes:
        clean = str(code).strip().upper()
        
        if clean in ['US', 'USA']:
            mapping[code] = {'iso3': 'USA', 'country_name': 'United States'}
        elif clean in ['CA', 'CAN']:
            mapping[code] = {'iso3': 'CAN', 'country_name': 'Canada'}
        elif clean in ['GB', 'GBR', 'UK']:
            mapping[code] = {'iso3': 'GBR', 'country_name': 'United Kingdom'}
        elif clean in ['AU', 'AUS']:
            mapping[code] = {'iso3': 'AUS', 'country_name': 'Australia'}
        else:
            country = pycountry.countries.get(alpha_2=clean) or pycountry.countries.get(alpha_3=clean)
            if country:
                mapping[code] = {'iso3': country.alpha_3, 'country_name': country.name}
            else:
                mapping[code] = {
                    'iso3': clean if len(clean) == 3 else None, 
                    'country_name': clean
                }

    iso3_map = {k: v['iso3'] for k, v in mapping.items()}
    name_map = {k: v['country_name'] for k, v in mapping.items()}

    df['iso3'] = df['country_clean'].map(iso3_map)
    df['country_name'] = df['country_clean'].map(name_map)
    
    return df


def fill_missing_countries(df):
    """Vult ontbrekende landen aan via reverse geocoding op basis van coördinaten."""
    df['latitude'] = pd.to_numeric(df['latitude'], errors='coerce')
    df['longitude'] = pd.to_numeric(df['longitude'], errors='coerce')
    
    valid_coords_mask = (
        df['latitude'].notna() & 
        df['longitude'].notna() & 
        (df['latitude'] != 0) & 
        (df['longitude'] != 0) &
        (df['latitude'].between(-90, 90)) &
        (df['longitude'].between(-180, 180))
    )
    
    missing_country_mask = df['country'].isna() & valid_coords_mask
    missing_df = df[missing_country_mask]
    
    df['country_clean'] = df['country']
    
    if not missing_df.empty:
        coords = list(zip(missing_df['latitude'], missing_df['longitude']))
        results = rg.search(coords, mode=1)
        detected_iso2 = [r['cc'].lower() for r in results]
        
        df.loc[missing_country_mask, 'country_clean'] = detected_iso2

        # Correctie voor specifieke bekende randgevallen van reverse_geocoder (zoals Andorra)
        is_andorra_code = df['country_clean'].str.lower() == 'ad'
        is_outside_andorra_geo = ~(
            df['latitude'].between(42.43, 42.66) & 
            df['longitude'].between(1.41, 1.78)
        )
        
        df.loc[missing_country_mask & is_andorra_code & is_outside_andorra_geo, 'country_clean'] = None

    df = add_iso3_and_names(df)
    
    df['country_name'] = df['country_name'].fillna('Onbekend / Internationale wateren')
    df['iso3'] = df['iso3'].fillna('UNK')
    
    return df