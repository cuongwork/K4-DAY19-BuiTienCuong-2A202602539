"""Solution-specific context assembly tests; live Cypher still needs Neo4j."""
from src.graph import Neo4jGraph


class FakeGraph(Neo4jGraph):
    def __init__(self):
        self.calls = []

    def seed_facts(self, question, doc_ids, **kwargs):
        return ['seed'], ['generic edge']

    def run(self, query, **params):
        self.calls.append((query, params))
        if 'RETURN k.id AS id' in query:
            return [{'id': 'case1', 'props': {'doc_id': 'news1', 'name': 'Vụ thử', 'summary': 'Tóm tắt'}}]
        if 'properties(ch) AS charge' in query:
            return [{'person': 'Thành', 'aliases': [], 'case_id': 'case1', 'crime': 'mua bán',
                     'charge': {'doc_id': 'news1', 'raw_charge': 'mua bán', 'status': 'convicted',
                                'stage': 'first_instance', 'evidence_text': 'Bằng chứng'},
                     'sentence': {'doc_id': 'news1', 'raw_text': '36 tháng tù', 'duration_months': 36,
                                  'stage': 'first_instance', 'scope': 'per_charge', 'evidence_text': 'Nguồn'}}]
        if 'a.doc_id AS doc_id' in query:
            return [{'doc_id': 'law1', 'number': 251, 'title': 'Tội mua bán', 'law': 'BLHS',
                     'article_text': 'Luật', 'clause': 1, 'text': '02 năm đến 07 năm'}]
        return []


def test_context_preserves_sentence_and_legal_grounding():
    facts = FakeGraph().context('Thành theo Điều nào?', ['news1'])
    assert any('36 tháng tù' in f and 'first_instance' in f and 'per_charge' in f for f in facts)
    assert any('Điều 251 BLHS' in f and '02 năm đến 07 năm' in f for f in facts)
    assert any('convicted' in f and 'Bằng chứng' in f for f in facts)


def test_small_budget_includes_both_sources():
    facts = FakeGraph().context('Thành', ['news1'], max_facts=2)
    assert len(facts) == 2
    assert '[news1]' in facts[0]
    assert '[law1]' in facts[1]
    assert FakeGraph().context('Thành', ['news1'], max_facts=0) == []


def test_aggregation_and_maximum_use_question_parameters():
    graph = FakeGraph()
    graph.context('Những vụ việc nào có MDMA, mức tối đa theo Điều 250 BLHS?', [])
    assert any(p.get('aggregate') is True and p.get('substances') == ['MDMA'] for _, p in graph.calls)
    assert any(p.get('maximum') is True and p.get('numbers') == [250] and p.get('law') == 'BLHS'
               for _, p in graph.calls)
