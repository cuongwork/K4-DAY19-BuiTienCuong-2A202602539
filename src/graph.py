"""Knowledge Graph (Neo4j) + GraphRAG over two drug-topic knowledge bases.

Contract (fixed — bench_kg.py and the tests rely on it):
    link_entity(name, known)                       -> one of `known` or None          (TODO KG-1)
    build_graph(graph, law_docs, news_docs, llm_fn)   load both KBs into Neo4j      (TODO KG-2)
        every node created from ONE document carries the property `doc_id`
    Neo4jGraph.context(question, doc_ids)         -> list[str] facts               (TODO KG-3)
    GraphRAGAgent.answer(question, top_k)         -> str                           (TODO KG-4)

Everything else in this file is a HINT: one possible ontology (below). Use it as is, change it,
or design your own — your own ontology + report/ONTOLOGY.md earns the bonus (see SUBMISSION.md).

Suggested ontology (Crime is the bridge between the law KB and the news KB):

    (:Article {id, title, law, doc_id})-[:DEFINES]->(:Crime {name})
    (:Article)-[:HAS_CLAUSE]->(:Clause {id, number, penalty, text})-[:MENTIONS]->(:Substance {name})
    (:Case {name, summary, date, doc_id})-[:CHARGED_WITH]->(:Crime)
    (:Case)-[:INVOLVES {amount}]->(:Substance)
    (:Case)-[:LOCATED_IN]->(:Location {name})
    (:Person {name, aliases})-[:INVOLVED_IN {role, sentence, charge}]->(:Case)
"""

from __future__ import annotations

import difflib
import hashlib
import json
import re
import unicodedata
from pathlib import Path
from typing import Any, Callable

from .models import Document
from .store import EmbeddingStore

# Canonical substance names: the ones BLHS Chương XX lists, plus common ones in Vietnamese news.
SUBSTANCES = ["Heroine", "Cocaine", "Methamphetamine", "Amphetamine", "MDMA", "XLR-11", "Ketamine",
              "cần sa", "thuốc phiện", "côca"]
CLAUSE_START = re.compile(r"^(\d+)\.\s", re.MULTILINE)
FOOTNOTE = re.compile(r"\[\d+\]")

def load_markdown_docs(folder: str | Path) -> list[Document]:
    """Read crawler output (.md with a flat `key: "value"` front matter) into Documents."""
    docs = []
    for path in sorted(Path(folder).glob("*.md")):
        raw = path.read_text(encoding="utf-8")
        _, front, body = raw.split("---", 2)
        metadata = {k: json.loads(v) for k, v in re.findall(r'^(\w+): (".*")$', front, re.MULTILINE)}
        docs.append(Document(id=metadata.get("doc_id", path.stem), content=body.strip(), metadata=metadata))
    return docs

def normalize_crime(name: str) -> str:
    """'Tội Mua bán trái phép chất ma túy' -> 'mua bán trái phép chất ma túy'."""
    name = unicodedata.normalize("NFC", name)
    name = re.sub(r"\s+", " ", name.strip().strip("\"'“”").lower())
    return name.removeprefix("tội ").strip()

def link_entity(name: str, known: list[str], normalize: Callable[[str], str] = normalize_crime) -> str | None:
    """Map a free-text mention (e.g. a charge written by a journalist) onto one canonical name in `known`."""
    query = normalize(name)
    if not query:
        return None
    originals = {}
    for item in known:
        originals.setdefault(normalize(item), item)
    if query in originals:
        return originals[query]
    matches = difflib.get_close_matches(query, originals, n=1, cutoff=0.8)
    return originals[matches[0]] if matches else None

def find_substances(text: str) -> list[str]:
    lowered = text.lower()
    return [name for name in SUBSTANCES if name.lower() in lowered]

# ----------------------------------------------------------------------------------------------
# HINT — suggested ontology: extraction helpers
# ----------------------------------------------------------------------------------------------

