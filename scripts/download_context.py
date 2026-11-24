#!/usr/bin/env python3
"""Download optional official Sri Lanka district context; no API key required."""
import hashlib
import json
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RAW = ROOT / 'data/raw/geoboundaries'
API = 'https://www.geoboundaries.org/api/current/gbOpen/LKA/ADM2/'

def read(url):
    request = urllib.request.Request(url, headers={'User-Agent': 'RELINK-research-data-preparation/0.1'})
    with urllib.request.urlopen(request, timeout=45) as response:
        return response.read(), response.geturl()

def download():
    if (ROOT / 'docs/evaluation/FROZEN_DATASET.json').exists():
        raise ValueError('Dataset release is frozen. Create a reviewed new version instead of regenerating in place.')
    RAW.mkdir(parents=True, exist_ok=True)
    metadata_bytes, resolved = read(API)
    metadata = json.loads(metadata_bytes)
    (RAW / 'metadata.json').write_bytes(metadata_bytes)
    geometry_url = metadata['simplifiedGeometryGeoJSON']
    try:
        geometry_bytes, geometry_resolved = read(geometry_url)
        if geometry_bytes.startswith(b'version https://git-lfs'):
            raise ValueError('Git LFS pointer returned instead of actual geometry')
    except (urllib.error.HTTPError, ValueError):
        prefix = 'https://github.com/wmgeolab/geoBoundaries/raw/'
        if not geometry_url.startswith(prefix):
            raise ValueError('Unexpected source URL; inspect metadata before downloading')
        media_url = 'https://media.githubusercontent.com/media/wmgeolab/geoBoundaries/' + geometry_url[len(prefix):]
        geometry_bytes, geometry_resolved = read(media_url)
    geometry = json.loads(geometry_bytes)
    if geometry.get('type') != 'FeatureCollection' or not geometry.get('features'):
        raise ValueError('Source did not return a nonempty GeoJSON FeatureCollection')
    (RAW / 'lka_adm2_simplified.geojson').write_bytes(geometry_bytes)
    citation_url = geometry_url.rsplit('/', 1)[0] + '/CITATION-AND-USE-geoBoundaries.txt'
    citation_fallback = 'https://media.githubusercontent.com/media/wmgeolab/geoBoundaries/' + citation_url.split('/raw/', 1)[1]
    try:
        citation_bytes, _ = read(citation_url)
        if citation_bytes.startswith(b'version https://git-lfs'):
            citation_bytes, _ = read(citation_fallback)
    except urllib.error.HTTPError:
        citation_bytes, _ = read(citation_fallback)
    (RAW / 'CITATION-AND-USE-geoBoundaries.txt').write_bytes(citation_bytes)
    manifest = {
        'dataset': 'geoBoundaries gbOpen Sri Lanka ADM2 simplified boundaries',
        'retrieved_utc': datetime.now(timezone.utc).isoformat(),
        'metadata_url': API, 'resolved_metadata_url': resolved,
        'geometry_url': geometry_url, 'resolved_geometry_url': geometry_resolved,
        'source_commit_from_download_url': geometry_url.split('/raw/', 1)[1].split('/')[0],
        'boundary_id': metadata['boundaryID'],
        'year_represented': metadata['boundaryYearRepresented'],
        'original_license': metadata['boundaryLicense'],
        'source': metadata['boundarySource'],
        'expected_units': int(metadata['admUnitCount']),
        'actual_units': len(geometry['features']),
        'purpose': 'Optional geographic display only; not telecom infrastructure, roads or live hazard data.',
        'sha256': {p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted(RAW.iterdir()) if p.is_file() and p.name != 'download_manifest.json'}
    }
    (RAW / 'download_manifest.json').write_text(json.dumps(manifest, indent=2) + '\n', encoding='utf-8', newline='\n')
    print(f'Downloaded {len(geometry["features"])} districts, {len(geometry_bytes):,} geometry bytes; licence: {metadata["boundaryLicense"]}')

if __name__ == '__main__':
    download()
