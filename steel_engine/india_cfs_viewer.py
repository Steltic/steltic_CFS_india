"""Publish metric CFS viewers from the final calculation package and saved frame model."""
from __future__ import annotations

import argparse
import html
import json
import math
import os
from pathlib import Path
import re
import tempfile

from report_cfs_second_wave import member_ratios


HERE = Path(__file__).resolve().parent
PROJECT_ACTIONS = "<!-- native project actions -->"


def _text(value):
    return html.escape(str(value), quote=True)


def _number(value, places=2):
    if isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(value):
        return f"{value:.{places}f}"
    return "not evaluated"


def _write(path, content):
    """Publish a complete UTF-8 document with no partial reads during replacement."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(dir=path.parent, delete=False) as f:
        temporary = Path(f.name)
    try:
        temporary.write_bytes(content.encode("utf-8"))
        os.replace(temporary, path)
    finally:
        temporary.unlink(missing_ok=True)
    return path


def _schedule(pkg):
    rows = []
    for member in pkg.get("cfs_members", []):
        strength = member_ratios(member).get("strength")
        if strength:
            ratio = _number(strength["dc"], 3)
            check = " / ".join(str(v) for v in (strength.get("check"), strength.get("combination")) if v)
        else:
            # Legacy jobs may retain a single group ratio without classified check rows.
            ratio = _number(member.get("DC"))
            check = "Native group ratio (check class unreported)" if ratio != "not evaluated" else "not evaluated"
        row = (member.get("id") or member.get("role") or "Unidentified group",
               member.get("role") or "not declared", member.get("section") or "not declared",
               member.get("n_ply", 1), ratio, check)
        rows.append("<tr>" + "".join(f"<td>{_text(v)}</td>" for v in row) + "</tr>")
    if not rows:
        return "<p>No cold-formed member groups were reported.</p>"
    columns = ("Native design group", "Role", "Section", "Plies", "Group D/C", "Check / combination")
    return ('<div class="cfs-scroll"><table aria-label="Cold-formed design groups"><thead><tr>' +
            "".join(f'<th scope="col">{c}</th>' for c in columns) +
            "</tr></thead><tbody>" + "".join(rows) + "</tbody></table></div>")


def _schedule_caption(pkg):
    state = (pkg.get("design_status") or {}).get("status") or "unreported"
    return (f'<p>Native design status <strong>{_text(state.upper())}</strong>. '
            'The group strength ratios and load combinations come from the IS 801 calculation. '
            '<a href="report.html">Open the calculation report for checks and assumptions.</a></p>')


def hybrid_page(frame_html, pkg):
    """Keep the navigable HR analysis and add the job's separate IS 801 design groups."""
    if frame_html.count(PROJECT_ACTIONS) != 1:
        raise ValueError("The analytical viewer has no unique project actions slot. Rebuild its native frame viewer first.")
    schedule = ('<p class="sub" id="cfs-view-scope">Analytical hot-rolled lateral frame</p>'
                "<button type=\"button\" id=\"cfs-open\" class=\"reset\">Cold-formed member schedule</button>"
                '<dialog id="cfs-schedule" aria-labelledby="cfs-schedule-title">'
                '<form method="dialog"><button aria-label="Close schedule">Close</button></form>'
                '<h2 id="cfs-schedule-title">Cold-formed member schedule</h2>'
                '<p>The 3D model shows the analytical hot-rolled frame. This schedule identifies '
                'the cold-formed sections selected for this building.</p>' + _schedule_caption(pkg) +
                _schedule(pkg) + '</dialog>')
    style = """<style>
    #cfs-schedule{width:min(720px,90vw);max-height:80vh;max-width:92vw;box-sizing:border-box;margin:auto;
      padding:20px;border:1px solid #476171;border-radius:8px;background:#18232c;color:#e7eef2;overflow:auto}
    #cfs-schedule::backdrop{background:rgba(0,0,0,.65)} #cfs-schedule form{float:right}
    #cfs-schedule button{padding:.35rem .75rem} #cfs-schedule h2{color:inherit;text-transform:none;font-size:18px}
    #cfs-schedule p{margin:.6rem 0} #cfs-schedule a{color:#9bd1ff}
    #cfs-schedule table{width:100%;border-collapse:collapse;font-size:13px} #cfs-schedule th,#cfs-schedule td{
      text-align:left;padding:.4rem;border-bottom:1px solid #455560;white-space:nowrap}.cfs-scroll{overflow:auto}
    </style>"""
    script = """<script>document.getElementById('cfs-open').addEventListener('click', function () {
      document.getElementById('cfs-schedule').showModal();
    });</script>"""
    page = frame_html.replace(PROJECT_ACTIONS, schedule)
    return page.replace("</head>", style + "</head>", 1).replace("</body>", script + "</body>", 1)