def parse_law_article(doc: Document) -> dict[str, Any]:
    """Deterministic (regex) extraction for one 'Điều' — law text is regular enough to skip the LLM."""
    article_id = doc.metadata["article"]                       # "Điều 251 BLHS"
    title = doc.metadata["title"].split(". ", 1)[-1]           # "Tội mua bán trái phép chất ma túy"
    body = FOOTNOTE.sub("", doc.content)
    starts = list(CLAUSE_START.finditer(body))
    clauses = []
    for index, start in enumerate(starts):
        end = starts[index + 1].start() if index + 1 < len(starts) else len(body)
        text = body[start.start():end].strip()
        first_line = text.splitlines()[0]
        penalty = re.search(r"\bbị ((?:phạt|tù|cảnh cáo).+?)(?::|$)", first_line)
        clauses.append({
            "id": f"{article_id} khoản {start.group(1)}",
            "number": int(start.group(1)),
            "penalty": penalty.group(1).rstrip(".") if penalty else "",
            "text": text,
            "substances": find_substances(text),
        })
    return {
        "id": article_id,
        "law": doc.metadata.get("law", ""),
        "title": title,
        "doc_id": doc.id,
        "crime": normalize_crime(title) if title.startswith("Tội ") else None,
        "clauses": clauses,
    }

NEWS_EXTRACTION_PROMPT = """Bạn trích xuất knowledge graph từ một bài báo tiếng Việt về ma túy.
Chỉ dùng thông tin có trong bài. Trả về JSON đúng dạng:
{{"cases": [{{
  "name": "tên ngắn của vụ việc, ví dụ: Vụ mua bán 36kg ma túy tại TP.HCM",
  "summary": "1-2 câu tóm tắt",
  "date": "ngày xảy ra/xét xử nếu có, dạng YYYY-MM-DD hoặc chuỗi rỗng",
  "location": "tỉnh/thành phố, chuỗi rỗng nếu không rõ",
  "charges": ["tội danh, BẮT BUỘC chọn đúng nguyên văn từ DANH SÁCH TỘI DANH"],
  "substances": [{{"name": "tên chất, dùng tên chuẩn trong DANH SÁCH CHẤT nếu khớp", "amount": "khối lượng nếu có"}}],
  "people": [{{"name": "họ tên", "aliases": ["biệt danh"], "role": "bị cáo|bị can|nghi phạm|người liên quan|cán bộ",
               "charge": "tội danh của người này (từ DANH SÁCH TỘI DANH) hoặc chuỗi rỗng",
               "sentence": "mức án nếu có, ví dụ: tử hình, 8 năm tù"}}]
}}]}}
Bài không nói về vụ việc cụ thể (tuyên truyền, hội nghị...) thì trả về {{"cases": []}}.

DANH SÁCH TỘI DANH: {crimes}
DANH SÁCH CHẤT: {substances}

Tiêu đề: {title}
Nội dung:
{content}"""

def extract_news_cases(doc: Document, llm_fn: Callable[[str], str], known_crimes: list[str]) -> list[dict]:
    """LLM extraction for one news article; charges are re-linked to law-KB crimes in code."""
    prompt = NEWS_EXTRACTION_PROMPT.format(
        crimes="; ".join(known_crimes), substances=", ".join(SUBSTANCES),
        title=doc.metadata.get("title", ""), content=doc.content[:12000],
    )
    try:
        cases = json.loads(llm_fn(prompt)).get("cases", [])
    except (json.JSONDecodeError, AttributeError):
        return []
    for case in cases:
        case["charges"] = sorted({c for c in (link_entity(x, known_crimes) for x in case.get("charges", [])) if c})
        for person in case.get("people", []):
            person["charge"] = link_entity(person.get("charge") or "", known_crimes) or ""
    return cases

# ----------------------------------------------------------------------------------------------
# Neo4j
# ----------------------------------------------------------------------------------------------

