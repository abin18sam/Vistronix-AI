import json
import os
import sys
import time
import urllib.request
import urllib.error
import uuid
from pathlib import Path

import fitz

BASE_URL = os.environ.get('API_BASE_URL', 'http://127.0.0.1:8001')


def request_json(method: str, url: str, data: bytes | None = None, headers: dict[str, str] | None = None):
    req = urllib.request.Request(url, data=data, headers=headers or {}, method=method)
    try:
        with urllib.request.urlopen(req, timeout=40) as resp:
            body = resp.read().decode('utf-8')
            if body:
                return resp.status, json.loads(body)
            return resp.status, {}
    except urllib.error.HTTPError as exc:
        body = exc.read().decode('utf-8', 'replace')
        try:
            payload = json.loads(body) if body else {}
        except Exception:
            payload = {'raw': body}
        return exc.code, payload
    except Exception as exc:
        raise RuntimeError(f'{method} {url} failed: {exc}') from exc


def wait_until(predicate, timeout=180, interval=1.0):
    deadline = time.time() + timeout
    last = None
    while time.time() < deadline:
        try:
            value = predicate()
            if value is not None:
                return value
            last = value
        except Exception as exc:
            last = exc
        time.sleep(interval)
    raise TimeoutError(f'Condition not met before timeout: {last}')


def create_pdf(path: Path):
    doc = fitz.open()
    page = doc.new_page()
    page.insert_text((72, 72), 'Physics and Force')
    doc.save(path)
    doc.close()


def main():
    print(f'Using API base URL: {BASE_URL}')
    print('Health:', request_json('GET', f'{BASE_URL}/health'))

    pdf_path = Path('tmp_live_test.pdf')
    create_pdf(pdf_path)
    payload = pdf_path.read_bytes()
    boundary = '----VisTronixRuntimeBoundary'
    body = (
        ('--' + boundary + '\r\n'
         'Content-Disposition: form-data; name="file"; filename="tmp_live_test.pdf"\r\n'
         'Content-Type: application/pdf\r\n\r\n').encode('utf-8')
        + payload + b'\r\n--' + boundary.encode('utf-8') + b'--\r\n'
    )
    status, upload = request_json('POST', f'{BASE_URL}/documents', data=body, headers={'Content-Type': f'multipart/form-data; boundary={boundary}'})
    print('Upload response:', status, upload)
    if status not in (200, 202):
        raise SystemExit(f'Upload failed: {status} {upload}')
    document_id = upload['document_id']
    job_id = upload['job_id']
    print(f'Document ID: {document_id}, Job ID: {job_id}')

    def parse_status():
        status_code, payload = request_json('GET', f'{BASE_URL}/documents/{document_id}/status')
        print('Parse status poll ->', status_code, payload)
        if status_code == 200 and payload.get('status') in {'completed', 'failed'}:
            return payload
        return None

    state = wait_until(parse_status, timeout=180, interval=2)
    if state.get('status') != 'completed':
        raise SystemExit(f'Parse did not complete: {state}')

    print('Trigger understand:')
    status_code, understand = request_json('POST', f'{BASE_URL}/documents/{document_id}/understand')
    print(status_code, understand)
    if status_code not in (200, 202):
        raise SystemExit(f'Understand request failed: {status_code} {understand}')

    def understand_status():
        status_code, payload = request_json('GET', f'{BASE_URL}/documents/{document_id}/status')
        print('Understand status poll ->', status_code, payload)
        if status_code == 200 and payload.get('status') in {'completed', 'failed'}:
            return payload
        return None

    state = wait_until(understand_status, timeout=180, interval=2)
    print('Final understanding job state:', state)
    if state.get('status') == 'failed':
        raise SystemExit(f'Understand job failed: {state}')

    kg = request_json('GET', f'{BASE_URL}/documents/{document_id}/knowledge-graph')
    print('Knowledge graph result:', kg)
    if kg[0] != 200:
        raise SystemExit(f'Knowledge graph fetch failed: {kg}')

    artifact_dir = Path('storage') / 'documents' / document_id / 'understanding'
    print('Artifact dir exists:', artifact_dir.exists())
    if artifact_dir.exists():
        for child in sorted(artifact_dir.iterdir()):
            print('Artifact:', child.name, child.stat().st_size)

    print('DONE')


if __name__ == '__main__':
    try:
        main()
    except Exception as exc:
        print(f'RUNTIME_CHECK_FAILED: {exc}', file=sys.stderr)
        raise
