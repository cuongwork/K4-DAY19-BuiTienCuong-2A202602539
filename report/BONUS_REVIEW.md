# Bằng chứng baseline và ontology mới — 05-10-2026

## Thiết lập

- Corpus: 18 điều luật + 20 bài báo; SHA-256 toàn bộ nội dung trùng nhau giữa hai lần capture.
- Cùng OpenAI gpt-4o-mini, text-embedding-3-small, top_k=3, chunk_size=800, 176 chunks.
- Cùng bench_kg.py nguyên bản; test gốc và benchmark không bị sửa.
- Baseline dùng package baseline_solution, helper/schema gợi ý và JSON mode cho extraction.
- Ontology mới có prompt extraction, KG-3 và chỉ dẫn trả lời khác; đây là so sánh pipeline, không cô lập riêng hiệu ứng schema.
- Bảng dùng lượt đo cuối của từng phiên bản; các lượt chẩn đoán lỗi giữ riêng trong evidence/. Temperature=0 vẫn có biến động LLM/API. Không suy ra thời gian indexing chỉ do schema.
- USD do bảng giá trong src/llm.py ước tính, không phải hóa đơn; không gồm judge trong chi phí pipeline.
- Baseline text mode thất bại được giữ ở evidence/baseline_failed_*.json và baseline_failed_text_mode.txt, không dùng làm baseline chính.

## Benchmark GraphRAG trước/sau

| Câu | Gợi ý recall / judge | Mới recall / judge |
| --- | --- | --- |
| Q1 | 1.00 / 2 | 1.00 / 2 |
| Q2 | 1.00 / 2 | 1.00 / 2 |
| Q3 | 0.67 / 1 | 1.00 / 2 |
| Q4 | 0.67 / 1 | 1.00 / 2 |
| Q5 | 1.00 / 2 | 1.00 / 2 |
| Q6 | 0.67 / 2 | 1.00 / 2 |

| Chỉ số GraphRAG | Gợi ý | Mới |
| --- | --- | --- |
| Node / cạnh | 205 / 384 | 282 / 519 |
| Indexing calls | 196 | 198 |
| Indexing USD | 0.00942 | 0.01520 |
| Indexing giây | 101.0 | 147.0 |
| Querying recall / judge | 0.83 / 1.67 | 1.00 / 2.00 |
| Querying in_tok trung bình | 5893 | 2413 |
| Querying USD / câu | 0.00093 | 0.00042 |
| Querying giây / câu | 2.22 | 2.67 |

Đọc nguyên câu trả lời trong hai file benchmark ở root; recall keyword và LLM judge không thay thế kiểm tra nguồn.

## B1–B4: truy vấn graph có thể kiểm chứng

Đây là kết quả truy vấn graph, không phải benchmark QA của GraphRAGAgent cho B1–B4.
Cypher, parameters và raw rows đầy đủ nằm trong evidence/baseline_bonus.json và evidence/custom_bonus.json.

| Câu | Kết quả baseline | Kết quả mới |
| --- | --- | --- |
| B1 | Có Quang nhưng raw_charge rỗng | Hai Charge độc lập, prosecuted, cùng nguồn |
| B2 | 24 tháng tù, không có stage | 24 tháng, first_instance, per_charge |
| B3 | Không có dòng Nguyễn Hữu Đức | withdrawn, bằng chứng hủy quyết định khởi tố |
| B4 | 6 kết quả sau chuẩn hóa Python | 6 kết quả lọc số trực tiếp |

Nguồn đối chiếu:

- B1: data/drug_news/news-100260924105118645.md, đoạn “Điều dưỡng Nguyễn Văn Quang bị truy tố cả tội nhận hối lộ và đánh bạc”.
- B2: data/drug_news/news-100260918080821054.md, đoạn “Từ đó, tòa sơ thẩm tuyên Thành 36 tháng tù” và câu tiếp theo về Kiên/Tuấn/Hưng 24 tháng; đoạn đầu xác nhận phúc thẩm bị hoãn.
- B3: data/drug_news/news-100260917203001265.md, đoạn ngày 13-4-2026 hủy quyết định khởi tố Đức.
- B4: bài Thành nêu 4 người 24–36 tháng; news-100260928173914514.md nêu Đinh Đức Tuấn và Trần Ngọc Thảo 2 năm 6 tháng (30 tháng).

### B1: Nguyễn Văn Quang: các tội bị truy tố

Baseline raw rows:
```json
[
  {
    "person": "Nguyễn Văn Quang",
    "doc_id": "news-100260924105118645",
    "case_name": "Vụ án tại Viện Pháp y tâm thần Trung ương",
    "raw_charge": "",
    "sentence": "",
    "role": "bị cáo"
  }
]
```

Ontology mới raw rows:
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

### B2: Trịnh Vũ Kiên: 24 tháng thuộc giai đoạn nào

