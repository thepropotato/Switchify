from flask import jsonify,Flask, render_template, redirect, url_for, request, session
from flask_wtf import FlaskForm
from wtforms import SelectField, SubmitField
import spotipy
from spotipy.oauth2 import SpotifyOAuth
import os
from flask import jsonify
from flask_socketio import emit
from flask_socketio import SocketIO
from flask import copy_current_request_context
import time
import google.oauth2.credentials
from google_auth_oauthlib.flow import Flow
from googleapiclient.discovery import build
from youtubesearchpython import VideosSearch
import csv
import re

app = Flask(__name__)
app.config['SECRET_KEY'] = 'your_secret_key'

socketio = SocketIO(app, async_mode=None, engineio_logger=True, secure=True)

# Replace these values with your own
client_id = '27301e2211b74792a852693dd9cc95bc'
client_secret = '8f5a80b4723c43ed850713d1b753cbb5'
redirect_uri = 'https://switchifytm.onrender.com:5000/callback'

# Set up Spotify API authentication
sp = spotipy.Spotify(auth_manager=SpotifyOAuth(client_id=client_id,
                                               client_secret=client_secret,
                                               redirect_uri=redirect_uri,
                                               scope='playlist-read-private playlist-read-collaborative',
                                               open_browser=True,
                                               show_dialog=True))

# Clear cached token
cache_path = ".cache"
if os.path.exists(cache_path):
    os.remove(cache_path)

@socketio.on('copy_playlist_message', namespace='/')
def handle_copy_playlist_message(message):
    socketio.emit('copy_playlist_message', {'message': message}, namespace='/', broadcast=True)


class LoginForm(FlaskForm):
    playlist = SelectField('Select a Playlist', choices=[], coerce=str)
    convert = SubmitField('Convert')


# Set up the OAuth flow for the first time
SCOPES = ["https://www.googleapis.com/auth/youtube.force-ssl"]
API_SERVICE_NAME = "youtube"
API_VERSION = "v3"

client_secrets = {
        "web": {
            "client_id": "198293411953-86bfnt1lksb04f041erh4kn097gv2gta.apps.googleusercontent.com",
            "project_id": "youtube-playlist-406517",
            "auth_uri": "https://accounts.google.com/o/oauth2/auth",
            "token_uri": "https://oauth2.googleapis.com/token",
            "auth_provider_x509_cert_url": "https://www.googleapis.com/oauth2/v1/certs",
            "client_secret": "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",
            "redirect_uris": ["https://switchifytm.onrender.com/youtube-auth"],
            "javascript_origins": ["https://switchifytm.onrender.com"]
        }
    }

def authenticate():
    # Set up OAuth credentials using Web server flow
    flow = Flow.from_client_config(client_secrets, SCOPES)
    flow.redirect_uri = "https://switchifytm.onrender.com/copy-playlist"

    # Generate the authorization URL
    authorization_url, _ = flow.authorization_url(prompt='consent')
    session['auth_url'] = authorization_url

    return authorization_url

# New route for YouTube authentication and playlist creation
@app.route('/youtube-auth', methods=['GET'])
def youtube_auth():
    # Get the authorization URL
    auth_url = authenticate()
    return redirect(auth_url)

def create_playlist(youtube, name):
    request = youtube.playlists().insert(
        part="snippet,status",
        body={
            "snippet": {
                "title": name,
                "description": "Your Spotify playlist in YT Music",
            },
            "status": {"privacyStatus": "private"},  # Change privacyStatus if needed
        },
    )
    response = request.execute()

    # Print the new playlist ID
    playlist_id = response["id"]
    print(f"Playlist created! ID: {playlist_id}")
    return playlist_id

