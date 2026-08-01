"""Services du module Appels d'offres (``apps.ao``).

AOF1 — le CORPS des services AO vit désormais ICI (il vivait encore interleavé
dans ``apps.compta.services`` malgré la sortie ODX11 des modèles).
``apps.compta.services`` porte maintenant un shim de ré-export **INVERSE**
(``from apps.ao.services import …``) pour ne casser aucun import historique.

``ao`` ne lit crm/ventes QUE via leurs selectors/services ou par référence
opaque — jamais leurs ``models`` (le lead reste un ``lead_id`` opaque).
"""
from decimal import ROUND_HALF_UP, Decimal

from django.utils import timezone

from .models import EcheanceAO, ResultatAO


# ── FG226 — Échéances d'AO dues (rappels) ──────────────────────────────────

def echeances_ao_dues(company, *, a_la_date=None):
    """Liste les échéances d'AO dont le rappel est dû (FG226), NON traitées.

    Une échéance est due quand ``date_echeance - rappel_jours <= a_la_date`` et
    qu'elle n'est pas encore traitée. Calcul pur (aucun envoi réseau) — sert au
    moteur d'alertes et aux tests.
    """
    a_la_date = a_la_date or timezone.now().date()
    dues = []
    qs = EcheanceAO.objects.filter(
        company=company, traitee=False).order_by('date_echeance')
    for ech in qs:
        seuil = ech.date_echeance - timezone.timedelta(days=ech.rappel_jours)
        if seuil <= a_la_date:
            dues.append(ech)
    return dues


# ── FG227 — Taux de réussite des appels d'offres ───────────────────────────

def taux_reussite_ao(company):
    """Taux de réussite gagné/perdu des AO (FG227).

    Compte les résultats par issue et calcule le taux = gagnés / (gagnés +
    perdus). Renvoie un dict d'agrégats. Lecture seule.
    """
    resultats = ResultatAO.objects.filter(company=company)
    gagnes = resultats.filter(issue=ResultatAO.Issue.GAGNE).count()
    perdus = resultats.filter(issue=ResultatAO.Issue.PERDU).count()
    total_decides = gagnes + perdus
    taux = Decimal('0.00')
    if total_decides > 0:
        taux = (Decimal(gagnes) / Decimal(total_decides) * Decimal('100')
                ).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
    return {
        'gagnes': gagnes,
        'perdus': perdus,
        'total_decides': total_decides,
        'total_resultats': resultats.count(),
        'taux_reussite_pct': taux,
    }
