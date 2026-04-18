"""Tests du raffinement Ollama (mocks HTTP, pas de service requis)."""

from unittest.mock import patch

import pandas as pd
import pytest

from abritel.ollama_categorisation import (
    appliquer_categorisation_ollama,
    categoriser_texte_ollama,
    ollama_actif,
)


def test_ollama_actif_false_when_service_down(monkeypatch: pytest.MonkeyPatch) -> None:
    """Sans service Ollama accessible, ollama_actif() retourne False sans erreur."""
    monkeypatch.delenv("ABRITEL_OLLAMA", raising=False)
    monkeypatch.delenv("CI", raising=False)
    monkeypatch.delenv("GITHUB_ACTIONS", raising=False)
    with patch("abritel.ollama_categorisation.requests.get", side_effect=ConnectionError()):
        assert ollama_actif() is False


def test_ollama_actif_true_when_service_up(monkeypatch: pytest.MonkeyPatch) -> None:
    """Si Ollama répond, ollama_actif() retourne True sans variable d'environnement."""
    monkeypatch.delenv("ABRITEL_OLLAMA", raising=False)
    monkeypatch.delenv("CI", raising=False)
    monkeypatch.delenv("GITHUB_ACTIONS", raising=False)

    class FakeResp:
        status_code = 200

    with patch("abritel.ollama_categorisation.requests.get", return_value=FakeResp()):
        assert ollama_actif() is True


def test_ollama_actif_forced_off_with_env(monkeypatch: pytest.MonkeyPatch) -> None:
    """ABRITEL_OLLAMA=0 désactive Ollama même si le service tourne."""
    monkeypatch.setenv("ABRITEL_OLLAMA", "0")
    monkeypatch.delenv("CI", raising=False)
    monkeypatch.delenv("GITHUB_ACTIONS", raising=False)
    # opt-out avant le ping HTTP — pas besoin de mocker requests.get
    assert ollama_actif() is False


def test_ollama_actif_forced_off_in_ci(monkeypatch: pytest.MonkeyPatch) -> None:
    """En CI, Ollama est toujours désactivé (pas de service sur les runners GitHub)."""
    monkeypatch.delenv("ABRITEL_OLLAMA", raising=False)
    monkeypatch.setenv("CI", "true")
    # CI check avant le ping HTTP — pas besoin de mocker requests.get
    assert ollama_actif() is False


