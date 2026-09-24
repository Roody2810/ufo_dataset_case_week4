import pandas as pd
import plotly.express as px
import streamlit as st

from src.data_cleaner import DataCleaner
from src.data_loader import load_combined_data, KaggleDataLoader
from src.constants import (
    COLOR_ACCENT,
    COLOR_CONTEXT,
    INVALID_VALUES,
    USA_NAMES,
    STATE_MAP,
    US_STATES
)

# Pagina configuratie
st.set_page_config(
    page_title="UFO Spotter Dashboard & Bevolkingsanalyse",
    page_icon="🛸",
    layout="wide"
)


def get_clean_series(dataframe: pd.DataFrame, col_name: str | None) -> pd.Series:
    """Filtert lege en ongeldige waarden uit een specifieke kolom met behulp van DataCleaner."""
    if not col_name or col_name not in dataframe.columns:
        return pd.Series(dtype=object)

    cleaner = DataCleaner(dataframe[[col_name]])
    cleaner.standardize_empty_values()
    cleaner.clean_text_columns(strip=True, replace_html=True)

    s = cleaner.get_df()[col_name].dropna()
    return s[~s.astype(str).str.lower().isin(INVALID_VALUES)]


def detect_column(dataframe: pd.DataFrame, candidates: list[str]) -> str | None:
    """Zoekt de eerste matchende kolom uit een lijst van bekende kolomnamen."""
    for col in dataframe.columns:
        if col.lower() in candidates:
            return col
    return None


def plot_per_100k(dataframe: pd.DataFrame, group_col: str = 'country_name', top_n: int = 8):
    """Genereert een staafdiagram voor waarnemingen per 100.000 inwoners."""
    if group_col not in dataframe.columns or 'population' not in dataframe.columns:
        st.info("Onvoldoende bevolkingsdata beschikbaar voor berekening per 100k inwoners.")
        return

    df_valid = dataframe.dropna(subset=[group_col, 'population']).copy()
    if df_valid.empty:
        st.info("Geen bevolkingsdata beschikbaar voor de huidige selectie.")
        return

    stats = df_valid.groupby(group_col).agg(
        Aantal=(group_col, 'count'),
        Bevolking=('population', 'max')
    ).reset_index()

    stats = stats[stats['Bevolking'] > 0]
    if stats.empty:
        st.info("Geen geldige bevolkingscijfers gevonden.")
        return

    stats['Per100k'] = (stats['Aantal'] / stats['Bevolking']) * 100000
    stats = stats.sort_values(by='Per100k', ascending=False).head(top_n)

    colors = [COLOR_ACCENT if i == 0 else COLOR_CONTEXT for i in range(len(stats))]

    fig = px.bar(
        stats,
        x='Per100k',
        y=group_col,
        orientation='h',
        text='Per100k'
    )
    max_val = stats['Per100k'].max()
    fig.update_traces(
        marker_color=colors,
        texttemplate='%{text:.2f}',
        textposition='outside',
        cliponaxis=False
    )
    fig.update_layout(
        yaxis=dict(autorange="reversed", title=group_col.replace('_', ' ').capitalize()),
        xaxis=dict(range=[0, max_val * 1.25], title="Waarnemingen per 100.000 inwoners"),
        margin=dict(l=20, r=40, t=30, b=20)
    )
    st.plotly_chart(fig, use_container_width=True)


def plot_hourly_distribution(dataframe: pd.DataFrame):
    """Genereert de uurverdeling van het aantal waarnemingen."""
    if 'hour' not in dataframe.columns or dataframe['hour'].dropna().empty:
        st.info("Geen tijdstippen beschikbaar.")
        return

    hourly_counts = dataframe['hour'].value_counts().sort_index().reset_index()
    hourly_counts.columns = ['Uur', 'Aantal']

    full_hours = pd.DataFrame({'Uur': list(range(24))})
    hourly_counts = pd.merge(full_hours, hourly_counts, on='Uur', how='left').fillna(0)
    hourly_counts['Aantal'] = hourly_counts['Aantal'].astype(int)

    hourly_counts['Tijdsblok'] = hourly_counts['Uur'].apply(lambda h: f"{int(h):02d}:00 - {int(h) + 1:02d}:00")
    hourly_counts['Uur_label'] = hourly_counts['Uur'].apply(lambda h: f"{int(h):02d}:00")

    max_count = hourly_counts['Aantal'].max()
    threshold = max_count * 0.80 if max_count > 0 else 0

    colors_hour = [
        COLOR_ACCENT if val >= threshold and val > 0 else COLOR_CONTEXT
        for val in hourly_counts['Aantal']
    ]

    fig_hourly = px.bar(
        hourly_counts,
        x='Uur_label',
        y='Aantal',
        hover_data={'Uur_label': False, 'Tijdsblok': True, 'Aantal': ':,d'}
    )
    fig_hourly.update_traces(marker_color=colors_hour)
    fig_hourly.update_layout(
        xaxis_title="Startuur",
        yaxis_title="Aantal meldingen",
        margin=dict(l=20, r=20, t=30, b=20)
    )
    st.plotly_chart(fig_hourly, use_container_width=True)


