
import streamlit as st
import plotly.express as px
import pandas as pd

st.set_page_config(
    page_title="FlameGuard AI",
    page_icon="🔥",
    layout="wide"
)

st.title("🔥 FlameGuard AI")
st.subheader(
    "AI-Powered Microgravity Combustion Research"
)

st.write(
    "Explore NASA combustion investigations "
    "and their implications for space fire safety."
)

st.sidebar.title("Navigation")

page = st.sidebar.selectbox(
    "Choose a page",
    [
        "Home",
        "Research Explorer",
        "Data Analytics",
        "Fire Safety Insights"
    ]
)

if page == "Home":
    st.header("Welcome to FlameGuard AI")
    st.info(
        "Turning NASA combustion research "
        "into actionable research insights."
    )

elif page == "Research Explorer":
    st.header("NASA Research Explorer")
    st.write(
        "Connect NASA PSI investigation metadata here."
    )

elif page == "Data Analytics":
    st.header("Combustion Data Analytics")

    data = pd.DataFrame({
        "Experiment": ["Experiment A", "Experiment B",
                       "Experiment C"],
        "Temperature": [30, 45, 38]
    })

    fig = px.bar(
        data,
        x="Experiment",
        y="Temperature",
        title="Illustrative Experiment Data"
    )

    st.plotly_chart(fig, use_container_width=True)
    st.caption("Illustrative values, not NASA measurements.")

elif page == "Fire Safety Insights":
    st.header("Fire Safety Research Insights")
    st.write(
        "Research-based safety insights will appear here."
    )
