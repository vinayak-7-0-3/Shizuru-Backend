import re
import secrets
import mimetypes
import os
from email.utils import formatdate
from urllib.parse import quote, unquote

from fastapi import APIRouter, Request, Response, HTTPException, Depends, status
from fastapi.security import HTTPBasic, HTTPBasicCredentials

from config import Config
from ...database.connection import mongo
from ...database.models import DBTrack
from .songs import stream_song
from ...logger import LOGGER

router = APIRouter()
security = HTTPBasic()

# Relaxed regex: Matches "Anything [ID].ext"
FILENAME_REGEX = re.compile(r"(.+) \[(.+)\]\.(\w+)$")

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
        
        if name == "":
            href = base_url
        else:
            href = base_url + quote(name)
            
        xml_lines.append('<D:response>')
        xml_lines.append(f'<D:href>{href}</D:href>')
        xml_lines.append('<D:propstat>')
        xml_lines.append('<D:prop>')
        
        # Display Name
        disp = name if name else unquote(base_url.rstrip('/').split('/')[-1]) or "webdav"
        xml_lines.append(f'<D:displayname>{disp}</D:displayname>')
        
        if is_dir:
            xml_lines.append('<D:resourcetype><D:collection/></D:resourcetype>')
        else:
            xml_lines.append('<D:resourcetype/>')
            # Content Length
            if 'size' in res and res['size'] is not None:
                xml_lines.append(f'<D:getcontentlength>{res["size"]}</D:getcontentlength>')
            # Content Type
            if 'mimetype' in res and res['mimetype']:
                xml_lines.append(f'<D:getcontenttype>{res["mimetype"]}</D:getcontenttype>')
        
        # Dates
        if 'last_modified' in res and res['last_modified']:
            # RFC 1123 format for getlastmodified
            # timestamp in seconds
            ts = res['last_modified'].timestamp()
            fmt = formatdate(timeval=ts, localtime=False, usegmt=True)
            xml_lines.append(f'<D:getlastmodified>{fmt}</D:getlastmodified>')
            
        if 'created_at' in res and res['created_at']:
            # ISO 8601 for creationdate
            fmt = res['created_at'].strftime('%Y-%m-%dT%H:%M:%SZ')
            xml_lines.append(f'<D:creationdate>{fmt}</D:creationdate>')

        if 'etag' in res and res['etag']:
            # ETag must be quoted
            xml_lines.append(f'<D:getetag>"{res["etag"]}"</D:getetag>')

        xml_lines.append('</D:prop>')
        xml_lines.append('<D:status>HTTP/1.1 200 OK</D:status>')
        xml_lines.append('</D:propstat>')
        xml_lines.append('</D:response>')
        
    xml_lines.append('</D:multistatus>')
    return "\n".join(xml_lines)

@router.api_route("/webdav/{path:path}", methods=["GET", "HEAD", "PROPFIND", "OPTIONS"])
async def webdav_handler(path: str, request: Request, username: str = Depends(check_auth)):
    path = unquote(path)
    # Remove trailing slash for consistency in logic, but keep track if needed
    clean_path = path.rstrip('/')
    
    # Base URL construction
    # If request is /webdav, base_url is .../webdav/
    # If request is /webdav/, base_url is .../webdav/
    base_url = str(request.base_url) + "webdav/"
    
    # Resource URL is what we are "at"
    if clean_path:
        resource_url = base_url + quote(clean_path)
    else:
        resource_url = base_url

    method = request.method

    if method == "OPTIONS":
        return Response(headers={
            "Allow": "GET, HEAD, PROPFIND, OPTIONS",
            "DAV": "1",
            "MS-Author-Via": "DAV"
        })

    if method == "PROPFIND":
        depth = request.headers.get("Depth", "1")
        
        # Root Listing
        if clean_path == "":
             resources = [
                 {'name': '', 'is_dir': True} # Self
             ]
             if depth != '0':
                 # Children
                 resources.append({'name': 'All Songs', 'is_dir': True})
                 
             xml_content = generate_propfind_xml(resources, base_url, is_collection=True)
             return Response(content=xml_content, media_type="application/xml; charset=utf-8", status_code=207)
        
        elif clean_path == "All Songs":
             resources = [
                 {'name': '', 'is_dir': True} # Self
             ]
             if depth != '0':
                 # List songs
                 # Fetch songs that have file_unique_id
                 limit = 500
                 cursor = mongo.db["songs"].find({"file_unique_id": {"$ne": None}, "file_size": {"$ne": None}}).limit(limit)
                 async for song_doc in cursor:
                     song = DBTrack(**song_doc)
                     safe_title = re.sub(r'[\\/*?:"<>|]', "", song.title).strip()
                     safe_artist = re.sub(r'[\\/*?:"<>|]', "", song.artist or "Unknown").strip()
                     
                     # Determine extension
                     ext = ".mp3"
                     if song.file_name:
                          _, ext_val = os.path.splitext(song.file_name)
                          if ext_val:
                              ext = ext_val
                     elif song.mime_type:
                          guess = mimetypes.guess_extension(song.mime_type)
                          if guess:
                              ext = guess
                              
                     name = f"{safe_title} - {safe_artist} [{song.file_unique_id}]{ext}"
                     
                     resources.append({
                         'name': name,
                         'is_dir': False,
                         'size': song.file_size,
                         'mimetype': song.mime_type,
                         'created_at': song.created_at,
                         'last_modified': song.updated_at,
                         'etag': song.file_unique_id
                     })
             
             xml_content = generate_propfind_xml(resources, resource_url, is_collection=True)
             return Response(content=xml_content, media_type="application/xml; charset=utf-8", status_code=207)
        
        else:
            # Check if it matches a file in "All Songs"
            # clean_path "All Songs/Title..."
            parts = clean_path.split('/')
            if len(parts) == 2 and parts[0] == "All Songs":
                filename = parts[1]
                match = FILENAME_REGEX.match(filename)
                if match:
                    file_unique_id = match.group(2)
                    song_doc = await mongo.db["songs"].find_one({"file_unique_id": file_unique_id})
                    if song_doc:
                        song = DBTrack(**song_doc)
                        resources = [{
                             'name': '', # Self
                             'is_dir': False,
                             'size': song.file_size,
                             'mimetype': song.mime_type,
                             'created_at': song.created_at,
                             'last_modified': song.updated_at,
                             'etag': song.file_unique_id
                        }]
                        xml_content = generate_propfind_xml(resources, resource_url, is_collection=False)
                        return Response(content=xml_content, media_type="application/xml; charset=utf-8", status_code=207)

            raise HTTPException(status_code=404, detail="Not Found")

    if method == "GET" or method == "HEAD":
        # Handle collections
        if clean_path == "" or clean_path == "All Songs":
             return Response(content="WebDAV Collection", media_type="text/plain")

        parts = clean_path.split('/')
        if len(parts) == 2 and parts[0] == "All Songs":
            filename = parts[1]
            match = FILENAME_REGEX.match(filename)
            if match:
                file_unique_id = match.group(2)
                LOGGER.info(f"WebDAV Streaming: {filename} -> {file_unique_id}")
                try:
                    return await stream_song(file_unique_id, request)
                except HTTPException as e:
                    LOGGER.error(f"Stream Error: {e.detail}")
                    raise e
            else:
                LOGGER.warning(f"WebDAV Filename mismatch: {filename}")
        else:
            LOGGER.warning(f"WebDAV Invalid Path Structure: {clean_path} ->Parts: {parts}")
        
        raise HTTPException(status_code=404, detail="File Not Found")

