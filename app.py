import streamlit as st
import pandas as pd
import altair as alt
import streamlit.components.v1 as components
from pyvis.network import Network
import scanner
import html

st.set_page_config(page_title="Bluesky Targeted Monitoring Scanner", page_icon="🕵️", layout="wide")

st.title("Bluesky Targeted Monitoring Scanner")
st.markdown("Identify Bluesky accounts that may be involved in targeted monitoring of users based on specific keywords in users' profiles.")

if "auth_data" not in st.session_state:
    st.session_state["auth_data"] = {
        "handle": "", 
        "app_password": "", 
        "target_handle": "", 
        "keywords": "crypto, nfts, airdrop, web3"
    }

auth_data = st.session_state["auth_data"]

# Main Interface Configuration
st.header("Authentication & Target Details")

auth_col1, auth_col2 = st.columns(2)
with auth_col1:
    handle = st.text_input("Your Bluesky Handle", value=auth_data.get("handle", ""), placeholder="e.g. you.bsky.social")
with auth_col2:
    app_password = st.text_input(
        "App Password", 
        value=auth_data.get("app_password", ""), 
        type="password",
        help="An App Password is a unique password specific to this tool. It keeps your main account password safe and allows this app to communicate with the Bluesky API on your behalf. To get one: go to your Bluesky Settings -> Advanced -> App passwords -> Add App Password."
    )

target_col1, target_col2, target_col3 = st.columns([2, 2, 1])
with target_col1:
    target_handle = st.text_input("Target Bluesky Handle", value=auth_data.get("target_handle", ""), placeholder="e.g. target.bsky.social")
with target_col2:
    keywords_input = st.text_input("Custom Topic Keywords (comma-separated)", value=auth_data.get("keywords", "crypto, nfts, airdrop, web3"))
with target_col3:
    scan_depth_options = {
        "100 Most Recent": 100,
        "500 Most Recent": 500,
        "1000 Most Recent": 1000,
        "All Followers": None
    }
    selected_depth = st.selectbox(
        "How many followers to scan?", 
        options=list(scan_depth_options.keys()),
        index=1,
        help="Bluesky organizes followers from newest to oldest. Select how many recent followers to analyze."
    )

# Update session state with the current input values
if (handle != auth_data.get("handle") or 
    app_password != auth_data.get("app_password") or 
    target_handle != auth_data.get("target_handle") or 
    keywords_input != auth_data.get("keywords")):
    st.session_state["auth_data"] = {
        "handle": handle,
        "app_password": app_password,
        "target_handle": target_handle,
        "keywords": keywords_input
    }

