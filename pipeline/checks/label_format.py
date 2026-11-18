"""CHECK 2 — Dòng nhãn YOLO: sai định dạng, ID lớp lạ, box tràn ảnh, box rỗng, box lặp.   (Script 2 trong slide)   ★★

Test:  pytest tests/test_label_format.py -q

Mỗi dòng nhãn: `id cx cy w h` (5 số, toạ độ 0–1). Trả về list[Issue]; `Issue.line` = số dòng (đếm từ 1).

| code             | severity | khi nào                                                                  |
|------------------|----------|--------------------------------------------------------------------------|
| BAD_FORMAT       | ERROR    | không đúng 5 cột số (dùng `parse_yolo_line`, bắt `ValueError`)           |
| BAD_CLASS_ID     | ERROR    | id lớp ngoài 0..len(ds.classes)-1                                        |
| BOX_ZERO         | ERROR    | w <= 0 hoặc h <= 0                                                       |
| BOX_OUT_OF_IMAGE | ERROR    | mép box vượt [0,1] quá `cfg["label_format"]["overflow_tol"]`; extra={"overflow": mức tràn} |
| DUP_BOX          | ERROR    | cùng lớp với một dòng TRƯỚC ĐÓ và IoU > `dup_box_iou`; báo ở dòng SAU    |
| BOX_TINY         | WARN     | cạnh ngắn của box (px) < `min_box_px`  (cần `ds.image_size(stem)`)       |
| BOX_HUGE         | WARN     | w*h > `max_box_frac`                                                     |

Gợi ý
- Mép trái = x - w/2, mép phải = x + w/2 (xem câu hỏi "dòng YOLO nào lỗi?" trong slide).
- Một dòng hỏng (BAD_FORMAT, BAD_CLASS_ID, BOX_ZERO) thì `continue`, đừng kiểm tiếp hình học của dòng đó.
- Dòng thiếu cột làm script của slide dừng giữa chừng: đây là lý do phải `try/except`.
- `iou_xywh(a, b)` có sẵn trong common.py.
- Ngưỡng nằm trong `cfg["label_format"]` — đừng viết cứng số vào code.
"""
"""CHECK 2 — Dòng nhãn YOLO: sai định dạng, ID lớp lạ, box tràn ảnh, box rỗng, box lặp."""
from ..common import ERROR, WARN, Issue, iou_xywh, parse_yolo_line


def run(ds, cfg):
    lf = cfg["label_format"]                      # đọc ngưỡng từ cấu hình, KHÔNG viết cứng
    tol, min_px = lf["overflow_tol"], lf["min_box_px"]
    max_frac, dup_iou = lf["max_box_frac"], lf["dup_box_iou"]
    n_cls = len(ds.classes)                       # = 4 lớp
    issues = []

    for lab in ds.label_files():                  # duyệt từng file .txt
        stem = lab.stem                           # "img_0001.txt" -> "img_0001"
        size = ds.image_size(stem)                # (rộng, cao) px, None nếu ảnh hỏng
        seen = []                                 # box hợp lệ đã gặp, để bắt DUP_BOX

        for ln_no, text in ds.read_label_lines(stem) or []:

            def add(sev, code, msg, **extra):
                issues.append(Issue("label_format", sev, code, stem, msg, ln_no, extra))

            # (1) Đủ 5 cột số chưa?
            try:
                c, x, y, w, h = parse_yolo_line(text)
            except ValueError as e:
                add(ERROR, "BAD_FORMAT", f"dòng sai định dạng: {e}")
                continue

            # (2) ID lớp có trong 0..3?
            if not 0 <= c < n_cls:
                add(ERROR, "BAD_CLASS_ID", f"id lớp {c} ngoài 0..{n_cls - 1}")
                continue

            # (3) Box rỗng?
            if w <= 0 or h <= 0:
                add(ERROR, "BOX_ZERO", f"box rộng/cao bằng 0 (w={w}, h={h})")
                continue

            # (4) Tràn ra ngoài ảnh? Lấy mức tràn lớn nhất của 4 mép
            overflow = max(0.0,
                           -(x - w / 2),          # mép trái
                           (x + w / 2) - 1,       # mép phải
                           -(y - h / 2),          # mép trên
                           (y + h / 2) - 1)       # mép dưới
            if overflow > tol:
                add(ERROR, "BOX_OUT_OF_IMAGE", f"box tràn ảnh {overflow:.4f}",
                    overflow=round(overflow, 6))

            # (5) Trùng box cùng lớp ở dòng trước?
            box = (x, y, w, h)
            if any(pc == c and iou_xywh(pb, box) > dup_iou for pc, pb in seen):
                add(ERROR, "DUP_BOX", "box trùng với một dòng trước đó")
            seen.append((c, box))

            # (6) Quá nhỏ? (cạnh ngắn tính bằng pixel)
            if size:
                W, H = size
                short = min(w * W, h * H)
                if short < min_px:
                    add(WARN, "BOX_TINY", f"cạnh ngắn {short:.1f}px < {min_px}px")

            # (7) Quá to?
            if w * h > max_frac:
                add(WARN, "BOX_HUGE", f"box phủ {w*h:.0%} ảnh")

    return issues