def test_categoriser_texte_ollama_parse_json(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("ABRITEL_OLLAMA_MODEL", "dummy")

    def fake_post(url: str, json: dict, timeout: float):  # noqa: ARG001
        class R:
            def raise_for_status(self) -> None:
                return None

            def json(self) -> dict:
                return {
                    "message": {
                        "content": '{"categorie": "Financier"}',
                    }
                }

        return R()

    with patch("abritel.ollama_categorisation.requests.post", fake_post):
        assert (
            categoriser_texte_ollama("arnaque tarif caché", note=1, cat_mots_cles="Autre")
            == "Financier"
        )


def test_categoriser_texte_ollama_prompt_includes_note_and_hint(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Le prompt envoyé à Ollama contient la note et la catégorie mots-clés."""
    monkeypatch.setenv("ABRITEL_OLLAMA_MODEL", "dummy")
    captured: dict = {}

    def fake_post(url: str, json: dict, timeout: float):  # noqa: ARG001
        captured["payload"] = json

        class R:
            def raise_for_status(self) -> None:
                return None

            def json(self) -> dict:
                return {"message": {"content": '{"categorie": "Financier"}'}}

        return R()

    with patch("abritel.ollama_categorisation.requests.post", fake_post):
        categoriser_texte_ollama("remboursement refusé", note=2, cat_mots_cles="Financier")

    user_msg = captured["payload"]["messages"][1]["content"]
    assert "2/5" in user_msg  # note présente
    assert "Financier" in user_msg  # hint mots-clés présent
    # Température 0 pour déterminisme
    assert captured["payload"]["options"]["temperature"] == 0


def test_categoriser_texte_ollama_reject_unknown(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("ABRITEL_OLLAMA_MODEL", "dummy")

    def fake_post(url: str, json: dict, timeout: float):  # noqa: ARG001
        class R:
            def raise_for_status(self) -> None:
                return None

            def json(self) -> dict:
                return {"message": {"content": '{"categorie": "Paiement"}'}}

        return R()

    with patch("abritel.ollama_categorisation.requests.post", fake_post):
        assert categoriser_texte_ollama("test") is None


def test_categoriser_texte_ollama_retry_on_invalid(monkeypatch: pytest.MonkeyPatch) -> None:
    """Ollama est relancé jusqu'à _OLLAMA_MAX_RETRIES fois si la réponse est invalide."""
    monkeypatch.setenv("ABRITEL_OLLAMA_MODEL", "dummy")
    call_count = 0

    def fake_post(url: str, json: dict, timeout: float):  # noqa: ARG001
        nonlocal call_count
        call_count += 1

        class R:
            def raise_for_status(self) -> None:
                return None

            def json(self) -> dict:
                if call_count < 3:
                    return {"message": {"content": '{"categorie": "Invalide"}'}}
                return {"message": {"content": '{"categorie": "Service Client"}'}}

        return R()

    with patch("abritel.ollama_categorisation.requests.post", fake_post):
        with patch("abritel.ollama_categorisation.time.sleep"):  # no real sleep in tests
            result = categoriser_texte_ollama("le SAV ne répond pas")

    assert result == "Service Client"
    assert call_count == 3


def test_appliquer_mode_autre_only(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("ABRITEL_OLLAMA_MODE", "autre")

    with patch(
        "abritel.ollama_categorisation.categoriser_texte_ollama",
        return_value="Financier",
    ) as mock_llm:
        df = pd.DataFrame(
            {
                "texte": ["x", "y"],
                "note": [1, 5],
                "Catégorie": ["Autre", "Bug Technique"],
                "Catégorie_secondaire": ["", ""],
                "Gravité": ["Haute", "Basse"],
            }
        )
        out = appliquer_categorisation_ollama(df)

    assert mock_llm.call_count == 1
    assert out.loc[0, "Catégorie"] == "Financier"
    assert out.loc[0, "Catégorie_mots_cles"] == "Autre"
    assert out.loc[1, "Catégorie"] == "Bug Technique"


def test_appliquer_mode_all_processes_all_rows(monkeypatch: pytest.MonkeyPatch) -> None:
    """Mode 'all' (défaut) : tous les avis passent par Ollama, pas seulement 'Autre'."""
    monkeypatch.setenv("ABRITEL_OLLAMA_MODE", "all")

    with patch(
        "abritel.ollama_categorisation.categoriser_texte_ollama",
        return_value="Service Client",
    ) as mock_llm:
        df = pd.DataFrame(
            {
                "texte": ["x", "y", "z"],
                "note": [1, 5, 3],
                "Catégorie": ["Autre", "Bug Technique", "Financier"],
                "Catégorie_secondaire": ["", "", ""],
                "Gravité": ["Haute", "Basse", "Basse"],
            }
        )
        appliquer_categorisation_ollama(df)

    assert mock_llm.call_count == 3  # tous les avis traités


def test_appliquer_cache_incremental_skips_cached_rows(monkeypatch: pytest.MonkeyPatch) -> None:
    """Les avis avec une Catégorie_ollama valide ne repassent pas par le LLM."""
    monkeypatch.setenv("ABRITEL_OLLAMA_MODE", "all")

    with patch(
        "abritel.ollama_categorisation.categoriser_texte_ollama",
        return_value="Financier",
    ) as mock_llm:
        df = pd.DataFrame(
            {
                "texte": ["avis ancien", "avis nouveau"],
                "note": [1, 2],
                "Catégorie": ["Autre", "Autre"],
                "Catégorie_secondaire": ["", ""],
                "Gravité": ["Haute", "Haute"],
                # Ligne 0 : cache valide depuis un run précédent
                "Catégorie_ollama": ["Service Client", ""],
            }
        )
        out = appliquer_categorisation_ollama(df, force_rerun=False)

    # Seule la ligne 1 (sans cache) a été envoyée à Ollama
    assert mock_llm.call_count == 1
    # Ligne 0 : catégorie restaurée depuis le cache
    assert out.loc[0, "Catégorie"] == "Service Client"
    # Ligne 1 : traitée par Ollama
    assert out.loc[1, "Catégorie"] == "Financier"


def test_appliquer_force_rerun_ignores_cache(monkeypatch: pytest.MonkeyPatch) -> None:
    """force_rerun=True relance Ollama sur tous les avis, même ceux avec cache."""
    monkeypatch.setenv("ABRITEL_OLLAMA_MODE", "all")

    with patch(
        "abritel.ollama_categorisation.categoriser_texte_ollama",
        return_value="Financier",
    ) as mock_llm:
        df = pd.DataFrame(
            {
                "texte": ["avis avec cache", "avis sans cache"],
                "note": [1, 2],
                "Catégorie": ["Autre", "Autre"],
                "Catégorie_secondaire": ["", ""],
                "Gravité": ["Haute", "Haute"],
                "Catégorie_ollama": ["Service Client", ""],
            }
        )
        out = appliquer_categorisation_ollama(df, force_rerun=True)

    # Les 2 lignes ont été retraitées
    assert mock_llm.call_count == 2
    assert out.loc[0, "Catégorie"] == "Financier"
    assert out.loc[1, "Catégorie"] == "Financier"


def test_appliquer_mode_autre_parallel_error_handling(monkeypatch: pytest.MonkeyPatch) -> None:
    """Les erreurs dans les workers parallèles sont absorbées sans planter le pipeline."""
    monkeypatch.setenv("ABRITEL_OLLAMA_MODE", "autre")

    call_count = 0

    def flaky_llm(texte: str, *, note: int = 0, cat_mots_cles: str = "Autre") -> str | None:  # noqa: ARG001
        nonlocal call_count
        call_count += 1
        if call_count == 1:
            raise RuntimeError("timeout simulé")
        return "Financier"

    with patch("abritel.ollama_categorisation.categoriser_texte_ollama", flaky_llm):
        df = pd.DataFrame(
            {
                "texte": ["x", "y"],
                "note": [1, 1],
                "Catégorie": ["Autre", "Autre"],
                "Catégorie_secondaire": ["", ""],
                "Gravité": ["Haute", "Haute"],
            }
        )
        out = appliquer_categorisation_ollama(df)

    # L'appel flaky a échoué (absorbé), l'autre a retourné Financier
    cats = set(out["Catégorie"].tolist())
    assert "Financier" in cats or "Autre" in cats  # aucun crash


def test_appliquer_on_progress_callback(monkeypatch: pytest.MonkeyPatch) -> None:
    """on_progress est appelé pendant le traitement pour permettre la sauvegarde progressive."""
    monkeypatch.setenv("ABRITEL_OLLAMA_MODE", "all")
    progress_calls: list[tuple[int, int]] = []

    def track_progress(df: pd.DataFrame, done: int, total: int) -> None:
        progress_calls.append((done, total))

    with patch(
        "abritel.ollama_categorisation.categoriser_texte_ollama",
        return_value="Financier",
    ):
        with patch("abritel.ollama_categorisation._CHECKPOINT_BATCH_SIZE", 2):
            df = pd.DataFrame(
                {
                    "texte": ["a", "b", "c"],
                    "note": [1, 2, 3],
                    "Catégorie": ["Autre", "Autre", "Autre"],
                    "Catégorie_secondaire": ["", "", ""],
                    "Gravité": ["Haute", "Haute", "Basse"],
                }
            )
            appliquer_categorisation_ollama(df, on_progress=track_progress)

    # batch_size=2, 3 avis → callback à 2 (batch) + 3 (final)
    assert len(progress_calls) == 2
    assert progress_calls[-1][0] == 3  # dernier appel = total traité
    assert progress_calls[-1][1] == 3  # total attendu


def test_categoriser_texte_ollama_markdown_json(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("ABRITEL_OLLAMA_MODEL", "dummy")

    def fake_post(url: str, json: dict, timeout: float):  # noqa: ARG001
        class R:
            def raise_for_status(self) -> None:
                return None

            def json(self) -> dict:
                return {
                    "message": {
                        "content": '```json\n{"categorie": "Service Client"}\n```',
                    }
                }

        return R()

    with patch("abritel.ollama_categorisation.requests.post", fake_post):
        assert categoriser_texte_ollama("le SAV ne répond pas") == "Service Client"
