"""report_cfs_third_wave.py -- report text of the 2026-10 third wave in the CFS reports (handoff P3 and P9).

Every function reads the cfg / calc package and returns a record or an HTML fragment; report_cfs_india.py hooks them
in, and the text passes through the second-wave public-text pass (report_cfs_second_wave.tidy_html) with the rest of
the report.

* column_orientation_html                       P3: the stated rule for the strong axis of a frame column that stands
      in frames of both directions (the corner of two braced walls), with the columns it decides.
"""
from __future__ import annotations

import html
import math


def _e(x):
    return html.escape(str(x if x is not None else "-"))


def _num(v):
    return isinstance(v, (int, float)) and not isinstance(v, bool) and math.isfinite(float(v))


def _f(v, d=3):
    return ("%%.%df" % d) % float(v) if _num(v) else "-"


def _t(head, rows):
    h = "".join("<th>%s</th>" % _e(c) for c in head)
    b = "".join("<tr>" + "".join("<td>%s</td>" % c for c in r) + "</tr>" for r in rows)
    return "<table><thead><tr>%s</tr></thead><tbody>%s</tbody></table>" % (h, b)


# ================================================================================================= P3 column axis
def column_orientation_html(lat):
    """P3: the rule that orients a frame column standing in frames of both directions, and the columns it decides.
    lat = pkg['lateral_frame'] (its 'column_orientation' record comes from the frame sub-run's lateral_result)."""
    co = (lat or {}).get("column_orientation")
    if not isinstance(co, dict) or not co.get("rule"):
        return ""
    rows = co.get("shared_columns") or []
    if not rows:
        return ("<p class='note'><b>Column orientation.</b> No frame column stands in frames of both directions. %s</p>"
                % _e(co["rule"]))
    cells = []
    for r in rows:
        g = r.get("grid") or ["-", "-"]
        fx = "; ".join(r.get("frames_X") or []) or "-"
        fy = "; ".join(r.get("frames_Y") or []) or "-"
        cells.append((_e("x-line %s, y-line %s" % (g[0], g[1])), _e(fx), _e(fy), _e(r.get("strong_axis"))))
    return ("<p class='note'><b>Column orientation.</b> %d frame column(s) stand in frames of both directions. %s</p>"
            % (len(rows), _e(co["rule"]))
            + _t(["column (grid lines, counted from 0)", "X-direction frames", "Y-direction frames",
                  "strong axis in the plane of"], cells))
