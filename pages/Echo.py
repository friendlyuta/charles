import streamlit as st
from dotenv import load_dotenv
import os
import time
import random
import requests
import mplfinance as mpf
import pandas as pd
from datetime import datetime
from openai import OpenAI

# Load environment variables
load_dotenv()

# Replace this with your actual Polygon.io and OpenAI API keys
POLYGON_API_KEY = os.getenv("POLYGON_API_KEY")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")

# Set OpenAI API key from Streamlit secrets
openai_client = OpenAI(api_key=OPENAI_API_KEY)

st.title("Charles - Stock Charting Assistant")

# Helper function to stream a message with a delay
def stream_message(message, delay=0.05):
    for word in message.split():
        yield word + " "
        time.sleep(delay)

# Charles greeting emulator
def response_generator():
    response = random.choice(
        [
            "Hi, I'm Charles! How can I assist you in charting today?",
            "Charles here! Is there anything I can help chart for you?",
            "Hello! I'm Charles, your charting assistant. What can I chart for you today?",
        ]
    )
    return response

# Initialize chat history
if "messages" not in st.session_state:
    st.session_state.messages = []

# Display chat messages from history on app rerun
for message in st.session_state.messages:
    with st.chat_message(message["role"]):
        st.markdown(message["content"])

# Initial greeting if no other messages have been sent
if len(st.session_state.messages) == 0:
    with st.chat_message("assistant"):
        response = response_generator()
        st.write_stream(stream_message(response))
        st.session_state.messages.append({"role": "assistant", "content": response})

def get_response(user_prompt):
    response = OpenAI().chat.completions.create(
        model="gpt-4o-mini",
        messages=[
            {"role": "system", "content": "You are Charles, a help assistant that can ONLY chart stocks and add/change/remove requested common indicators to be overlayed. For now provide only the stock ticker for the given input and only give the ticker. Nothing else."},
            {"role": "user", "content": user_prompt},
        ],
        stream=True
    )

    for chunk in response:
        content = chunk.choices[0].delta.content
        if content:
            yield content

# Function to fetch stock data from Polygon API using URL
def fetch_stock_data(ticker, timespan="day", multiplier=1, limit=100, from_date="2024-01-01", to_date=None):
    if not to_date:
        to_date = datetime.now().strftime("%Y-%m-%d")
    
    url = (
        f"https://api.polygon.io/v2/aggs/ticker/{ticker}/range/{multiplier}/{timespan}/{from_date}/{to_date}"
        f"?adjusted=true&sort=asc&limit={limit}&apiKey={POLYGON_API_KEY}"
    )
    
    response = requests.get(url)
    data = response.json()

    # Handle API response errors
    if response.status_code != 200 or "results" not in data:
        st.error("Error fetching stock data")
        return pd.DataFrame()

    return pd.DataFrame([
        {
            "Date": datetime.fromtimestamp(item["t"] / 1000),
            "Open": item["o"],
            "High": item["h"],
            "Low": item["l"],
            "Close": item["c"],
            "Volume": item["v"]
        }
        for item in data["results"]
    ]).set_index("Date")

# Accept user input
if prompt := st.chat_input("How can I help you?"):
    # Add user message to chat history
    st.session_state.messages.append({"role": "user", "content": prompt})
    with st.chat_message("user"):
        st.markdown(prompt)

    # Initialize empty list to collect the assistant's response
    collected_messages = []
    ai_response = get_response(prompt)
    
    # Collect all response chunks
    for chunk in ai_response:
        collected_messages.append(chunk)  # Append each chunk to the list

    # Join collected messages into a single string
    full_ai_response = ''.join(collected_messages)
    
    # Display the full response at once
    with st.chat_message("assistant"):
        st.write_stream(stream_message(full_ai_response))
    
    # Add assistant response to chat history
    st.session_state.messages.append({"role": "assistant", "content": full_ai_response})

    # Extract stock ticker from the assistant's response
    ticker = ''.join(e for e in full_ai_response if e.isalnum()).upper()

    # Fetch stock data
    stock_data = fetch_stock_data(ticker=ticker)

    if not stock_data.empty:
        # Plot the candlestick chart using mplfinance
        fig, ax = mpf.plot(
            stock_data,
            type="candle",
            style="charles",
            title=f"{ticker} Stock Price",
            ylabel="Price",
            volume=True,
            returnfig=True
        )

        # Display the plot in Streamlit
        st.pyplot(fig)
    else:
        st.error("No data available for the specified ticker.")
