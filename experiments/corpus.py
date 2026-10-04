"""Synthetic corpus with exact, graded relevance for controlled IR experiments.

Why synthetic? Public test collections are large, licensed and slow to run in
CI. A generated collection with *known* relevance lets us (a) reproduce every
number from a seed, (b) run in seconds, and (c) vary one property at a time
(document length skew, vocabulary overlap, morphology) to see which ranking
assumptions matter. The design mirrors the structure real collections exhibit:

* **Topics and subtopics.** Each topic owns a Zipf-distributed vocabulary;
  each subtopic owns a small focused vocabulary. A document has one primary
  (topic, subtopic) pair and, with some probability, a secondary topic whose
  words act as *hard negatives* for queries on that topic.
* **Graded relevance.** For a query on (t, s): documents with primary (t, s)
  are highly relevant (grade 3); documents with primary topic t but another
  subtopic are marginally relevant (grade 1); everything else is irrelevant.
* **Morphology.** Emitted words are inflected (``-s``, ``-ing``, ``-ed``) at a
  configurable rate while queries use base forms, so the effect of stemming
  is measurable.
* **Length skew and keyword stuffing.** Lengths are log-normal; a small share
  of documents repeat one topic word many times. These stress BM25's length
  normalisation (``b``) and term-frequency saturation (``k1``).
"""

from __future__ import annotations

import math
import random
from collections.abc import Callable
from dataclasses import dataclass, field

from app.search.index import Document

_SYLLABLES = [
    "ka",
    "to",
    "ri",
    "me",
    "sa",
    "lu",
    "ne",
    "vo",
    "di",
    "pa",
    "zu",
    "fe",
    "gi",
    "ho",
    "wy",
    "ba",
    "nu",
    "ce",
]
_SUFFIXES = ["s", "ing", "ed"]

HIGH_GRADE = 3.0
LOW_GRADE = 1.0


def _make_word(rng: random.Random, min_syl: int = 2, max_syl: int = 4) -> str:
    return "".join(rng.choice(_SYLLABLES) for _ in range(rng.randint(min_syl, max_syl)))


@dataclass(slots=True)
class SyntheticCorpus:
    documents: list[Document]
    queries: dict[str, str]
    qrels: dict[str, dict[int, float]]
    topics: list[list[str]] = field(default_factory=list)
    subtopics: list[list[list[str]]] = field(default_factory=list)

    @property
    def size(self) -> int:
        return len(self.documents)

    def relevant_counts(self) -> dict[str, int]:
        return {qid: sum(1 for g in qrels.values() if g > 0) for qid, qrels in self.qrels.items()}


def _zipf_sampler(rng: random.Random, words: list[str]) -> Callable[[], str]:
    weights = [1.0 / (i + 1) for i in range(len(words))]
    total = sum(weights)
    cumulative: list[float] = []
    acc = 0.0
    for w in weights:
        acc += w / total
        cumulative.append(acc)

    def sample() -> str:
        u = rng.random()
        for word, bound in zip(words, cumulative, strict=True):
            if u <= bound:
                return word
        return words[-1]

    return sample


def generate_corpus(
    *,
    num_docs: int = 600,
    num_topics: int = 12,
    subtopics_per_topic: int = 4,
    vocab_per_topic: int = 60,
    subtopic_vocab: int = 10,
    shared_vocab: int = 200,
    mean_length: int = 120,
    length_sigma: float = 0.6,
    secondary_topic_prob: float = 0.35,
    noise_ratio: float = 0.45,
    subtopic_ratio: float = 0.12,
    inflection_rate: float = 0.35,
    stuffing_prob: float = 0.05,
    queries_per_subtopic: int = 2,
    query_length: tuple[int, int] = (1, 3),
    seed: int = 42,
) -> SyntheticCorpus:
    rng = random.Random(seed)
    seen: set[str] = set()

    def fresh_words(count: int) -> list[str]:
        words: list[str] = []
        while len(words) < count:
            word = _make_word(rng)
            if word not in seen:
                seen.add(word)
                words.append(word)
        return words

    shared = fresh_words(shared_vocab)
    topics = [fresh_words(vocab_per_topic) for _ in range(num_topics)]
    subtopics = [
        [fresh_words(subtopic_vocab) for _ in range(subtopics_per_topic)] for _ in range(num_topics)
    ]

    sample_shared = _zipf_sampler(rng, shared)
    sample_topic = [_zipf_sampler(rng, words) for words in topics]
    sample_sub = [[_zipf_sampler(rng, words) for words in subs] for subs in subtopics]

    def inflect(word: str) -> str:
        return word + rng.choice(_SUFFIXES) if rng.random() < inflection_rate else word

    documents: list[Document] = []
    labels: list[tuple[int, int, int | None]] = []
    for doc_id in range(num_docs):
        topic = rng.randrange(num_topics)
        sub = rng.randrange(subtopics_per_topic)
        other: int | None = None
        if rng.random() < secondary_topic_prob:
            other = rng.choice([t for t in range(num_topics) if t != topic])
        length = max(15, int(rng.lognormvariate(math.log(mean_length), length_sigma)))
        words: list[str] = []
        for _ in range(length):
            u = rng.random()
            if u < noise_ratio:
                words.append(inflect(sample_shared()))
            elif u < noise_ratio + subtopic_ratio:
                words.append(inflect(sample_sub[topic][sub]()))
            elif other is not None and u < noise_ratio + subtopic_ratio + 0.15:
                words.append(inflect(sample_topic[other]()))
            else:
                words.append(inflect(sample_topic[topic]()))
        if rng.random() < stuffing_prob:
            stuffed = sample_topic[topic]()
            words.extend([stuffed] * rng.randint(20, 60))
        title_words = [
            sample_sub[topic][sub]() if rng.random() < 0.5 else sample_topic[topic]()
            for _ in range(rng.randint(2, 5))
        ]
        documents.append(
            Document(
                doc_id=doc_id,
                fields={"title": " ".join(title_words), "content": " ".join(words)},
                metadata={
                    "topic": topic,
                    "subtopic": sub,
                    "secondary": other,
                    "length": len(words),
                },
            )
        )
        labels.append((topic, sub, other))

    queries: dict[str, str] = {}
    qrels: dict[str, dict[int, float]] = {}
    for topic in range(num_topics):
        for sub in range(subtopics_per_topic):
            relevant = {
                doc_id: HIGH_GRADE if (t == topic and s == sub) else LOW_GRADE
                for doc_id, (t, s, _) in enumerate(labels)
                if t == topic
            }
            if not any(grade == HIGH_GRADE for grade in relevant.values()):
                continue
            for q in range(queries_per_subtopic):
                terms = {sample_sub[topic][sub]() for _ in range(rng.randint(*query_length))}
                if rng.random() < 0.5:
                    terms.add(sample_topic[topic]())
                query_id = f"t{topic:02d}s{sub}q{q}"
                queries[query_id] = " ".join(sorted(terms))
                qrels[query_id] = dict(relevant)
    return SyntheticCorpus(
        documents=documents, queries=queries, qrels=qrels, topics=topics, subtopics=subtopics
    )


__all__ = ["HIGH_GRADE", "LOW_GRADE", "SyntheticCorpus", "generate_corpus"]
