# Baseline ontology gợi ý

Package riêng để chạy `bench_kg.py` nguyên bản qua `LAB_SOLUTION_PACKAGE`.
KG-2 dùng `parse_law_article`, `extract_news_cases`, `suggested_constraints`,
`add_law_article`, `add_news_case` từ code starter. Không dùng Charge/Sentence mới.
Adapter bật json_mode=True khi gọi extraction để parser starter nhận JSON hợp lệ.
KG-3 theo đường Case → Crime ← Article → Clause của LAB_GUIDE, có nhánh tổng hợp Q6.
KG-4 dùng prompt gốc; ontology mới có chỉ dẫn phân biệt status/stage/scope bổ sung.
Vì vậy so sánh benchmark là so sánh hai pipeline hoàn chỉnh, không phải thí nghiệm
chỉ thay schema trong khi mọi thành phần khác giữ nguyên. Trích xuất LLM có biến động.

```powershell
$env:LAB_SOLUTION_PACKAGE='baseline_solution'
.\.venv\Scripts\python.exe -X utf8 -B bench_kg.py --judge --out ket_qua_benchmark_kg.hint.txt
.\.venv\Scripts\python.exe -X utf8 -B -m scripts.collect_bonus_evidence baseline
Remove-Item Env:LAB_SOLUTION_PACKAGE
```

Lệnh benchmark reset graph. Trước khi chạy baseline, capture graph mới bằng:

```powershell
.\.venv\Scripts\python.exe -X utf8 -B -m scripts.collect_bonus_evidence custom
```

Khôi phục snapshot đã capture (không gọi LLM, không tính là benchmark mới):

```powershell
.\.venv\Scripts\python.exe -X utf8 -B -m scripts.collect_bonus_evidence restore
```

Để đo lại ontology mới, bỏ `LAB_SOLUTION_PACKAGE`, tắt cache extraction,
chạy `bench_kg.py --judge` và capture custom sau khi kết thúc.
