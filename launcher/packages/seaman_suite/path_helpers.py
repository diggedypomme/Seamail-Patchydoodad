from pathlib import Path
import json
import os


PACKAGE_ROOT = Path(__file__).resolve().parent
WORKSPACE_ROOT = PACKAGE_ROOT.parents[2]
LAUNCHER_ROOT = WORKSPACE_ROOT / "launcher"
CONFIG_PATH = LAUNCHER_ROOT / "config.json"


def _normalize_path(value: str | None) -> str | None:
    if not value:
        return None
    return str(Path(value).expanduser())


def _default_game_executable_for(seamail_root: str | None) -> str:
    base = Path(seamail_root) if seamail_root else (WORKSPACE_ROOT / "SeaMail")
    preferred_names = [
        "Seaman_1_2_57.exe",
        "Seaman_FINAL.exe",
        "Seaman_fully_patched.exe",
        "Seaman_patched.exe",
        "Seaman.exe",
    ]
    for name in preferred_names:
        candidate = base / name
        if candidate.exists() and candidate.is_file():
            return str(candidate)
    return str(base / "Seaman_1_2_57.exe")


def _default_config() -> dict:
    return {
        "game_root": str(WORKSPACE_ROOT),
        "seamail_root": str(WORKSPACE_ROOT / "SeaMail"),
        "game_executable": _default_game_executable_for(str(WORKSPACE_ROOT / "SeaMail")),
    }


def load_launcher_config() -> dict:
    config = _default_config()
    if CONFIG_PATH.exists():
        try:
            loaded = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
            if isinstance(loaded, dict):
                config.update({key: value for key, value in loaded.items() if value})
        except (json.JSONDecodeError, OSError):
            pass

    game_root = os.environ.get("GAME_ROOT")
    seamail_root = os.environ.get("SEAMAIL_ROOT")
    if game_root:
        config["game_root"] = game_root
    if seamail_root:
        config["seamail_root"] = seamail_root

    config["game_root"] = _normalize_path(config.get("game_root"))
    config["seamail_root"] = _normalize_path(config.get("seamail_root"))
    config["game_executable"] = _normalize_path(config.get("game_executable"))
    return config


def save_launcher_config(data: dict) -> dict:
    current = load_launcher_config()
    next_game_root = _normalize_path(data.get("game_root")) or current.get("game_root")
    next_seamail_root = _normalize_path(data.get("seamail_root")) or current.get("seamail_root")
    requested_game_executable = _normalize_path(data.get("game_executable"))

    current_default_executable = _default_game_executable_for(current.get("seamail_root"))
    next_default_executable = _default_game_executable_for(next_seamail_root)
    current_game_executable = _normalize_path(current.get("game_executable"))

    if requested_game_executable:
        next_game_executable = requested_game_executable
    elif not current_game_executable or current_game_executable == current_default_executable:
        next_game_executable = next_default_executable
    else:
        next_game_executable = current_game_executable

    config = {
        "game_root": next_game_root,
        "seamail_root": next_seamail_root,
        "game_executable": next_game_executable,
    }
    CONFIG_PATH.parent.mkdir(parents=True, exist_ok=True)
    CONFIG_PATH.write_text(json.dumps(config, indent=2), encoding="utf-8")
    return config


def resolve_game_root() -> Path:
    config = load_launcher_config()
    configured = config.get("game_root")
    if configured:
        candidate = Path(configured)
        if candidate.exists() and candidate.is_dir():
            return candidate
    return WORKSPACE_ROOT


def resolve_game_executable() -> Path:
    config = load_launcher_config()
    seamail_root = resolve_seamail_root()
    configured = config.get("game_executable")
    default_executable = _default_game_executable_for(str(seamail_root))
    candidates: list[Path] = []
    if configured and configured != default_executable:
        candidates.append(Path(configured))

    candidates.extend(
        [
            seamail_root / "Seaman_1_2_57.exe",
            seamail_root / "Seaman_FINAL.exe",
            seamail_root / "Seaman_fully_patched.exe",
            seamail_root / "Seaman_patched.exe",
            seamail_root / "Seaman.exe",
        ]
    )
    candidates.extend(sorted(seamail_root.glob("Seaman*.exe")))

    seen: set[str] = set()
    for candidate in candidates:
        normalized = str(candidate).lower()
        if normalized in seen:
            continue
        seen.add(normalized)
        if candidate.exists() and candidate.is_file():
            return candidate

    return Path(configured) if configured else Path(_default_game_executable_for(str(seamail_root)))


def resolve_seamail_root() -> Path:
    config = load_launcher_config()
    configured = config.get("seamail_root")
    candidates: list[Path] = []
    if configured:
        candidates.append(Path(configured))

    game_root = config.get("game_root")
    if game_root:
        candidates.append(Path(game_root) / "SeaMail")

    candidates.extend(
        [
            WORKSPACE_ROOT / "SeaMail",
            PACKAGE_ROOT / "SeaMail",
            PACKAGE_ROOT / "seaman_data" / "SeaMail",
        ]
    )

    for candidate in candidates:
        if candidate.exists() and candidate.is_dir():
            return candidate

    return Path(configured) if configured else WORKSPACE_ROOT / "SeaMail"


def resolve_hostdb_dir() -> Path:
    seamail_root = resolve_seamail_root()
    return seamail_root / "hostDB"


def resolve_resource_dir() -> Path:
    seamail_root = resolve_seamail_root()
    return seamail_root / "Resource"


def resolve_weather_dll() -> Path:
    return resolve_seamail_root() / "WeatherGet.dll"


def validate_paths(
    game_root: str | None = None,
    seamail_root: str | None = None,
    game_executable: str | None = None,
) -> dict:
    config = load_launcher_config()
    effective_game_root = Path(_normalize_path(game_root) or config.get("game_root") or WORKSPACE_ROOT)
    effective_seamail_root = Path(
        _normalize_path(seamail_root)
        or config.get("seamail_root")
        or (effective_game_root / "SeaMail")
    )
    effective_game_executable = Path(
        _normalize_path(game_executable)
        or _normalize_path(config.get("game_executable"))
        or _default_game_executable_for(str(effective_seamail_root))
    )
    hostdb = effective_seamail_root / "hostDB"
    resource = effective_seamail_root / "Resource"
    weather_dll = effective_seamail_root / "WeatherGet.dll"

    return {
        "game_root": str(effective_game_root),
        "seamail_root": str(effective_seamail_root),
        "game_executable": str(effective_game_executable),
        "hostdb_path": str(hostdb),
        "resource_path": str(resource),
        "weather_dll_path": str(weather_dll),
        "game_root_exists": effective_game_root.exists() and effective_game_root.is_dir(),
        "seamail_exists": effective_seamail_root.exists() and effective_seamail_root.is_dir(),
        "game_executable_exists": effective_game_executable.exists() and effective_game_executable.is_file(),
        "hostdb_exists": hostdb.exists() and hostdb.is_dir(),
        "resource_exists": resource.exists() and resource.is_dir(),
        "weather_dll_exists": weather_dll.exists() and weather_dll.is_file(),
        "valid": effective_seamail_root.exists() and hostdb.exists() and resource.exists() and effective_game_executable.exists(),
    }
