import math

import pytest
from hypothesis import given, settings, strategies as st

from app.search import metrics as m

pytestmark = pytest.mark.research

QRELS = {1: 3.0, 2: 2.0, 3: 1.0}


def test_precision_recall_f1() -> None:
    ranked = [1, 9, 2, 8, 7]
    assert m.precision_at_k(ranked, QRELS, 2) == 0.5
    assert m.precision_at_k(ranked, QRELS, 5) == pytest.approx(0.4)
    assert m.recall_at_k(ranked, QRELS, 3) == pytest.approx(2 / 3)
    assert m.recall_at_k(ranked, {}, 3) == 0.0
    assert m.f1_at_k(ranked, QRELS, 3) == pytest.approx(2 * (2 / 3) * (2 / 3) / (4 / 3))
    assert m.f1_at_k([9], QRELS, 1) == 0.0
    with pytest.raises(ValueError, match="positive"):
        m.precision_at_k(ranked, QRELS, 0)


def test_reciprocal_rank_and_average_precision() -> None:
    assert m.reciprocal_rank([9, 8, 1], QRELS) == pytest.approx(1 / 3)
    assert m.reciprocal_rank([9, 8], QRELS) == 0.0
    # IIR example: relevant at ranks 1, 3, 5 of 3 relevant -> (1 + 2/3 + 3/5) / 3
    assert m.average_precision([1, 9, 2, 8, 3], QRELS) == pytest.approx((1 + 2 / 3 + 3 / 5) / 3)
    assert m.average_precision([1, 9, 2, 8, 3], QRELS, k=2) == pytest.approx(1 / 3)
    assert m.average_precision([9], {}) == 0.0


def test_dcg_and_ndcg_known_values() -> None:
    # Järvelin & Kekäläinen with gains 2^g - 1: grades 3,2,1 ideal.
    ideal = (2**3 - 1) / math.log2(2) + (2**2 - 1) / math.log2(3) + (2**1 - 1) / math.log2(4)
    assert m.dcg_at_k([1, 2, 3], QRELS, 10) == pytest.approx(ideal)
    assert m.ndcg_at_k([1, 2, 3], QRELS, 10) == pytest.approx(1.0)
    worst_order = m.ndcg_at_k([3, 2, 1], QRELS, 10)
    assert 0 < worst_order < 1
    assert m.ndcg_at_k([7, 8], QRELS, 10) == 0.0
    assert m.ndcg_at_k([1], {}, 10) == 0.0
    assert m.dcg_at_k([], QRELS, 10) == 0.0
    # Cut-off: only the first k positions count in both DCG and the ideal.
    assert m.ndcg_at_k([3, 1, 2], QRELS, 1) == pytest.approx((2**1 - 1) / (2**3 - 1))


@settings(max_examples=100, deadline=None)
@given(
    ranked=st.lists(st.integers(0, 15), unique=True, max_size=15),
    grades=st.dictionaries(st.integers(0, 15), st.sampled_from([0.0, 1.0, 2.0, 3.0]), max_size=10),
    k=st.integers(1, 15),
)
def test_metric_ranges(ranked: list[int], grades: dict[int, float], k: int) -> None:
    for fn in (m.precision_at_k, m.recall_at_k, m.ndcg_at_k, m.f1_at_k):
        value = fn(ranked, grades, k)
        assert 0.0 <= value <= 1.0 + 1e-9
    assert 0.0 <= m.average_precision(ranked, grades) <= 1.0 + 1e-9
    assert 0.0 <= m.reciprocal_rank(ranked, grades) <= 1.0


def test_perfect_ranking_maximises_everything() -> None:
    perfect = [1, 2, 3]
    scores = m.evaluate_query(perfect, QRELS)
    assert scores["nDCG@10"] == pytest.approx(1.0)
    assert scores["MAP"] == pytest.approx(1.0)
    assert scores["MRR"] == 1.0
    assert scores["R@10"] == 1.0


def test_binary_threshold_and_graded_split() -> None:
    ranked = [3, 2, 1]
    strict = m.evaluate_query(ranked, QRELS, binary_threshold=3.0)
    lenient = m.evaluate_query(ranked, QRELS, binary_threshold=1.0)
    assert strict["MRR"] == pytest.approx(1 / 3) and lenient["MRR"] == 1.0
    assert strict["nDCG@10"] == lenient["nDCG@10"]  # graded metric unaffected
    assert m.binarize(QRELS, 2.0) == {1: 3.0, 2: 2.0}


def test_bootstrap_summary_is_deterministic_and_bracketing() -> None:
    values = [0.2, 0.4, 0.6, 0.8, 1.0]
    first = m.bootstrap_summary(values, seed=1)
    second = m.bootstrap_summary(values, seed=1)
    assert first == second
    assert first.ci_low <= first.mean <= first.ci_high
    assert first.n == 5 and first.std > 0
    assert m.bootstrap_summary([]).n == 0
    assert m.bootstrap_summary([0.5]).std == 0.0
    assert first.to_dict()["ci95"][0] <= 0.6 <= first.to_dict()["ci95"][1]


def test_paired_bootstrap_pvalue() -> None:
    same = [0.5] * 20
    assert m.paired_bootstrap_pvalue(same, same) == 1.0
    better = [0.9 + 0.01 * (i % 3) for i in range(30)]
    worse = [0.1 + 0.01 * (i % 3) for i in range(30)]
    assert m.paired_bootstrap_pvalue(better, worse) < 0.01
    assert m.paired_bootstrap_pvalue([], []) == 1.0


def test_evaluate_run_aggregates() -> None:
    result = m.evaluate_run({"q1": [1, 2, 3], "q2": [9, 9, 9]}, {"q1": QRELS, "q2": QRELS}, seed=3)
    assert result["queries"] == 2
    assert result["per_query"]["q1"]["MRR"] == 1.0 and result["per_query"]["q2"]["MRR"] == 0.0
    assert result["aggregate"]["MRR"]["mean"] == pytest.approx(0.5)
    assert set(result["aggregate"]) == set(m.METRICS)
