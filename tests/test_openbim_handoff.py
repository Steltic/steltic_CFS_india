"""Exercise the real metric schema and stale-job protection when installed."""
import json
from pathlib import Path
import sys

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]/"steel_engine"))
pytest.importorskip("steltic_openbim_india.model")
import openbim_handoff as export


def inputs(job):
    out=job/"design"
    out.mkdir()
    native=dict(building="Probe",design_status=dict(status="partial",authority="native gates",n_reasons=1),
                lateral_frame={},cfs_connections=[],
                cfs_members=[dict(id="s",section="CLR100X50X15X2",n_ply=1,Fy_MPa=250,
                                  role="stud",DC=.6,ok=True,checks=[])])
    (out/"calc_package_cfs.json").write_text(json.dumps(native))
    return dict(schema_version="1.0",project=dict(id="Probe",name="Probe",module="CFS",units="mm"),
                materials={"CF":dict(grade="sheet",standard="IS 801",fy_mpa=250)},levels=[dict(id="G",elevation_mm=0)],
                grids={a:[dict(id="1",coordinate_mm=0)] for a in ("x","y")},profiles={},
                members=[dict(id="M",role="stud",start=[0,0,0],end=[0,0,3000],native_ref="cfs:s",material="CF")])


def test_binds_actual_member_and_rejects_same_name_geometry(tmp_path):
    layout=inputs(tmp_path)
    dest=export.write_handoff(tmp_path,layout)
    good=dest.read_bytes()
    spec=json.loads(good)
    label=spec["members"][0]["profile"]
    assert spec["checks"][-1]["status"]=="review"
    assert spec["source_evidence"]["files"]["design/calc_package_cfs.json"]==export.file_hash(tmp_path/"design/calc_package_cfs.json")
    supplied=spec["profiles"][label]
    supplied["dimensions_mm"]["t"]+=.5
    layout["profiles"][label]=supplied
    with pytest.raises(ValueError,match="authored profile"):
        export.write_handoff(tmp_path,layout)
    assert dest.read_bytes()==good


def test_export_rejects_concurrent_native_change(tmp_path,monkeypatch):
    layout=inputs(tmp_path)
    dest=export.write_handoff(tmp_path,layout)
    original=dest.read_bytes()
    import steltic_openbim_india.model as model
    real_validate=model.validate
    def update_after_read(data):
        source=tmp_path/"design/calc_package_cfs.json"
        native=json.loads(source.read_bytes())
        native["cfs_members"][0]["DC"]=1.1
        source.write_text(json.dumps(native))
        return real_validate(data)
    monkeypatch.setattr(model,"validate",update_after_read)
    with pytest.raises(ValueError,match="source changed"):
        export.write_handoff(tmp_path,layout)
    assert dest.read_bytes()==original


def test_vendored_hr_grade_and_thickness_strength(tmp_path):
    layout=inputs(tmp_path)
    lat=tmp_path/"lateral/Probe_lateral/design"
    lat.mkdir(parents=True)
    native=tmp_path/"design/calc_package_cfs.json"
    p=json.loads(native.read_bytes())
    p["lateral_frame"]={"members":[dict(id="b",section="WPB400X400X239.62",role="floor",DC=.72)]}
    native.write_text(json.dumps(p))
    (lat/"calc_package.json").write_text(json.dumps({"members":[dict(id="b",inputs=dict(grade="E250 C"),
                                                        governing_element_result=dict(fy_MPa=240))]}))
    layout["members"][0].update(native_ref="hr:b",material="HR")
    layout["materials"]["HR"]=dict(grade="E250 B0",standard="IS 2062")
    with pytest.raises(ValueError,match="material grade"):
        export.write_handoff(tmp_path,layout)
    layout["materials"]["HR"].update(grade="E250 C",fy_mpa=250)
    with pytest.raises(ValueError,match="material yield"):
        export.write_handoff(tmp_path,layout)
    del layout["materials"]["HR"]["fy_mpa"]
    model=json.loads(export.write_handoff(tmp_path,layout).read_bytes())
    assert model["materials"][model["members"][0]["material"]]["fy_mpa"]==240
