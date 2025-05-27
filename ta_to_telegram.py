import os
import requests
import pandas as pd
import pandas_ta as ta
import plotly.graph_objects as go
from datetime import datetime
from zoneinfo import ZoneInfo
from dotenv import load_dotenv
from io import BytesIO

from read_write_google_sheet import read_google_sheet

# --- Load environment variables ---
load_dotenv()
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("CHANNEL_ID")  # e.g., '@yourchannel'

# --- Time info ---
NPT = ZoneInfo("Asia/Kathmandu")
now_npt = datetime.now(NPT)
current_time_str = now_npt.strftime("%H:%M")
current_date = now_npt.strftime("%Y-%m-%d")

def send_plot_to_telegram(title, fig):
    """Send plot image to Telegram channel"""
    telegram_url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendPhoto"
    
    img_bytes = fig.to_image(format="png")
    buf = BytesIO(img_bytes)
    buf.seek(0)

    files = {'photo': buf}
    data = {
        "chat_id": TELEGRAM_CHAT_ID
    }

    try:
        response = requests.post(telegram_url, data=data, files=files)
        if response.ok:
            print(f"Sent: {title}")
        else:
            print(f"[ERROR] {title}: {response.text}")
    except Exception as e:
        print(f"[EXCEPTION] Failed to send {title}: {str(e)}")


def create_bar_chart(data, title, xlabel, color='skyblue'):
    """Create a horizontal Plotly bar chart optimized for Telegram"""
    if data.empty:
        print(f"No data available for {title}")
        return None

    data = data.head(10)[::-1]  # Top 10 and reverse for horizontal bars

    fig = go.Figure()
    fig.add_trace(go.Bar(
        y=data.index,
        x=data.values.round(2),
        orientation='h',
        marker_color=color,
        text=data.values.round(2),
        textposition='auto',
        texttemplate='%{text:.2f}'
    ))

    fig.update_layout(
        title=dict(text=title, x=0.5, xanchor='center', font=dict(size=24)),
        xaxis_title=xlabel,
        yaxis_title="Ticker",
        template="plotly_white",
        height=800,
        width=1000,
        margin=dict(l=120, r=40, t=80, b=40),  # Add space for ticker labels
        font=dict(size=16)
    )

    return fig


def create_table(data, title, columns):
    """Create a Plotly table"""
    if data.empty:
        print(f"No data available for {title}")
        return None
        
    data = data.head(10)  # Ensure only top 10
    fig = go.Figure(data=[go.Table(
        header=dict(
            values=columns,
            fill_color='lightgray',
            align='left'
        ),
        cells=dict(
            values=[data.index, data.values.round(2)],
            fill_color='white',
            align='left'
        )
    )])
    
    fig.update_layout(
        title=dict(text=title, x=0.5, xanchor='center'),
        height=400,
        margin=dict(l=20, r=20, t=60, b=20)
    )
    
    return fig