def _portal_svg(geometry):
    nodes = {str(k): tuple(map(float, xy)) for k, xy in geometry["nodes"].items()}
    xs, zs = zip(*nodes.values())
    xmin, xmax, zmin, zmax = min(xs), max(xs), min(zs), max(zs)
    scale = min(790 / max(1., xmax-xmin), 300 / max(1., zmax-zmin))
    def plot(point):
        x, z = point
        return 55 + (x-xmin)*scale, 340 - (z-zmin)*scale
    marks = []
    for a, b, raw_label in geometry["elements"]:
        label = str(raw_label)
        x1, y1 = plot(nodes[str(a)])
        x2, y2 = plot(nodes[str(b)])
        kind = next((s for s in ("col", "raf", "knee", "mezz") if s in label.lower()), "other")
        length = math.dist(nodes[str(a)], nodes[str(b)])
        escaped = _text(label)
        marks.append(f'<g class="elem {kind}" data-label="{escaped}"><title>{escaped}, {length:,.1f} mm segment</title>'
                     f'<line x1="{x1:.3f}" y1="{y1:.3f}" x2="{x2:.3f}" y2="{y2:.3f}"/></g>')
    for node, flags in geometry.get("supports", {}).items():
        x, y = plot(nodes[str(node)])
        axes = ("horizontal translation", "vertical translation", "in-plane rotation")
        label = "Support restraint unreported"
        if isinstance(flags, (list,tuple)) and len(flags) == 3 and all(f in (0, 1) for f in flags):
            restraints = ", ".join(axis for axis, fixed in zip(axes, flags) if fixed)
            label = "Restrained " + restraints if restraints else "No in-plane degrees of freedom restrained"
        marks.append(f'<rect x="{x-5:.3f}" y="{y:.3f}" width="10" height="5"><title>Node {_text(node)}. {_text(label)}</title></rect>')
    marks.append(f'<text x="55" y="377">Transverse span {xmax-xmin:,.0f} mm</text>'
                 f'<text x="55" y="23">Highest workpoint {zmax:,.0f} mm</text>')
    return ('<svg viewBox="0 0 900 395" role="img" aria-label="Transverse portal analytical elevation">' +
            "".join(marks) + "</svg>")