def plot_top_states(dataframe: pd.DataFrame, state_col: str | None, top_n: int = 10):
    """Genereert een staafdiagram voor de meest voorkomende Amerikaanse staten."""
    clean_s_series = get_clean_series(dataframe, state_col)
    if clean_s_series.empty:
        st.info("Geen staatgegevens beschikbaar in de huidige selectie.")
        return

    state_counts = clean_s_series.value_counts().head(top_n).reset_index()
    state_counts.columns = ['Staat', 'Aantal']

    colors_state = [COLOR_ACCENT if i == 0 else COLOR_CONTEXT for i in range(len(state_counts))]

    fig_state = px.bar(state_counts, x='Staat', y='Aantal', text='Aantal')
    max_st_val = state_counts['Aantal'].max()
    fig_state.update_traces(marker_color=colors_state, textposition='outside', cliponaxis=False)
    fig_state.update_layout(
        yaxis=dict(range=[0, max_st_val * 1.18], title="Aantal meldingen"),
        xaxis=dict(title="Amerikaanse Staat"),
        margin=dict(l=20, r=20, t=30, b=20)
    )
    st.plotly_chart(fig_state, use_container_width=True)


def plot_timeline(dataframe: pd.DataFrame, key_suffix: str = "default"):
    """Genereert de tijdslijn van waarnemingen over de jaren heen."""
    if 'datetime_clean' not in dataframe.columns or dataframe['datetime_clean'].dropna().empty:
        st.info("Geen datumgegevens beschikbaar voor de tijdslijn.")
        return

    df_timeline = dataframe.dropna(subset=['datetime_clean']).copy()
    total_records = len(df_timeline)

    default_cumulative = total_records < 100

    is_cumulative = st.checkbox(
        "Toon cumulatief verloop",
        value=default_cumulative,
        key=f"cum_check_{key_suffix}"
    )

    if total_records < 20:
        df_timeline['date'] = df_timeline['datetime_clean'].dt.year
        x_title = "Jaar"
    else:
        df_timeline['date'] = df_timeline['datetime_clean'].dt.to_period('M').dt.to_timestamp()
        x_title = "Datum"

    timeline_counts = df_timeline.groupby('date').size().reset_index(name='Aantal')

    if is_cumulative:
        timeline_counts['Aantal'] = timeline_counts['Aantal'].cumsum()
        y_title = "Cumulatief aantal meldingen"
    else:
        y_title = "Aantal meldingen"

    fig_timeline = px.line(
        timeline_counts,
        x='date',
        y='Aantal',
        labels={'date': x_title, 'Aantal': y_title}
    )
    fig_timeline.update_traces(line_color=COLOR_ACCENT, line_width=2.5)

    max_y = timeline_counts['Aantal'].max()
    fig_timeline.update_layout(
        yaxis=dict(tick0=0, dtick=1 if max_y <= 10 else None, title=y_title),
        margin=dict(l=20, r=20, t=30, b=20)
    )

    if total_records >= 20:
        fig_timeline.update_xaxes(
            rangeselector=dict(
                buttons=[
                    dict(count=5, label="5J", step="year", stepmode="backward"),
                    dict(count=10, label="10J", step="year", stepmode="backward"),
                    dict(count=25, label="25J", step="year", stepmode="backward"),
                    dict(step="all", label="Alles")
                ]
            )
        )

    st.plotly_chart(fig_timeline, use_container_width=True)