if st.button("Run Target Audit", type="primary"):
    if not handle or not app_password or not target_handle:
        st.error("Please provide your handle, app password, and a target handle.")
    else:
        keywords = [k.strip() for k in keywords_input.split(",") if k.strip()]
        
        # Step 1: Authentication
        with st.spinner("Authenticating with Bluesky API..."):
            try:
                client = scanner.get_client(handle, app_password)
            except Exception as e:
                st.error(f"Authentication Failed: {e}")
                st.stop()
                
        # Step 2: Fetching Followers (Tier 1)
        limit_val = scan_depth_options[selected_depth]
        loading_text = f"Fetching up to {limit_val} followers for {target_handle}..." if limit_val else f"Fetching ALL followers for {target_handle}... (This may take a minute for large accounts)"
        with st.spinner(loading_text):
            followers_df = scanner.fetch_target_followers(client, target_handle, limit=limit_val)
            
        if followers_df.empty:
            st.warning("No followers found or error fetching followers. Ensure the target handle is correct.")
            st.stop()
            
        # Step 3: Deep Scan (Tier 2)
        total_followers = len(followers_df)
        qualified_scans = len(followers_df[followers_df['follows_count'] >= 10])
        est_seconds = qualified_scans * 0.18  # Approx 5-6 api calls a second including network latency
        est_mins = round(est_seconds / 60)
        if est_mins > 1:
            time_text = f"around {est_mins} minutes"
        elif est_mins == 1:
            time_text = "around 1 minute"
        else:
            time_text = "less than a minute"
        
        scan_info = st.info(f"Found {total_followers} followers. {qualified_scans} follow at least 10 accounts and qualify for a Deep Scan. This should take {time_text}.")
        scan_progress = st.progress(0, text="Running Deep Scan on qualified followers... (Calculating ETA)")
        
        import time
        start_time = time.time()
        
        def update_progress(current, total):
            elapsed_time = time.time() - start_time
            if current > 0:
                seconds_per_item = elapsed_time / current
                eta_seconds = (total - current) * seconds_per_item
                mins, secs = divmod(int(eta_seconds), 60)
                time_str = f"~ {mins}m {secs}s remaining" if mins > 0 else f"~ {secs}s remaining"
            else:
                time_str = "calculating..."
                
            scan_progress.progress(current / total, text=f"Deep Scanning: {current}/{total} followers (Est. {time_str})")
            
        followers_df = scanner.run_deep_scan(client, followers_df, keywords, progress_callback=update_progress)
        scan_progress.empty()
        scan_info.empty()
            
        # Step 4: Coordinated Topology (Phase 3)
        with st.spinner("Analyzing network for coordinated behavior..."):
            suspicious_network_df = followers_df[followers_df['deep_scan_score'] >= 25.0]
            if not suspicious_network_df.empty:
                connections_df = scanner.fetch_network_connections(client, suspicious_network_df)
            else:
                connections_df = pd.DataFrame()
                
        # Step 5: Target specific overlap
        with st.spinner("Fetching accounts followed by target..."):
            target_followed = scanner.fetch_target_follows(client, target_handle, limit=1000)
            
        st.success("Audit Complete!")
        
        # Layout Results
        st.header("Targeted Monitoring Assessment")
        
        high_risk_df = followers_df[followers_df['deep_scan_score'] >= 25.0]
        high_risk_count = len(high_risk_df)
        avg_high_risk_toxicity = high_risk_df['deep_scan_score'].mean() if not high_risk_df.empty else 0.0
        
        metric_col1, metric_col2, metric_col3 = st.columns(3)
        metric_col1.metric("Total Followers Analyzed", len(followers_df))
        metric_col2.metric("High Risk Accounts", high_risk_count)
        metric_col3.metric("Avg Topic Match (High Risk)", f"{avg_high_risk_toxicity:.1f}%")
        
        # Data Table
        st.subheader("Follower Analysis Data")
        st.markdown("Sort by `Targeted Topic Density` to find the accounts most heavily focused on your keywords.")
        
        # Formatting for display
        table_df = followers_df.copy()
        for col in ['followers_count', 'follows_count', 'posts_count', 'inauthenticity_score']:
            table_df[col] = table_df[col].astype(int)
        
        table_df['behavior_flags'] = table_df['flags'].apply(lambda f: ", ".join(f) if isinstance(f, list) else str(f))
        table_df['Profile'] = "https://bsky.app/profile/" + table_df['handle']
        
        # Reorder columns
        cols = ['Profile', 'deep_scan_score', 'behavior_flags', 'followers_count', 'follows_count', 'posts_count', 'description']
        view_df = table_df[cols]
        
        st.dataframe(
            view_df.sort_values(by=['deep_scan_score'], ascending=False), 
            use_container_width=True,
            hide_index=True,
            column_config={
                "Profile": st.column_config.LinkColumn("Profile URL", display_text="https://bsky.app/profile/(.*)"),
                "deep_scan_score": st.column_config.NumberColumn("Targeted Topic Density", format="%.1f%%")
            }
        )

        # Charts
        with st.expander("View Network Health Charts"):
            chart_col1, chart_col2 = st.columns(2)
            
            with chart_col1:
                st.subheader("Distribution of Keyword Matches")
                chart1 = alt.Chart(followers_df).mark_bar(color='#d80000').encode(
                    x=alt.X("deep_scan_score:Q", bin=alt.Bin(maxbins=20), title="Topic Keyword Density (%)"),
                    y=alt.Y("count():Q", title="Number of Followers"),
                    tooltip=['count()']
                ).properties(height=300)
                st.altair_chart(chart1, use_container_width=True)
                
            with chart_col2:
                st.subheader("Common Suspicious Behaviors")
                # Flatten the flags lists and count occurrences
                all_flags = [flag for flags_list in followers_df['flags'] for flag in (flags_list if isinstance(flags_list, list) else [])]
                if all_flags:
                    flags_df = pd.DataFrame({'Flag': all_flags})
                    flag_counts = flags_df['Flag'].value_counts().reset_index()
                    flag_counts.columns = ['Flag', 'Count']
                    
                    chart2 = alt.Chart(flag_counts).mark_bar(color='#333333').encode(
                        x=alt.X("Count:Q", title="Occurrences"),
                        y=alt.Y("Flag:N", sort='-x', title=""),
                        tooltip=['Count']
                    ).properties(height=300)
                    st.altair_chart(chart2, use_container_width=True)
                else:
                    st.info("No heuristic flags detected in the analyzed network.")
        
        # Visualizing Network Graph
        st.subheader("Targeted Monitoring Network Graph")
        st.markdown("Visualizes connections between the most suspicious followers (High Risk: >= 25% topic match).")
        st.markdown("**Legend:** 🔴 Target Account | 🟠 Suspicious Follower | ⚫ Mutual Connection")
        
        try:
            # Revert notebook=True as it breaks Streamlit iframe rendering with an infinite loading screen.
            # Use cdn_resources='remote' so that `neighbourhoodHighlight` JS is injected inline rather than looking for a missing local utils.js
            net = Network(height='800px', width='100%', bgcolor='#ffffff', font_color='black', directed=True, neighborhood_highlight=True, cdn_resources='remote')
            
            # Use direct options object manipulation for more reliable stabilization
            net.force_atlas_2based(gravity=-50, central_gravity=0.01, spring_length=100, spring_strength=0.08, damping=0.9, overlap=1)
            net.options.physics.stabilization = {
                "enabled": True, 
                "iterations": 1000, 
                "updateInterval": 100,
                "onlyDynamicEdges": False,
                "fit": True
            }
            # Color configuration for unselected nodes and edges to ensure they fade in dark mode
            net.options.edges.color = {"inherit": True}
            
            # Disable scroll zooming and show navigation buttons
            net.options.interaction = {
                "zoomView": False,
                "navigationButtons": True
            }
            
            # Add central node
            net.add_node(html.escape(target_handle), label=html.escape(target_handle), color='#d80000', size=25, title="Audit Target")
            
            # Add suspicious nodes and default connection to target
            for _, row in suspicious_network_df.iterrows():
                node_id = row['handle']
                # Don't accidentally re-add the target if they are somehow in their own follower list
                if node_id == target_handle:
                    continue
                flags_str = "\n".join(row['flags']) if isinstance(row['flags'], list) else str(row['flags'])
                score_val = row['deep_scan_score']
                node_color = 'orange'
                title_tooltip = f"Handle: {html.escape(node_id)}\nDensity: {score_val:.1f}%\nFlags:\n{html.escape(flags_str)}"
                net.add_node(html.escape(node_id), label=html.escape(node_id), title=title_tooltip, color=node_color, size=15)
                net.add_edge(html.escape(node_id), html.escape(target_handle), color='gray')
                
            # Render shared connections
            if not connections_df.empty:
                followee_counts = connections_df['target_handle'].value_counts()
                # Find followees that are followed by MORE THAN 1 suspicious account
                shared_followees = followee_counts[followee_counts >= 2].index
                
                for followee in shared_followees:
                     if followee == target_handle:
                         continue
                     net.add_node(html.escape(followee), label=html.escape(followee), color='#333333', size=10, title=f"Shared Connection: {html.escape(followee)}")
                    
                for _, row in connections_df.iterrows():
                    source = row['source_handle']
                    target = row['target_handle']
                    if target in shared_followees and target != target_handle:
                        # Shared connections are grayed-out arrows to blue nodes
                        net.add_edge(html.escape(source), html.escape(target), color='#cccccc')
                
            path = '/tmp/graph.html'
            net.save_graph(path)
            
            with open(path, 'r', encoding='utf-8') as f:
                source_code = f.read()
                
            # Inject fixes for PyVis styling to make it look clean in Streamlit
            # 1. Remove the white border/background from the bootstrap card container
            source_code = source_code.replace('<div class="card" style="width: 100%">', '<div class="card" style="width: 100%; border: none; background-color: transparent;">')
            
            # 2. Hide the loading bar and remove white borders/margins via CSS
            custom_css = """
            #loadingBar { display: none !important; }
            body { margin: 0; padding: 0; background-color: transparent !important; }
            .card { border: none !important; margin: 0 !important; background-color: transparent !important; box-shadow: none !important; }
            .card-body { padding: 0 !important; background-color: transparent !important; }
            #mynetwork { border: 1px solid #ebebeb !important; border-radius: 8px; outline: none !important; }
            </style>
            """
            source_code = source_code.replace('</style>', custom_css)
            
            # 3. Light Mode Dimming: Modify Pyvis's hardcoded neighborhood isolation colors to fade cleanly into white
            source_code = source_code.replace('"rgba(200,200,200,0.5)"', '"rgba(240,240,240,0.5)"')
            source_code = source_code.replace('"rgba(150,150,150,0.75)"', '"rgba(240,240,240,0.5)"')
            
            # 4. Inject explicit edge dimming since PyVis natively only dims nodes
            js_dim_edges = """
                  var allEdgesObj = edges.get({ returnType: "Object" });
                  var originalEdgeColors = {};
                  for (let edgeId in allEdgesObj) {
                    originalEdgeColors[edgeId] = allEdgesObj[edgeId].color;
                  }
                  
                  network.on("click", function(params) {
                      var currentEdges = edges.get({ returnType: "Object" });
                      var updateEdgesArray = [];
                      if (params.nodes.length > 0) {
                          var selectedNode = params.nodes[0];
                          var connectedEdges = network.getConnectedEdges(selectedNode);
                          for (let edgeId in currentEdges) {
                              if (!connectedEdges.includes(edgeId)) {
                                  currentEdges[edgeId].color = "rgba(220,220,220,0.6)";
                              } else {
                                  currentEdges[edgeId].color = originalEdgeColors[edgeId] || "gray";
                              }
                              updateEdgesArray.push(currentEdges[edgeId]);
                          }
                      } else {
                          for (let edgeId in currentEdges) {
                              currentEdges[edgeId].color = originalEdgeColors[edgeId] || "gray";
                              updateEdgesArray.push(currentEdges[edgeId]);
                          }
                      }
                      edges.update(updateEdgesArray);
                  });
                  network.on("click", neighbourhoodHighlight);
            """
            source_code = source_code.replace('network.on("click", neighbourhoodHighlight);', js_dim_edges)
            
            # 5. Inject Javascript to freeze physics immediately after the layout calculations finish
            js_match = "network = new vis.Network(container, data, options);"
            freeze_js = """network = new vis.Network(container, data, options);
                  network.once("stabilizationIterationsDone", function() {
                      network.setOptions( { physics: false } );
                  });"""
            source_code = source_code.replace(js_match, freeze_js)
            
            components.html(source_code, height=850, scrolling=True)
        except Exception as e:
            st.error(f"Failed to generate network visualization: {e}")

        # Target Follower Overlap Graph
        st.subheader("Targeted Friends & Connections Overlap")
        st.markdown("Visualizes which of the suspicious followers are also monitoring accounts that you (the target) follow.")
        st.markdown("**Legend:** 🔴 Target Account | 🟠 Suspicious Follower | ⚫ Mutual Friend (Target Follows Them)")
        
        try:
            if not connections_df.empty and target_followed:
                suspicious_followees = connections_df['target_handle'].unique()
                mutual_friends = set(target_followed).intersection(set(suspicious_followees))
                
                if mutual_friends:
                    net2 = Network(height='600px', width='100%', bgcolor='#ffffff', font_color='black', directed=True, neighborhood_highlight=True, cdn_resources='remote')
                    net2.force_atlas_2based(gravity=-50, central_gravity=0.01, spring_length=100, spring_strength=0.08, damping=0.9, overlap=1)
                    net2.options.physics.stabilization = {
                        "enabled": True, "iterations": 1000, "updateInterval": 100, "onlyDynamicEdges": False, "fit": True
                    }
                    net2.options.edges.color = {"inherit": True}
                    net2.options.interaction = {
                        "zoomView": False,
                        "navigationButtons": True
                    }
                    
                    # Add Target Node
                    net2.add_node(html.escape(target_handle), label=html.escape(target_handle), color='#d80000', size=25, title="Audit Target")
                    
                    added_nodes = {target_handle}
                    
                    # Add Mutual Friend nodes and edges from target
                    for friend in mutual_friends:
                        if friend not in added_nodes:
                            net2.add_node(html.escape(friend), label=html.escape(friend), color='#333333', size=15, title=f"Mutual Friend: {html.escape(friend)}")
                            added_nodes.add(friend)
                            net2.add_edge(html.escape(target_handle), html.escape(friend), color='gray')
                            
                    # Add suspicious followers that follow these mutual friends
                    for _, row in connections_df[connections_df['target_handle'].isin(mutual_friends)].iterrows():
                        susp_handle = row['source_handle']
                        friend_handle = row['target_handle']
                        
                        if susp_handle not in added_nodes:
                            score_mask = suspicious_network_df['handle'] == susp_handle
                            if score_mask.any():
                                score_val = suspicious_network_df[score_mask]['deep_scan_score'].values[0]
                                node_color = 'orange'
                                title_tooltip = f"Targeted Follower\nDensity: {score_val:.1f}%"
                            else:
                                score_val = 0.0
                                node_color = 'orange'
                                title_tooltip = f"Targeted Follower\nDensity: Unknown"
                                
                            net2.add_node(html.escape(susp_handle), label=html.escape(susp_handle), title=title_tooltip, color=node_color, size=15)
                            added_nodes.add(susp_handle)
                            
                        # Suspicious node follows friend
                        net2.add_edge(html.escape(susp_handle), html.escape(friend_handle), color='#cccccc')
                        
                    path2 = '/tmp/graph2.html'
                    net2.save_graph(path2)
                    
                    with open(path2, 'r', encoding='utf-8') as f:
                        source_code2 = f.read()
                        
                    source_code2 = source_code2.replace('<div class="card" style="width: 100%">', '<div class="card" style="width: 100%; border: none; background-color: transparent;">')
                    custom_css2 = """
            #loadingBar { display: none !important; }
            body { margin: 0; padding: 0; background-color: transparent !important; }
            .card { border: none !important; margin: 0 !important; background-color: transparent !important; box-shadow: none !important; }
            .card-body { padding: 0 !important; background-color: transparent !important; }
            #mynetwork { border: 1px solid #ebebeb !important; border-radius: 8px; outline: none !important; }
            </style>
            """
                    source_code2 = source_code2.replace('</style>', custom_css2)
                    source_code2 = source_code2.replace('"rgba(200,200,200,0.5)"', '"rgba(240,240,240,0.5)"')
                    source_code2 = source_code2.replace('"rgba(150,150,150,0.75)"', '"rgba(240,240,240,0.5)"')
                    source_code2 = source_code2.replace('network.on("click", neighbourhoodHighlight);', js_dim_edges)
                    source_code2 = source_code2.replace(js_match, freeze_js)
                    
                    components.html(source_code2, height=650, scrolling=True)
                else:
                    st.info("No suspicious followers are tracking accounts that the target follows.")
            else:
                st.info("Insufficient data to build a target overlap network graph.")
                
        except Exception as e:
            st.error(f"Failed to generate target overlap visualization: {e}")



        # CSV Export
        st.subheader("Export State")
        colA, colB = st.columns(2)
        timestamp = pd.Timestamp.now().strftime("%Y%m%d_%H%M%S")
        
        with colA:
            csv = followers_df.to_csv(index=False)
            st.download_button(
                label="Download Full Audit State (CSV)",
                data=csv,
                file_name=f"{target_handle}_audit_state_{timestamp}.csv",
                mime="text/csv"
            )
        with colB:
            json_data = followers_df.to_json(orient="records")
            st.download_button(
                label="Download Full Audit State (JSON)",
                data=json_data,
                file_name=f"{target_handle}_audit_state_{timestamp}.json",
                mime="application/json"
            )

