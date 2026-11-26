"""Optional exporter for an India CFS design job and its declared physical layout.

The native analysis selects sections, check results and grades. Physical
occurrences (including explicit secondary placement, panel holes and connection
parts) come from the building designer. No bay or fastener layout is inferred
from a schedule. See docs/openbim.md.
"""
import copy
import csv
import hashlib
import json
import math
import os
from pathlib import Path
from tempfile import NamedTemporaryFile


def file_hash(path):
    with path.open("rb") as source:
        return hashlib.file_digest(source, "sha256").hexdigest() if hasattr(hashlib, "file_digest") else _digest(source)


def _digest(source):
    digest = hashlib.sha256()
    for block in iter(lambda: source.read(1024 * 1024), b""):
        digest.update(block)
    return digest.hexdigest()


def _governing(identifier, row, description):
    checks = [c for c in row.get("checks", []) if isinstance(c, dict) and not c.get("informational")]
    if isinstance(row.get("checks"), dict):
        checks = [c for c in row["checks"].values() if isinstance(c, dict) and not c.get("informational")]
    utilization = row.get("DC", row.get("dc"))
    if not isinstance(utilization, (int, float)) or not math.isfinite(utilization) or utilization < 0:
        utilization = None
    failed = row.get("ok") is False or any(c.get("ok") is False for c in checks) or (utilization is not None and utilization > 1)
    incomplete = any(c.get("ok") is None for c in checks) or bool(row.get("not_evaluated"))
    status = "fail" if failed else "review" if incomplete or utilization is None else "pass"
    result = {"id": identifier, "description": description, "status": status,
              "reference": row.get("governing_clause") or row.get("clause") or row.get("limit_state") or "native calculation package"}
    if utilization is not None:
        result["utilization"] = utilization
    return result


def _catalog(pkg):
    records, checks = {}, {}
    lateral = pkg.get("lateral_frame") or {}
    groups = [("cfs", pkg.get("cfs_members", [])), ("hr", lateral.get("members") or []),
              ("connection", pkg.get("cfs_connections", [])),
              ("hr-connection", lateral.get("connections") or [])]
    for group, items in groups:
        for row in items:
            rid = group + ":" + row["id"]
            if rid in records:
                raise ValueError("duplicate native design record: " + rid)
            records[rid] = row
            checks[rid] = _governing(rid, row, row.get("governing_check") or row.get("type") or row.get("role") or rid)
    for k, row in enumerate(lateral.get("drift_table") or []):
        rid = f"drift:{k+1}"
        checks[rid] = _governing(rid, row, f"Storey {row.get('storey')} {row.get('dir')} drift {row.get('load','')}".strip())
    return records, checks


def _rolled_sections():
    directory = Path(__file__).parent / "hr_vendor"
    catalog = {}
    for file in ("is808_shapes.csv", "is1161_tubes.csv"):
        with (directory / file).open(encoding="utf-8-sig", newline="") as source:
            catalog.update({row["Label"]: row for row in csv.DictReader(source) if row.get("validated") == "ok"})
    return catalog


def _profile(section, count, rolled, polygons):
    from is811_sections import props
    if section in rolled:
        r = rolled[section]
        if r["Type"] == "CHS":
            return dict(family="CHS", dimensions_mm=dict(diameter=float(r["D_mm"]), t=float(r["t_mm"])))
        # Rolled angles (ISA), channels and I-sections share the SI catalogue.
        family = "L" if r["Type"] == "ISA" else "C" if r["Type"] in ("MC", "MCP", "LC", "SC", "ISMC") else "I"
        if family=="I" and r["Type"] not in ("NPB","WPB","MB","HB","LB","WB","JB","ISMB","ISWB","ISLB","ISHB","ISJB"):
            raise ValueError(f"Supply explicit section geometry for {section} ({r['Type']})")
        dims = dict(d=float(r["D_mm"]), b=float(r["B_mm"]), tw=float(r["tw_mm"]), tf=float(r["tf_mm"]),
                    r=float(r.get("R1_mm") or 0), r2=float(r.get("R2_mm") or 0))
        if family=="I": dims["slope_deg"]=float(r.get("flange_slope_deg") or 90)-90
        if count != 1:
            raise ValueError("Supply explicit contours for a built-up rolled profile")
        return dict(family=family, dimensions_mm=dims)
    p=props(section)
    kind=p["type"]
    if kind in ("EA","UA"):
        family="L"
    elif kind=="LZ" or (p.get("generic") and section.startswith("Z")):
        family="Z"
    elif kind.startswith("C") or (p.get("generic") and section.startswith("C")):
        family="C"
    else:
        raise ValueError(f"Supply explicit contours for {section} ({kind})")
    dims=dict(d=p["h"],b=p["b"],t=p["t"],lip=p.get("c") or 0,r=p.get("Ri") or 0)
    result=dict(family=family,dimensions_mm=dims)
    if count==1:
        return result
    if count!=2 or family!="C":
        raise ValueError("Supply explicit contours for this built-up section")
    single=polygons(result)[0]
    ring=[[round(x+dims["b"]/2,5),round(y,5)] for x,y in list(single.exterior.coords)[:-1]]
    return dict(family="POLYGON",contours_mm=[ring,[[-x,y] for x,y in reversed(ring)]])


