"""CIQ617 — lectures du dossier réglementaire 82-21 (``RegulatoryDossier``).

Le dossier est la SEULE source de l'état 82-21 d'une affaire (contrat partagé
``contract_samples/dossier_8221.json``, bloc ``resume``). Le chantier
(``apps.installations``) n'en garde qu'un MIROIR, écrit par
``installations.services.refleter_dossier_8221`` ; il lit ce résumé par
``ventes.selectors.dossier_8221_resume`` (frontière M3 : jamais le modèle).

Aucun montant, aucun délai promis au client ; aucun statut de devis touché
(règle #4).
"""
from __future__ import annotations

#: Statuts d'une pièce de checklist qui la rendent « fournie ».
_PIECE_FOURNIE = ('fourni', 'valide', 'na')


def _iso(valeur):
    return valeur.isoformat() if valeur else None


def _champ(dossier, nom):
    """Champ posé par une tâche ultérieure (CIQ619/CIQ620) : None s'il
    n'existe pas encore sur le modèle — la clé du contrat reste servie."""
    return getattr(dossier, nom, None)


def resume_dossier_8221(dossier):
    """Bloc ``resume`` (contrat CIQ12) d'un ``RegulatoryDossier``."""
    manquantes = [
        item.code for item in dossier.checklist_items.all()
        if item.obligatoire and item.statut not in _PIECE_FOURNIE]
    return {
        'source': 'dossier',
        'statut': dossier.statut,
        'reference': dossier.reference_dossier,
        'operateur': dossier.operateur,
        'date_depot': _iso(dossier.date_depot),
        'date_decision': _iso(dossier.date_decision),
        'pieces_manquantes': manquantes,
        'etude': {
            'frais_notifies_le': _iso(_champ(dossier,
                                             'etude_frais_notifies_le')),
            'paiement_limite_le': None,
            'payee_le': _iso(_champ(dossier, 'etude_payee_le')),
            'conclusion': _champ(dossier, 'etude_conclusion'),
            'reglages_imposes': _champ(dossier, 'etude_reglages_imposes'),
        },
        'capacite': {
            'etat': _champ(dossier, 'capacite_etat'),
            'date': _iso(_champ(dossier, 'capacite_date')),
        },
        'convention_signee_le': _iso(_champ(dossier, 'convention_signee_le')),
        'travaux_limite_le': None,
        'demande_exploitation_le': _iso(
            _champ(dossier, 'demande_exploitation_le')),
        'accord_exploitation_le': _iso(
            _champ(dossier, 'accord_exploitation_le')),
        'equipements_figes': list(_champ(dossier, 'equipements_figes') or []),
        'alertes_modification': [],
    }


def dossier_8221_de_devis(company, devis_id):
    """Le dossier 82-21 le plus récent d'un devis de la société, ou None."""
    if not devis_id or company is None:
        return None
    from .models import RegulatoryDossier
    return (RegulatoryDossier.objects
            .filter(company=company, devis_id=devis_id)
            .prefetch_related('checklist_items')
            .order_by('-created_at', '-id').first())


def dossier_8221_resume(company, devis_id):
    """CIQ617 — ``resume`` du dossier 82-21 de l'affaire, ou None si aucun
    dossier n'existe (le chantier garde alors sa saisie : ``source:
    saisie_chantier``). Scopé société : un devis d'une autre société → None."""
    dossier = dossier_8221_de_devis(company, devis_id)
    if dossier is None:
        return None
    resume = resume_dossier_8221(dossier)
    resume['regime'] = dossier.regime_8221
    return resume