st.markdown("---")
st.header("About This Tool")
st.markdown("""
### What does this tool do?
The **Bluesky Targeted Monitoring Scanner** helps identify Bluesky accounts that may be involved in targeted monitoring of users based on specific keywords in users' profiles. Reporting has indicated that governments use fake accounts, posing as members of a community, to monitor and sometimes even engage with surveilled accounts.

### How are the Risk Buckets defined?
When you scan a target account, the system downloads all of their followers. It then runs a **Deep Scan** on every follower that follows at least 10 other accounts (accounts that follow <10 people are ignored and scored 0%, as they lack sufficient data to establish a network pattern). 

The Deep Scan checks the basic profiles of the accounts that each follower tracks to look for your Custom Topic Keywords. The result is a **Topic Keyword Density (%)**.

For example, if you enter `crypto, nfts` and 40% of the accounts a follower tracks mention those words in their bios, their Density is 40%. The tool groups them strictly by this density score:
* **High Risk:** $\ge$ 25% Keyword Match Density
* **Medium Risk:** 10% - 24% Keyword Match Density
* **Low Risk:** 0% - 9% Keyword Match Density

### What are Heuristic Flags?
In addition to the Deep Scan, the system runs behavioral checks on every follower to guess if the account behaves like a normal human or a bot script. Abnormalities like a suspiciously young Account Age, bizarre Follow/Follower Ratios, or a total lack of Posts are surfaced as supplementary **Heuristic Flags**. They help provide critical context—if an account is High Risk (25% density) AND has the "Zero Posts" flag, you're highly likely looking at an automated bot!

### How do I read the Graphs?
In threat analysis, a huge indicator of an organized network is that the accounts behave perfectly identically because they are controlled by the same script or list. 
* **🔴 Red Node:** The account you are auditing.
* **🟠 Orange Nodes:** High Risk Followers (Density $\ge$ 25%).
* **⚫ Black Nodes (Mutual Connections):** Accounts that are being followed by *multiple* different High Risk target accounts simultaneously. 
* **⚫ Black Nodes (Target Followed Overlap):** Accounts followed by the targeting accounts, *and* happen to be accounts that you (the Target) follow. This helps identify if the bad actors are attacking your specific friend group! 

*Tip: Click on any colored circle in the graph to dim the noise and highlight their specific neighborhood web!*

### Limitations
This tool is designed to identify one very specific type of account and behavior pattern: networks of keyword-focused accounts following a central target. It is **not** an exhaustive tool to determine if your account is being surveilled. In fact, most monitoring tools and data scrapers do not require the use of fake "follower" accounts at all to monitor public activity.

---
<div style="text-align: center; margin-top: 30px; font-style: italic; color: #666;">
    An <a href="https://bsky.app/profile/airplaneian.com" target="_blank" style="color: #d80000; text-decoration: none;">@airplaneian</a> joint
</div>
""", unsafe_allow_html=True)