class Neo4jGraph:
    """Thin wrapper over the official neo4j driver."""

    def __init__(self, uri: str, user: str, password: str) -> None:
        from neo4j import GraphDatabase

        self.driver = GraphDatabase.driver(uri, auth=(user, password), notifications_min_severity="OFF")
        self.driver.verify_connectivity()

    def close(self) -> None:
        self.driver.close()

    def run(self, cypher: str, **params: Any) -> list[dict]:
        records, _, _ = self.driver.execute_query(cypher, params)
        return [record.data() for record in records]

    def reset(self) -> None:
        """Delete every node, relationship and constraint (bench_kg.py calls this before build_graph)."""
        self.run("MATCH (n) DETACH DELETE n")
        for row in self.run("SHOW CONSTRAINTS YIELD name RETURN name"):
            self.run(f"DROP CONSTRAINT `{row['name']}` IF EXISTS")

    def stats(self) -> dict[str, int]:
        nodes = self.run("MATCH (n) RETURN count(n) AS n")[0]["n"]
        rels = self.run("MATCH ()-[r]->() RETURN count(r) AS n")[0]["n"]
        return {"nodes": nodes, "relationships": rels}

    def write_batch(self, statements: list[tuple[str, list[dict]]]) -> None:
        """One atomic transaction; the callback contains no LLM or file writes."""
        def write(tx):
            for query, rows in statements:
                tx.run(query, rows=rows).consume()
        with self.driver.session(database="neo4j") as session:
            session.execute_write(write)

    def seed_facts(self, question: str, doc_ids: list[str], skip_labels: tuple[str, ...] = (),
                   limit: int = 60) -> tuple[list[str], list[str]]:
        """Ontology-independent first step: seed nodes + their 1-hop edges as text facts.

        Seeds = nodes whose `doc_id` is in doc_ids, or whose `name`/`aliases` appear in the question.
        Returns (seed elementIds, facts). Nodes with a label in skip_labels are left out of the facts.
        """
        seeds = self.run(
            """
            MATCH (n)
            WHERE n.doc_id IN $doc_ids
               OR (n.name IS :: STRING AND size(n.name) >= 3 AND toLower($q) CONTAINS toLower(n.name))
               OR any(a IN coalesce(n.aliases, []) WHERE size(a) >= 3 AND toLower($q) CONTAINS toLower(a))
            RETURN elementId(n) AS id
            """,
            q=question, doc_ids=doc_ids,
        )
        seed_ids = [row["id"] for row in seeds]
        edges = self.run(
            """
            MATCH (s)-[r]-(m)
            WHERE elementId(s) IN $ids
              AND none(l IN labels(s) + labels(m) WHERE l IN $skip)
            WITH DISTINCT r LIMIT $limit
            WITH startNode(r) AS a, r, endNode(r) AS b
            RETURN labels(a)[0] AS a_label, coalesce(a.name, a.id) AS a_name, type(r) AS rel,
                   properties(r) AS props, labels(b)[0] AS b_label, coalesce(b.name, b.id) AS b_name
            """,
            ids=seed_ids, skip=list(skip_labels), limit=limit,
        )
        facts = []
        for e in edges:
            props = ", ".join(f"{k}: {v}" for k, v in e["props"].items() if v)
            facts.append(f"({e['a_label']}: {e['a_name']}) -[{e['rel']}{' {' + props + '}' if props else ''}]-> "
                         f"({e['b_label']}: {e['b_name']})")
        return seed_ids, facts

    # ---------------------------------------------------------------- HINT — suggested ontology: writes

    def suggested_constraints(self) -> None:
        for label, key in [("Article", "id"), ("Clause", "id"), ("Crime", "name"), ("Case", "name"),
                           ("Substance", "name"), ("Person", "name"), ("Location", "name")]:
            self.run(f"CREATE CONSTRAINT IF NOT EXISTS FOR (n:{label}) REQUIRE n.{key} IS UNIQUE")

    def add_law_article(self, article: dict) -> None:
        self.run(
            """
            MERGE (a:Article {id: $id}) SET a.title = $title, a.law = $law, a.doc_id = $doc_id
            FOREACH (crime IN CASE WHEN $crime IS NULL THEN [] ELSE [$crime] END |
                MERGE (c:Crime {name: crime}) MERGE (a)-[:DEFINES]->(c))
            WITH a
            UNWIND $clauses AS clause
            MERGE (cl:Clause {id: clause.id})
              SET cl.number = clause.number, cl.penalty = clause.penalty, cl.text = clause.text, cl.doc_id = $doc_id
            MERGE (a)-[:HAS_CLAUSE]->(cl)
            FOREACH (s IN clause.substances | MERGE (sub:Substance {name: s}) MERGE (cl)-[:MENTIONS]->(sub))
            """,
            **article,
        )

    def add_news_case(self, case: dict, doc: Document) -> None:
        self.run(
            """
            MERGE (k:Case {name: $name})
              SET k.summary = $summary, k.date = $date, k.doc_id = $doc_id, k.source_title = $title
            FOREACH (loc IN CASE WHEN $location = '' THEN [] ELSE [$location] END |
                MERGE (l:Location {name: loc}) MERGE (k)-[:LOCATED_IN]->(l))
            FOREACH (crime IN $charges | MERGE (c:Crime {name: crime}) MERGE (k)-[:CHARGED_WITH]->(c))
            FOREACH (s IN $substances | MERGE (sub:Substance {name: s.name}) MERGE (k)-[r:INVOLVES]->(sub)
                SET r.amount = s.amount)
            FOREACH (p IN $people | MERGE (person:Person {name: p.name})
                SET person.aliases = coalesce(p.aliases, [])
                MERGE (person)-[r:INVOLVED_IN]->(k) SET r.role = p.role, r.charge = p.charge, r.sentence = p.sentence)
            """,
            name=case.get("name") or doc.metadata.get("title", doc.id),
            summary=case.get("summary", ""), date=case.get("date", ""), location=case.get("location", ""),
            charges=case.get("charges", []), people=[p for p in case.get("people", []) if p.get("name")],
            substances=[s for s in case.get("substances", []) if s.get("name")],
            doc_id=doc.id, title=doc.metadata.get("title", ""),
        )

    # ---------------------------------------------------------------- KG-3

    def context(self, question: str, doc_ids: list[str], max_facts: int = 60) -> list[str]:
        """Graph facts for a question: seeds + 1 hop, then the legal basis of every case reached."""
        # TODO KG-3: multi-hop retrieval over YOUR ontology.
        #   1. self.seed_facts(question, doc_ids) -> (seed_ids, facts)   (ontology-independent, already written)
        #   2. From the seeds, walk to the other KB through your bridge node (Cypher, see LAB_GUIDE Bước 5)
        #   3. Append one readable string per fact; return the list.
        #
        # HINT (suggested ontology):
        #   a. Cases that are a seed or next to one -> add f"Vụ việc '{name}': {summary}" to facts
        #        MATCH (k:Case) WHERE elementId(k) IN $ids OR EXISTS { MATCH (s)--(k) WHERE elementId(s) IN $ids }
        #   b. For those cases follow
        #        (Case)-[:CHARGED_WITH]->(Crime)<-[:DEFINES]-(Article)-[:HAS_CLAUSE]->(Clause)
        #      keep clause 1 + clauses that MENTION a Substance the case INVOLVES
        #   c. Articles named in the question ("Điều 251" -> re.findall(r"[Đđ]iều (\d+)", question)):
        #      clause 1 + clauses mentioning find_substances(question)
        #   d. One fact per clause: f"[{article_id} - {title}] khoản {number}: {text}"
        from .kg_context import get_context
        return get_context(self, question, doc_ids, max_facts)

    @staticmethod
    def _sentence_fact(person: str, case_id: str, sentence: dict) -> str:
        from .kg_context import proof_excerpt
        return (f"[{sentence.get('doc_id')}] {person}, vụ {case_id}: án {sentence.get('raw_text')}; "
                f"stage={sentence.get('stage')}; scope={sentence.get('scope')}; "
                f"duration_months={sentence.get('duration_months', 'không áp dụng')}; "
                f"trích nguồn: {proof_excerpt(sentence.get('evidence_text', ''), [person, sentence.get('raw_text')])}")

