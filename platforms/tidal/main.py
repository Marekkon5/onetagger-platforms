import tidalapi
import onetagger
from datetime import datetime

SESSION = None

# Get tidal session
def get_session():
    config = tidalapi.Config(quality=tidalapi.Quality.low_320k, video_quality=tidalapi.VideoQuality.low)
    return tidalapi.Session(config)

# Create tidal session from config
def session_from_config(config):
    session = get_session()
    session.load_oauth_session(config['token_type'], config['access_token'], config['refresh_token'], datetime.fromtimestamp(float(config['expiry_time'])))
    return session

def cover_url(cover, resolution):
    if cover == None:
        return None
    return f'https://resources.tidal.com/images/{cover.replace("-", "/")}/{resolution}x{resolution}.jpg'

def match_track(info, config):
    custom_config = config.getcustom('tidal')
    session = session_from_config(custom_config)
    results: list[tidalapi.Track] = session.search(f'{info.artist()} {info.title()}', [tidalapi.Track], limit=1)['tracks']
    
    # Map results
    tracks = []
    for track in results:
        tracks.append(onetagger.new_track(
            platform = 'tidal',
            title = track.name,
            url = track.get_url(),
            duration = float(track.duration),
            track_number = track.track_num,
            artists = [a.name for a in track.artists],
            album = track.album.name,
            release_id = str(track.album.id),
            track_id = str(track.id),
            isrc = track.isrc,
            version = track.version,
            explicit = track.explicit,
            art = cover_url(track.album.cover, 1280),
            thumbnail = cover_url(track.album.cover, 320)
        ))

    return onetagger.match_tracks(info, tracks, config, True)

def extend_track(track, config):
    return track

def config_callback(name, config):
    global SESSION 

    # Generate login URL and open
    if name == 'login':
        session = get_session()
        login, future = session.login_oauth()
        url = login.verification_uri_complete
        if 'http' not in url:
            url = f'https://{url}'
        onetagger.browser(url)
        future.result()

        # Save global session
        SESSION = session
        return
    
    # Check if the session authenticated
    if name == 'check':
        if SESSION == None:
            raise Exception('Click login button first')
        print(SESSION.check_login())

        # Update config
        if SESSION.check_login():
            return {
                'token_type': SESSION.token_type,
                'access_token': SESSION.access_token,
                'refresh_token': SESSION.refresh_token,
                'expiry_time': str(datetime.timestamp(SESSION.expiry_time))
            }
