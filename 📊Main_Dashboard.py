import streamlit as st
import pandas as pd
import snowflake.connector
import plotly.graph_objects as go

# --- Page Config ------------------------------------------------------------------------------------------------------
st.set_page_config(
    page_title="AXL Staking Stats",
    page_icon="https://pbs.twimg.com/profile_images/1877235283755778048/4nlylmxm_400x400.jpg",
    layout="wide"
)

# --- Title with Logo -----------------------------------------------------------------------------------------------------
st.markdown(
    """
    <div style="display: flex; align-items: center; gap: 15px;">
        <img src="https://axelarscan.io/logos/chains/axelarnet.svg" alt="Axelar Logo" style="width:60px; height:60px;">
        <h1 style="margin: 0;">AXL Staking Stats</h1>
    </div>
    """,
    unsafe_allow_html=True
)

# --- Builder Info ---------------------------------------------------------------------------------------------------------
st.markdown(
    """
    <div style="margin-top: 20px; margin-bottom: 20px; font-size: 16px;">
        <div style="display: flex; align-items: center; gap: 10px;">
            <img src="https://pbs.twimg.com/profile_images/1841479747332608000/bindDGZQ_400x400.jpg" style="width:25px; height:25px; border-radius: 50%;">
            <span>Built by: <a href="https://x.com/0xeman_raz" target="_blank">Eman Raz</a></span>
        </div>
    </div>
    """,
    unsafe_allow_html=True
)

st.info("📊Charts initially display data for a default time range. Select a custom range to view results for your desired period.")
st.info("⏳On-chain data retrieval may take a few moments. Please wait while the results load.")

# --- Snowflake Connection ----------------------------------------------------------------------------------------
conn = snowflake.connector.connect(
    user=st.secrets["snowflake"]["user"],
    password=st.secrets["snowflake"]["password"],
    account=st.secrets["snowflake"]["account"],
    warehouse="SNOWFLAKE_LEARNING_WH",
    database="AXELAR",
    schema="PUBLIC"
)

# --- Date Inputs ---------------------------------------------------------------------------------------------------
start_date = st.date_input("Start Date", value=pd.to_datetime("2022-08-01"))
end_date = st.date_input("End Date", value=pd.to_datetime("2025-06-30"))

# --- Query Functions -------------------------------------------------------------------------------------------------------------------------------------
@st.cache_data
def load_share_of_staked_tokens(start_date, end_date):
    query = f"""
        WITH delegate AS (
            SELECT
                TRUNC(block_timestamp,'month') AS monthly, 
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
            SELECT
                TRUNC(block_timestamp,'month') AS monthly, 
                SUM(amount/POW(10,6)) * -1 AS undelegate_amount,
                SUM(SUM(amount/POW(10,6)) * -1) OVER (ORDER BY TRUNC(block_timestamp,'month') ASC) AS cumulative_undelegate_amount
            FROM axelar.gov.fact_staking
            WHERE action = 'undelegate'
              AND TX_SUCCEEDED = 'TRUE'
              AND block_timestamp::date >= '{start_date}'
              AND block_timestamp::date <= '{end_date}'
            GROUP BY 1
        )
        SELECT 
            (cumulative_delegate_amount + cumulative_undelegate_amount) / 1008585017 * 100 AS share_of_staked_tokens
        FROM delegate a
        LEFT OUTER JOIN undelegate b
          ON a.monthly = b.monthly
        WHERE a.monthly >= '{start_date}'
        ORDER BY a.monthly DESC
        LIMIT 1
    """
    df = pd.read_sql(query, conn)
    if not df.empty:
        return round(df["SHARE_OF_STAKED_TOKENS"].iloc[0], 2)
    else:
        return None

