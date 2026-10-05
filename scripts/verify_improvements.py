"""Read-only live acceptance checks; writes evidence, never changes graph or gold."""
import json
import re
from pathlib import Path
from dotenv import load_dotenv
from bench_kg import connect_graph


def main():
    load_dotenv()
    graph = connect_graph()
    try:
        rows = graph.run('''
            MATCH (p:Person)-[:HAS_CHARGE]->(ch:Charge)
            WHERE p.name IN $names
            RETURN p.name AS person, ch.raw_charge AS charge, ch.status AS status,
                   ch.evidence_text AS evidence, ch.doc_id AS doc_id ORDER BY p.name, ch.raw_charge
        ''', names=['Nguyễn Văn Quang', 'Nguyễn Hữu Đức'])
        quang = [r for r in rows if r['person'] == 'Nguyễn Văn Quang']
        assert {r['charge'].casefold() for r in quang} == {'nhận hối lộ', 'đánh bạc'}, rows
        assert all(r['status'] == 'prosecuted' and r['evidence'] for r in quang)
        assert any(r['person'] == 'Nguyễn Hữu Đức' and r['status'] == 'withdrawn' for r in rows), rows
        facts = graph.context('Những vụ việc nào trong tin tức có liên quan đến ma túy MDMA?', [])
        combined = [f for f in facts if 'news-100260924105118645' in f or 'news-100260930085028036' in f]
        assert len(combined) == 1 and all(doc in combined[0] for doc in
               ['news-100260924105118645', 'news-100260930085028036']), combined
        assert any('Lê Minh Thành' in f for f in facts), facts
        assert any('Cái Quang Huy' in f for f in facts), facts
        text = Path('ket_qua_benchmark_kg.txt').read_text(encoding='utf-8')
        nodes, rels = map(int, re.search(r'KG: (\d+) nodes / (\d+) rels', text).groups())
        assert graph.stats() == {'nodes': nodes, 'relationships': rels}
        result = {'stats': graph.stats(), 'B1_B3': rows, 'Q6_facts': facts,
                  'Q6_group_count': len(facts), 'acceptance': 'passed'}
        Path('report/evidence/improvements_verified.json').write_text(
            json.dumps(result, ensure_ascii=False, indent=2), encoding='utf-8')
        print('Live acceptance passed:', result['stats'], 'Q6 groups:', len(facts))
    finally:
        graph.close()


if __name__ == '__main__':
    main()
