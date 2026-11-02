import re
import unicodedata


_PROFANITY = (
    'fuck', 'fucking', 'shit', 'bullshit', 'asshole', 'bitch', 'bastard',
    'dick', 'cunt', 'motherfucker', 'whore', 'slut',
    'كس امك', 'كسمك', 'كسختك', 'شرموطة', 'قحبة', 'منيوك', 'متناك',
    'خول', 'عرص', 'زبي', 'طيز', 'ابن الشرموطة', 'ابن القحبة',
)


def _normalize(value):
    value = unicodedata.normalize('NFKC', value or '').lower()
    value = re.sub(r'[\u064b-\u065f\u0670\u0640]', '', value)
    value = value.translate(str.maketrans({'أ': 'ا', 'إ': 'ا', 'آ': 'ا', 'ى': 'ي'}))
    return re.sub(r'[^\w]+', ' ', value, flags=re.UNICODE).strip()


def moderation_reason(review):
    text = _normalize(' '.join((
        review.role_title, review.interview_process, review.pros, review.cons,
    )))
    tokens = set(text.split())
    for term in _PROFANITY:
        normalized = _normalize(term)
        if ' ' in normalized:
            if f' {normalized} ' in f' {text} ':
                return 'Automatically held: abusive language detected.'
        elif normalized in tokens:
            return 'Automatically held: abusive language detected.'
    return ''
