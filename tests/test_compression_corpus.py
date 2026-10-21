from scripts.benchmark_compression import evaluate_corpus, load_corpus


def test_compression_corpus_preserves_required_error_facts():
    report = evaluate_corpus(load_corpus())
    assert report["preserved_all"], [
        (result["name"], result["missing_markers"])
        for result in report["results"]
        if not result["preserved"]
    ]


def test_compression_corpus_redacts_secrets():
    report = evaluate_corpus(load_corpus())
    assert report["no_secret_leaks"]


def test_compression_corpus_reaches_90_percent_aggregate_token_proxy_reduction():
    report = evaluate_corpus(load_corpus())
    assert report["aggregate_reduction"] >= 0.90


def test_compression_corpus_reports_character_reduction_separately():
    report = evaluate_corpus(load_corpus())
    assert report["original_chars"] > report["compressed_chars"]
    assert report["aggregate_character_reduction"] >= 0.90
