# -*- coding: utf-8 -*-
"""
FastTextModel: A wrapper for Facebook fastText model

Author: Evgenii Nikitin <e.nikitin@nyu.edu>

Part of https://github.com/crazyfrogspb/RedditScore project

Copyright (c) 2018 Evgenii Nikitin. All rights reserved.
This work is licensed under the terms of the MIT license.
"""

import os
import tempfile
import warnings

import fastText
import numpy as np
import pandas as pd
from sklearn.base import BaseEstimator, ClassifierMixin

from . import redditmodel


def data_to_temp(X, label, y=None):
    # Generate temorary file
    fd, path = tempfile.mkstemp()
    with os.fdopen(fd, 'w') as tmp:
        for i in range(X.shape[0]):
            if y is not None:
                doc = label + y[i] + ' ' + ' '.join(X[i])
            else:
                doc = ' '.join(X[i])
            tmp.write("%s\n" % doc)
    return path


class FastTextClassifier(BaseEstimator, ClassifierMixin):
    # Auxiliary sklearn-style wrapper for fastText python library
    def __init__(self, lr=0.1,
                 dim=100,
                 ws=5,
                 epoch=5,
                 minCount=1,
                 minCountLabel=0,
                 minn=0,
                 maxn=0,
                 neg=5,
                 wordNgrams=1,
                 loss="softmax",
                 bucket=2000000,
                 thread=12,
                 lrUpdateRate=100,
                 t=1e-4,
                 label="__label__",
                 verbose=2):
        self.lr = lr
        self.dim = dim
        self.ws = ws
        self.epoch = epoch
        self.minCount = minCount
        self.minCountLabel = minCountLabel
        self.minn = minn
        self.maxn = maxn
        self.neg = neg
        self.wordNgrams = wordNgrams
        self.loss = loss
        self.bucket = bucket
        self.thread = thread
        self.lrUpdateRate = lrUpdateRate
        self.t = t
        self.label = label
        self.verbose = verbose

        self._model = None
        self._num_classes = None

    def fit(self, X, y):
        # Fit model
        if not isinstance(X, np.ndarray):
            X = np.array(X)
        if not isinstance(y, np.ndarray):
            y = np.array(y)

        path = data_to_temp(X, self.label, y)
        self._num_classes = len(np.unique(y))
        self._model = fastText.train_supervised(path,
                                                lr=self.lr,
                                                dim=self.dim,
                                                ws=self.ws,
                                                epoch=self.epoch,
                                                minCount=self.minCount,
                                                minCountLabel=self.minCountLabel,
                                                minn=self.minn,
                                                maxn=self.maxn,
                                                neg=self.neg,
                                                wordNgrams=self.wordNgrams,
                                                loss=self.loss,
                                                bucket=self.bucket,
                                                thread=self.thread,
                                                lrUpdateRate=self.lrUpdateRate,
                                                t=self.t,
                                                label=self.label,
                                                verbose=self.verbose)
        os.remove(path)
        return self

    def predict(self, X):
        # Return predictions
        docs = [' '.join(doc) for doc in X]
        predictions = self._model.predict(docs, k=1)[0]
        predictions = np.array([pred[0][len(self.label):]
                                for pred in predictions])
        return predictions

    def predict_proba(self, X):
        # Return predicted probabilities
        docs = [' '.join(doc) for doc in X]
        predictions = zip(*self._model.predict(docs, k=self._num_classes))
        probabilities = []
        for pred in predictions:
            d = {key[len(self.label):]: value for key, value in zip(*pred)}
            probabilities.append(d)
        probabilities = pd.DataFrame(probabilities).fillna(1e-10)

        return probabilities


class FastTextModel(redditmodel.RedditModel):
    """Facebook fastText classifier

    Parameters
    ----------
    random_state : int, optional
        Random seed (the default is 24).
    **kwargs
        Other parameters for fastText model.
        Full description can be found here:
        https://github.com/facebookresearch/fastText

    Attributes
    ----------
    model_type : str
        Model type name
    _model : FastTextClassifier
        sklearn-style wrapper for fastText model
    """

    def __init__(self, random_state=24, **kwargs):
        super().__init__(random_state=random_state)
        self.model_type = 'fasttext'
        self._model = FastTextClassifier(**kwargs)

    def set_params(self, **params):
        """Set parameters of the model

        Parameters
        ----------
        **params
            Model parameters to update
        """
        self._model.set_params(**params)

    def fit(self, X, y):
        """Fit model

        Parameters
        ----------
        X: iterable, shape (n_samples, )
            Sequence of tokenized documents

        y: iterable, shape (n_samples, )
            Sequence of labels

        Returns
        -------
        FastTextModel
            Fitted model object
        """
        self._classes = sorted(np.unique(y))
        self._model.fit(X, y)
        fd, path = tempfile.mkstemp()
        self._model._model.save_softmax(path)
        emb = pd.read_csv(
            path, skiprows=[0], delimiter=' ', header=None).dropna(axis=1)
        emb.iloc[:, 0] = emb.iloc[:, 0].str[len(self._model.label):]
        emb.set_index(0, inplace=True)
        self.class_embeddings = emb
        os.remove(path)
        self.fitted = True
        return self
