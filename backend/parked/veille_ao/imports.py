"""VAO28 — import de fichier d'avis DANS LE SAS.

Coordination explicite avec AOF169 — les deux ne font PAS la même chose
--------------------------------------------------------------------------
``apps/ao/imports.importer_avis`` (AOF169) crée directement des **affaires**
(``AppelOffre``) : c'est l'amont du tunnel commercial, un humain a déjà
tranché. ``veille_ao`` alimente le **SAS** : un humain n'a rien tranché encore,
et il triera. Les deux chemins coexistent délibérément et ne doivent JAMAIS
fusionner — sinon un fichier d'agrégateur de 400 lignes ouvrirait 400 dossiers
dont 380 seraient du bruit.

Le parseur de fichier n'est pas réinventé : ``apps.dataimport.parsing.iter_rows``
lit CSV et XLSX, détecte séparateur et encodage, et ``normalize_header``
normalise les en-têtes. Seule la CARTE d'en-têtes est locale — un CSV
d'agrégateur ou de portail sectoriel n'a aucun gabarit imposé, et plusieurs
libellés courants doivent pointer le même champ.

Aucun appel réseau ici, jamais (règle #5) : la source est un FICHIER.
"""
from __future__ import annotations

import logging
from decimal import Decimal, InvalidOperation

from django.utils import timezone

logger = logging.getLogger(__name__)

#: Clé de spec déclarée dans ``platform.import_specs`` (VAO13).
SPEC_AVIS_VEILLE = 'avis_veille'

#: En-tête normalisé → champ du sas. Plusieurs libellés pointent le même champ :
#: ces fichiers viennent d'agrégateurs et de portails sectoriels différents,
#: jamais d'un gabarit imposé.
FIELD_MAPS_VEILLE = {
    SPEC_AVIS_VEILLE: {
        'reference': 'reference_avis', 'reference_avis': 'reference_avis',
        'ref': 'reference_avis', 'numero': 'reference_avis',
        'ref_consultation': 'ref_consultation',
        'consultation': 'ref_consultation',
        'organisme': 'org_acronyme', 'acronyme': 'org_acronyme',
        'objet': 'objet', 'intitule': 'objet', 'designation': 'objet',
        'acheteur': 'acheteur', 'acheteur_public': 'acheteur',
        'administration': 'acheteur', 'maitre_ouvrage': 'acheteur',
        'lieu': 'lieu', 'lieu_execution': 'lieu', 'ville': 'lieu',
        'region': 'region',
        'procedure': 'procedure', 'mode_passation': 'procedure',
        'categorie': 'categorie', 'type_marche': 'categorie',
        'lot': 'lot', 'numero_lot': 'lot',
        'date_publication': 'date_publication', 'publie_le': 'date_publication',
        'publication': 'date_publication',
        'date_limite': 'date_limite_remise', 'date_remise': 'date_limite_remise',
        'remise': 'date_limite_remise', 'echeance': 'date_limite_remise',
        'date_ouverture': 'date_ouverture', 'ouverture': 'date_ouverture',
        'montant': 'montant_estime', 'montant_estime': 'montant_estime',
        'estimation': 'montant_estime',
        'caution': 'caution_provisoire',
        'caution_provisoire': 'caution_provisoire',
        'url': 'url_detail', 'lien': 'url_detail', 'url_detail': 'url_detail',
    },
}

#: Catégories acceptées (tout le reste retombe sur « autre » — un import ne
#: doit pas échouer parce qu'un agrégateur écrit « Fourniture » au singulier).
_CATEGORIES = {'travaux': 'travaux', 'fournitures': 'fournitures',
               'fourniture': 'fournitures', 'services': 'services',
               'service': 'services'}

#: Formats de date rencontrés en pratique sur les fichiers marocains.
_FORMATS_DATE = ('%d/%m/%Y %H:%M', '%d/%m/%Y', '%Y-%m-%d %H:%M',
                 '%Y-%m-%d', '%d-%m-%Y')


def _mapper(ligne, carte):
    """Applique la carte d'en-têtes à une ligne brute."""
    from apps.dataimport.parsing import normalize_header

    sortie = {}
    for entete, valeur in (ligne or {}).items():
        champ = carte.get(normalize_header(entete))
        if champ:
            sortie[champ] = valeur
    return sortie


def _decimal(valeur, champ, erreurs):
    if valeur in (None, ''):
        return None
    try:
        return Decimal(str(valeur).replace(' ', '').replace(',', '.').strip())
    except (InvalidOperation, ValueError):
        erreurs.append(f'{champ} : « {valeur} » n\'est pas un nombre.')
        return None


def _date(valeur, champ, erreurs, *, avec_heure=False):
    """Lit une date en tolérant les formats courants ; rejette en FRANÇAIS."""
    from datetime import datetime

    if valeur in (None, ''):
        return None
    if hasattr(valeur, 'year'):
        return valeur
    texte = str(valeur).strip()
    for gabarit in _FORMATS_DATE:
        try:
            lue = datetime.strptime(texte, gabarit)
        except ValueError:
            continue
        if not avec_heure:
            return lue.date()
        if timezone.is_naive(lue):
            lue = timezone.make_aware(lue, timezone.get_current_timezone())
        return lue
    erreurs.append(f'{champ} : « {texte} » n\'est pas une date lisible '
                   '(attendu jj/mm/aaaa).')
    return None


