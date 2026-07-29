from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
import json
import math
import re
from typing import Dict, List, Tuple, Optional

import h5py
import numpy as np


H5_DIR = Path(r"E:\WuXi\Example_new\vtk_test_nh2sh_all")
VTK_DIR = Path(r"E:\SAM\Temp\VTK")
REPORT_JSON = Path(r"E:\WuXi\Example_new\vtk_geometry_viewer\sam_h5_vtk_validation.json")

VTK_TYPES = {
    "B31": 3,
    "B33": 3,
    "T3D2": 3,
    "S3": 5,
    "S3I": 5,
    "S3R": 5,
    "S4": 9,
    "S4I": 9,
    "S4R": 9,
    "C3D4": 10,
    "C3D6": 13,
    "C3D8": 12,
}


@dataclass
class VtkData:
    file: Path
    points: np.ndarray
    cells: List[List[int]]
    cell_types: np.ndarray
    point_fields: Dict[str, np.ndarray] = field(default_factory=dict)
    cell_fields: Dict[str, np.ndarray] = field(default_factory=dict)


def parse_vtk(path: Path) -> VtkData:
    toks = path.read_text(errors="ignore").split()
    i = 0
    n = len(toks)
    points = None
    cells: List[List[int]] = []
    cell_types = None
    point_fields: Dict[str, np.ndarray] = {}
    cell_fields: Dict[str, np.ndarray] = {}
    point_count = 0
    cell_count = 0
    section = None
    while i < n:
        t = toks[i]
        if t == "POINTS":
            point_count = int(toks[i + 1])
            i += 3
            points = np.array([float(x) for x in toks[i : i + point_count * 3]], dtype=np.float64).reshape(point_count, 3)
            i += point_count * 3
        elif t == "CELLS":
            cell_count = int(toks[i + 1])
            size = int(toks[i + 2])
            i += 3
            start = i
            for _ in range(cell_count):
                k = int(toks[i])
                i += 1
                cells.append([int(x) for x in toks[i : i + k]])
                i += k
            if i - start != size:
                raise ValueError(f"{path.name}: CELLS size mismatch")
        elif t == "CELL_TYPES":
            c = int(toks[i + 1])
            i += 2
            cell_types = np.array([int(x) for x in toks[i : i + c]], dtype=np.int32)
            i += c
        elif t == "POINT_DATA":
            point_count = int(toks[i + 1])
            section = "point"
            i += 2
        elif t == "CELL_DATA":
            cell_count = int(toks[i + 1])
            section = "cell"
            i += 2
        elif t == "VECTORS":
            name = toks[i + 1]
            i += 3
            count = point_count if section == "point" else cell_count
            arr = np.array([float(x) for x in toks[i : i + count * 3]], dtype=np.float64).reshape(count, 3)
            (point_fields if section == "point" else cell_fields)[name] = arr
            i += count * 3
        elif t == "TENSORS":
            name = toks[i + 1]
            i += 3
            count = point_count if section == "point" else cell_count
            arr = np.array([float(x) for x in toks[i : i + count * 9]], dtype=np.float64).reshape(count, 3, 3)
            (point_fields if section == "point" else cell_fields)[name] = arr
            i += count * 9
        elif t == "SCALARS":
            name = toks[i + 1]
            i += 3
            comp = 1
            if i < n and re.match(r"^\d+$", toks[i]):
                comp = int(toks[i])
                i += 1
            if i < n and toks[i] == "LOOKUP_TABLE":
                i += 2
            count = point_count if section == "point" else cell_count
            data = np.array([float(x) for x in toks[i : i + count * comp]], dtype=np.float64)
            arr = data if comp == 1 else data.reshape(count, comp)
            (point_fields if section == "point" else cell_fields)[name] = arr
            i += count * comp
        else:
            i += 1
    if points is None or cell_types is None:
        raise ValueError(f"{path.name}: incomplete VTK geometry")
    return VtkData(path, points, cells, cell_types, point_fields, cell_fields)


def frame_number(name: str) -> int:
    match = re.search(r"(\d+)$", name)
    return int(match.group(1)) if match else 0


def h5_frames(h5: h5py.File) -> List[Dict[str, str]]:
    out = []
    if "/Steps" not in h5:
        return out
    for step in sorted(h5["/Steps"].keys()):
        frroot = f"/Steps/{step}/Frames"
        if frroot not in h5:
            continue
        for frame in sorted(h5[frroot].keys(), key=frame_number):
            out.append({"step": step, "frame": frame, "path": f"{frroot}/{frame}"})
    return out