# --- Row2: Monthly Share Chart ---
@st.cache_data
def load_monthly_share_data(start_date, end_date):
    query = f"""
        WITH delegate AS (
            SELECT 
                TRUNC(block_timestamp,'month') AS monthly, 
                SUM(amount/POW(10,6)) AS delegate_amount,
                SUM(SUM(amount/POW(10,6))) OVER (ORDER BY TRUNC(block_timestamp,'month') ASC) AS cumulative_delegate_amount,
                COUNT(DISTINCT tx_id) AS delegate_tx,
                COUNT(DISTINCT DELEGATOR_ADDRESS) AS delegate_user,
                AVG(amount/POW(10,6)) AS avg_delegate_amount 
            FROM axelar.gov.fact_staking
            WHERE action = 'delegate'
              AND block_timestamp::date >= '{start_date}'
              AND block_timestamp::date <= '{end_date}'
            GROUP BY 1
        ),
        undelegate AS (
            SELECT 
                TRUNC(block_timestamp,'month') AS monthly, 
                SUM(amount/POW(10,6)) * -1 AS undelegate_amount,
                SUM(SUM(amount/POW(10,6)) * -1) OVER (ORDER BY TRUNC(block_timestamp,'month') ASC) AS cumulative_undelegate_amount,
                COUNT(DISTINCT tx_id) * -1 AS undelegate_tx,
                COUNT(DISTINCT DELEGATOR_ADDRESS) * -1 AS undelegate_user,
                AVG(amount/POW(10,6)) AS avg_undelegate_amount 
            FROM axelar.gov.fact_staking
            WHERE action = 'undelegate'
              AND block_timestamp::date >= '{start_date}'
              AND block_timestamp::date <= '{end_date}'
            GROUP BY 1
        )
        SELECT 
            a.monthly, 
            delegate_amount,
            undelegate_amount,
            cumulative_delegate_amount,
            cumulative_undelegate_amount,
            delegate_tx,
            undelegate_tx,
            delegate_user,
            undelegate_user,
            1008585017 AS supply,
            cumulative_delegate_amount + cumulative_undelegate_amount AS net,
            (cumulative_delegate_amount + cumulative_undelegate_amount) / 1008585017 * 100 AS "Share of Staked Tokens From Supply"
        FROM delegate a
        LEFT OUTER JOIN undelegate b ON a.monthly = b.monthly 
        WHERE a.monthly >= '{start_date}' AND a.monthly <= '{end_date}'
        ORDER BY 1 ASC
    """
    return pd.read_sql(query, conn)

# --- Row3: All-Time Delegate KPIs ---
@st.cache_data
def load_delegate_kpis(start_date, end_date):
    query = f"""
        SELECT 
            ROUND(SUM(amount/POW(10,6)), 2) AS amount,
            COUNT(DISTINCT tx_id) AS txns,
            COUNT(DISTINCT DELEGATOR_ADDRESS) AS user,
            ROUND(AVG(amount/POW(10,6)), 2) AS avg_amount
        FROM axelar.gov.fact_staking
        WHERE action = 'delegate'
          AND block_timestamp::date >= '{start_date}'
          AND block_timestamp::date <= '{end_date}'
    """
    return pd.read_sql(query, conn)

# --- Row4: Current Net Staked --------
@st.cache_data
def load_current_net_staked(start_date, end_date):
    query = f"""
        WITH delegate AS (
            SELECT 
                TRUNC(block_timestamp,'month') AS monthly, 
                SUM(amount/POW(10,6)) AS delegate_amount,
                SUM(SUM(amount/POW(10,6))) OVER (ORDER BY TRUNC(block_timestamp,'month') ASC) AS cumulative_delegate_amount
            FROM axelar.gov.fact_staking
            WHERE action = 'delegate'
              AND block_timestamp::date >= '{start_date}'
              AND block_timestamp::date <= '{end_date}'
            GROUP BY 1
        ),
        undelegate AS (
            SELECT 
                TRUNC(block_timestamp,'month') AS monthly, 
                SUM(amount/POW(10,6)) * -1 AS undelegate_amount,
                SUM(SUM(amount/POW(10,6)) * -1) OVER (ORDER BY TRUNC(block_timestamp,'month') ASC) AS cumulative_undelegate_amount
            FROM axelar.gov.fact_staking
            WHERE action = 'undelegate'
              AND block_timestamp::date >= '{start_date}'
              AND block_timestamp::date <= '{end_date}'
            GROUP BY 1
        )
        SELECT 
            ROUND((cumulative_delegate_amount + cumulative_undelegate_amount), 1) AS Net
        FROM delegate a 
        LEFT JOIN undelegate b ON a.monthly = b.monthly
        WHERE a.monthly >= '{start_date}'
        ORDER BY a.monthly DESC
        LIMIT 1
    """
    df = pd.read_sql(query, conn)
    if not df.empty:
        return df["NET"].iloc[0]
    else:
        return None

