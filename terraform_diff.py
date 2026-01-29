from __future__ import annotations

import html
from typing import Any, Tuple


class FilterModule:
    """
    Diff-aware YAML renderer for Terraform plans.

    Behaviors:

    CREATE:
      show full after

    UPDATE:
      show ONLY changed fields (before vs after)

    REPLACE:
      show only keys known after apply
      suppress removals

    DELETE:
      show full before

    JSON view always raw.
    """

    def filters(self):
        return {
            "diff_yaml": self.diff_yaml,
            "to_nice_json": self.to_nice_json,
            "to_nice_yaml": self.to_nice_yaml,
            "restrict_before": self.restrict_before,
        }

    # ----------------------------
    # Public
    # ----------------------------

    def diff_yaml(self, before, after, actions=None):
        before = before or {}
        after = after or {}
        actions = actions or []

        is_replace = "create" in actions and "delete" in actions
        is_update = actions == ["update"]

        if is_update:
            before, after = self._extract_changes(before, after)

        if is_replace and isinstance(before, dict) and isinstance(after, dict):
            before = {k: before.get(k) for k in after.keys()}

        lines = self._diff(before, after, suppress_removals=is_replace)
        return "\n".join(lines)

    def restrict_before(self, before, after, actions=None):
        before = before or {}
        after = after or {}
        actions = actions or []

        is_replace = "create" in actions and "delete" in actions
        is_update = actions == ["update"]

        if is_update:
            before, _ = self._extract_changes(before, after)

        if is_replace and isinstance(before, dict) and isinstance(after, dict):
            return {k: before.get(k) for k in after.keys()}

        return before

    def to_nice_json(self, data):
        import json
        return json.dumps(data, indent=2, sort_keys=True)

    def to_nice_yaml(self, data):
        import yaml
        return yaml.safe_dump(data, sort_keys=False, default_flow_style=False)

    # ----------------------------
    # Change extraction (UPDATE)
    # ----------------------------

    def _extract_changes(self, before: Any, after: Any) -> Tuple[Any, Any]:
        """
        Return only changed portions of before/after.
        """

        if isinstance(before, dict) and isinstance(after, dict):
            b_out = {}
            a_out = {}

            for k in after.keys():
                if k not in before:
                    b_out[k] = None
                    a_out[k] = after[k]
                    continue

                b_val, a_val = self._extract_changes(before[k], after[k])
                if b_val is not None or a_val is not None:
                    b_out[k] = b_val
                    a_out[k] = a_val

            return b_out or None, a_out or None

        if isinstance(before, list) and isinstance(after, list):
            if before != after:
                return before, after
            return None, None

        if before != after:
            return before, after

        return None, None

    # ----------------------------
    # Rendering
    # ----------------------------

    def _diff(self, before: Any, after: Any, indent=0, suppress_removals=False):
        pad = "  " * indent
        lines = []

        if isinstance(after, list):
            return self._diff_list(before or [], after, indent, suppress_removals)

        if isinstance(after, dict):
            before = before or {}

            for key in sorted(after.keys()):
                a = after.get(key)
                b = before.get(key)
                esc_key = html.escape(str(key))

                if key not in before:
                    lines.append(f'{pad}<span class="diff-add">{esc_key}:</span>')
                    lines.extend(self._diff({}, a, indent + 1, suppress_removals))

                elif b == a:
                    if isinstance(a, (dict, list)):
                        lines.append(f"{pad}{esc_key}:")
                        lines.extend(self._diff(b, a, indent + 1, suppress_removals))
                    else:
                        lines.append(f"{pad}{esc_key}: {html.escape(str(a))}")

                else:
                    if isinstance(a, (dict, list)):
                        lines.append(f'{pad}<span class="diff-update">{esc_key}:</span>')
                        lines.extend(self._diff(b, a, indent + 1, suppress_removals))
                    else:
                        lines.append(
                            f'{pad}<span class="diff-update">{esc_key}: {html.escape(str(a))}</span>'
                        )

            if not suppress_removals:
                for key in sorted(set(before.keys()) - set(after.keys())):
                    esc_key = html.escape(str(key))
                    lines.append(
                        f'{pad}<span class="diff-del">{esc_key}: {html.escape(str(before[key]))}</span>'
                    )

            return lines

        if before != after:
            return [f'{pad}<span class="diff-update">{html.escape(str(after))}</span>']

        return [f'{pad}{html.escape(str(after))}']

    def _diff_list(self, before, after, indent, suppress_removals):
        pad = "  " * indent
        lines = []
        max_len = max(len(before), len(after))

        for i in range(max_len):
            b = before[i] if i < len(before) else None
            a = after[i] if i < len(after) else None
            prefix = f"{pad}- "

            if b is None:
                lines.append(f'{prefix}<span class="diff-add">{html.escape(str(a))}</span>')
            elif a is None:
                if not suppress_removals:
                    lines.append(f'{prefix}<span class="diff-del">{html.escape(str(b))}</span>')
            elif b == a:
                lines.append(f"{prefix}{html.escape(str(a))}")
            else:
                lines.append(f'{prefix}<span class="diff-update">{html.escape(str(a))}</span>')

        return lines
