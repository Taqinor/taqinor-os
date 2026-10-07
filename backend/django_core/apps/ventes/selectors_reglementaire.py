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


#: CIQ619 — délais MAXIMAUX du décret 2.25.100 (jamais une date promise).
#: Art. 13 : l'étude est payée sous 10 jours après notification des frais,
#: sinon le dossier est retourné.
DELAI_PAIEMENT_ETUDE_JOURS = 10
DELAI_PAIEMENT_ETUDE_SOURCE = 'décret 2.25.100 art. 13'
#: Art. 14 : travaux sous 2 ans après la convention (accord / autorisation).
DELAI_TRAVAUX_ACCORD_MOIS = 24
DELAI_TRAVAUX_ACCORD_SOURCE = 'décret 2.25.100 art. 14'
#: Art. 8 : travaux sous 12 mois après le récépissé (déclaration).
DELAI_TRAVAUX_DECLARATION_MOIS = 12
DELAI_TRAVAUX_DECLARATION_SOURCE = 'décret 2.25.100 art. 8'


def _ajouter_mois(jour, mois):
    """``jour`` + ``mois`` mois calendaires (29/02 → 28/02 si besoin)."""
    import calendar
    total = jour.month - 1 + mois
    annee, mois_cible = jour.year + total // 12, total % 12 + 1
    dernier = calendar.monthrange(annee, mois_cible)[1]
    return jour.replace(year=annee, month=mois_cible,
                        day=min(jour.day, dernier))


def paiement_etude_limite(dossier):
    """Date limite de paiement de l'étude (art. 13), ou None."""
    from datetime import timedelta
    notifie = _champ(dossier, 'etude_frais_notifies_le')
    if not notifie:
        return None
    return notifie + timedelta(days=DELAI_PAIEMENT_ETUDE_JOURS)


def travaux_limite(dossier):
    """Date limite des travaux : accord/autorisation → convention + 2 ans
    (art. 14) ; déclaration → récépissé (``date_decision``) + 12 mois
    (art. 8). None tant que la date d'origine n'est pas saisie."""
    regime = dossier.regime_8221
    if regime in ('accord_raccordement', 'autorisation_anre'):
        convention = _champ(dossier, 'convention_signee_le')
        return (_ajouter_mois(convention, DELAI_TRAVAUX_ACCORD_MOIS)
                if convention else None)
    if regime == 'declaration_bt' and dossier.date_decision:
        return _ajouter_mois(dossier.date_decision,
                             DELAI_TRAVAUX_DECLARATION_MOIS)
    return None


def _alertes(dossier):
    from .domain.dossier_8221 import alertes_modification_dossier
    return alertes_modification_dossier(dossier)


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
            'paiement_limite_le': _iso(paiement_etude_limite(dossier)),
            'payee_le': _iso(_champ(dossier, 'etude_payee_le')),
            'conclusion': _champ(dossier, 'etude_conclusion'),
            'reglages_imposes': _champ(dossier, 'etude_reglages_imposes'),
        },
        'capacite': {
            'etat': _champ(dossier, 'capacite_etat'),
            'date': _iso(_champ(dossier, 'capacite_date')),
        },
        'convention_signee_le': _iso(_champ(dossier, 'convention_signee_le')),
        'travaux_limite_le': _iso(travaux_limite(dossier)),
        'demande_exploitation_le': _iso(
            _champ(dossier, 'demande_exploitation_le')),
        'accord_exploitation_le': _iso(
            _champ(dossier, 'accord_exploitation_le')),
        'equipements_figes': list(_champ(dossier, 'equipements_figes') or []),
        # CIQ620 — avertissement (jamais un blocage) si le matériel a changé
        # depuis le dépôt (loi 82-21 art. 8-9).
        'alertes_modification': _alertes(dossier),
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


def injection_limitee_devis(company, devis_id):
    """CIQ663 — la sortie du moteur C&I (contrat CIQ2,
    ``etude_params['etude_ci']['taille']``) indique-t-elle une injection
    LIMITÉE (taille plafonnée par l'injection : ``raison_arret`` =
    ``plafond_injection``) ? Lecture seule, scopée société ; ``False`` sans
    devis ni étude (jamais une valeur devinée)."""
    if not devis_id or company is None:
        return False
    from .models import Devis
    devis = (Devis.objects.filter(pk=devis_id, company=company)
             .only('etude_params').first())
    if devis is None:
        return False
    etude = (devis.etude_params or {}).get('etude_ci') or {}
    taille = etude.get('taille') if isinstance(etude, dict) else None
    return (isinstance(taille, dict)
            and taille.get('raison_arret') == 'plafond_injection')


def regime_contrat_dossier(dossier):
    """CIQ638 — bloc ``regime`` du contrat ``dossier_8221.json`` du régime
    STOCKÉ d'un dossier : libellé sans seuil, base légale (article), guichet
    « à confirmer ». La puissance retenue n'est donnée que si le devis la
    porte (jamais devinée)."""
    from core.reglementaire.regime_8221 import forme_regime
    devis = getattr(dossier, 'devis', None)
    puissance = ((getattr(devis, 'etude_params', None) or {})
                 .get('puissance_kwc'))
    return forme_regime(dossier.regime_8221, puissance)


def pieces_contrat_dossier(dossier):
    """CIQ638 — bloc ``pieces`` du contrat : les pièces du décret du régime
    du dossier (``regulatory_docs.required_documents``), chacune avec son
    ``etape`` et sa ``source`` ; ``statut`` = celui de la pièce de checklist
    de même code (``None`` si elle n'a pas été ouverte). Une pièce « à
    confirmer » le reste dans sa source, jamais présentée comme certaine."""
    from .regulatory_docs import required_documents
    statuts = {item.code: item.statut for item in dossier.checklist_items.all()}
    return [{
        'code': piece['code'], 'label': piece['label'],
        'etape': piece['etape'], 'obligatoire': piece['obligatoire'],
        'source': piece['source'], 'statut': statuts.get(piece['code']),
    } for piece in required_documents(dossier.regime_8221)]
