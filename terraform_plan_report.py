"""
Ansible Action Plugin: terraform_plan_report

Parses Terraform plan JSON and extracts meaningful changes
for human-readable reporting.

Output is returned as Ansible fact:

terraform_changes: [
  {
    address: "...",
    type: "...",
    name: "...",
    actions: ["create"|"update"|"delete"],
    before: {...},
    after: {...}
  }
]

Rules:
- after_unknown is discarded
- resources with actions == ["no-op"] are dropped
- null values are recursively removed
- resources where before == after are dropped
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, List

from ansible.plugins.action import ActionBase
from ansible.errors import AnsibleActionFail


def _remove_nulls(obj: Any) -> Any:
    """
    Recursively remove keys with None values from dicts and lists.
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

        args = self._task.args
        plan_path = args.get("plan_json")

        if not plan_path:
            raise AnsibleActionFail("plan_json parameter is required")

        path = Path(plan_path)

        if not path.exists():
            raise AnsibleActionFail(f"Terraform plan JSON not found: {plan_path}")

        try:
            with path.open() as f:
                plan = json.load(f)
        except Exception as exc:
            raise AnsibleActionFail(f"Failed to load Terraform plan JSON: {exc}")

        resource_changes = plan.get("resource_changes")
        if not isinstance(resource_changes, list):
            raise AnsibleActionFail("Invalid Terraform JSON: resource_changes missing or malformed")

        results: List[Dict[str, Any]] = []

        for rc in resource_changes:
            change = rc.get("change", {})
            actions = change.get("actions", [])

            # Skip no-op
            if actions == ["no-op"]:
                continue

            before = _remove_nulls(change.get("before") or {})
            after = _remove_nulls(change.get("after") or {})

            # Drop if no effective difference
            if before == after:
                continue

            results.append(
                {
                    "address": rc.get("address"),
                    "type": rc.get("type"),
                    "name": rc.get("name"),
                    "actions": actions,
                    "before": before,
                    "after": after,
                }
            )

        return {
            "changed": False,
            "ansible_facts": {
                "terraform_changes": results
            }
        }
