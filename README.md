# Bluesky Targeted Monitoring Scanner

A Streamlit application designed to identify Bluesky accounts that may be involved in targeted monitoring of users based on specific keywords in users' profiles.

Reporting indicates that governments and organized groups sometimes use fake accounts, posing as members of a community, to monitor and engage with surveilled accounts. This tool helps visualize those networks.

## Features
- **Deep Scan (Keyword Density):** Fetches the followers of a target account and deeply scans the profiles of the accounts *they* follow to calculate a "Topic Keyword Density".
- **Heuristic Flags:** Runs supplementary behavioral checks to guess if an account behaves like an automated script, flagging abnormalities like suspiciously young account age, bizarre follow/follower ratios, or a total lack of posts.
- **Interactive UI:** Navigate through risk buckets (High Risk, Medium Risk, Low Risk) based on their topic density.
- **Topology Cartography:** Generates two interactive `pyvis` physics-based network graphs: 
  - **Suspicious Network:** Visualizes coordinated behavior between the most suspicious followers.
  - **Target Overlap:** Identifies which suspicious followers are also monitoring accounts that the target directly follows (Mutual Friends).
- **Export Data:** Download a comprehensive JSON or CSV report of the audit state for external analysis.

## Setup Instructions

1. **Clone the Repository & Create Virtual Environment:**
   Run the following commands in your terminal:
   ```bash
   python -m venv venv
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

1. **Authenticate:** Provide your own Bluesky Handle and a specialized App Password. (*Note: Never use your master password. Generate an App Password in your Bluesky Settings -> Advanced -> App Passwords*).
2. **Set Target:** Enter the target Bluesky handle you wish to audit (e.g., `target.bsky.social`).
3. **Configure Scanner:**
   - **Custom Topic Keywords:** Provide a comma-separated list of keywords the tool will use to calculate density (e.g., `crypto, nfts, airdrop`).
   - **Scan Depth:** Choose to analyze the `100`, `500`, or `1000` most recent followers, or scan the `All Time` directory.
4. **Execute:** Click "Run Target Audit" to initiate the deep scans and visualize the generated cartography!

## Limitations
This tool is designed to identify one very specific type of account and behavior pattern: networks of keyword-focused accounts following a central target. It is **not** an exhaustive tool to determine if your account is being surveilled. Most monitoring tools and data scrapers do not require the use of fake "follower" accounts at all to monitor public activity.
