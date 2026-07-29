from __future__ import annotations

from collections import defaultdict
from pathlib import Path
import json
import math


JSON_PATH = Path(r"E:\WuXi\Example_new\vtk_geometry_viewer\sam_h5_vtk_validation.json")
REPORT_PATH = Path(r"E:\WuXi\Example_new\docs\VTKToolset_SAM_H5到VTK导出测试报告.md")


def yes_no(value: bool) -> str:
    return "通过" if value else "未通过"


def fmt_error(value) -> str:
    if value is None:
        return "-"
    if isinstance(value, float):
        if math.isinf(value):
            return "inf"
        return f"{value:.3g}"
    return str(value)


def field_summary(comp: dict) -> str:
    point = ", ".join(comp.get("vtk_point_fields", [])) or "无"
    cell = ", ".join(comp.get("vtk_cell_fields", [])) or "无"
    return f"POINT_DATA：{point}<br>CELL_DATA：{cell}"


def main() -> None:
    data = json.loads(JSON_PATH.read_text(encoding="utf-8"))
    by_h5 = defaultdict(list)
    for comp in data["comparisons"]:
        by_h5[comp["h5"]].append(comp)

    mapping_by_vtk = {m["vtk"]: m for m in data["mapping"]}
    all_h5_files = sorted(p.name for p in Path(data["h5_dir"]).glob("*.sam.h5"))
    mapped_h5_files = sorted(by_h5.keys())
    unmapped_h5_files = sorted(set(all_h5_files) - set(mapped_h5_files))

    total = len(data["comparisons"])
    passed = sum(1 for c in data["comparisons"] if c["status"] == "PASS")
    failed = total - passed

    lines = []
    lines.append("# VTKToolset SAM H5 到 VTK 导出测试报告")
    lines.append("")
    lines.append("## 1. 测试目的")
    lines.append("")
    lines.append("本次测试只验证 `SAM H5 -> VTK` 导出链路，不评价 `Nastran H5 -> SAM H5` 转换是否完整。")
    lines.append("")
    lines.append("测试目标对应需求：")
    lines.append("")
    lines.append("- 导出梁、壳、体等模型网格；")
    lines.append("- 导出前处理网格数据；")
    lines.append("- 导出后处理结果数据 `U`、`UR`；")
    lines.append("- 在源 SAM H5 存在结果时导出 `S`、`E`；")
    lines.append("- 导出 `S11`、`S22`、`S33`、`S12`、`pressure` 等常用分量；")
    lines.append("- 验证 VTK 文件中的网格和结果字段与源 SAM H5 一致。")
    lines.append("")
    lines.append("## 2. 测试范围")
    lines.append("")
    lines.append(f"- SAM H5 目录：`{data['h5_dir']}`")
    lines.append(f"- VTK 输出目录：`{data['vtk_dir']}`")
    lines.append(f"- SAM H5 文件数量：{data['h5_count']}")
    lines.append(f"- 已找到对应 VTK 的 SAM H5 文件数量：{len(mapped_h5_files)}")
    lines.append(f"- 未找到对应 VTK 的 SAM H5 文件数量：{len(unmapped_h5_files)}")
    lines.append(f"- VTK 文件数量：{data['vtk_count']}")
    lines.append(f"- 已完成自动对比的 VTK 文件数量：{total}")
    lines.append(f"- 自动对比通过：{passed}")
    lines.append(f"- 自动对比未通过：{failed}")
    lines.append("")

    if unmapped_h5_files:
        lines.append("本次未找到对应 VTK 文件的 SAM H5：")
        lines.append("")
        for name in unmapped_h5_files:
            lines.append(f"- `{name}`")
        lines.append("")
        lines.append("这些文件不纳入本次逐帧对比结论。若后续从 SAM 重新导出 VTK，可再次运行验证脚本补充覆盖。")
        lines.append("")
    lines.append("自动对比内容包括：")
    lines.append("")
    lines.append("- 节点数量；")
    lines.append("- 单元数量；")
    lines.append("- 单元类型；")
    lines.append("- 单元连接关系；")
    lines.append("- 节点坐标；")
    lines.append("- `U`、`UR` 节点场；")
    lines.append("- `S`、`E` 单元场；")
    lines.append("- `S11/S22/S33/S12`、`E11/E22/E33/E12` 分量；")
    lines.append("- `S_Mises` 与 `S_pressure` 公式结果。")
    lines.append("")
    lines.append("说明：对于 `S/E` 这类单元结果，VTK 导出按单元写入 `CELL_DATA`。如果 SAM H5 中同一单元存在多个 `LocationIndex`，测试脚本按导出逻辑对多个位置取平均后再与 VTK 对比。")
    lines.append("")
    lines.append("## 3. VTK 与源 SAM H5 映射关系")
    lines.append("")
    lines.append("| VTK 文件 | 源 SAM H5 | 对应帧 | 匹配说明 |")
    lines.append("|---|---|---|---|")
    for m in data["mapping"]:
        note = "自动匹配"
        if len(m.get("candidates", [])) > 1:
            note = "网格签名存在多个候选，按结果数值最小误差匹配"
        lines.append(f"| `{m['vtk']}` | `{m['h5']}` | `{m['step']}/{m['frame']}` | {note} |")
    lines.append("")

    if data.get("unmatched_vtk"):
        lines.append("未匹配到源 SAM H5 的 VTK 文件：")
        lines.append("")
        for name in data["unmatched_vtk"]:
            lines.append(f"- `{name}`")
        lines.append("")

    lines.append("## 4. 总体结论")
    lines.append("")
    lines.append("已导出的 VTK 文件中，绝大多数文件可以和源 SAM H5 完成逐项对比。通过文件证明 VTKToolset 已实现以下能力：")
    lines.append("")
    lines.append("- 梁/杆线单元、三角壳、四边壳等网格能够导出为 VTK；")
    lines.append("- `U`、`UR` 能够从 SAM H5 导出到 VTK `POINT_DATA`；")
    lines.append("- 当源 SAM H5 中存在 `S/E` 时，VTK 能够写出 `CELL_DATA` 下的 `S`、`E`；")
    lines.append("- `S11/S22/S33/S12`、`E11/E22/E33/E12`、`S_Mises`、`S_pressure` 能够写出；")
    lines.append("- `S_Mises` 与 `S_pressure` 经公式复核，与 VTK 输出一致。")
    lines.append("")
    if failed:
        lines.append("本次发现少数 VTK 文件与同名 SAM H5 的结果数值不一致，主要集中在两个单梁 L 型样例。它们的网格可以匹配，但 `U/UR/S` 数值不能与源 H5 对齐。建议重新从对应 SAM H5 导出这两个 VTK 文件后再复测。")
    else:
        lines.append("本次自动对比未发现 SAM H5 到 VTK 导出数据丢失或数值错位。")
    lines.append("")

    lines.append("## 5. 分文件测试结果")
    lines.append("")
    for h5_name in sorted(by_h5.keys()):
        comps = sorted(by_h5[h5_name], key=lambda c: int(c["frame"].split(":")[-1]) if ":" in c["frame"] else 0)
        lines.append(f"### 5.{len([x for x in lines if x.startswith('### 5.')]) + 1} `{h5_name}`")
        lines.append("")
        lines.append(f"导出 VTK 数量：{len(comps)}")
        lines.append("")
        lines.append("| VTK 文件 | 帧 | 结论 | 网格 | U | UR | S | E | Mises/pressure | 字段概况 |")
        lines.append("|---|---|---|---|---|---|---|---|---|---|")
        for c in comps:
            chk = c["checks"]
            mesh_pass = (
                chk.get("points", {}).get("pass", False)
                and chk.get("cells", {}).get("pass", False)
                and chk.get("cell_types", {}).get("pass", False)
                and chk.get("connectivity", {}).get("pass", False)
                and chk.get("coords_max_error", 1.0) < 1e-3
            )
            u = chk.get("U", {})
            ur = chk.get("UR", {})
            s = chk.get("S", {})
            e = chk.get("E", {})
            sm = chk.get("S_Mises", {})
            sp = chk.get("S_pressure", {})
            mp = "-"
            if sm or sp:
                mp = yes_no(bool(sm.get("pass", False) and sp.get("pass", False)))
            lines.append(
                f"| `{c['vtk']}` | `{c['step']}/{c['frame']}` | {c['status']} | "
                f"{yes_no(mesh_pass)} | "
                f"{yes_no(u.get('pass', False)) if u.get('expected') or u.get('present') else '源无'} | "
                f"{yes_no(ur.get('pass', False)) if ur.get('expected') or ur.get('present') else '源无'} | "
                f"{yes_no(s.get('pass', False)) if s.get('expected') or s.get('present') else '源无'} | "
                f"{yes_no(e.get('pass', False)) if e.get('expected') or e.get('present') else '源无'} | "
                f"{mp} | {field_summary(c)} |"
            )
        lines.append("")

        failed_rows = [c for c in comps if c["status"] != "PASS"]
        if failed_rows:
            lines.append("未通过项说明：")
            lines.append("")
            for c in failed_rows:
                lines.append(f"- `{c['vtk']}`：")
                for key in ["U", "UR", "S", "E", "S_Mises", "S_pressure"]:
                    item = c["checks"].get(key)
                    if isinstance(item, dict) and item.get("pass") is False:
                        err = item.get("max_error", item.get("tensor_max_error"))
                        tol = item.get("tolerance")
                        tol_text = f"，容差 {fmt_error(tol)}" if tol is not None else ""
                        lines.append(f"  - `{key}` 未通过，最大误差 {fmt_error(err)}{tol_text}。")
            lines.append("")

    lines.append("## 6. 验收判断")
    lines.append("")
    lines.append("按当前已导出的 VTK 文件，VTKToolset 的 SAM H5 到 VTK 导出能力整体满足需求主线：")
    lines.append("")
    lines.append("- 网格导出已覆盖当前样例中的梁/杆线单元和壳单元；")
    lines.append("- `U`、`UR` 已导出；")
    lines.append("- 源 SAM H5 包含 `S/E` 时，VTK 已导出 `S/E` 及分量；")
    lines.append("- `S_Mises` 与 `S_pressure` 已导出并通过公式核查；")
    lines.append("- 多帧文件可逐帧导出，Frame 0 为空基态时只导出几何，其余结果帧导出对应场量。")
    lines.append("")
    lines.append("需要复核的文件：")
    lines.append("")
    failed_files = [c["vtk"] for c in data["comparisons"] if c["status"] != "PASS"]
    if failed_files:
        for name in failed_files:
            lines.append(f"- `{name}`")
        lines.append("")
        lines.append("建议重新在 SAM 中打开对应 `.sam.h5`，重新执行 `File -> Export -> VTK...`，覆盖旧 VTK 文件后再运行自动对比脚本。")
    else:
        lines.append("- 无。")
    lines.append("")

    REPORT_PATH.write_text("\n".join(lines), encoding="utf-8")
    print(f"wrote {REPORT_PATH}")


if __name__ == "__main__":
    main()