# ---------------------------------------------------------------------------------------------- KG-2

def build_graph(graph: Neo4jGraph, law_docs: list[Document], news_docs: list[Document],
                llm_fn: Callable[..., str]) -> None:
    """Load both KBs into an empty graph. llm_fn(prompt, json_mode=False) -> str (metered OpenAI chat)."""
    for label in ("Article", "Clause", "Crime", "Case", "Person", "Charge", "Sentence", "Location"):
        graph.run(f"CREATE CONSTRAINT IF NOT EXISTS FOR (n:{label}) REQUIRE n.id IS UNIQUE")
    graph.run("CREATE CONSTRAINT IF NOT EXISTS FOR (n:Substance) REQUIRE n.name IS UNIQUE")
    crimes = []
    law_batch = GraphBatch(graph)
    for doc in law_docs:
        article = parse_law_article(doc)
        number = re.search(r"\d+", doc.metadata["article"]).group()
        version = str(doc.metadata.get("law") or doc.id.rsplit("-", 1)[0])
        aid = entity_key("article", version, number)
        law_batch.run("MERGE (a:Article {id:$id}) SET a += $props", id=aid, props={
            "title": article["title"], "law": article["law"], "article_number": int(number),
            "document_version_key": version, "text": doc.content, "doc_id": doc.id,
            "source_url": doc.metadata.get("source_url", "")})
        if article["crime"]:
            crime = article["crime"]
            crimes.append(crime)
            law_batch.run("MATCH (a:Article {id:$aid}) MERGE (c:Crime {id:$cid}) "
                      "SET c.name=$name MERGE (a)-[:DEFINES]->(c)",
                      aid=aid, cid=entity_key("crime", crime), name=crime)
        for clause in article["clauses"]:
            law_batch.run("MATCH (a:Article {id:$aid}) MERGE (cl:Clause {id:$id}) "
                      "SET cl += $props MERGE (a)-[:HAS_CLAUSE]->(cl) "
                      "FOREACH (name IN $substances | MERGE (s:Substance {name:name}) "
                      "MERGE (cl)-[:MENTIONS]->(s))", aid=aid,
                      id=entity_key("clause", aid, clause["number"]),
                      props={k: clause[k] for k in ("number", "penalty", "text")} | {"doc_id":doc.id},
                      substances=clause["substances"])
    law_batch.flush()
    for doc in news_docs:
        cases = extract_charge_cases(doc, llm_fn, sorted(set(crimes)))
        news_batch = GraphBatch(graph)
        for index, case in enumerate(cases):
            if len(cases) == 1:
                reference = re.search(r'\d+\s+bị cáo\s+trong\s+vụ án\s+xảy ra tại\s+[^.!?]+', source_text(doc.content))
                if reference:
                    case['case_reference'] = re.split(r'\s+(?:và một số|tiếp tục|bắt đầu)', reference.group())[0]
            write_charge_case(news_batch, doc, case, index)
        news_batch.flush()