# Core Dashboard Layout
st.title("UFO Spotter Dashboard")
st.markdown(
    "Analyse van wereldwijde UFO-waarnemingen in combinatie met bevolkingsdata "
    "om patronen in locaties, tijden en vormen te ontdekken."
)

with st.spinner("Data laden..."):
    df = load_combined_data()

if df.empty:
    st.error("De dataset kon niet worden geladen.")
    st.stop()

# Datacleaning via DataCleaner class
cleaner = DataCleaner(df)
cleaner.standardize_empty_values()
cleaner.clean_text_columns(replace_html=True, strip=True)

# Coerce numerieke velden (inclusief duur voor latere filtering)
num_cols = [c for c in ['population', 'length_of_encounter_seconds'] if c in cleaner.get_df().columns]
if num_cols:
    cleaner.convert_numeric(columns=num_cols)

cleaner.drop_duplicates()

# Datetime opschonen en verwerken
datetime_col = detect_column(cleaner.get_df(), ['date_time', 'datetime', 'date'])
if datetime_col:
    cleaner.df[datetime_col] = cleaner.df[datetime_col].astype(str).str.replace('24:00', '00:00')
    cleaner.convert_datetime(columns=[datetime_col])

    df = cleaner.get_df()
    df['datetime_clean'] = df[datetime_col]
    df['hour'] = df['datetime_clean'].dt.hour
    df['year'] = df['datetime_clean'].dt.year
else:
    df = cleaner.get_df()

# Kolommen detecteren
state_col = detect_column(df, ['state', 'state/province', 'state_code', 'region', 'staat', 'province'])
city_col = detect_column(df, ['city', 'stad', 'town', 'location'])
shape_col = detect_column(df, ['shape', 'ufo_shape', 'vorm'])

if state_col:
    df['state_full'] = df[state_col].astype(str).str.strip().str.upper().map(STATE_MAP).fillna(df[state_col])
    state_col = 'state_full'

# Sidebar Filters
st.sidebar.header("Filters")

available_countries = []
if 'country_name' in df.columns:
    raw_countries = df['country_name'].dropna().unique()
    available_countries = sorted([c for c in raw_countries if str(c).lower() not in INVALID_VALUES])

selected_country = st.sidebar.selectbox(
    "Selecteer land / weergave:",
    options=["Wereldwijd overzicht"] + available_countries
)

selected_state = "Alle staten"
is_usa_selected = selected_country.lower() in USA_NAMES

if is_usa_selected and state_col:
    usa_df = df[df['country_name'] == selected_country]
    clean_states_series = get_clean_series(usa_df, state_col)

    us_allowed_names = {STATE_MAP[code] for code in US_STATES if code in STATE_MAP} | US_STATES
    available_states = sorted([s for s in clean_states_series.unique() if s in us_allowed_names])

    selected_state = st.sidebar.selectbox(
        "Selecteer Amerikaanse staat:",
        options=["Alle staten"] + available_states
    )

hour_range = st.sidebar.slider(
    "Selecteer uur van de dag:",
    min_value=0,
    max_value=24,
    value=(0, 24)
)

show_only_populated = st.sidebar.checkbox(
    "Toon alleen locaties met bekende bevolkingsdata",
    value=False
)

# Data filtering
filtered_df = df.copy()
is_overview_mode = (selected_country == "Wereldwijd overzicht")

if not is_overview_mode and 'country_name' in filtered_df.columns:
    filtered_df = filtered_df[filtered_df['country_name'] == selected_country]

if is_usa_selected and selected_state != "Alle staten" and state_col:
    filtered_df = filtered_df[filtered_df[state_col] == selected_state]

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

