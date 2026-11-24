"""Dataset integrity checks survive checkout and detect damaged artifacts."""
import csv
import hashlib
from pathlib import Path

import pytest

from scripts.check_data import check_manifest
from scripts.prepare_data import csv_rows


def manifest(root: Path, rows):
    csv_rows(root / 'data/file_manifest.csv', rows, ['path', 'bytes', 'sha256', 'origin'])


@pytest.fixture
def dataset(tmp_path):
    path = tmp_path / 'data/processed/example.csv'
    csv_rows(path, [{'label': 'Colombo'}], ['label'])
    content = path.read_bytes()
    row = {'path': 'data/processed/example.csv', 'bytes': len(content),
           'sha256': hashlib.sha256(content).hexdigest(), 'origin': 'synthetic'}
    manifest(tmp_path, [row])
    return tmp_path, path, row


def test_csv_has_stable_utf8_lf_bytes(tmp_path):
    path = tmp_path / 'table.csv'
    csv_rows(path, [{'label': 'தமிழ்'}], ['label'])
    assert path.read_bytes() == 'label\nதமிழ்\n'.encode('utf-8')


def test_manifest_accepts_complete_dataset(dataset):
    root, _, _ = dataset
    assert check_manifest(root) == 1


@pytest.mark.parametrize('damage', ['same_size', 'size', 'missing', 'unlisted', 'duplicate', 'unsafe'])
def test_manifest_rejects_damage(dataset, damage):
    root, path, row = dataset
    if damage == 'same_size':
        path.write_bytes(path.read_bytes().replace(b'Colombo', b'Kandy  '))
    elif damage == 'size':
        path.write_bytes(path.read_bytes() + b'X')
    elif damage == 'missing':
        path.unlink()
    elif damage == 'unlisted':
        (path.parent / 'extra.json').write_text('{}')
    elif damage == 'duplicate':
        manifest(root, [row, row])
    elif damage == 'unsafe':
        manifest(root, [{**row, 'path': 'data/processed/../../outside'}])
    with pytest.raises(ValueError):
        check_manifest(root)
