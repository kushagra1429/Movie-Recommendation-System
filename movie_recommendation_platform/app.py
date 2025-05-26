import pickle
import time
import streamlit as st
import requests
import os
import gzip
import json
import threading
from functools import lru_cache

# Thread-safe cache
poster_cache = {}
cache_lock = threading.Lock()

# Persistent cache file
CACHE_FILE = 'poster_cache.json'

def load_cache():
    """Load poster cache from file"""
    global poster_cache
    try:
        if os.path.exists(CACHE_FILE):
            with open(CACHE_FILE, 'r') as f:
                poster_cache = json.load(f)
                print(f"Loaded {len(poster_cache)} cached posters")
    except Exception as e:
        print(f"Error loading cache: {e}")
        poster_cache = {}

def save_cache():
    """Save poster cache to file"""
    try:
        with open(CACHE_FILE, 'w') as f:
            json.dump(poster_cache, f)
        print(f"Saved {len(poster_cache)} posters to cache")
    except Exception as e:
        print(f"Error saving cache: {e}")

def fetch_single_poster(movie_id, max_retries=3):
    """Fetch a single poster with better error handling"""
    movie_id_str = str(movie_id)
    
    # Check cache first
    with cache_lock:
        if movie_id_str in poster_cache:
            cached_result = poster_cache[movie_id_str]
            if cached_result is not None:  # Don't retry failed requests immediately
                return cached_result
    
    url = f"https://api.themoviedb.org/3/movie/{movie_id}?api_key=8265bd1679663a7ea12ac168da84d2e8&language=en-US"
    
    for attempt in range(max_retries):
        try:
            print(f"Fetching poster for movie_id: {movie_id} (attempt {attempt + 1})")
            
            # Add delay between attempts
            if attempt > 0:
                delay = min(2 ** attempt, 10)  # Cap at 10 seconds
                print(f"Waiting {delay} seconds before retry...")
                time.sleep(delay)
            
            response = requests.get(url, timeout=15)
            
            # Handle rate limiting
            if response.status_code == 429:
                retry_after = int(response.headers.get('Retry-After', 5))
                print(f"Rate limited. Waiting {retry_after} seconds...")
                time.sleep(retry_after)
                continue
            
            # Handle other HTTP errors
            if response.status_code != 200:
                print(f"HTTP {response.status_code} for movie_id {movie_id}")
                if attempt == max_retries - 1:
                    with cache_lock:
                        poster_cache[movie_id_str] = None
                    return None
                continue
            
            data = response.json()
            poster_path = data.get('poster_path')
            
            if poster_path:
                full_path = f"https://image.tmdb.org/t/p/w500{poster_path}"
                print(f"Successfully fetched poster: {full_path}")
                
                with cache_lock:
                    poster_cache[movie_id_str] = full_path
                
                return full_path
            else:
                print(f"No poster_path found for movie_id {movie_id}")
                with cache_lock:
                    poster_cache[movie_id_str] = None
                return None
                
        except requests.exceptions.Timeout:
            print(f"Timeout for movie_id {movie_id}")
        except requests.exceptions.RequestException as e:
            print(f"Request error for movie_id {movie_id}: {e}")
        except Exception as e:
            print(f"Unexpected error for movie_id {movie_id}: {e}")
    
    # All attempts failed
    with cache_lock:
        poster_cache[movie_id_str] = None
    return None

def fetch_posters_sequential(movie_ids):
    """Fetch posters sequentially with controlled delays"""
    results = {}
    
    for i, movie_id in enumerate(movie_ids):
        print(f"Fetching poster {i+1}/{len(movie_ids)}")
        
        # Add delay between requests to respect rate limits
        if i > 0:
            time.sleep(1)  # 1 second delay between requests
        
        poster_url = fetch_single_poster(movie_id)
        results[movie_id] = poster_url
        
        # Save cache periodically
        if (i + 1) % 2 == 0:  # Save every 2 requests
            save_cache()
    
    # Final save
    save_cache()
    return results

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
PARENT_DIR = os.path.abspath(os.path.join(BASE_DIR, '..'))

def load_pickle_or_gzip(filename):
    gz_path = os.path.join(PARENT_DIR, filename + '.gz')
    normal_path = os.path.join(PARENT_DIR, filename)
    
    if os.path.exists(gz_path):
        with gzip.open(gz_path, 'rb') as f:
            return pickle.load(f)
    elif os.path.exists(normal_path):
        with open(normal_path, 'rb') as f:
            return pickle.load(f)
    else:
        raise FileNotFoundError(f"Neither {filename} nor {filename}.gz found in {PARENT_DIR}")

