from typing import Dict, Optional

_LATEST_SEQUENCE_BY_NODE: Dict[str, str] = {}


def record_latest_sequence(node_id, sequence_root: str) -> None:
    if node_id is None:
        return
    _LATEST_SEQUENCE_BY_NODE[str(node_id)] = sequence_root


def get_latest_sequence(node_id) -> Optional[str]:
    if node_id is None:
        return None
    return _LATEST_SEQUENCE_BY_NODE.get(str(node_id))