class GraphBatch:
    """Group identical trusted statements into UNWIND batches in dependency order."""
    def __init__(self, graph):
        self.graph = graph
        self.groups: dict[str, list[dict]] = {}

    def run(self, query: str, **params):
        self.groups.setdefault(query, []).append(params)

    def flush(self):
        statements = [("UNWIND $rows AS row " + re.sub(r"\$(\w+)", r"row.\1", query), rows)
                      for query, rows in self.groups.items()]
        if statements:
            self.graph.write_batch(statements)
        self.groups.clear()


def entity_key(kind: str, *parts: Any) -> str:
    """Deterministic, unambiguous IDs; names stay available as display properties."""
    value = json.dumps(parts, ensure_ascii=False, separators=(",", ":"))
    return kind + ":" + hashlib.sha256(value.encode("utf-8")).hexdigest()[:24]


def source_text(value: str) -> str:
    return re.sub(r"\s+", " ", unicodedata.normalize("NFC", value)).strip()


def duration_months(text: str) -> int | None:
    """Normalize explicit years/months, without converting life/death to numbers."""
    if re.search(r"chung thân|tử hình", text.lower()):
        return None
    years = re.search(r"(\d+)\s*năm", text)
    months = re.search(r"(\d+)\s*tháng", text)
    if not years and not months:
        return None
    return (int(years.group(1)) * 12 if years else 0) + (int(months.group(1)) if months else 0)


