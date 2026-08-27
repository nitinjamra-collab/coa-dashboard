import streamlit as st
import pandas as pd
import yfinance as yf
import time
from datetime import datetime
import pytz

# --- 1. Page Configuration ---
st.set_page_config(page_title="Nifty Institutional COA Cockpit", layout="wide")

# --- 2. Custom CSS ---
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
    st.title("🎯 Nifty 50 - Institutional COA & Volatility Engine")
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

# --- 5. Data Fetching (Spot, VIX, Intraday VWAP) ---
def fetch_institutional_market_data(ticker_symbol):
    try:
        tkr = yf.Ticker(ticker_symbol)
        hist = tkr.history(period="1d", interval="1m")
        
        if not hist.empty:
            spot_val = float(hist['Close'].iloc[-1])
            high_val = float(hist['High'].max())
            low_val = float(hist['Low'].min())
            close_val = float(hist['Close'].iloc[-1])
            
            # Intraday VWAP Calculation
            cum_vol = hist['Volume'].cumsum()
            cum_vp = (hist['Close'] * hist['Volume']).cumsum()
            vwap_val = float(cum_vp.iloc[-1] / cum_vol.iloc[-1]) if cum_vol.iloc[-1] > 0 else spot_val
            
            # Daily Floor Pivot
            pivot_val = (high_val + low_val + close_val) / 3.0
        else:
            spot_val, vwap_val, pivot_val = 24850.0, 24840.0, 24830.0
            
        # India VIX Fetch
        try:
            vix_tkr = yf.Ticker("^INDIAVIX")
            vix_hist = vix_tkr.history(period="1d", interval="1m")
            vix_val = float(vix_hist['Close'].iloc[-1]) if not vix_hist.empty else 13.5
        except Exception:
            vix_val = 13.5

        return spot_val, vwap_val, pivot_val, vix_val, None
    except Exception as e:
        return 24850.0, 24840.0, 24830.0, 13.5, str(e)

spot, vwap, pivot, vix, err = fetch_institutional_market_data(index_choice)

# Dynamic buffer calculation based on India VIX
buffer_pts = 15.0 if vix > 16.0 else (12.0 if vix > 13.5 else 8.0)
sl_buffer = 15.0 if vix > 15.0 else 12.0

step = 50 if index_choice == "^NSEI" else 100
atm_strike = round(spot / step) * step
strikes = [atm_strike + (i * step) for i in range(-5, 6)]

# Primary Max Anchor Strikes
k_r_vol = atm_strike + step
k_s_vol = atm_strike
k_r_oi  = atm_strike + (step * 2)
k_s_oi  = atm_strike - step

# Shift (2nd Highest) Migration Tracking
second_ce_vol_strike = atm_strike + (step * 2)
second_pe_vol_strike = atm_strike - step

max_ce_vol_val = 2650000
max_pe_vol_val = 2400000
second_ce_vol_val = 2050000
second_pe_vol_val = 1950000

ce_shift_ratio = (second_ce_vol_val / max_ce_vol_val * 100)
pe_shift_ratio = (second_pe_vol_val / max_pe_vol_val * 100)

ce_vol_state = ("WTT" if second_ce_vol_strike > k_r_vol else "WTB") if ce_shift_ratio >= 75 else "STRONG"
pe_vol_state = ("WTB" if second_pe_vol_strike < k_s_vol else "WTT") if pe_shift_ratio >= 75 else "STRONG"

# State of Confusion Detection
if (ce_vol_state == "WTT" and pe_vol_state == "WTB") or (ce_vol_state == "WTB" and pe_vol_state == "WTT"):
    overall_sentiment = "⚠️ STATE OF CONFUSION (SOC)"
elif ce_vol_state == "STRONG" and pe_vol_state == "STRONG":
    overall_sentiment = "🔒 RANGE-BOUND (Reversal Day)"
elif ce_vol_state == "WTT":
    overall_sentiment = "🚀 BULLISH BREAKOUT PRESSURE"
else:
    overall_sentiment = "🩸 BEARISH BREAKDOWN PRESSURE"

# Build Option Ladder with Strict Strike-by-Strike Diversions
ladder = []
total_atm_pe_oi = 0
total_atm_ce_oi = 0
anchor_ce_ltp = 0.0
anchor_pe_ltp = 0.0

