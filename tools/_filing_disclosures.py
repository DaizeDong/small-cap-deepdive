"""Extract local disclosure evidence without joining unrelated filing sentences.

These deterministic rules identify explicit statements, not the absence of all
financial risk. Unsupported, conditional and unresolved historical language
retains a null flag for review. Evidence offsets always refer to the input text.
"""
from __future__ import annotations

import re

_WEAKNESS = r'material\s+weakness(?:es)?'
_GOING = r'going[ -]concern'
_DOUBT = r'substantial\s+doubt'
_BREAK = re.compile(r'[.!?](?=\s|$)|;', re.I)
_ASSERTION_START = (
    r'(?:we|they|management|the|our|a|an|another|there|these|those|no|new|current|'
    r'earlier|substantial|material|identified|discovered|detected|found|reported)\b')
_COORDINATION = re.compile(
    rf'(?:,\s*)?\b(?:and|but|whereas|while|although|however|yet)\b(?=\s+{_ASSERTION_START})'
    rf'|,\s*(?={_ASSERTION_START})', re.I)
_PREDICATE = re.compile(
    r'\b(?:is|are|was|were|has|have|had|identified|found|detected|reported|exists?|'
    r'remains?|resolved|remediated|corrected|alleviated)\b', re.I)
_CONDITIONAL = re.compile(
    r'\b(?:if|whether|may|might|could|would|potential)\b|'
    r'\b(?:cannot|can\s+not)\s+(?:provide\s+)?assurance\b', re.I)
_HISTORICAL = re.compile(r'\b(?:prior|previous|previously|historical|historically)\b', re.I)
_REMEDIED = re.compile(r'\b(?:remediated|resolved|corrected|alleviated)\b', re.I)
_NEGATION = re.compile(r"\b(?:no|none|not|never|neither|nor|without|cannot)\b|\b\w+n['’]t\b", re.I)
_REMEDY_MODIFIER = r'(?:been|to|be|yet|fully|successfully|completely|already|now)'
_NEGATED_REMEDY = re.compile(
    rf'\b(?:not|never)\s+(?:{_REMEDY_MODIFIER}\s+)*'
    r'(?:remediated|resolved|corrected|alleviated)\b', re.I)
_UNRESOLVED = re.compile(r'\b(?:unremediated|unresolved|uncorrected)\b', re.I)
_UNREMEDIED = re.compile(
    rf'{_NEGATED_REMEDY.pattern}|{_UNRESOLVED.pattern}', re.I)
_FUTURE_REMEDY = re.compile(r'\b(?:plan|plans|planned|will|expect|expects|intend|intends)\b', re.I)
_WEAKNESS_SUBJECT = (
    rf'{_WEAKNESS}(?:\s+(?:previously\s+)?(?:identified|reported|detected|found))?'
    r'(?:\s+(?:in|over|affecting)\s+(?:(?!(?:and|but|while|that|which|was|were|has|have|is|are|remains)\b)\w+\s*){1,10})?')
_DOUBT_SUBJECT = rf'{_DOUBT}\s+(?:about|regarding|concerning)\s+(?:[\w\x27-]+\s+){{0,24}}{_GOING}'
_REMEDY_OBJECT_PREFIX = r'(?:(?:the|a|an|all|previously|identified|reported|known|prior|existing|current)\s+)*'


def _clauses(text):
    start = 0
    for end in [match.end() for match in _BREAK.finditer(text)] + [len(text)]:
        sentence = text[start:end]
        conditional = bool(_CONDITIONAL.search(sentence))
        local_start = 0
        boundaries = []
        previous_boundary = 0
        for match in _COORDINATION.finditer(sentence):
            # A comma after a time preface does not introduce a second assertion.
            if match.group().strip() == ',' and not _PREDICATE.search(sentence[previous_boundary:match.start()]):
                continue
            boundaries.append((match.start(), match.end()))
            previous_boundary = match.end()
        for stop, next_start in boundaries + [(len(sentence), len(sentence))]:
            piece = sentence[local_start:stop]
            left = len(piece) - len(piece.lstrip())
            right = len(piece.rstrip())
            if left < right:
                offset = start + local_start
                yield offset + left, offset + right, piece[left:right], conditional
            local_start = next_start
        start = end


def _unscoped_negation(text, assertions):
    """Require every explicit negator to belong to a recognized assertion."""
    return any(not any(match.start() <= negative.start() < match.end() for match in assertions)
               for negative in _NEGATION.finditer(text))


def _negative_status(text, patterns):
    assertions = [match for pattern in patterns for match in re.finditer(pattern, text, re.I)]
    if assertions:
        if len(list(_NEGATION.finditer(text))) != 1 or _unscoped_negation(text, assertions):
            return 'ambiguous'
        return 'negated'
    return None


def _remedy_polarity(assertion):
    negatives = list(_NEGATION.finditer(assertion))
    if not negatives:
        return 'affirmative' if _UNRESOLVED.search(assertion) else 'resolved'
    negated = _NEGATED_REMEDY.search(assertion)
    if len(negatives) == 1 and negated and negated.start() == negatives[0].start():
        return 'affirmative'
    return 'ambiguous'