Baseline raw rows:
```json
[
  {
    "person": "Trịnh Vũ Kiên",
    "doc_id": "news-100260918080821054",
    "case_name": "Vụ góp tiền mua ma túy tại Hà Nội",
    "raw_charge": "mua bán trái phép chất ma túy",
    "sentence": "24 tháng tù",
    "role": "bị cáo"
  }
]
```

Ontology mới raw rows:
```json
[
  {
    "person": "Trịnh Vũ Kiên",
    "doc_id": "news-100260918080821054",
    "case_id": "case:b55b08f76fb235f1afa659d2",
    "raw_charge": "mua bán trái phép chất ma túy",
    "crime": "mua bán trái phép chất ma túy",
    "status": "convicted",
    "charge_stage": "first_instance",
    "event_date": "",
    "evidence_text": "Cùng tội danh, Trịnh Vũ Kiên, Kim Xuân Tuấn và Nguyễn Quang Hưng (cùng 30 tuổi) mỗi người bị tuyên phạt 24 tháng tù.",
    "sentence": "24 tháng tù",
    "sentence_stage": "first_instance",
    "months": 24,
    "scope": "per_charge",
    "sentence_evidence": "Các bị cáo Kiên, Tuấn và Hưng mỗi người 24 tháng tù về tội mua bán trái phép chất ma túy."
  }
]
```

### B3: Nguyễn Hữu Đức: hủy quyết định khởi tố

Baseline raw rows:
```json
[]
```

Ontology mới raw rows:
```json
[
  {
    "person": "Nguyễn Hữu Đức",
    "doc_id": "news-100260917203001265",
    "case_id": "case:524edff39fef2c42889a902b",
    "raw_charge": "vận chuyển trái phép chất ma túy",
    "crime": "vận chuyển trái phép chất ma túy",
    "status": "withdrawn",
    "charge_stage": "unknown",
    "event_date": "",
    "evidence_text": "Do không đủ căn cứ chứng minh Đức đồng phạm với Huy về hành vi vận chuyển trái phép chất ma túy, ngày 13-4-2026, Viện Kiểm sát nhân dân TP Hà Nội đã hủy quyết định khởi tố bị can đối với Đức.",
    "sentence": null,
    "sentence_stage": null,
    "months": null,
    "scope": null,
    "sentence_evidence": null
  }
]
```

### B4: Án tù 24–36 tháng

Baseline raw rows:
```json
[
  {
    "person": "Cao Thị Bích Hằng",
    "doc_id": "news-100260930085028036",
    "sentence": "không rõ"
  },
  {
    "person": "Dương Minh Tuấn",
    "doc_id": "news-100260924095400982",
    "sentence": "chuỗi rỗng"
  },
  {
    "person": "Kim Xuân Tuấn",
    "doc_id": "news-100260918080821054",
    "sentence": "24 tháng tù"
  },
  {
    "person": "Lê Minh Thành",
    "doc_id": "news-100260918080821054",
    "sentence": "36 tháng tù"
  },
  {
    "person": "Lê Văn Đông",
    "doc_id": "news-100260930085028036",
    "sentence": "không rõ"
  },
  {
    "person": "Nguyễn Quang Hưng",
    "doc_id": "news-100260918080821054",
    "sentence": "24 tháng tù"
  },
  {
    "person": "Nguyễn Thị Mai Anh",
    "doc_id": "news-100260930085028036",
    "sentence": "không rõ"
  },
  {
    "person": "Ngô Việt Dũng",
    "doc_id": "news-100260930085028036",
    "sentence": "không rõ"
  },
  {
    "person": "Phan Kim Nhi",
    "doc_id": "news-100260924095400982",
    "sentence": "chuỗi rỗng"
  },
  {
    "person": "Trần Minh Tâm",
    "doc_id": "news-100260928173914514",
    "sentence": "tử hình"
  },
  {
    "person": "Trần Ngọc Thảo",
    "doc_id": "news-100260928173914514",
    "sentence": "2 năm 6 tháng tù"
  },
  {
    "person": "Trần Quốc An",
    "doc_id": "news-100260930085028036",
    "sentence": "không rõ"
  },
  {
    "person": "Trần Thanh Tuấn",
    "doc_id": "news-100260928173914514",
    "sentence": "tử hình"
  },
  {
    "person": "Trịnh Vũ Kiên",
    "doc_id": "news-100260918080821054",
    "sentence": "24 tháng tù"
  },
  {
    "person": "Võ Nữ Minh Thư",
    "doc_id": "news-100260928173914514",
    "sentence": "8 năm tù"
  },
  {
    "person": "Đinh Đức Tuấn",
    "doc_id": "news-100260928173914514",
    "sentence": "2 năm 6 tháng tù"
  },
  {
    "person": "Đỗ Thị Ngọc Yến",
    "doc_id": "news-100260928173914514",
    "sentence": "8 năm 6 tháng tù"
  }
]
```