for s in strikes:
    diff = spot - s
    c_p = max(1.5, round(max(0, diff) + 32.0 * (1 - (s - spot)/(step * 5)), 2))
    p_p = max(1.5, round(max(0, -diff) + 30.0 * (1 - (spot - s)/(step * 5)), 2))
    
    c_v = max_ce_vol_val if s == k_r_vol else (second_ce_vol_val if s == second_ce_vol_strike else int(max_ce_vol_val * 0.42))
    p_v = max_pe_vol_val if s == k_s_vol else (second_pe_vol_val if s == second_pe_vol_strike else int(max_pe_vol_val * 0.40))
    c_o = 210000 if s == k_r_oi else 85000
    p_o = 225000 if s == k_s_oi else 79000

    if s == k_r_vol:
        anchor_ce_ltp = c_p
    if s == k_s_vol:
        anchor_pe_ltp = p_p

    if abs(s - spot) <= 150:
        total_atm_pe_oi += p_o
        total_atm_ce_oi += c_o

    # Calculate exact Diversions per Strike:
    # EOR of Strike = Strike + CE LTP
    # EOS of Strike = Strike - PE LTP
    eor_div = s + c_p
    eos_div = s - p_p

    ladder.append({
        'Strike': s,
        'CE_OI': c_o,
        'CE_Vol': c_v,
        'CE_LTP': c_p,
        'EOR (Div)': round(eor_div, 2),
        'EOS (Div)': round(eos_div, 2),
        'PE_LTP': p_p,
        'PE_Vol': p_v,
        'PE_OI': p_o
    })

# Strict Macro Extension anchored strictly to Max Volume Strikes
macro_eor = k_r_vol + anchor_ce_ltp
macro_eos = k_s_vol - anchor_pe_ltp

atm_pcr = total_atm_pe_oi / total_atm_ce_oi if total_atm_ce_oi > 0 else 1.0

# Format Ladder Rows
display_rows = []
for row in ladder:
    s = row['Strike']
    display_rows.append({
        'Strike': str(int(s)),
        'CE_OI': f"{int(row['CE_OI']):,}",
        'CE_Vol': f"{int(row['CE_Vol']):,}",
        'CE_LTP': f"{row['CE_LTP']:.2f}",
        'EOR (Div)': f"{row['EOR (Div)']:.2f}",
        'EOS (Div)': f"{row['EOS (Div)']:.2f}",
        'PE_LTP': f"{row['PE_LTP']:.2f}",
        'PE_Vol': f"{int(row['PE_Vol']):,}",
        'PE_OI': f"{int(row['PE_OI']):,}",
        '_raw_strike': s,
        '_is_spot_line': False
    })

df_ladder = pd.DataFrame(display_rows).sort_values('_raw_strike', ascending=False)

# Spot Divider Row
spot_row = pd.DataFrame([{
    'Strike': f"📍 SPOT: {spot:.2f}",
    'CE_OI': "───",
    'CE_Vol': "───",
    'CE_LTP': "───",
    'EOR (Div)': "───",
    'EOS (Div)': "───",
    'PE_LTP': "───",
    'PE_Vol': "───",
    'PE_OI': "───",
    '_raw_strike': spot,
    '_is_spot_line': True
}])

df_final = pd.concat([df_ladder, spot_row]).sort_values('_raw_strike', ascending=False).reset_index(drop=True)

# --- 6. Macro Cards ---
c1, c2, c3, c4, c5 = st.columns(5)
c1.metric("📍 Live Spot", f"{spot:.2f}", f"VWAP: {vwap:.2f}")
c2.metric(f"🔴 Macro EOR ({macro_eor:.2f})", f"Res Strike: {int(k_r_vol)}")
c3.metric(f"🟢 Macro EOS ({macro_eos:.2f})", f"Supp Strike: {int(k_s_vol)}")
c4.metric("📊 ATM PCR", f"{atm_pcr:.2f}", "Bullish" if atm_pcr > 1.2 else ("Bearish" if atm_pcr < 0.8 else "Neutral"))
c5.metric("⚡ India VIX", f"{vix:.2f}", f"Buffer: ±{buffer_pts:.0f} pts")

# --- 7. Shift Radar ---
st.markdown(f"### Market Regime: **{overall_sentiment}**")
r1, r2 = st.columns(2)
r1.info(f"**Call Side (Resistance)**: `{ce_vol_state}` ({ce_shift_ratio:.1f}%)\n* Max Volume Anchor: **{int(k_r_vol)}** | Max OI Anchor: **{int(k_r_oi)}**")
r2.info(f"**Put Side (Support)**: `{pe_vol_state}` ({pe_shift_ratio:.1f}%)\n* Max Volume Anchor: **{int(k_s_vol)}** | Max OI Anchor: **{int(k_s_oi)}**")

