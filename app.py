import streamlit as st
import pandas as pd
import os
import time
from datetime import datetime, timedelta
from kiteconnect import KiteConnect

# ---------------- STATIC CONFIG ----------------
API_KEY    = "cr7csx6ic2slbuxl"
API_SECRET = "9f2wb92rvoz0w7p4lfhqnkr15l1z5pqd"
OUTPUT_FOLDER = "downloaded_data"

st.title("📈 Zerodha Kite Data Downloader")


# ---------------- STEP 1: LOGIN URL ----------------
kite = KiteConnect(api_key=API_KEY)
login_url = kite.login_url()

st.header("Step 1 — Login to Kite")
st.markdown(f"[👉 CLICK HERE TO LOGIN]({login_url})")

request_token = st.text_input("Paste REQUEST_TOKEN after logging in:")


if st.button("Proceed"):
    try:
        session = kite.generate_session(request_token, api_secret=API_SECRET)
        kite.set_access_token(session["access_token"])

        st.session_state["logged_in"] = True
        st.session_state["kite"] = kite

        st.success("Logged in successfully!")
    except Exception as e:
        st.error(f"Login failed: {e}")


# --------------- TOKEN SEARCH FUNCTION (Stock + Index) ----------------
def get_token(symbol, kite):
    inst = kite.instruments()
    df = pd.DataFrame(inst)

    # Normalise
    symbol = symbol.upper().strip()

    # Try exact match on tradingsymbol
    row = df[df["tradingsymbol"].str.upper() == symbol]

    if not row.empty:
        return int(row.iloc[0]["instrument_token"])

    # Try match on name field (indices often appear here)
    row2 = df[df["name"].str.upper() == symbol]

    if not row2.empty:
        return int(row2.iloc[0]["instrument_token"])

    # Print closest matches for debugging
    matches = df[df["tradingsymbol"].str.contains(symbol[:3], case=False, na=False)]
    print("Possible matches:", matches[["tradingsymbol","name"]].head())

    return None

# ---------------- STEP 2: SYMBOL + DATE RANGE + INTERVAL ----------------
if st.session_state.get("logged_in", False):

    st.header("Step 2 — Enter Download Details")

    symbol = st.text_input("Symbol (Example: RELIANCE, TCS, NIFTY 50, NIFTY BANK)")

    start_date = st.date_input("Start Date")
    end_date = st.date_input("End Date")

    interval = st.selectbox(
        "Interval",
        ["minute", "5minute", "15minute", "30minute", "60minute", "day"]
    )

    def download(symbol, start_date, end_date, interval):
        kite = st.session_state["kite"]

        token = get_token(symbol, kite)
        if not token:
            return None, "Symbol not found. For NIFTY use 'NIFTY 50'."

        os.makedirs(OUTPUT_FOLDER, exist_ok=True)
        file_path = os.path.join(OUTPUT_FOLDER, f"{symbol.replace(' ', '_')}.csv")

        all_rows = []
        current = datetime.combine(start_date, datetime.min.time())
        end_dt = datetime.combine(end_date, datetime.min.time())

        total_days = (end_dt - current).days
        done = 0
        progress = st.progress(0)

        while current < end_dt:
            next_day = min(current + timedelta(days=60), end_dt)

            try:
                chunk = kite.historical_data(
                    token,
                    current.strftime("%Y-%m-%d"),
                    next_day.strftime("%Y-%m-%d"),
                    interval=interval
                )
                all_rows.extend(chunk)

            except Exception as e:
                return None, f"Error fetching data: {e}"

            done += 60
            progress.progress(min(done / total_days, 1))
            current = next_day
            time.sleep(0.1)

        df = pd.DataFrame(all_rows)
        df.to_csv(file_path, index=False)
        return file_path, None


    if st.button("Download Data"):
        if not symbol:
            st.error("Enter symbol")
        else:
            st.info("Downloading…")
            file_path, error = download(symbol, start_date, end_date, interval)

            if error:
                st.error(error)
            else:
                st.success("Download complete!")
                with open(file_path, "rb") as f:
                    st.download_button("Download CSV", f, file_name=os.path.basename(file_path))
