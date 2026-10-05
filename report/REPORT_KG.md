# Báo cáo thực nghiệm Day 19 — So sánh Flat RAG và GraphRAG

**Họ tên:** Bùi Tiến Cường  **MSSV:** 2A202602539  **Ngày:** 05-10-2026

Trong bài thực hành này, học viên xây dựng hệ thống GraphRAG trên hai cơ sở tri thức về luật và tin tức, đồng thời so sánh với Flat RAG về chất lượng trả lời, chi phí và thời gian xử lý. Mục tiêu là đánh giá khả năng bổ sung quan hệ có cấu trúc cho truy xuất văn bản, đặc biệt đối với câu hỏi liên kết hai cơ sở tri thức và câu hỏi tổng hợp.

Thực nghiệm sử dụng 18 điều luật và 20 bài báo, được chia thành 176 đoạn văn bản với `chunk_size=800`, `top_k=3`. Mô hình sinh câu trả lời là `openai:gpt-4o-mini`; mô hình embedding là `openai:text-embedding-3-small`. Kết quả chính được tạo bởi lệnh `bench_kg.py --judge` và lưu trong [ket_qua_benchmark_kg.txt](../ket_qua_benchmark_kg.txt). Ontology tự thiết kế được trình bày tại [ONTOLOGY.md](ONTOLOGY.md).

Đồ thị của lượt thực nghiệm cuối gồm 282 node và 519 cạnh. Lượt thực nghiệm trước gồm 278 node và 507 cạnh, được sử dụng để chụp ảnh minh chứng và lưu tại [custom_before_final_check.txt](evidence/custom_before_final_check.txt). Báo cáo sử dụng số liệu lượt cuối cho các bảng định lượng; số liệu trên ảnh được xác định riêng theo thời điểm ghi nhận.

## 1. Phân tích chi phí thực nghiệm

Chi phí được phân thành hai giai đoạn: xây dựng chỉ mục một lần (Indexing) và xử lý truy vấn trung bình trên mỗi câu hỏi (Querying). Hai bảng sau giữ nguyên số liệu từ file kết quả chính:

```text
== Indexing (one-off)
pipeline  calls    in_tok  out_tok       USD  seconds
flat        176     56072        0   0.00112     40.0
graph       198    107994    10476   0.01520    147.0

== Querying (mean per question)
pipeline  recall  judge   in_tok  out_tok       USD  seconds
flat        0.43   1.00      694       47   0.00013     1.31
graph       1.00   2.00     2413      111   0.00042     2.67
```

| Chỉ số | Flat | Graph | Graph / Flat |
| --- | --- | --- | --- |
| Indexing USD | 0.00112 | 0.01520 | 13.57× |
| Indexing giây | 40.0 | 147.0 | 3.68× |
| Mỗi câu: USD | 0.00013 | 0.00042 | 3.23× |
| Mỗi câu: giây | 1.31 | 2.67 | 2.04× |
| Mỗi câu: in_tok | 694 | 2413 | 3.48× |

Các tỉ lệ Graph/Flat được tính từ số liệu đã làm tròn trong file benchmark. Chi phí USD được ước tính theo bảng giá trong `src/llm.py`, không phải chi phí đối soát trên hóa đơn và không bao gồm các lượt gọi LLM phục vụ chấm điểm judge.

So với Flat RAG, GraphRAG vẫn tạo embedding cho cùng 176 đoạn văn bản nhưng bổ sung trích xuất dữ liệu có cấu trúc, kiểm tra tính hợp lệ, trích xuất lại khi cần và ghi dữ liệu vào Neo4j. Giai đoạn xây dựng chỉ mục tăng 22 lượt gọi, 51.922 input token và 10.476 output token. Trong giai đoạn truy vấn, các đoạn văn bản truy xuất được giữ nguyên và bổ sung dữ kiện từ đồ thị; input token trung bình tăng từ 694 lên 2413. Truy xuất đồ thị và ngữ cảnh dài hơn có thể góp phần làm tăng thời gian xử lý, tuy nhiên thực nghiệm chưa đo riêng thời gian của từng thành phần.

