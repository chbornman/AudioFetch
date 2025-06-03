"""
Information about various audio players and their characteristics.
"""

PLAYER_INFO = {
    'plyr': {
        'name': 'Plyr',
        'description': 'Modern, accessible HTML5 media player',
        'supported': True,
        'characteristics': [
            'Often used for audiobooks and podcasts',
            'Supports playlists and chapters',
            'May use APIs to load track URLs'
        ]
    },
    'simple_mp3': {
        'name': 'Simple MP3 Links',
        'description': 'Direct MP3 file links on the page',
        'supported': True,
        'characteristics': [
            'Direct download links',
            'No JavaScript required',
            'Preserves original filenames'
        ]
    },
    'howler': {
        'name': 'Howler.js',
        'description': 'JavaScript audio library for the modern web',
        'supported': False,
        'characteristics': [
            'Used by music streaming sites',
            'Game development platforms',
            'Often has custom player UI'
        ]
    },
    'mediaelement': {
        'name': 'MediaElement.js',
        'description': 'HTML5 audio and video player',
        'supported': False,
        'characteristics': [
            'WordPress default player',
            'Educational platforms',
            'Supports multiple formats'
        ]
    },
    'videojs': {
        'name': 'Video.js',
        'description': 'Open source HTML5 video player',
        'supported': False,
        'characteristics': [
            'Used by video platforms',
            'Also handles audio content',
            'Highly customizable'
        ]
    },
    'jwplayer': {
        'name': 'JW Player',
        'description': 'Commercial media player',
        'supported': False,
        'characteristics': [
            'Enterprise platforms',
            'DRM protection common',
            'Complex API'
        ]
    },
    'html5audio': {
        'name': 'HTML5 Audio',
        'description': 'Native HTML5 <audio> elements',
        'supported': False,
        'characteristics': [
            'Basic browser player',
            'No special library needed',
            'Simple implementation'
        ]
    },
    'soundcloud': {
        'name': 'SoundCloud',
        'description': 'SoundCloud embedded player',
        'supported': False,
        'characteristics': [
            'Embedded iframe player',
            'Requires API access',
            'Stream protection'
        ]
    },
    'spotify': {
        'name': 'Spotify',
        'description': 'Spotify embedded player',
        'supported': False,
        'characteristics': [
            'Embedded iframe player',
            'Requires authentication',
            'DRM protected'
        ]
    }
}

def get_player_info(player_id):
    """Get information about a specific player."""
    return PLAYER_INFO.get(player_id, {
        'name': player_id,
        'description': 'Unknown player type',
        'supported': False,
        'characteristics': []
    })