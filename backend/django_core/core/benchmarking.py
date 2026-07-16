"""SCA48 — Plancher légal de k-anonymat pour tout agrégat inter-tenants.

Couche de FONDATION (``core`` ne connaît aucun module métier — contrat
import-linter ``core-foundation-is-a-base-layer``). Le brief légal est net :
jamais publier un agrégat calculable sur un groupe trop petit pour empêcher
la ré-identification d'une société membre. Encoder le plancher maintenant
coûte une constante ; l'ajouter APRÈS qu'un produit de benchmarking soit déjà
livré serait un incident (donnée nominative fuitée via un agrégat trop fin).

Toute agrégation inter-tenants — dont NTDATA46 (collecte, ``AgregatBenchmark``)
et NTDATA47 (restitution comparative, endpoint ``semantic/benchmarks/``) —
DOIT importer et respecter ce plancher : une strate (secteur/métrique/période…)
dont l'effectif de sociétés contributrices est strictement inférieur à
``BENCHMARK_MIN_COMPANIES`` ne doit JAMAIS être publiée ni exposée, même
anonymisée.
"""
from __future__ import annotations

# Plancher k-anonymat : nombre MINIMUM de sociétés distinctes qu'une strate
# doit compter pour être publiable. En dessous, une valeur d'agrégat (médiane,
# quartile…) pourrait être rétro-déduite jusqu'à identifier une société
# précise dans un petit groupe — jamais acceptable, même en anonymisé.
BENCHMARK_MIN_COMPANIES = 5


def strate_publiable(nb_companies):
    """Vrai si une strate d'agrégat inter-tenants compte assez de sociétés
    distinctes (``nb_companies``) pour être publiée sans risque de
    ré-identification — c.-à-d. ``nb_companies >= BENCHMARK_MIN_COMPANIES``.

    Aide légère pour les appelants (NTDATA46/47) : centralise la comparaison
    plutôt que de la répéter en dur à chaque site d'appel."""
    return nb_companies >= BENCHMARK_MIN_COMPANIES
