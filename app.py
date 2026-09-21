import streamlit as st
import pandas as pd
import matplotlib.pyplot as plt
@st.cache_data
def load_data():
    ufo_df = pd.read_csv("data/ufo_sighting_data.csv")

    population_df = pd.read_csv(
        "data/US-population-by-state(wide)-selected-columns.csv"
    )

    mask_24 = ufo_df["Date_time"].str.endswith("24:00")

    ufo_df["datetime_clean"] = pd.to_datetime(
        ufo_df["Date_time"],
        errors="coerce"
    )

    ufo_df.loc[mask_24, "datetime_clean"] = (
        pd.to_datetime(
            ufo_df.loc[mask_24, "Date_time"].str.replace(
                "24:00", "00:00", regex=False
            ),
            errors="coerce"
        ) + pd.Timedelta(days=1)
    )

    ufo_df["year"] = ufo_df["datetime_clean"].dt.year
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

    return ufo_df, population_df


ufo_df, population_df = load_data()
population_long = population_df.melt(
    id_vars="year",
    var_name="state",
    value_name="population"
)
ufo_per_state_year = (
    ufo_df[ufo_df["state"].notna()]
    .groupby(["year", "state"])
    .size()
    .reset_index(name="ufo_count")
)
dashboard_df = population_long.merge(
    ufo_per_state_year,
    on=["year", "state"],
    how="left"
)

dashboard_df["ufo_count"] = dashboard_df["ufo_count"].fillna(0).astype(int)
st.title("UFO Sightings Dashboard")
st.write(
    "Ontdek patronen in geregistreerde UFO-meldingen en vergelijk "
    "Amerikaanse staten op basis van bevolkingsgrootte."
)
yearly_sightings = (
    ufo_df[ufo_df["year"].between(1949, 2013)]
    .groupby("year")
    .size()
    .reset_index(name="ufo_count")
)

st.subheader("UFO-meldingen door de jaren heen")

fig, ax = plt.subplots(figsize=(10, 5))

ax.plot(
    yearly_sightings["year"],
    yearly_sightings["ufo_count"]
)

ax.set_xlabel("Jaar")
ax.set_ylabel("Aantal UFO-meldingen")

st.pyplot(fig)



