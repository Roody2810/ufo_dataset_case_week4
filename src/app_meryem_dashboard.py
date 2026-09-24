import streamlit as st
import pandas as pd
import matplotlib.pyplot as plt
import kagglehub

st.set_page_config(
    page_title="UFO Sightings Dashboard",
    page_icon="🛸",
    layout="wide"
)

# ---------------------------------------------------------
# DATA OPHALEN EN OPSCHONEN
# UFO-data wordt in het script opgehaald via de openbare
# Kaggle API met kagglehub.
# Bron API: https://github.com/Kaggle/kagglehub
# Dataset: camnugent/ufo-sightings-around-the-world
# ---------------------------------------------------------

@st.cache_data
def load_data():
    # Publieke Kaggle-dataset via API downloaden.
    ufo_path = kagglehub.dataset_download(
        "camnugent/ufo-sightings-around-the-world",
        path="ufo_sighting_data.csv"
    )
    ufo_df = pd.read_csv(ufo_path, low_memory=False)

    # Tweede dataset uit het project.
    population_df = pd.read_csv(
        "data/US-population-by-state(wide)-selected-columns.csv"
    )

    # ---- UFO-data opschonen ----
    ufo_df["duration_seconds_clean"] = pd.to_numeric(
        ufo_df["length_of_encounter_seconds"]
        .astype(str)
        .str.replace("`", "", regex=False),
        errors="coerce"
    )

    ufo_df["latitude_clean"] = pd.to_numeric(
        ufo_df["latitude"],
        errors="coerce"
    )

    # Waarden zoals 24:00 apart corrigeren.
    mask_24 = ufo_df["Date_time"].astype(str).str.endswith("24:00")

    ufo_df["datetime_clean"] = pd.to_datetime(
        ufo_df["Date_time"],
        errors="coerce"
    )

    corrected_24 = (
        pd.to_datetime(
            ufo_df.loc[mask_24, "Date_time"]
            .str.replace("24:00", "00:00", regex=False),
            errors="coerce"
        )
        + pd.Timedelta(days=1)
    )

    ufo_df.loc[mask_24, "datetime_clean"] = corrected_24

    ufo_df["year"] = ufo_df["datetime_clean"].dt.year
    ufo_df["month"] = ufo_df["datetime_clean"].dt.month
    ufo_df["day_of_week"] = ufo_df["datetime_clean"].dt.day_name()
    ufo_df["hour"] = ufo_df["datetime_clean"].dt.hour

    state_mapping = {
        "al": "Alabama",
        "ak": "Alaska",
        "az": "Arizona",
        "ar": "Arkansas",
        "ca": "California",
        "co": "Colorado",
        "ct": "Connecticut",
        "de": "Delaware",
        "dc": "District of Columbia"
    }

    ufo_df["state"] = ufo_df["state/province"].map(state_mapping)

    # ---- Population-data lang maken ----
    population_long = population_df.melt(
        id_vars="year",
        var_name="state",
        value_name="population"
    )

    # Aantal UFO-meldingen per jaar en staat.
    ufo_per_state_year = (
        ufo_df[ufo_df["state"].notna()]
        .groupby(["year", "state"])
        .size()
        .reset_index(name="ufo_count")
    )

    # Voor het dashboard starten we vanuit de population-tabel,
    # zodat combinaties met 0 UFO-meldingen ook blijven bestaan.
    dashboard_df = population_long.merge(
        ufo_per_state_year,
        on=["year", "state"],
        how="left"
    )

    dashboard_df["ufo_count"] = (
        dashboard_df["ufo_count"]
        .fillna(0)
        .astype(int)
    )

    dashboard_df["ufo_per_100k"] = (
        dashboard_df["ufo_count"] / dashboard_df["population"]
    ) * 100000

    return ufo_df, population_df, population_long, ufo_per_state_year, dashboard_df


ufo_df, population_df, population_long, ufo_per_state_year, dashboard_df = load_data()


# ---------------------------------------------------------
# TITEL + KPI'S
# ---------------------------------------------------------

st.title("🛸 UFO Sightings Dashboard")
st.write(
    "Ontdek patronen in geregistreerde UFO-meldingen door de tijd, "
    "vergelijk vormen en tijdstippen en bekijk meldingen ten opzichte "
    "van de bevolkingsgrootte van geselecteerde Amerikaanse staten."
)

full_year_df = ufo_df[ufo_df["year"].between(1949, 2013)].copy()

kpi1, kpi2, kpi3, kpi4 = st.columns(4)

