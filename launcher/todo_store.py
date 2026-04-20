from __future__ import annotations

from pathlib import Path
import json



def _status_from_progress(progress: int) -> str:
    if progress <= 0:
        return "todo"
    if progress >= 100:
        return "done"
    return "in_progress"


def _progress_from_status(status: str) -> int:
    if status == "done":
        return 100
    if status == "in_progress":
        return 50
    return 0


class TodoStore:
    def __init__(self, path: Path) -> None:
        self.path = path
        self.path.parent.mkdir(parents=True, exist_ok=True)

    def _load_raw(self) -> dict:
        try:
            return json.loads(self.path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return {"categories": []}

    def _save_raw(self, payload: dict) -> None:
        self.path.write_text(json.dumps(payload, indent=2), encoding="utf-8")

    def list_categories(self) -> dict:
        payload = self._load_raw()
        categories = []
        total_items = 0
        total_progress_sum = 0

        for category in payload.get("categories", []):
            items = category.get("items", [])
            enriched = []
            for item in items:
                progress = item.get("progress", _progress_from_status(item.get("status", "todo")))
                status = _status_from_progress(progress)
                enriched.append({**item, "progress": progress, "status": status})
            total_count = len(enriched)
            cat_progress = int(sum(i["progress"] for i in enriched) / total_count) if total_count else 0
            categories.append({**category, "items": enriched, "progress_percent": cat_progress})
            total_items += total_count
            total_progress_sum += sum(i["progress"] for i in enriched)

        overall = int(total_progress_sum / total_items) if total_items else 0
        return {
            "categories": categories,
            "summary": {
                "total_items": total_items,
                "progress_percent": overall,
            },
        }

    def update_item(self, category_id: str, item_id: str, progress: int) -> dict | None:
        progress = max(0, min(100, int(progress)))
        payload = self._load_raw()
        for category in payload.get("categories", []):
            if category.get("id") != category_id:
                continue
            for item in category.get("items", []):
                if item.get("id") == item_id:
                    item["progress"] = progress
                    item["status"] = _status_from_progress(progress)
                    self._save_raw(payload)
                    return item
        return None