def portal_page(name, pkg):
    geometry = pkg["portal_frame_geometry"]
    if geometry.get("units", "mm") != "mm":
        raise ValueError("The portal elevation requires native coordinates in millimetres")
    results = (pkg.get("portal") or {}).get("results_by_combo") or {}
    groups = list(dict.fromkeys(str(e[2]) for e in geometry["elements"]))
    # Only the three reported maxima cross this boundary. Each maximum can occur at a different station.
    actions = {}
    for combination, record in results.items():
        actions[combination] = {label: [row.get(k) for k in ("P_N", "V_N", "M_Nmm")]
                                for label, row in (record.get("forces") or {}).items()}
    def options(values):
        return "".join(f'<option value="{_text(v)}">{_text(v)}</option>' for v in values)
    interactive = ""
    if actions:
        interactive = ('<section aria-labelledby="actions-title"><h2 id="actions-title">Portal member actions</h2>'
                       '<p>Each value is an independent maximum absolute force over the named analysis member '
                       'in one load combination.</p><div class="controls"><label>Load combination '
                       f'<select id="combination">{options(actions)}</select></label><label>Analysis member '
                       f'<select id="member">{options(groups)}</select></label></div>'
                       '<dl aria-live="polite"><div><dt>Axial force</dt><dd id="axial"></dd></div>'
                       '<div><dt>Shear force</dt><dd id="shear"></dd></div>'
                       '<div><dt>Bending moment</dt><dd id="moment"></dd></div></dl></section>')
    encoded = json.dumps(actions, ensure_ascii=True, allow_nan=False, separators=(",", ":")).replace("<", r"\u003c").replace(">", r"\u003e").replace("&", r"\u0026")
    counts = []
    if geometry.get("n_frames"):
        counts.append(f'{int(geometry["n_frames"])} transverse frames')
    if geometry.get("spacing_mm"):
        counts.append(f'{float(geometry["spacing_mm"]):,.0f} mm frame spacing')
    eq = (pkg.get("lateral_frame") or {}).get("seismic_summary") or {}
    if eq.get("R") is not None:
        counts.append(f'seismic R = {_number(eq["R"], 1)}')
    page = (HERE / "cfs_portal_viewer.html").read_text(encoding="utf-8")
    values = dict(TITLE=_text(name), FRAME_INFO=" &middot; ".join(counts), SVG=_portal_svg(geometry),
                  CONTROLS=interactive, DATA=encoded, SCHEDULE=_schedule(pkg), CAPTION=_schedule_caption(pkg))
    # One substitution pass also preserves user-supplied strings that happen to contain source placeholders.
    return re.sub(r"__(TITLE|FRAME_INFO|SVG|CONTROLS|DATA|SCHEDULE|CAPTION)__", lambda m: values[m[1]], page)


def write_portal(name, pkg, path):
    return str(_write(path, portal_page(name, pkg)))


def _local_frame(job, pkg):
    name = (pkg.get("lateral_frame") or {}).get("name")
    if not isinstance(name, str) or not name or name in (".", "..") or "/" in name or "\\" in name or ":" in name:
        raise ValueError("The saved CFS package has no valid lateral frame name")
    return Path(job) / "lateral" / name


def write_new_job_viewer(root, name, pkg):
    """The child HR job has already issued its metric viewer; bind it to this CFS schedule."""
    job = Path(root)
    if pkg.get("portal_frame_geometry"):
        return write_portal(name, pkg, job / "viewer_3d.html")
    lateral = pkg.get("lateral_frame") or {}
    if not lateral.get("name"):
        return None
    frame = _local_frame(job, pkg) / "viewer_3d.html"
    if not frame.is_file() and (lateral.get("status") or {}).get("status") != "complete":
        return None
    return str(_write(job / "viewer_3d.html", hybrid_page(frame.read_text(encoding="utf-8"), pkg)))


def rebuild_saved(job, output):
    """Write the viewer and its lateral companion from a saved job without executing archived scripts."""
    job, output = Path(job).resolve(), Path(output).resolve()
    if output.is_relative_to(job):
        raise ValueError("Choose a separate output directory to preserve the saved native job")
    pkg = json.loads((job / "design" / "calc_package_cfs.json").read_bytes())
    name = pkg["building"]
    if pkg.get("portal_frame_geometry"):
        return [_write(output / "viewer_3d.html", portal_page(name, pkg))]
    frame = _local_frame(job, pkg)
    import india_cfs_env  # Enable the vendored India engine's flat import layout.
    from hr_vendor.viewer3d import rebuild_saved as rebuild_frame
    with tempfile.TemporaryDirectory() as temp:
        staged = Path(temp) / "viewer_3d.html"
        rebuild_frame(frame, staged)
        native_html = staged.read_text(encoding="utf-8")
        cfs_html = hybrid_page(native_html, pkg)
    companion = output / frame.relative_to(job) / "viewer_3d.html"
    return [_write(output / "viewer_3d.html", cfs_html), _write(companion, native_html)]


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Rebuild a CFS job's analytical web viewers in a separate directory.")
    parser.add_argument("job", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    for path in rebuild_saved(args.job, args.output):
        print(path)
