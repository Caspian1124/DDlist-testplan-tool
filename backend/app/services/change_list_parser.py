from __future__ import annotations

import re
from collections import Counter
from typing import Iterable, List, Sequence

from app.models.part_models import ChangeListMatch, NormalizedPart, ReleaseNoteRow

TOKEN_SPLIT_PATTERN = re.compile(r"[\/,;:\s\[\]\(\)]+")


def split_release_note_text(content: str) -> List[str]:
    if not content:
        return []
    return [token.strip() for token in TOKEN_SPLIT_PATTERN.split(content) if token.strip()]


def extract_pn_candidates(content: str, pn_pattern: re.Pattern) -> List[str]:
    found: List[str] = []
    for item in pn_pattern.findall(content or ""):
        found.append(str(item).strip().upper())
    for token in split_release_note_text(content or ""):
        match = pn_pattern.fullmatch(token)
        if match:
            found.append(match.group(0).strip().upper())
    seen = set()
    result = []
    for pn in found:
        if pn not in seen:
            seen.add(pn)
            result.append(pn)
    return result


def compare_release_note_with_ddlist(release_rows: Iterable[ReleaseNoteRow], ddlist_parts: Sequence[NormalizedPart], pn_pattern: re.Pattern) -> List[ChangeListMatch]:
    ddlist_counter = Counter([p.pn.strip().upper() for p in ddlist_parts if p.pn])
    results: List[ChangeListMatch] = []
    for row in release_rows:
        candidates = extract_pn_candidates(row.content, pn_pattern)
        for pn in candidates:
            matched_count = ddlist_counter.get(pn, 0)
            exists = matched_count > 0
            results.append(ChangeListMatch(
                release_date=row.release_date,
                release_version=row.release_version,
                extracted_pn=pn,
                exists_in_ddlist=exists,
                matched_ddlist_row_count=matched_count,
                status="FOUND" if exists else "NOT_FOUND",
                message="部件已更新" if exists else f"未找到部件号：{pn}",
            ))
    return results
