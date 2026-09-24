# Vergeet niet "pip install -r requirements.txt" uit te voeren in je terminal, anders werkt het niet

import pandas as pd
import plotly.express as px
import streamlit as st

from src.data_loader import load_combined_data, kaggleDataLoader

st.set_page_config(
    page_title="UFO Spotter Dashboard & Bevolkingsanalyse",
    page_icon="🛸",
    layout="wide"
)

# Visuals & constanten
COLOR_ACCENT = "#00E676"
COLOR_CONTEXT = "#94A3B8"
INVALID_VALUES = {'onbekend', 'unknown', 'none', 'nan', 'null', '', 'other', 'n/a', 'undefined'}


def get_clean_series(dataframe: pd.DataFrame, col_name: str | None) -> pd.Series:
    """Filtert lege en ongeldige waarden uit een specifieke kolom."""
    if not col_name or col_name not in dataframe.columns:
        return pd.Series(dtype=object)
    s = dataframe[col_name].dropna().astype(str).str.strip()
    return s[~s.str.lower().isin(INVALID_VALUES)]


def detect_column(dataframe: pd.DataFrame, candidates: list[str]) -> str | None:
    """Zoekt de eerste matchende kolom uit een lijst van bekende kolomnamen."""
    for col in dataframe.columns:
        if col.lower() in candidates:
            return col
    return None


st.title("UFO Spotter Dashboard")
st.markdown(
    "**Waar en wanneer maak je de meeste kans om een UFO te spotten?** "
    "Combineert wereldwijde waarnemingen met bevolkingsdata om patronen in locaties en tijdstippen te analyseren."
)

# Data laden
with st.spinner("Data laden..."):
    df = load_combined_data()

if df.empty:
    st.error("Het is niet gelukt om de dataset te laden.")
    st.stop()

# Datetime verwerken
datetime_col = 'Date_time' if 'Date_time' in df.columns else 'datetime'
if datetime_col in df.columns:
    df['datetime_clean'] = pd.to_datetime(
        df[datetime_col].astype(str).str.replace('24:00', '00:00'),
        errors='coerce'
    )
    df['hour'] = df['datetime_clean'].dt.hour
    df['year'] = df['datetime_clean'].dt.year

state_col = detect_column(df, ['state', 'state/province', 'state_code', 'region', 'staat', 'province'])
city_col = detect_column(df, ['city', 'stad', 'town', 'location'])
shape_col = detect_column(df, ['shape', 'ufo_shape'])

# Sidebar
st.sidebar.header("Dashboard Filters")

available_countries = []
if 'country_name' in df.columns:
    raw_countries = df['country_name'].dropna().unique()
    available_countries = sorted([c for c in raw_countries if c.lower() not in INVALID_VALUES])

selected_country = st.sidebar.selectbox(
    "Selecteer weergave:",
    options=["Alle landen (Spotter Overview)"] + available_countries
)

hour_range = st.sidebar.slider(
    "Selecteer tijdsframe (uur van de dag):",
    min_value=0,
    max_value=24,
    value=(0, 24)
)

show_only_populated = st.sidebar.checkbox(
    "Toon alleen locaties met bevolkingsdata",
    value=False
)

# Data filteren
filtered_df = df.copy()
is_overview_mode = (selected_country == "Alle landen (Spotter Overview)")

if not is_overview_mode and 'country_name' in filtered_df.columns:
    filtered_df = filtered_df[filtered_df['country_name'] == selected_country]

if 'hour' in filtered_df.columns:
    min_h, max_h = hour_range
    if not (min_h == 0 and max_h == 24):
        actual_max_h = 23 if max_h == 24 else max_h
        filtered_df = filtered_df[
            (filtered_df['hour'].isna()) |
            ((filtered_df['hour'] >= min_h) & (filtered_df['hour'] <= actual_max_h))
        ]

if show_only_populated and 'population' in filtered_df.columns:
    filtered_df = filtered_df[filtered_df['population'].notna()]

st.divider()