def write_handoff(job_root, layout):
    """Bind the declared mm layout to THIS native job and write its checked sidecar.

    Members carry native_ref 'cfs:<id>' or 'hr:<id>'. Explicit supplemental
    geometry instead uses a declared profile and a reference to a review check.
    With no native result the exporter fails before replacing an existing file.
    """
    try:
        from steltic_openbim_india.model import validate
        from steltic_openbim_india.profiles import section_polygons
    except ImportError as ex:
        raise ImportError("Install steltic_openBIM_india to export a physical CFS layout.") from ex
    root = Path(job_root).resolve()
    source_name = "design/calc_package_cfs.json"
    raw = (root / source_name).read_bytes()
    pkg = json.loads(raw)
    files = {source_name: hashlib.sha256(raw).hexdigest()}
    model = copy.deepcopy(layout)
    if model["project"].get("id") != pkg["building"] or model["project"].get("module")!="CFS":
        raise ValueError("layout project must identify the native CFS job")
    records, checks = _catalog(pkg)
    for name in ("cfg_snapshot.json","load_plan.json","STATUS.md","EOR_inputs.json","report.html","viewer_3d.html"):
        if (root/name).is_file():
            files[name]=file_hash(root/name)
    lateral = Path("lateral")/(pkg["building"]+"_lateral")
    for filename in ("design/calc_package.json","design/member_schedule.csv","lateral_result.json","report.html","viewer_3d.html"):
        relative=(lateral/filename).as_posix()
        path=root/relative
        if not path.is_file():
            continue
        if filename=="design/calc_package.json":
            raw=path.read_bytes()
            files[relative]=hashlib.sha256(raw).hexdigest()
            for full in json.loads(raw).get("members",[]):
                group=records.get("hr:"+full["id"])
                if group is not None:
                    group["native_grade"]=(full.get("inputs") or {}).get("grade")
                    group["native_fy"]=(full.get("governing_element_result") or {}).get("fy_MPa")
        else:
            files[relative]=file_hash(path)
    material_profiles = model.setdefault("profiles", {})
    declared_profile_names = set(material_profiles)
    native_names = set()
    rolled = _rolled_sections()
    authored = list(model.get("checks", []))
    if any(c["id"] in checks or c["id"]=="native:status" for c in authored):
        raise ValueError("layout check identifier collides with a native result")
    for collection, allowed in (("members", ("cfs","hr")), ("connections",("connection","hr-connection"))):
        for item in model.get(collection,[]):
            ref=item.pop("native_ref",None)
            if not ref:
                if collection=="members" and not any(c["id"] in item.get("checks",[]) and c["status"]=="review" for c in authored):
                    raise ValueError(f"{item['id']}: unbound supplemental member needs an explicit review check")
                continue
            if ref not in records or ref.split(":",1)[0] not in allowed:
                raise ValueError(f"{item['id']}: unknown native {collection} record {ref}")
            item["checks"] = list(dict.fromkeys([*item.get("checks", []),ref]))
            if collection=="members":
                row=records[ref]
                sec=row["section"]
                count=int(row.get("n_ply") or 1)
                label=(f"{count}x" if count>1 else "")+sec
                if item.get("profile",label)!=label:
                    raise ValueError(f"{item['id']}: declared profile differs from native selection {label}")
                item["profile"]=label
                if label not in native_names:
                    native_profile=_profile(sec,count,rolled,section_polygons)
                    if label in declared_profile_names:
                        actual=section_polygons(material_profiles[label])
                        expected=section_polygons(native_profile)
                        if len(actual)!=len(expected) or any(
                            not any(a.symmetric_difference(e).area <= max(e.area*1e-7,1e-6) for a in actual)
                            for e in expected
                        ):
                            raise ValueError(f"{label}: authored profile geometry differs from native dimensions")
                    material_profiles[label]=native_profile
                    native_names.add(label)
                material=model["materials"][item["material"]]
                if row.get("native_grade") and material["grade"].casefold().strip()!=row["native_grade"].casefold().strip():
                    raise ValueError(f"{item['id']}: material grade must match native {row['native_grade']}")
                expected_fy=row.get("Fy_MPa") or row.get("native_fy")
                if expected_fy is not None:
                    fy=material.get("fy_mpa")
                    if fy is not None and abs(fy-expected_fy)>1e-6:
                        raise ValueError(f"{item['id']}: material yield must match native {expected_fy} MPa")
                    if fy is None:
                        # An IS 2062 grade can have different design strengths
                        # by thickness. Keep the native effective Fy per group.
                        item["material"]=f"{item['material']}-{expected_fy:g}MPa"
                        resolved=dict(material,fy_mpa=expected_fy)
                        if model["materials"].setdefault(item["material"],resolved)!=resolved:
                            raise ValueError("material key collision: "+item["material"])
    st=pkg["design_status"]
    model["checks"] = [*authored,*checks.values(),dict(id="native:status",description=f"Steltic India design gate: {st['status']}",
                                                         reference=st["authority"],status="pass" if st["status"]=="complete" else "review")]
    model["source_evidence"] = dict(files=files,
                                    design_status=st["status"],gate_reasons=st.get("n_reasons"),native_job=pkg["building"])
    validate(model)
    dest=root/"design"/"openbim_handoff.json"
    tmp=None
    try:
        with NamedTemporaryFile(mode="w",encoding="utf-8",dir=dest.parent,delete=False) as out:
            tmp=Path(out.name)
            json.dump(model,out,ensure_ascii=False,separators=(",",":"),allow_nan=False)
        for name,expected in files.items():
            if file_hash(root/name)!=expected:
                raise ValueError("native source changed during export: "+name)
        os.replace(tmp,dest)
    finally:
        if tmp is not None:
            tmp.unlink(missing_ok=True)
    return dest
