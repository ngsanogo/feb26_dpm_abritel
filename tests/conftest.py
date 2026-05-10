"""Fixtures globales pour la suite de tests."""

import pytest


@pytest.fixture(autouse=True)
def _disable_ollama_in_tests(monkeypatch: pytest.MonkeyPatch) -> None:
    """Désactive Ollama dans tous les tests.

    Les tests rapides ne doivent jamais toucher un service externe (réseau, LLM).
    Les tests Ollama dédiés mockent eux-mêmes ``ollama_actif`` et les appels HTTP.
    """
    monkeypatch.setenv("ABRITEL_OLLAMA", "0")
