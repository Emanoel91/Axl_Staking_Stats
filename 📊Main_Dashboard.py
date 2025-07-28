import streamlit as st
import pandas as pd
import snowflake.connector
import plotly.express as px
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


# --- Info Box --------------------------------------------------------------------------------------------------------------
#st.markdown(
#    """
#    <div style="background-color: #c0ced9; padding: 15px; border-radius: 10px; border: 1px solid #c0ced9;">
#        The AXL token is the native cryptocurrency of the Axelar network, a decentralized blockchain interoperability platform designed to 
#connect multiple blockchains, enabling seamless cross-chain communication and asset transfers. Staking AXL tokens involves locking 
#them in the Axelar network to support its operations and security, in return for earning rewards.
#    </div>
#    """,
#    unsafe_allow_html=True
#)

st.info(
    "📊Charts initially display data for a default time range. Select a custom range to view results for your desired period."

)

st.info(
    "⏳On-chain data retrieval may take a few moments. Please wait while the results load."
)

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

# --- Query Functions ---------------------------------------------------------------------------------------
# --- Row 1: Total Amounts Staked, Unstaked, and Net Staked ---

@st.cache_data
def load_staking_totals(start_date, end_date):
    query = f"""
        WITH delegate AS (
            SELECT
                TRUNC(block_timestamp, 'week') AS date,
                SUM(amount / POW(10, 6)) AS amount_staked
            FROM axelar.gov.fact_staking
            WHERE action = 'delegate'
              AND TX_SUCCEEDED = 'TRUE'
              AND block_timestamp::date >= '{start_date}'
              AND block_timestamp::date <= '{end_date}'
            GROUP BY 1
        ),
        undelegate AS (
            SELECT
                TRUNC(block_timestamp, 'week') AS date,
                SUM(amount / POW(10, 6)) AS amount_unstaked
            FROM axelar.gov.fact_staking
            WHERE action = 'undelegate'
              AND TX_SUCCEEDED = 'TRUE'
              AND block_timestamp::date >= '{start_date}'
              AND block_timestamp::date <= '{end_date}'
            GROUP BY 1
        ),
        final AS (
            SELECT a.date,
                   amount_staked,
                   amount_unstaked,
                   amount_staked - amount_unstaked AS net
            FROM delegate a
            LEFT OUTER JOIN undelegate b
              ON a.date = b.date
        )
        SELECT
            ROUND(SUM(amount_staked), 2) AS total_staked,
            ROUND(SUM(amount_unstaked), 2) AS total_unstaked,
            ROUND(SUM(net), 2) AS total_net_staked
        FROM final
    """
    return pd.read_sql(query, conn).iloc[0]


# --- Load Data ----------------------------------------------------------------------------------------
staking_totals = load_staking_totals(start_date, end_date)

# ------------------------------------------------------------------------------------------------------

# --- Row 1: Metrics ---
staking_totals.index = staking_totals.index.str.lower() 

col1, col2, col3 = st.columns(3)
col1.metric("Total Amount Staked", f"{staking_totals['total_staked']:,} AXL")
col2.metric("Total Amount UnStaked", f"{staking_totals['total_unstaked']:,} AXL")
col3.metric("Total Amount Net Staked", f"{staking_totals['total_net_staked']:,} AXL")



# --- Reference and Rebuild Info --------------------------------------------------------------------------------------
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