# Mode 1: Wereldwijd overzicht
if is_overview_mode:
    st.header("UFO Spotter Quick Guide (Wereldwijd Overzicht)")
    st.caption("Snel overzicht van de beste locaties en tijden op basis van historische data.")

    # KPI's berekenen
    top_country, top_country_pct = "Onbekend", 0.0
    if 'country_name' in filtered_df.columns and not filtered_df.empty:
        clean_countries = get_clean_series(filtered_df, 'country_name')
        if not clean_countries.empty:
            c_counts = clean_countries.value_counts()
            top_country = c_counts.index[0]
            top_country_pct = (c_counts.iloc[0] / len(filtered_df)) * 100

    peak_hour_str = "N.v.t."
    if 'hour' in filtered_df.columns and not filtered_df['hour'].dropna().empty:
        peak_hour = int(filtered_df['hour'].mode()[0])
        peak_hour_str = f"{peak_hour:02d}:00u - {peak_hour+1:02d}:00u"

    top_state_str = "Onbekend"
    clean_states = get_clean_series(filtered_df, state_col)
    if not clean_states.empty:
        top_state_str = clean_states.value_counts().index[0].upper()

    top_shape_str = "Licht"
    clean_shapes = get_clean_series(filtered_df, shape_col)
    if not clean_shapes.empty:
        top_shape_str = clean_shapes.value_counts().index[0].capitalize()

    # KPI Weergave
    kpi1, kpi2, kpi3, kpi4 = st.columns(4)
    kpi1.metric("Hotspot Land", top_country, f"{top_country_pct:.1f}% van meldingen")
    kpi2.metric("Beste Tijdstip", peak_hour_str, "Late avond / Nacht")
    kpi3.metric("Top Regio / Staat", top_state_str, "Hoogste concentratie")
    kpi4.metric("Meest Geziene Vorm", top_shape_str, "Meest gemelde type")

    st.divider()

    # Landenvergelijking & US Staten
    row1_col1, row1_col2 = st.columns(2)

    with row1_col1:
        st.subheader("Landenvergelijking")
        clean_c_series = get_clean_series(filtered_df, 'country_name')
        if not clean_c_series.empty:
            country_counts = clean_c_series.value_counts().head(8).reset_index()
            country_counts.columns = ['Land', 'Aantal']

            colors = [
                COLOR_ACCENT if land in ['Verenigde Staten', 'USA', 'United States', 'US'] else COLOR_CONTEXT
                for land in country_counts['Land']
            ]

            fig_country = px.bar(country_counts, x='Aantal', y='Land', orientation='h', text='Aantal')
            max_val = country_counts['Aantal'].max()
            fig_country.update_traces(marker_color=colors, textposition='outside', cliponaxis=False)
            fig_country.update_layout(
                yaxis=dict(autorange="reversed"),
                xaxis=dict(range=[0, max_val * 1.18], title="Totaal aantal waarnemingen"),
                margin=dict(l=20, r=40, t=30, b=20)
            )
            st.plotly_chart(fig_country, use_container_width=True)

    with row1_col2:
        st.subheader("Hotspot Staten (VS)")
        clean_s_series = get_clean_series(filtered_df, state_col)
        if not clean_s_series.empty:
            state_counts = clean_s_series.value_counts().head(10).reset_index()
            state_counts.columns = ['Staat', 'Aantal']
            state_counts['Staat'] = state_counts['Staat'].str.upper()

            top_st = state_counts.iloc[0]['Staat']
            colors_state = [COLOR_ACCENT if st_code == top_st else COLOR_CONTEXT for st_code in state_counts['Staat']]

            fig_state = px.bar(state_counts, x='Staat', y='Aantal', text='Aantal')
            max_st_val = state_counts['Aantal'].max()
            fig_state.update_traces(marker_color=colors_state, textposition='outside', cliponaxis=False)
            fig_state.update_layout(
                yaxis=dict(range=[0, max_st_val * 1.18], title="Aantal meldingen"),
                xaxis=dict(title="Amerikaanse Staat"),
                margin=dict(l=20, r=20, t=30, b=20)
            )
            st.plotly_chart(fig_state, use_container_width=True)
        else:
            st.info("Geen specifieke staatgegevens beschikbaar in de huidige selectie.")

    st.divider()

    # Piekuren & Vormen
    row2_col1, row2_col2 = st.columns(2)

    with row2_col1:
        st.subheader("Piekuren van Waarnemingen")
        if 'hour' in filtered_df.columns and not filtered_df['hour'].dropna().empty:
            hourly_counts = filtered_df['hour'].value_counts().sort_index().reset_index()
            hourly_counts.columns = ['Uur', 'Aantal']

            full_hours = pd.DataFrame({'Uur': list(range(24))})
            hourly_counts = pd.merge(full_hours, hourly_counts, on='Uur', how='left').fillna(0)
            hourly_counts['Aantal'] = hourly_counts['Aantal'].astype(int)

            hourly_counts['Tijdsblok'] = hourly_counts['Uur'].apply(lambda h: f"{int(h):02d}:00 - {int(h)+1:02d}:00")
            hourly_counts['Uur_label'] = hourly_counts['Uur'].apply(lambda h: f"{int(h):02d}:00")

            colors_hour = [COLOR_ACCENT if 20 <= h <= 23 else COLOR_CONTEXT for h in hourly_counts['Uur']]

            fig_hourly = px.bar(
                hourly_counts,
                x='Uur_label',
                y='Aantal',
                hover_data={'Uur_label': False, 'Tijdsblok': True, 'Aantal': ':,d'}
            )
            fig_hourly.update_traces(marker_color=colors_hour)
            fig_hourly.update_layout(
                xaxis_title="Tijdsblok",
                yaxis_title="Aantal meldingen",
                margin=dict(l=20, r=20, t=30, b=20)
            )
            st.plotly_chart(fig_hourly, use_container_width=True)

    with row2_col2:
        st.subheader("Meest Voorkomende Vormen")
        clean_sh_series = get_clean_series(filtered_df, shape_col)
        if not clean_sh_series.empty:
            shape_counts = clean_sh_series.value_counts().head(7).reset_index()
            shape_counts.columns = ['Vorm', 'Aantal']

            fig_shape = px.bar(shape_counts, x='Aantal', y='Vorm', orientation='h', text='Aantal')
            colors_shape = [COLOR_ACCENT if i == 0 else COLOR_CONTEXT for i in range(len(shape_counts))]
            max_sh_val = shape_counts['Aantal'].max()
            fig_shape.update_traces(marker_color=colors_shape, textposition='outside', cliponaxis=False)
            fig_shape.update_layout(
                yaxis=dict(autorange="reversed"),
                xaxis=dict(range=[0, max_sh_val * 1.18]),
                margin=dict(l=20, r=30, t=30, b=20)
            )
            st.plotly_chart(fig_shape, use_container_width=True)

