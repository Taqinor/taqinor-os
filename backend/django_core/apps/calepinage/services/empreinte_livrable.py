# -*- coding: utf-8 -*-
"""ACAL221 — L'EMPREINTE DES ENTRÉES d'un livrable du calepinage.

LE CONSTAT (C-ACAL-121, C-ACAL-134)
-----------------------------------
Les octets d'un PDF diffèrent d'un rendu à l'autre (182 840 puis 182 838
octets sur le même calepinage) : ni le sha256 d'un PDF rendu, ni
``layout_hash`` seul ne disent si deux remises décrivent la MÊME étude. Les
ancres de ``pack_technique.py`` / ``reglementaire.py`` (``layout_hash[:12]``)
ignoraient la simulation, les saisies électriques, la pose réelle, les
gabarits, les photos, la langue, l'identité et la marque imprimées.

LA RÈGLE
--------
UNE fonction, :func:`empreinte_des_entrees` : le SHA-256 hex d'un JSON trié qui
réunit TOUT ce qu'un livrable lit —

* la conception : l'empreinte « document » D-ACAL-4
  (:func:`services.layout.empreinte_document`, champs volatils exclus) ;
* la simulation SERVIE (``selectors.resultat_servi`` — fraîcheur comprise) :
  son ``hash_entree``, ``simule``, ``simulation_perimee`` et ses blocs, privés
  de leurs dates de calcul ;
* les saisies stockées du registre :data:`services.resultat.CLES_SAISIES`
  (entrée électrique, schéma unifilaire édité, raccordement, dérogations) ;
* la pose réelle (``PoseReelle``), les photos de site (``PhotoSite``) et les
  saisies des dossiers réglementaires (``DossierReglementaire``) ;
* les gabarits ACTIFS de la société (id, code, genre, version, fichier) —
  dossiers ET manuel du propriétaire ;
* l'identité imprimée (titre, client et adresses LUS par ``crm.selectors``) et
  la marque de la société (``styles_de_societe``) ;
* la langue et la sélection de sections demandées.

Lecture STRICTEMENT PURE : rien n'est écrit, aucun statut touché (règle #4).
L'empreinte n'est stockée que par ses consommateurs (nom d'une version
remise, ancre GED). Aucune date de rendu n'y entre : deux lectures sans geste
rendent la même valeur.
"""
from __future__ import annotations

import hashlib
import json

__all__ = ['CHAMPS_VOLATILS', 'empreinte_des_entrees']

#: Les clés ignorées PARTOUT dans la simulation servie et les saisies : des
#: horodatages de calcul / de saisie, jamais une donnée imprimée.
CHAMPS_VOLATILS = frozenset({'calcule_le', 'saisi_le'})


def _sans_volatils(valeur):
    """Une copie de ``valeur`` privée, à toute profondeur, des :data:`CHAMPS_VOLATILS`."""
    if isinstance(valeur, dict):
        return {cle: _sans_volatils(v) for cle, v in valeur.items()
                if cle not in CHAMPS_VOLATILS}
    if isinstance(valeur, (list, tuple)):
        return [_sans_volatils(v) for v in valeur]
    return valeur


def _simulation_servie(calepinage):
    """Ce que les livrables lisent de la simulation : le résultat SERVI."""
    from .. import selectors
    from .electrique import BLOCS_SIMULATION

    servi = selectors.resultat_servi(calepinage) or {}
    return _sans_volatils({
        'hash_entree': servi.get('hash_entree') or '',
        'simule': bool(servi.get('simule')),
        'simulation_perimee': bool(servi.get('simulation_perimee')),
        'blocs': {cle: servi.get(cle) for cle in BLOCS_SIMULATION},
    })


def _saisies_stockees(calepinage):
    """Les clés de SAISIE du registre ACAL57, telles qu'enregistrées."""
    from .resultat import CLES_SAISIES

    resultat = getattr(calepinage, 'resultat', None)
    resultat = resultat if isinstance(resultat, dict) else {}
    return _sans_volatils({cle: resultat.get(cle) for cle in CLES_SAISIES})