Với N câu hỏi và tập dữ liệu không thay đổi, tổng chi phí API ước tính của Flat RAG là `0.00112 + N × 0.00013` USD; của GraphRAG là `0.01520 + N × 0.00042` USD. Chênh lệch `0.01408 + N × 0.00029` luôn dương với N không âm. Do đó, cấu hình GraphRAG được khảo sát không có điểm hòa vốn so với Flat RAG nếu chỉ xét chi phí API. Việc tăng số truy vấn giúp phân bổ chi phí xây dựng chỉ mục, nhưng lựa chọn GraphRAG vẫn cần được cân nhắc trên cơ sở lợi ích chất lượng và nhu cầu kiểm chứng.

## 2. Đánh giá kết quả theo câu hỏi Q1–Q6

| Câu | Loại | Flat recall / judge | Graph recall / judge | Phương án ưu thế | Giải thích |
| --- | --- | --- | --- | --- | --- |
| Q1 | single-hop-law | 1.00 / 2 | 1.00 / 2 | Hòa chất lượng | Định nghĩa tiền chất nằm trong văn bản truy xuất; Graph thêm nguồn Điều 2 khoản 4 nhưng không tăng điểm. |
| Q2 | single-hop-news | 1.00 / 2 | 1.00 / 2 | Hòa chất lượng | Cả hai nêu đúng Trần Thanh Tuấn và Trần Minh Tâm lãnh án tử hình, không cần nối sang luật. |
| Q3 | cross-kb | 0.00 / 0 | 1.00 / 2 | Graph | Flat trả “Không đủ thông tin.”; Graph nối Thành, án 36 tháng, tội mua bán, Điều 251 khoản 1 và khung 02–07 năm. |
| Q4 | cross-kb | 0.00 / 0 | 1.00 / 2 | Graph | Graph nối hành vi Hoàng Nato với Điều 255 khoản 4, tối đa 20 năm/chung thân; Flat không đủ thông tin. |
| Q5 | cross-kb-multi-hop | 0.60 / 1 | 1.00 / 2 | Graph | Flat ghi “khoản b)” mơ hồ và thiếu số Điều; Graph nêu Điều 250 khoản 4, MDMA hơn 9,6kg và khung hình phạt. |
| Q6 | aggregation | 0.00 / 1 | 1.00 / 2 | Graph | Flat dùng tên Đức/Thành/Đông; Graph nêu đủ Huy, Viện Pháp y tâm thần và Thành, nhóm hai bài cùng vụ và giữ nguồn. |

GraphRAG đạt recall trung bình 1.00 và judge 2.00/2, trong khi Flat RAG đạt lần lượt 0.43 và 1.00/2. Mức cải thiện tập trung ở Q3–Q6, là các câu yêu cầu liên kết tin tức với luật hoặc tổng hợp dữ liệu. Đối với Q1–Q2, hai phương án có cùng chất lượng theo bộ đo; Flat RAG có thời gian xử lý từng câu thấp hơn.

Recall trong bài tập là mức bao phủ từ khóa bắt buộc, không phải recall truy xuất tài liệu. Judge là điểm do LLM đánh giá trên thang 0–2. Hai chỉ số này cần được đối chiếu với câu trả lời và nguồn, không được xem là chứng nhận tính đúng đắn toàn diện. Riêng Q5, việc xác định ngưỡng vẫn dựa trên LLM đọc văn bản luật; ontology chưa triển khai bộ suy luận số học xác định.

## 3. Phân tích lỗi

Học viên phân tích ba nhóm lỗi E2, E6 và E4 theo hướng dẫn tại LAB_GUIDE, Bước 8.4. Mỗi nhóm được trình bày theo bốn thành phần: hiện tượng, bằng chứng, nguyên nhân và đề xuất sửa. Các lỗi E2/E6 được ghi nhận ở pipeline sử dụng ontology gợi ý và đối chiếu với phiên bản cải tiến. Kết quả baseline được lưu trong [ket_qua_benchmark_kg.hint.txt](../ket_qua_benchmark_kg.hint.txt); không được đồng nhất với kết quả của phiên bản cuối.

