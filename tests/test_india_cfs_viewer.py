"""A saved native CFS viewer binds displayed sections and forces to its own job."""
import json
from pathlib import Path
import re
import sys
from types import ModuleType

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "steel_engine"))
import india_cfs_viewer as viewer


def test_portal_uses_metric_group_actions_and_safe_text():
    pkg = {
        "portal_frame_geometry": {"nodes": {"base": [0, 0], "top": [0, 3000]},
                                  "elements": [["base", "top", "col_L"]],
                                  "supports": {"base": [True, True, False]}, "units": "mm"},
        "portal": {"results_by_combo": {"DL</script>": {"forces": {"col_L": {
            "P_N": 12500., "V_N": 0., "M_Nmm": 2500000.}}}}},
        "cfs_members": [{"id": "Column 1", "role": "column", "section": "CLR150", "n_ply": 2, "DC": .967},
                        {"role": "joist", "DC": None}],
        "design_status": {"status": "partial"},
    }
    page = viewer.portal_page("Portal <north>", pkg)
    actual = json.loads(re.search(r'<script id="portal-actions" type="application/json">(.*?)</script>', page)[1])
    assert actual == {"DL</script>": {"col_L": [12500., 0., 2500000.]}}
    assert "<h1>Portal &lt;north&gt;</h1>" in page
    assert 'horizontal translation, vertical translation</title>' in page
    assert "in-plane rotation</title>" not in page
    assert '<td>CLR150</td><td>2</td><td>0.97</td>' in page
    assert 'not evaluated' in page and '3,000 mm' in page and 'PARTIAL' in page


def test_saved_hybrid_resolves_the_local_companion_and_binds_its_cfs_schedule(tmp_path, monkeypatch):
    job = tmp_path / "source"
    (job / "design").mkdir(parents=True)
    child = job / "lateral" / "FrameA"
    child.mkdir(parents=True)
    pkg = dict(building="Case", lateral_frame={"name": "FrameA", "root": "old-machine-path"},
               cfs_members=[dict(role="joist", section="C100", n_ply=2, DC=.451)],
               design_status={"status": "complete"})
    source = job / "design" / "calc_package_cfs.json"
    source.write_text(json.dumps(pkg), encoding="utf8")
    before = source.read_bytes()
    template = "<!doctype html><html><head></head><body>" + viewer.PROJECT_ACTIONS + "</body></html>"
    def rebuild(frame_job, path):
        assert frame_job == child
        Path(path).write_text(template, encoding="utf8")
    native = ModuleType("hr_vendor.viewer3d")
    native.rebuild_saved = rebuild
    monkeypatch.setitem(sys.modules, "hr_vendor.viewer3d", native)
    out = tmp_path / "web"
    main, companion = viewer.rebuild_saved(job, out)
    assert main == out / "viewer_3d.html"
    assert companion == out / "lateral" / "FrameA" / "viewer_3d.html"
    assert companion.read_text(encoding="utf8") == template
    assert "<td>C100</td><td>2</td><td>0.45</td>" in main.read_text(encoding="utf8")
    assert source.read_bytes() == before and not (job / "viewer_3d.html").exists()
    with pytest.raises(ValueError, match="separate"):
        viewer.rebuild_saved(job, job)
    with pytest.raises(ValueError, match="no unique"):
        viewer.hybrid_page("<html></html>", pkg)
