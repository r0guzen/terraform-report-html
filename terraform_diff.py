from __future__ import annotations

import html
from typing import Any


class FilterModule:
    """
    Ansible filter plugin providing diff-aware YAML rendering.

    Produces HTML-highlighted YAML-like output:

      - Added   -> green bold
      - Updated -> amber bold
      - Removed -> red bold
      - Same    -> normal

    Replace behavior:
      - suppress removals
      - restrict before keys to after keys
    """

    def filters(self):
        return {
            "diff_yaml": self.diff_yaml,
            "to_nice_json": self.to_nice_json,
            "to_nice_yaml": self.to_nice_yaml,
            "restrict_before": self.restrict_before,
        }

    # ----------------------------
    # Public Filters
    # ----------------------------

    def diff_yaml(self, before, after, actions=None):
        is_replace = actions and "create" in actions and "delete" in actions

        before = before or {}
        after = after or {}

        if is_replace and isinstance(before, dict) and isinstance(after, dict):
            before = {k: before.get(k) for k in after.keys()}

        lines = self._diff(before, after, suppress_removals=is_replace)
        return "\n".join(lines)

    def restrict_before(self, before, after, actions=None):
        is_replace = actions and "create" in actions and "delete" in actions

        if not is_replace:
            return before

        if isinstance(before, dict) and isinstance(after, dict):
            return {k: before.get(k) for k in after.keys()}

        return before

    def to_nice_json(self, data):
        import json
        return json.dumps(data, indent=2, sort_keys=True)

    def to_nice_yaml(self, data):
        import yaml
        return yaml.safe_dump(
            data,
            sort_keys=False,
            default_flow_style=False
        )

    # ----------------------------
    # Internal Helpers
    # ----------------------------

    def _diff(self, before: Any, after: Any, indent=0, suppress_removals=False):
        pad = "  " * indent
        lines = []

        # LISTS
        if isinstance(after, list):
            return self._diff_list(before or [], after, indent, suppress_removals)

        # DICTS
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
                    lines.append(f"{pad}{esc_key}:")
                    lines.extend(self._diff(b, a, indent + 1, suppress_removals))

                else:
                    lines.append(f'{pad}<span class="diff-update">{esc_key}:</span>')
                    lines.extend(self._diff(b, a, indent + 1, suppress_removals))

            if not suppress_removals:
                for key in sorted(set(before.keys()) - set(after.keys())):
                    esc_key = html.escape(str(key))
                    lines.append(
                        f'{pad}<span class="diff-del">{esc_key}: {html.escape(str(before[key]))}</span>'
                    )

            return lines

        # SCALARS
        if before != after:
            return [f'{pad}<span class="diff-update">{html.escape(str(after))}</span>']

        return [f'{pad}{html.escape(str(after))}']

    def _diff_list(self, before, after, indent, suppress_removals):
        pad = "  " * indent
        lines = []

        before = before or []

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
