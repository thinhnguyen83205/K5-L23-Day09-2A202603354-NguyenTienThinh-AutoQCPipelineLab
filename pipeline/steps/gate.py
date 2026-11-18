"""BƯỚC 4 — Cửa chặn: quyết định Release / Hold / Rework."""
from ..common import ERROR, WARN


def decide(issues, image_stems, cfg, reviewed=frozenset()):
    stems = set(image_stems)                      # danh sách ảnh hiện có
    n_images = len(stems)                         # MẪU SỐ = số ảnh

    # Đếm lỗi bắt buộc: KHÔNG bỏ qua dù ảnh đã được duyệt
    n_errors = sum(1 for i in issues if i.severity == ERROR)

    # Tập các ẢNH (không trùng) còn cảnh báo chưa ai duyệt
    warn_imgs = {i.image for i in issues
                 if i.severity == WARN
                 and i.image in stems              # bỏ "data.yaml", "<dataset>", ảnh đã xoá
                 and i.image not in reviewed}      # bỏ ảnh người đã xem

    ratio = round(len(warn_imgs) / n_images, 4) if n_images else 0
    thr = cfg["gate"]["warn_ratio_hold"]

    if n_errors:
        decision = "Rework"
        reasons = [f"còn {n_errors} lỗi bắt buộc (ERROR): phải sửa trước khi xuất"]
    elif ratio >= thr:
        decision = "Hold"
        reasons = [f"{len(warn_imgs)}/{n_images} ảnh ({ratio:.1%}) còn cảnh báo "
                   f"chưa được người duyệt, >= ngưỡng {thr:.0%}"]
    else:
        decision = "Release"
        reasons = [f"0 lỗi bắt buộc; {len(warn_imgs)}/{n_images} ảnh ({ratio:.1%}) "
                   f"còn cảnh báo, < ngưỡng {thr:.0%}"]

    return {"decision": decision, "n_errors": n_errors,
            "n_warn_images": len(warn_imgs), "n_images": n_images,
            "warn_ratio": ratio, "reasons": reasons}