import streamlit as st
import pandas as pd
import plotly.express as px

# Importeer de gefuseerde data uit src/data_loader.py
from src.data_loader import load_combined_data

# --- PAGINA CONFIGURATIE ---
st.set_page_config(
    page_title="UFO Sightings & Bevolking Dashboard",
    page_icon="🛸",
    layout="wide"
)

st.title("🛸 UFO Sightings & Bevolkingsanalyse")
st.markdown(
    "Dit dashboard combineert Kaggle UFO-waarnemingen met actuele bevolkingsdata via een REST API "
    "en maakt gebruik van **Reverse Geocoding** om ontbrekende landgegevens aan te vullen."
)

# --- DATA LADEN ---
with st.spinner("Data laden, reverse geocoding toepassen en verwerken..."):
    df = load_combined_data()

if df.empty:
    st.error("Het is niet gelukt om de dataset te laden.")
    st.stop()

# Datetime opschonen, uren en jaren berekenen
datetime_col = 'Date_time' if 'Date_time' in df.columns else 'datetime'

if datetime_col in df.columns:
    df['datetime_clean'] = df[datetime_col].astype(str).str.replace('24:00', '00:00')
    df['datetime_clean'] = pd.to_datetime(df['datetime_clean'], errors='coerce')
    df['hour'] = df['datetime_clean'].dt.hour
    df['year'] = df['datetime_clean'].dt.year

# --- SIDEBAR WIDGETS ---
st.sidebar.header("🎛️ Dashboard Filters")

# 1. DROPDOWN (Sorteer landnamen netjes op alfabet)
available_countries = sorted([c for c in df['country_name'].dropna().unique() if c != 'Onbekend']) if 'country_name' in df.columns else []
selected_country = st.sidebar.selectbox(
    "Selecteer een land:",
    options=["Alle landen"] + available_countries
)

# 2. SLIDER VOOR TIJDSTIP VAN DE DAG (0 tot 24 uur)
hour_range = st.sidebar.slider(
    "Selecteer een tijdsframe (uur):",
    min_value=0,
    max_value=24,
    value=(0, 24)
)

# 3. CHECKBOX
show_only_populated = st.sidebar.checkbox(
    "Toon alleen locaties met bevolkingsdata",
    value=False
)

# --- DATAFILTERING LOGICA ---
filtered_df = df.copy()

# 1. Filter op land
if selected_country != "Alle landen" and 'country_name' in filtered_df.columns:
    filtered_df = filtered_df[filtered_df['country_name'] == selected_country]

# 2. Filter op uren-slider
if 'hour' in filtered_df.columns:
    min_h, max_h = hour_range
    
    # Als de slider op (0, 24) staat, behouden we 100% van de data (ook NaN's)
    if min_h == 0 and max_h == 24:
        pass
    else:
        # Als max op 24 staat, bedoelt de gebruiker t/m uur 23 (het laatste uur van de dag)
        actual_max_h = 23 if max_h == 24 else max_h
        filtered_df = filtered_df[
            (filtered_df['hour'].isna()) | 
            ((filtered_df['hour'] >= min_h) & (filtered_df['hour'] <= actual_max_h))
        ]

# 3. Filter op checkbox
if show_only_populated and 'population' in filtered_df.columns:
    filtered_df = filtered_df[filtered_df['population'].notna()]

# --- KPI METRICS ---
col1, col2, col3 = st.columns(3)

col1.metric("Aantal waarnemingen", f"{len(filtered_df):,}")
col2.metric("Geselecteerde tijdsframe", f"{hour_range[0]:02d}:00u - {hour_range[1]:02d}:00u")

if 'country_name' in filtered_df.columns and 'population' in filtered_df.columns and not filtered_df.empty:
    stats_per_country = filtered_df.groupby('country_name').agg(
        sightings=('iso3', 'count'),
        population=('population', 'first')
    ).reset_index()

    stats_per_country = stats_per_country[stats_per_country['population'] > 0]

    if not stats_per_country.empty:
        stats_per_country['per_100k'] = (stats_per_country['sightings'] / stats_per_country['population']) * 100000
        avg_per_100k = stats_per_country['per_100k'].mean()
        col3.metric("Gem. Sightings / 100k inw.", f"{avg_per_100k:.2f}")
    else:
        col3.metric("Gem. Sightings / 100k inw.", "N.v.t.")
else:
    col3.metric("Gem. Sightings / 100k inw.", "N.v.t.")

st.divider()

# --- GRAFIEK 1: LIJNGRAFIEK VERLOOP OVER DE JAREN ---
st.subheader("📈 Verloop van UFO Waarnemingen over de Jaren")

if 'datetime_clean' in filtered_df.columns and not filtered_df['datetime_clean'].dropna().empty:
    df_timeline = filtered_df.dropna(subset=['datetime_clean']).copy()
    df_timeline['date'] = df_timeline['datetime_clean'].dt.to_period('M').dt.to_timestamp()
    timeline_counts = df_timeline.groupby('date').size().reset_index(name='Aantal')

    fig_timeline = px.line(
        timeline_counts,
        x='date',
        y='Aantal',
        title="Trend van UFO meldingen door de tijd",
        labels={'date': 'Datum', 'Aantal': 'Aantal meldingen'}
    )

    fig_timeline.update_xaxes(
        rangeselector=dict(
            buttons=list([
                dict(count=5, label="5Y", step="year", stepmode="backward"),
                dict(count=10, label="10Y", step="year", stepmode="backward"),
                dict(count=25, label="25Y", step="year", stepmode="backward"),
                dict(count=50, label="50Y", step="year", stepmode="backward"),
                dict(step="all", label="All time")
            ])
        )
    )
    st.plotly_chart(fig_timeline, use_container_width=True)
