"""Auftragsrechnungen suchen parallel und fallen bei einem Absturz zurück."""

import pytest

from sp5generator.jobs import _retry_single_worker
from sp5generator.solver import SEARCH_WORKERS, parallel_workers, solve
from test_core_rules import case, shift


def test_library_default_stays_reproducible():
    # Aufrufe aus Tests und Kommandozeile bleiben einspurig und damit
    # wiederholbar; nur der Auftragsprozess rechnet parallel.
    assert SEARCH_WORKERS == 1
    assert solve(case(), time_limit=5).parameters["workers"] == 1


@pytest.mark.parametrize("workers", [1, 2, 4])
def test_the_chosen_number_is_used_and_reported(workers):
    snapshot = case(n=3, shifts=[shift("mon", 5, 8, 8), shift("tue", 6, 8, 8)])

    result = solve(snapshot, time_limit=5, workers=workers)

    assert result.parameters["workers"] == workers
    assert result.validation.valid and result.validation.complete


def test_a_nonsense_number_never_disables_the_search():
    assert solve(case(), time_limit=5, workers=0).parameters["workers"] == 1
    assert solve(case(), time_limit=5, workers=-3).parameters["workers"] == 1


def test_the_job_process_asks_for_more_than_one_search():
    assert parallel_workers() >= 1
    assert parallel_workers() <= 8


def test_only_a_crashed_first_attempt_is_repeated():
    # Abgestürzt: der Auftrag steht noch auf laufend, obwohl das Kind endete.
    assert _retry_single_worker("running", 0, stopping=False) is True
    # Fertig, abgebrochen oder fehlgeschlagen: nichts zu wiederholen.
    for state in ("succeeded", "cancelled", "failed"):
        assert _retry_single_worker(state, 0, stopping=False) is False
    # Ein zweiter Absturz gilt als Fehlschlag.
    assert _retry_single_worker("running", 1, stopping=False) is False
    # Beim Herunterfahren wird nicht neu begonnen.
    assert _retry_single_worker("running", 0, stopping=True) is False
