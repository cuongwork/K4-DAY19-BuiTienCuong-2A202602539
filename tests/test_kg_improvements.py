"""Regression checks for extraction integrity, grouping, and legal context selection."""
from src.kg_extraction import compound_charge, source_units, validate_payload
from src.kg_context import group_cases, legal_excerpt, fact_budget, proof_excerpt
from src.models import Document


def test_rejects_explicit_multi_offence_but_preserves_single_legal_name():
    proof = 'Nguyễn Văn A bị truy tố cả tội nhận hối lộ và đánh bạc.'
    assert compound_charge('nhận hối lộ và đánh bạc', proof, [])
    assert compound_charge('nhận hối lộ, đánh bạc', proof, [])
    name = 'vi phạm quy định về nghiên cứu và thăm dò'
    assert not compound_charge(name, 'A phạm tội ' + name, [name])
    assert not compound_charge(name, 'A phạm tội ' + name, [])


def test_validator_retries_compound_without_fabricating_split_records():
    doc = Document('news', 'Nguyễn Văn A bị truy tố cả tội nhận hối lộ và đánh bạc.', {})
    text, units = source_units(doc.content)
    charge = {'raw_charge': 'nhận hối lộ và đánh bạc', 'status': 'prosecuted', 'evidence_ids': ['S0001']}
    payload = {'cases': [{'people': [{'name': 'Nguyễn Văn A', 'charges': [charge]}]}]}
    cases, errors = validate_payload(payload, doc, [], text, units)
    assert any('multiple offences' in e for e in errors)
    assert cases[0]['people'][0]['charges'] == []
    payload['cases'][0]['people'][0]['charges'] = [dict(charge, raw_charge=name) for name in ['nhận hối lộ', 'đánh bạc']]
    cases, errors = validate_payload(payload, doc, [], text, units)
    assert not errors
    assert len(cases[0]['people'][0]['charges']) == 2


def test_missing_second_offence_and_withdrawn_person_require_retry():
    doc = Document('news', 'Nguyễn Văn A bị truy tố cả tội nhận hối lộ và đánh bạc. '
                   'Nguyễn Hữu Bình từng bị khởi tố. Viện đã hủy quyết định khởi tố bị can đối với Bình.', {})
    text, units = source_units(doc.content)
    payload = {'cases': [{'people': [{'name': 'Nguyễn Văn A', 'charges': [{
        'raw_charge': 'nhận hối lộ', 'status': 'prosecuted', 'evidence_ids': ['S0001']}]}]}]}
    _, errors = validate_payload(payload, doc, [], text, units)
    assert any('missing' in e and 'đánh bạc' in e for e in errors)
    assert any('withdrawn' in e and 'Nguyễn Hữu Bình' in e for e in errors)


def test_direct_forensic_substance_statement_cannot_be_silently_omitted():
    doc = Document('news', 'Kết luận giám định xác định số viên nén này là MDMA.', {})
    text, units = source_units(doc.content)
    _, errors = validate_payload({'cases': [{'people': [], 'substances': []}]}, doc, [], text, units)
    assert any('substance MDMA missing' in e for e in errors)
    doc = Document('news', 'Công an thu giữ Methamphetamine.', {})
    text, units = source_units(doc.content)
    _, errors = validate_payload({'cases': [{'people': [], 'substances': [
        {'name': 'Methamphetamine', 'amount': '', 'evidence_ids': ['S0001']}]}]}, doc, [], text, units)
    assert not errors


def test_explicit_case_reference_can_group_sources_without_merging_nodes():
    a, b = case_row('one', 'doc1'), case_row('two', 'doc2')
    a['props']['date'], b['props']['date'] = '2025-01-01', '2025-01-02'
    for row in (a, b):
        row['props']['case_reference'] = '10 bị cáo trong vụ án xảy ra tại tổ chức X'
    facts = group_cases([a, b])
    assert len(facts) == 1 and 'doc1' in facts[0] and 'doc2' in facts[0]


def test_context_quotes_relevant_source_without_destroying_full_evidence():
    text = 'Nguyễn Văn A bị truy tố. ' + ('Một câu không liên quan. ' * 50) + 'A bị tuyên 36 tháng tù.'
    excerpt = proof_excerpt(text, ['Nguyễn Văn A', '36 tháng tù'])
    assert len(excerpt) < len(text)
    assert 'Nguyễn Văn A' in excerpt and '36 tháng tù' in excerpt
    assert '[…]' in excerpt


def case_row(key, doc, substance='MDMA', date='', location=''):
    return {'id': key, 'props': {'doc_id': doc, 'name': 'Vụ thử', 'summary': 'Tóm tắt', 'date': date},
            'people': ['Nguyễn Văn A', 'Trần Văn B'], 'substance': substance,
            'involvement': {'amount': '1g', 'evidence_text': 'Bằng chứng'}, 'location': location}


def test_grouping_same_case_preserves_substances_and_does_not_merge_by_people_alone():
    rows = [case_row('one', 'doc1'), case_row('one', 'doc1', 'Ketamine'), case_row('two', 'doc2')]
    facts = group_cases(rows)
    assert len(facts) == 2
    assert 'MDMA' in facts[0] and 'Ketamine' in facts[0]
    assert 'doc1' in facts[0] and 'doc2' in facts[1]


def test_cross_document_group_requires_event_corroboration_and_keeps_sources():
    facts = group_cases([case_row('one', 'doc1', date='2025-01-01', location='Hà Nội'),
                        case_row('two', 'doc2', date='2025-01-01', location='Hà Nội')])
    assert len(facts) == 1
    assert 'doc1' in facts[0] and 'doc2' in facts[0]


def test_legal_excerpt_preserves_penalty_and_threshold_for_selected_substance():
    text = '4. Phạt tù 20 năm, chung thân hoặc tử hình:\n\na) Cần sa 10kg.\n\nb) MDMA 100 gam trở lên.'
    result = legal_excerpt(text, ['MDMA'])
    assert 'tử hình' in result and '100 gam' in result
    assert 'Cần sa' not in result
    assert legal_excerpt(text, [], maximum=True) == text.split('\n')[0]
    assert fact_budget(['short', 'x' * 10000], 2, max_tokens=10) == ['short']
