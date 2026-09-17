"""Systemd preflight: verify secret metadata without reading or printing it."""
import os
import stat
from pathlib import Path


def check_secret(path=Path('/etc/ai-advent-day12/openrouter.env')):
    metadata = path.lstat()
    if not stat.S_ISREG(metadata.st_mode) or stat.S_IMODE(metadata.st_mode) != 0o600 or metadata.st_uid != 0 or metadata.st_gid != 0:
        raise RuntimeError('OpenRouter EnvironmentFile must be a regular root:root 0600 file')
    if not os.environ.get('OPENROUTER_API_KEY', '').strip():
        raise RuntimeError('OPENROUTER_API_KEY is required')


if __name__ == '__main__':
    check_secret()
