from __future__ import annotations

from dataclasses import dataclass
from typing import Iterator

import httpx

from app.config import settings
from app.db import SessionLocal
from app.services.drive_oauth_service import DriveNotConnectedError, get_drive_credentials


DRIVE_FILES_BASE = 'https://www.googleapis.com/drive/v3/files'
DRIVE_UPLOAD_BASE = 'https://www.googleapis.com/upload/drive/v3/files'


class DriveStorageError(RuntimeError):
    pass


@dataclass
class DriveStreamPayload:
    chunks: Iterator[bytes]
    mime_type: str
    file_size: int | None
    filename: str


def _timeout() -> float:
    return 60.0


def _access_token(user_id: int | None) -> str:
    db = SessionLocal()
    try:
        credentials = get_drive_credentials(db, user_id=user_id)
        if not credentials.token:
            raise DriveStorageError('Failed to acquire Drive access token')
        return credentials.token
    except DriveNotConnectedError:
        raise
    except Exception as exc:
        raise DriveStorageError(f'Failed to load Drive credentials: {exc}') from exc
    finally:
        db.close()


def upload_file(file_stream: bytes, filename: str, mime_type: str, user_id: int | None = None) -> dict:
    if not file_stream:
        raise DriveStorageError('Cannot upload empty file')

    token = _access_token(user_id)
    headers = {'Authorization': f'Bearer {token}'}
    metadata: dict[str, object] = {'name': filename or 'note.pdf'}
    if settings.google_drive_folder_id:
        metadata['parents'] = [settings.google_drive_folder_id]

    with httpx.Client(timeout=_timeout()) as client:
        create_resp = client.post(
            DRIVE_FILES_BASE,
            headers=headers,
            params={'fields': 'id,webViewLink'},
            json=metadata,
        )
        if create_resp.status_code >= 300:
            raise DriveStorageError(f'Drive metadata upload failed: {create_resp.text[:300]}')
        file_id = create_resp.json().get('id')
        if not file_id:
            raise DriveStorageError('Drive did not return file id')

        media_resp = client.patch(
            f'{DRIVE_UPLOAD_BASE}/{file_id}',
            headers={
                'Authorization': f'Bearer {token}',
                'Content-Type': mime_type or 'application/pdf',
            },
            params={'uploadType': 'media'},
            content=file_stream,
        )
        if media_resp.status_code >= 300:
            client.delete(f'{DRIVE_FILES_BASE}/{file_id}', headers=headers)
            raise DriveStorageError(f'Drive file upload failed: {media_resp.text[:300]}')

        view_resp = client.get(
            f'{DRIVE_FILES_BASE}/{file_id}',
            headers=headers,
            params={'fields': 'id,webViewLink'},
        )
        web_view_link = None
        if view_resp.status_code < 300:
            web_view_link = view_resp.json().get('webViewLink')

    return {'file_id': str(file_id), 'web_view_link': web_view_link}


def stream_file(file_id: str, user_id: int | None = None) -> DriveStreamPayload:
    if not file_id:
        raise DriveStorageError('Missing Drive file id')

    token = _access_token(user_id)
    client = httpx.Client(timeout=_timeout())
    response = client.stream(
        'GET',
        f'{DRIVE_FILES_BASE}/{file_id}',
        headers={'Authorization': f'Bearer {token}'},
        params={'alt': 'media'},
    )
    stream_ctx = response.__enter__()

    if stream_ctx.status_code >= 300:
        try:
            message = stream_ctx.text
        except Exception:
            message = 'Drive request failed'
        response.__exit__(None, None, None)
        client.close()
        raise DriveStorageError(f'Drive download failed: {message[:300]}')

    def iterator() -> Iterator[bytes]:
        try:
            for chunk in stream_ctx.iter_bytes(chunk_size=64 * 1024):
                if chunk:
                    yield chunk
        finally:
            response.__exit__(None, None, None)
            client.close()

    content_length = stream_ctx.headers.get('Content-Length')
    return DriveStreamPayload(
        chunks=iterator(),
        mime_type=stream_ctx.headers.get('Content-Type') or 'application/pdf',
        file_size=int(content_length) if content_length and content_length.isdigit() else None,
        filename=f'{file_id}.pdf',
    )


def delete_file(file_id: str, user_id: int | None = None) -> None:
    if not file_id:
        return

    token = _access_token(user_id)
    with httpx.Client(timeout=_timeout()) as client:
        response = client.delete(
            f'{DRIVE_FILES_BASE}/{file_id}',
            headers={'Authorization': f'Bearer {token}'},
        )
        # If file is already gone, proceed with DB cleanup.
        if response.status_code in (200, 204, 404):
            return
        raise DriveStorageError(f'Drive delete failed: {response.text[:300]}')
