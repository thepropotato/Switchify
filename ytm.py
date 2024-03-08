import os
import google.oauth2.credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from youtubesearchpython import VideosSearch
import csv
from app import socketio
import re

# Set up the OAuth flow for the first time
SCOPES = ["https://www.googleapis.com/auth/youtube.force-ssl"]
API_SERVICE_NAME = "youtube"
API_VERSION = "v3"

def authenticate():
    # Provide your client secret directly in the code (not recommended for production)
    client_secret = {
        "installed": {
            "client_id": "198293411953-bea77l744kbt4lvs01ptd0fpbk9d33ib.apps.googleusercontent.com",
            "project_id": "youtube-playlist-406517",
            "auth_uri": "https://accounts.google.com/o/oauth2/auth",
            "token_uri": "https://oauth2.googleapis.com/token",
            "auth_provider_x509_cert_url": "https://www.googleapis.com/oauth2/v1/certs",
            "client_secret": "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",
            "redirect_uris": ["http://localhost"]
        }
    }

    # Set up OAuth credentials
    flow = InstalledAppFlow.from_client_config(client_secret, SCOPES)
    credentials = flow.run_local_server(port=8080)

    # Build the YouTube API client
    youtube = build(API_SERVICE_NAME, API_VERSION, credentials=credentials)
    return youtube


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