def h5_geometry_signature(path: Path) -> Dict:
    with h5py.File(path, "r") as h5:
        coords = h5["/Parts/Part-1/Nodes/Coordinates"][:].astype(np.float64)
        types: Dict[int, int] = {}
        cells = 0
        unsupported = []
        for cls in sorted(h5["/Parts/Part-1/Elements"].keys(), key=frame_number):
            g = h5[f"/Parts/Part-1/Elements/{cls}"]
            et = str(g.attrs.get("ElementType", ["?"])[0])
            n = len(g["Labels"])
            vt = VTK_TYPES.get(et)
            if vt is None:
                unsupported.append({"class": cls, "type": et, "count": n})
            else:
                types[vt] = types.get(vt, 0) + n
                cells += n
        return {
            "file": path.name,
            "points": len(coords),
            "cells": cells,
            "types": types,
            "bbox_min": coords.min(axis=0),
            "bbox_max": coords.max(axis=0),
            "frames": h5_frames(h5),
            "unsupported": unsupported,
        }


def vtk_signature(v: VtkData) -> Dict:
    types: Dict[int, int] = {}
    unique, counts = np.unique(v.cell_types, return_counts=True)
    for t, c in zip(unique.tolist(), counts.tolist()):
        types[int(t)] = int(c)
    return {
        "file": v.file.name,
        "points": int(v.points.shape[0]),
        "cells": len(v.cells),
        "types": types,
        "bbox_min": v.points.min(axis=0),
        "bbox_max": v.points.max(axis=0),
        "point_fields": sorted(v.point_fields.keys()),
        "cell_fields": sorted(v.cell_fields.keys()),
    }


def normalize_prefix(name: str) -> str:
    n = name.lower()
    n = re.sub(r"\.sam\.h5$|\.vtk$", "", n)
    n = re.sub(r"[_\-\s]+", "", n)
    n = n.replace("onemesh", "")
    return n


def name_score(vtk_name: str, h5_name: str) -> int:
    v = normalize_prefix(re.sub(r"_\d+$", "", Path(vtk_name).stem))
    h = normalize_prefix(Path(h5_name).stem)
    score = 0
    for token in re.split(r"[_\-]+", Path(h5_name).stem.lower()):
        if token and token not in {"sam", "h5"} and token in vtk_name.lower():
            score += len(token)
    if v and (v in h or h in v):
        score += max(len(v), len(h))
    return score


def h5_expected_cells(h5: h5py.File) -> Tuple[List[List[int]], np.ndarray, List[Tuple[str, int, str]]]:
    cells: List[List[int]] = []
    types: List[int] = []
    class_rows: List[Tuple[str, int, str]] = []
    for cls in sorted(h5["/Parts/Part-1/Elements"].keys(), key=frame_number):
        g = h5[f"/Parts/Part-1/Elements/{cls}"]
        et = str(g.attrs.get("ElementType", ["?"])[0])
        vt = VTK_TYPES.get(et)
        if vt is None:
            continue
        conn = g["Connectivities"][:].astype(int)
        for row, ids in enumerate(conn):
            cells.append(ids.tolist())
            types.append(vt)
            class_rows.append((cls, row, et))
    return cells, np.array(types, dtype=np.int32), class_rows


def aggregate_tensor_field(h5: h5py.File, frame_path: str, field: str, class_rows: List[Tuple[str, int, str]]) -> Optional[np.ndarray]:
    root = f"{frame_path}/{field}/Part-1-1"
    if root not in h5:
        return None
    values = np.zeros((len(class_rows), 4), dtype=np.float64)
    counts = np.zeros((len(class_rows),), dtype=np.int32)
    class_to_global: Dict[str, List[int]] = {}
    for i, (cls, row, _et) in enumerate(class_rows):
        class_to_global.setdefault(cls, []).append(i)
    for cls, global_indices in class_to_global.items():
        croot = f"{root}/{cls}"
        if croot not in h5:
            continue
        by_row = np.zeros((len(global_indices), 4), dtype=np.float64)
        c = 0
        for loc in h5[croot].keys():
            real_path = f"{croot}/{loc}/Real"
            if real_path not in h5:
                continue
            data = h5[real_path][:].astype(np.float64)
            cols = min(data.shape[1] if data.ndim > 1 else 1, 4)
            if data.ndim == 1:
                by_row[:, 0] += data[: len(global_indices)]
            else:
                by_row[:, :cols] += data[: len(global_indices), :cols]
            c += 1
        if c:
            by_row /= c
            for local, global_i in enumerate(global_indices):
                values[global_i, :] = by_row[local, :]
                counts[global_i] = c
    return values


def tensor4_to_vtk(v: np.ndarray) -> np.ndarray:
    out = np.zeros((v.shape[0], 3, 3), dtype=np.float64)
    out[:, 0, 0] = v[:, 0]
    out[:, 1, 1] = v[:, 1]
    out[:, 2, 2] = v[:, 2]
    out[:, 0, 1] = out[:, 1, 0] = v[:, 3]
    return out


