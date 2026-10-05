# Cải tiến B1, Q6 và graph context — 05-10-2026

Cùng corpus, model, top_k=3, chunk_size=800, 176 chunks. Các file benchmark do bench_kg.py nguyên bản sinh ra.
Bảng dùng bản trước cải tiến và lượt cuối của code sau cải tiến; các lượt chẩn đoán giữ riêng trong evidence/. Có biến động extraction/LLM/API. USD là ước tính theo bảng giá code, không phải tổng tiền mọi lượt chạy.

| GraphRAG | Trước | Sau |
| --- | --- | --- |
| Indexing USD | 0.01699 | 0.01520 |
| Indexing giây | 186.8 | 147.0 |
| Input token / câu | 10088 | 2413 |
| Query USD / câu | 0.00158 | 0.00042 |
| Query giây / câu | 3.34 | 2.67 |
| Recall / judge | 1.00 / 2.00 | 1.00 / 2.00 |

Input token giảm 76.1%; USD querying giảm 73.4%.

| Câu | Trước recall / judge | Sau recall / judge |
| --- | --- | --- |
| Q1 | 1.00 / 2 | 1.00 / 2 |
| Q2 | 1.00 / 2 | 1.00 / 2 |
| Q3 | 1.00 / 2 | 1.00 / 2 |
| Q4 | 1.00 / 2 | 1.00 / 2 |
| Q5 | 1.00 / 2 | 1.00 / 2 |
| Q6 | 1.00 / 2 | 1.00 / 2 |

## B1

Trước:
```json
[
  {
    "person": "Nguyễn Văn Quang",
    "doc_id": "news-100260924105118645",
    "case_id": "case:b8e0e153b69e763a2e175c81",
    "raw_charge": "Nhận hối lộ và đánh bạc",
    "crime": null,
    "status": "prosecuted",
    "charge_stage": "prosecution",
    "event_date": "",
    "evidence_text": "Điều dưỡng Nguyễn Văn Quang bị truy tố cả tội nhận hối lộ và đánh bạc, do nhiều lần cá độ bóng đá quốc tế với số tiền giao dịch lên tới 10 triệu đồng mỗi trận.",
    "sentence": null,
    "sentence_stage": null,
    "months": null,
    "scope": null,
    "sentence_evidence": null
  }
]
```

Sau:
```json
[
  {
    "person": "Nguyễn Văn Quang",
    "doc_id": "news-100260924105118645",
    "case_id": "case:b8e0e153b69e763a2e175c81",
    "raw_charge": "đánh bạc",
    "crime": null,
    "status": "prosecuted",
    "charge_stage": "prosecution",
    "event_date": "",
    "evidence_text": "Điều dưỡng Nguyễn Văn Quang bị truy tố cả tội nhận hối lộ và đánh bạc, do nhiều lần cá độ bóng đá quốc tế với số tiền giao dịch lên tới 10 triệu đồng mỗi trận.",
    "sentence": null,
    "sentence_stage": null,
    "months": null,
    "scope": null,
    "sentence_evidence": null
  },
  {
    "person": "Nguyễn Văn Quang",
    "doc_id": "news-100260924105118645",
    "case_id": "case:b8e0e153b69e763a2e175c81",
    "raw_charge": "nhận hối lộ",
    "crime": null,
    "status": "prosecuted",
    "charge_stage": "prosecution",
    "event_date": "",
    "evidence_text": "Điều dưỡng Nguyễn Văn Quang bị truy tố cả tội nhận hối lộ và đánh bạc, do nhiều lần cá độ bóng đá quốc tế với số tiền giao dịch lên tới 10 triệu đồng mỗi trận.",
    "sentence": null,
    "sentence_stage": null,
    "months": null,
    "scope": null,
    "sentence_evidence": null
  }
]
```

## Q6

Đọc nguyên câu trả lời Q6 trong ket_qua_benchmark_kg.txt; context trả một mục cho mỗi Case hoặc nhóm có bằng chứng xác nhận.
Không hợp nhất node liên tài liệu, không ghi đè doc_id. Source list được giữ trong mỗi mục.

## Cách giảm context

- Lọc người được hỏi và tội liên quan trước khi mở rộng luật; câu khung cơ bản lấy khoản 1.
- Câu tối đa lấy phần mở đầu khung phạt các khoản; câu theo chất giữ các điểm liên quan và điểm tổng khối lượng.
- Không thêm lại cạnh seed dạng hash; bỏ lặp summaries/person/case trong câu tổng hợp.
- Giữ đầy đủ evidence_text trong graph, dùng trích đoạn nguyên văn có dấu […] trong prompt.
- Ngân sách phần graph 5.000 token (ước tính byte/3 khi thiếu tiktoken), bỏ nguyên facts thấp ưu tiên; chunks vector không cắt.

## Giới hạn

- Phát hiện compound charge dựa danh sách tội rõ ràng trong nguồn, không bảo đảm phát hiện mọi cách diễn đạt.
- Nhóm Case liên tài liệu bảo thủ; có thể còn trùng khi thiếu ngày/địa điểm/bằng chứng chung.
- Rút phần đầu khoản chỉ dùng cho câu hỏi mức tối đa; câu hỏi điều kiện áp dụng cần các điểm đầy đủ liên quan.
- Đánh giá bằng keyword recall và LLM judge vẫn cần kiểm tra nguồn; không xác minh luật hiện hành.
- Không sửa base RAG, test gốc, benchmark, câu hỏi/gold/must_include.