def _remedy_status(text, topic, subject):
    """Recognize a remedy only when the disclosure is its subject or direct object."""
    if _FUTURE_REMEDY.search(text):
        return None
    predicate = (
        rf'{subject}\s+(?:has|have|had|is|are|was|were|remains?|continues?)\b'
        rf'(?:\s+(?:{_REMEDY_MODIFIER}|not|never))*'
        r'\s+(?:remediated|resolved|corrected|alleviated|unremediated|unresolved|uncorrected)\b')
    adjective = rf'\b(?:unremediated|unresolved|uncorrected)\s+{topic}'
    object_remedy = (
        rf'\b(?:(?:not|never)\s+(?:{_REMEDY_MODIFIER}\s+)*)?'
        rf'(?:remediated|resolved|corrected|alleviated)\s+{_REMEDY_OBJECT_PREFIX}{topic}')
    assertions = [match for pattern in (predicate, adjective, object_remedy)
                  for match in re.finditer(pattern, text, re.I)]
    if assertions and _unscoped_negation(text, assertions):
        return 'ambiguous'
    states = {_remedy_polarity(match.group()) for match in assertions}
    if len(states) > 1:
        return 'ambiguous'
    return next(iter(states), None)


def _weakness_status(text):
    if _CONDITIONAL.search(text):
        return 'ambiguous'
    negative = (
        rf'\bno\s+(?:(?:new|other|additional|known|identified|unremediated|unresolved|uncorrected)\s+)*{_WEAKNESS}',
        rf'\b(?:not|never)\s+(?:identify|identified|find|found|detect|detected|report|reported)'
        rf'\s+(?:\w+\s+){{0,6}}{_WEAKNESS}',
        rf'{_WEAKNESS}.{{0,60}}\b(?:is|are|was|were)\s+not\s+(?:present|identified|found|detected)',
    )
    negative_status = _negative_status(text, negative)
    if negative_status:
        return negative_status
    remedy = _remedy_status(text, _WEAKNESS, _WEAKNESS_SUBJECT)
    if remedy:
        return remedy
    if _REMEDIED.search(text) or _UNREMEDIED.search(text):
        return 'ambiguous'
    if _HISTORICAL.search(text):
        return 'historical'
    if re.search(r'\b(?:defined|definition)\b|\bis\s+a\s+deficiency\b', text, re.I):
        return 'ambiguous'
    ineffective = re.search(r'\b(?:is|are|was|were)\s+not\s+effective\b', text, re.I)
    if ineffective and re.search(r'\b(?:internal|financial\s+reporting)\s+controls?\b', text, re.I):
        return 'ambiguous' if _unscoped_negation(text, [ineffective]) else 'affirmative'
    if _NEGATION.search(text):
        return 'ambiguous'
    affirmative = (
        rf'\b(?:identified|discovered|detected|found|reported)\s+(?:\w+\s+){{0,6}}{_WEAKNESS}',
        rf'{_WEAKNESS}.{{0,80}}\b(?:exists|exist|persists|persist|remains|remain)\b',
        rf'{_WEAKNESS}.{{0,80}}\b(?:was|were|has\s+been|have\s+been)\s+identified\b',
    )
    if any(re.search(pattern, text, re.I) for pattern in affirmative):
        return 'affirmative'
    return 'ambiguous'


def _going_status(text):
    going = re.search(_GOING, text, re.I)
    doubt = re.search(_DOUBT, text, re.I)
    if _CONDITIONAL.search(text):
        return 'ambiguous'
    if not going or not doubt:
        if going and re.search(r'going[ -]concern\s+basis\b', text, re.I):
            return 'not_asserted'
        return 'ambiguous'
    negative = (
        rf'\b(?:no|without)\s+(?:any\s+)?{_DOUBT}',
        rf'\bnot\s+(?:raise|raises|raised|have|has|create|creates)\s+(?:any\s+)?{_DOUBT}',
        rf'{_DOUBT}.{{0,60}}\b(?:does|did)\s+not\s+exist\b',
    )
    negative_status = _negative_status(text, negative)
    if negative_status:
        return negative_status
    remedy = _remedy_status(text, _DOUBT, _DOUBT_SUBJECT)
    if remedy:
        return remedy
    if _REMEDIED.search(text) or _UNREMEDIED.search(text):
        return 'ambiguous'
    if _HISTORICAL.search(text):
        return 'historical'
    if _NEGATION.search(text):
        return 'ambiguous'
    if re.search(r'\b(?:raises?|raised|exists?|there\s+is|have|has)\b', text, re.I):
        return 'affirmative'
    return 'ambiguous'


def _summarize(spans):
    states = {span['status'] for span in spans}
    for state, flag in (('affirmative', True), ('ambiguous', None), ('historical', None),
                        ('resolved', False), ('negated', False), ('not_asserted', False)):
        if state in states:
            return {'status': state, 'flag': flag, 'spans': spans}
    return {'status': 'not_mentioned', 'flag': False, 'spans': []}


def scan_disclosures(text: str) -> dict:
    """Return explicit going-concern and control-weakness findings with source spans."""
    if not isinstance(text, str):
        raise TypeError('Filing text must be a string')
    spans = {'going_concern': [], 'material_weakness': []}
    for start, end, clause, conditional in _clauses(text):
        weaknesses = len(re.findall(_WEAKNESS, clause, re.I))
        doubts = len(re.findall(_DOUBT, clause, re.I))
        going = bool(re.search(_GOING, clause, re.I))
        # Repeated or mixed topics without a recognized assertion boundary do
        # not have a reliable shared polarity. Keep their original evidence.
        unclear_scope = conditional or weaknesses > 1 or doubts > 1 or bool(weaknesses and (doubts or going))
        for topic, pattern, classify in (
            ('going_concern', rf'{_GOING}|{_DOUBT}', _going_status),
            ('material_weakness', _WEAKNESS, _weakness_status),
        ):
            if re.search(pattern, clause, re.I):
                spans[topic].append({'start': start, 'end': end, 'text': clause,
                                     'status': 'ambiguous' if unclear_scope else classify(clause)})
    return {topic: _summarize(rows) for topic, rows in spans.items()}
