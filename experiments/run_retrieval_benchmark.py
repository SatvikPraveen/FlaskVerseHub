"""Benchmark ranking functions on a reproducible synthetic corpus.

Usage::

    python -m experiments.run_retrieval_benchmark --config experiments/configs/default.yaml

Outputs (under ``--out``): ``results.json`` (full per-query + aggregate
metrics with bootstrap CIs and paired significance tests), ``REPORT.md``
(human-readable table) and ``ndcg.png`` (bar chart, when matplotlib is
available).
"""

from __future__ import annotations

import argparse
import json
import platform
import sys
import time
from pathlib import Path
from typing import Any

import yaml

from app.search.analysis import Analyzer
from app.search.engine import SearchEngine
from app.search.metrics import METRICS, evaluate_run, paired_bootstrap_pvalue
from experiments.corpus import generate_corpus

DEFAULT_CONFIG: dict[str, Any] = {
    "seed": 42,
    "corpus": {
        "num_docs": 600,
        "num_topics": 12,
        "subtopics_per_topic": 4,
        "queries_per_subtopic": 2,
    },
    "analyzers": {
        "porter+stop": {"stem": True},
        "nostem": {"stem": False},
    },
    "rankers": {
        "bm25(k1=1.2,b=0.75)": {"name": "bm25", "params": {"k1": 1.2, "b": 0.75}},
        "bm25(k1=1.5,b=0.75)": {"name": "bm25", "params": {"k1": 1.5, "b": 0.75}},
        "bm25(k1=1.5,b=0.0)": {"name": "bm25", "params": {"k1": 1.5, "b": 0.0}},
        "bm25+(delta=1)": {"name": "bm25plus", "params": {"k1": 1.5, "b": 0.75, "delta": 1.0}},
        "tfidf(lnc.ltc)": {"name": "tfidf", "params": {}},
    },
    "field_boosts": {"title": 3.0, "content": 1.0},
    "baseline": "bm25(k1=1.5,b=0.75)",
    "primary_metric": "nDCG@10",
    "binary_threshold": 3.0,
    "k": 10,
}


def load_config(path: Path | None) -> dict[str, Any]:
    config = json.loads(json.dumps(DEFAULT_CONFIG))
    if path is not None:
        with path.open() as handle:
            user = yaml.safe_load(handle) or {}
        for key, value in user.items():
            if (
                isinstance(value, dict)
                and isinstance(config.get(key), dict)
                and key not in {"rankers", "analyzers"}
            ):
                config[key].update(value)
            else:
                config[key] = value
    return config


def run(config: dict[str, Any]) -> dict[str, Any]:
    seed = int(config["seed"])
    corpus = generate_corpus(seed=seed, **config["corpus"])
    runs: dict[str, dict[str, Any]] = {}
    timings: dict[str, float] = {}
    for analyzer_name, analyzer_kwargs in config["analyzers"].items():
        analyzer = Analyzer(**analyzer_kwargs)
        for ranker_label, spec in config["rankers"].items():
            label = f"{ranker_label} | {analyzer_name}"
            started = time.perf_counter()
            engine = SearchEngine(
                corpus.documents,
                analyzer=analyzer,
                ranker=spec["name"],
                ranker_params=spec.get("params", {}),
                field_boosts=config["field_boosts"],
            )
            rankings = {
                query_id: engine.ranked_ids(query, k=int(config["k"]) * 10)
                for query_id, query in corpus.queries.items()
            }
            timings[label] = round((time.perf_counter() - started) * 1000, 1)
            runs[label] = evaluate_run(
                rankings,
                corpus.qrels,
                metrics=METRICS,
                seed=seed,
                binary_threshold=float(config.get("binary_threshold", 1.0)),
            )

    primary = config["primary_metric"]
    baseline_label = next(
        (
            label
            for label in runs
            if label.startswith(config["baseline"])
            and label.endswith(next(iter(config["analyzers"])))
        ),
        next(iter(runs)),
    )
    baseline_scores = [runs[baseline_label]["per_query"][q][primary] for q in corpus.qrels]
    significance: dict[str, float] = {}
    for label, result in runs.items():
        scores = [result["per_query"][q][primary] for q in corpus.qrels]
        significance[label] = paired_bootstrap_pvalue(scores, baseline_scores, seed=seed)

    return {
        "meta": {
            "generated_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            "python": platform.python_version(),
            "seed": seed,
            "corpus": {
                "documents": corpus.size,
                "queries": len(corpus.queries),
                "mean_relevant_per_query": round(
                    sum(corpus.relevant_counts().values()) / max(1, len(corpus.qrels)), 1
                ),
                **config["corpus"],
            },
            "field_boosts": config["field_boosts"],
            "baseline": baseline_label,
            "primary_metric": primary,
            "binary_threshold": config.get("binary_threshold", 1.0),
        },
        "systems": {
            label: {
                "aggregate": result["aggregate"],
                "index_and_query_ms": timings[label],
                f"p_value_vs_baseline[{primary}]": significance[label],
            }
            for label, result in runs.items()
        },
        "per_query": {label: result["per_query"] for label, result in runs.items()},
    }