# Mode 1: Wereldwijd Overzicht
if is_overview_mode:
    st.header("Wereldwijd Overzicht")

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
        peak_hour_str = f"{peak_hour:02d}:00u - {peak_hour + 1:02d}:00u"

    top_state_str = "Onbekend"
    clean_states = get_clean_series(filtered_df, state_col)
    if not clean_states.empty:
        top_state_str = clean_states.value_counts().index[0]

    top_shape_str = "Onbekend"
    clean_shapes = get_clean_series(filtered_df, shape_col)
    if not clean_shapes.empty:
        top_shape_str = clean_shapes.value_counts().index[0].capitalize()

    kpi1, kpi2, kpi3, kpi4 = st.columns(4)
    kpi1.metric("Meeste Meldingen", top_country, f"{top_country_pct:.1f}% van totaal")
    kpi2.metric("Piek Tijdstip", peak_hour_str)
    kpi3.metric("Top Staat/Regio", top_state_str)
    kpi4.metric("Meest Gemelde Vorm", top_shape_str)

    st.divider()

    row1_col1, row1_col2 = st.columns(2)

    with row1_col1:
        st.subheader("Top Landen (Aantal meldingen)")
        clean_c_series = get_clean_series(filtered_df, 'country_name')
        if not clean_c_series.empty:
            country_counts = clean_c_series.value_counts().head(8).reset_index()
            country_counts.columns = ['Land', 'Aantal']

            colors = [COLOR_ACCENT if i == 0 else COLOR_CONTEXT for i in range(len(country_counts))]

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
        st.subheader("Waarnemingen per 100k Inwoners")
        plot_per_100k(filtered_df, group_col='country_name', top_n=8)

    st.divider()

    row2_col1, row2_col2 = st.columns(2)

    with row2_col1:
        st.subheader("Top Staten (VS)")
        plot_top_states(filtered_df, state_col)

    with row2_col2:
        st.subheader("Meest Voorkomende Vormen")
        clean_sh_series = get_clean_series(filtered_df, shape_col)
        if not clean_sh_series.empty:
            shape_counts = clean_sh_series.value_counts().head(7).reset_index()
            shape_counts.columns = ['Vorm', 'Aantal']

            colors_shape = [COLOR_ACCENT if i == 0 else COLOR_CONTEXT for i in range(len(shape_counts))]

            fig_shape = px.bar(shape_counts, x='Aantal', y='Vorm', orientation='h', text='Aantal')
            max_sh_val = shape_counts['Aantal'].max()
            fig_shape.update_traces(marker_color=colors_shape, textposition='outside', cliponaxis=False)
            fig_shape.update_layout(
                yaxis=dict(autorange="reversed"),
                xaxis=dict(range=[0, max_sh_val * 1.18]),
                margin=dict(l=20, r=30, t=30, b=20)
            )
            st.plotly_chart(fig_shape, use_container_width=True)

    st.divider()

    st.subheader("Verdeling per Uur")
    plot_hourly_distribution(filtered_df)

    st.divider()

    st.subheader("Verloop van Waarnemingen over de Tijd")
    plot_timeline(filtered_df, key_suffix="overview")

# Mode 2: Specifiek Land
else:
    header_title = f"Overzicht: {selected_country}"
    if is_usa_selected and selected_state != "Alle staten":
        header_title += f" ({selected_state})"

    st.header(header_title)

    total_sightings = len(filtered_df)

    per_100k_str = "N.v.t."
    if 'population' in filtered_df.columns and not filtered_df['population'].dropna().empty:
        pop = filtered_df['population'].iloc[0]
        if pd.notna(pop) and pop > 0:
            per_100k_val = (total_sightings / pop) * 100000
            per_100k_str = f"{per_100k_val:.2f}"

    top_shape = "Onbekend"
    clean_sh = get_clean_series(filtered_df, shape_col)
    if not clean_sh.empty:
        top_shape = clean_sh.value_counts().index[0].capitalize()

    # 1. KPI's
    k1, k2, k3 = st.columns(3)
    k1.metric("Aantal Waarnemingen", f"{total_sightings:,}")
    k2.metric("Per 100k Inwoners", per_100k_str)
    k3.metric("Meest Geziene Vorm", top_shape)

    st.divider()

    # 2. Sightings over de jaren (Tijdslijn)
    st.subheader("Verloop over de Tijd")
    plot_timeline(filtered_df, key_suffix="country")

    # 3. Staten (alleen zichtbaar bij VS -> Alle staten)
    if is_usa_selected and selected_state == "Alle staten":
        st.divider()
        st.subheader("Top Staten (VS)")
        plot_top_states(filtered_df, state_col)

    st.divider()

    # 4a/4b. Vormen & Uurverdeling / Top Steden
    col_a, col_b = st.columns(2)

    with col_a:
        st.subheader("Meest Geziene Vormen")
        if not clean_sh.empty:
            shape_counts = clean_sh.value_counts().head(7).reset_index()
            shape_counts.columns = ['Vorm', 'Aantal']

            colors_shape = [COLOR_ACCENT if i == 0 else COLOR_CONTEXT for i in range(len(shape_counts))]

            fig_shape = px.bar(shape_counts, x='Aantal', y='Vorm', orientation='h', text='Aantal')
            max_sh_val = shape_counts['Aantal'].max()
            fig_shape.update_traces(marker_color=colors_shape, textposition='outside', cliponaxis=False)
            fig_shape.update_layout(
                yaxis=dict(autorange="reversed"),
                xaxis=dict(range=[0, max_sh_val * 1.2]),
                margin=dict(l=20, r=30, t=30, b=20)
            )
            st.plotly_chart(fig_shape, use_container_width=True)
        else:
            st.info("Geen gegevens beschikbaar over vormen voor deze selectie.")

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
            st.subheader("Verdeling per Uur")
            plot_hourly_distribution(filtered_df)