def extract_charge_cases(doc: Document, llm_fn: Callable[..., str], crimes: list[str]) -> list[dict]:
    from .kg_extraction import extract_cases
    return extract_cases(doc, llm_fn, crimes)


def write_charge_case(graph: Neo4jGraph, doc: Document, case: dict, index: int) -> None:
    kid = entity_key("case", doc.id, index)
    provenance = {"doc_id": doc.id, "source_url": doc.metadata.get("source_url", "")}
    graph.run("MERGE (k:Case {id:$id}) SET k += $props", id=kid,
              props=provenance | {"name":case.get("name") or doc.metadata.get("title", doc.id),
                                 "summary":case.get("summary", ""), "date":case.get("date", ""),
                                 "case_reference":case.get("case_reference", "")})
    if case.get("location"):
        graph.run("MATCH (k:Case {id:$kid}) MERGE (l:Location {id:$id}) "
                  "SET l += $props MERGE (k)-[:LOCATED_IN]->(l)", kid=kid,
                  id=entity_key("location", doc.id, source_text(case["location"]).lower()),
                  props=provenance | {"name":case["location"]})
    for substance in case.get("substances", []):
        name = link_entity(str(substance.get("name", "")), SUBSTANCES, lambda s:s.strip().lower())
        evidence = source_text(str(substance.get("evidence_text", "")))
        if name and evidence and evidence in source_text(doc.content):
            graph.run("MATCH (k:Case {id:$kid}) MERGE (s:Substance {name:$name}) "
                      "MERGE (k)-[r:INVOLVES]->(s) SET r += $props", kid=kid, name=name,
                      props={"amount":str(substance.get("amount", "")), "evidence_text":evidence, "doc_id":doc.id})
    for person in case.get("people", []):
        name = source_text(person["name"])
        pid = entity_key("person", doc.id, name.lower())
        graph.run("MATCH (k:Case {id:$kid}) MERGE (p:Person {id:$id}) "
                  "SET p += $props MERGE (p)-[r:INVOLVED_IN]->(k) SET r.role=$role", kid=kid, id=pid,
                  props=provenance | {"name":name, "aliases":[a for a in person.get("aliases", []) if isinstance(a,str)]},
                  role=str(person.get("role", "")))
        for charge in person["charges"]:
            chid = entity_key("charge", kid, pid, charge["crime"] or charge["raw_charge"],
                              charge["status"], charge.get("event_date") or source_text(charge["evidence_text"]))
            stage = charge.get("stage", "unknown")
            if stage not in {"investigation", "prosecution", "first_instance", "appeal", "unknown"}:
                stage = "unknown"
            props = provenance | {k:str(charge.get(k, "")) for k in
                                  ("raw_charge", "status", "event_date", "evidence_text", "link_method")}
            graph.run("MATCH (p:Person {id:$pid}), (k:Case {id:$kid}) "
                      "MERGE (ch:Charge {id:$id}) SET ch += $props "
                      "MERGE (p)-[:HAS_CHARGE]->(ch) MERGE (k)-[:HAS_CHARGE]->(ch)",
                      pid=pid, kid=kid, id=chid, props=props | {"stage":stage})
            if charge["crime"]:
                graph.run("MATCH (ch:Charge {id:$id}), (c:Crime {id:$cid}) "
                          "MERGE (ch)-[:OF_CRIME]->(c)", id=chid, cid=entity_key("crime", charge["crime"]))
            if charge["status"] == "convicted":
                for sentence in charge.get("sentences", []):
                    write_sentence(graph, doc, kid, chid, "Charge", sentence, "per_charge")
        for sentence in person.get("aggregate_sentences", []):
            write_sentence(graph, doc, kid, pid, "Person", sentence, "aggregate")


