"""Smoke test Ollama depuis Docker : le moteur tourne sur le Mac, pas dans le conteneur.

Utilisé par ``scripts/ci_docker.sh --ollama``. Variables :
``ABRITEL_OLLAMA_URL`` (défaut http://host.docker.internal:11434),
``ABRITEL_OLLAMA_MODEL`` (défaut gemma4:31b),
``ABRITEL_OLLAMA_TIMEOUT`` (secondes, défaut 300).
"""

from __future__ import annotations

import os
import sys

from abritel.ollama_categorisation import categoriser_texte_ollama


def main() -> int:
    url = os.environ.get("ABRITEL_OLLAMA_URL", "http://host.docker.internal:11434")
    model = os.environ.get("ABRITEL_OLLAMA_MODEL", "gemma4:31b")
    timeout = float(os.environ.get("ABRITEL_OLLAMA_TIMEOUT", "300"))

    texte = "Frais cachés et remboursement refusé pour ma réservation Abritel."
    cat = categoriser_texte_ollama(texte, base_url=url, model=model, timeout_s=timeout)
    print(f"Ollama smoke (model={model!r}) → catégorie: {cat!r}")
    if cat is None:
        print("Échec : réponse vide ou catégorie invalide.", file=sys.stderr)
        return 1
    print("Ollama smoke : OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
