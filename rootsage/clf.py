import joblib

from numpy import vectorize


clf_N = joblib.load("rootsage/classifiers/N.joblib")
clf_P = joblib.load("rootsage/classifiers/P.joblib")
clf_K = joblib.load("rootsage/classifiers/K.joblib")

clf_mapping = {
    0: "Low",
    1: "High",
    2: "Okay"
}


def classify_N(data):
    """
    Classify the given nitrogen levels depending on
    the associated crop.

    :param data: the data to be classified
    """

    pred = clf_N.predict(data)
    """
    vectorize(clf_mapping.get) returns a function
    that behaves like dict.get but takes a numpy array
    so all 0s will become 'low', 1s to 'high', and so on
    """
    return vectorize(clf_mapping.get)(pred)


def classify_P(data):
    """
    Classify the given phosphorus levels depending on
    the associated crop.

    :param data: the data to be classified
    """

    pred = clf_P.predict(data)
    return vectorize(clf_mapping.get)(pred)


def classify_K(data):
    """
    Classify the given potassium levels depending on
    the associated crop.

    :param data: the data to be classified
    """

    pred = clf_K.predict(data)
    return vectorize(clf_mapping.get)(pred)


def classify(data):
    return {
        "clf_N": classify_N(data[["N", "label"]])[0], 
        "clf_P": classify_P(data[["P", "label"]])[0], 
        "clf_K": classify_K(data[["K", "label"]])[0]
    }