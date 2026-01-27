from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, List

from ansible.plugins.action import ActionBase
from ansible.errors import AnsibleActionFail


def _remove_nulls(obj: Any) -> Any:
    """
    Recursively remove keys with None values.
    """
    if isinstance(obj, dict):
        return {
            k: _remove_nulls(v)
            for k, v in obj.items()
            if v is not None
        }
    if isinstance(obj, list):
        return [_remove_nulls(v) for v in obj if v is not None]
    return obj


class ActionModule(ActionBase):
    TRANSFERS_FILES = False

    def run(self, tmp=None, task_vars=None):
        super().run(tmp, task_vars)

        plan_path = self._task.args.get("plan_json")
        if not plan_path:
            raise AnsibleActionFail("plan_json parameter is required")

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

            before = _remove_nulls(change.get("before") or {})
            after = _remove_nulls(change.get("after") or {})

            if before == after:
                continue

            # Extract device_name (prefer after)
            device = after.get("device_name") or before.get("device_name")
            if not device:
                raise AnsibleActionFail(
                    f"device_name missing in resource {rc.get('address')}"
                )

            # Remove device_name from payload (now metadata)
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

        return {
            "changed": False,
            "ansible_facts": {
                "terraform_changes_by_device": by_device
            }
        }
