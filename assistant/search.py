"""
BM25 keyword search over a site's chunks.

Pure Python, no model downloads: an index for a small-business site is a
few hundred chunks, which BM25 searches in milliseconds and which deploys
to any free serverless host.
"""

import json
import math
import re
from collections import Counter
from pathlib import Path

STOPWORDS = set(
    "a an and are as at be by can do does for from has have how i if in is it its "
    "me my of on or our so that the their there this to was we what when where which "
    "who why will with you your".split()
)
TOKEN = re.compile(r"[a-z0-9]+")
SUFFIXES = ("ations", "ation", "ions", "ion", "ings", "ing", "ers", "er", "ed", "ly", "es", "s")

# Keyword search can't tell that "located" means "address". These cover the
# questions visitors ask small businesses most; each query term pulls in its group.
SYNONYM_GROUPS = [
    "where located location address find directions map area visit campus",
    "contact phone call email reach whatsapp number enquiry enquire",
    "hours open opening close closing timing times schedule",
    "price prices pricing cost costs fee fees tuition rate rates charge charges package",
    "apply application admission admissions enrol enroll enrolment register registration join",
    "book booking appointment reserve reservation consultation",
    "service services offer offering treatments products programmes programs",
    "curriculum pathways syllabus courses qualifications",
    "age ages aged year years old grade grades",
    "staff team doctors teachers leadership founder owner",
]


def _stem(token: str) -> str:
    if len(token) <= 4:
        return token
    if token.endswith("ies"):
        return token[:-3] + "y"
    for suffix in SUFFIXES:
        if token.endswith(suffix) and not token.endswith("ss") and len(token) - len(suffix) >= 3:
            return token[: -len(suffix)]
    return token


def tokenize(text: str) -> list[str]:
    return [_stem(t) for t in TOKEN.findall(text.lower()) if t not in STOPWORDS]


SYNONYMS: dict[str, set[str]] = {}
for _group in SYNONYM_GROUPS:
    _stems = set(tokenize(_group))
    for _stem_term in _stems:
        SYNONYMS.setdefault(_stem_term, set()).update(_stems)


def _url_words(url: str) -> str:
    path = url.split("://", 1)[-1].split("/", 1)[-1]
    return re.sub(r"[/_\-.]+", " ", path)


LABEL = re.compile(
    r"^(.{1,30}:|(our )?(location|address|find us|phone|telephone|tel|mobile|email|e-mail|whatsapp|fax|"
    r"contact( us| details)?|(opening |office |business )?hours|timings?|open)\s*:?)$",
    re.IGNORECASE,
)
SENTENCE_SPLIT = re.compile(r"(?<=[.!?])\s+(?=[A-Z0-9\"'(])|\n+")


def best_sentences(query: str, passages: list[dict], n: int = 3, max_chars: int = 480) -> list[str]:
    """The sentences from the top passages that best match the query, in reading order.

    Used when no LLM is available: quoting the most relevant sentences beats
    quoting the first 450 characters of the best chunk.
    """
    terms = expand_query(query)
    candidates = []
    for rank, passage in enumerate(passages[:3]):
        lines = [s.strip() for s in SENTENCE_SPLIT.split(passage["text"]) if s.strip()]
        for pos, line in enumerate(lines):
            following = lines[pos + 1] if pos + 1 < len(lines) else ""
            weight = 1.0
            if line.endswith("?") and following:
                # FAQ pair: match on the question, quote the answer.
                matched_text, quote = f"{line} {following}", following
            elif LABEL.match(line) and following:
                # Label/value block on contact pages: "Location" / "Sunmarke School" / "Behind ..., Dubai"
                value = []
                for nxt in lines[pos + 1:pos + 4]:
                    if nxt.endswith("?") or LABEL.match(nxt):
                        break
                    value.append(nxt)
                    if sum(len(v) for v in value) >= 60:
                        break
                if not value:
                    continue
                matched_text, quote = f"{line} {' '.join(value)}", f"{line.rstrip(':')}: {', '.join(value)}"
            elif len(line) >= 25:
                matched_text, quote = line, line
            elif len(line.split()) >= 3:
                # Short list items ("Two Swimming Pools") can answer on their own, at lower confidence.
                matched_text, quote, weight = line, line, 0.8
            else:
                continue
            tokens = set(tokenize(matched_text))
            score = weight * sum(w for t, w in terms.items() if t in tokens)
            if score > 0:
                # Earlier passages are more relevant overall; break ties in their favor.
                candidates.append((score - 0.1 * rank, rank, pos, quote))

    picked: list[tuple] = []
    for candidate in sorted(candidates, reverse=True):
        # A label/value block and its own value line can both match; keep only one of them.
        if any(candidate[3] in p[3] or p[3] in candidate[3] for p in picked):
            continue
        picked.append(candidate)
        if len(picked) == n:
            break
    picked.sort(key=lambda c: (c[1], c[2]))
    out, used = [], 0
    for *_, sentence in picked:
        if used + len(sentence) > max_chars and out:
            break
        out.append(sentence)
        used += len(sentence)
    return out