### Lỗi E2: thiếu ngữ cảnh luật khi hỏi mức tối đa

- **Hiện tượng:** Q4 Graph baseline trả tối đa 7 năm, thay vì 20 năm/chung thân.
- **Bằng chứng:** nguyên văn Q4 graph trong `.hint.txt`, recall 0.67, judge 1:

```text
Giang hồ 'Hoàng Nato' bị bắt về hành vi tổ chức sử dụng trái phép chất ma túy. Hành vi này có thể bị phạt tù tối đa 7 năm theo Điều 255 khoản 1 của Bộ luật Hình sự.
```

Q4 graph trong file chính, recall 1.00, judge 2:

```text
Giang hồ 'Hoàng Nato' bị bắt về hành vi "tổ chức sử dụng trái phép chất ma túy". Hành vi này có thể bị phạt tù tối đa lên đến 20 năm hoặc tù chung thân theo Điều 255 Bộ luật Hình sự (BLHS) (khoản 4) [blhs-dieu-255].
```

- **Nguyên nhân:** Cơ chế lựa chọn ngữ cảnh tại KG-3 của baseline chưa bảo đảm cung cấp khung hình phạt cao nhất cho câu hỏi về mức tối đa. Câu trả lời sử dụng khoản 1 thay vì khoản 4 cho thấy sự không phù hợp giữa yêu cầu truy vấn và phần luật được sử dụng. Tuy nhiên, câu trả lời không đủ để xác định duy nhất nguyên nhân; cần phân biệt thiếu ngữ cảnh với việc LLM diễn giải sai ngữ cảnh.
- **Đề xuất sửa:** Phân biệt truy vấn về khung cơ bản và mức tối đa trong `src/kg_context.py`. Với truy vấn về mức tối đa, cung cấp phần mở đầu khung phạt của các khoản liên quan. Phiên bản cải tiến đạt recall 1.00 và judge 2 tại Q4. Việc mở rộng ngữ cảnh làm tăng token; giới hạn ngữ cảnh và lựa chọn trích đoạn giúp giảm chi phí nhưng vẫn có nguy cơ bỏ sót điều kiện ở các câu hỏi chưa khảo sát.

### Lỗi E6: tội danh rỗng dù nguồn nêu hai tội

- **Hiện tượng:** Baseline lưu Nguyễn Văn Quang với charge rỗng, bỏ nhận hối lộ và đánh bạc. Tội ngoài danh mục luật ma túy không có nghĩa là nguồn không nêu tội.
- **Bằng chứng:** truy vấn trên graph baseline, raw rows lưu ở [baseline_bonus.json](evidence/baseline_bonus.json), B1:

```cypher
MATCH (p:Person)-[r:INVOLVED_IN]->(k:Case)
WHERE p.name = 'Nguyễn Văn Quang'
RETURN p.name AS person, k.doc_id AS doc_id,
       r.charge AS raw_charge, r.sentence AS sentence, r.role AS role;
```

```text
person: Nguyễn Văn Quang
doc_id: news-100260924105118645
raw_charge: ""
sentence: ""
role: bị cáo
```

Nguồn `data/drug_news/news-100260924105118645.md`:

```text
Điều dưỡng Nguyễn Văn Quang bị truy tố cả tội nhận hối lộ và đánh bạc, do nhiều lần cá độ bóng đá quốc tế với số tiền giao dịch lên tới 10 triệu đồng mỗi trận.
```

Truy vấn bản mới; raw rows ở [custom_bonus.json](evidence/custom_bonus.json), B1:

```cypher
MATCH (p:Person)-[:HAS_CHARGE]->(ch:Charge)
WHERE p.name = 'Nguyễn Văn Quang'
RETURN p.name, ch.raw_charge, ch.status, ch.doc_id, ch.evidence_text
ORDER BY ch.raw_charge;
```

