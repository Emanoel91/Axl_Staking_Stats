import streamlit as st
import pandas as pd
import snowflake.connector
import plotly.graph_objects as go

# --- Page Config: Tab Title & Icon -------------------------------------------------------------------------------------
st.set_page_config(
    page_title="AXL Staking Stats",
    page_icon="https://pbs.twimg.com/profile_images/1877235283755778048/4nlylmxm_400x400.jpg",
    layout="wide"
)

# --- Title with Logo ---------------------------------------------------------------------------------------------------
st.markdown(
    """
    <div style="display: flex; align-items: center; gap: 15px;">
        <img src="https://axelarscan.io/logos/chains/axelarnet.svg" alt="Axelar Logo" style="width:60px; height:60px;">
        <h1 style="margin: 0;">AXL Staking Stats</h1>
    </div>
    """,
    unsafe_allow_html=True
)

# --- Page Builder ----------------------------------------------------------------------------------------------------------
st.markdown(
    """
    <div style="margin-top: 20px; margin-bottom: 20px; font-size: 16px;">
        <div style="display: flex; align-items: center; gap: 10px;">
            <img src="https://pbs.twimg.com/profile_images/1841479747332608000/bindDGZQ_400x400.jpg" alt="Eman Raz" style="width:25px; height:25px; border-radius: 50%;">
            <span>Built by: <a href="https://x.com/0xeman_raz" target="_blank">Eman Raz</a></span>
        </div>
    </div>
    """,
    unsafe_allow_html=True
)

st.info("📊Charts initially display data for a default time range. Select a custom range to view results for your desired period.")
st.info("⏳On-chain data retrieval may take a few moments. Please wait while the results load.")

# --- Snowflake Connection --------------------------------------------------------------------------------------------------
conn = snowflake.connector.connect(
    user=st.secrets["snowflake"]["user"],
    password=st.secrets["snowflake"]["password"],
    account=st.secrets["snowflake"]["account"],
    warehouse="SNOWFLAKE_LEARNING_WH",
    database="AXELAR",
    schema="PUBLIC"
)

# --- Time Frame & Period Selection ---
start_date = st.date_input("Start Date", value=pd.to_datetime("2022-08-01"))
end_date = st.date_input("End Date", value=pd.to_datetime("2025-06-30"))

# --- Query Functions -------------------------------------------------------------------------------------------------------------------------
# --- Row 1: Share of Staked Tokens -----------
@st.cache_data
def load_share_of_staked_tokens(start_date, end_date):
    query = f"""
        WITH delegate AS (
            SELECT
                TRUNC(block_timestamp, 'month') AS monthly,
                SUM(amount / POW(10, 6)) AS delegate_amount,
                SUM(SUM(amount / POW(10, 6))) OVER (ORDER BY TRUNC(block_timestamp, 'month') ASC) AS cumulative_delegate_amount
            FROM axelar.gov.fact_staking
            WHERE action = 'delegate'
              AND TX_SUCCEEDED = 'TRUE'
              AND block_timestamp::date >= '{start_date}'
              AND block_timestamp::date <= '{end_date}'
            GROUP BY 1
        ),
        undelegate AS (
            SELECT
                TRUNC(block_timestamp, 'month') AS monthly,
                SUM(amount / POW(10, 6)) * -1 AS undelegate_amount,
                SUM(SUM(amount / POW(10, 6)) * -1) OVER (ORDER BY TRUNC(block_timestamp, 'month') ASC) AS cumulative_undelegate_amount
            FROM axelar.gov.fact_staking
            WHERE action = 'undelegate'
              AND TX_SUCCEEDED = 'TRUE'
              AND block_timestamp::date >= '{start_date}'
              AND block_timestamp::date <= '{end_date}'
            GROUP BY 1
        )
        SELECT 
            a.monthly,
            (cumulative_delegate_amount + cumulative_undelegate_amount) / 1008585017 * 100 AS share_of_staked_tokens
        FROM delegate a
        LEFT JOIN undelegate b ON a.monthly = b.monthly
        ORDER BY a.monthly DESC
        LIMIT 1
    """
    df = pd.read_sql(query, conn)
    if not df.empty:
        return round(df["SHARE_OF_STAKED_TOKENS"].iloc[0], 2)
    else:
        return None

