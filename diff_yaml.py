from __future__ import annotations
from typing import Any
import html


def _diff(before: Any, after: Any, indent=0):
    lines = []
    pad = "  " * indent

    if isinstance(before, dict) and isinstance(after, dict):
        keys = sorted(set(before) | set(after))

        for k in keys:
            b = before.get(k)
            a = after.get(k)

            if k not in before:
                lines.append(f'{pad}<span class="diff-add">{k}: {html.escape(str(a))}</span>')
            elif k not in after:
                lines.append(f'{pad}<span class="diff-del">{k}: {html.escape(str(b))}</span>')
            elif b == a:
                if isinstance(a, dict):
                    lines.append(f"{pad}{k}:")
                    lines.extend(_diff(b, a, indent + 1))
                else:
                    lines.append(f"{pad}{k}: {html.escape(str(a))}")
            else:
                if isinstance(a, dict):
                    lines.append(f'{pad}<span class="diff-update">{k}:</span>')
                    lines.extend(_diff(b, a, indent + 1))
                else:
                    lines.append(
                        f'{pad}<span class="diff-update">{k}: {html.escape(str(a))}</span>'
                    )

    else:
        if before != after:
            lines.append(f'{pad}<span class="diff-update">{html.escape(str(after))}</span>')
        else:
            lines.append(f'{pad}{html.escape(str(after))}')

    return lines


def diff_yaml(before, after):
    """
    Produce HTML-highlighted YAML-like diff.

    Added   -> green bold
    Updated -> amber bold
    Removed -> red bold
    """
    lines = _diff(before or {}, after or {})
    return "\n".join(lines)
