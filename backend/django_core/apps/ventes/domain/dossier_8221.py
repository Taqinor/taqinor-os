"""CIQ618 — ouverture automatique du dossier réglementaire 82-21 d'un site
professionnel (D-CIQ-18 : l'installateur monte le dossier).

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


# ── CIQ620 — équipements FIGÉS au dépôt (loi 82-21 art. 8-9) ──────────────
#: Le dossier déposé contient fabricant et modèle (décret 2.25.100 art. 12) ;
#: toute modification exige un accord préalable (loi 82-21 art. 9) ou devient
#: une nouvelle demande (art. 8). Un AVERTISSEMENT, jamais un blocage.
ALERTE_MODIFICATION = {
    'code': 'equipement_modifie',
    'message': ("modification du dossier — accord préalable requis "
                "(loi 82-21 art. 9)"),
    'base': 'loi 82-21 art. 8-9',
}
#: Statuts du dossier à partir desquels la liste d'équipements est déposée.
STATUTS_DEPOSES = ('depose', 'en_instruction', 'complement_demande',
                   'approuve', 'comptage_pose', 'refuse')
_ROLES_DECLARES = ('panneau', 'onduleur_reseau', 'onduleur_hybride',
                   'onduleur_offgrid', 'batterie')


def _est_declare(nom):
    from .catalogue import classer_produit
    nom = nom or ''
    return (classer_produit(nom) in _ROLES_DECLARES
            or 'onduleur' in nom.lower())


def _puissance(produit):
    """Puissance lue sur la fiche technique (Wc d'un module, kW AC d'un
    onduleur, kWh d'une batterie), ou None — jamais devinée."""
    from apps.stock.selectors import specs_for_produit
    specs = specs_for_produit(produit) or {}
    for cle in ('pmax_wc', 'ac_kw', 'kwh_nominal'):
        if specs.get(cle) is not None:
            return float(specs[cle])
    return None


def equipements_du_devis(devis):
    """Équipements déclarables (modules, onduleurs, batteries) des lignes
    retenues du devis : ``[{produit_id, fabricant, modele, quantite,
    puissance}]`` regroupés par produit, triés par produit."""
    from ..utils.options import option_lines
    par_produit = {}
    for ligne in option_lines(devis):
        produit = getattr(ligne, 'produit', None)
        if produit is None or not _est_declare(produit.nom):
            continue
        entree = par_produit.setdefault(produit.pk, {
            'produit_id': produit.pk,
            'fabricant': getattr(produit, 'marque', None) or '',
            'modele': produit.nom,
            'quantite': 0.0,
            'puissance': _puissance(produit),
        })
        try:
            entree['quantite'] += float(ligne.quantite or 0)
        except (TypeError, ValueError):
            pass
    return [par_produit[k] for k in sorted(par_produit)]


def figer_equipements_dossier_8221(dossier):
    """CIQ620 — au passage à ``depose`` (ou au-delà), fige UNE fois la liste
    d'équipements depuis les lignes du devis ; jamais réécrite ensuite.
    Aucun dépôt automatique. Renvoie True si elle vient d'être figée."""
    if dossier.statut not in STATUTS_DEPOSES or dossier.equipements_figes:
        return False
    dossier.equipements_figes = equipements_du_devis(dossier.devis)
    dossier.save(update_fields=['equipements_figes', 'updated_at'])
    return True


def _signature(equipements):
    return {int(e['produit_id']): float(e.get('quantite') or 0)
            for e in equipements or [] if e.get('produit_id')}


def _derniere_revision(devis):
    vus = set()
    while getattr(devis, 'superseded_by_id', None) and devis.pk not in vus:
        vus.add(devis.pk)
        devis = devis.superseded_by
    return devis


def alertes_modification_dossier(dossier):
    """CIQ620 — alertes si le matériel de la DERNIÈRE révision du devis ou
    de la nomenclature du chantier (lue par ``installations.selectors``)
    diffère des équipements figés au dépôt. Avant dépôt → aucune. Jamais un
    blocage : la révision reste possible (décisions QJR5)."""
    if dossier.statut not in STATUTS_DEPOSES or not dossier.equipements_figes:
        return []
    fige = _signature(dossier.equipements_figes)
    alertes = []
    revision = _derniere_revision(dossier.devis)
    if _signature(equipements_du_devis(revision)) != fige:
        alertes.append(dict(ALERTE_MODIFICATION, origine='devis'))
    from apps.installations.selectors import installation_for_devis
    chantier = installation_for_devis(revision, company=dossier.company)
    bom = {}
    for ligne in (getattr(chantier, 'bom', None) or []):
        if (isinstance(ligne, dict) and ligne.get('produit_id')
                and _est_declare(ligne.get('designation'))):
            pid = int(ligne['produit_id'])
            bom[pid] = bom.get(pid, 0.0) + float(ligne.get('quantite') or 0)
    if bom and bom != fige:
        alertes.append(dict(ALERTE_MODIFICATION, origine='chantier'))
    return alertes
