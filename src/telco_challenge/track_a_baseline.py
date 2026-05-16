from __future__ import annotations

import math
import re
from dataclasses import dataclass
from typing import Iterable, Protocol

try:
    from sklearn.feature_extraction.text import TfidfVectorizer
    from sklearn.linear_model import LogisticRegression
except ImportError:
    TfidfVectorizer = None
    LogisticRegression = None


ACTION_PATTERNS: list[tuple[str, str]] = [
    ("insufficient_data", r"\binsufficient data\b"),
    ("test_server", r"\btest server\b|\btransmission issues\b"),
    ("add_neighbor", r"\badd neighbor relationship\b"),
    ("decrease_power", r"\bdecrease transmission power\b"),
    ("increase_power", r"\bincrease transmission power\b"),
    ("press_tilt", r"\bpress down\b.*\btilt\b"),
    ("lift_tilt", r"\blift\b.*\btilt\b"),
    ("azimuth", r"\bazimuth\b"),
    ("increase_a3", r"\bincrease a3 offset\b"),
    ("decrease_a3", r"\bdecrease a3 offset\b"),
    ("pdcch", r"\bpdcchoccupiedsymbolnum\b"),
    ("covinterfreq", r"\bcovinterfreq\b"),
    ("handover", r"\bhandover\b"),
]


@dataclass(frozen=True)
class OptionScore:
    option_id: str
    label: str
    score: float


class TrackAPredictor(Protocol):
    def fit(self, rows: Iterable[dict]) -> None:
        ...

    def predict_row(self, row: dict) -> str:
        ...


class TrackAOptionBaseline:
    def __init__(self, alpha: float = 1.0) -> None:
        self.alpha = alpha
        self.label_counts: dict[str, list[int]] = {}
        self.action_counts: dict[str, list[int]] = {}
        self.global_positive = 0
        self.global_total = 0

    def fit(self, rows: Iterable[dict]) -> None:
        for row in rows:
            answer_ids = set(str(row.get("answer", "")).split("|"))
            for option in row["task"]["options"]:
                label = normalize_label(option["label"])
                is_positive = option["id"] in answer_ids
                self._add(self.label_counts, label, is_positive)
                self.global_positive += int(is_positive)
                self.global_total += 1
                for action in action_features(label):
                    self._add(self.action_counts, action, is_positive)

    def predict_row(self, row: dict) -> str:
        scores = self.score_options(row)
        if row.get("tag") == "multiple-answer":
            selected = choose_multiple(scores)
        else:
            selected = scores[:1]
        return "|".join(item.option_id for item in selected)

    def score_options(self, row: dict) -> list[OptionScore]:
        scored = []
        for option in row["task"]["options"]:
            label = normalize_label(option["label"])
            score = self.score_label(label)
            scored.append(OptionScore(option_id=option["id"], label=option["label"], score=score))
        return sorted(scored, key=lambda item: (-item.score, option_number(item.option_id)))

    def score_label(self, label: str) -> float:
        label_score = smoothed_rate(self.label_counts.get(label), self.alpha, self.global_rate)
        actions = action_features(label)
        if not actions:
            return label_score
        action_scores = [smoothed_rate(self.action_counts.get(action), self.alpha, self.global_rate) for action in actions]
        action_score = sum(action_scores) / len(action_scores)
        if label in self.label_counts and sum(self.label_counts[label]) >= 3:
            return 0.7 * label_score + 0.3 * action_score
        return 0.2 * label_score + 0.8 * action_score

    @property
    def global_rate(self) -> float:
        if not self.global_total:
            return 0.0
        return self.global_positive / self.global_total

    @staticmethod
    def _add(store: dict[str, list[int]], key: str, is_positive: bool) -> None:
        counts = store.setdefault(key, [0, 0])
        counts[0] += int(is_positive)
        counts[1] += 1


class TrackATfidfBaseline:
    def __init__(self, multiple_ratio: float = 0.8) -> None:
        if TfidfVectorizer is None or LogisticRegression is None:
            raise RuntimeError("scikit-learn is required for TrackATfidfBaseline")
        self.multiple_ratio = multiple_ratio
        self.vectorizer = TfidfVectorizer(
            lowercase=True,
            ngram_range=(1, 3),
            min_df=2,
            max_features=20000,
            sublinear_tf=True,
        )
        self.classifier = LogisticRegression(
            max_iter=1000,
            class_weight="balanced",
            solver="liblinear",
        )

    def fit(self, rows: Iterable[dict]) -> None:
        texts = []
        labels = []
        for row in rows:
            answer_ids = set(str(row.get("answer", "")).split("|"))
            for option in row["task"]["options"]:
                texts.append(option_text(row, option))
                labels.append(int(option["id"] in answer_ids))
        matrix = self.vectorizer.fit_transform(texts)
        self.classifier.fit(matrix, labels)

    def predict_row(self, row: dict) -> str:
        scores = self.score_options(row)
        if row.get("tag") == "multiple-answer":
            selected = choose_multiple(scores, ratio=self.multiple_ratio)
        else:
            selected = scores[:1]
        return "|".join(item.option_id for item in selected)

    def score_options(self, row: dict) -> list[OptionScore]:
        texts = [option_text(row, option) for option in row["task"]["options"]]
        matrix = self.vectorizer.transform(texts)
        probabilities = self.classifier.predict_proba(matrix)[:, 1]
        scored = [
            OptionScore(option_id=option["id"], label=option["label"], score=float(probability))
            for option, probability in zip(row["task"]["options"], probabilities)
        ]
        return sorted(scored, key=lambda item: (-item.score, option_number(item.option_id)))

def choose_multiple(scores: list[OptionScore], ratio: float = 0.65) -> list[OptionScore]:
    if not scores:
        return []
    top = scores[0].score
    threshold = max(0.07, top * ratio)
    selected = [item for item in scores if item.score >= threshold]
    selected = selected[:4]
    if len(selected) < 2:
        selected = scores[:2]
    return selected


def normalize_label(label: str) -> str:
    value = label.lower().strip()
    value = re.sub(r"\s+", " ", value)
    value = value.replace("2 sym", "2sym")
    return value


def action_features(label: str) -> list[str]:
    return [name for name, pattern in ACTION_PATTERNS if re.search(pattern, label)]


def option_text(row: dict, option: dict) -> str:
    tag = row.get("tag", "")
    label = option.get("label", "")
    normalized = normalize_label(label)
    features = " ".join(action_features(normalized))
    return f"tag:{tag} action:{features} label:{normalized}"


def smoothed_rate(counts: list[int] | None, alpha: float, prior: float) -> float:
    if counts is None:
        return prior
    positives, total = counts
    return (positives + alpha * prior) / (total + alpha)


def option_number(option_id: str) -> int:
    match = re.search(r"\d+", option_id)
    return int(match.group(0)) if match else math.inf