# --- Row5: Monthly Delegation Data --------------
@st.cache_data
def load_monthly_delegation_data(start_date, end_date):
    query = f"""
        WITH delegate AS (
            SELECT 
                TRUNC(block_timestamp,'month') AS monthly, 
                SUM(amount/POW(10,6)) AS delegate_amount,
                SUM(SUM(amount/POW(10,6))) OVER (ORDER BY TRUNC(block_timestamp,'month') ASC) AS cumulative_delegate_amount,
                COUNT(DISTINCT tx_id) AS delegate_tx,
                COUNT(DISTINCT DELEGATOR_ADDRESS) AS delegate_user,
                AVG(amount/POW(10,6)) AS avg_delegate_amount
            FROM axelar.gov.fact_staking
            WHERE action = 'delegate'
              AND block_timestamp::date >= '{start_date}'
              AND block_timestamp::date <= '{end_date}'
            GROUP BY 1
        ),
        undelegate AS (
            SELECT 
                TRUNC(block_timestamp,'month') AS monthly, 
                SUM(amount/POW(10,6)) * -1 AS undelegate_amount,
                SUM(SUM(amount/POW(10,6)) * -1) OVER (ORDER BY TRUNC(block_timestamp,'month') ASC) AS cumulative_undelegate_amount,
                COUNT(DISTINCT tx_id) * -1 AS undelegate_tx,
                COUNT(DISTINCT DELEGATOR_ADDRESS) * -1 AS undelegate_user,
                AVG(amount/POW(10,6)) AS avg_undelegate_amount
            FROM axelar.gov.fact_staking
            WHERE action = 'undelegate'
              AND block_timestamp::date >= '{start_date}'
              AND block_timestamp::date <= '{end_date}'
            GROUP BY 1
        )
        SELECT 
            a.monthly,
            ROUND(delegate_amount,1) AS "Delegate Amount",
            ROUND(undelegate_amount,1) AS "Undelegate Amount",
            cumulative_delegate_amount,
            cumulative_undelegate_amount,
            delegate_tx AS "Delegate Txns",
            undelegate_tx AS "Undelegate Txns",
            delegate_user AS "Delegators",
            undelegate_user AS "Undelegators",
            ROUND((cumulative_delegate_amount + cumulative_undelegate_amount),1) AS "Net Delegated Amount"
        FROM delegate a 
        LEFT JOIN undelegate b ON a.monthly = b.monthly 
        WHERE a.monthly >= '{start_date}'
        ORDER BY a.monthly ASC
    """
    df = pd.read_sql(query, conn)
    if not df.empty:
        df['monthly'] = pd.to_datetime(df['MONTHLY'])
    return df
    
# --- Load Data -----------------------------------------------------------------------------------------------------------
share_of_staked_tokens = load_share_of_staked_tokens(start_date, end_date)
monthly_share_df = load_monthly_share_data(start_date, end_date)
delegate_kpis_df = load_delegate_kpis(start_date, end_date)
current_net_staked = load_current_net_staked(start_date, end_date)
monthly_data = load_monthly_delegation_data(start_date, end_date)

# --- Row 1: KPI ------------------------------------------------------------------------------------------------------------
st.markdown(
    """
    <div style="background-color:#fc0060; padding:1px; border-radius:10px;">
        <h2 style="color:#000000; text-align:center;">Share of Staked Tokens from Supply</h2>
    </div>
    """,
    unsafe_allow_html=True
)
if share_of_staked_tokens is not None:
    st.metric("Share of Staked Tokens From Supply", f"{share_of_staked_tokens:.2f}%")
else:
    st.warning("No data available for the selected period.")

# --- Row 2: Monthly Share of Staked Tokens from Supply Chart -------------------------
if not monthly_share_df.empty:
    fig = go.Figure()
    fig.add_trace(go.Scatter(
        x=monthly_share_df['MONTHLY'],
        y=monthly_share_df['Share of Staked Tokens From Supply'],
        mode='markers+lines',
        marker=dict(size=8, color='blue'),
        line=dict(color='blue', width=2)
    ))
    fig.update_layout(
        title="Monthly Share of Staked Tokens from Supply",
        xaxis_title="Month",
        yaxis_title="Share (%)",
        hovermode='x unified',
        template='plotly_white',
        height=500
    )
    st.plotly_chart(fig, use_container_width=True)
else:
    st.warning("No monthly data available for the selected period.")