def main():
    # --- Send Title Message ---
    title_message = f"""
    ━━━━━━━━━━━━━━━━━━━━━━
    📢 *NEPSE TECHNICAL ALERTS*
    📅 *{current_date}*
    ━━━━━━━━━━━━━━━━━━━━━━
    """

    telegram_url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    payload = {
        "chat_id": TELEGRAM_CHAT_ID,
        "text": title_message,
        "parse_mode": "Markdown"
    }

    try:
        response = requests.post(telegram_url, data=payload)
        if response.ok:
            print("✅ Title message sent.")
        else:
            print(f"[ERROR] Title: {response.text}")
    except Exception as e:
        print(f"[EXCEPTION] Failed to send title: {str(e)}")


    # --- Load data ---
    sheet_id = "1n_QX2H3HEM1wYbEQmHV4fYBwfDzd19sBEiOv4MBXrFo"
    try:
        df = read_google_sheet(sheet_id)
        if df.empty:
            print("No data loaded from Google Sheet")
            return
            
        df['Date'] = pd.to_datetime(df['Date'])
        df['Close'] = pd.to_numeric(df['Close'], errors='coerce')
        df['Turnover'] = pd.to_numeric(df['Turnover'], errors='coerce')
        
        pivot = df.pivot_table(values='Close', index='Date', columns='Ticker')
        if pivot.empty:
            print("No valid pivot data created")
            return
    except Exception as e:
        print(f"Error loading data: {str(e)}")
        return

    # --- Daily Percentage Change ---
    daily_pct = pivot.pct_change(fill_method=None)
    latest_change = daily_pct.iloc[-1] * 100

    # --- Top Gainers & Losers ---
    gainers = latest_change.sort_values(ascending=False).dropna()
    losers = latest_change.sort_values().dropna()

    gainers_fig = create_bar_chart(gainers, "Top 10 Gainers (%)", "Daily % Change", 'green')
    if gainers_fig:
        send_plot_to_telegram("📈 Top 10 Gainers (%)", gainers_fig)

    losers_fig = create_bar_chart(losers, "Top 10 Losers (%)", "Daily % Change", 'red')
    if losers_fig:
        send_plot_to_telegram("📉 Top 10 Losers (%)", losers_fig)

    # --- RSI Analysis ---
    rsi_df = pivot.apply(lambda x: ta.rsi(x, length=14))
    latest_rsi = rsi_df.iloc[-1]
    
    overbought = latest_rsi[latest_rsi > 70].sort_values(ascending=False).dropna()
    oversold = latest_rsi[latest_rsi < 30].sort_values().dropna()

    overbought_fig = create_bar_chart(overbought, "Overbought Stocks (RSI > 70)", "RSI", 'orange')
    if overbought_fig:
        send_plot_to_telegram("📈 Overbought Stocks (RSI > 70)", overbought_fig)

    oversold_fig = create_bar_chart(oversold, "Oversold Stocks (RSI < 30)", "RSI", 'blue')
    if oversold_fig:
        send_plot_to_telegram("📉 Oversold Stocks (RSI < 30)", oversold_fig)

    # --- MA20 Crossovers ---
    ma20 = pivot.rolling(window=20).mean()
    prev_prices = pivot.iloc[-2]
    latest_prices = pivot.iloc[-1]
    prev_ma20 = ma20.iloc[-2]
    latest_ma20 = ma20.iloc[-1]

    buy_signals = (prev_prices < prev_ma20) & (latest_prices > latest_ma20)
    sell_signals = (prev_prices > prev_ma20) & (latest_prices < latest_ma20)

    buy_df = latest_prices[buy_signals].dropna()
    sell_df = latest_prices[sell_signals].dropna()

    buy_fig = create_table(buy_df, "Buy Signals (Price > MA20)", ["Ticker", "Price"])
    if buy_fig:
        send_plot_to_telegram("🟢 Buy Signals (Price > MA20)", buy_fig)

    sell_fig = create_table(sell_df, "Sell Signals (Price < MA20)", ["Ticker", "Price"])
    if sell_fig:
        send_plot_to_telegram("🔴 Sell Signals (Price < MA20)", sell_fig)

    # --- MA200 Relative % ---
    ma200 = pivot.rolling(window=200).mean()
    latest_ma200 = ma200.iloc[-1]
    rel_diff = ((latest_prices - latest_ma200) / latest_ma200 * 100).dropna()

    top10_above = rel_diff.sort_values(ascending=False).head(10)
    bottom10_below = rel_diff.sort_values().head(10)

    above_fig = create_bar_chart(top10_above, "Above 200-day MA (%) (Top 10)", "% Above", 'green')
    if above_fig:
        send_plot_to_telegram("Above 200-day MA (%) (Top 10)", above_fig)

    below_fig = create_bar_chart(bottom10_below, "Below 200-day MA (%) (Bottom 10)", "% Below", 'red')
    if below_fig:
        send_plot_to_telegram( "Below 200-day MA (%) (Bottom 10)", below_fig)

    # --- Turnover Analysis ---
    turnover_pivot = df.pivot_table(values='Turnover', index='Date', columns='Ticker')
    
    # 5-day Turnover
    turnover_5d = turnover_pivot.tail(5).sum()
    top10_turnover = turnover_5d.sort_values(ascending=False).dropna().head(10)

    turnover_fig = create_bar_chart(top10_turnover, "Top 10 Stocks by 5-Day Turnover", "Turnover", 'purple')
    if turnover_fig:
        send_plot_to_telegram("🔥 Top 10 Stocks by 5-Day Turnover", turnover_fig)

    # Turnover Spike vs MA50
    turnover_ma50 = turnover_pivot.rolling(window=50).mean()
    latest_turnover = turnover_pivot.iloc[-1]
    latest_ma50 = turnover_ma50.iloc[-1]
    rel_diff_turnover = ((latest_turnover - latest_ma50) / latest_ma50 * 100).dropna()
    top10_spikes = rel_diff_turnover.sort_values(ascending=False).head(10)

    spike_fig = create_bar_chart(top10_spikes, "Hot Stocks (volume vs Average 50-Day volume)", "% Spike", 'orange')
    if spike_fig:
        send_plot_to_telegram("📊 Hot Stocks (volume vs Average 50-Day volume)", spike_fig)
    
    disclaimer_text = (
        "⚠️ *Disclaimer:*\n"
        "The content shared here is for informational purposes only and should not be considered as financial advice. "
        "Always do your own research before making investment decisions. No one is liable for any losses incurred."
    )

    telegram_url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    payload = {
        "chat_id": TELEGRAM_CHAT_ID,
        "text": disclaimer_text,
        "parse_mode": "Markdown"
    }

    try:
        response = requests.post(telegram_url, data=payload)
        if response.ok:
            print("✅ Disclaimer message sent.")
        else:
            print(f"[ERROR] Disclaimer: {response.text}")
    except Exception as e:
        print(f"[EXCEPTION] Failed to send disclaimer: {str(e)}")


if __name__ == "__main__":
    main()