import time
import pandas as pd
from atproto import Client

def get_client(handle, app_password):
    client = Client()
    try:
        client.login(handle, app_password)
        return client
    except Exception as e:
        raise ValueError(f"Failed to authenticate: {str(e)}")

def calculate_inauthenticity_score(profile):
    score = 0
    flags = []
    # Age heuristic
    try:
        created_at = getattr(profile, 'created_at', None)
        if created_at:
            created_date = pd.to_datetime(created_at)
            # using timezone-aware current time
            age_days = (pd.Timestamp.now(tz='UTC') - created_date).days
            if age_days < 30:
                score += 30
                flags.append("New Account (<30 days)")
            elif age_days < 90:
                score += 15
                flags.append("Recent Account (<90 days)")
    except Exception:
        pass

    # Follower/Following ratio
    followers = getattr(profile, 'followers_count', 0) or 0
    following = getattr(profile, 'follows_count', 0) or 0
    if following > 2000 and followers < 10:
        score += 60
        flags.append("Extreme Ratio Anomaly (Following >2000, Followers <10)")
    elif following > 100 and followers < 10:
        score += 40
        flags.append("High Following, Low Followers")
    elif following > 300 and followers < 50:
        score += 30
        flags.append("Ratio Anomaly")
    elif following > 0 and (following / max(followers, 1)) > 50:
        score += 20
        flags.append("High Follow Velocity")
    
    # Post count
    posts = getattr(profile, 'posts_count', 0) or 0
    if posts == 0:
        score += 10
        flags.append("Zero Posts")
    elif posts < 5:
        score += 5
        flags.append("Low Post Count")
        
    # Placeholder for Advanced Weighting (e.g. content similarity/follower overlap)
    # This logic would go here, examining actual posts/reposts
    
    return min(score, 100), flags

def chunked_iterable(iterable, size):
    for i in range(0, len(iterable), size):
        yield iterable[i:i + size]

def fetch_target_followers(client, target_handle, limit=None):
    followers = []
    cursor = None
    
    try:
        # Resolve handle to DID if necessary, but get_followers accepts actor
        while limit is None or len(followers) < limit:
            batch_limit = min(100, limit - len(followers)) if limit is not None else 100
            response = client.app.bsky.graph.get_followers({'actor': target_handle, 'cursor': cursor, 'limit': batch_limit})
            if not getattr(response, 'followers', None):
                break
                
            # Extract DIDs from basic profiles to fetch detailed profiles
            dids = [f.did for f in response.followers]
            
            # Batch fetch profiles (API limit is 25 per request)
            detailed_profiles = []
            for chunk in chunked_iterable(dids, 25):
                if not chunk: continue
                try:
                    profiles_resp = client.app.bsky.actor.get_profiles({'actors': chunk})
                    detailed_profiles.extend(profiles_resp.profiles)
                except Exception as e:
                    print(f"Error fetching detailed profiles: {e}")
                time.sleep(0.2)  # Respect rate limiting
                
            # Map detailed profiles by DID
            profile_map = {p.did: p for p in detailed_profiles}
                
            for basic_f in response.followers:
                f = profile_map.get(basic_f.did, basic_f)
                score, flags = calculate_inauthenticity_score(f)
                followers.append({
                    'did': f.did,
                    'handle': f.handle,
                    'display_name': getattr(f, 'display_name', '') or '',
                    'description': getattr(f, 'description', '') or '',
                    'created_at': getattr(f, 'created_at', None),
                    'followers_count': getattr(f, 'followers_count', 0) or 0,
                    'follows_count': getattr(f, 'follows_count', 0) or 0,
                    'posts_count': getattr(f, 'posts_count', 0) or 0,
                    'inauthenticity_score': score,
                    'flags': flags
                })
            
            cursor = getattr(response, 'cursor', None)
            if not cursor:
                break
            time.sleep(0.5)  # Respect rate limiting
            
    except Exception as e:
        print(f"Error fetching followers: {e}")
        
    return pd.DataFrame(followers)

def check_keyword_density(profile, keywords):
    if not keywords:
        return 0.0
        
    display_name = getattr(profile, 'display_name', '') or ''
    description = getattr(profile, 'description', '') or ''
    text_to_check = f"{display_name} {description}".lower()
    
    if not text_to_check.strip():
        return 0.0
        
    # Check if ANY of the keywords appear in the profile
    has_match = any(kw.lower().strip() in text_to_check for kw in keywords)
    return 1.0 if has_match else 0.0

def deep_scan_follower(client, follower_did, keywords):
    if not keywords:
        return 0.0
        
    try:
        # Fetch a sample of who this suspicious account follows
        response = client.app.bsky.graph.get_follows({'actor': follower_did, 'limit': 50})
        if not getattr(response, 'follows', None):
            return 0.0
            
        density_scores = []
        for followee in response.follows:
            density = check_keyword_density(followee, keywords)
            density_scores.append(density)
            
        if density_scores:
            return sum(density_scores) / len(density_scores)
            
    except Exception as e:
        print(f"Error in deep scan for {follower_did}: {e}")
        
    return 0.0

def run_deep_scan(client, followers_df, keywords, progress_callback=None):
    if followers_df.empty:
        return followers_df
        
    followers_df['deep_scan_score'] = 0.0
    total = len(followers_df.index)
    
    # Run deep scan on ALL followers
    for i, idx in enumerate(followers_df.index):
        follows_count = followers_df.at[idx, 'follows_count']
        
        if follows_count < 10:
            # Skip accounts that follow too few people to establish a statistically significant topic density pattern
            deep_deep_score = 0.0
        else:
            did = followers_df.at[idx, 'did']
            deep_deep_score = deep_scan_follower(client, did, keywords)
            time.sleep(0.05)  # Rate limiting reduced for speed
            
        followers_df.at[idx, 'deep_scan_score'] = deep_deep_score * 100  # Convert to percentage
        
        if progress_callback:
            progress_callback(i + 1, total)
        
    return followers_df

def fetch_network_connections(client, suspicious_df, limit_per_account=50):
    edges = []
    
    for _, row in suspicious_df.iterrows():
        follower_did = row['did']
        follower_handle = row['handle']
        try:
            # Fetch who this highly suspicious account follows
            response = client.app.bsky.graph.get_follows({'actor': follower_did, 'limit': limit_per_account})
            if not getattr(response, 'follows', None):
                continue
                
            for followee in response.follows:
                edges.append({
                    'source_handle': follower_handle,
                    'target_handle': followee.handle,
                    'target_did': followee.did
                })
        except Exception as e:
            print(f"Error fetching follows for {follower_handle}: {e}")
            
        time.sleep(0.3)  # Rate limiting for secondary fetch
        
    return pd.DataFrame(edges)

def fetch_target_follows(client, target_handle, limit=1000):
    follows = []
    cursor = None
    try:
        while len(follows) < limit:
            response = client.app.bsky.graph.get_follows({'actor': target_handle, 'cursor': cursor, 'limit': min(100, limit - len(follows))})
            if not getattr(response, 'follows', None):
                break
            for followee in response.follows:
                follows.append(followee.handle)
            cursor = getattr(response, 'cursor', None)
            if not cursor:
                break
            time.sleep(0.5)
    except Exception as e:
        print(f"Error fetching target follows {target_handle}: {e}")
    return follows
