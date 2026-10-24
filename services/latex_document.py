"""Route parsed learning materials using explicit labels, never AI guesses."""
import re


def document_profile(questions):
    labelled = sum(bool(q.get('classification_evidence')) for q in questions)
    kind = 'bank' if labelled else 'assessment'
    return dict(document_kind=kind, labelled_count=labelled, total_count=len(questions),
                mixed=bool(labelled and labelled < len(questions)))


def knowledge_heading(value):
    # Paper sections describe answer format, not a knowledge category.
    value = re.sub(r'^\s*(?:[IVX]+|\d+)\s*[.):–-]\s*', '', value or '', flags=re.I)
    return bool(value and not re.match(
        r'(?i)\s*(phần\b|part\b|section\b|trắc nghiệm\b|đúng\s*[/–-]?\s*sai\b|trả lời ngắn\b|tự luận\b|đề\s+(kiểm tra|thi|số|\d)\b)', value))