def _lignes_liees(calepinage):
    """Pose réelle, photos de site et dossiers réglementaires du calepinage."""
    from ..models import DossierReglementaire, PhotoSite, PoseReelle

    if not getattr(calepinage, 'pk', None):
        return {'pose_reelle': [], 'photos': [], 'dossiers': []}
    pose = list(PoseReelle.objects
                .filter(calepinage_id=calepinage.pk)
                .order_by('pan', 'pk')
                .values('pk', 'pan', 'modules_poses', 'ecarts_position',
                        'releve_le'))
    photos = list(PhotoSite.objects
                  .filter(calepinage_id=calepinage.pk)
                  .order_by('pk')
                  .values('pk', 'attachment_id', 'genre', 'prise_le',
                          'legende', 'calage', 'slot_code'))
    dossiers = list(DossierReglementaire.objects
                    .filter(calepinage_id=calepinage.pk)
                    .order_by('pk')
                    .values('pk', 'gabarit_id', 'champs_saisis',
                            'pieces_jointes'))
    return {'pose_reelle': pose, 'photos': photos, 'dossiers': dossiers}


def _gabarits(company):
    """Les gabarits ACTIFS de la société (dossiers réglementaires et manuel)."""
    from ..models import GabaritDossierReglementaire

    if company is None:
        return []
    return list(GabaritDossierReglementaire.objects
                .filter(company=company, actif=True)
                .order_by('pk')
                .values('pk', 'pays', 'code', 'genre', 'intitule',
                        'pieces_attendues', 'champs', 'version',
                        'fichier_id'))


def _identite(calepinage):
    """Titre, client et adresses imprimés — LUS par les sélecteurs du CRM."""
    company = getattr(calepinage, 'company', None)
    identite = {'titre': getattr(calepinage, 'titre', '') or '',
                'client': None, 'client_adresse': None,
                'lead': None, 'lead_adresse': None}
    if company is None:
        return identite
    from apps.crm.selectors import get_company_client, get_company_lead

    client = get_company_client(company, getattr(calepinage, 'client_id', None))
    if client is not None:
        identite['client'] = ' '.join(filter(None, (
            getattr(client, 'prenom', '') or '',
            getattr(client, 'nom', '') or '')))
        identite['client_adresse'] = getattr(client, 'adresse', None)
    lead = get_company_lead(company, getattr(calepinage, 'lead_id', None))
    if lead is not None:
        identite['lead'] = ' '.join(filter(None, (
            getattr(lead, 'prenom', '') or '',
            getattr(lead, 'nom', '') or '')))
        identite['lead_adresse'] = getattr(lead, 'adresse', None)
    return identite


def _marque(company):
    """La marque imprimée (``styles_de_societe``), vide sans société."""
    from .documents.gabarit_document import styles_de_societe

    if company is None:
        return styles_de_societe({})
    return styles_de_societe(company)


def _entrees_du_livrable(calepinage, langue='fr', sections=None):
    """Le dictionnaire CANONIQUE des entrées d'un livrable (avant hachage).

    Exposé pour les diagnostics et les tests ; :func:`empreinte_des_entrees`
    en est le SHA-256. ``sections`` garde l'ORDRE demandé (il change le
    document) ; ``None`` vaut « aucune sélection » (toutes les sections).
    """
    from .layout import empreinte_document

    company = getattr(calepinage, 'company', None)
    return {
        'document': empreinte_document(getattr(calepinage, 'roof_layout', None)),
        'simulation': _simulation_servie(calepinage),
        'saisies': _saisies_stockees(calepinage),
        'lignes': _lignes_liees(calepinage),
        'gabarits': _gabarits(company),
        'identite': _identite(calepinage),
        'marque': _marque(company),
        'langue': str(langue or '').strip().lower(),
        'sections': None if sections is None else [str(s) for s in sections],
    }


def empreinte_des_entrees(calepinage, langue='fr', sections=None):
    """ACAL221 — l'empreinte (SHA-256 hex) de TOUT ce qu'un livrable lit.

    Stable entre deux lectures sans geste ; change dès qu'UNE entrée change
    (conception, simulation servie, saisie électrique, pose réelle, gabarit,
    photo, langue, sections, titre / client / adresse, marque de la société).
    Lecture PURE : aucune écriture.
    """
    canonique = json.dumps(_entrees_du_livrable(calepinage, langue, sections),
                           sort_keys=True, separators=(',', ':'),
                           ensure_ascii=False, default=str)
    return hashlib.sha256(canonique.encode('utf-8')).hexdigest()
