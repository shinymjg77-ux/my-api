import json
from pathlib import Path


RELEASE_META_FILENAME = ".release-meta.json"
PROJECT_ROOT = Path(__file__).resolve().parents[2]
REQUIRED_FIELDS = ("git_sha", "release_id", "built_at")
OPTIONAL_FIELDS = ("backend_slot", "n8n_compose_sha256")


def get_release_meta_path(project_root: Path | None = None) -> Path:
    return (project_root or PROJECT_ROOT) / RELEASE_META_FILENAME


def load_release_meta(path: Path | None = None) -> tuple[dict[str, str] | None, str | None]:
    release_meta_path = path or get_release_meta_path()

    if not release_meta_path.is_file():
        return None, "missing"

    try:
        payload = json.loads(release_meta_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None, "invalid_json"

    if not isinstance(payload, dict):
        return None, "invalid_shape"

    meta: dict[str, str] = {}
    for key in REQUIRED_FIELDS:
        value = payload.get(key)
        if not isinstance(value, str) or not value.strip():
            return None, "invalid_shape"
        meta[key] = value.strip()

    for key in OPTIONAL_FIELDS:
        value = payload.get(key)
        if isinstance(value, str) and value.strip():
            meta[key] = value.strip()

    return meta, None