def _valider(donnees):
    """``(champs, erreurs)`` — rejet LIGNE À LIGNE, avec un motif français.

    Une ligne fautive n'annule jamais les 399 autres : un fichier
    d'agrégateur contient toujours au moins une ligne bancale, et tout
    rejeter à cause d'elle rendrait l'import inutilisable.
    """
    erreurs = []
    objet = (donnees.get('objet') or '').strip()
    acheteur = (donnees.get('acheteur') or '').strip()
    if not objet and not acheteur:
        erreurs.append("Ligne vide : ni objet ni acheteur.")

    categorie = _CATEGORIES.get(
        (donnees.get('categorie') or '').strip().lower(), 'autre')

    champs = {
        'reference_avis': (donnees.get('reference_avis') or '').strip(),
        'ref_consultation': (donnees.get('ref_consultation') or '').strip(),
        'org_acronyme': (donnees.get('org_acronyme') or '').strip(),
        'objet': objet,
        'acheteur': acheteur,
        'lieu': (donnees.get('lieu') or '').strip(),
        'region': (donnees.get('region') or '').strip(),
        'procedure': (donnees.get('procedure') or '').strip(),
        'categorie': categorie,
        'lot': (donnees.get('lot') or '').strip(),
        'url_detail': (donnees.get('url_detail') or '').strip(),
        'date_publication': _date(donnees.get('date_publication'),
                                  'date de publication', erreurs),
        'date_limite_remise': _date(donnees.get('date_limite_remise'),
                                    'date limite', erreurs, avec_heure=True),
        'date_ouverture': _date(donnees.get('date_ouverture'),
                                "date d'ouverture", erreurs, avec_heure=True),
        'montant_estime': _decimal(donnees.get('montant_estime'),
                                   'montant estimé', erreurs),
        'caution_provisoire': _decimal(donnees.get('caution_provisoire'),
                                       'caution provisoire', erreurs),
    }
    return champs, erreurs


def previsualiser(fichier_octets, filename):
    """APERÇU — ne touche JAMAIS la base.

    Rend ``{'spec', 'lignes': [{'numero', 'champs', 'erreurs'}], 'valides',
    'rejetees'}``. L'aperçu et l'import appliquent EXACTEMENT le même
    validateur : ce que l'aperçu annonce est ce que l'import fera.
    """
    from apps.dataimport.parsing import iter_rows

    carte = FIELD_MAPS_VEILLE[SPEC_AVIS_VEILLE]
    _entetes, brutes = iter_rows(fichier_octets, filename)

    lignes = []
    valides = rejetees = 0
    for numero, brute in enumerate(brutes, start=2):
        champs, erreurs = _valider(_mapper(brute, carte))
        lignes.append({'numero': numero, 'champs': champs,
                       'erreurs': erreurs})
        if erreurs:
            rejetees += 1
        else:
            valides += 1
    return {'spec': SPEC_AVIS_VEILLE, 'lignes': lignes, 'valides': valides,
            'rejetees': rejetees}


def importer_avis(company, fichier_octets, filename, *, source=None,
                  user=None):
    """Importe des avis DANS LE SAS — idempotent par empreinte (VAO11).

    Ré-importer le même fichier MET À JOUR les avis existants au lieu d'en
    créer des jumeaux : un agrégateur republie chaque semaine le même stock,
    et un import qui double le sas le rend inutilisable en un mois.

    **Aucun ``AppelOffre`` n'est créé ici** : c'est un sas, un humain tranche
    (VAO30). La création d'affaires depuis un fichier est l'autre chemin,
    ``apps/ao/imports.importer_avis`` (AOF169) — les deux ne fusionnent pas.
    """
    from .scoring import mots_cles_actifs, scorer_avis
    from .services import (
        appliquer_regles_exclusion, enregistrer_avis, regles_actives,
        resoudre_source,
    )
    from .models import StatutAvis, TypeSource

    source = resoudre_source(company, source, defaut=TypeSource.IMPORT_CSV)
    apercu = previsualiser(fichier_octets, filename)
    mots = mots_cles_actifs(company)
    regles = regles_actives(company)

    crees = mis_a_jour = auto_ignores = 0
    rejets = []
    for ligne in apercu['lignes']:
        if ligne['erreurs']:
            rejets.append(ligne)
            continue
        champs = {k: v for k, v in ligne['champs'].items()
                  if v not in (None, '')}
        avis, cree, _niveau = enregistrer_avis(company, source, champs)
        scorer_avis(avis, mots)
        avis.save(update_fields=['score', 'mots_cles_declenches',
                                 'updated_at'])
        if avis.statut == StatutAvis.NOUVEAU and appliquer_regles_exclusion(
                avis, regles, user=user) is not None:
            auto_ignores += 1
        if cree:
            crees += 1
        else:
            mis_a_jour += 1

    logger.info('veille_ao: import %s — %s créés, %s mis à jour, %s rejets',
                filename, crees, mis_a_jour, len(rejets))
    return {'crees': crees, 'mis_a_jour': mis_a_jour,
            'auto_ignores': auto_ignores, 'rejets': rejets,
            'source_id': source.pk}
