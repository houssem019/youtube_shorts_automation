import os
import google_auth_oauthlib.flow
import googleapiclient.discovery
import googleapiclient.errors
from google.oauth2.credentials import Credentials
from google.auth.transport.requests import Request
from google.auth.exceptions import RefreshError
import logging
from config import YOUTUBE_CLIENT_SECRETS_FILE, YOUTUBE_TOKEN_FILE, YOUTUBE_SCOPES

logger = logging.getLogger(__name__)

class YouTubeUploader:
    def __init__(self):
        self.youtube = None

    def authenticate(self):
        """
        Authenticates the user using OAuth 2.0.
        """
        creds = None
        # The file token.json stores the user's access and refresh tokens, and is
        # created automatically when the authorization flow completes for the first
        # time.
        if os.path.exists(YOUTUBE_TOKEN_FILE):
            creds = Credentials.from_authorized_user_file(YOUTUBE_TOKEN_FILE, YOUTUBE_SCOPES)

        # If there are no (valid) credentials available, let the user log in.
        changed = False
        if creds and not creds.valid and creds.expired and creds.refresh_token:
            try:
                creds.refresh(Request())
                changed = True
            except RefreshError as e:
                # expired or revoked: sign in again instead of crashing the run (the video is already made)
                logger.warning(f"The saved YouTube sign-in no longer works ({e}); sign in again in the browser.")
                creds = None
        if not creds or not creds.valid:
            if not os.path.exists(YOUTUBE_CLIENT_SECRETS_FILE):
                logger.error(f"Client secrets file not found at {YOUTUBE_CLIENT_SECRETS_FILE}")
                return False

            flow = google_auth_oauthlib.flow.InstalledAppFlow.from_client_secrets_file(
                YOUTUBE_CLIENT_SECRETS_FILE, YOUTUBE_SCOPES)
            creds = flow.run_local_server(port=0)
            changed = True

        if changed:
            # Save the credentials for the next run
            with open(YOUTUBE_TOKEN_FILE, 'w') as token:
                token.write(creds.to_json())

        try:
            self.youtube = googleapiclient.discovery.build("youtube", "v3", credentials=creds)
            return True
        except Exception as e:
            logger.error(f"Failed to build YouTube service: {e}")
            return False

    def upload_video(self, file_path, title, description, tags=None, category_id="22", privacy_status="private"):
        """
        Uploads a video to YouTube.
        """
        if not self.youtube:
            if not self.authenticate():
                return False

        body = {
            "snippet": {
                "title": title,
                "description": description,
                "tags": tags or [],
                "categoryId": category_id
            },
            "status": {
                "privacyStatus": privacy_status,
                "selfDeclaredMadeForKids": False,
            }
        }

        try:
            logger.info(f"Uploading {file_path}...")
            request = self.youtube.videos().insert(
                part="snippet,status",
                body=body,
                media_body=googleapiclient.http.MediaFileUpload(file_path, chunksize=-1, resumable=True)
            )
            response = None
            while response is None:
                status, response = request.next_chunk()
                if status:
                    logger.info(f"Uploaded {int(status.progress() * 100)}%")

            logger.info(f"Upload Complete! Video ID: {response['id']}")
            return response['id']

        except googleapiclient.errors.HttpError as e:
            logger.error(f"An HTTP error {e.resp.status} occurred: {e.content}")
            return None
        except Exception as e:
            logger.error(f"An error occurred: {e}")
            return None

    def set_thumbnail(self, video_id, image_path):
        """Sets a custom thumbnail. YouTube refuses it (403) until the channel is phone-verified;
        the PNG then stays on disk to be uploaded by hand. Returns True when it was set."""
        try:
            self.youtube.thumbnails().set(
                videoId=video_id,
                media_body=googleapiclient.http.MediaFileUpload(image_path, mimetype="image/png")
            ).execute()
            logger.info("Thumbnail set.")
            return True
        except googleapiclient.errors.HttpError as e:
            logger.warning(f"YouTube did not accept the thumbnail ({e.resp.status}: {e.content}). "
                           f"Upload it by hand in YouTube Studio: {image_path}")
        except Exception as e:
            logger.warning(f"Could not set the thumbnail ({e}). Upload it by hand: {image_path}")
        return False

    def get_playlist_id(self, playlist_title):
        """
        Searches for a playlist by title and returns its ID.
        """
        if not self.youtube:
            if not self.authenticate():
                return None

        try:
            request = self.youtube.playlists().list(
                part="snippet",
                mine=True,
                maxResults=50
            )
            response = request.execute()

            for item in response.get("items", []):
                if item["snippet"]["title"] == playlist_title:
                    return item["id"]
            return None
        except Exception as e:
            logger.error(f"Error searching for playlist: {e}")
            return None

    def add_video_to_playlist(self, video_id, playlist_id):
        """
        Adds a video to a playlist.
        """
        if not self.youtube:
            if not self.authenticate():
                return False

        try:
            request = self.youtube.playlistItems().insert(
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
            logger.info(f"Added video {video_id} to playlist {playlist_id}")
            return True
        except Exception as e:
            logger.error(f"Error adding video to playlist: {e}")
            return False
