import re
import secrets
from urllib.parse import quote, unquote

from fastapi import APIRouter, Request, Response, HTTPException, Depends, status
from fastapi.security import HTTPBasic, HTTPBasicCredentials

from config import Config
from ...database.connection import mongo
from ...database.models import DBTrack
from .songs import stream_song

router = APIRouter()
security = HTTPBasic()

FILENAME_REGEX = re.compile(r"(.+) - \[(.+)\]\.mp3$")

def check_auth(credentials: HTTPBasicCredentials = Depends(security)):
    if not Config.ENABLE_WEBDAV:
        raise HTTPException(status_code=404, detail="WebDAV not enabled")
    
    current_username = credentials.username.encode("utf8")
    correct_username = Config.WEBDAV_USERNAME.encode("utf8")
    is_correct_username = secrets.compare_digest(current_username, correct_username)
    
    current_password = credentials.password.encode("utf8")
    correct_password = Config.WEBDAV_PASSWORD.encode("utf8")
    is_correct_password = secrets.compare_digest(current_password, correct_password)
    
    if not (is_correct_username and is_correct_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password",
            headers={"WWW-Authenticate": "Basic"},
        )
    return credentials.username

def generate_propfind_xml(resources: list, base_url: str, is_collection: bool = True):
    xml_lines = [
        '<?xml version="1.0" encoding="utf-8" ?>',
        '<D:multistatus xmlns:D="DAV:">'
    ]
    
    # Ensure base_url ends with / if collection
    if is_collection and not base_url.endswith('/'):
        base_url += '/'
        
    for res in resources:
        name = res['name']
        is_dir = res.get('is_dir', False)
        
        # href should be absolute or relative to root? Absolute is safer.
        # If name is empty, it's the requested resource (self)
        if name == "":
            href = base_url
        else:
            href = base_url + quote(name)
            
        xml_lines.append('<D:response>')
        xml_lines.append(f'<D:href>{href}</D:href>')
        xml_lines.append('<D:propstat>')
        xml_lines.append('<D:prop>')
        
        # Display Name
        disp = name if name else "/" # simplistic
        xml_lines.append(f'<D:displayname>{disp}</D:displayname>')
        
        if is_dir:
            xml_lines.append('<D:resourcetype><D:collection/></D:resourcetype>')
        else:
            xml_lines.append('<D:resourcetype/>')
            if 'size' in res:
                xml_lines.append(f'<D:getcontentlength>{res["size"]}</D:getcontentlength>')
            if 'mimetype' in res:
                xml_lines.append(f'<D:getcontenttype>{res["mimetype"]}</D:getcontenttype>')
        
        # Last Modified (optional, can add if available)
                
        xml_lines.append('</D:prop>')
        xml_lines.append('<D:status>HTTP/1.1 200 OK</D:status>')
        xml_lines.append('</D:propstat>')
        xml_lines.append('</D:response>')
        
    xml_lines.append('</D:multistatus>')
    return "\n".join(xml_lines)

@router.api_route("/webdav/{path:path}", methods=["GET", "HEAD", "PROPFIND", "OPTIONS"])
async def webdav_handler(path: str, request: Request, username: str = Depends(check_auth)):
    # Normalize path
    # path comes from {path:path}, so "webdav/foo" -> path="foo"
    # wait. Route is prefix /webdav, so path is what follows.
    
    path = unquote(path)
    path = path.strip('/')
    method = request.method
    
    base_url = str(request.base_url) + "webdav/"
    if path:
        resource_url = base_url + quote(path)
    else:
        resource_url = base_url

    if method == "OPTIONS":
        return Response(headers={
            "Allow": "GET, HEAD, PROPFIND, OPTIONS",
            "DAV": "1",
            "MS-Author-Via": "DAV"
        })

    if method == "PROPFIND":
        depth = request.headers.get("Depth", "1")
        
        # Root Listing
        if path == "":
             resources = [
                 {'name': '', 'is_dir': True} # Self
             ]
             if depth != '0':
                 # Children
                 resources.append({'name': 'All Songs', 'is_dir': True})
                 
             xml_content = generate_propfind_xml(resources, base_url)
             return Response(content=xml_content, media_type="application/xml; charset=utf-8", status_code=207)
        
        elif path == "All Songs":
             resources = [
                 {'name': '', 'is_dir': True} # Self
             ]
             if depth != '0':
                 # List songs
                 # Fetch all songs (beware limits)
                 limit = 500
                 cursor = mongo.db["songs"].find().limit(limit)
                 async for song_doc in cursor:
                     song = DBTrack(**song_doc)
                     # Construct filename: Title - Artist [file_unique_id].mp3
                     # Only allow safe chars in filename?
                     safe_title = re.sub(r'[\\/*?:"<>|]', "", song.title)
                     safe_artist = re.sub(r'[\\/*?:"<>|]', "", song.artist or "Unknown")
                     name = f"{safe_title} - {safe_artist} [{song.file_unique_id}].mp3"
                     
                     resources.append({
                         'name': name,
                         'is_dir': False,
                         'size': song.file_size,
                         'mimetype': song.mime_type
                     })
             
             xml_content = generate_propfind_xml(resources, resource_url, True)
             return Response(content=xml_content, media_type="application/xml; charset=utf-8", status_code=207)
        
        else:
            # Check if it matches a file in "All Songs"
            # path would be "All Songs/Title - Artist [id].mp3"
            parts = path.split('/')
            if len(parts) == 2 and parts[0] == "All Songs":
                filename = parts[1]
                match = FILENAME_REGEX.match(filename)
                if match:
                    # It's a file
                    # PROPFIND on a file with Depth 0 or 1 returns the file properties
                    # We need to fetch details to get size etc?
                    # Ideally we parse ID and fetch.
                    file_unique_id = match.group(2)
                    song_doc = await mongo.db["songs"].find_one({"file_unique_id": file_unique_id})
                    if song_doc:
                        song = DBTrack(**song_doc)
                        resources = [{
                             'name': '', # Self relative to the URL
                             'is_dir': False,
                             'size': song.file_size,
                             'mimetype': song.mime_type
                        }]
                        # The base url for this resource
                        xml_content = generate_propfind_xml(resources, resource_url, False)
                        return Response(content=xml_content, media_type="application/xml; charset=utf-8", status_code=207)

            raise HTTPException(status_code=404, detail="Not Found")

    if method == "GET" or method == "HEAD":
        # Handle "All Songs/Title - Artist [id].mp3"
        parts = path.split('/')
        if len(parts) == 2 and parts[0] == "All Songs":
            filename = parts[1]
            match = FILENAME_REGEX.match(filename)
            if match:
                file_unique_id = match.group(2)
                # Delegate to stream_song
                return await stream_song(file_unique_id, request)
        
        raise HTTPException(status_code=404, detail="File Not Found")

