# Báo cáo Day 09 — Nguyễn Tiến Thịnh, 2A202603354

## 1. Kết luận trước
Pipeline kết luận **Hold** (mã thoát 10). Vào **224 ảnh**, bước nhận loại **22 ảnh**, xuất **202 ảnh** ra `export/clean_v1/`. Đây là **bản nháp, chưa phát hành**.
Lý do: sau khi máy sửa và người duyệt 80 ảnh thì không còn lỗi bắt buộc nào (0 ERROR trong `07_error_list_v3`). Tuy nhiên vẫn còn **38/202 ảnh (18.8%)** có cảnh báo chưa được người xem, vượt ngưỡng 10%. Nguyên nhân là hàng đợi có 125 ảnh, lớn hơn ngân sách duyệt 80 ảnh.

## 2. Lỗi và phân việc
Số liệu lấy từ `01_intake` và `02_error_list_v1` (202 ảnh sau bước nhận; riêng các lỗi ảnh tính trên 224 ảnh đầu vào).

| Mã lỗi | Số ảnh/dòng | Ai sửa (máy/người) | Vì sao |
|---|---:|---|---|
| DUP_IMAGE_EXACT | 8 ảnh / 224 | máy (loại ảnh) | trùng từng byte (md5): giữ ảnh sẽ làm model học lặp |
| DUP_IMAGE_NEAR | 4 ảnh / 224 | máy (loại ảnh) | trùng gần đúng (phash ≤ 12) |
| LEAK_TEST | 5 ảnh / 224 | máy (loại ảnh) | trùng ảnh test/val: giữ lại thì metric đẹp giả |
| BAD_SIZE | 3 ảnh / 224 | máy (loại ảnh) | cạnh ngắn < 250 px |
| CORRUPT_IMAGE | 2 ảnh / 224 | máy (loại ảnh) | không mở/giải mã được |
| BOX_OUT_OF_IMAGE | 8 dòng | máy (`clip_box`) | cắt box về trong [0,1] là an toàn, giữ nguyên lớp |
| DUP_BOX | 7 dòng | máy (`drop_line`) | box vẽ hai lần (vd. `img_0001` dòng 3) |
| BAD_CLASS_ID | 6 dòng | máy (`drop_line`) | id 93, 7, 4, −1: không biết lớp thật nên xoá dòng |
| BOX_ZERO | 4 dòng | máy (`drop_line`) | box không có diện tích |
| BAD_FORMAT | 3 dòng | máy (`drop_line`) | `nan`, thiếu cột |
| BAD_CLASS_NAME | 2 (data.yaml) | máy (`rename_classes`) | `Person`, `Bus` viết hoa sai |
| MISSING_LABEL_FILE | 6 ảnh | **người** (gán mới) | máy không được bịa nhãn → `needs_label` |
| POSSIBLE_MISSING | 53 | **người** | model thấy vật nhưng nhãn không có box (chỉ là nghi ngờ) |
| POSSIBLE_FALSE_POS | 29 | **người** | box nhãn không khớp vật nào model thấy |
| POSSIBLE_LOOSE_BOX | 28 | **người** | đúng lớp nhưng IoU thấp |
| POSSIBLE_WRONG_CLASS | 18 | **người** | car↔truck↔bus: lỗi ý nghĩa, chỉ người quyết |
| EMPTY_LABEL | 12 | **người** | ảnh nền thật hay người gán quên? |
| BOX_TINY / BOX_HUGE / CLASS_RARE | 6 / 3 / 4 | **người** | quy tắc dự án, chỉ cảnh báo |

Tổng cộng máy thực hiện **35 thay đổi** (`03_fixes.csv`: 20 `drop_line`, 8 `clip_box`, 1 `rename_classes`, 6 `needs_label`). Sau khi máy sửa, `04_error_list_v2` chỉ còn **6 lỗi bắt buộc**, cả 6 đều là ảnh thiếu file nhãn.

**Hàng đợi:** `05_review_queue.csv` xếp theo tổng trọng số của các cờ trên mỗi ảnh. Ảnh thiếu nhãn (`NEEDS_LABEL` = 10) đứng đầu vì nếu không gán thì cả lô phải Rework. Tiếp theo là ảnh vừa bị máy xoá dòng vừa có nhiều cờ ngữ nghĩa (vd. `img_0020`, ưu tiên 11.5). Sau đó đến `WRONG_CLASS` (3), `MISSING` / `FALSE_POS` (2)… Với ngân sách 80 ảnh, người duyệt hết 6 ảnh thiếu nhãn và 74 ảnh có cờ, nhờ đó số cảnh báo ngữ nghĩa giảm từ **123** (trên 103 ảnh) xuống **57** (trên 54 ảnh). Còn 45/125 ảnh trong hàng đợi chưa được xem (ảnh thứ 81 có ưu tiên 3.33).

