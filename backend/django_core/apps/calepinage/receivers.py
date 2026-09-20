"""Abonnements au bus d'événements (M6) du module « calepinage ».

``core.events`` expose des objets ``django.dispatch.Signal`` (bus synchrone qui
ne dépend de rien). Une app réagit au changement d'état d'une AUTRE app en s'y
abonnant ICI (décorateur ``@receiver`` avec un ``dispatch_uid`` stable) et en
branchant ce module dans ``apps.py`` ``ready()`` — jamais en important les vues
ou les modèles de l'autre app (frontière import-linter).

CAL39 — LE MIROIR ÉVÉNEMENTIEL, ET POURQUOI IL EXISTE
------------------------------------------------------
L'atelier en mode « devis » écrit dans ``Devis.roof_layout``. Le module
Calepinage, lui, fait vivre les versions, les variantes, la planche, la note de
calcul, les chaînes, la production et le badge « à jour » — toutes bâties sur
``Calepinage.roof_layout``. Sans ce miroir, un calepinage créé depuis la fiche
lead resterait GELÉ à sa création pendant que le devis, lui, continue d'être
redessiné : toutes ces fonctions liraient un document périmé, sans que personne
ne le voie.

ZÉRO CHANGEMENT D'ÉCRAN (demande fondateur n°3) : aucune ligne de
``LeadWorkspace.jsx`` ni de ``ToitureDesign.jsx`` n'est touchée. Les trois
chemins d'enregistrement de ventes (``from-layout``, ``sync-layout`` et
l'action ``layout``) émettent le MÊME événement ``layout_finalise``, et c'est
lui — pas l'écran — qui alimente le calepinage canonique.

BEST-EFFORT, TOUJOURS : un miroir en échec ne doit JAMAIS faire échouer un
enregistrement de devis déjà réussi. L'erreur est journalisée, pas propagée.
"""
from __future__ import annotations

import logging

from django.dispatch import receiver

from core.events import layout_finalise

logger = logging.getLogger(__name__)

__all__ = ['miroir_layout_du_devis']


@receiver(layout_finalise, dispatch_uid='calepinage_miroir_layout_finalise')
def miroir_layout_du_devis(sender, devis, user=None, **kwargs):
    """Alimente le calepinage canonique du devis avec sa conception.

    * le calepinage est OBTENU ou CRÉÉ (idempotent : le même devis rend
      toujours le même calepinage — ``services.obtenir_ou_creer_pour_devis``) ;
    * la conception est enregistrée par le chemin d'écriture COMMUN
      (``services.enregistrer_layout``), donc elle dépose une version quand —
      et seulement quand — elle a changé, et le chatter est alimenté ;
    * la SOCIÉTÉ et l'AUTEUR viennent du serveur : la société est celle du
      devis, l'auteur est l'utilisateur agissant transmis par l'événement.

    Aucun statut n'est écrit (règle #4), ni côté devis ni côté calepinage.
    """
    layout = getattr(devis, 'roof_layout', None)
    company = getattr(devis, 'company', None)
    if devis is None or company is None or not isinstance(layout, dict) \
            or not layout:
        return
    try:
        from .services.creation import obtenir_ou_creer_pour_devis
        from .services.layout import enregistrer_layout

        calepinage, _ = obtenir_ou_creer_pour_devis(
            devis.pk, company, user=user)
        enregistrer_layout(calepinage, layout, user=user)
    except Exception:  # noqa: BLE001 — un miroir ne casse jamais la source
        logger.exception(
            'CAL39 : miroir de conception en échec pour le devis %s',
            getattr(devis, 'pk', None))