def max_abs(a: np.ndarray, b: np.ndarray) -> float:
    if a is None or b is None:
        return math.inf
    if a.shape != b.shape:
        return math.inf
    if a.size == 0:
        return 0.0
    return float(np.max(np.abs(a - b)))


def scaled_tolerance(reference: np.ndarray, base: float = 1e-3, rel: float = 1e-7) -> float:
    if reference is None or reference.size == 0:
        return base
    scale = float(np.max(np.abs(reference)))
    return max(base, scale * rel)


def compare_h5_vtk(h5_path: Path, frame: Dict[str, str], vtk: VtkData) -> Dict:
    result = {
        "vtk": vtk.file.name,
        "h5": h5_path.name,
        "frame": frame["frame"],
        "step": frame["step"],
        "status": "PASS",
        "checks": {},
        "warnings": [],
    }
    with h5py.File(h5_path, "r") as h5:
        coords = h5["/Parts/Part-1/Nodes/Coordinates"][:].astype(np.float64)
        exp_cells, exp_types, class_rows = h5_expected_cells(h5)
        result["checks"]["points"] = {"h5": int(coords.shape[0]), "vtk": int(vtk.points.shape[0]), "pass": coords.shape[0] == vtk.points.shape[0]}
        result["checks"]["cells"] = {"h5": len(exp_cells), "vtk": len(vtk.cells), "pass": len(exp_cells) == len(vtk.cells)}
        result["checks"]["cell_types"] = {"pass": bool(np.array_equal(exp_types, vtk.cell_types))}
        result["checks"]["connectivity"] = {"mismatch": int(sum(1 for a, b in zip(exp_cells, vtk.cells) if a != b)), "pass": exp_cells == vtk.cells}
        result["checks"]["coords_max_error"] = max_abs(coords, vtk.points)

        frame_path = frame["path"]
        h5_fields = [k for k in h5[frame_path].keys()]
        result["h5_fields"] = sorted(h5_fields)
        result["vtk_point_fields"] = sorted(vtk.point_fields.keys())
        result["vtk_cell_fields"] = sorted(vtk.cell_fields.keys())

        for fld in ["U", "UR"]:
            h5p = f"{frame_path}/{fld}/Part-1-1/Real"
            if h5p in h5:
                h5_arr = h5[h5p][:].astype(np.float64)
                err = max_abs(h5_arr, vtk.point_fields.get(fld))
                scale = float(np.max(np.abs(h5_arr))) if h5_arr.size else 0.0
                tol = max(1e-4, scale * 1e-7)
                result["checks"][fld] = {"expected": True, "present": fld in vtk.point_fields, "max_error": err, "tolerance": tol, "pass": fld in vtk.point_fields and err <= tol}
            else:
                result["checks"][fld] = {"expected": False, "present": fld in vtk.point_fields, "pass": fld not in vtk.point_fields}

        for fld, comps in [("S", ["S11", "S22", "S33", "S12"]), ("E", ["E11", "E22", "E33", "E12"])]:
            h5_tensor = aggregate_tensor_field(h5, frame_path, fld, class_rows)
            expected = h5_tensor is not None
            present = fld in vtk.cell_fields
            item = {"expected": expected, "present": present, "pass": True}
            if expected:
                tensor_ref = tensor4_to_vtk(h5_tensor)
                tensor_tol = scaled_tolerance(tensor_ref)
                item["tensor_max_error"] = max_abs(tensor_ref, vtk.cell_fields.get(fld))
                item["tolerance"] = tensor_tol
                item["pass"] = present and item["tensor_max_error"] <= tensor_tol
                for idx, comp in enumerate(comps):
                    comp_present = comp in vtk.cell_fields
                    comp_err = max_abs(h5_tensor[:, idx], vtk.cell_fields.get(comp)) if comp_present else math.inf
                    comp_tol = scaled_tolerance(h5_tensor[:, idx])
                    item[comp] = {"present": comp_present, "max_error": comp_err, "tolerance": comp_tol, "pass": comp_present and comp_err <= comp_tol}
                    item["pass"] = item["pass"] and item[comp]["pass"]
                # Exporter also writes 13/23 as zero-filled components for 3D viewer compatibility.
                for zero_comp in [f"{fld}13", f"{fld}23"]:
                    if zero_comp in vtk.cell_fields:
                        zero_err = float(np.max(np.abs(vtk.cell_fields[zero_comp]))) if vtk.cell_fields[zero_comp].size else 0.0
                        item[zero_comp] = {"present": True, "max_abs": zero_err, "pass": zero_err < 1e-12}
            else:
                item["pass"] = not present
            result["checks"][fld] = item

        if aggregate_tensor_field(h5, frame_path, "S", class_rows) is not None:
            s = aggregate_tensor_field(h5, frame_path, "S", class_rows)
            s11, s22, s33, s12 = s[:, 0], s[:, 1], s[:, 2], s[:, 3]
            mises = np.sqrt(0.5 * ((s11 - s22) ** 2 + (s22 - s33) ** 2 + (s33 - s11) ** 2) + 3.0 * s12 * s12)
            pressure = -(s11 + s22 + s33) / 3.0
            mises_err = max_abs(mises, vtk.cell_fields.get("S_Mises"))
            pressure_err = max_abs(pressure, vtk.cell_fields.get("S_pressure"))
            mises_tol = scaled_tolerance(mises)
            pressure_tol = scaled_tolerance(pressure)
            result["checks"]["S_Mises"] = {"present": "S_Mises" in vtk.cell_fields, "max_error": mises_err, "tolerance": mises_tol, "pass": "S_Mises" in vtk.cell_fields and mises_err <= mises_tol}
            result["checks"]["S_pressure"] = {"present": "S_pressure" in vtk.cell_fields, "max_error": pressure_err, "tolerance": pressure_tol, "pass": "S_pressure" in vtk.cell_fields and pressure_err <= pressure_tol}

    def check_pass(x):
        if isinstance(x, dict) and "pass" in x:
            return bool(x["pass"])
        return True

    all_pass = True
    for val in result["checks"].values():
        if isinstance(val, dict) and "pass" in val:
            all_pass = all_pass and bool(val["pass"])
        elif isinstance(val, (int, float)):
            all_pass = all_pass and float(val) < 1e-3
    result["status"] = "PASS" if all_pass else "FAIL"
    return result