def expand_query(query: str) -> dict[str, float]:
    """Query terms weighted 1.0, synonyms they pull in weighted 0.5."""
    weights: dict[str, float] = {}
    for term in tokenize(query):
        weights[term] = 1.0
        for synonym in SYNONYMS.get(term, ()):
            weights.setdefault(synonym, 0.5)
    return weights


class SiteIndex:
    """A business's crawled content plus a BM25 index over it."""

    K1 = 1.5
    B = 0.75

    def __init__(self, meta: dict, chunks: list[dict]):
        self.meta = meta
        self.chunks = chunks
        # Title, section heading and URL path count double: a chunk under "Tuition Fees" on
        # /admissions/tuition-fees is about fees even if the word appears once in its text.
        self.docs = []
        for c in chunks:
            doc = Counter(tokenize(c["text"]))
            labels = tokenize(f"{c['title']} {c.get('section', '')} {_url_words(c['url'])}")
            for term in labels:
                doc[term] += 2
            self.docs.append(doc)
        self.lengths = [sum(d.values()) for d in self.docs]
        self.avg_length = (sum(self.lengths) / len(self.lengths)) if self.lengths else 1.0
        df = Counter()
        for doc in self.docs:
            df.update(doc.keys())
        n = len(self.docs)
        self.idf = {t: math.log(1 + (n - f + 0.5) / (f + 0.5)) for t, f in df.items()}

    def search(self, query: str, k: int = 5, per_page: int = 2) -> list[dict]:
        """Top-k chunks, at most per_page from any one URL so answers draw on varied pages."""
        terms = expand_query(query)
        asked = {t for t, w in terms.items() if w == 1.0}
        scored = []
        for i, doc in enumerate(self.docs):
            score = 0.0
            matched = 0
            norm = self.K1 * (1 - self.B + self.B * self.lengths[i] / self.avg_length)
            for term, weight in terms.items():
                freq = doc.get(term)
                if freq:
                    score += weight * self.idf[term] * freq * (self.K1 + 1) / (freq + norm)
                    matched += term in asked
            if score > 0:
                # Reward chunks that cover more of what was actually asked.
                coverage = matched / len(asked) if asked else 0.0
                scored.append((score * (1 + 0.5 * coverage), i))
        scored.sort(reverse=True)

        results, per_url = [], Counter()
        for score, i in scored:
            url = self.chunks[i]["url"]
            if per_url[url] >= per_page:
                continue
            per_url[url] += 1
            results.append({**self.chunks[i], "score": round(score, 3)})
            if len(results) == k:
                break
        return results

    def save(self, path: Path) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(
            json.dumps({"meta": self.meta, "chunks": self.chunks}, ensure_ascii=False, indent=1),
            encoding="utf-8",
        )

    @classmethod
    def load(cls, path: Path) -> "SiteIndex":
        data = json.loads(path.read_text(encoding="utf-8"))
        return cls(data["meta"], data["chunks"])