```text
Nguyễn Văn Quang | đánh bạc    | prosecuted | news-100260924105118645
Nguyễn Văn Quang | nhận hối lộ | prosecuted | news-100260924105118645
```

Cả hai có evidence_text là câu nguồn trên, không có liên kết Crime vì ngoài KB (`crime=null`, `link_method=unlinked`). Không ép gán điều luật ma túy.

- **Nguyên nhân:** Schema và prompt trích xuất của baseline biểu diễn tội danh bằng một chuỗi trên quan hệ người–vụ, gắn với danh mục tội trong cơ sở luật. Trong lượt thực nghiệm này, các tội ngoài danh mục không được giữ lại. Phiên bản tự thiết kế trước cải tiến cũng từng gộp hai tội trong một Charge, cho thấy việc bổ sung loại node chưa đủ nếu không điều chỉnh yêu cầu trích xuất và kiểm tra dữ liệu.
- **Đề xuất sửa:** Trong `src/kg_extraction.py`, yêu cầu mỗi Charge biểu diễn một tội, bảo toàn raw_charge ngoài danh mục và kiểm tra danh sách tội được nêu rõ trong nguồn. Trong `src/graph.py`, lưu từng Charge cùng trạng thái và bằng chứng. Truy vấn B1 của phiên bản cuối xác nhận hai ghi nhận riêng biệt. Phương án này tăng số node và có thể tăng chi phí trích xuất lại; kiểm tra tính nguyên văn của bằng chứng chưa bảo đảm tính đầy đủ hoặc tính đúng về ngữ nghĩa.

### Lỗi E4: recall thấp không đồng nghĩa hoàn toàn sai

- **Hiện tượng:** Q6 Flat có recall 0.00 nhưng judge 1: có dữ kiện MDMA đúng một phần nhưng không đủ định danh vụ.
- **Bằng chứng:** trích nguyên văn Q6 Flat từ file chính:

```text
1. Vụ việc của Đức liên quan đến số viên nén hình tam giác màu hồng - xám được xác định là MDMA.
2. Vụ việc của Thành liên quan đến 5 viên nén màu trắng được xác định là ma túy MDMA.
3. Vụ việc của Đông liên quan đến 0,686g ma túy MDMA được thu giữ trong buồng chữa bệnh.
```

`data/benchmark_kg.json` yêu cầu `Cái Quang Huy`, `Lê Minh Thành`, `Pháp y tâm thần`. Không có nguyên các chuỗi này nên recall bằng 0; judge ghi nhận đúng một phần. Đây là khác biệt tiêu chí, không chứng minh Flat đúng đủ.

- **Nguyên nhân:** Phép đo từ khóa không ghi nhận cách gọi rút gọn hoặc mô tả khác với chuỗi bắt buộc. Đồng thời, câu trả lời Flat RAG thực sự thiếu Cái Quang Huy và không xác định rõ vụ Viện Pháp y tâm thần. Vì vậy, chênh lệch giữa recall và judge phản ánh khác biệt tiêu chí, chưa đủ để kết luận bộ chấm sai hoặc câu trả lời đúng hoàn toàn.
- **Đề xuất sửa:** Giữ nguyên benchmark và đáp án chuẩn của bài thực hành. Trong đánh giá mở rộng, có thể bổ sung đối chiếu thực thể, tên thay thế và nguồn chứng minh, kết hợp đọc câu trả lời với cả recall và judge. Phương án này tăng chi phí kiểm chứng; tập tên thay thế quá rộng có thể làm tăng số trường hợp chấp nhận nhầm.

## 4. Kết luận

Trong phạm vi bộ câu hỏi khảo sát, GraphRAG phù hợp với các yêu cầu liên kết tin tức–luật, phân biệt người, tội danh, mức án và giai đoạn tố tụng, cũng như tổng hợp dữ liệu từ nhiều bài báo. Phương án này có ưu thế tại Q3–Q6, nâng recall trung bình từ 0.43 lên 1.00 và judge từ 1.00 lên 2.00/2. Tuy nhiên, chi phí xây dựng chỉ mục cao gấp 13.57 lần, chi phí truy vấn cao gấp 3.23 lần và thời gian truy vấn trung bình cao gấp 2.04 lần so với Flat RAG.

