from flask import jsonify,Flask, render_template, redirect, url_for, request, session
from flask_wtf import FlaskForm
from wtforms import SelectField, SubmitField
import spotipy
from spotipy.oauth2 import SpotifyOAuth
import os
import ytm
from flask import jsonify
from flask_socketio import emit
from flask_socketio import SocketIO
from flask import copy_current_request_context
import time

app = Flask(__name__)
app.config['SECRET_KEY'] = 'your_secret_key'

socketio = SocketIO(app, async_mode=None, engineio_logger=True)

# Replace these values with your own
client_id = '27301e2211b74792a852693dd9cc95bc'
client_secret = '8f5a80b4723c43ed850713d1b753cbb5'
redirect_uri = 'https://switchifytm.web.app/callback'

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



from flask_socketio import emit

@app.route('/copy-playlist', methods=['POST'])
def copy_playlist_route():
    # Retrieve the song titles from the AJAX request
    data = request.get_json()
    song_titles = data.get('songs', [])
    selected_playlist = data.get('selected_playlist', '')
    
    print("Received Song Titles:", song_titles)
    youtube = ytm.authenticate()
    pid = ytm.create_playlist(youtube, selected_playlist)

    # Emit initial message
    socketio.emit('copy_playlist_message', {'message': 'Copying playlist...'}, namespace='/')

    # Simulate a long-running process (replace this with your actual copy_playlist() logic)
    for title in song_titles:
        print(f"Copying song: {title}")
        ytm.copy_playlist_by_song(youtube, title, pid)
        socketio.emit('copy_playlist_message', {'message': f"Copying: {title}"}, namespace='/')
        time.sleep(1)  # Add a short delay to simulate processing time

    socketio.emit('copy_playlist_message', {'message': 'Playlist copied successfully!'}, namespace='/')

    return jsonify({"Copy status": "Playlist copied successfully!"})



if __name__ == "__main__":
    socketio.run(app, debug=True, port=5000)