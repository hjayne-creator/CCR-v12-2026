from __future__ import annotations

import json
from pathlib import Path

from app.models.schemas import ClientRulesPack, RuleDef

_CLIENTS = Path(__file__).resolve().parents[1] / "clients"

SLUG_TO_FOLDER = {
    "sgs-engineering": "sgs",
    "sgs": "sgs",
}

# Hierarchy rank: lower = higher priority when conflicts arise.
HIERARCHY_RANK = {
    "factual_accuracy": 1,
    "data_integrity": 2,
    "mandatory_client_rules": 3,
    "content_completeness": 4,
    "seo_editorial": 5,
}


def _folder_for(slug: str) -> str:
    return SLUG_TO_FOLDER.get(slug, slug)


def rules_path_for(slug: str) -> Path:
    return _CLIENTS / _folder_for(slug) / "rules.json"


def load_client_rules(slug: str) -> ClientRulesPack:
    """Load rules from disk (no cache — UI edits must apply to the next run)."""
    rules_path = rules_path_for(slug)
    if not rules_path.exists():
        raise FileNotFoundError(f"No rules pack for client slug={slug!r} at {rules_path}")
    data = json.loads(rules_path.read_text(encoding="utf-8"))
    return ClientRulesPack.model_validate(data)


def save_client_rules(slug: str, pack: ClientRulesPack) -> ClientRulesPack:
    """Validate and write rules.json so the next run sees updates."""
    pack = pack.model_copy(update={"client_slug": slug})
    path = rules_path_for(slug)
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = pack.model_dump(mode="json")
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return load_client_rules(slug)


def style_excerpt_path(slug: str) -> Path | None:
    path = _CLIENTS / _folder_for(slug) / "style_excerpt.md"
    return path if path.exists() else None


def load_style_excerpt(slug: str) -> str:
    path = style_excerpt_path(slug)
    if not path:
        return ""
    return path.read_text(encoding="utf-8")


def save_style_excerpt(slug: str, text: str) -> str:
    path = _CLIENTS / _folder_for(slug) / "style_excerpt.md"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text if text.endswith("\n") else text + "\n", encoding="utf-8")
    return path.read_text(encoding="utf-8")


def rules_for_stage(pack: ClientRulesPack, stage: str) -> list[RuleDef]:
    return [r for r in pack.rules if stage in r.scope or not r.scope]


def mandatory_rules(pack: ClientRulesPack, stage: str | None = None) -> list[RuleDef]:
    rules = pack.rules if stage is None else rules_for_stage(pack, stage)
    return [r for r in rules if r.priority == "MANDATORY"]
