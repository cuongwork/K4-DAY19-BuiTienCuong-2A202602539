"""Capture reproducible graph-only B1-B4 queries and a restorable custom graph.

Run from repo root: python -m scripts.collect_bonus_evidence custom|baseline|restore.
No LLM calls. Raw rows and exact Cypher are saved; no inferred scores.
"""
import argparse
import hashlib
import json
from pathlib import Path

from dotenv import load_dotenv
from bench_kg import connect_graph
from src.graph import load_markdown_docs, duration_months

OUT = Path('report/evidence')
NAMES = ['Nguyễn Văn Quang', 'Trịnh Vũ Kiên', 'Nguyễn Hữu Đức']
BASE = """
MATCH (p:Person)-[r:INVOLVED_IN]->(k:Case)
WHERE p.name IN $names
RETURN p.name AS person, k.doc_id AS doc_id, k.name AS case_name,
       r.charge AS raw_charge, r.sentence AS sentence, r.role AS role
ORDER BY person, doc_id
"""
CUSTOM = """
MATCH (p:Person)-[:HAS_CHARGE]->(ch:Charge)<-[:HAS_CHARGE]-(k:Case)
WHERE p.name IN $names
OPTIONAL MATCH (ch)-[:OF_CRIME]->(c:Crime)
OPTIONAL MATCH (ch)-[:HAS_SENTENCE]->(s:Sentence)
RETURN p.name AS person, k.doc_id AS doc_id, k.id AS case_id,
       ch.raw_charge AS raw_charge, c.name AS crime, ch.status AS status,
       ch.stage AS charge_stage, ch.event_date AS event_date, ch.evidence_text AS evidence_text,
       s.raw_text AS sentence, s.stage AS sentence_stage, s.duration_months AS months,
       s.scope AS scope, s.evidence_text AS sentence_evidence
ORDER BY person, doc_id, ch.id, s.id
"""
B4 = """
MATCH (p:Person)-[:HAS_CHARGE]->(:Charge)-[:HAS_SENTENCE]->(s:Sentence)-[:IN_CASE]->(k:Case)
WHERE s.penalty_type = 'imprisonment' AND s.duration_months >= 24 AND s.duration_months <= 36
RETURN DISTINCT p.name AS person, k.doc_id AS doc_id, s.raw_text AS sentence,
                s.duration_months AS months, s.stage AS stage, s.scope AS scope
UNION
MATCH (p:Person)-[:HAS_SENTENCE]->(s:Sentence)-[:IN_CASE]->(k:Case)
WHERE s.penalty_type = 'imprisonment' AND s.duration_months >= 24 AND s.duration_months <= 36
RETURN DISTINCT p.name AS person, k.doc_id AS doc_id, s.raw_text AS sentence,
                s.duration_months AS months, s.stage AS stage, s.scope AS scope
"""
BASE_B4 = """
MATCH (p:Person)-[r:INVOLVED_IN]->(k:Case)
WHERE r.sentence IS NOT NULL AND r.sentence <> ''
RETURN p.name AS person, k.doc_id AS doc_id, r.sentence AS sentence ORDER BY person, doc_id
"""


def save(name, value):
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / name).write_text(json.dumps(value, ensure_ascii=False, indent=2), encoding='utf-8')


def main():
    mode = argparse.ArgumentParser()
    mode.add_argument('mode', choices=['custom', 'baseline', 'restore'])
    args = mode.parse_args()
    load_dotenv()
    graph = connect_graph()
    try:
        if args.mode == 'restore':
            snapshot = json.loads((OUT / 'custom_graph_snapshot.json').read_text(encoding='utf-8'))
            graph.reset()
            allowed = {'Article', 'Clause', 'Crime', 'Case', 'Person', 'Charge', 'Sentence', 'Location', 'Substance'}
            for label in allowed:
                rows = [n for n in snapshot['nodes'] if n['labels'] == [label]]
                if rows:
                    graph.run(f'UNWIND $rows AS row CREATE (n:{label}) SET n = row.props, n.__snapshot_id = row.id', rows=rows)
            for rel in sorted({r['type'] for r in snapshot['relationships']}):
                if not rel.replace('_', '').isalnum():
                    raise ValueError('Invalid snapshot relationship')
                rows = [r for r in snapshot['relationships'] if r['type'] == rel]
                graph.run(f'UNWIND $rows AS row MATCH (a {{__snapshot_id:row.start}}), (b {{__snapshot_id:row.end}}) '
                          f'CREATE (a)-[r:{rel}]->(b) SET r = row.props', rows=rows)
            graph.run('MATCH (n) REMOVE n.__snapshot_id')
            for label in allowed:
                key = 'name' if label == 'Substance' else 'id'
                graph.run(f'CREATE CONSTRAINT IF NOT EXISTS FOR (n:{label}) REQUIRE n.{key} IS UNIQUE')
            print('Restored custom graph:', graph.stats())
            return
        query = CUSTOM if args.mode == 'custom' else BASE
        questions = {}
        for number, person in enumerate(NAMES, 1):
            questions[f'B{number}'] = {'cypher': query, 'params': {'names': [person]},
                                      'rows': graph.run(query, names=[person])}
        query4 = B4 if args.mode == 'custom' else BASE_B4
        questions['B4'] = {'cypher': query4, 'rows': graph.run(query4)}
        if args.mode == 'baseline':
            questions['B4']['normalized_in_python'] = [
                dict(row, months=months) for row in questions['B4']['rows']
                if (months := duration_months(row['sentence'])) is not None and 24 <= months <= 36]
        corpus = load_markdown_docs('data/drug_law') + load_markdown_docs('data/drug_news')
        save(args.mode + '_bonus.json', {
            'stats': graph.stats(), 'questions': questions,
            'corpus_sha256': {d.id: hashlib.sha256(d.content.encode()).hexdigest() for d in corpus},
            'labels': graph.run('MATCH (n) RETURN DISTINCT labels(n) AS labels'),
            'relationships': graph.run('MATCH ()-[r]->() RETURN DISTINCT type(r) AS type')})
        if args.mode == 'custom':
            save('custom_graph_snapshot.json', {
                'nodes': graph.run('MATCH (n) RETURN elementId(n) AS id, labels(n) AS labels, properties(n) AS props'),
                'relationships': graph.run('MATCH (a)-[r]->(b) RETURN elementId(a) AS start, elementId(b) AS end, '
                                           'type(r) AS type, properties(r) AS props')})
        print(args.mode, graph.stats(), {k: len(v['rows']) for k, v in questions.items()})
    finally:
        graph.close()


if __name__ == '__main__':
    main()