def write_sentence(graph: Neo4jGraph, doc: Document, kid: str, owner: str,
                   label: str, sentence: dict, scope: str) -> None:
    evidence = source_text(str(sentence.get("evidence_text", "")))
    raw = source_text(str(sentence.get("raw_text", "")))
    if not evidence or evidence not in source_text(doc.content) or not raw or raw not in evidence:
        return
    stage = sentence.get("stage", "unknown")
    if stage not in {"first_instance", "appeal", "unknown"}:
        stage = "unknown"
    months = duration_months(raw)
    penalty = ("death" if "tử hình" in raw.lower() else "life_imprisonment" if "chung thân" in raw.lower()
               else "imprisonment" if "tù" in raw.lower() else "other")
    props = {"scope":scope, "stage":stage, "penalty_type":penalty, "raw_text":raw,
             "event_date":str(sentence.get("event_date", "")), "evidence_text":evidence,
             "doc_id":doc.id, "source_url":doc.metadata.get("source_url", "")}
    if penalty == "imprisonment" and months is not None:
        props["duration_months"] = months
    sid = entity_key("sentence", owner, stage, sentence.get("event_date") or evidence, scope)
    graph.run(f"MATCH (o:{label} {{id:$owner}}), (k:Case {{id:$kid}}) "
              "MERGE (s:Sentence {id:$id}) SET s += $props "
              "MERGE (o)-[:HAS_SENTENCE]->(s) MERGE (s)-[:IN_CASE]->(k)",
              owner=owner, kid=kid, id=sid, props=props)

# ---------------------------------------------------------------------------------------------- KG-4

GRAPH_PROMPT = """Trả lời câu hỏi chỉ dựa trên ngữ cảnh (đoạn văn bản và dữ kiện từ knowledge graph).
Nêu rõ số Điều luật khi có. Nếu ngữ cảnh không đủ, nói không đủ thông tin.
Phân biệt bị bắt, khởi tố, truy tố và kết án; sơ thẩm và phúc thẩm; án riêng và án tổng hợp.
Khung hình phạt theo luật không phải mức án thực tế. Khoản suy ra từ khối lượng không chứng minh
đó là khoản cơ quan tố tụng đã áp dụng. Nêu nguồn doc_id khi dùng dữ kiện graph.
Danh sách vụ chỉ bao phủ dữ liệu đã trích xuất; không khẳng định đầy đủ ngoài corpus.
Khi liệt kê vụ, mỗi mục Vụ trong dữ kiện graph chỉ xuất hiện một lần. Tên người và tên bài
trong cùng mục không phải các vụ khác nhau; dùng chunks để bổ sung, không liệt kê lại mục đã có.

Dữ kiện knowledge graph:
{facts}

Đoạn văn bản:
{chunks}

Câu hỏi: {question}
Trả lời:"""

class GraphRAGAgent:
    """Hybrid GraphRAG: the same vector top-k as flat RAG, plus facts expanded from the graph."""

    def __init__(self, store: EmbeddingStore, graph: Neo4jGraph, llm_fn: Callable[[str], str]) -> None:
        self.store = store
        self.graph = graph
        self.llm_fn = llm_fn

    def answer(self, question: str, top_k: int = 3) -> str:
        # TODO KG-4: vector top-k (same as flat RAG) -> doc_ids of the hits -> self.graph.context(question, doc_ids)
        #            -> fill GRAPH_PROMPT -> self.llm_fn(prompt)
        chunks = self.store.search(question, top_k=top_k)
        doc_ids = list(dict.fromkeys(chunk['metadata']['doc_id'] for chunk in chunks))
        facts = self.graph.context(question, doc_ids)
        prompt = GRAPH_PROMPT.format(
            facts="\n".join(f"- {fact}" for fact in facts),
            chunks="\n\n".join(f"[{i}] {chunk['content']}" for i, chunk in enumerate(chunks, 1)),
            question=question,
        )
        return self.llm_fn(prompt)
