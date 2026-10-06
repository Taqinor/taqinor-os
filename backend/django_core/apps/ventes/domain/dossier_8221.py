"""CIQ618 — ouverture automatique du dossier réglementaire 82-21 d'un site
professionnel (D-CIQ-18 : TAQINOR monte le dossier).

Appelée par ``installations`` (récepteur ``devis_accepted``) via la façade
``ventes.services.ouvrir_dossier_8221`` — jamais par un import de modèle.
Aucun délai promis au client ; aucun statut de devis changé (règle #4).
"""
from __future__ import annotations

from django.db.models import Q

#: Prochaine action posée quand le régime n'est pas connu (CIQ613/CIQ616).
PROCHAINE_ACTION_QUALIFIER = (
    "Qualifier le régime 82-21 (puissance ou niveau inconnu)")


def _semer_pieces(dossier):
    """Sème les pièces de ``required_documents`` (étape + ordre), sans
    doublon de code. Renvoie le nombre de pièces créées."""
    from ..models import DossierChecklistItem
    from ..regulatory_docs import required_documents

    existants = set(dossier.checklist_items.values_list('code', flat=True))
    crees = 0
    for ordre, piece in enumerate(required_documents(dossier.regime_8221)):
        if piece['code'] in existants:
            continue
        DossierChecklistItem.objects.create(
            company=dossier.company, dossier=dossier, code=piece['code'],
            libelle=piece['label'], etape=piece.get('etape') or 'depot',
            obligatoire=piece.get('obligatoire', True), ordre=ordre)
        crees += 1
    return crees


def ouvrir_dossier_8221(devis, chantier_id, regime, user=None):
    """CIQ618 — ouvre (une seule fois par affaire) le dossier 82-21.

    Idempotent : un dossier déjà ouvert pour ce devis, pour une version qu'il
    remplace (révision QJR5) ou pour ce chantier est RÉUTILISÉ — rattaché au
    devis courant et au chantier — jamais dupliqué. Sinon : dossier
    ``en_constitution`` lié au devis et au chantier (FK chaîne), pièces de
    ``required_documents`` semées avec étape et ordre ; régime ``a_qualifier``
    → ``prochaine_action`` « Qualifier le régime 82-21 ». Renvoie
    ``(dossier, created)`` ou ``(None, False)`` sans devis persisté."""
    from ..models import RegulatoryDossier
    from ..selectors import devis_predecesseurs_revision_ids

    company = getattr(devis, 'company', None)
    if getattr(devis, 'pk', None) is None or company is None:
        return None, False
    ids = [devis.pk] + devis_predecesseurs_revision_ids(devis)
    filtre = Q(devis_id__in=ids)
    if chantier_id:
        filtre |= Q(chantier_id=chantier_id)
    existant = (RegulatoryDossier.objects.filter(company=company)
                .filter(filtre).order_by('created_at', 'id').first())
    if existant is not None:
        champs = []
        if existant.devis_id != devis.pk:
            existant.devis = devis
            champs.append('devis')
        if chantier_id and existant.chantier_id != chantier_id:
            existant.chantier_id = chantier_id
            champs.append('chantier')
        if champs:
            existant.save(update_fields=champs + ['updated_at'])
        return existant, False

    regime = regime or 'a_qualifier'
    dossier = RegulatoryDossier.objects.create(
        company=company, devis=devis, chantier_id=chantier_id or None,
        regime_8221=regime,
        statut=RegulatoryDossier.Statut.EN_CONSTITUTION,
        prochaine_action=(PROCHAINE_ACTION_QUALIFIER
                          if regime == 'a_qualifier' else ''),
        created_by=user if getattr(user, 'pk', None) else None)
    _semer_pieces(dossier)
    return dossier, True
