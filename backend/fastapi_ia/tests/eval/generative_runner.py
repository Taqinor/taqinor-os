"""NTAI32 — runner d'evaluation OFFLINE des features IA generatives.

Extension de YHARD12 (``runner.py``, agent NL->SQL) aux familles generatives
resume / brouillon / extraction. MEME contrat que son aine :

  * AUCUN appel LLM, aucune cle, aucun reseau — mode "fixtures" par defaut ;
  * scoring DETERMINISTE par PROPRIETES (pas de comparaison de texte exact,
    qui serait ingerable sur une sortie generative) ;
  * ``run_generative_eval_or_raise(seuil)`` sert de porte CI.

Pour rejouer un VRAI modele plus tard : passer ``producer`` a
``score_generative_case`` (``producer(case) -> sortie``). Le reste du harnais
(proprietes, seuils, detection de cas negatifs) ne bouge pas. Ce mode reste
GATE OFF par defaut (``producer=None`` == on score la fixture du cas).

Note de composition : les motifs PII ci-dessous sont l'ASSERTION du harnais,
pas un masqueur. Quand la primitive de redaction de la fondation
(``core/ai/redaction.py``, NTAI3) sera posee, ``_contient_pii`` devra l'appeler
au lieu de ses regex locales — le reste du harnais est inchange.
"""
from __future__ import annotations

import re
from typing import Callable, Optional

from .generative_cases import (FAMILLES_REQUISES, GENERATIVE_CASES,
                               SEUIL_DEFAUT)

#: Motifs de PII marocaine en clair — une generation destinee a un tiers ne
#: doit JAMAIS en contenir.
PII_PATTERNS = {
    "cin": re.compile(r"\b[A-Z]{1,2}\d{5,6}\b"),
    "rib": re.compile(r"\b\d{16,24}\b"),
    "telephone": re.compile(r"\b(?:\+212|0)\s?[5-7](?:[\s.-]?\d{2}){4}\b"),
    "email": re.compile(r"\b[\w.+-]+@[\w-]+\.[A-Za-z]{2,}\b"),
    "cnss": re.compile(r"\bCNSS\s*:?\s*\d{6,}\b", re.IGNORECASE),
}


def _tables_interdites() -> set:
    """Noms de tables SQL bruts, repris du service NL->SQL quand il est
    importable (source de verite unique), sinon un socle minimal fige.

    Le harnais generatif doit tourner MEME sans les dependances lourdes de
    ``sql_agent_service`` (langchain…) : il ne teste pas ce service.
    """
    try:  # pragma: no cover - depend de l'environnement
        from app.services import sql_agent_service as svc
        return {str(t).lower() for t in svc._ALLOWED_TABLES}
    except Exception:  # noqa: BLE001 - degradation volontaire
        # Sous-ensemble FIGE de l'allowlist reelle (assez pour que le harnais
        # garde ses dents sans les dependances lourdes du service).
        return {"crm_client", "ventes_devis", "ventes_facture",
                "stock_produit", "sav_ticket"}


def _contient_pii(texte: str) -> list:
    """Types de PII detectes en clair dans ``texte`` (liste triee, vide = OK)."""
    trouves = {
        nom for nom, motif in PII_PATTERNS.items() if motif.search(texte or "")
    }
    return sorted(trouves)


def _noms_de_tables_cites(texte: str) -> list:
    lowered = (texte or "").lower()
    return sorted(t for t in _tables_interdites() if t in lowered)


def _verifier_texte(case: dict, sortie) -> list:
    """Proprietes d'une sortie TEXTUELLE (resume / brouillon)."""
    echecs = []
    texte = sortie if isinstance(sortie, str) else str(sortie)

    if case.get("non_vide") and not texte.strip():
        echecs.append("sortie vide")

    plafond = case.get("max_chars")
    if plafond and len(texte) > plafond:
        echecs.append(f"sortie trop longue ({len(texte)} > {plafond})")

    if case.get("sans_pii"):
        pii = _contient_pii(texte)
        if pii:
            echecs.append(f"PII en clair : {pii}")

    if case.get("sans_nom_de_table"):
        tables = _noms_de_tables_cites(texte)
        if tables:
            echecs.append(f"nom(s) de table SQL cite(s) : {tables}")

    for jalon in case.get("doit_contenir") or []:
        if jalon.lower() not in texte.lower():
            echecs.append(f"jalon factuel absent : {jalon!r}")

    for interdit in case.get("ne_doit_pas_contenir") or []:
        if interdit.lower() in texte.lower():
            echecs.append(f"formule interdite presente : {interdit!r}")

    return echecs


