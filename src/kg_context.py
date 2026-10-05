"""Question-scoped graph retrieval; source nodes remain document-specific."""
import re
import unicodedata


def normalized(value):
    return re.sub(r'\s+', ' ', unicodedata.normalize('NFC', str(value or ''))).strip().casefold()


def proof_excerpt(text, focus=()):
    """Verbatim, visibly separated excerpts; full contiguous evidence stays in graph."""
    if len(text) <= 700:
        return text
    parts = re.split(r'(?<=[.!?])\s+', text)
    ranked = sorted(range(len(parts)), key=lambda i: -sum(
        normalized(term) in normalized(parts[i]) for term in focus if term))
    chosen = sorted(ranked[:2])
    return ' […] '.join(parts[i] for i in chosen)


def legal_excerpt(text, substances, maximum=False):
    """Keep original penalty lead and relevant points, never rewrite legal numbers."""
    if maximum:
        return text.split('\n', 1)[0]
    points = re.split(r'\n\s*\n(?=[a-zđ]\))', text)
    if len(points) < 2 or not substances:
        return text
    wanted = [p for p in points[1:] if any(normalized(s) in normalized(p) for s in substances)
              or re.search(r'tổng khối lượng|tổng thể tích|có 0?2 chất', p, re.I)]
    return '\n\n'.join([points[0], *wanted])


def fact_budget(facts, max_facts, max_tokens=5000):
    """Drop whole low-priority facts, not source spans; use exact tokens if available."""
    try:
        import tiktoken
        encoder = tiktoken.get_encoding('o200k_base')
        size = lambda text: len(encoder.encode(text))
    except (ImportError, OSError, ValueError):
        # Conservative fallback for Vietnamese; no runtime network dependency.
        size = lambda text: len(text.encode('utf-8')) // 3 + 1
    output, used = [], 0
    for fact in dict.fromkeys(facts):
        cost = size(fact)
        if len(output) >= max_facts:
            break
        if used + cost <= max_tokens:
            output.append(fact)
            used += cost
    return output


def group_cases(rows):
    """One retrieval item per Case; cross-document grouping requires corroboration.

    Two matching full names plus the same explicit event date and location, or
    two matching full names plus a shared long verbatim source sentence.
    No transitive union: every member must match every other member.
    """
    by_id = {}
    for row in rows:
        item = by_id.setdefault(row['id'], dict(row, substances=[]))
        item['substances'].append((row['substance'], row['involvement']))
    groups = []

    def corroborates(a, b):
        if a['id'] == b['id']:
            return True
        common = {normalized(p) for p in a.get('people', [])} & {normalized(p) for p in b.get('people', [])}
        if len(common) < 2:
            return False
        ap, bp = a['props'], b['props']
        reference = normalized(ap.get('case_reference'))
        same_case_reference = bool(reference and reference == normalized(bp.get('case_reference')))
        date = str(ap.get('date', ''))
        if (not same_case_reference and re.fullmatch(r'\d{4}-\d{2}-\d{2}', date)
                and re.fullmatch(r'\d{4}-\d{2}-\d{2}', str(bp.get('date', '')))
                and date != bp['date']):
            return False
        event = bool(re.fullmatch(r'\d{4}-\d{2}-\d{2}', date) and date == bp.get('date')
                     and normalized(a.get('location')) and normalized(a.get('location')) == normalized(b.get('location')))
        source_a = ' '.join(r.get('evidence_text', '') for _, r in a['substances'])
        source_b = normalized(' '.join(r.get('evidence_text', '') for _, r in b['substances']))
        shared = any(len(normalized(s)) >= 100 and normalized(s) in source_b
                     for s in re.split(r'(?<=[.!?])\s+', source_a))
        return event or shared or same_case_reference

    for item in by_id.values():
        group = next((g for g in groups if all(corroborates(item, other) for other in g)), None)
        if group is None:
            groups.append([item])
        else:
            group.append(item)
    facts = []
    for group in groups:
        sources = sorted({i['props']['doc_id'] for i in group})
        names = list(dict.fromkeys(i['props'].get('name', '') for i in group))
        people = sorted({p for i in group for p in i.get('people', [])})
        substance_facts = list(dict.fromkeys(f"{s}: {r.get('amount') or 'khối lượng chưa rõ'}"
                                            for i in group for s, r in i['substances']))
        proofs = list(dict.fromkeys(proof_excerpt(r.get('evidence_text', ''), [s, r.get('amount')])
                                   for i in group for s, r in i['substances']))
        # Each Case's summary is included only once, not again under every person.
        summaries = list(dict.fromkeys(i['props'].get('summary', '') for i in group))
        facts.append(f"[{', '.join(sources)}] Vụ: {' / '.join(names)}; người: {', '.join(people)}; "
                     f"{' ; '.join(substance_facts)}; {' '.join(summaries)}; bằng chứng: {' '.join(proofs)}")
    return facts


