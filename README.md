# Bluesky Network Authenticity Analyzer

A Streamlit application that assesses the risk of inauthentic followers on Bluesky.

## Features
- **Tier 1 (Surface Scan):** Fetches the complete list of followers for a target user and calculates a base "Inauthenticity Score" based on account age, follower/following ratio, and post count.
- **Tier 2 (Deep Scan):** For highly suspicious accounts from Tier 1, fetches a sample of their following list and analyzes keyword density in display names and bios against a set of custom topic keywords.
- **Interactive UI:** View distribution charts, a rankable data table of followers, and download a CSV report.

## Requirements
- Apple Silicon (M1/M2/M3) Mac or compatible environment
- Python 3.10+

## Setup Instructions

1. **Create and Activate a Virtual Environment:**
   Run the following commands in your terminal to isolate your dependencies:
   ```bash
   python3 -m venv venv
   source venv/bin/activate
   ```

2. **Install Dependencies:**
   ```bash
   pip install --upgrade pip
   pip install -r requirements.txt
   ```

3. **Run the Application:**
   ```bash
   streamlit run app.py
   ```

## Usage
Once the Streamlit app opens in your browser:
1. Enter your Bluesky Handle (e.g., `you.bsky.social`) and App Password in the sidebar.
2. Enter the target Bluesky handle you wish to audit.
3. Provide a list of comma-separated Custom Topic Keywords (e.g., `crypto, nfts, airdrop`).
4. Click "Run Target Audit" to execute the analysis and view the results!
