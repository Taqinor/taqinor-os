"""XCTR9 — Valeur vie client (CLV) sur revenu récurrent, fondation pure.

Comme :mod:`core.churn_risk`, :mod:`core.payment_delay` et
:mod:`core.stock_reorder`, ce module reste une couche de BASE — contrat
import-linter ``core-foundation-is-a-base-layer`` : il n'importe AUCUNE app
métier. L'app appelante (``apps.contrats``) calcule l'ARPC (revenu mensuel
moyen par client — ici le MRR du client) et le TAUX DE CHURN observé via SA
propre couche ``selectors`` (MRR + mouvements XCTR7) et passe deux simples
nombres à :func:`clv` ; ``core`` fournit uniquement le calcul générique et ne
touche jamais la base ni le réseau (librairie standard seulement).

Formule (patron SaaS classique) ::

    CLV = ARPC_mensuel / taux_churn_mensuel

``taux_churn_mensuel`` est une FRACTION (ex. 0.05 = 5 % de churn mensuel), pas
un pourcentage. Le résultat est le revenu total espéré sur la durée de vie
moyenne d'un client (``1 / taux_churn`` mois).

Repli PROPRE (jamais d'exception, jamais de division par zéro) : si
``taux_churn`` est ``None``, nul, négatif, ou si ``arpc`` est ``None`` ou
négatif, la CLV est INCONNUE — :func:`clv` renvoie un résultat avec
``clv=None`` et ``used_fallback=True`` plutôt que de deviner une valeur.
"""
from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal

# Plafond de bornage de la CLV (en unités monétaires) pour éviter un résultat
# absurde/déraisonnable quand ``taux_churn`` est minuscule (proche de 0) sans
# être nul — ex. 0.0001 (0.01 % mensuel) donnerait une CLV à 10 000x l'ARPC.
# Le plafond suit la même logique de « borne défensive » que
# ``core.churn_risk`` borne son score à [0, 1] : on préfère une valeur
# lisible et exploitable côté UI à un nombre techniquement exact mais absurde.
DEFAULT_MAX_MULTIPLE = Decimal('120')  # 120 mois d'ARPC = 10 ans, plafond haut


@dataclass
class ClvResult:
    """Résultat de :func:`clv`.

    ``clv`` est ``None`` quand le calcul est IMPOSSIBLE (churn nul/inconnu/
    négatif, ou ARPC absent/négatif) — ``used_fallback`` vaut alors ``True`` et
    ``clv`` ne doit JAMAIS être traité comme 0 par l'appelant (0 signifierait
    « client sans valeur », ce n'est pas ce que ``None`` exprime ici).
    ``duree_vie_mois`` est la durée de vie moyenne espérée (``1/taux_churn``),
    ``None`` dans les mêmes conditions que ``clv``.
    """

    clv: Decimal | None
    duree_vie_mois: Decimal | None
    used_fallback: bool = False
    plafonnee: bool = False


def _coerce_decimal(raw):
    """Convertit en ``Decimal`` ou renvoie ``None`` si non numérique/absent."""
    if raw is None:
        return None
    try:
        return Decimal(str(raw))
    except (TypeError, ValueError, ArithmeticError):
        return None


def clv(arpc, taux_churn, *, max_multiple=None) -> ClvResult:
    """Calcule la valeur vie client (CLV) sur revenu récurrent.

    - ``arpc`` : revenu mensuel moyen par client (ex. le MRR d'UN client).
    - ``taux_churn`` : taux de churn mensuel OBSERVÉ, en FRACTION ``[0, 1]``
      (ex. 0.05 = 5 %/mois) — PAS un pourcentage.
    - ``max_multiple`` : plafond du multiple ``CLV / ARPC`` (défaut
      :data:`DEFAULT_MAX_MULTIPLE` = 120 mois). Sert à borner un résultat
      démesuré quand le churn est minuscule sans être nul.

    Repli propre (``clv=None``, ``used_fallback=True``) si :
    - ``taux_churn`` est ``None``, ``<= 0`` ;
    - ``arpc`` est ``None`` ou ``< 0``.

    Un ``arpc`` de 0 est un cas VALIDE (client sans MRR actif — CLV = 0, pas un
    repli) : la CLV vaut alors 0, pas ``None``.

    Renvoie un :class:`ClvResult`.
    """
    arpc_d = _coerce_decimal(arpc)
    churn_d = _coerce_decimal(taux_churn)

    if churn_d is None or churn_d <= 0:
        return ClvResult(clv=None, duree_vie_mois=None, used_fallback=True)
    if arpc_d is None or arpc_d < 0:
        return ClvResult(clv=None, duree_vie_mois=None, used_fallback=True)

    duree_vie_mois = Decimal('1') / churn_d
    valeur = arpc_d * duree_vie_mois

    plafond = max_multiple if max_multiple is not None else DEFAULT_MAX_MULTIPLE
    plafond = Decimal(str(plafond))
    plafonnee = False
    valeur_max = arpc_d * plafond
    if arpc_d > 0 and valeur > valeur_max:
        valeur = valeur_max
        duree_vie_mois = plafond
        plafonnee = True

    return ClvResult(
        clv=valeur.quantize(Decimal('0.01')),
        duree_vie_mois=duree_vie_mois.quantize(Decimal('0.01')),
        used_fallback=False,
        plafonnee=plafonnee,
    )