@app.route('/copy-playlist', methods=['GET', 'POST'])
def copy_playlist_route():
    # Retrieve the song titles from the AJAX request
    print("COPY PLAYLIST ROUTE TRIGGERED")

    # Retrieve the authorization URL from the session
    auth_url = session.pop('auth_url', None)

    if auth_url is None:
        return jsonify({"error": "Authorization URL not found"})

    # Retrieve the authorization code from the callback URL
    authorization_response = request.args.get('code')
    print(authorization_response)

    if authorization_response is None:
        return jsonify({"error": "Authorization code not provided"})

    # Set up OAuth credentials using Web server flow
    flow = Flow.from_client_config(client_secrets, SCOPES)
    flow.redirect_uri = "https://switchifytm.onrender.com/copy-playlist"

    
    flow.fetch_token(authorization_response=authorization_response)

    # Build the YouTube API client
    youtube = build(API_SERVICE_NAME, API_VERSION, credentials=flow.credentials)
    print(youtube)

    data = request.get_json()
    song_titles = data.get('songs', [])
    selected_playlist = data.get('selected_playlist', '')
    
    print("Received Song Titles:", song_titles)
    pid = create_playlist(youtube, selected_playlist)

    # Emit initial message
    socketio.emit('copy_playlist_message', {'message': 'Copying playlist...'}, namespace='/')

    # Simulate a long-running process (replace this with your actual copy_playlist() logic)
    for title in song_titles:
        print(f"Copying song: {title}")
        copy_playlist_by_song(youtube, title, pid)
        socketio.emit('copy_playlist_message', {'message': f"Copying: {title}"}, namespace='/')
        time.sleep(1)  # Add a short delay to simulate processing time

    socketio.emit('copy_playlist_message', {'message': 'Playlist copied successfully!'}, namespace='/')

    return jsonify({"Copy status": "Playlist copied successfully!"})

def extract_video_id(link):
    # Extract the video ID from a YouTube link
    match = re.search(r"v=([a-zA-Z0-9_-]+)", link)
    return match.group(1) if match else None

def add_songs_to_playlist(youtube, playlist_id, video_ids):
    # Add a video to the specified playlist
    for video_id in video_ids :
        request = youtube.playlistItems().insert(
            part="snippet",
            body={
                "snippet": {
                    "playlistId": playlist_id,
                    "resourceId": {
                        "kind": "youtube#video",
                        "videoId": video_id
                    }
                }
            }
        )
        request.execute()


def search_youtube_music(title):
    try:
        # Create a VideosSearch object with the title
        videos_search = VideosSearch(title, limit=1)

        # Check if there are any search results
        if 'result' in videos_search.result() and videos_search.result()['result']:
            result = videos_search.result()['result'][0]
            # Print video details
            print("Title:", result['title'])
            print("Video URL:", result['link'])
            return extract_video_id(result['link'])
        else:
            print("No search results found for:", title)
            return None

    except Exception as e:
        print("Error:", e)
        return None



def copy_playlist(song_titles, playlist_name):
    youtube = authenticate()

    pid = create_playlist(youtube, playlist_name)

    video_ids = []
    for title in song_titles:
        vid = search_youtube_music(title=title)

        if vid is not None:
            video_ids.append(vid)
            message = f"{title} added to the queue"
            socketio.emit('update_message', {'message': message})
        else:
            message = f"Could not find video for: {title}, Trying again !"
            socketio.emit('update_message', {'message': message})
            vid = search_youtube_music(title=title[:title.rfind("(")-1])
            if vid is not None:
                video_ids.append(vid)
                

    # Add songs to the previously created playlist
    add_songs_to_playlist(youtube, pid, video_ids)
    print(f"All songs added to the playlist (ID: {pid})!")


def copy_playlist_by_song(youtube, title, pid):

    vid = search_youtube_music(title=title)

    if vid is not None:
        video_id = vid
        print(f"{title} added to the queue")
    else:
        print(f"Could not find video for: {title}, Trying again !")
        vid = search_youtube_music(title=title[:title.rfind("(")-1])
        if vid is not None:
            video_id = vid

    # Add a video to the specified playlist
    request = youtube.playlistItems().insert(
        part="snippet",
        body={
            "snippet": {
                "playlistId": pid,
                "resourceId": {
                    "kind": "youtube#video",
                    "videoId": video_id
                }
            }
        }
    )
    request.execute()
    print(f"{title} added to the playlist (ID: {pid})!")