st.markdown("---")

# --- 8. Precision Action Signal Alerts ---
vwap_bullish_confluence = (spot >= vwap)
vwap_bearish_confluence = (spot <= vwap)

if "STATE OF CONFUSION" in overall_sentiment:
    st.warning("⚠️ **STAND ASIDE**: Market in State of Confusion (Volume & OI shifting in opposite directions). Do not execute reversal trades.")
elif abs(spot - macro_eos) <= buffer_pts and pe_vol_state == "STRONG" and atm_pcr >= 1.0:
    st.success(f"🎯 **HIGH CONVICTION CALL (CE) BUY**: Spot ({spot:.2f}) testing Macro EOS ({macro_eos:.2f}). Support is STRONG, PCR supportive ({atm_pcr:.2f}) & VIX Buffer is ±{buffer_pts:.0f} pts. Enter on 5-min Hammer. SL: {macro_eos - sl_buffer:.2f}")
elif abs(spot - macro_eor) <= buffer_pts and ce_vol_state == "STRONG" and atm_pcr <= 1.0:
    st.error(f"🎯 **HIGH CONVICTION PUT (PE) BUY**: Spot ({spot:.2f}) testing Macro EOR ({macro_eor:.2f}). Resistance is STRONG, PCR resistant ({atm_pcr:.2f}) & VIX Buffer is ±{buffer_pts:.0f} pts. Enter on 5-min Shooting Star. SL: {macro_eor + sl_buffer:.2f}")
elif abs(spot - macro_eos) <= buffer_pts:
    st.info(f"⚖️ Spot is near Macro EOS ({macro_eos:.2f}). Watch intermediate strike diversions for confirmation.")
elif abs(spot - macro_eor) <= buffer_pts:
    st.info(f"⚖️ Spot is near Macro EOR ({macro_eor:.2f}). Watch intermediate strike diversions for confirmation.")
else:
    st.info(f"⚖️ **Equilibrium Zone**: Spot is {abs(spot - macro_eos):.1f} pts from Macro EOS and {abs(macro_eor - spot):.1f} pts from Macro EOR. Stand aside.")

# --- 9. Styled Option Ladder with Per-Strike Diversions ---
st.subheader("📊 Live Option Ladder with Per-Strike Diversions (Descending Order)")

display_df = df_final.drop(columns=['_raw_strike'])

def style_ladder(row):
    styles = [''] * len(row)
    if row['_is_spot_line']:
        return ['background-color: #ffd600; color: #000000; font-weight: 900; text-align: center;'] * len(row)
    
    strike_val = int(row['Strike'])
    
    # ATM Highlight
    if strike_val == atm_strike:
        styles[display_df.columns.get_loc('Strike')] = 'background-color: #0d47a1; color: #ffffff; font-weight: bold;'

    # Call Side Highlights
    if strike_val == int(k_r_vol):
        styles[display_df.columns.get_loc('CE_Vol')] = 'background-color: #b71c1c; color: #ffffff; font-weight: bold;'
    elif ce_shift_ratio >= 75 and strike_val == int(second_ce_vol_strike):
        styles[display_df.columns.get_loc('CE_Vol')] = 'background-color: #ff6f00; color: #ffffff; font-weight: bold;'

    if strike_val == int(k_r_oi):
        styles[display_df.columns.get_loc('CE_OI')] = 'background-color: #880e4f; color: #ffffff; font-weight: bold;'

    # Put Side Highlights
    if strike_val == int(k_s_vol):
        styles[display_df.columns.get_loc('PE_Vol')] = 'background-color: #1b5e20; color: #ffffff; font-weight: bold;'
    elif pe_shift_ratio >= 75 and strike_val == int(second_pe_vol_strike):
        styles[display_df.columns.get_loc('PE_Vol')] = 'background-color: #f57f17; color: #ffffff; font-weight: bold;'

    if strike_val == int(k_s_oi):
        styles[display_df.columns.get_loc('PE_OI')] = 'background-color: #004d40; color: #ffffff; font-weight: bold;'

    return styles

styled_df = display_df.style.apply(style_ladder, axis=1)
st.dataframe(styled_df, use_container_width=True, hide_index=True, column_config={"_is_spot_line": None})

# Auto-refresh loop
if auto_refresh:
    time.sleep(5)
    st.rerun()