def _verifier_extraction(case: dict, sortie) -> list:
    """Proprietes d'une sortie STRUCTUREE (extraction documentaire)."""
    echecs = []
    if not isinstance(sortie, dict):
        return ["sortie d'extraction non structuree (dict attendu)"]

    attendues = case.get("schema_cles")
    if attendues is not None:
        attendues = set(attendues)
        obtenues = set(sortie)
        manquantes = attendues - obtenues
        inventees = obtenues - attendues
        if manquantes:
            echecs.append(f"cles manquantes : {sorted(manquantes)}")
        if inventees:
            echecs.append(f"cles hors schema (hallucination) : "
                          f"{sorted(inventees)}")

    if case.get("valeurs_str"):
        mauvaises = sorted(
            cle for cle, valeur in sortie.items() if not isinstance(valeur, str))
        if mauvaises:
            echecs.append(f"valeurs non-chaines : {mauvaises}")

    if case.get("sans_pii"):
        pii = _contient_pii(" ".join(str(v) for v in sortie.values()))
        if pii:
            echecs.append(f"PII en clair : {pii}")

    return echecs


def score_generative_case(case: dict,
                          producer: Optional[Callable[[dict], object]] = None
                          ) -> dict:
    """Score UN cas generatif. ``producer(case) -> sortie`` optionnel (mode
    rejouable) ; par defaut on score ``case['sortie']`` (zero appel reseau).

    Pour un cas ``attendu_en_echec``, ``passed`` signifie « le harnais a
    correctement REFUSE cette sortie » — jamais « la sortie est bonne ».
    """
    sortie = producer(case) if producer else case.get("sortie")

    if case.get("feature") == "extraction":
        echecs = _verifier_extraction(case, sortie)
    else:
        echecs = _verifier_texte(case, sortie)

    attendu_en_echec = bool(case.get("attendu_en_echec"))
    if attendu_en_echec:
        return {
            "id": case["id"],
            "feature": case.get("feature", ""),
            "passed": bool(echecs),
            "reason": ("" if echecs else
                       "Cas negatif attendu mais aucune propriete violee "
                       "(le harnais est trop laxiste)."),
        }
    return {
        "id": case["id"],
        "feature": case.get("feature", ""),
        "passed": not echecs,
        "reason": "; ".join(echecs),
    }


def familles_couvertes(cases=None) -> set:
    """Familles generatives presentes dans le jeu de cas."""
    return {c.get("feature", "") for c in (cases or GENERATIVE_CASES)}


def run_generative_eval(producer=None, cases=None) -> dict:
    """Score tout le jeu de cas generatif.

    Renvoie ``{"score", "results", "total", "passed", "familles"}``. Leve
    ``AssertionError`` si une famille requise (resume/brouillon/extraction) a
    disparu du jeu de cas — un score de 100% sur un jeu ampute ne vaut rien.
    """
    cases = list(cases or GENERATIVE_CASES)
    couvertes = familles_couvertes(cases)
    manquantes = set(FAMILLES_REQUISES) - couvertes
    if manquantes:
        raise AssertionError(
            f"Familles generatives non couvertes : {sorted(manquantes)}")

    results = [score_generative_case(c, producer=producer) for c in cases]
    total = len(results)
    passed = sum(1 for r in results if r["passed"])
    return {
        "score": (passed / total) if total else 0.0,
        "results": results,
        "total": total,
        "passed": passed,
        "familles": sorted(couvertes),
    }


def run_generative_eval_or_raise(threshold: float = SEUIL_DEFAUT,
                                 producer=None, cases=None) -> dict:
    """Leve ``AssertionError`` sous ``threshold`` — porte CI/locale."""
    report = run_generative_eval(producer=producer, cases=cases)
    if report["score"] < threshold:
        failing = [r for r in report["results"] if not r["passed"]]
        detail = "; ".join(f"{r['id']}: {r['reason']}" for r in failing)
        raise AssertionError(
            f"Score eval generatif {report['score']:.2%} < seuil "
            f"{threshold:.2%}. Cas en echec: {detail}")
    return report
