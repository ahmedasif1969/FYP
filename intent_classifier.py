"""Train a small multinomial Naive Bayes classifier from fictional examples."""

import json
import math
import re
from collections import Counter
from pathlib import Path

COMMON_WORDS = set(
    "a an the can could do does how i is it me my of our please to we what who would "
    "you your for and in on with need want help request get one have".split()
)


class IntentClassifier:
    def __init__(self, examples):
        self.vocabulary = set()
        self.word_counts = {}
        self.document_counts = {}
        for intent, sentences in examples.items():
            counts = Counter(
                word for sentence in sentences for word in self.tokens(sentence)
                if word not in COMMON_WORDS
            )
            self.word_counts[intent] = counts
            self.document_counts[intent] = len(sentences)
            self.vocabulary.update(counts)
        self.total_documents = sum(self.document_counts.values())

    @classmethod
    def from_file(cls, path=Path(__file__).with_name("intent_examples.json")):
        return cls(json.loads(path.read_text(encoding="utf-8")))

    @staticmethod
    def tokens(text):
        return re.findall(r"[a-z0-9]+", text.casefold())

    def predict(self, text):
        words = [word for word in self.tokens(text) if word in self.vocabulary]
        if not words:
            return "needs_clarification", 0.0

        scores = {}
        for intent, counts in self.word_counts.items():
            denominator = counts.total() + len(self.vocabulary)
            prior = self.document_counts[intent] / self.total_documents
            scores[intent] = math.log(prior) + sum(
                math.log((counts[word] + 1) / denominator) for word in words
            )

        best = max(scores, key=scores.get)
        score = 1 / sum(math.exp(value - scores[best]) for value in scores.values())
        return (best if score >= 0.45 else "needs_clarification"), score
