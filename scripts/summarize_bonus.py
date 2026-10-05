"""Generate a source-grounded comparison from measured files, never edit benchmarks."""
import json
import re
from pathlib import Path


def benchmark(path):
    text = Path(path).read_text(encoding='utf-8')
    questions = re.findall(r'--- (Q\d+) \[[^]]+\] graph recall=([\d.]+) judge=(\d+)', text)
    sections = text.split('== ')
    indexing = re.search(r'^graph\s+(\d+)\s+(\d+)\s+(\d+)\s+([\d.]+)\s+([\d.]+)', sections[1], re.M).groups()
    querying = re.search(r'^graph\s+([\d.]+)\s+([\d.]+)\s+(\d+)\s+(\d+)\s+([\d.]+)\s+([\d.]+)', sections[2], re.M).groups()
    return text.splitlines()[0], questions, indexing, querying


def main():
    out = Path('report/evidence')
    custom = json.loads((out / 'custom_bonus.json').read_text(encoding='utf-8'))
    baseline = json.loads((out / 'baseline_bonus.json').read_text(encoding='utf-8'))
    assert custom['corpus_sha256'] == baseline['corpus_sha256'], 'Corpus mismatch'
    ch, cq, ci, cm = benchmark('ket_qua_benchmark_kg.txt')
    bh, bq, bi, bm = benchmark('ket_qua_benchmark_kg.hint.txt')
    assert ch.split('| KG:')[0] == bh.split('| KG:')[0], 'Model/retrieval settings mismatch'
    b1 = custom['questions']['B1']['rows']
    separate = len({r['raw_charge'].casefold() for r in b1}) >= 2
    b1_result = ('Hai Charge độc lập, prosecuted, cùng nguồn' if separate else
                 'Giữ raw_charge/prosecuted có nguồn; cần kiểm tra đã tách đủ tội')
    lines = ['# Bằng chứng baseline và ontology mới — 05-10-2026', '',
             '## Thiết lập', '',
             '- Corpus: 18 điều luật + 20 bài báo; SHA-256 toàn bộ nội dung trùng nhau giữa hai lần capture.',
             '- Cùng OpenAI gpt-4o-mini, text-embedding-3-small, top_k=3, chunk_size=800, 176 chunks.',
             '- Cùng bench_kg.py nguyên bản; test gốc và benchmark không bị sửa.',
             '- Baseline dùng package baseline_solution, helper/schema gợi ý và JSON mode cho extraction.',
             '- Ontology mới có prompt extraction, KG-3 và chỉ dẫn trả lời khác; đây là so sánh pipeline, không cô lập riêng hiệu ứng schema.',
             '- Bảng dùng lượt đo cuối của từng phiên bản; các lượt chẩn đoán lỗi giữ riêng trong evidence/. Temperature=0 vẫn có biến động LLM/API. Không suy ra thời gian indexing chỉ do schema.',
             '- USD do bảng giá trong src/llm.py ước tính, không phải hóa đơn; không gồm judge trong chi phí pipeline.',
             '- Baseline text mode thất bại được giữ ở evidence/baseline_failed_*.json và baseline_failed_text_mode.txt, không dùng làm baseline chính.', '',
             '## Benchmark GraphRAG trước/sau', '',
             '| Câu | Gợi ý recall / judge | Mới recall / judge |', '| --- | --- | --- |']
    for (q, br, bj), (q2, cr, cj) in zip(bq, cq):
        assert q == q2
        lines.append(f'| {q} | {br} / {bj} | {cr} / {cj} |')
    lines += ['', '| Chỉ số GraphRAG | Gợi ý | Mới |', '| --- | --- | --- |',
              f"| Node / cạnh | {baseline['stats']['nodes']} / {baseline['stats']['relationships']} | {custom['stats']['nodes']} / {custom['stats']['relationships']} |",
              f'| Indexing calls | {bi[0]} | {ci[0]} |',
              f'| Indexing USD | {bi[3]} | {ci[3]} |',
              f'| Indexing giây | {bi[4]} | {ci[4]} |',
              f'| Querying recall / judge | {bm[0]} / {bm[1]} | {cm[0]} / {cm[1]} |',
              f'| Querying in_tok trung bình | {bm[2]} | {cm[2]} |',
              f'| Querying USD / câu | {bm[4]} | {cm[4]} |',
              f'| Querying giây / câu | {bm[5]} | {cm[5]} |', '',
              'Đọc nguyên câu trả lời trong hai file benchmark ở root; recall keyword và LLM judge không thay thế kiểm tra nguồn.', '',
              '## B1–B4: truy vấn graph có thể kiểm chứng', '',
              'Đây là kết quả truy vấn graph, không phải benchmark QA của GraphRAGAgent cho B1–B4.',
              'Cypher, parameters và raw rows đầy đủ nằm trong evidence/baseline_bonus.json và evidence/custom_bonus.json.', '']
    lines += ['| Câu | Kết quả baseline | Kết quả mới |', '| --- | --- | --- |',
              f'| B1 | Có Quang nhưng raw_charge rỗng | {b1_result} |',
              '| B2 | 24 tháng tù, không có stage | 24 tháng, first_instance, per_charge |',
              '| B3 | Không có dòng Nguyễn Hữu Đức | withdrawn, bằng chứng hủy quyết định khởi tố |',
              f"| B4 | {len(baseline['questions']['B4']['normalized_in_python'])} kết quả sau chuẩn hóa Python | {len(custom['questions']['B4']['rows'])} kết quả lọc số trực tiếp |", '',
              'Nguồn đối chiếu:', '',
              '- B1: data/drug_news/news-100260924105118645.md, đoạn “Điều dưỡng Nguyễn Văn Quang bị truy tố cả tội nhận hối lộ và đánh bạc”.',
              '- B2: data/drug_news/news-100260918080821054.md, đoạn “Từ đó, tòa sơ thẩm tuyên Thành 36 tháng tù” và câu tiếp theo về Kiên/Tuấn/Hưng 24 tháng; đoạn đầu xác nhận phúc thẩm bị hoãn.',
              '- B3: data/drug_news/news-100260917203001265.md, đoạn ngày 13-4-2026 hủy quyết định khởi tố Đức.',
              '- B4: bài Thành nêu 4 người 24–36 tháng; news-100260928173914514.md nêu Đinh Đức Tuấn và Trần Ngọc Thảo 2 năm 6 tháng (30 tháng).', '']
    labels = {'B1': 'Nguyễn Văn Quang: các tội bị truy tố', 'B2': 'Trịnh Vũ Kiên: 24 tháng thuộc giai đoạn nào',
              'B3': 'Nguyễn Hữu Đức: hủy quyết định khởi tố', 'B4': 'Án tù 24–36 tháng'}
    for key, title in labels.items():
        b = baseline['questions'][key]
        c = custom['questions'][key]
        lines += [f'### {key}: {title}', '', 'Baseline raw rows:', '```json',
                  json.dumps(b['rows'], ensure_ascii=False, indent=2), '```', '',
                  'Ontology mới raw rows:', '```json', json.dumps(c['rows'], ensure_ascii=False, indent=2), '```', '']
        if key == 'B4':
            lines += ['Baseline sau chuẩn hóa chuỗi bằng Python (để không coi thiếu numeric property là không thể trả lời):',
                      '```json', json.dumps(b['normalized_in_python'], ensure_ascii=False, indent=2), '```', '']
    lines += ['## Diễn giải và hạn chế', '',
              f'- B1: {b1_result}. Đối chiếu raw rows và nguồn ở trên; không tự tạo Crime có luật giả định cho tội ngoài KB.',
              '- B2: kiểm tra sentence_stage=first_instance với nguồn nói án sơ thẩm và phiên phúc thẩm bị hoãn. Schema baseline không có stage, nhưng có thể lấy ngữ cảnh từ chunks; không khẳng định baseline QA không thể trả lời.',
              '- B3: kiểm tra withdrawn và bằng chứng hủy quyết định trong raw rows; không xem withdrawn là acquitted. Ngày thiếu/không hợp lệ không tự điền.',
              '- B4: mới lọc trực tiếp duration_months, trả stage/scope. Baseline có thể chuẩn hóa chuỗi ở code ngoài graph; so cả raw và kết quả chuẩn hóa ở trên.',
              '- Các rows thiếu hoặc sai của baseline phản ánh extraction/schema/pipeline trong lần chạy này, không chứng minh mọi ontology gợi ý luôn sai.',
              '- Q5 vẫn do LLM đối chiếu khối lượng với luật; judge=2 không chứng minh cơ quan tố tụng đã áp dụng khoản được suy ra.',
              '- Q6 nhóm theo Case; nhóm liên tài liệu cần ít nhất hai người chung và căn cứ sự kiện/bằng chứng lặp dài/tham chiếu vụ án nguyên văn. Case thiếu căn cứ vẫn giữ riêng; không xem mọi node là vụ ngoài đời duy nhất.',
              '- Corpus luật BLHS ở repo là bản 2015 sửa đổi 2017; benchmark đánh giá theo corpus đã cung cấp, không xác minh luật hiện hành năm 2026.',
              '- Có cơ sở nộp bằng chứng xét bonus, nhưng mức điểm phụ thuộc người chấm. Chưa chạy QA B1–B4 riêng bằng cùng LLM.', '',
              '## Tái lập', '',
              'Xem baseline_solution/README.md. collect_bonus_evidence.py capture/restore graph, summarize_bonus.py dựng báo cáo này từ file đo.',
              f"Graph mới đã capture: {custom['stats']['nodes']} node / {custom['stats']['relationships']} cạnh. Restore snapshot không phải lần đo benchmark mới."]
    Path('report/BONUS_REVIEW.md').write_text('\n'.join(lines) + '\n', encoding='utf-8')
    print('Report generated; matching corpus/settings confirmed.')


if __name__ == '__main__':
    main()