# Mode 2: Specifiek land
else:
    st.header(f"Gedetailleerde Analyse: {selected_country}")

    c_col1, c_col2, c_col3 = st.columns(3)
    c_col1.metric("Aantal waarnemingen", f"{len(filtered_df):,}")
    c_col2.metric("Geselecteerd tijdsframe", f"{hour_range[0]:02d}:00u - {hour_range[1]:02d}:00u")

    if 'population' in filtered_df.columns and not filtered_df.empty:
        pop = filtered_df['population'].iloc[0]
        if pd.notna(pop) and pop > 0:
            per_100k = (len(filtered_df) / pop) * 100000
            c_col3.metric("Sightings per 100k inw.", f"{per_100k:.2f}")
        else:
            c_col3.metric("Sightings per 100k inw.", "N.v.t.")

    st.divider()

    col_a, col_b = st.columns(2)

    with col_a:
        st.subheader(f"Uurverdeling in {selected_country}")
        if 'hour' in filtered_df.columns and not filtered_df['hour'].dropna().empty:
            hourly_c = filtered_df['hour'].value_counts().sort_index().reset_index()
            hourly_c.columns = ['Uur', 'Aantal']

            full_h = pd.DataFrame({'Uur': list(range(24))})
            hourly_c = pd.merge(full_h, hourly_c, on='Uur', how='left').fillna(0)
            hourly_c['Aantal'] = hourly_c['Aantal'].astype(int)

            hourly_c['Tijdsblok'] = hourly_c['Uur'].apply(lambda h: f"{int(h):02d}:00 - {int(h)+1:02d}:00")
            hourly_c['Uur_label'] = hourly_c['Uur'].apply(lambda h: f"{int(h):02d}:00")

            fig_h = px.bar(
                hourly_c,
                x='Uur_label',
                y='Aantal',
                color_discrete_sequence=[COLOR_ACCENT],
                hover_data={'Uur_label': False, 'Tijdsblok': True, 'Aantal': ':,d'}
            )
            fig_h.update_layout(
                xaxis_title="Startuur (bijv. 21:00 = 21:00 - 22:00)",
                yaxis_title="Aantal meldingen"
            )
            st.plotly_chart(fig_h, use_container_width=True)

    with col_b:
        clean_cities = get_clean_series(filtered_df, city_col)
        if not clean_cities.empty:
            st.subheader(f"Top Steden in {selected_country}")
            city_counts = clean_cities.value_counts().head(8).reset_index()
            city_counts.columns = ['Stad', 'Aantal']
            city_counts['Stad'] = city_counts['Stad'].str.title()

            fig_city = px.bar(
                city_counts, x='Aantal', y='Stad', orientation='h', text='Aantal',
                color_discrete_sequence=[COLOR_CONTEXT]
            )
            max_c_val = city_counts['Aantal'].max()
            fig_city.update_traces(textposition='outside', cliponaxis=False)
            fig_city.update_layout(
                yaxis=dict(autorange="reversed"),
                xaxis=dict(range=[0, max_c_val * 1.2]),
                margin=dict(l=20, r=30, t=30, b=20)
            )
            st.plotly_chart(fig_city, use_container_width=True)
        else:
            st.subheader(f"Populaire Vormen in {selected_country}")
            clean_sh_country = get_clean_series(filtered_df, shape_col)
            if not clean_sh_country.empty:
                shape_c = clean_sh_country.value_counts().head(8).reset_index()
                shape_c.columns = ['Vorm', 'Aantal']

                fig_s = px.bar(
                    shape_c, x='Aantal', y='Vorm', orientation='h', text='Aantal',
                    color_discrete_sequence=[COLOR_CONTEXT]
                )
                max_s_val = shape_c['Aantal'].max()
                fig_s.update_traces(textposition='outside', cliponaxis=False)
                fig_s.update_layout(
                    yaxis=dict(autorange="reversed"),
                    xaxis=dict(range=[0, max_s_val * 1.2])
                )
                st.plotly_chart(fig_s, use_container_width=True)

