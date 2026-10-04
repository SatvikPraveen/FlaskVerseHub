import json
from pathlib import Path

import pytest

from experiments import run_retrieval_benchmark as bench
from experiments.corpus import HIGH_GRADE, LOW_GRADE, generate_corpus

pytestmark = pytest.mark.research


def test_corpus_is_deterministic_and_consistent() -> None:
    a = generate_corpus(num_docs=80, num_topics=4, seed=3)
    b = generate_corpus(num_docs=80, num_topics=4, seed=3)
    assert [d.fields for d in a.documents] == [d.fields for d in b.documents]
    assert a.queries == b.queries and a.qrels == b.qrels
    assert a.size == 80 and a.queries
    for query_id, qrels in a.qrels.items():
        assert query_id in a.queries
        grades = set(qrels.values())
        assert grades <= {HIGH_GRADE, LOW_GRADE} and HIGH_GRADE in grades
        topic = int(query_id[1:3])
        for doc_id, grade in qrels.items():
            meta = a.documents[doc_id].metadata
            assert meta["topic"] == topic
            assert (grade == HIGH_GRADE) == (meta["subtopic"] == int(query_id[4]))
    assert all(count > 0 for count in a.relevant_counts().values())


def test_different_seeds_differ() -> None:
    assert (
        generate_corpus(num_docs=30, num_topics=3, seed=1).queries
        != generate_corpus(num_docs=30, num_topics=3, seed=2).queries
    )


def test_load_config_merges_overrides(tmp_path: Path) -> None:
    config_path = tmp_path / "c.yaml"
    config_path.write_text(
        "seed: 9\ncorpus: {num_docs: 50}\nrankers:\n  only: {name: bm25, params: {}}\n"
    )
    config = bench.load_config(config_path)
    assert config["seed"] == 9
    assert config["corpus"]["num_docs"] == 50 and config["corpus"]["num_topics"] == 12  # merged
    assert list(config["rankers"]) == ["only"]  # replaced
    assert bench.load_config(None)["seed"] == 42


def test_end_to_end_quick_benchmark(tmp_path: Path) -> None:
    exit_code = bench.main(
        ["--config", "experiments/configs/quick.yaml", "--out", str(tmp_path), "--no-plot"]
    )
    assert exit_code == 0
    results = json.loads((tmp_path / "results.json").read_text())
    assert results["meta"]["seed"] == 7
    systems = results["systems"]
    assert len(systems) == 2
    for system in systems.values():
        ndcg = system["aggregate"]["nDCG@10"]
        assert 0 <= ndcg["ci95"][0] <= ndcg["mean"] <= ndcg["ci95"][1] <= 1
        assert 0 <= system["p_value_vs_baseline[nDCG@10]"] <= 1
    report = (tmp_path / "REPORT.md").read_text()
    assert "| System |" in report and "bm25(k1=1.5,b=0.75)" in report
    # Reproducibility: a second run yields identical aggregates.
    again = bench.run(bench.load_config(Path("experiments/configs/quick.yaml")))
    assert again["systems"].keys() == systems.keys()
    for label, system in systems.items():
        assert again["systems"][label]["aggregate"] == system["aggregate"]


def test_plot_writes_png(tmp_path: Path) -> None:
    pytest.importorskip("matplotlib")
    results = bench.run(bench.load_config(Path("experiments/configs/quick.yaml")))
    target = tmp_path / "ndcg.png"
    assert bench.plot(results, target) is True
    assert target.stat().st_size > 1000


def test_stemming_improves_effectiveness_on_inflected_corpus() -> None:
    """Sanity check of the experimental design: morphology makes stemming measurable."""
    config = bench.load_config(Path("experiments/configs/quick.yaml"))
    config["analyzers"] = {"porter": {"stem": True}, "nostem": {"stem": False}}
    config["corpus"]["inflection_rate"] = 0.6
    results = bench.run(config)
    stem = results["systems"]["bm25(k1=1.5,b=0.75) | porter"]["aggregate"]["nDCG@10"]["mean"]
    nostem = results["systems"]["bm25(k1=1.5,b=0.75) | nostem"]["aggregate"]["nDCG@10"]["mean"]
    assert stem > nostem
