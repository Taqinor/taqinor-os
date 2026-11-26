"""ADEV132 — les entrées du moteur unique, une seule porte pour les trois marchés.

``entrees_pour(lead, company)`` enveloppe, SANS les réécrire, les trois
adaptateurs existants : ``domain/entrees.py::entrees_depuis_lead``
(résidentiel), ``domain/etude_ci.py::resoudre_entrees`` (commercial,
industriel) et ``domain/pompage.py::resoudre_entrees`` (agricole). Il n'y a
aucune seconde lecture de la consommation, du lieu ni de l'occupation : la
provenance (``entrees_utilisees``, forme du contrat ``conception_lead.json``)
est relevée sur ce que l'adaptateur a résolu.

* résidentiel : base de l'``empreinte`` = ``empreinte_entrees`` de
  l'adaptateur (même cache que les blocs des devis) ; ``champ`` = la colonne
  du lead, ou le réglage société nommé ;
* C&I et agricole : ``champ`` = l'entrée nommée de la résolution (ses
  feuilles agrègent plusieurs colonnes du lead), ``source`` lue sur sa
  provenance ; base de l'``empreinte`` = SHA-256 des entrées résolues ;
* les trois marchés (relecture E4 B1, :func:`completer`) : la base couvre
  aussi le raccordement du lead, la TVA et le catalogue de la société.

Lecture pure : rien n'est écrit (règle n° 4).
"""
from dataclasses import dataclass, field
from datetime import date, datetime
from decimal import Decimal
import hashlib
import json

MARCHES_CI = ('commercial', 'industriel')

#: Colonnes du lead lues par l'adaptateur résidentiel et rendues telles quelles.
_COLONNES_RESIDENTIEL = ('facture_hiver', 'facture_ete', 'ete_differente',
                         'conso_mensuelle_kwh', 'gps_lat', 'gps_lng', 'raccordement')

#: Origine d'une provenance de résolution (C&I, pompage) → source du contrat.
_SOURCES = {'lead': 'lead', 'reglage_societe': 'reglage_societe', 'saisie': 'saisie',
            'calepinage': 'calepinage'}


@dataclass(frozen=True)
class EntreesConception:
    """Les entrées d'UNE conception : l'objet de l'adaptateur de son marché,
    la provenance de chaque valeur et l'empreinte."""

    marche: str
    moteur: object = None      # résidentiel : ``EntreesMoteur``
    resolution: object = None  # C&I : ``_Resolution`` ; agricole : ``(_Resolution, reglages)``
    entrees_utilisees: dict = field(default_factory=dict)
    empreinte: str = ''
    empreinte_pose: str = ''
    toit: object = None


def _json(valeur):
    if isinstance(valeur, Decimal):
        return float(valeur)
    if isinstance(valeur, (date, datetime)):
        return valeur.isoformat()
    if isinstance(valeur, (list, tuple)):
        return [_json(v) for v in valeur]
    if isinstance(valeur, dict):
        return {str(k): _json(v) for k, v in valeur.items()}
    return valeur


def _vide(valeur):
    return valeur in (None, '', [], {})


def marche_du_lead(lead):
    """Le marché du lead (vide ⇒ résidentiel, comme le devis automatique)."""
    marche = (getattr(lead, 'type_installation', '') or '').strip().lower() or 'residentiel'
    if marche not in ('residentiel', 'agricole') + MARCHES_CI:
        raise ValueError('Marché inconnu du moteur : « %s ».' % marche)
    return marche


def _provenance_residentielle(lead, moteur):
    """``{champ: {valeur, source}}`` de ce que l'adaptateur résidentiel a lu."""
    sortie = {}
    for colonne in _COLONNES_RESIDENTIEL:
        valeur = getattr(lead, colonne, None)
        if not _vide(valeur):
            sortie[colonne] = {'valeur': _json(valeur), 'source': 'lead'}
    if moteur is None:
        return sortie
    if moteur.ville:
        sortie['ville'] = {'valeur': moteur.ville, 'source': 'lead'}
    if moteur.occupation is not None:
        declaree = not _vide(getattr(lead, 'occupation_jour', None))
        sortie['occupation_jour'] = {'valeur': moteur.occupation,
                                     'source': 'lead' if declaree else 'defaut'}
    if moteur.equipements:
        sortie['equipements'] = {'valeur': sorted(moteur.equipements), 'source': 'lead'}
    if moteur.tranches is not None:
        sortie['bareme_tarifaire'] = {'valeur': 'bareme_societe', 'source': 'reglage_societe'}
    for reglage in ('charges_fixes_mad', 'productible_kwh_kwc'):
        if moteur[reglage] is not None:
            sortie[reglage] = {'valeur': _json(moteur[reglage]), 'source': 'reglage_societe'}
    return sortie