def render_report(results: dict[str, Any]) -> str:
    meta = results["meta"]
    metrics = list(next(iter(results["systems"].values()))["aggregate"])
    lines = [
        "# Retrieval benchmark report",
        "",
        f"Generated {meta['generated_at']} on Python {meta['python']} with seed `{meta['seed']}`.",
        f"Corpus: {meta['corpus']['documents']} synthetic documents, {meta['corpus']['queries']} queries, "
        f"{meta['corpus']['num_topics']} topics. Field boosts: `{meta['field_boosts']}`.",
        f"Baseline for significance tests: **{meta['baseline']}** on **{meta['primary_metric']}** "
        "(two-sided paired bootstrap, 5000 resamples). Binary metrics count a document as relevant when "
        f"its grade is at least {meta['binary_threshold']}; nDCG uses the full graded judgements.",
        "",
        "| System | " + " | ".join(metrics) + " | p-value | time (ms) |",
        "|---|" + "---|" * (len(metrics) + 2),
    ]
    primary = meta["primary_metric"]
    ordered = sorted(
        results["systems"].items(), key=lambda kv: kv[1]["aggregate"][primary]["mean"], reverse=True
    )
    for label, system in ordered:
        cells = []
        for metric in metrics:
            agg = system["aggregate"][metric]
            cells.append(f"{agg['mean']:.3f} [{agg['ci95'][0]:.3f}, {agg['ci95'][1]:.3f}]")
        p_value = system[f"p_value_vs_baseline[{primary}]"]
        marker = "**" if p_value < 0.05 and label != meta["baseline"] else ""
        lines.append(
            f"| {label} | "
            + " | ".join(cells)
            + f" | {marker}{p_value:.3f}{marker} | {system['index_and_query_ms']} |"
        )
    lines += [
        "",
        "Values are means over queries with 95% percentile-bootstrap confidence intervals.",
        "Bold p-values mark systems that differ significantly (p < 0.05) from the baseline.",
    ]
    return "\n".join(lines) + "\n"


def plot(results: dict[str, Any], path: Path) -> bool:
    try:
        import matplotlib

        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
    except ImportError:  # pragma: no cover
        return False
    primary = results["meta"]["primary_metric"]
    systems = sorted(results["systems"].items(), key=lambda kv: kv[1]["aggregate"][primary]["mean"])
    labels = [label for label, _ in systems]
    means = [s["aggregate"][primary]["mean"] for _, s in systems]
    lows = [
        m - s["aggregate"][primary]["ci95"][0] for m, (_, s) in zip(means, systems, strict=True)
    ]
    highs = [
        s["aggregate"][primary]["ci95"][1] - m for m, (_, s) in zip(means, systems, strict=True)
    ]
    fig, ax = plt.subplots(figsize=(9, 0.45 * len(labels) + 1.5))
    ax.barh(labels, means, xerr=[lows, highs], color="#4C72B0", capsize=3)
    ax.set_xlabel(primary)
    ax.set_xlim(0, 1)
    ax.set_title(f"{primary} by system (95% bootstrap CI)")
    fig.tight_layout()
    fig.savefig(path, dpi=150)
    plt.close(fig)
    return True


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument(
        "--config", type=Path, default=None, help="YAML config overriding defaults."
    )
    parser.add_argument(
        "--out", type=Path, default=Path("experiments/results"), help="Output directory."
    )
    parser.add_argument("--seed", type=int, default=None, help="Override the config seed.")
    parser.add_argument("--no-plot", action="store_true")
    args = parser.parse_args(argv)

    config = load_config(args.config)
    if args.seed is not None:
        config["seed"] = args.seed
    results = run(config)
    args.out.mkdir(parents=True, exist_ok=True)
    (args.out / "results.json").write_text(json.dumps(results, indent=2) + "\n")
    (args.out / "REPORT.md").write_text(render_report(results))
    if not args.no_plot:
        plot(results, args.out / "ndcg.png")
    print(render_report(results))
    print(f"Wrote {args.out / 'results.json'} and {args.out / 'REPORT.md'}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
