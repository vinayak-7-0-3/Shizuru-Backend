import aiohttp
import asyncio
import re
import time

from .models import *
from ..utils.errors import AppleMusicError

class AppleMusic:
    def __init__(self, session: aiohttp.ClientSession, dev_token: Optional[str] = None, storefronts: Optional[List[str]] = None):
        self.storefronts = storefronts or ['us', 'in', 'jp']
        self.dev_token = dev_token
        self.dev_token_expiry = 0  # UNIX timestamp
        self.session = session

    async def _ensure_token(self):
        now = int(time.time())
        if not self.dev_token or now >= self.dev_token_expiry:
            self.dev_token, self.dev_token_expiry = await self.get_token()

    def _headers(self) -> Dict[str, str]:
        headers = {
            'Authorization': f'Bearer {self.dev_token}',
            'Origin': 'https://music.apple.com',
            'User-Agent': 'Mozilla/5.0',
        }
        return headers

    async def _get(self, endpoint: str, params: Optional[Dict] = None):
        await self._ensure_token()
        last_exception = None

        for storefront in self.storefronts[:3]:  # Try up to 3 storefronts
            url = f"https://amp-api.music.apple.com/v1/catalog/{storefront}/{endpoint.lstrip('/')}"
            try:
                async with self.session.get(url, headers=self._headers(), params=params) as resp:
                    if resp.status == 404:
                        continue
                    if resp.status == 429:
                        retry_after = int(resp.headers.get("Retry-After", "30"))
                        await asyncio.sleep(retry_after)
                        continue
                    resp.raise_for_status()
                    return await resp.json()
            except aiohttp.ClientResponseError as e:
                last_exception = e
                continue

        raise AppleMusicError(f'Failed to fetch metadata - {last_exception if last_exception else ''}') 

    def get_artwork_url(self, artwork_data: Optional[Dict], size: int = 1200) -> Optional[str]:
        if not artwork_data or 'url' not in artwork_data:
            return None
        url = artwork_data['url']
        return url.replace('{w}', str(size)).replace('{h}', str(size))


    async def search(self, term: str, types: str = "songs", limit: int = 1):
        """
        Search using query
        Args:
            term: query
            types: query type (songs|albums|artits).
                You can combine this using commas - example : songs,albums,artists
            limit: no. of results
        """
        endpoint = "search"
        params = {
            'term': term,
            'types': types,
            'limit': limit
        }

        resp = await self._get(endpoint, params)

        try:
            track_id = resp['results']['songs'].get('data', [])[0].get('id')
        except KeyError:
            raise AppleMusicError(f"Track not found : {term}")

        if track_id:
            track_data = await self.get_song(track_id)
            track_data = track_data['data'][0]
            cover_url = self.get_artwork_url(track_data['attributes'].get('artwork'))
            return BaseTrack(
                title=track_data['attributes']['name'],
                track_id=track_id,
                artist=track_data['attributes']['artistName'],
                artist_id=track_data['relationships']['artists']['data'][0]['id'], #assumign first one will always be main artist
                album=track_data['attributes']['albumName'],
                album_id=track_data['relationships']['albums']['data'][0]['id'],
                isrc=track_data['attributes']['isrc'],
                track_no=track_data['attributes']['trackNumber'],
                provider='apple-music',
                duration=track_data['attributes']['durationInMillis'],
                cover_url=cover_url,
                tags=track_data['attributes']['genreNames']
            )


    async def get_song(self, song_id: str):
        """Get song using apple music id"""
        endpoint = f"songs/{song_id}"
        return await self._get(endpoint)


    async def get_album(self, album_id: str):
        """Get album using apple music id"""
        endpoint = f"albums/{album_id}"
        album_data = await self._get(endpoint)
        album_data = album_data['data'][0]

        cover_url = self.get_artwork_url(album_data['attributes'].get('artwork'))

        try:
            artist_id = album_data['relationships']['artists']['data'][0]['id']
        except:
            artist_id = '0' # fallback for various artist 
        return BaseAlbum(
            title=album_data['attributes']['name'],
            album_id=album_id,
            artist=album_data['attributes']['artistName'],
            artist_id=artist_id,
            provider='apple-music',
            upc=album_data['attributes'].get('upc'),
            tags=album_data['attributes']['genreNames'],
            cover_url=cover_url,
            track_count=album_data['attributes']['trackCount']
        )


    async def get_artist(self, artist_id: str):
        endpoint = f"artists/{artist_id}"
        artist_data = await self._get(endpoint)
        artist_data = artist_data['data'][0]

        cover_url = self.get_artwork_url(artist_data['attributes'].get('artwork'))
        
        return BaseArtist(
            name=artist_data['attributes']['name'],
            artist_id=artist_id,
            provider='apple-music',
            tags=artist_data['attributes']['genreNames'],
            cover_url=cover_url
        )




    async def get_token(self) -> (str, int):
        main_page_url = 'https://beta.music.apple.com'

        async with self.session.get(main_page_url) as main_resp:
            if main_resp.status != 200:
                raise AppleMusicError(f"Login : Failed to fetch main page: {main_resp.status}")
            main_page_body = await main_resp.text()

        js_file_match = re.search(r'/assets/index.*\.js', main_page_body)
        if not js_file_match:
            raise AppleMusicError("Login : Index JS file not found")

        js_file_url = main_page_url + js_file_match.group(0)

        async with self.session.get(js_file_url) as js_resp:
            if js_resp.status != 200:
                raise AppleMusicError(f"Login : Failed to fetch JS file: {js_resp.status}")
            js_file_body = await js_resp.text()

        token_match = re.search(r'eyJ[a-zA-Z0-9\-_\.]+', js_file_body)

        if not token_match:
            raise AppleMusicError("Login : Token not Found")

        token = token_match.group(0)
        # Approximate expiry: Apple tokens are usually valid for 1 hour (3600 seconds)
        expiry = int(time.time()) + 3600 - 60  # refresh a bit early
        return token, expiry