Flat RAG là lựa chọn phù hợp hơn cho các câu hỏi định nghĩa hoặc thông tin tập trung trong một tài liệu: Q1–Q2 đều đạt recall 1.00 và judge 2 ở cả hai phương án. Nếu nhu cầu chủ yếu là truy vấn một bước hoặc tập dữ liệu thường xuyên thay đổi, lợi ích chất lượng quan sát được chưa đủ để khẳng định việc dựng lại KG là hiệu quả kinh tế. GraphRAG nên được lựa chọn khi nhu cầu trả lời quan hệ và truy vết bằng chứng có giá trị lớn hơn chi phí tăng thêm. Kết luận này cần được kiểm chứng trên tập câu hỏi lớn hơn trước khi áp dụng thực tế.

So với pipeline sử dụng ontology gợi ý, phiên bản cải tiến nâng recall từ 0.83 lên 1.00 và judge từ 1.67 lên 2.00; Q3/Q4 được cải thiện, B1/B3 có biểu diễn dữ liệu đầy đủ hơn theo bằng chứng đã lưu. Chi phí xây dựng chỉ mục tăng từ 0.00942 lên 0.01520 USD (1.61 lần), trong khi chi phí truy vấn giảm từ 0.00093 xuống 0.00042 USD/câu (54.8%). Theo số liệu đã làm tròn, phần chi phí xây dựng tăng thêm được bù sau khoảng 12 câu khi so với Graph baseline, không phải so với Flat RAG. Ước tính chưa xét cập nhật dữ liệu hoặc biến động API. Do đồng thời thay đổi extraction, retrieval và prompt, thực nghiệm không cô lập tác động riêng của ontology. Bằng chứng bổ sung được trình bày trong [BONUS_REVIEW.md](BONUS_REVIEW.md).

## 5. Kiểm chứng triển khai và minh chứng Neo4j

Các kiểm tra sau được thực hiện trên phiên bản mã nguồn cuối ngày 05-10-2026. Output được giữ nguyên nhằm hỗ trợ tái lập kết quả:

```text
$ .\.venv\Scripts\python.exe -X utf8 -B -m pytest tests/ -q
............................................................             [100%]
60 passed in 0.14s

$ .\.venv\Scripts\python.exe -X utf8 -B bench_kg.py --check
[OK] Dữ liệu: 18 điều luật, 20 bài báo
[OK] KG-1 link_entity
[OK] Neo4j kết nối được
[provider] chat = openai:gpt-4o-mini | embedding = openai:text-embedding-3-small
[OK] KG-2 build_graph: 152 node / 306 cạnh, đường xuyên 2 KB dài 2 cạnh
[OK] KG-3 context: 7 dữ kiện, có Điều 251
[OK] KG-4 GraphRAGAgent.answer
[OK] Chi phí check: 2 lần gọi LLM, $0.00183. Graph nhỏ (luật + 1 bài) vẫn còn trong Neo4j để bạn xem; chạy --judge để dựng graph đầy đủ.
```

Tổng cộng 60 test đạt yêu cầu, gồm 48 test gốc và 12 test bổ sung; khi chạy riêng bộ gốc, kết quả là `48 passed in 0.08s`. Lệnh `--check` đạt 7 dòng `[OK]` và chỉ dựng dữ liệu luật cùng một bài báo, nên số 152/306 không được sử dụng làm quy mô đồ thị benchmark. Sau đó, lệnh `--judge` được thực hiện thành công với mã thoát 0; đồ thị đầy đủ được lưu và kiểm tra bằng truy vấn trực tiếp:

```text
Saved ket_qua_benchmark_kg.txt
custom {'nodes': 282, 'relationships': 519} {'B1': 2, 'B2': 1, 'B3': 1, 'B4': 6}
Live acceptance passed: {'nodes': 282, 'relationships': 519} Q6 groups: 3
```

### Ảnh Neo4j