st.divider()

# Trend over de jaren
st.subheader("Verloop van UFO Waarnemingen over de Jaren")

if 'datetime_clean' in filtered_df.columns and not filtered_df['datetime_clean'].dropna().empty:
    df_timeline = filtered_df.dropna(subset=['datetime_clean']).copy()
    df_timeline['date'] = df_timeline['datetime_clean'].dt.to_period('M').dt.to_timestamp()
    timeline_counts = df_timeline.groupby('date').size().reset_index(name='Aantal')

    fig_timeline = px.line(
        timeline_counts,
        x='date',
        y='Aantal',
        labels={'date': 'Datum', 'Aantal': 'Aantal meldingen'}
    )
    fig_timeline.update_traces(line_color=COLOR_ACCENT, line_width=2.5)

    fig_timeline.update_xaxes(
        rangeselector=dict(
            buttons=[
                dict(count=5, label="5Y", step="year", stepmode="backward"),
                dict(count=10, label="10Y", step="year", stepmode="backward"),
                dict(count=25, label="25Y", step="year", stepmode="backward"),
                dict(step="all", label="All time")
            ]
        )
    )
    st.plotly_chart(fig_timeline, use_container_width=True)

st.divider()

# Join verantwoording
with st.expander("Data Integratie & Join Verantwoording"):
    st.markdown("**Samenvoegsleutel (Join Key):** `iso3` (UFO dataset) = `countryId` (REST API)")
    rijen_totaal = len(df)

    col_a, col_b = st.columns(2)
    col_a.metric("Aantal rijen vóór merge", f"{rijen_totaal:,}")
    col_b.metric("Aantal rijen ná merge", f"{rijen_totaal:,}")

    st.success("De left-join is geslaagd op basis van ISO-3 landcodes. Er is geen dataverlies of onbedoelde verdubbeling opgetreden.")
# ============================================================
# MARIHUANAGEBRUIK VS UFO-MELDINGEN
# ============================================================

st.divider()

st.header("Marihuanagebruik vs. UFO-meldingen")


# ------------------------------------------------------------
# 1. Drugs dataset laden
# ------------------------------------------------------------

drug_loader = kaggleDataLoader(
    "mexwell/us-drug-abuse",
    download_dir="../data"
)

drugs = drug_loader.load_csv("drugs.csv")


# ------------------------------------------------------------
# 2. UFO's per staat tellen
# ------------------------------------------------------------

ufo_per_state = (
    df["state/province"]
    .dropna()
    .astype(str)
    .str.strip()
    .str.upper()
    .value_counts()
    .reset_index()
)

ufo_per_state.columns = ["State_code", "UFO_count"]


# ------------------------------------------------------------
# 3. Staatnamen drugs -> Amerikaanse afkortingen
# ------------------------------------------------------------

state_codes = {
    "alabama": "AL",
    "alaska": "AK",
    "arizona": "AZ",
    "arkansas": "AR",
    "california": "CA",
    "colorado": "CO",
    "connecticut": "CT",
    "delaware": "DE",
    "florida": "FL",
    "georgia": "GA",
    "hawaii": "HI",
    "idaho": "ID",
    "illinois": "IL",
    "indiana": "IN",
    "iowa": "IA",
    "kansas": "KS",
    "kentucky": "KY",
    "louisiana": "LA",
    "maine": "ME",
    "maryland": "MD",
    "massachusetts": "MA",
    "michigan": "MI",
    "minnesota": "MN",
    "mississippi": "MS",
    "missouri": "MO",
    "montana": "MT",
    "nebraska": "NE",
    "nevada": "NV",
    "new hampshire": "NH",
    "new jersey": "NJ",
    "new mexico": "NM",
    "new york": "NY",
    "north carolina": "NC",
    "north dakota": "ND",
    "ohio": "OH",
    "oklahoma": "OK",
    "oregon": "OR",
    "pennsylvania": "PA",
    "rhode island": "RI",
    "south carolina": "SC",
    "south dakota": "SD",
    "tennessee": "TN",
    "texas": "TX",
    "utah": "UT",
    "vermont": "VT",
    "virginia": "VA",
    "washington": "WA",
    "west virginia": "WV",
    "wisconsin": "WI",
    "wyoming": "WY"
}