kpi1.metric("Totaal aantal records", f"{len(ufo_df):,}".replace(",", "."))
kpi2.metric(
    "Periode",
    f"{int(ufo_df['year'].min())}–{int(ufo_df['year'].max())}"
)
kpi3.metric(
    "Meest gemelde vorm",
    str(ufo_df["UFO_shape"].value_counts().index[0]).title()
)
kpi4.metric(
    "Piek-uur",
    f"{int(ufo_df['hour'].value_counts().idxmax()):02d}:00"
)

st.caption(
    "Voor jaarvergelijkingen gebruiken we 1949–2013. "
    "2014 is geen volledig jaar in deze dataset."
)

st.divider()


# ---------------------------------------------------------
# SIDEBAR FILTERS
# ---------------------------------------------------------

st.sidebar.header("Filters")

available_countries = sorted(
    ufo_df["country"].dropna().astype(str).unique().tolist()
)

country_choice = st.sidebar.selectbox(
    "Land",
    ["Alle landen"] + available_countries
)

filtered_ufo = full_year_df.copy()

if country_choice != "Alle landen":
    filtered_ufo = filtered_ufo[
        filtered_ufo["country"] == country_choice
    ]

shape_options = sorted(
    filtered_ufo["UFO_shape"].dropna().astype(str).unique().tolist()
)

shape_choice = st.sidebar.selectbox(
    "UFO-vorm",
    ["Alle vormen"] + shape_options
)

if shape_choice != "Alle vormen":
    filtered_ufo = filtered_ufo[
        filtered_ufo["UFO_shape"] == shape_choice
    ]

st.sidebar.caption(
    "Deze filters beïnvloeden de algemene tijdgrafieken. "
    "De bevolkingsvergelijking gebruikt alleen de geselecteerde staten."
)


# ---------------------------------------------------------
# 1. MELDINGEN PER JAAR
# ---------------------------------------------------------

st.header("1. UFO-meldingen door de jaren heen")

yearly_sightings = (
    filtered_ufo
    .groupby("year")
    .size()
    .reset_index(name="ufo_count")
)

fig1, ax1 = plt.subplots(figsize=(11, 4.5))
ax1.plot(
    yearly_sightings["year"],
    yearly_sightings["ufo_count"],
    marker="o",
    markersize=2
)
ax1.set_xlabel("Jaar")
ax1.set_ylabel("Aantal geregistreerde meldingen")
ax1.set_title("Aantal geregistreerde UFO-meldingen per jaar")
ax1.grid(alpha=0.25)
fig1.tight_layout()
st.pyplot(fig1)
plt.close(fig1)

st.caption(
    "Deze grafiek toont geregistreerde meldingen in de dataset; "
    "hij zegt niet hoeveel UFO's daadwerkelijk zijn verschenen."
)

st.divider()


# ---------------------------------------------------------
# 2. MELDINGEN PER 100.000 INWONERS
# Verplichte slider
# ---------------------------------------------------------

st.header("2. Vergelijk staten met hun bevolkingsgrootte")

population_years = dashboard_df[
    (dashboard_df["year"].between(1949, 2013))
    & (dashboard_df["population"].notna())
    & (dashboard_df["state"] != "Alaska")
]["year"]

min_pop_year = int(population_years.min())
max_pop_year = int(population_years.max())

selected_year = st.slider(
    "Selecteer een jaar",
    min_value=min_pop_year,
    max_value=max_pop_year,
    value=max_pop_year,
    step=1
)

state_year = (
    dashboard_df[
        (dashboard_df["year"] == selected_year)
        & (dashboard_df["population"].notna())
        & (dashboard_df["state"] != "Alaska")
    ]
    .sort_values("ufo_per_100k", ascending=False)
    .copy()
)

col_a, col_b = st.columns(2)

with col_a:
    st.subheader(f"Per 100.000 inwoners — {selected_year}")

    fig2, ax2 = plt.subplots(figsize=(7, 5))
    ax2.barh(
        state_year["state"],
        state_year["ufo_per_100k"]
    )
    ax2.invert_yaxis()
    ax2.set_xlabel("UFO-meldingen per 100.000 inwoners")
    ax2.set_ylabel("Staat")
    fig2.tight_layout()
    st.pyplot(fig2)
    plt.close(fig2)

with col_b:
    st.subheader(f"Absolute aantallen — {selected_year}")

    absolute_state_year = state_year.sort_values(
        "ufo_count",
        ascending=False
    )

    fig3, ax3 = plt.subplots(figsize=(7, 5))
    ax3.barh(
        absolute_state_year["state"],
        absolute_state_year["ufo_count"]
    )
    ax3.invert_yaxis()
    ax3.set_xlabel("Aantal geregistreerde UFO-meldingen")
    ax3.set_ylabel("Staat")
    fig3.tight_layout()
    st.pyplot(fig3)
    plt.close(fig3)