Ba ảnh minh chứng gồm: [kg_count.png](img/kg_count.png) trình bày số lượng node thuộc 9 label; [kg_cross_kb.png](img/kg_cross_kb.png) biểu diễn đường Person → Case → Charge → Crime ← Article cùng Results overview; [kg_my_case.png](img/kg_my_case.png) trình bày vụ việc của Cái Quang Huy, liên kết tới Article, chất và địa điểm, với 10 node và 11 cạnh trong Results overview. Các ảnh ghi nhận lượt thực nghiệm trước gồm 278 node và 507 cạnh. Lượt cuối gồm 282 node và 519 cạnh do biến động trích xuất; hai thời điểm được phân biệt, không thay đổi ảnh để làm khớp số liệu.

Người chọn cho ảnh Q-D: **Cái Quang Huy**, khác Lê Minh Thành và có tội nối được sang luật. Nguyễn Văn Quang dùng cho bằng chứng B1; hai tội ngoài KB không có đường tới Article nên không dùng cho Q-D.

Ảnh do học viên chụp trực tiếp từ Neo4j Browser và giữ nguyên, không cắt hoặc chỉnh sửa. Các truy vấn sử dụng trong ảnh như sau:

Q-A — `kg_count.png`:

```cypher
MATCH (n) RETURN labels(n)[0] AS label, count(*) AS n ORDER BY n DESC;
```

Q-B — `kg_cross_kb.png`:

```cypher
MATCH p=(:Person)-[:INVOLVED_IN]->(:Case)-[:HAS_CHARGE]->(:Charge)-[:OF_CRIME]->(:Crime)<-[:DEFINES]-(:Article)
RETURN p LIMIT 25;
```

Q-D — `kg_my_case.png`:

```cypher
MATCH p=(:Person {name:'Cái Quang Huy'})-[:INVOLVED_IN]->(k:Case)-[:HAS_CHARGE]->(:Charge)-[:OF_CRIME]->(:Crime)<-[:DEFINES]-(:Article)
OPTIONAL MATCH q=(k)-[:INVOLVES|LOCATED_IN]->()
RETURN p, q;
```

## Vấn đề kỹ thuật và giới hạn thực nghiệm

- Lần check đầu trong sandbox gặp `httpcore.ConnectError: [WinError 10013] An attempt was made to access a socket in a way forbidden by its access permissions`, rồi `openai.APIConnectionError: Connection error.` khi gọi API. Đã restore graph, chạy lại với quyền mạng được duyệt đạt 7 `[OK]`, rồi restore graph đầy đủ.
- Truy vấn ảnh cũ gọi `toString(p[k])` trên aliases dạng danh sách gây `Neo.ClientError.Statement.TypeError`: `Invalid input for function 'toString()': Expected a String, Float, Integer, Boolean, Temporal or Duration, got: StringArray[]`. Đổi sang thuộc tính chuỗi `p.name` đã tránh lỗi; không phải lỗi build graph.
- Person/Case vẫn theo tài liệu, có thể lặp giữa bài; Q6 nhóm bằng chứng ở context chứ không MERGE ngoài đời. Ngày sự kiện của Charge Đức còn trống. Fuzzy/LLM có thể sai/thiếu; Q5 chưa suy luận ngưỡng xác định. Sáu câu không chứng minh tổng quát.
- Lượt cuối có cảnh báo validation về chất ngoài danh mục, tên không xuất hiện nguyên văn, ngày thiếu năm trong bằng chứng và khối lượng không nguyên văn; code giữ phần hợp lệ, không cache phần lỗi. B1/B3/Q6 kiểm chứng live vẫn đạt, nhưng không tuyên bố toàn corpus trích xuất hoàn hảo. Node/cạnh thay đổi 278/507 → 282/519 giữa hai lượt cùng code.
- Phạm vi đánh giá gồm sáu câu hỏi; các kết quả chưa có khoảng tin cậy hoặc kiểm định thống kê. Không suy rộng độ chính xác và thời gian của lượt đo sang mọi tập dữ liệu hoặc môi trường triển khai.