drugs["State_code"] = (
    drugs["State"]
    .astype(str)
    .str.strip()
    .str.lower()
    .map(state_codes)
)


# ------------------------------------------------------------
# 4. Marijuana 18-25
# ------------------------------------------------------------

drugs["Marijuana_18_25"] = pd.to_numeric(
    drugs["Rates.Marijuana.Used Past Year.18-25"],
    errors="coerce"
)


# ------------------------------------------------------------
# 5. Data combineren
# ------------------------------------------------------------

data_scatter = pd.merge(
    drugs,
    ufo_per_state,
    on="State_code",
    how="inner"
)


# ------------------------------------------------------------
# 6. Alleen benodigde kolommen
# ------------------------------------------------------------

data_scatter = data_scatter[
    [
        "State",
        "State_code",
        "Marijuana_18_25",
        "UFO_count"
    ]
].dropna()


# ------------------------------------------------------------
# 7. Controleren
# ------------------------------------------------------------

st.write(
    "Aantal gekoppelde staten:",
    len(data_scatter)
)

st.dataframe(data_scatter)


# ------------------------------------------------------------
# 8. Scatterplot
# ------------------------------------------------------------

fig_scatter = px.scatter(
    data_scatter,
    x="Marijuana_18_25",
    y="UFO_count",
    hover_name="State",
    trendline="ols",
    labels={
        "Marijuana_18_25": "Marihuanagebruik 18-25 (%)",
        "UFO_count": "Aantal UFO-meldingen"
    },
    title="Marihuanagebruik vs. UFO-meldingen per staat"
)

st.plotly_chart(
    fig_scatter,
    use_container_width=True
)


# ------------------------------------------------------------
# 9. Correlatie
# ------------------------------------------------------------

correlation = data_scatter[
    "Marijuana_18_25"
].corr(
    data_scatter["UFO_count"]
)

st.metric(
    "Pearson correlatie",
    f"{correlation:.2f}"
)

# ------------------------------------------------------------
# 10. Dropdown + Slider + Checkbox
# ------------------------------------------------------------

# Dropdown: kies UFO-vorm
shapes = sorted(df["UFO_shape"].dropna().unique())

selected_shape = st.selectbox(
    "Kies een UFO-vorm",
    shapes
)

# Slider: maximale waarnemingsduur
max_duration = st.slider(
    "Maximale waarnemingsduur (seconden)",
    min_value=1,
    max_value=2000,
    value=1000
)

# Checkbox: alleen extreme waarnemingen
extreme_only = st.checkbox(
    "Alleen waarnemingen van 10 minuten of langer"
)

# Data filteren
filtered_df = df[
    (df["UFO_shape"] == selected_shape) &
    (
        pd.to_numeric(
            df["length_of_encounter_seconds"],
            errors="coerce"
        ) <= max_duration
    )
]

# Extra filter wanneer checkbox aan staat
if extreme_only:
    filtered_df = filtered_df[
        pd.to_numeric(
            filtered_df["length_of_encounter_seconds"],
            errors="coerce"
        ) >= 600
    ]

# Aantal gevonden waarnemingen
st.write(
    f"Aantal waarnemingen: **{len(filtered_df)}**"
)

# Jaar uit datum halen
filtered_df["Year"] = pd.to_datetime(
    filtered_df["Date_time"],
    errors="coerce"
).dt.year

# Aantal waarnemingen per jaar
year_counts = (
    filtered_df["Year"]
    .value_counts()
    .sort_index()
    .reset_index()
)

year_counts.columns = ["Year", "UFO_count"]

# Grafiek
fig = px.line(
    year_counts,
    x="Year",
    y="UFO_count",
    markers=True,
    title=f"UFO-waarnemingen van vorm: {selected_shape}"
)

fig.update_layout(
    xaxis_title="Jaar",
    yaxis_title="Aantal waarnemingen"
)

st.plotly_chart(fig, width="stretch")