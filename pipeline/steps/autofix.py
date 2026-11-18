"""BƯỚC 2/4 — Sửa tự động những lỗi bắt buộc mà máy sửa được AN TOÀN."""
from collections import defaultdict

import yaml

from ..common import ERROR, parse_yolo_line

DROP = {"BAD_FORMAT", "BAD_CLASS_ID", "BOX_ZERO", "DUP_BOX"}                       # xoá dòng
REMOVE = {"DUP_IMAGE_EXACT", "DUP_IMAGE_NEAR", "LEAK_TEST", "CORRUPT_IMAGE", "BAD_SIZE"}  # xoá ảnh


def _clip(text):
    """Cắt box về trong [0,1]. Trả về dòng mới, hoặc None nếu box nằm hẳn ngoài ảnh."""
    c, x, y, w, h = parse_yolo_line(text)
    # đổi (tâm, rộng, cao) -> (4 mép), rồi kẹp mỗi mép vào [0, 1]
    x1, y1 = max(0.0, x - w / 2), max(0.0, y - h / 2)
    x2, y2 = min(1.0, x + w / 2), min(1.0, y + h / 2)
    if x2 <= x1 or y2 <= y1:                      # BẪY 3: không còn diện tích
        return None
    # đổi ngược (4 mép) -> (tâm, rộng, cao)
    return f"{c} {(x1 + x2) / 2:.6f} {(y1 + y2) / 2:.6f} {x2 - x1:.6f} {y2 - y1:.6f}"


def fix(ds, issues, cfg):
    errors = [i for i in issues if i.severity == ERROR]     # bỏ qua WARN
    fixes = []

    # ---- 1) Lỗi cấp ẢNH: xoá ảnh + nhãn ----
    removed = set()
    for i in errors:
        if i.code in REMOVE and i.image not in removed:
            p = ds.image_path(i.image)
            if p is None:
                continue
            p.unlink()                                       # xoá ảnh
            lab = ds.label_path(i.image)
            if lab.exists():
                lab.unlink()                                 # xoá nhãn
            removed.add(i.image)
            fixes.append({"image": i.image, "line": "", "action": "remove_image",
                          "before": p.name, "after": f"(đã xoá: {i.code})"})

    # ---- 2) Lỗi cấp DÒNG: gom theo file (BẪY 1) ----
    drop, clip = defaultdict(set), defaultdict(set)
    for i in errors:
        if i.image in removed or i.line is None:             # ảnh đã xoá thì bỏ qua êm
            continue
        if i.code in DROP:
            drop[i.image].add(i.line)
        elif i.code == "BOX_OUT_OF_IMAGE":
            clip[i.image].add(i.line)

    for stem in sorted(set(drop) | set(clip)):
        p = ds.label_path(stem)
        if not p.exists():
            continue
        raw = p.read_text(encoding="utf-8", errors="replace").splitlines()
        out = []
        for n, text in enumerate(raw, 1):         # BẪY 2: n đếm cả dòng trống = số dòng gốc
            if n in drop[stem]:                   # BẪY 4: xoá được ưu tiên trước cắt
                fixes.append({"image": stem, "line": n, "action": "drop_line",
                              "before": text, "after": ""})
                continue
            if n in clip[stem]:
                new = _clip(text)
                if new is None:                   # BẪY 3
                    fixes.append({"image": stem, "line": n, "action": "drop_line",
                                  "before": text, "after": ""})
                    continue
                fixes.append({"image": stem, "line": n, "action": "clip_box",
                              "before": text, "after": new})
                text = new
            out.append(text)
        p.write_text("".join(l + "\n" for l in out), encoding="utf-8")   # ghi MỘT lần

    # ---- 3) Thiếu file nhãn: KHÔNG bịa, chỉ ghi chuyển người ----
    for i in errors:
        if i.code == "MISSING_LABEL_FILE" and i.image not in removed:
            fixes.append({"image": i.image, "line": "", "action": "needs_label",
                          "before": "(không có file)", "after": "chuyển người gán"})

    # ---- 4) Tên lớp sai trong data.yaml ----
    if any(i.code == "BAD_CLASS_NAME" for i in errors):
        data = yaml.safe_load(ds.yaml_path.read_text(encoding="utf-8")) or {}
        before = data.get("names")
        data["names"] = {k: v for k, v in enumerate(cfg["classes"])}
        ds.yaml_path.write_text(yaml.safe_dump(data, allow_unicode=True, sort_keys=False),
                                encoding="utf-8")
        fixes.append({"image": "data.yaml", "line": "", "action": "rename_classes",
                      "before": str(before), "after": str(cfg["classes"])})

    return fixes