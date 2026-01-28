from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, List, Iterable

from ansible.plugins.action import ActionBase
from ansible.errors import AnsibleActionFail


MASK = "**********"


def _clean_value(value: Any, *, keep_root_empty_dict: bool = False) -> Any:
    """
    Recursively remove:
      - None values
      - empty lists
      - empty dicts (except root if keep_root_empty_dict=True)

    Returns cleaned value or None if fully empty.
    """

    if value is None:
        return None

    if isinstance(value, list):
        cleaned = [
            _clean_value(v)
            for v in value
            if _clean_value(v) is not None
        ]
        return cleaned or None

    if isinstance(value, dict):
        cleaned = {}
        for k, v in value.items():
            cv = _clean_value(v)
            if cv is not None:
                cleaned[k] = cv

        if not cleaned:
            return {} if keep_root_empty_dict else None

        return cleaned

    return value


def _redact(obj: Any, keys: Iterable[str]) -> Any:
    """
    Recursively replace values for matching keys with MASK.
    Keys are matched case-insensitively.
    """
    if isinstance(obj, dict):
        new = {}
        for k, v in obj.items():
            if k.lower() in keys:
                new[k] = MASK
            else:
                new[k] = _redact(v, keys)
        return new

    if isinstance(obj, list):
        return [_redact(v, keys) for v in obj]

    return obj


class ActionModule(ActionBase):
    TRANSFERS_FILES = False

    def run(self, tmp=None, task_vars=None):
        super().run(tmp, task_vars)

        args = self._task.args

        plan_path = args.get("plan_json")
        redact_keys = args.get("redact_keys", [])

        if not plan_path:
            raise AnsibleActionFail("plan_json parameter is required")

        if not isinstance(redact_keys, list):
            raise AnsibleActionFail("redact_keys must be a list")

        redact_keys = {k.lower() for k in redact_keys}

        path = Path(plan_path)
        if not path.exists():
            raise AnsibleActionFail(f"Terraform plan JSON not found: {plan_path}")

        try:
            plan = json.loads(path.read_text())
        except Exception as exc:
            raise AnsibleActionFail(f"Failed to parse Terraform JSON: {exc}")

        resource_changes = plan.get("resource_changes")
        if not isinstance(resource_changes, list):
            raise AnsibleActionFail("Invalid Terraform JSON: resource_changes missing")

        by_device: Dict[str, List[Dict[str, Any]]] = {}

        for rc in resource_changes:
            change = rc.get("change", {})
            actions = change.get("actions", [])

            if actions == ["no-op"]:
                continue

            before_raw = change.get("before") or {}
            after_raw = change.get("after") or {}

            before = _clean_value(before_raw, keep_root_empty_dict=True) or {}
            after = _clean_value(after_raw, keep_root_empty_dict=True) or {}

            if before == after:
                continue

            # Redact secrets
            before = _redact(before, redact_keys)
            after = _redact(after, redact_keys)

            device = after.get("device_name") or before.get("device_name")
            if not device:
                raise AnsibleActionFail(
                    f"device_name missing in resource {rc.get('address')}"
                )

            before.pop("device_name", None)
            after.pop("device_name", None)

            entry = {
                "address": rc.get("address"),
                "type": rc.get("type"),
                "name": rc.get("name"),
                "actions": actions,
                "before": before,
                "after": after,
            }

            by_device.setdefault(device, []).append(entry)

        result = {
            "changed": False,
            "terraform_changes_by_device": by_device,
        }

        return result
