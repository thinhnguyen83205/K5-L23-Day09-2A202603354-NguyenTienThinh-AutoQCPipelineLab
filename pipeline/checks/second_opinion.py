"""CHECK 6 — Ý kiến thứ hai: so nhãn với một model LỚN HƠN (yolo26l). Chỉ CẢNH BÁO."""
from ..common import WARN, Issue, iou_xywh, parse_yolo_line
from ..model_cache import get_preds


def run(ds, cfg, preds=None):
    so = cfg["second_opinion"]                    # mọi ngưỡng đọc từ config
    if preds is None:
        preds = get_preds(ds, cfg, "checker")     # đọc dự đoán đã lưu sẵn
    issues = []

    for img in ds.image_files():
        stem = img.stem
        lines = ds.read_label_lines(stem)         # giữ SỐ DÒNG GỐC
        if stem not in preds or lines is None:    # không có dự đoán / không có file nhãn
            continue
        size = ds.image_size(stem)
        if not size:
            continue
        W, H = size

        # Nhãn hợp lệ, kèm số dòng gốc: (số dòng, lớp, box)
        labels = []
        for n, text in lines:
            try:
                c, x, y, w, h = parse_yolo_line(text)
            except ValueError:
                continue                          # dòng hỏng: bỏ qua, không làm chết script
            if 0 <= c < len(ds.classes):
                labels.append((n, c, (x, y, w, h)))

        # ===== (a) Nhìn từ phía MODEL =====
        for p in preds[stem]:
            pc, conf, box = int(p[0]), p[1], tuple(p[2:6])
            # lọc: model không đủ tự tin, hoặc vật quá nhỏ
            if conf < so["conf"] or box[2] * W * box[3] * H < so["min_area_px"]:
                continue

            # các nhãn chồng lên dự đoán đủ nhiều (mọi lớp)
            cands = [(iou_xywh(box, lb), lc) for _, lc, lb in labels]
            cands = [(v, lc) for v, lc in cands if v >= so["iou_missing"]]
            same = [v for v, lc in cands if lc == pc]      # IoU của nhãn cùng lớp
            other = [v for v, lc in cands if lc != pc]     # IoU của nhãn khác lớp

            if not cands:                                   # (1)
                issues.append(Issue("second_opinion", WARN, "POSSIBLE_MISSING", stem,
                                    f"model thấy lớp {pc} (conf {conf:.2f}) mà nhãn không có box",
                                    extra={"conf": conf}))
            elif same:                                      # (2)
                if max(same) < so["iou_loose"]:
                    issues.append(Issue("second_opinion", WARN, "POSSIBLE_LOOSE_BOX", stem,
                                        f"đúng lớp nhưng IoU {max(same):.2f} thấp",
                                        extra={"conf": conf, "iou": round(max(same), 3)}))
            elif max(other) >= so["iou_match"]:            # (3)
                issues.append(Issue("second_opinion", WARN, "POSSIBLE_WRONG_CLASS", stem,
                                    f"model nói lớp {pc}, nhãn khác lớp (IoU {max(other):.2f})",
                                    extra={"conf": conf, "iou": round(max(other), 3)}))

        # ===== (b) Nhìn từ phía NHÃN =====
        # dùng fp_conf (thấp hơn) và KHÔNG lọc diện tích: chỉ cần model "hơi thấy" là đủ
        fp_preds = [tuple(p[2:6]) for p in preds[stem] if p[1] >= so["fp_conf"]]
        for n, lc, lb in labels:
            if all(iou_xywh(lb, pb) < so["iou_missing"] for pb in fp_preds):
                issues.append(Issue("second_opinion", WARN, "POSSIBLE_FALSE_POS", stem,
                                    "box nhãn không khớp vật nào model thấy", n))
    return issues