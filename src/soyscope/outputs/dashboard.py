"""Streamlit dashboard for SoyScope."""

from __future__ import annotations

import json
import sys
from pathlib import Path

import streamlit as st
import plotly.express as px
import plotly.graph_objects as go
import pandas as pd

# Add project to path
_PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent.parent
sys.path.insert(0, str(_PROJECT_ROOT / "src"))

from soyscope.config import get_settings
from soyscope.db import Database


def get_db() -> Database:
    settings = get_settings()
    db = Database(settings.db_path)
    return db


def page_overview():
    st.header("Database Overview")
    db = get_db()
    stats = db.get_stats()

    # Key metrics
    col1, col2, col3, col4 = st.columns(4)
    col1.metric("Total Findings", f"{stats['total_findings']:,}")
    col2.metric("Sectors", stats["total_sectors"])
    col3.metric("Derivatives", stats["total_derivatives"])
    col4.metric("Enriched", f"{stats['total_enriched']:,}")

    col5, col6, col7, col8 = st.columns(4)
    col5.metric("Checkoff Projects", f"{stats['total_checkoff']:,}")
    col6.metric("Tags", stats["total_tags"])
    col7.metric("Search Runs", stats["total_runs"])
    col8.metric("Tier 2 (AI)", stats["enrichment_summary"])

    # Source distribution
    st.subheader("Findings by Source API")
    if stats["by_source"]:
        df_source = pd.DataFrame(
            list(stats["by_source"].items()), columns=["Source", "Count"]
        )
        fig = px.bar(df_source, x="Source", y="Count", color="Source",
                     title="Findings by Source API")
        st.plotly_chart(fig, use_container_width=True)

    # Timeline
    st.subheader("Findings by Year")
    if stats["by_year"]:
        df_year = pd.DataFrame(
            list(stats["by_year"].items()), columns=["Year", "Count"]
        )
        df_year["Year"] = df_year["Year"].astype(int)
        df_year = df_year.sort_values("Year")
        fig = px.line(df_year, x="Year", y="Count", markers=True,
                      title="Publication Timeline")
        st.plotly_chart(fig, use_container_width=True)

    # Source type
    st.subheader("Findings by Type")
    if stats["by_type"]:
        df_type = pd.DataFrame(
            list(stats["by_type"].items()), columns=["Type", "Count"]
        )
        fig = px.pie(df_type, names="Type", values="Count",
                     title="Source Type Distribution")
        st.plotly_chart(fig, use_container_width=True)


def page_explorer():
    st.header("Finding Explorer")
    db = get_db()

    # Search
    query = st.text_input("Search findings", placeholder="e.g., soy adhesive construction")

    # Filters
    col1, col2, col3 = st.columns(3)
    with col1:
        year_range = st.slider("Year Range", 2000, 2026, (2000, 2026))
    with col2:
        source_filter = st.multiselect("Source API",
            ["openalex", "semantic_scholar", "exa", "crossref", "pubmed", "tavily", "core", "checkoff"])
    with col3:
        type_filter = st.multiselect("Source Type",
            ["paper", "patent", "news", "report", "trade_pub", "conference", "govt_report"])

    # Query
    if query:
        findings = db.search_findings(query, limit=200)
    else:
        findings = db.get_all_findings(limit=200)

    # Apply filters
    if findings:
        df = pd.DataFrame(findings)
        if "year" in df.columns:
            df = df[df["year"].between(year_range[0], year_range[1]) | df["year"].isna()]
        if source_filter:
            df = df[df["source_api"].isin(source_filter)]
        if type_filter:
            df = df[df["source_type"].isin(type_filter)]

        st.write(f"Showing {len(df)} findings")

        # Display columns
        display_cols = ["id", "title", "year", "source_api", "source_type", "venue", "citation_count", "doi"]
        available_cols = [c for c in display_cols if c in df.columns]
        st.dataframe(df[available_cols], use_container_width=True, height=600)

        # Detail view
        if not df.empty:
            selected_id = st.selectbox("View details for finding ID:", df["id"].tolist())
            if selected_id:
                finding = db.get_finding_by_id(selected_id)
                if finding:
                    st.subheader(finding["title"])
                    st.write(f"**Year:** {finding.get('year', 'N/A')}")
                    st.write(f"**DOI:** {finding.get('doi', 'N/A')}")
                    st.write(f"**Venue:** {finding.get('venue', 'N/A')}")
                    st.write(f"**Source:** {finding.get('source_api', 'N/A')} ({finding.get('source_type', 'N/A')})")
                    if finding.get("abstract"):
                        st.write("**Abstract:**")
                        st.write(finding["abstract"][:2000])

                    # Enrichment
                    enrichment = db.get_enrichment(selected_id)
                    if enrichment:
                        st.write("---")
                        st.write(f"**TRL:** {enrichment.get('trl_estimate', 'N/A')}")
                        st.write(f"**Novelty Score:** {enrichment.get('novelty_score', 'N/A')}")
                        st.write(f"**Status:** {enrichment.get('commercialization_status', 'N/A')}")
                        if enrichment.get("ai_summary"):
                            st.write(f"**AI Summary:** {enrichment['ai_summary']}")
    else:
        st.info("No findings found. Run `soyscope build` to populate the database.")


