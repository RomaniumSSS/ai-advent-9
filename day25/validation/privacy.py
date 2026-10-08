"""Private output boundary for raw validation results and recordings."""
from pathlib import Path

PRIVATE_ROOT=Path(__file__).resolve().parents[1]/'private'


def private_output(output, private_root=PRIVATE_ROOT):
    root=Path(private_root).resolve()
    path=Path(output).resolve()
    if path==root or not path.is_relative_to(root):
        raise ValueError('output_must_be_inside_day25_private')
    return path