# --- Row2: Monthly Share of Staked Tokens from Supply -----------------------------------------------------------
@st.cache_data
def load_monthly_share_data(start_date, end_date):
    query = f"""
        WITH delegate AS (
            SELECT TRUNC(block_timestamp,'month') AS monthly, 
                   SUM(amount/POW(10,6)) AS delegate_amount,
                   SUM(SUM(amount/POW(10,6))) OVER (ORDER BY TRUNC(block_timestamp,'month') ASC) AS cumulative_delegate_amount
            FROM axelar.gov.fact_staking
            WHERE action = 'delegate'
              AND TX_SUCCEEDED = 'TRUE'
              AND block_timestamp::date >= '{start_date}'
              AND block_timestamp::date <= '{end_date}'
            GROUP BY 1
        ),
        undelegate AS (
            SELECT TRUNC(block_timestamp,'month') AS monthly, 
                   SUM(amount/POW(10,6)) * -1 AS undelegate_amount,
                   SUM(SUM(amount/POW(10,6)) * -1) OVER (ORDER BY TRUNC(block_timestamp,'month') ASC) AS cumulative_undelegate_amount
            FROM axelar.gov.fact_staking
            WHERE action = 'undelegate'
              AND TX_SUCCEEDED = 'TRUE'
              AND block_timestamp::date >= '{start_date}'
              AND block_timestamp::date <= '{end_date}'
            GROUP BY 1
        )
        SELECT a.monthly, 
               1181742149 AS supply,
               (cumulative_delegate_amount + cumulative_undelegate_amount) / 1181742149 * 100 AS share_of_staked_tokens
        FROM delegate a
        LEFT JOIN undelegate b ON a.monthly = b.monthly 
        WHERE a.monthly >= '{start_date}'
        ORDER BY a.monthly ASC
    """
    return pd.read_sql(query, conn)

# --- Load Data ------------------------------------------------------------------------------------------------------------------------------------
share_of_staked_tokens = load_share_of_staked_tokens(start_date, end_date)
monthly_data = load_monthly_share_data(start_date, end_date)

# --- Row 1: KPI for Share of Staked Tokens ---
if share_of_staked_tokens is not None:
    st.metric("Share of Staked Tokens From Supply", f"{share_of_staked_tokens:.2f}%")
else:
    st.warning("No data available for the selected period.")

# --- Row2: Plot Column-Line Chart ---------------------------------------------------------------------------------
if not monthly_data.empty:
    fig = go.Figure()

    # Bar chart for supply
    fig.add_trace(
        go.Bar(
            x=monthly_data["MONTHLY"],
            y=monthly_data["SUPPLY"],
            name="Supply",
            marker_color="#0099ff",
            yaxis="y1"
        )
    )

    # Line chart for Share of Staked Tokens
    fig.add_trace(
        go.Scatter(
            x=monthly_data["MONTHLY"],
            y=monthly_data["SHARE_OF_STAKED_TOKENS"],
            name="Share of Staked Tokens (%)",
            mode="lines+markers",
            line=dict(color="#fc0060", width=3),
            yaxis="y2"
        )
    )

    # Layout with two Y axes
    fig.update_layout(
        title="Monthly Share of Staked Tokens from Supply",
        xaxis=dict(title="Month"),
        yaxis=dict(
            title="Supply",
            titlefont=dict(color="#0099ff"),
            tickfont=dict(color="#0099ff")
        ),
        yaxis2=dict(
            title="Share of Staked Tokens (%)",
            titlefont=dict(color="#fc0060"),
            tickfont=dict(color="#fc0060"),
            overlaying="y",
            side="right"
        ),
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
        barmode="group",
        template="plotly_white",
        height=500
    )

    st.plotly_chart(fig, use_container_width=True)
else:
    st.warning("No data available for the selected period.")

# --- Reference and Rebuild Info ---------------------------------------------------------------------------------------------------------------------
st.markdown(
    """
    <div style="margin-top: 20px; margin-bottom: 20px; font-size: 16px;">
        <div style="display: flex; align-items: center; gap: 10px; margin-bottom: 10px;">
            <img src="https://cdn-icons-png.flaticon.com/512/3178/3178287.png" alt="Reference" style="width:20px; height:20px;">
            <span>Dashboard Reference: <a href="https://flipsidecrypto.xyz/hess/axl-staking-stats-X1tELe" target="_blank">https://flipsidecrypto.xyz/hess/axl-staking-stats-X1tELe/</a></span>
        </div>
        <div style="display: flex; align-items: center; gap: 10px;">
            <img src="https://pbs.twimg.com/profile_images/1856738793325268992/OouKI10c_400x400.jpg" alt="Flipside" style="width:25px; height:25px; border-radius: 50%;">
            <span>Data Powered by: <a href="https://flipsidecrypto.xyz/home/" target="_blank">Flipside</a></span>
        </div>
    </div>
    """,
    unsafe_allow_html=True
)

# --- Links with Logos ---------------------------------------------------------------------------------------
st.markdown(
    """
    <div style="font-size: 16px;">
        <div style="display: flex; align-items: center; gap: 10px;">
            <img src="https://axelarscan.io/logos/logo.png" alt="Axelar" style="width:20px; height:20px;">
            <a href="https://www.axelar.network/" target="_blank">https://www.axelar.network/</a>
        </div>
        <div style="display: flex; align-items: center; gap: 10px;">
            <img src="https://cdn-icons-png.flaticon.com/512/5968/5968958.png" alt="X" style="width:20px; height:20px;">
            <a href="https://x.com/axelar" target="_blank">https://x.com/axelar</a>
        </div>
    </div>
    """,
    unsafe_allow_html=True
)
