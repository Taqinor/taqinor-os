"""NTGRC4 — politique de rétention Ventes pilotée par `grc.PolitiqueRetentionObjet`.

Les Ventes exposent le type d'objet ``ventes_facture`` en **signalement
seul** : une facture émise relève d'obligations comptables et fiscales
(conservation 10 ans au Maroc) — elle ne s'anonymise pas et ne se détruit pas
sur une politique de rétention interne. Le balayage COMPTE donc les factures
échues au regard de la durée configurée et le rapporte (c'est utile : il dit
au DPO combien de pièces sortent de la fenêtre de conservation choisie), mais
ne modifie JAMAIS rien, même avec ``--commit``.

C'est délibéré et documenté plutôt que silencieux : une politique qui
prétendrait anonymiser une facture serait, elle, un vrai risque légal.
"""
from __future__ import annotations

TYPES = ('ventes_facture',)

MOTIF_NON_APPLICABLE = (
    "Une facture émise est conservée au titre des obligations comptables et "
    "fiscales : la rétention interne la SIGNALE, elle ne l'anonymise ni ne la "
    "supprime."
)


def _echues(politique, now):
    """Factures échues pour CETTE politique (bornées à sa société)."""
    from django.apps import apps as django_apps
    from django.utils import timezone

    # Résolution PAR CHAÎNE (jamais un import de `apps.facturation.models`) :
    # la frontière cross-app reste intacte. `date_emission` est une DateField.
    Facture = django_apps.get_model('facturation', 'Facture')
    cutoff = (now - timezone.timedelta(days=politique['jours'])).date()
    return Facture.objects.filter(
        company=politique['company'], date_emission__lt=cutoff)


def sweep_objets(now, apply_):
    """Compte les factures hors fenêtre de conservation. Ne modifie rien."""
    from apps.grc.selectors import politiques_retention_actives

    total = 0
    for politique in politiques_retention_actives(TYPES):
        total += _echues(politique, now).count()
    return total


def register():
    """Enregistre la politique Ventes (idempotent, appelée en ready())."""
    from core.retention import register_retention_policy

    register_retention_policy('ventes_factures_echues', sweep_objets)
