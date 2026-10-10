"""Private durable runtime files; never use the synchronized source tree as a DB."""
import hashlib
import json
import os
from pathlib import Path
import tempfile


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def atomic_json(path, value):
    path = Path(path)
    fd, tmp = tempfile.mkstemp(dir=path.parent)
    try:
        with os.fdopen(fd, 'w') as stream:
            json.dump(value, stream, sort_keys=True, allow_nan=False)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(tmp, path)
        directory = os.open(path.parent, os.O_RDONLY)
        try:
            os.fsync(directory)
        finally:
            os.close(directory)
    finally:
        if os.path.exists(tmp):
            os.unlink(tmp)


def read_json(path):
    path = Path(path)
    if path.stat().st_size > 65536:
        raise ValueError('json_size_limit')
    return json.loads(path.read_text())


def private_file(path):
    path = Path(path).resolve(strict=True)
    for part in (path, *path.parents):
        st = part.stat()
        if st.st_uid != 0 or st.st_mode & 0o022:
            raise ValueError('untrusted_deployment_path')
    return path