Ontology mới raw rows:
```json
[
  {
    "person": "Lê Minh Thành",
    "doc_id": "news-100260918080821054",
    "sentence": "36 tháng tù",
    "months": 36,
    "stage": "first_instance",
    "scope": "per_charge"
  },
  {
    "person": "Trịnh Vũ Kiên",
    "doc_id": "news-100260918080821054",
    "sentence": "24 tháng tù",
    "months": 24,
    "stage": "first_instance",
    "scope": "per_charge"
  },
  {
    "person": "Kim Xuân Tuấn",
    "doc_id": "news-100260918080821054",
    "sentence": "24 tháng tù",
    "months": 24,
    "stage": "first_instance",
    "scope": "per_charge"
  },
  {
    "person": "Nguyễn Quang Hưng",
    "doc_id": "news-100260918080821054",
    "sentence": "24 tháng tù",
    "months": 24,
    "stage": "first_instance",
    "scope": "per_charge"
  },
  {
    "person": "Đinh Đức Tuấn",
    "doc_id": "news-100260928173914514",
    "sentence": "2 năm 6 tháng tù",
    "months": 30,
    "stage": "first_instance",
    "scope": "per_charge"
  },
  {
    "person": "Trần Ngọc Thảo",
    "doc_id": "news-100260928173914514",
    "sentence": "2 năm 6 tháng tù",
    "months": 30,
    "stage": "first_instance",
    "scope": "per_charge"
  }
]
```

Baseline sau chuẩn hóa chuỗi bằng Python (để không coi thiếu numeric property là không thể trả lời):
```json
[
  {
    "person": "Kim Xuân Tuấn",
    "doc_id": "news-100260918080821054",
    "sentence": "24 tháng tù",
    "months": 24
  },
  {
    "person": "Lê Minh Thành",
    "doc_id": "news-100260918080821054",
    "sentence": "36 tháng tù",
    "months": 36
  },
  {
    "person": "Nguyễn Quang Hưng",
    "doc_id": "news-100260918080821054",
    "sentence": "24 tháng tù",
    "months": 24
  },
  {
    "person": "Trần Ngọc Thảo",
    "doc_id": "news-100260928173914514",
    "sentence": "2 năm 6 tháng tù",
    "months": 30
  },
  {
    "person": "Trịnh Vũ Kiên",
    "doc_id": "news-100260918080821054",
    "sentence": "24 tháng tù",
    "months": 24
  },
  {
    "person": "Đinh Đức Tuấn",
    "doc_id": "news-100260928173914514",
    "sentence": "2 năm 6 tháng tù",
    "months": 30
  }
]
```

## Diễn giải và hạn chế

- B1: Hai Charge độc lập, prosecuted, cùng nguồn. Đối chiếu raw rows và nguồn ở trên; không tự tạo Crime có luật giả định cho tội ngoài KB.
- B2: kiểm tra sentence_stage=first_instance với nguồn nói án sơ thẩm và phiên phúc thẩm bị hoãn. Schema baseline không có stage, nhưng có thể lấy ngữ cảnh từ chunks; không khẳng định baseline QA không thể trả lời.
- B3: kiểm tra withdrawn và bằng chứng hủy quyết định trong raw rows; không xem withdrawn là acquitted. Ngày thiếu/không hợp lệ không tự điền.
- B4: mới lọc trực tiếp duration_months, trả stage/scope. Baseline có thể chuẩn hóa chuỗi ở code ngoài graph; so cả raw và kết quả chuẩn hóa ở trên.
- Các rows thiếu hoặc sai của baseline phản ánh extraction/schema/pipeline trong lần chạy này, không chứng minh mọi ontology gợi ý luôn sai.
- Q5 vẫn do LLM đối chiếu khối lượng với luật; judge=2 không chứng minh cơ quan tố tụng đã áp dụng khoản được suy ra.
- Q6 nhóm theo Case; nhóm liên tài liệu cần ít nhất hai người chung và căn cứ sự kiện/bằng chứng lặp dài/tham chiếu vụ án nguyên văn. Case thiếu căn cứ vẫn giữ riêng; không xem mọi node là vụ ngoài đời duy nhất.
- Corpus luật BLHS ở repo là bản 2015 sửa đổi 2017; benchmark đánh giá theo corpus đã cung cấp, không xác minh luật hiện hành năm 2026.
- Có cơ sở nộp bằng chứng xét bonus, nhưng mức điểm phụ thuộc người chấm. Chưa chạy QA B1–B4 riêng bằng cùng LLM.

## Tái lập

Xem baseline_solution/README.md. collect_bonus_evidence.py capture/restore graph, summarize_bonus.py dựng báo cáo này từ file đo.
Graph mới đã capture: 282 node / 519 cạnh. Restore snapshot không phải lần đo benchmark mới.
