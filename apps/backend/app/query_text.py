"""Small local-only text heuristics; never translate or call a language service."""

import re
import unicodedata


def fold_text(text: str) -> str:
    """Accent/case/final-sigma insensitive matching, not an outbound rewrite."""
    return "".join(
        char for char in unicodedata.normalize("NFD", text.casefold())
        if not unicodedata.combining(char)
    )


QUESTION_START = (
    r"(?:what|who|where|when|why|how|is|are|was|were|do|does|did|has|have|had|"
    r"can|could|will|would|should|τι|πο[υύ]|π[οό]τε|π[ωώ]ς|γιατ[ιί]|"
    r"ποιος|ποια|ποιο|ποιες|ποιοι|π[οό]σο|π[οό]σα|ε[ιί]ναι|υπ[αά]ρχει)"
)
CLAUSE_SPLIT = re.compile(
    rf"(?:\s+(?:and|και)\s+|\s*[?;;!.]\s*(?:(?:and|και)\s+)?)"
    rf"(?={QUESTION_START}\b)", re.IGNORECASE,
)
DEPENDENT_CLAUSE = re.compile(
    r"\b(?:it|its|they|them|their|αυτο|αυτου|αυτη|αυτησ|αυτα|αυτων)\b",
    re.IGNORECASE,
)
ADVANCED_QUERY = re.compile(r'https?://|\b(?:site|intitle|inurl|filetype):|["«»]', re.IGNORECASE)
GREEK_STOPWORDS = set(
    "και η ο οι το τα τη την τον του τησ των σε στο στην στον στα με για απο "
    "να ενα μια ειναι ηταν θα αν δεν τι ποιοσ ποια ποιο ποιεσ ποιοι ποιων "
    "που πωσ ποτε γιατι ποσο ποσα υπαρχει υπαρχουν ωσ αυτο αυτη αυτοσ".split()
)


def question_clauses(query: str) -> list[str]:
    original = " ".join(unicodedata.normalize("NFC", query or "").split()).strip()
    if ADVANCED_QUERY.search(original):
        return [original]
    parts = [part.strip(" .?!;;") for part in CLAUSE_SPLIT.split(original) if part.strip(" .?!;;")]
    # Do not invent a subject for orphaned pronouns or rewrite search operators.
    if len(parts) < 2 or any(DEPENDENT_CLAUSE.search(fold_text(part)) for part in parts[1:]):
        return [original]
    return list(dict.fromkeys(parts))


def infer_greek_language(query: str) -> str:
    letters = [char for char in query if char.isalpha()]
    greek = sum("GREEK" in unicodedata.name(char, "") for char in letters)
    greek_question = re.match(r"^(?:τι|πωσ|ποτε|που|γιατι|ποια|ποιοσ|ειναι)\b", fold_text(query.strip()))
    return "el" if greek >= 3 and (greek >= len(letters) / 2 or greek_question) else ""


def is_greek_current_query(query: str) -> bool:
    return bool(re.search(
        r"\b(?:σημερα|τωρα|επικαιροτητα|εξελιξεισ|ειδησεισ|τρεχουσα|τρεχουσεσ|τελευταιεσ)\b",
        fold_text(query),
    ))