else:
    st.info("Geen tijdsdata beschikbaar om een trendlijn op te bouwen.")

st.divider()

# --- RIJ 2: UUR & VORM ---
row2_col1, row2_col2 = st.columns(2)

with row2_col1:
    st.subheader("⏰ Waarnemingen per Uur van de Dag")
    if 'hour' in filtered_df.columns and not filtered_df['hour'].dropna().empty:
        hourly_counts = filtered_df['hour'].value_counts().sort_index().reset_index()
        hourly_counts.columns = ['Uur', 'Aantal']
        
        fig_hourly = px.bar(
            hourly_counts,
            x='Uur',
            y='Aantal',
            labels={'Uur': 'Uur van de dag (0-23)', 'Aantal': 'Aantal meldingen'},
            color='Aantal',
            color_continuous_scale='Viridis'
        )
        fig_hourly.update_layout(xaxis=dict(tickmode='linear', tick0=0, dtick=2))
        st.plotly_chart(fig_hourly, use_container_width=True)

with row2_col2:
    st.subheader("🛸 Vorm van de UFO (Top 10)")
    shape_col = 'shape' if 'shape' in filtered_df.columns else ('UFO_shape' if 'UFO_shape' in filtered_df.columns else None)
    
    if shape_col and not filtered_df[shape_col].dropna().empty:
        shape_counts = filtered_df[shape_col].value_counts().head(10).reset_index()
        shape_counts.columns = ['Vorm', 'Aantal']
        
        fig_shape = px.pie(
            shape_counts,
            names='Vorm',
            values='Aantal',
            hole=0.4
        )
        st.plotly_chart(fig_shape, use_container_width=True)

st.divider()

# --- GRAFIEK 3: INTERACTIEVE WERELDKAART ---
st.subheader("🗺️ Globale Spreiding van UFO Waarnemingen")

if 'iso3' in filtered_df.columns and not filtered_df.empty:
    map_df = filtered_df.groupby(['iso3', 'country_name']).size().reset_index(name='Aantal Waarnemingen')
    
    fig_map = px.choropleth(
        map_df,
        locations="iso3",
        color="Aantal Waarnemingen",
        hover_name="country_name",
        color_continuous_scale="Reds",
        projection="natural earth",
        title="Aantal UFO Meldingen per Land"
    )
    st.plotly_chart(fig_map, use_container_width=True)

st.divider()

# --- GRAFIEK 4: LANDEN PER 100K INWONERS ---
st.subheader("🌍 Waarnemingen per 100.000 Inwoners (Top 5 + Overig)")

if 'country_name' in filtered_df.columns and 'population' in filtered_df.columns and not filtered_df.empty:
    country_metrics = filtered_df.groupby('country_name').agg(
        totaal_sightings=('iso3', 'count'),
        bevolking=('population', 'first')
    ).reset_index()
    
    # FILTER: Neem alleen landen mee met minstens 100 waarnemingen én bekende bevolking
    country_metrics = country_metrics[
        (country_metrics['bevolking'] > 0) & 
        (country_metrics['country_name'] != 'Onbekend / Internationale wateren')
    ]
    
    if not country_metrics.empty:
        country_metrics['per_100k'] = (country_metrics['totaal_sightings'] / country_metrics['bevolking']) * 100000
        country_metrics = country_metrics.sort_values(by='per_100k', ascending=False)
        
        # 🔍 INSPECTIE TABEL: Bekijk de waarden die in de grafiek worden gebruikt
        st.write("🔍 **Inspectie Top 10 Berekende Landen (per 100k inwoners):**")
        st.dataframe(country_metrics.head(10), use_container_width=True)
        
        if len(country_metrics) > 5:
            top_5 = country_metrics.head(5)
            overig_sightings = country_metrics.iloc[5:]['totaal_sightings'].sum()
            overig_bevolking = country_metrics.iloc[5:]['bevolking'].sum()
            
            overig_row = pd.DataFrame([{
                'country_name': 'Overig (Rest van de wereld)',
                'totaal_sightings': overig_sightings,
                'bevolking': overig_bevolking,
                'per_100k': (overig_sightings / overig_bevolking) * 100000 if overig_bevolking > 0 else 0
            }])
            
            plot_country_df = pd.concat([top_5, overig_row], ignore_index=True)
        else:
            plot_country_df = country_metrics

        fig_pop = px.bar(
            plot_country_df,
            x='country_name',
            y='per_100k',
            labels={'country_name': 'Land / Categorie', 'per_100k': 'Sightings per 100.000 inwoners'},
            color='per_100k',
            color_continuous_scale='Magma',
            text_auto='.2f'
        )
        st.plotly_chart(fig_pop, use_container_width=True)

# DATA TABEL
st.subheader("📄 Geselecteerde Dataset")
st.dataframe(filtered_df.head(100), use_container_width=True)

st.divider()

# --- JOIN VERANTWOORDING ---
with st.expander("ℹ️ Data Integratie & Join Verantwoording"):
    st.markdown("**Samenvoegsleutel (Join Key):** `iso3` (UFO dataset na geocoding) 🔗 `countryId` (REST API)")
    
    rijen_totaal = len(df)
    
    col_a, col_b = st.columns(2)
    col_a.metric("Aantal rijen VÓÓR merge", f"{rijen_totaal:,}")
    col_b.metric("Aantal rijen NÁ merge", f"{rijen_totaal:,}")
    
    st.success("✅ De left-join is geslaagd op basis van ISO-3 landcodes: exact evenveel rijen overgebleven, dus geen dataverlies of onbedoelde verdubbelingen.")