## 3. Calibration (2 ngưỡng)
| Tham số | Khởi đầu | Đã chọn | Precision / Recall (trước → sau) | Lý do (đánh đổi) |
|---|---|---|---|---|
| `duplicates.phash_dist` | 2 | **12** | DUP_IMAGE_NEAR: 1.00 / 0.50 → 1.00 / 0.67 | Ở 2 bỏ sót một nửa số ảnh trùng gần đúng. Khoảng 4–14 có cùng P/R trên calib; trên raw, khoảng 10–14 bắt thêm được cặp trùng thật `img_0186`–`img_0061` mà không loại oan ảnh nào. Chọn 12 ở giữa khoảng để có biên an toàn cả hai phía. |
| `second_opinion.conf` | 0.25 | **0.6** | WRONG_CLASS 0.56/0.83 → 0.62/0.83; MISSING 0.50/1.00 → 0.57/1.00 | Mức precision cao nhất mà recall MISSING vẫn còn 1.00. Từ 0.7 trở lên, recall MISSING giảm (0.88, rồi 0.75): bắt đầu bỏ sót vật bị quên gán. |

**Calibration đánh lừa ở đâu:**
- `phash_dist = 16` có **F1 cao nhất trên calib** (0.91). Nhưng khi chạy trên raw, bước nhận loại **31 ảnh** thay vì 22, tức loại thêm 9 ảnh. Mở ra xem thì nhiều cặp **hoàn toàn khác nhau**: `img_0013` (bàn làm việc với laptop) bị coi là rò rỉ của `test_087` (sân bóng chày), còn `img_0011` (tennis) bị coi là trùng `img_0008` (trượt tuyết). Calib chỉ có 6 cặp trùng gần đúng, quá ít để thấy cái giá của việc nới ngưỡng.
- `conf = 0.8` làm pipeline ra **Release** (13–16 ảnh còn cảnh báo, < 10%). Nhưng dữ liệu không hề tốt hơn: chỉ là tắt bớt cảnh báo, và recall MISSING tụt xuống 0.75. Vì vậy tôi không chọn ngưỡng theo kết luận của gate.

## 4. Cửa chặn và điều pipeline KHÔNG bắt được
**(a) Gate chặn đúng.** Chạy `python -m pipeline.run --budget 0 --reports work/rep_nb --export-dir work/exp_nb` (không có người duyệt) cho kết quả **REWORK — còn 6 lỗi bắt buộc**, mã thoát **20**, log ghi "KHÔNG xuất". Thư mục `work/exp_nb` không được tạo. 6 ảnh thiếu file nhãn không được máy tự bịa nhãn, nên lô bị chặn.

**(b) Điểm mù:**
1. **Box lỏng gần như không bị bắt:** recall `POSSIBLE_LOOSE_BOX` trên calib chỉ **0.20** (bắt 1/5) ở mọi mức conf ≥ 0.4.
2. **Model lớn cũng sai:** precision `POSSIBLE_FALSE_POS` chỉ **0.31**. Sau khi người đã thay bằng nhãn đúng, 80 ảnh đã duyệt vẫn còn **29 cảnh báo** của model, nghĩa là model đang cãi lại người. Ngược lại, nếu model và người gán cùng bỏ sót một vật (vật nhỏ, bị che) thì không có cảnh báo nào.
3. **Ảnh trùng biến đổi mạnh:** ở `phash_dist = 12`, recall DUP_IMAGE_NEAR trên calib là 0.67, tức 2/6 cặp trùng bị lọt.
4. **4 ảnh `EMPTY_LABEL`** còn lại: máy không phân biệt được ảnh nền thật với ảnh người gán quên.

(Lỗi tự thấy khi xem `viz_labels.py`: `img_0001` dòng 3 vẽ trùng box dòng 1; `img_0030` dòng 9 box tràn mép trái 0.023; TODO: thêm 1 lỗi bạn tự thấy.)

## 5. Train: raw vs clean (tùy chọn, chấm riêng)
**Chưa chạy.** Tôi ưu tiên hoàn thành phần lõi (pipeline, calibration, báo cáo) trước; phần train trên Colab sẽ làm sau.

## 6. Quyết định và ghi chú AI
**(a)** Quyết định: **Hold**. `clean_v1` chỉ dùng để thử nghiệm, chưa phát hành. Để thành **Release** cần: (1) tăng ngân sách duyệt để người xem thêm ít nhất khoảng 18 ảnh trong 45 ảnh còn lại của hàng đợi, sao cho số ảnh còn cảnh báo < 21/202; (2) chạy lại `make run`, kiểm tra 0 ERROR và tỉ lệ cảnh báo < 10%. Không được nới `conf` chỉ để gate im lặng.

**(b) AI:** Có dùng Claude.
- *Prompt chính:* nhờ hướng dẫn từng bước và giải thích lab, rồi đưa docstring và test của từng module để viết code.
- *Cách kiểm:* chạy `pytest` từng module (14/10/11/15 test), toàn bộ 79 test; đối chiếu kết quả `label_format` với `img_0001`, `img_0030` đã tính tay; mở ảnh để kiểm các cặp bị cho là trùng.
- *1 lần AI sai:* AI hướng dẫn cài Python 3.13 bằng `winget` và `py install`, nhưng máy không có `winget` và `py` là launcher bản cũ không có lệnh `install`; cuối cùng phải tải bộ cài từ python.org.