# --- Row 3: KPIs -------------------------------
st.markdown(
    """
    <div style="background-color:#fc0060; padding:1px; border-radius:10px;">
        <h2 style="color:#000000; text-align:center;">Overview</h2>
    </div>
    """,
    unsafe_allow_html=True
)

if not delegate_kpis_df.empty:
    amount = delegate_kpis_df["AMOUNT"].iloc[0]
    avg_amount = delegate_kpis_df["AVG_AMOUNT"].iloc[0]
    txns = delegate_kpis_df["TXNS"].iloc[0]
    user = delegate_kpis_df["USER"].iloc[0]

    col1, col2, col3, col4 = st.columns(4)

    with col1:
        st.metric(label="Total Delegated Amount (All Time)", value=f"{amount:,.2f} AXL")
        st.caption("(Exclude Undelegate Amount)")

    with col2:
        st.metric(label="Average Delegate Amount", value=f"{avg_amount:,.2f} AXL")

    with col3:
        st.metric(label="Total Delegate Transactions", value=f"{txns:,}")
        st.caption("(All Time)")

    with col4:
        st.metric(label="Total Delegators", value=f"{user:,}")
        st.caption("Cumulative count of all users who have ever delegated AXL")
else:
    st.warning("No delegate KPI data available for the selected period.")

# --- Row 4: Single KPI -----------------------------
if current_net_staked is not None:
    st.markdown(
        f"""
        <div style="text-align: center; padding: 40px; background-color: #f8f9fa; border-radius: 15px; margin: 20px 0;">
            <h2 style="font-size: 32px; margin-bottom: 10px;">Current Net Staked</h2>
            <p style="font-size: 48px; font-weight: bold; color: #2e7d32;">{current_net_staked:,.1f} AXL</p>
        </div>
        """,
        unsafe_allow_html=True
    )
else:
    st.warning("No data available for Current Net Staked in the selected period.")
    
if not monthly_data.empty:
# --- Row 5: Combined Delegate & Undelegate + Net --------------------------
    fig1 = go.Figure()
    fig1.add_bar(x=monthly_data['monthly'], y=monthly_data['Delegate Amount'], name='Delegate Amount', marker_color='green', yaxis='y1')
    fig1.add_bar(x=monthly_data['monthly'], y=monthly_data['Undelegate Amount'], name='Undelegate Amount', marker_color='red', yaxis='y1')
    fig1.add_trace(go.Scatter(x=monthly_data['monthly'], y=monthly_data['Net Delegated Amount'],
                              name='Net Delegated Amount', mode='lines+markers', line=dict(color='blue', width=2), yaxis='y2'))
    fig1.update_layout(
        title="Monthly Delegate and Undelegate Amount + Net (AXL)",
        barmode='group',
        yaxis=dict(title="$AXL", side='left'),
        yaxis2=dict(title="$AXL", overlaying='y', side='right'),
        legend=dict(x=0, y=1.1, orientation='h'),
        height=500
    )
    st.plotly_chart(fig1, use_container_width=True)

    # --- Row 6: Two Side-by-Side Charts ---------------
    col1, col2 = st.columns(2)

    # Monthly Number of Users
    with col1:
        fig2 = go.Figure()
        fig2.add_bar(x=monthly_data['monthly'], y=monthly_data['Delegators'], name='Delegators', marker_color='green')
        fig2.add_bar(x=monthly_data['monthly'], y=monthly_data['Undelegators'], name='Undelegators', marker_color='red')
        fig2.update_layout(
            title="Monthly Number of Users",
            barmode='group',
            yaxis_title="Number of Users",
            legend=dict(x=0, y=1.1, orientation='h'),
            height=400
        )
        st.plotly_chart(fig2, use_container_width=True)

    # Monthly Number of Transactions
    with col2:
        fig3 = go.Figure()
        fig3.add_bar(x=monthly_data['monthly'], y=monthly_data['Delegate Txns'], name='Delegate Txns', marker_color='green')
        fig3.add_bar(x=monthly_data['monthly'], y=monthly_data['Undelegate Txns'], name='Undelegate Txns', marker_color='red')
        fig3.update_layout(
            title="Monthly Number of Transactions",
            barmode='group',
            yaxis_title="Number of Transactions",
            legend=dict(x=0, y=1.1, orientation='h'),
            height=400
        )
        st.plotly_chart(fig3, use_container_width=True)
else:
    st.warning("No data available for Monthly Delegation details in the selected period.")

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