def infer_frame_index(vtk_name: str) -> int:
    m = re.search(r"_(\d+)\.vtk$", vtk_name)
    return int(m.group(1)) if m else 0


def main() -> None:
    h5_paths = sorted(H5_DIR.glob("*.sam.h5"))
    vtk_paths = sorted(VTK_DIR.glob("*.vtk"))
    h5_sigs = {p.name: h5_geometry_signature(p) for p in h5_paths}
    vtks = [parse_vtk(p) for p in vtk_paths]
    vtk_sigs = {v.file.name: vtk_signature(v) for v in vtks}

    mapping = []
    comparisons = []
    unmatched = []

    def comparison_score(comp: Dict) -> float:
        score = 0.0
        for fld in ["U", "UR"]:
            item = comp["checks"].get(fld, {})
            if item.get("expected") and item.get("present"):
                score += min(float(item.get("max_error", 1.0e30)), 1.0e30)
            elif item.get("expected") != item.get("present"):
                score += 1.0e20
        for fld in ["S", "E"]:
            item = comp["checks"].get(fld, {})
            if item.get("expected") and item.get("present"):
                score += min(float(item.get("tensor_max_error", 1.0e30)), 1.0e30)
            elif item.get("expected") != item.get("present"):
                score += 1.0e20
        return score

    for vtk in vtks:
        vs = vtk_sigs[vtk.file.name]
        candidates = []
        for h5_name, hs in h5_sigs.items():
            if hs["points"] == vs["points"] and hs["cells"] == vs["cells"] and hs["types"] == vs["types"]:
                candidates.append(h5_name)
        if not candidates:
            unmatched.append(vtk.file.name)
            continue
        idx = infer_frame_index(vtk.file.name)
        trial_rows = []
        for candidate in candidates:
            frames = h5_sigs[candidate]["frames"]
            frame = next((f for f in frames if frame_number(f["frame"]) == idx), None)
            if frame is None and idx < len(frames):
                frame = frames[idx]
            if frame is None and frames:
                frame = frames[0]
            if not frame:
                continue
            comp = compare_h5_vtk(H5_DIR / candidate, frame, vtk)
            trial_rows.append((comparison_score(comp), -name_score(vtk.file.name, candidate), candidate, frame, comp))
        if not trial_rows:
            unmatched.append(vtk.file.name)
            continue
        trial_rows.sort(key=lambda x: (x[0], x[1]))
        score, _neg_name_score, best, frame, comp = trial_rows[0]
        mapping.append({
            "vtk": vtk.file.name,
            "h5": best,
            "frame": frame["frame"],
            "step": frame["step"],
            "candidates": candidates,
            "match_score": score,
        })
        comparisons.append(comp)

    report = {
        "h5_dir": str(H5_DIR),
        "vtk_dir": str(VTK_DIR),
        "h5_count": len(h5_paths),
        "vtk_count": len(vtk_paths),
        "mapping": mapping,
        "unmatched_vtk": unmatched,
        "comparisons": comparisons,
    }
    REPORT_JSON.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print("wrote", REPORT_JSON)
    print("h5_count", len(h5_paths), "vtk_count", len(vtk_paths), "comparisons", len(comparisons), "unmatched", unmatched)
    print("failures", [c["vtk"] for c in comparisons if c["status"] != "PASS"])


if __name__ == "__main__":
    main()