st.info(
    "Waarom twee grafieken? Een staat kan veel meldingen hebben omdat er "
    "veel mensen wonen. 'Per 100.000 inwoners' maakt de staten beter vergelijkbaar."
)

st.divider()


# ---------------------------------------------------------
# 3. MELDINGEN PER UUR
# ---------------------------------------------------------

st.header("3. Op welk tijdstip worden UFO's gemeld?")

hourly_sightings = (
    filtered_ufo["hour"]
    .dropna()
    .value_counts()
    .sort_index()
    .reindex(range(24), fill_value=0)
    .reset_index()
)

hourly_sightings.columns = ["hour", "ufo_count"]

fig4, ax4 = plt.subplots(figsize=(11, 4.5))
ax4.plot(
    hourly_sightings["hour"],
    hourly_sightings["ufo_count"],
    marker="o"
)
ax4.set_xlabel("Uur van de dag")
ax4.set_ylabel("Aantal geregistreerde meldingen")
ax4.set_xticks(range(24))
ax4.grid(alpha=0.25)
fig4.tight_layout()
st.pyplot(fig4)
plt.close(fig4)

peak_hour = int(
    hourly_sightings.loc[
        hourly_sightings["ufo_count"].idxmax(),
        "hour"
    ]
)

st.write(
    f"**Piek in deze selectie:** rond **{peak_hour:02d}:00 uur**."
)

st.divider()


# ---------------------------------------------------------
# 4. DAG VAN DE WEEK
# ---------------------------------------------------------

st.header("4. Op welke dag van de week zijn de meeste meldingen?")

day_order = [
    "Monday",
    "Tuesday",
    "Wednesday",
    "Thursday",
    "Friday",
    "Saturday",
    "Sunday"
]

day_labels = {
    "Monday": "Maandag",
    "Tuesday": "Dinsdag",
    "Wednesday": "Woensdag",
    "Thursday": "Donderdag",
    "Friday": "Vrijdag",
    "Saturday": "Zaterdag",
    "Sunday": "Zondag"
}

day_counts = (
    filtered_ufo["day_of_week"]
    .value_counts()
    .reindex(day_order, fill_value=0)
    .reset_index()
)

day_counts.columns = ["day", "ufo_count"]
day_counts["dag"] = day_counts["day"].map(day_labels)

fig5, ax5 = plt.subplots(figsize=(10, 4.5))
ax5.bar(
    day_counts["dag"],
    day_counts["ufo_count"]
)
ax5.set_xlabel("Dag")
ax5.set_ylabel("Aantal geregistreerde meldingen")
ax5.tick_params(axis="x", rotation=25)
fig5.tight_layout()
st.pyplot(fig5)
plt.close(fig5)

st.divider()


# ---------------------------------------------------------
# 5. UFO-VORMEN
# Verplichte dropdown
# ---------------------------------------------------------

st.header("5. Welke UFO-vormen worden het vaakst gemeld?")

top_n = st.selectbox(
    "Hoeveel vormen wil je bekijken?",
    [5, 10, 15, 20],
    index=1
)

shape_counts = (
    filtered_ufo["UFO_shape"]
    .dropna()
    .value_counts()
    .head(top_n)
    .sort_values(ascending=True)
)

fig6, ax6 = plt.subplots(figsize=(10, 5.5))
ax6.barh(
    shape_counts.index,
    shape_counts.values
)
ax6.set_xlabel("Aantal geregistreerde meldingen")
ax6.set_ylabel("UFO-vorm")
fig6.tight_layout()
st.pyplot(fig6)
plt.close(fig6)

st.divider()


# ---------------------------------------------------------
# 6. MELDINGEN PER MAAND
# ---------------------------------------------------------

st.header("6. In welke maanden worden de meeste meldingen geregistreerd?")

month_labels = {
    1: "Jan",
    2: "Feb",
    3: "Mrt",
    4: "Apr",
    5: "Mei",
    6: "Jun",
    7: "Jul",
    8: "Aug",
    9: "Sep",
    10: "Okt",
    11: "Nov",
    12: "Dec"
}

month_counts = (
    filtered_ufo["month"]
    .dropna()
    .astype(int)
    .value_counts()
    .reindex(range(1, 13), fill_value=0)
    .reset_index()
)

month_counts.columns = ["month", "ufo_count"]
month_counts["label"] = month_counts["month"].map(month_labels)

