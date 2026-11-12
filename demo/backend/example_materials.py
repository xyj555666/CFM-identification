"""Resolve the explicit downloadable files in the public example catalog."""
from pathlib import Path

def selected_file(root, example, role):
    """Resolve only files registered in the server's example catalog."""
    file = next((f for f in example.get('network_files', {}).get('files', []) if f['role'] == role), None)
    if file is None:
        raise ValueError('EXAMPLE_FILE_NOT_FOUND')
    root = Path(root).resolve()
    path = (root / file['path']).resolve()
    if not path.is_relative_to(root) or not path.is_file() or path.suffix.lower() != '.csv':
        raise ValueError('EXAMPLE_FILE_NOT_FOUND')
    return path, file['name']