@st.cache_data
def get_recommendations(movie_title):
    """Cached function to get movie recommendations"""
    try:
        index = movies[movies['title'] == movie_title].index[0]
        distances = sorted(list(enumerate(similarity[index])), reverse=True, key=lambda x: x[1])
        
        recommended_movies = []
        for i in distances[1:6]:  # Top 5 recommendations
            movie_data = {
                'title': movies.iloc[i[0]].title,
                'movie_id': movies.iloc[i[0]].movie_id,
                'similarity_score': distances[i[0]][1]
            }
            recommended_movies.append(movie_data)
        
        return recommended_movies
    except Exception as e:
        st.error(f"Error getting recommendations: {e}")
        return []

def display_movie_card(movie, poster_url):
    """Display a single movie card"""
    st.subheader(movie['title'])
    
    if poster_url and poster_url != "None":
        try:
            st.image(poster_url, width=200, caption=f"Similarity: {movie['similarity_score']:.1%}")
        except Exception as e:
            st.error(f"Error loading image: {e}")
            st.text("🎬 Image failed to load")
            if st.button(f"Retry {movie['title']}", key=f"retry_{movie['movie_id']}"):
                # Clear cache for this movie and retry
                with cache_lock:
                    movie_id_str = str(movie['movie_id'])
                    if movie_id_str in poster_cache:
                        del poster_cache[movie_id_str]
                st.experimental_rerun()
    else:
        st.text("🎬 Poster not available")
        st.caption(f"Movie ID: {movie['movie_id']}")
        if st.button(f"Try fetch {movie['title']}", key=f"fetch_{movie['movie_id']}"):
            poster_url = fetch_single_poster(movie['movie_id'])
            if poster_url:
                st.experimental_rerun()

def display_recommendations_progressive(recommended_movies):
    """Display recommendations with progressive loading"""
    if not recommended_movies:
        st.warning("No recommendations found.")
        return
    
    # Create columns
    cols = st.columns(5)
    
    # Get movie IDs
    movie_ids = [movie['movie_id'] for movie in recommended_movies]
    
    # Show initial layout with placeholders
    placeholders = []
    for idx, (movie, col) in enumerate(zip(recommended_movies, cols)):
        with col:
            placeholder = st.empty()
            placeholders.append(placeholder)
            with placeholder.container():
                st.text(movie['title'])
                st.text("Loading poster...")
    
    # Fetch posters progressively
    progress_bar = st.progress(0)
    status_text = st.empty()
    
    for idx, movie_id in enumerate(movie_ids):
        status_text.text(f"Loading poster {idx + 1} of {len(movie_ids)}...")
        progress_bar.progress((idx + 1) / len(movie_ids))
        
        # Fetch poster
        poster_url = fetch_single_poster(movie_id)
        
        # Update the specific placeholder
        movie = recommended_movies[idx]
        with placeholders[idx].container():
            display_movie_card(movie, poster_url)
        
        # Small delay to show progress
        time.sleep(0.5)
    
    # Clean up progress indicators
    progress_bar.empty()
    status_text.empty()

# Streamlit App
def main():
    st.set_page_config(page_title="Movie Recommender", layout="wide")
    st.header('🎬 Movie Recommender System')
    
    # Load cache at startup
    load_cache()
    
    # Debug section
    with st.sidebar:
        st.subheader("Debug Info")
        st.text(f"Cached posters: {len(poster_cache)}")
        
        if st.button("Clear Cache"):
            with cache_lock:
                poster_cache.clear()
            if os.path.exists(CACHE_FILE):
                os.remove(CACHE_FILE)
            st.success("Cache cleared!")
            st.experimental_rerun()
        
        if st.button("Test API"):
            test_id = 550  # Fight Club
            result = fetch_single_poster(test_id)
            if result:
                st.success("API working!")
                st.image(result, width=100)
            else:
                st.error("API test failed")
    
    try:
        # Load data
        global movies, similarity
        movies = load_pickle_or_gzip('movie_list.pkl')
        similarity = load_pickle_or_gzip('similarity.pkl')
        
        movie_list = movies['title'].values
        
        # Movie selection
        selected_movie = st.selectbox(
            "Type or select a movie from the dropdown",
            movie_list,
            help="Start typing to search for movies"
        )
        
        if st.button('🔍 Show Recommendations', type="primary"):
            if selected_movie:
                st.subheader(f"Movies similar to: **{selected_movie}**")
                
                # Get recommendations
                recommended_movies = get_recommendations(selected_movie)
                
                if recommended_movies:
                    # Show movie IDs for debugging
                    with st.expander("Debug: Movie IDs"):
                        for movie in recommended_movies:
                            st.text(f"{movie['title']}: ID {movie['movie_id']}")
                    
                    display_recommendations_progressive(recommended_movies)
                else:
                    st.error("Could not generate recommendations. Please try another movie.")
    
    except FileNotFoundError as e:
        st.error(f"Required files not found: {e}")
        st.info("Please ensure movie_list.pkl and similarity.pkl are in the parent directory.")
    except Exception as e:
        st.error(f"An error occurred: {e}")
        st.exception(e)  # Show full traceback for debugging

if __name__ == "__main__":
    main()