fig7, ax7 = plt.subplots(figsize=(10, 4.5))
ax7.bar(
    month_counts["label"],
    month_counts["ufo_count"]
)
ax7.set_xlabel("Maand")
ax7.set_ylabel("Aantal geregistreerde meldingen")
fig7.tight_layout()
st.pyplot(fig7)
plt.close(fig7)

st.divider()


# ---------------------------------------------------------
# 7. DUUR VAN MELDINGEN
# ---------------------------------------------------------

st.header("7. Hoe lang duren gemelde UFO-waarnemingen?")

duration_valid = filtered_ufo[
    (filtered_ufo["duration_seconds_clean"].notna())
    & (filtered_ufo["duration_seconds_clean"] > 0)
    & (filtered_ufo["duration_seconds_clean"] <= 3600)
]["duration_seconds_clean"]

st.caption(
    "Voor deze grafiek tonen we waarnemingen van maximaal 1 uur, "
    "zodat extreme waarden de verdeling niet onleesbaar maken."
)

fig8, ax8 = plt.subplots(figsize=(10, 4.5))
ax8.hist(
    duration_valid,
    bins=40
)
ax8.set_xlabel("Duur in seconden")
ax8.set_ylabel("Aantal meldingen")
fig8.tight_layout()
st.pyplot(fig8)
plt.close(fig8)

st.divider()


# ---------------------------------------------------------
# 8. ONDERLIGGENDE DATA
# Verplichte checkbox
# ---------------------------------------------------------

st.header("8. Onderliggende gegevens")

show_data = st.checkbox("Toon de onderliggende data")

if show_data:
    display_df = state_year[
        ["year", "state", "ufo_count", "population", "ufo_per_100k"]
    ].copy()

    display_df = display_df.rename(
        columns={
            "year": "Jaar",
            "state": "Staat",
            "ufo_count": "UFO-meldingen",
            "population": "Bevolking",
            "ufo_per_100k": "Meldingen per 100.000"
        }
    )

    display_df["Meldingen per 100.000"] = (
        display_df["Meldingen per 100.000"].round(2)
    )

    st.dataframe(
        display_df,
        use_container_width=True,
        hide_index=True
    )

st.divider()


# ---------------------------------------------------------
# 9. DATAKWALITEIT / JOIN-UITLEG
# ---------------------------------------------------------

with st.expander("Bekijk datakwaliteit en informatie over de join"):
    st.write(
        f"**UFO-dataset:** {len(ufo_df):,} rijen "
        f"en {ufo_df.shape[1]} kolommen."
    )
    st.write(
        f"**Population dataset (wide):** {len(population_df):,} rijen "
        f"en {population_df.shape[1]} kolommen."
    )
    st.write(
        f"**Population dataset na melt:** {len(population_long):,} rijen."
    )
    st.write(
        f"**UFO-aantallen per staat/jaar vóór de join:** "
        f"{len(ufo_per_state_year):,} rijen."
    )
    st.write(
        f"**Dashboard-tabel na de join:** {len(dashboard_df):,} rijen."
    )
    st.write("**Join-sleutels:** `year` + `state`.")
    st.write(
        "We gebruiken een left join vanuit de population-tabel. "
        "Staat-jaarcombinaties zonder UFO-melding blijven daardoor bestaan "
        "en krijgen `ufo_count = 0`."
    )
    st.write(
        "Alaska wordt niet gebruikt in de per-capita grafiek wanneer "
        "bevolkingsdata ontbreekt."
    )

st.divider()


# ---------------------------------------------------------
# 10. KORTE CONCLUSIE
# ---------------------------------------------------------

st.header("10. Wat kunnen we uit het dashboard halen?")

st.markdown(
    """
- De dataset laat zien hoe het **aantal geregistreerde UFO-meldingen door de tijd** verandert.
- Het **tijdstip van de dag** laat duidelijke verschillen in meldingsfrequentie zien.
- Sommige **UFO-vormen** worden veel vaker gerapporteerd dan andere.
- Absolute aantallen per staat vertellen niet het hele verhaal: door te corrigeren voor
  **bevolkingsgrootte** kunnen staten anders worden gerangschikt.
- Deze resultaten gaan over **geregistreerde meldingen in de dataset**, niet over bewijs
  voor het daadwerkelijke bestaan van buitenaardse UFO's.
"""
)

st.caption(
    "UFO-bron: Kaggle – camnugent/ufo-sightings-around-the-world. "
    "Population-bron: US Population by State – Census Data (1790–2024)."
)
