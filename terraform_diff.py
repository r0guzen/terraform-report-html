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

    For Terraform replace actions:
      - suppress removals (after_unknown artifacts)
      - show only real changes
    """

    def filters(self):
        return {
            "diff_yaml": self.diff_yaml
        }

    # ----------------------------
    # Public Filters
    # ----------------------------

    def diff_yaml(self, before, after, actions=None):
        """
        Produce HTML-highlighted YAML-style diff.

        :param before: original object
        :param after: new object
        :param actions: terraform actions list
        :return: HTML string
        """

        is_replace = actions and "create" in actions and "delete" in actions

        lines = self._diff(before or {}, after or {}, suppress_removals=is_replace)
        return "\n".join(lines)

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

        if isinstance(after, dict):
            before = before or {}

            for key in sorted(after.keys()):
                a = after.get(key)
                b = before.get(key)

                esc_key = html.escape(str(key))

                # ADDED
                if key not in before:
                    if isinstance(a, dict):
                        lines.append(f'{pad}<span class="diff-add">{esc_key}:</span>')
                        lines.extend(self._diff({}, a, indent + 1, suppress_removals))
                    else:
                        lines.append(
                            f'{pad}<span class="diff-add">{esc_key}: {html.escape(str(a))}</span>'
                        )

                # UNCHANGED
                elif b == a:
                    if isinstance(a, dict):
                        lines.append(f"{pad}{esc_key}:")
                        lines.extend(self._diff(b, a, indent + 1, suppress_removals))
                    else:
                        lines.append(f"{pad}{esc_key}: {html.escape(str(a))}")

                # UPDATED
                else:
                    if isinstance(a, dict):
                        lines.append(f'{pad}<span class="diff-update">{esc_key}:</span>')
                        lines.extend(self._diff(b, a, indent + 1, suppress_removals))
                    else:
                        lines.append(
                            f'{pad}<span class="diff-update">{esc_key}: {html.escape(str(a))}</span>'
                        )

            # REMOVED (skip for replace)
            if not suppress_removals:
                for key in sorted(set(before.keys()) - set(after.keys())):
                    esc_key = html.escape(str(key))
                    lines.append(
                        f'{pad}<span class="diff-del">{esc_key}: {html.escape(str(before[key]))}</span>'
                    )

        else:
            if before != after:
                lines.append(f'{pad}<span class="diff-update">{html.escape(str(after))}</span>')
            else:
                lines.append(f'{pad}{html.escape(str(after))}')

        return lines
