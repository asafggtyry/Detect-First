"""Learned word/character models, independent of message evidence rules."""
from __future__ import annotations

import numpy as np
from sklearn.base import BaseEstimator, ClassifierMixin
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import LogisticRegression
from sklearn.pipeline import FeatureUnion, Pipeline

from detect_first.message_data import clean_text


class ThresholdClassifier(ClassifierMixin, BaseEstimator):
    def __init__(self, threshold: float = 0.5):
        self.threshold = threshold

    def fit(self, X, y, sample_weight=None):
        self.estimator_ = LogisticRegression(C=1.0, class_weight="balanced",
                                             max_iter=1000, random_state=2026)
        self.estimator_.fit(X, y, sample_weight=sample_weight)
        self.classes_ = self.estimator_.classes_
        return self

    def predict_proba(self, X):
        return self.estimator_.predict_proba(X)

    def predict(self, X):
        return (self.predict_proba(X)[:, 1] >= self.threshold).astype(int)


def build_message_pipeline(features: str) -> Pipeline:
    common = dict(preprocessor=clean_text, min_df=2, sublinear_tf=True, dtype=np.float32)
    word = TfidfVectorizer(ngram_range=(1, 2), max_features=80_000, **common)
    char = TfidfVectorizer(analyzer="char_wb", ngram_range=(3, 5),
                           max_features=100_000, **common)
    choices = {"word": word, "char": char,
               "hybrid": FeatureUnion([("word", word), ("char", char)])}
    return Pipeline([("features", choices[features]), ("classifier", ThresholdClassifier())])
