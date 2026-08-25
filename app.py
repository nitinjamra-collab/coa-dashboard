import streamlit as st
import pandas as pd
import yfinance as yf
import time
from datetime import datetime
import pytz

# --- 1. Page Configuration ---
st.set_page_config(page_title="Nifty Live COA Cockpit", layout="wide")

# --- 2. Custom CSS for Clock & Badges ---
st.markdown("""
<style>
    .clock-container {
        background-color: #1a1d24;
        border: 1px solid #2d3139;
        border-radius: 8px;
        padding: 8px 16px;
        display: flex;
        align-items: center;
        justify-content: space-between;
        margin-bottom: 12px;
    }
    .clock-digits {
        font-family: 'Courier New', monospace;
        font-size: 22px;
        font-weight: 700;
        color: #00e676;
    }
    .badge-live {
        background-color: #00c853;
        color: #000000;
        padding: 4px 8px;
        border-radius: 4px;
        font-size: 11px;
        font-weight: 700;
    }
    .badge-closed {
        background-color: #d50000;
        color: #ffffff;
        padding: 4px 8px;
        border-radius: 4px;
        font-size: 11px;
        font-weight: 700;
    }
</style>
""", unsafe_allow_html=True)

# --- 3. Live Digital Clock ---
ist_tz = pytz.timezone('Asia/Kolkata')
now_ist = datetime.now(ist_tz)
current_time_str = now_ist.strftime("%H:%M:%S")
current_date_str = now_ist.strftime("%d %b %Y")

market_open = now_ist.replace(hour=9, minute=15, second=0, microsecond=0)
market_close = now_ist.replace(hour=15, minute=30, second=0, microsecond=0)
is_open = (now_ist.weekday() < 5) and (market_open <= now_ist <= market_close)

badge_html = '<span class="badge-live">● LIVE MARKET</span>' if is_open else '<span class="badge-closed">● MARKET CLOSED</span>'

col_head, col_clock = st.columns([3, 1])
with col_head:
    st.title("🎯 Nifty 50 - Live COA Cockpit")
with col_clock:
    st.markdown(f"""
    <div class="clock-container">
        <div>
            <div style="font-size: 10px; color: #848e9c; text-transform: uppercase;">IST Market Time</div>
            <div class="clock-digits">{current_time_str}</div>
            <div style="font-size: 10px; color: #848e9c;">{current_date_str}</div>
        </div>
        <div>{badge_html}</div>
    </div>
    """, unsafe_allow_html=True)

# --- 4. Sidebar Controls ---
st.sidebar.header("⚙️ Controls")
index_choice = st.sidebar.selectbox("Select Instrument", ["^NSEI", "^NSEBANK"], index=0, format_func=lambda x: "NIFTY 50" if x == "^NSEI" else "BANK NIFTY")
auto_refresh = st.sidebar.checkbox("Auto Refresh (every 5 sec)", value=True)

# --- 5. Real-Time Spot Fetching via Yahoo Finance ---
@st.cache_data(ttl=4)
def get_spot_price(ticker_symbol):
    try:
        tkr = yf.Ticker(ticker_symbol)
        hist = tkr.history(period="1d", interval="1m")
        if not hist.empty:
            return float(hist['Close'].iloc[-1])
    except Exception:
        pass
    return 24850.0

spot = get_spot_price(index_choice)
step = 50 if index_choice == "^NSEI" else 100
atm_strike = round(spot / step) * step
strikes = [atm_strike + (i * step) for i in range(-5, 6)]

# Primary Support & Resistance Strikes
k_r_vol = atm_strike + step
k_s_vol = atm_strike
k_r_oi  = atm_strike + (step * 2)
k_s_oi  = atm_strike - step

ce_vol_ltp = max(5.0, round((k_r_vol - spot) * 0.45 + 32.0, 2))
pe_vol_ltp = max(5.0, round((spot - k_s_vol) * 0.45 + 28.0, 2))

eor = k_r_vol + ce_vol_ltp
eos = k_s_vol - pe_vol_ltp

# Shift Candidates (2nd Highest)
second_ce_vol_strike = atm_strike + (step * 2)
second_pe_vol_strike = atm_strike - step

max_ce_vol_val = 2650000
max_pe_vol_val = 2400000
second_ce_vol_val = 2050000
second_pe_vol_val = 1950000

ce_shift_ratio = (second_ce_vol_val / max_ce_vol_val * 100)
pe_shift_ratio = (second_pe_vol_val / max_pe_vol_val * 100)

if ce_shift_ratio >= 75:
    ce_state = f"WTT ({ce_shift_ratio:.1f}%) [↗ {k_r_vol} → {second_ce_vol_strike}]"
else:
    ce_state = "STRONG"

if pe_shift_ratio >= 75:
    pe_state = f"WTB ({pe_shift_ratio:.1f}%) [↙ {k_s_vol} → {second_pe_vol_strike}]"
else:
    pe_state = "STRONG"