def final_dup (song_titles, playlist_name) :
    youtube = authenticate()

    # Create the playlist and get the playlist ID
    pid = create_playlist(youtube, playlist_name)

    for title in song_titles:
        try:
            copy_playlist_by_song(youtube, title, pid)
        except Exception as e :
            print(f"Error: {e}")
    print("Copied playlist")

def run_spotify():
    # Get the user's playlists
    playlists = sp.current_user_playlists()
    playlist_names = []

    # Print the names of the playlists
    if playlists['items']:
        print(f"{sp.me()['display_name']}'s Playlists:")
        for index, playlist in enumerate(playlists['items']):
            print(f"- {index}. {playlist['name']} (ID: {playlist['id']})")
            playlist_names.append(playlist['name'])
        return playlist_names
    else:
        print("No playlists found for the user.")
        return None

def get_songs(playlist_name):
    playlists = sp.current_user_playlists()

    for index, playlist in enumerate(playlists['items']):
        if playlist['name'] == playlist_name:
            playlist_id = playlist['id']
            break
    else:
        print("Invalid playlist name.")
        return None

    # Get the tracks from the chosen playlist with pagination
    names = []
    offset = 0
    while True:
        tracks = sp.playlist_tracks(playlist_id, offset=offset)
        if not tracks['items']:
            break

        for track in tracks['items']:
            track_name = track['track']['name']
            artists = ', '.join([artist['name'] for artist in track['track']['artists']])
            album = track['track']['album']['name']

            if "’" in track_name:
                track_name = track_name.replace("’", "'")

            if "(From" in track_name:
                names.append(track_name + " by " + artists)
            else:
                names.append(track_name + f' (From "{album}") by ' + artists)

        offset += len(tracks['items'])

    return names

@app.route('/', methods=['GET', 'POST'])
def home():
    form = LoginForm()

    if form.validate_on_submit():
        # Get the selected playlist from the form
        selected_playlist = form.playlist.data

        # Call the get_songs function to get the songs for the selected playlist
        songs = get_songs(selected_playlist)

        # Render the template with the selected playlist and songs
        return render_template('page2.html', selected_playlist=selected_playlist, songs=songs)

    if 'token_info' in session:
        # User is logged in, show the form
        playlists = run_spotify()
        form.playlist.choices = [(playlist, playlist) for playlist in playlists]
        return render_template('page1.html', form=form)
    else:
        # User is not logged in, show login button
        return render_template('index.html')

@app.route('/callback')
def callback():
    auth_manager = SpotifyOAuth(client_id=client_id,
                                client_secret=client_secret,
                                redirect_uri=redirect_uri,
                                scope='playlist-read-private playlist-read-collaborative',
                                open_browser=True,
                                show_dialog=True)

    token_info = auth_manager.get_access_token(request.args['code'])
    session['token_info'] = token_info

    return redirect(url_for('home'))

@app.route('/convert', methods=['POST'])
def convert():
    # Get the selected playlist from the form
    selected_playlist = request.form['playlist']

    # Call the run_spotify function to get the playlists

    # Call the get_songs function to get the songs for the selected playlist
    songs = get_songs(selected_playlist)

    # Render the template with the selected playlist and songs
    return render_template('page2.html', selected_playlist=selected_playlist, songs=songs)

@app.errorhandler(Exception)
def handle_error(e):
    app.logger.error(f"An error occurred: {str(e)}")
    # Log more details, if needed
    app.logger.exception(e)
    return 'Internal Server Error', 500


if __name__ == "__main__":
    socketio.run(app, debug=True, port=5000)
