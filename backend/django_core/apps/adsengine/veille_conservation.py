"""VEIL19 — Conservation et sortie d'un client (Platform Terms §3.d.i).

Deux gestes, jamais plus :

* ``purger_extraits(now, apply_, company=None)`` — efface les TEXTES (extrait,
  légende, titres) des ``VeillePubVue`` plus anciennes que
  ``VEILLE_CONSERVATION_PUBS_JOURS`` jours (défaut 90 : choix de prudence,
  aucun texte ne l'impose). Les agrégats d'annonceur et les verdicts sont
  GARDÉS. Branchée dans le registre partagé ``core.retention`` (``apps.py``) :
  simulation par défaut (``apply_=False`` → rien n'est modifié, le compte est
  exact).
* ``purger_societe(company_id, apply_)`` — fin de contrat : TOUTES les données
  de veille d'UNE société (découvertes, requêtes, pubs vues, annonceurs,
  verdicts). Commande ``veille_purger --company <id>``.
"""
from __future__ import annotations

import datetime

from django.db import transaction
from django.utils import timezone

NOM_POLITIQUE = 'adsengine.veille_pubs_vues'
JOURS_DEFAUT = 90


def jours_conservation():
    from core.retention import setting_days
    jours = setting_days('VEILLE_CONSERVATION_PUBS_JOURS', JOURS_DEFAUT)
    return jours if jours > 0 else JOURS_DEFAUT


def _a_purger(now, company=None):
    from .models import VeillePubVue

    limite = now - datetime.timedelta(days=jours_conservation())
    qs = VeillePubVue.objects.filter(created_at__lt=limite).exclude(
        extrait='', legende='', titres=[])
    if company is not None:
        qs = qs.filter(company_id=getattr(company, 'id', company))
    return qs


def purger_extraits(now=None, apply_=False, company=None):
    """Compte (simulation) ou efface (``apply_``) les textes des pubs vues
    trop anciennes. Renvoie le nombre de lignes concernées."""
    now = now or timezone.now()
    qs = _a_purger(now, company)
    if not apply_:
        return qs.count()
    return qs.update(extrait='', legende='', titres=[])


def politique_retention(now, apply_):
    """Point d'entrée du registre ``core.retention`` (toutes sociétés)."""
    return purger_extraits(now=now, apply_=apply_)


def compter_societe(company_id):
    from .models import (VeilleAnnonceur, VeilleDecouverte, VeillePubVue,
                         VeilleRequete, VeilleVerdict)
    return {
        'decouvertes': VeilleDecouverte.objects.filter(
            company_id=company_id).count(),
        'requetes': VeilleRequete.objects.filter(
            company_id=company_id).count(),
        'pubs_vues': VeillePubVue.objects.filter(
            company_id=company_id).count(),
        'annonceurs': VeilleAnnonceur.objects.filter(
            company_id=company_id).count(),
        'verdicts': VeilleVerdict.objects.filter(
            company_id=company_id).count(),
    }


def purger_societe(company_id, apply_=False):
    """Fin de contrat : efface TOUTES les données de veille d'une société.
    Renvoie ``{'avant': {...}, 'apres': {...}}`` ; en simulation, ``apres`` =
    ``avant`` (rien supprimé)."""
    from .models import (VeilleAnnonceur, VeilleDecouverte, VeillePubVue,
                         VeilleRequete, VeilleVerdict)

    avant = compter_societe(company_id)
    if apply_:
        with transaction.atomic():
            VeilleAnnonceur.objects.filter(company_id=company_id).update(
                verdict_courant=None, doublon_de=None, jeu_decouverte=None)
            VeilleVerdict.objects.filter(company_id=company_id).delete()
            VeillePubVue.objects.filter(company_id=company_id).delete()
            VeilleAnnonceur.objects.filter(company_id=company_id).delete()
            VeilleRequete.objects.filter(company_id=company_id).delete()
            VeilleDecouverte.objects.filter(company_id=company_id).delete()
    return {'avant': avant, 'apres': compter_societe(company_id)}