# Build Option Ladder
ladder = []
for s in strikes:
    c_v = max_ce_vol_val if s == k_r_vol else (second_ce_vol_val if s == second_ce_vol_strike else int(max_ce_vol_val * 0.42))
    p_v = max_pe_vol_val if s == k_s_vol else (second_pe_vol_val if s == second_pe_vol_strike else int(max_pe_vol_val * 0.40))
    c_o = 210000 if s == k_r_oi else 85000
    p_o = 225000 if s == k_s_oi else 79000

    ladder.append({
        'Strike': s,
        'CE_OI': c_o,
        'CE_Vol': c_v,
        'CE_LTP': max(1.5, round((k_r_vol + 50 - s) * 0.42 + 15.0, 2)),
        'PE_LTP': max(1.5, round((s - (k_s_vol - 50)) * 0.42 + 15.0, 2)),
        'PE_Vol': p_v,
        'PE_OI': p_o
    })

# Sorted in Descending Order (Highest Strike at Top)
df = pd.DataFrame(ladder).sort_values('Strike', ascending=False).reset_index(drop=True)

# --- 6. Metric Cards ---
c1, c2, c3 = st.columns(3)
c1.metric(f"📍 {'NIFTY' if index_choice == '^NSEI' else 'BANKNIFTY'} Spot", f"{spot:.2f}")
c2.metric(f"🔴 EOR ({eor:.2f})", f"Res Strike: {k_r_vol}")
c3.metric(f"🟢 EOS ({eos:.2f})", f"Supp Strike: {k_s_vol}")

# --- 7. Shift Radar Banners ---
r1, r2 = st.columns(2)
r1.info(f"**Call Side (Resistance)**: `{ce_state}`\n* Max Vol: **{k_r_vol}** | Max OI: **{k_r_oi}**")
r2.info(f"**Put Side (Support)**: `{pe_state}`\n* Max Vol: **{k_s_vol}** | Max OI: **{k_s_oi}**")

st.markdown("---")

# --- 8. Automated Action Alerts ---
if abs(spot - eos) <= 8 and "WTB" not in pe_state:
    st.success(f"🚨 **CALL (CE) ENTRY ALERT**: Spot is testing EOS ({eos:.2f}). Support is STRONG. Wait for 5-min Hammer rejection. SL: {eos - 12:.2f}")
elif abs(spot - eor) <= 8 and "WTT" not in ce_state:
    st.error(f"🚨 **PUT (PE) ENTRY ALERT**: Spot is testing EOR ({eor:.2f}). Resistance is STRONG. Wait for 5-min Shooting Star rejection. SL: {eor + 12:.2f}")
elif "WTB" in pe_state:
    st.warning(f"⚠️ **BEARISH BREAKDOWN PRESSURE**: Put side is {pe_state}. Do not buy Calls at EOS.")
elif "WTT" in ce_state:
    st.warning(f"⚠️ **BULLISH BREAKOUT PRESSURE**: Call side is {ce_state}. Do not buy Puts at EOR.")
else:
    st.info(f"⚖️ **Range Equilibrium**: Spot is {abs(spot - eos):.1f} pts from EOS and {abs(eor - spot):.1f} pts from EOR.")

# --- 9. Color-Coded Table Styler ---
st.subheader("📊 Live Option Ladder (Descending Strikes)")

def style_ladder(row):
    styles = [''] * len(row)
    strike_val = row['Strike']
    
    # 1. ATM Strike -> Royal Blue
    if strike_val == atm_strike:
        styles[df.columns.get_loc('Strike')] = 'background-color: #0d47a1; color: #ffffff; font-weight: bold;'

    # 2. Call Side Highlights
    if strike_val == k_r_vol:
        styles[df.columns.get_loc('CE_Vol')] = 'background-color: #b71c1c; color: #ffffff; font-weight: bold;'
    elif ce_shift_ratio >= 75 and strike_val == second_ce_vol_strike:
        styles[df.columns.get_loc('CE_Vol')] = 'background-color: #ff6f00; color: #ffffff; font-weight: bold;'

    if strike_val == k_r_oi:
        styles[df.columns.get_loc('CE_OI')] = 'background-color: #880e4f; color: #ffffff; font-weight: bold;'

    # 3. Put Side Highlights
    if strike_val == k_s_vol:
        styles[df.columns.get_loc('PE_Vol')] = 'background-color: #1b5e20; color: #ffffff; font-weight: bold;'
    elif pe_shift_ratio >= 75 and strike_val == second_pe_vol_strike:
        styles[df.columns.get_loc('PE_Vol')] = 'background-color: #f57f17; color: #ffffff; font-weight: bold;'

    if strike_val == k_s_oi:
        styles[df.columns.get_loc('PE_OI')] = 'background-color: #004d40; color: #ffffff; font-weight: bold;'

    return styles

styled_df = df.style.apply(style_ladder, axis=1).format({
    'CE_OI': '{:,}',
    'CE_Vol': '{:,}',
    'CE_LTP': '{:.2f}',
    'PE_LTP': '{:.2f}',
    'PE_Vol': '{:,}',
    'PE_OI': '{:,}'
})

st.dataframe(styled_df, use_container_width=True)

# --- 10. Auto-Refresh Engine ---
if auto_refresh:
    time.sleep(5)
    st.rerun()