"""Runnable LAB_GUIDE suggested ontology, not a copy of the custom solution.

KG-1 and KG-4 share the same contract. KG-2 uses starter extraction/writes.
KG-3 follows the guide: case bridge, clause 1 and substance-related clauses.
An aggregation branch is included so Q6 is not artificially top-k limited.
"""
import json
import re
from pathlib import Path

from src.graph import (Neo4jGraph as CustomGraph, GraphRAGAgent as CustomAgent,
                       load_markdown_docs, link_entity, parse_law_article,
                       extract_news_cases, find_substances)


class Neo4jGraph(CustomGraph):
    def context(self, question, doc_ids, max_facts=60):
        if max_facts <= 0:
            return []
        ids, edges = self.seed_facts(question, doc_ids, limit=max_facts)
        cases = self.run("""
            MATCH (k:Case)
            WHERE elementId(k) IN $ids
               OR EXISTS { MATCH (s)--(k) WHERE elementId(s) IN $ids }
            RETURN elementId(k) AS id, k.name AS name, k.summary AS summary, k.doc_id AS doc_id
            ORDER BY k.name
        """, ids=ids)
        case_ids = [r['id'] for r in cases]
        facts = [f"[{r['doc_id']}] Vụ {r['name']}: {r['summary']}" for r in cases]
        for row in self.run("""
            MATCH (k:Case)-[:CHARGED_WITH]->(:Crime)<-[:DEFINES]-(a:Article)-[:HAS_CLAUSE]->(cl:Clause)
            WHERE elementId(k) IN $cases AND (cl.number = 1 OR EXISTS {
                MATCH (k)-[:INVOLVES]->(:Substance)<-[:MENTIONS]-(cl)
            })
            RETURN DISTINCT a.doc_id AS doc_id, a.title AS title, cl.number AS number, cl.text AS text
            UNION
            MATCH (a:Article)-[:HAS_CLAUSE]->(cl:Clause)
            WHERE (a.id IN $articles OR elementId(a) IN $ids OR elementId(cl) IN $ids)
              AND (cl.number = 1 OR elementId(a) IN $ids OR elementId(cl) IN $ids OR EXISTS {
                MATCH (cl)-[:MENTIONS]->(s:Substance) WHERE s.name IN $substances
              })
            RETURN DISTINCT a.doc_id AS doc_id, a.title AS title, cl.number AS number, cl.text AS text
        """, cases=case_ids, ids=ids,
             articles=[f'blhs-dieu-{n}' for n in re.findall(r'[Đđ]iều\s+(\d+)', question)],
             substances=find_substances(question)):
            facts.append(f"[{row['doc_id']} — {row['title']}] khoản {row['number']}: {row['text']}")
        substances = find_substances(question)
        if substances and re.search(r'những vụ|các vụ|vụ việc nào', question.lower()):
            for r in self.run("""
                MATCH (k:Case)-[r:INVOLVES]->(s:Substance)
                WHERE s.name IN $substances
                RETURN DISTINCT k.name AS name, k.summary AS summary, k.doc_id AS doc_id,
                                s.name AS substance, r.amount AS amount ORDER BY k.name
            """, substances=substances):
                facts.append(f"[{r['doc_id']}] Vụ {r['name']}: {r['summary']}; {r['substance']}: {r['amount']}")
        return list(dict.fromkeys(facts + edges))[:max_facts]


def build_graph(graph, law_docs, news_docs, llm_fn):
    graph.suggested_constraints()
    crimes = []
    for doc in law_docs:
        article = parse_law_article(doc)
        graph.add_law_article(article)
        if article['crime']:
            crimes.append(article['crime'])
    extracted = []
    for doc in news_docs:
        # Starter parser expects raw JSON; use provider JSON mode, as custom KG-2 does.
        cases = extract_news_cases(doc, lambda prompt: llm_fn(prompt, json_mode=True), sorted(set(crimes)))
        extracted.append({'doc_id': doc.id, 'cases': cases})
        for case in cases:
            graph.add_news_case(case, doc)
    output = Path('report/evidence')
    output.mkdir(parents=True, exist_ok=True)
    (output / 'baseline_extraction.json').write_text(
        json.dumps(extracted, ensure_ascii=False, indent=2), encoding='utf-8')


class GraphRAGAgent(CustomAgent):
    def answer(self, question, top_k=3):
        chunks = self.store.search(question, top_k=top_k)
        doc_ids = list(dict.fromkeys(c['metadata']['doc_id'] for c in chunks))
        facts = self.graph.context(question, doc_ids)
        prompt = ('Trả lời câu hỏi chỉ dựa trên ngữ cảnh (đoạn văn bản và dữ kiện từ knowledge graph).\n'
                  'Nêu rõ số Điều luật khi có. Nếu ngữ cảnh không đủ, nói không đủ thông tin.\n\n'
                  'Dữ kiện knowledge graph:\n' + '\n'.join('- ' + f for f in facts) +
                  '\n\nĐoạn văn bản:\n' + '\n\n'.join(
                      f"[{i}] {c['content']}" for i, c in enumerate(chunks, 1)) +
                  '\n\nCâu hỏi: ' + question + '\nTrả lời:')
        return self.llm_fn(prompt)