st.divider()

with st.expander("Data Integratie Details"):
    st.markdown("**Samenvoeging:** `iso3` (UFO data) = `countryId` (Bevolkingsdata API)")
    rijen_totaal = len(df)

    col_a, col_b = st.columns(2)
    col_a.metric("Aantal rijen voor merge", f"{rijen_totaal:,}")
    col_b.metric("Aantal rijen na merge", f"{rijen_totaal:,}")

# ============================================================
# MARIHUANAGEBRUIK VS UFO-MELDINGEN
# ============================================================

st.divider()
st.header("Marihuanagebruik vs. UFO-meldingen")

# 1. Drugs dataset laden
try:
    drug_loader = KaggleDataLoader(
        "mexwell/us-drug-abuse",
        download_dir="../data"
    )
    drugs = drug_loader.load_csv("drugs.csv")
except Exception as e:
    st.warning(f"Kon drugs.csv niet laden: {e}")
    drugs = pd.DataFrame()

if not drugs.empty:
    # Omgekeerde mapping van STATE_MAP (Full Name -> Code)
    inv_state_map = {v.lower(): k for k, v in STATE_MAP.items()} if STATE_MAP else {}

    # 2. UFO's per staat tellen
    raw_state_col = detect_column(df, ['state', 'state/province', 'state_code', 'state_full']) or 'state'
    ufo_states = df[raw_state_col].dropna().astype(str).str.strip()
    ufo_states_code = ufo_states.map(lambda x: inv_state_map.get(x.lower(), x)).str.upper()

    ufo_per_state = ufo_states_code.value_counts().reset_index()
    ufo_per_state.columns = ["State_code", "UFO_count"]

    # 3. Drugs data opschonen met DataCleaner
    drugs_cleaner = DataCleaner(drugs)
    drugs_cleaner.clean_text_columns(columns=["State"], strip=True, lower=True)

    target_rate_col = "Rates.Marijuana.Used Past Year.18-25"
    if target_rate_col in drugs.columns:
        drugs_cleaner.convert_numeric(columns=[target_rate_col])

    drugs_df = drugs_cleaner.get_df()
    drugs_df["State_code"] = drugs_df["State"].map(inv_state_map)
    drugs_df["Marijuana_18_25"] = drugs_df[target_rate_col] if target_rate_col in drugs_df.columns else pd.Series(
        dtype=float)

    # 4. Data combineren & opschonen
    data_scatter = pd.merge(
        drugs_df,
        ufo_per_state,
        on="State_code",
        how="inner"
    )[["State", "State_code", "Marijuana_18_25", "UFO_count"]].dropna()

    data_scatter = data_scatter.drop_duplicates(subset=["State_code"]).head(50)

    st.write("Aantal gekoppelde staten:", len(data_scatter))
    st.dataframe(data_scatter)

    # 5. Scatterplot & Correlatie
    if not data_scatter.empty:
        fig_scatter = px.scatter(
            data_scatter,
            x="Marijuana_18_25",
            y="UFO_count",
            hover_name="State",
            labels={
                "Marijuana_18_25": "Marihuanagebruik 18-25 (%)",
                "UFO_count": "Aantal UFO-meldingen"
            },
            title="Marihuanagebruik vs. UFO-meldingen per staat"
        )
        st.plotly_chart(fig_scatter, use_container_width=True)

        correlation = data_scatter["Marijuana_18_25"].corr(data_scatter["UFO_count"])
        st.metric("Pearson correlatie", f"{correlation:.2f}")

