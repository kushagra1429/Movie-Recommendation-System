import pickle
import streamlit as st
import requests
import os
import gzip

# def fetch_poster(movie_id):
#     url = "https://api.themoviedb.org/3/movie/{}?api_key=8265bd1679663a7ea12ac168da84d2e8&language=en-US".format(movie_id)
#     data = requests.get(url)
#     data = data.json()
#     poster_path = data['poster_path']
#     full_path = "https://image.tmdb.org/t/p/w500/" + poster_path
#     return full_path

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

# Go one directory up to access the pkl files
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

def recommend(movie):
    index = movies[movies['title'] == movie].index[0]
    distances = sorted(list(enumerate(similarity[index])), reverse=True, key=lambda x: x[1])
    recommended_movie_names = []
    recommended_movie_posters = []
    for i in distances[1:6]:
        # fetch the movie poster
        movie_id = movies.iloc[i[0]].movie_id
        # recommended_movie_posters.append(fetch_poster(movie_id))
        recommended_movie_names.append(movies.iloc[i[0]].title)

    return recommended_movie_names, recommended_movie_posters

st.header('Movie Recommender System')

movies = load_pickle_or_gzip('movie_list.pkl')
similarity = load_pickle_or_gzip('similarity.pkl')

movie_list = movies['title'].values
selected_movie = st.selectbox(
    "Type or select a movie from the dropdown",
    movie_list
)

if st.button('Show Recommendation'):
    recommended_movie_names, recommended_movie_posters = recommend(selected_movie)
    col1, col2, col3, col4, col5 = st.columns(5)
    with col1:
        st.text(recommended_movie_names[0])
        # st.image(recommended_movie_posters[0])
    with col2:
        st.text(recommended_movie_names[1])
        # st.image(recommended_movie_posters[1])
    with col3:
        st.text(recommended_movie_names[2])
        # st.image(recommended_movie_posters[2])
    with col4:
        st.text(recommended_movie_names[3])
        # st.image(recommended_movie_posters[3])
    with col5:
        st.text(recommended_movie_names[4])
        # st.image(recommended_movie_posters[4])