def page_matrix():
    st.header("Sector × Derivative Matrix")
    db = get_db()
    stats = db.get_stats()
    matrix_data = stats.get("sector_derivative_matrix", [])

    if not matrix_data:
        st.info("No sector-derivative associations found. Run `soyscope enrich` first.")
        return

    df = pd.DataFrame(matrix_data)
    pivot = df.pivot_table(index="sector", columns="derivative", values="count", fill_value=0)

    # Heatmap
    fig = go.Figure(data=go.Heatmap(
        z=pivot.values,
        x=pivot.columns.tolist(),
        y=pivot.index.tolist(),
        colorscale="Greens",
        text=pivot.values,
        texttemplate="%{text}",
        textfont={"size": 10},
    ))
    fig.update_layout(
        title="Findings: Sector × Derivative",
        xaxis_title="Derivative",
        yaxis_title="Sector",
        height=max(400, len(pivot.index) * 30),
    )
    fig.update_xaxes(tickangle=45)
    st.plotly_chart(fig, use_container_width=True)

    # Raw data
    with st.expander("View raw matrix data"):
        st.dataframe(pivot, use_container_width=True)


def page_trends():
    st.header("Trends & Emerging Sectors")
    db = get_db()
    stats = db.get_stats()

    # Year-over-year
    st.subheader("Year-over-Year Growth")
    if stats["by_year"]:
        df_year = pd.DataFrame(list(stats["by_year"].items()), columns=["Year", "Count"])
        df_year["Year"] = df_year["Year"].astype(int)
        df_year = df_year.sort_values("Year")
        df_year["Growth"] = df_year["Count"].pct_change() * 100

        fig = px.bar(df_year, x="Year", y="Count", title="Findings per Year")
        st.plotly_chart(fig, use_container_width=True)

        fig2 = px.line(df_year[df_year["Growth"].notna()], x="Year", y="Growth",
                       markers=True, title="Year-over-Year Growth (%)")
        st.plotly_chart(fig2, use_container_width=True)

    # Sector trends over time
    st.subheader("Sector Activity Over Time")
    with db.connect() as conn:
        rows = conn.execute(
            """SELECT s.name as sector, f.year, COUNT(*) as cnt
               FROM finding_sectors fs
               JOIN sectors s ON fs.sector_id = s.id
               JOIN findings f ON fs.finding_id = f.id
               WHERE f.year IS NOT NULL
               GROUP BY s.name, f.year
               ORDER BY f.year"""
        ).fetchall()

    if rows:
        df_sectors = pd.DataFrame([dict(r) for r in rows])
        fig = px.line(df_sectors, x="year", y="cnt", color="sector",
                      title="Sector Activity Over Time")
        st.plotly_chart(fig, use_container_width=True)


def page_novel():
    st.header("Novel Uses & AI Discoveries")
    db = get_db()

    # Top novel findings
    st.subheader("Highest Novelty Scores")
    with db.connect() as conn:
        rows = conn.execute(
            """SELECT f.id, f.title, f.year, e.novelty_score, e.trl_estimate,
                      e.commercialization_status, e.ai_summary
               FROM enrichments e
               JOIN findings f ON e.finding_id = f.id
               WHERE e.novelty_score IS NOT NULL
               ORDER BY e.novelty_score DESC
               LIMIT 50"""
        ).fetchall()

    if rows:
        df = pd.DataFrame([dict(r) for r in rows])
        st.dataframe(df, use_container_width=True, height=400)

        # Novelty distribution
        fig = px.histogram(df, x="novelty_score", nbins=20,
                           title="Novelty Score Distribution")
        st.plotly_chart(fig, use_container_width=True)
    else:
        st.info("No enrichment data. Run `soyscope enrich` first.")

    # AI-discovered categories
    st.subheader("AI-Discovered Categories")
    with db.connect() as conn:
        ai_sectors = [dict(r) for r in conn.execute(
            "SELECT * FROM sectors WHERE is_ai_discovered = 1"
        ).fetchall()]
        ai_derivatives = [dict(r) for r in conn.execute(
            "SELECT * FROM derivatives WHERE is_ai_discovered = 1"
        ).fetchall()]

    if ai_sectors:
        st.write(f"**New Sectors Discovered:** {len(ai_sectors)}")
        for s in ai_sectors:
            st.write(f"  - {s['name']}: {s.get('description', '')}")

    if ai_derivatives:
        st.write(f"**New Derivatives Discovered:** {len(ai_derivatives)}")
        for d in ai_derivatives:
            st.write(f"  - {d['name']}: {d.get('description', '')}")

    if not ai_sectors and not ai_derivatives:
        st.info("No AI-discovered categories yet.")


def page_run_history():
    st.header("Search Run History")
    db = get_db()

    with db.connect() as conn:
        runs = [dict(r) for r in conn.execute(
            "SELECT * FROM search_runs ORDER BY id DESC LIMIT 50"
        ).fetchall()]

    if not runs:
        st.info("No search runs recorded yet.")
        return

    df = pd.DataFrame(runs)
    st.dataframe(df, use_container_width=True)

    # API usage per run
    for run in runs[:5]:
        if run.get("api_costs_json"):
            try:
                costs = json.loads(run["api_costs_json"])
                if costs:
                    st.write(f"**Run {run['id']}** ({run['run_type']}, {run['status']})")
                    st.json(costs)
            except (json.JSONDecodeError, TypeError):
                pass


def main():
    st.set_page_config(
        page_title="SoyScope Dashboard",
        page_icon="🌱",
        layout="wide",
        initial_sidebar_state="expanded",
    )

    st.sidebar.title("SoyScope")
    st.sidebar.markdown("Industrial Soy Uses Tracker")

    page = st.sidebar.radio("Navigate", [
        "Overview",
        "Explorer",
        "Matrix View",
        "Trends",
        "Novel Uses",
        "Run History",
    ])

    if page == "Overview":
        page_overview()
    elif page == "Explorer":
        page_explorer()
    elif page == "Matrix View":
        page_matrix()
    elif page == "Trends":
        page_trends()
    elif page == "Novel Uses":
        page_novel()
    elif page == "Run History":
        page_run_history()


if __name__ == "__main__":
    main()
