"""Compare measured custom pipelines before/after; does not modify benchmark files."""
import json
from pathlib import Path
from scripts.summarize_bonus import benchmark


def main():
    before_path = 'report/evidence/custom_before_improvements.txt'
    after_path = 'ket_qua_benchmark_kg.txt'
    bh, bq, bi, bm = benchmark(before_path)
    ah, aq, ai, am = benchmark(after_path)
    assert bh.split('| KG:')[0] == ah.split('| KG:')[0]
    old = json.loads(Path('report/evidence/custom_bonus_before_improvements.json').read_text(encoding='utf-8'))
    new = json.loads(Path('report/evidence/custom_bonus.json').read_text(encoding='utf-8'))
    assert old['corpus_sha256'] == new['corpus_sha256']
    percent = lambda b, a: (1 - float(a) / float(b)) * 100
    lines = ['# Cải tiến B1, Q6 và graph context — 05-10-2026', '',
             'Cùng corpus, model, top_k=3, chunk_size=800, 176 chunks. Các file benchmark do bench_kg.py nguyên bản sinh ra.',
             'Bảng dùng bản trước cải tiến và lượt cuối của code sau cải tiến; các lượt chẩn đoán giữ riêng trong evidence/. Có biến động extraction/LLM/API. USD là ước tính theo bảng giá code, không phải tổng tiền mọi lượt chạy.', '',
             '| GraphRAG | Trước | Sau |', '| --- | --- | --- |',
             f'| Indexing USD | {bi[3]} | {ai[3]} |',
             f'| Indexing giây | {bi[4]} | {ai[4]} |',
             f'| Input token / câu | {bm[2]} | {am[2]} |',
             f'| Query USD / câu | {bm[4]} | {am[4]} |',
             f'| Query giây / câu | {bm[5]} | {am[5]} |',
             f'| Recall / judge | {bm[0]} / {bm[1]} | {am[0]} / {am[1]} |', '',
             f'Input token giảm {percent(bm[2], am[2]):.1f}%; USD querying giảm {percent(bm[4], am[4]):.1f}%.', '',
             '| Câu | Trước recall / judge | Sau recall / judge |', '| --- | --- | --- |']
    for (q, br, bj), (q2, ar, aj) in zip(bq, aq):
        assert q == q2
        lines.append(f'| {q} | {br} / {bj} | {ar} / {aj} |')
    lines += ['', '## B1', '', 'Trước:', '```json',
              json.dumps(old['questions']['B1']['rows'], ensure_ascii=False, indent=2), '```', '',
              'Sau:', '```json', json.dumps(new['questions']['B1']['rows'], ensure_ascii=False, indent=2), '```', '',
              '## Q6', '',
              'Đọc nguyên câu trả lời Q6 trong ket_qua_benchmark_kg.txt; context trả một mục cho mỗi Case hoặc nhóm có bằng chứng xác nhận.',
              'Không hợp nhất node liên tài liệu, không ghi đè doc_id. Source list được giữ trong mỗi mục.', '',
              '## Cách giảm context', '',
              '- Lọc người được hỏi và tội liên quan trước khi mở rộng luật; câu khung cơ bản lấy khoản 1.',
              '- Câu tối đa lấy phần mở đầu khung phạt các khoản; câu theo chất giữ các điểm liên quan và điểm tổng khối lượng.',
              '- Không thêm lại cạnh seed dạng hash; bỏ lặp summaries/person/case trong câu tổng hợp.',
              '- Giữ đầy đủ evidence_text trong graph, dùng trích đoạn nguyên văn có dấu […] trong prompt.',
              '- Ngân sách phần graph 5.000 token (ước tính byte/3 khi thiếu tiktoken), bỏ nguyên facts thấp ưu tiên; chunks vector không cắt.', '',
              '## Giới hạn', '',
              '- Phát hiện compound charge dựa danh sách tội rõ ràng trong nguồn, không bảo đảm phát hiện mọi cách diễn đạt.',
              '- Nhóm Case liên tài liệu bảo thủ; có thể còn trùng khi thiếu ngày/địa điểm/bằng chứng chung.',
              '- Rút phần đầu khoản chỉ dùng cho câu hỏi mức tối đa; câu hỏi điều kiện áp dụng cần các điểm đầy đủ liên quan.',
              '- Đánh giá bằng keyword recall và LLM judge vẫn cần kiểm tra nguồn; không xác minh luật hiện hành.',
              '- Không sửa base RAG, test gốc, benchmark, câu hỏi/gold/must_include.']
    Path('report/IMPROVEMENT_REVIEW.md').write_text('\n'.join(lines) + '\n', encoding='utf-8')
    print('Before/after comparison written; corpus and model settings match.')


if __name__ == '__main__':
    main()