def get_context(graph, question, doc_ids, max_facts):
    if max_facts <= 0:
        return []
    from .graph import find_substances
    lowered = normalized(question)
    substances = find_substances(question)
    aggregation = bool(substances and re.search(r'những vụ|các vụ|vụ việc nào', lowered))
    maximum = bool(re.search(r'tối đa|cao nhất', lowered))
    basic = bool(re.search(r'khung.*cơ bản', lowered))
    law_question = bool(re.search(r'luật|điều|khoản|khung|hình phạt|tối đa|cao nhất|định nghĩa|là gì', lowered))
    # Keep the original seed mechanism, but avoid emitting redundant generic edges.
    ids, _ = graph.seed_facts(question, doc_ids, limit=0)
    cases = graph.run("""
        MATCH (k:Case)
        WHERE elementId(k) IN $ids
           OR EXISTS { MATCH (p:Person)-[:INVOLVED_IN]->(k) WHERE elementId(p) IN $ids }
           OR EXISTS { MATCH (k)-[:HAS_CHARGE]->(ch:Charge) WHERE elementId(ch) IN $ids }
           OR EXISTS { MATCH (s:Sentence)-[:IN_CASE]->(k) WHERE elementId(s) IN $ids }
        RETURN k.id AS id, properties(k) AS props ORDER BY k.id
    """, ids=ids)
    case_ids = [r['id'] for r in cases]
    substance_rows = graph.run("""
        MATCH (k:Case)-[r:INVOLVES]->(s:Substance)
        WHERE ($aggregate AND s.name IN $substances) OR (NOT $aggregate AND k.id IN $cases)
        OPTIONAL MATCH (p:Person)-[:INVOLVED_IN]->(k)
        WITH k, r, s, collect(DISTINCT p.name) AS people
        OPTIONAL MATCH (k)-[:LOCATED_IN]->(l:Location)
        RETURN DISTINCT k.id AS id, properties(k) AS props, s.name AS substance,
                        properties(r) AS involvement, people, l.name AS location
        ORDER BY k.id, s.name
    """, cases=case_ids, aggregate=aggregation, substances=substances)
    if aggregation and not law_question:
        return fact_budget(group_cases(substance_rows), max_facts)
    records = graph.run("""
        MATCH (p:Person)-[:INVOLVED_IN]->(k:Case)
        WHERE k.id IN $cases
        OPTIONAL MATCH (p)-[:HAS_CHARGE]->(ch:Charge)<-[:HAS_CHARGE]-(k)
        OPTIONAL MATCH (ch)-[:OF_CRIME]->(c:Crime)
        OPTIONAL MATCH (ch)-[:HAS_SENTENCE]->(s:Sentence)
        RETURN p.name AS person, p.aliases AS aliases, k.id AS case_id,
               properties(ch) AS charge, c.name AS crime, properties(s) AS sentence
        ORDER BY p.name, ch.id, s.id
    """, cases=case_ids)
    named = [r for r in records if any(normalized(n) in lowered for n in
             [r['person'], *(r.get('aliases') or [])] if n)]
    if named:
        records = named
        case_ids = list(dict.fromkeys(r['case_id'] for r in named))
    facts = []
    for row in records:
        ch, sentence = row.get('charge') or {}, row.get('sentence') or {}
        if ch:
            facts.append(f"[{ch.get('doc_id')}] {row['person']}: tội {ch.get('raw_charge')}; "
                         f"status={ch.get('status')}; stage={ch.get('stage')}; "
                         f"trích nguồn: {proof_excerpt(ch.get('evidence_text', ''), [row['person'], ch.get('raw_charge')])}")
        if sentence:
            facts.append(graph._sentence_fact(row['person'], row['case_id'], sentence))
    for row in graph.run("""
        MATCH (p:Person)-[:HAS_SENTENCE]->(s:Sentence)-[:IN_CASE]->(k:Case)
        WHERE k.id IN $cases AND (size($people) = 0 OR p.name IN $people)
        RETURN p.name AS person, k.id AS case_id, properties(s) AS sentence
        ORDER BY p.name, s.id
    """, cases=case_ids, people=[r['person'] for r in named]):
        facts.append(graph._sentence_fact(row['person'], row['case_id'], row['sentence']))
    if substances or re.search(r'khối lượng|ma túy|chất', lowered):
        facts += group_cases([r for r in substance_rows if r['id'] in case_ids])
    numbers = [int(n) for n in re.findall(r'[Đđ]iều\s+(\d+)', question)]
    law = 'BLHS' if 'hình sự' in lowered or 'blhs' in lowered else None
    # Preserve legal grounding by default, except explicit news-only requests.
    news_only = not law_question and bool(re.search(r'những bị cáo|ai.*(?:án|tù)|mức án', lowered))
    legal = [] if news_only else graph.run("""
        MATCH (a:Article)
        WHERE (a.article_number IN $numbers AND ($law IS NULL OR a.law = $law))
           OR (size($cases) = 0 AND (elementId(a) IN $ids OR EXISTS {
               MATCH (a)-[:HAS_CLAUSE]->(cl:Clause) WHERE elementId(cl) IN $ids }))
           OR EXISTS {
               MATCH (k:Case)-[:HAS_CHARGE]->(ch:Charge)-[:OF_CRIME]->(:Crime)<-[:DEFINES]-(a)
               WHERE k.id IN $cases AND (size($people) = 0 OR EXISTS {
                   MATCH (p:Person)-[:HAS_CHARGE]->(ch) WHERE p.name IN $people })
           }
        OPTIONAL MATCH (a)-[:HAS_CLAUSE]->(cl:Clause)
        WHERE ($basic AND cl.number = 1) OR (NOT $basic AND (
            $maximum OR cl.number = 1 OR (size($cases) = 0 AND (elementId(a) IN $ids OR elementId(cl) IN $ids))
            OR EXISTS { MATCH (cl)-[:MENTIONS]->(s:Substance) WHERE s.name IN $substances }
            OR EXISTS { MATCH (cl)-[:MENTIONS]->(:Substance)<-[:INVOLVES]-(k:Case) WHERE k.id IN $cases }
        ))
        RETURN a.doc_id AS doc_id, a.article_number AS number, a.title AS title,
               a.law AS law, a.text AS article_text, cl.number AS clause, cl.text AS text
        ORDER BY a.law, a.article_number, cl.number
    """, ids=ids, cases=case_ids, numbers=numbers, law=law, maximum=maximum, basic=basic,
         people=[r['person'] for r in named], substances=substances)
    # Rank definitions by words in the question, rather than whichever clause appears first.
    if not case_ids:
        words = set(re.findall(r'\w+', lowered)) - {'theo', 'luật', 'là', 'gì', 'năm', 'của'}
        legal.sort(key=lambda r: -len(words & set(re.findall(r'\w+', normalized(r.get('text'))))))
    legal_facts = [f"[{r['doc_id']}] Điều {r['number']} {r['law']} — {r['title']}; khoản {r['clause']}: "
                   f"{legal_excerpt(r['text'], substances or list({x['substance'] for x in substance_rows}), maximum)}"
                   if r['clause'] is not None else
                   f"[{r['doc_id']}] Điều {r['number']} {r['law']}: {r['article_text']}" for r in legal]
    ordered = []
    for i in range(max(len(facts), len(legal_facts))):
        if i < len(facts):
            ordered.append(facts[i])
        if i < len(legal_facts):
            ordered.append(legal_facts[i])
    summaries = [f"[{r['props'].get('doc_id')}] Vụ: {r['props'].get('name')}; {r['props'].get('summary')}"
                 for r in cases if r['id'] in case_ids]
    return fact_budget(ordered + summaries, max_facts)