def _provenance_resolue(resolution, reglages=None):
    """``{champ: {valeur, source}}`` des entrées résolues (C&I, pompage)."""
    sortie = {}
    for cle, entree in sorted(resolution.entrees_resolues().items()):
        origine = (entree.get('provenance') or {}).get('origine')
        sortie[cle] = {'valeur': entree.get('valeur'), 'source': _SOURCES.get(origine, 'defaut')}
    for cle, (valeur, _prov) in sorted((reglages or {}).items()):
        sortie[cle] = {'valeur': _json(valeur), 'source': 'reglage_societe'}
    return sortie


def _empreinte(charge):
    canonique = json.dumps(charge, sort_keys=True, separators=(',', ':'), default=str,
                           ensure_ascii=False)
    return hashlib.sha256(canonique.encode('utf-8')).hexdigest()


#: T4-X7-022 — les souhaits du lead que la DÉCISION de chaque marché lit :
#: résidentiel ``decisions.py::_taille_residentielle`` (taille) et
#: ``decider_taille_residentielle`` (batterie) ; C&I ``decider_ci`` (taille) et
#: ``etude_ci_batterie`` (batterie, via ``lignes_des_options``). Agricole : aucun
#: (pompage sans batterie, taille tirée de la pompe).
_SOUHAITS_LUS = ('taille_souhaitee_kwc', 'batterie_souhaitee')
SOUHAITS_PAR_MARCHE = {'residentiel': _SOUHAITS_LUS, 'commercial': _SOUHAITS_LUS, 'industriel': _SOUHAITS_LUS}


def completer(empreinte, lead, company, utilisees):
    """Relecture E4 B1 — ce que les noyaux lisent hors de l'empreinte de
    l'adaptateur : le RACCORDEMENT du lead (phase du site : l'adaptateur
    résidentiel le lit sans l'empreindre), la TVA et le CATALOGUE de la société
    (``conception/societe.py``). Ajoutés à ``utilisees`` (provenance dite) ;
    rend l'empreinte qui les couvre."""
    from apps.ventes.conception.societe import entrees_de_la_societe

    raccordement = getattr(lead, 'raccordement', None)
    if not _vide(raccordement) and 'raccordement' not in utilisees:
        utilisees['raccordement'] = {'valeur': _json(raccordement), 'source': 'lead'}
    societe = entrees_de_la_societe(company)
    utilisees.update(societe)
    charge = {'entrees': empreinte, 'raccordement': raccordement or '',
              'societe': {cle: entree['valeur'] for cle, entree in sorted(societe.items())}}
    # T4-X7-022 — les SOUHAITS du lead (taille, batterie) décident des options
    # (``decisions.py``) sans entrer dans l'empreinte de l'adaptateur : « Avec » →
    # « Les deux options » laissait la carte à une seule option (empreinte égale ⇒
    # rien rangé). Posés seulement quand l'un est renseigné : l'empreinte d'un lead
    # sans souhait reste celle d'avant (aucune conception rangée ne devient périmée).
    # Seulement les marchés dont la décision les lit (:data:`SOUHAITS_PAR_MARCHE`) :
    # l'agricole n'en lit aucun, son empreinte reste celle d'avant T4-X7-022.
    souhaits = {c: _json(getattr(lead, c, None)) for c in SOUHAITS_PAR_MARCHE.get(marche_du_lead(lead), ())
                if not _vide(getattr(lead, c, None))}
    if souhaits:
        charge['souhaits'] = souhaits
    return _empreinte(charge)


def entrees_pour(lead, company, *, toit=None):
    """L'``EntreesConception`` du lead, par l'adaptateur de son marché.

    ``toit`` : la pose servie par le calepinage (entrée du moteur à l'étape
    6) ; son ``empreinte`` entre dans l'empreinte quand elle est donnée."""
    from apps.ventes.domain.entrees import empreinte_entrees, entrees_depuis_lead

    marche = marche_du_lead(lead)
    empreinte_pose = (getattr(toit, 'empreinte', '') or '') if toit is not None else ''
    if marche == 'residentiel':
        moteur = entrees_depuis_lead(lead, company)
        utilisees = _provenance_residentielle(lead, moteur)
        empreinte = empreinte_entrees(moteur) if moteur is not None else _empreinte(utilisees)
        resolution = None
    elif marche in MARCHES_CI:
        from apps.ventes.domain.etude_ci import resoudre_entrees
        # Le marché est posé par la couche lead elle-même : aucun corps.
        moteur, resolution = None, resoudre_entrees({}, lead=lead)
        utilisees = _provenance_resolue(resolution)
        empreinte = _empreinte({'marche': marche, 'entrees': utilisees})
    else:
        from apps.ventes.domain.pompage import resoudre_entrees
        moteur = None
        resolution = resoudre_entrees(company, {}, lead=lead)
        utilisees = _provenance_resolue(*resolution)
        empreinte = _empreinte({'marche': marche, 'entrees': utilisees})
    empreinte = completer(empreinte, lead, company, utilisees)
    if empreinte_pose:
        empreinte = _empreinte({'entrees': empreinte, 'pose': empreinte_pose})
    return EntreesConception(marche=marche, moteur=moteur, resolution=resolution,
                             entrees_utilisees=utilisees, empreinte=empreinte,
                             empreinte_pose=empreinte_pose, toit=toit)
