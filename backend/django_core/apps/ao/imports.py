"""Import CSV/XLSX d'un RELEVÉ de toiture (``apps.ao``) — AOF30.

Besoin réel : un technicien relève une toiture sur tableur, hors ligne, sans
tablette. Sans cette porte, son relevé se resaisit à la main — et une saisie
manuelle de 28 obstacles produit des écarts qu'on ne détecte qu'au calepinage.

Deux spécifications d'import :

* ``obstacles`` — repère, nature, x0, x1, y0, y1, hauteur, provenance ;
* ``chaines`` — libellé, axe, segments, mesure totale, tolérance.

Trois garanties :

1. **APERÇU avant validation** : ``previsualiser`` ne touche jamais la base ;
2. **rejets LIGNE À LIGNE avec motif en français** : une provenance invalide
   n'annule pas les 27 autres lignes ;
3. **idempotence par repère** (obstacles) / par libellé (chaînes) : ré-importer
   le même fichier MET À JOUR, il ne duplique pas.

La lecture bas niveau est déléguée à ``apps.dataimport.parsing`` (jamais
réimplémentée) : détection CSV/XLSX, séparateur, encodage et normalisation
d'en-têtes y vivent déjà.
"""
from __future__ import annotations

import re
from decimal import Decimal, InvalidOperation

from apps.dataimport.parsing import normalize_header

from .models import ChaineCotes, ObstacleAO, StatutCote

__all__ = [
    'FIELD_MAPS_AO', 'previsualiser', 'importer_obstacles',
    'importer_chaines',
]

#: En-tête normalisé → champ. Même forme que ``dataimport.FIELD_MAPS`` :
#: plusieurs libellés courants pointent le même champ (les relevés viennent de
#: tableurs écrits à la main, jamais d'un gabarit imposé).
FIELD_MAPS_AO = {
    'obstacles': {
        'repere': 'repere', 'rep': 'repere',
        'nature': 'nature', 'type': 'nature',
        'designation': 'designation', 'libelle': 'designation',
        'x0': 'rect_x0_m', 'x1': 'rect_x1_m',
        'y0': 'rect_y0_m', 'y1': 'rect_y1_m',
        'hauteur': 'hauteur_m', 'hauteur_m': 'hauteur_m',
        'provenance': 'provenance', 'source': 'provenance',
        'hors_zone_pv': 'hors_zone_pv',
    },
    'chaines': {
        'libelle': 'libelle', 'nom': 'libelle', 'chaine': 'libelle',
        'axe': 'axe',
        'segments': 'segments', 'cotes': 'segments',
        'mesure': 'mesure_globale_m', 'mesure_totale': 'mesure_globale_m',
        'total': 'mesure_globale_m',
        'tolerance': 'tolerance_m', 'tolerance_m': 'tolerance_m',
    },
}

_NATURES = {v for v, _ in ObstacleAO.Nature.choices}
_PROVENANCES = {v for v, _ in ObstacleAO.Provenance.choices}
_AXES = {v for v, _ in ChaineCotes.Axe.choices}
_STATUTS_COTE = {v for v, _ in StatutCote.choices}


def _mapper(ligne, carte):
    """Applique la carte d'en-têtes à une ligne brute."""
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
        return Decimal(str(valeur).replace(',', '.').strip())
    except (InvalidOperation, ValueError):
        erreurs.append(f'{champ} : « {valeur} » n\'est pas un nombre.')
        return None


def _segments(valeur, erreurs):
    """``A→B=19.36|B→C=7.92:MESURE`` → liste de segments normalisée.

    Séparateur ``|`` (ou ``;``) entre segments, ``=`` avant la valeur, ``:``
    avant un statut OPTIONNEL. Le ``|`` est le séparateur RECOMMANDÉ : un
    fichier CSV dont les cellules contiennent des ``;`` fait basculer la
    détection automatique de délimiteur, et toute la ligne se disloque.

    Format volontairement TOLÉRANT : un statut inconnu est signalé sans jeter
    la ligne entière.
    """
    if valeur in (None, ''):
        return []
    segments = []
    for brut in re.split(r'[|;]', str(valeur)):
        brut = brut.strip()
        if not brut:
            continue
        statut = StatutCote.MESURE.value
        if ':' in brut:
            brut, statut_brut = brut.rsplit(':', 1)
            statut_brut = statut_brut.strip().upper()
            if statut_brut not in _STATUTS_COTE:
                erreurs.append(
                    f'segment « {brut.strip()} » : statut inconnu '
                    f'« {statut_brut} ».')
            else:
                statut = statut_brut
        if '=' not in brut:
            erreurs.append(
                f'segment « {brut} » : format attendu « libellé=valeur ».')
            continue
        libelle, valeur_brute = brut.split('=', 1)
        try:
            valeur_m = float(str(valeur_brute).replace(',', '.').strip())
        except ValueError:
            erreurs.append(
                f'segment « {libelle.strip()} » : « {valeur_brute.strip()} » '
                "n'est pas un nombre.")
            continue
        segments.append({
            'libelle': libelle.strip(), 'valeur_m': valeur_m,
            'statut': statut,
        })
    return segments


def _valider_obstacle(donnees):
    """Renvoie ``(champs, erreurs)`` pour une ligne d'obstacle."""
    erreurs = []
    repere = (donnees.get('repere') or '').strip()
    if not repere:
        erreurs.append(
            'repère : obligatoire (il sert de clé de rapprochement).')
    nature = (donnees.get('nature') or '').strip().lower()
    if nature and nature not in _NATURES:
        erreurs.append(f'nature : « {nature} » inconnue.')
        nature = ''
    provenance = (donnees.get('provenance') or '').strip().upper()
    if provenance and provenance not in _PROVENANCES:
        erreurs.append(f'provenance : « {provenance} » inconnue.')
        provenance = ''
    champs = {
        'repere': repere,
        'designation': (donnees.get('designation') or '').strip(),
        'nature': nature or ObstacleAO.Nature.CAISSON_TECHNIQUE,
        'provenance': provenance or ObstacleAO.Provenance.MESURE,
        'rect_x0_m': _decimal(donnees.get('rect_x0_m'), 'x0', erreurs),
        'rect_x1_m': _decimal(donnees.get('rect_x1_m'), 'x1', erreurs),
        'rect_y0_m': _decimal(donnees.get('rect_y0_m'), 'y0', erreurs),
        'rect_y1_m': _decimal(donnees.get('rect_y1_m'), 'y1', erreurs),
        'hauteur_m': _decimal(donnees.get('hauteur_m'), 'hauteur', erreurs),
        'hors_zone_pv': str(
            donnees.get('hors_zone_pv') or '').strip().lower() in (
                '1', 'true', 'vrai', 'oui'),
    }
    return champs, erreurs


def _valider_chaine(donnees):
    erreurs = []
    libelle = (donnees.get('libelle') or '').strip()
    if not libelle:
        erreurs.append(
            'libellé : obligatoire (il sert de clé de rapprochement).')
    axe = (donnees.get('axe') or '').strip().lower()
    if axe and axe not in _AXES:
        erreurs.append(f'axe : « {axe} » inconnu.')
        axe = ''
    champs = {
        'libelle': libelle,
        'axe': axe or ChaineCotes.Axe.X,
        'segments': _segments(donnees.get('segments'), erreurs),
        'mesure_globale_m': _decimal(
            donnees.get('mesure_globale_m'), 'mesure totale', erreurs),
    }
    tolerance = _decimal(donnees.get('tolerance_m'), 'tolérance', erreurs)
    if tolerance is not None:
        champs['tolerance_m'] = tolerance
    return champs, erreurs


_VALIDATEURS = {
    'obstacles': _valider_obstacle,
    'chaines': _valider_chaine,
}


def previsualiser(fichier_octets, filename, spec):
    """APERÇU d'un import — ne touche JAMAIS la base (AOF30).

    Renvoie ``{'spec', 'lignes': [{'numero', 'champs', 'erreurs'}],
    'valides', 'rejetees'}``. Un rejet est LIGNE À LIGNE : une provenance
    invalide n'annule pas les 27 autres lignes du relevé.
    """
    from apps.dataimport.parsing import iter_rows

    carte = FIELD_MAPS_AO[spec]
    valideur = _VALIDATEURS[spec]
    _, lignes_brutes = iter_rows(fichier_octets, filename)

    lignes = []
    valides = rejetees = 0
    for numero, brute in enumerate(lignes_brutes, start=2):
        champs, erreurs = valideur(_mapper(brute, carte))
        lignes.append({'numero': numero, 'champs': champs,
                       'erreurs': erreurs})
        if erreurs:
            rejetees += 1
        else:
            valides += 1
    return {'spec': spec, 'lignes': lignes, 'valides': valides,
            'rejetees': rejetees}


def importer_obstacles(toiture, fichier_octets, filename, *, releve=None):
    """Importe des obstacles — IDEMPOTENT par ``repere`` (AOF30).

    Ré-importer le même fichier MET À JOUR les obstacles existants au lieu
    d'en créer des jumeaux. Les lignes rejetées sont renvoyées avec leur motif
    en français ; elles n'empêchent JAMAIS les autres de passer.
    """
    apercu = previsualiser(fichier_octets, filename, 'obstacles')
    crees = mis_a_jour = 0
    rejets = []
    for ligne in apercu['lignes']:
        if ligne['erreurs']:
            rejets.append(ligne)
            continue
        champs = dict(ligne['champs'])
        repere = champs.pop('repere')
        obstacle = ObstacleAO.objects.filter(
            company=toiture.company, toiture=toiture, repere=repere).first()
        if obstacle is None:
            obstacle = ObstacleAO(
                company=toiture.company, toiture=toiture, repere=repere)
            crees += 1
        else:
            mis_a_jour += 1
        for nom, valeur in champs.items():
            setattr(obstacle, nom, valeur)
        if releve is not None:
            obstacle.releve = releve
        obstacle.appliquer_degagement()
        obstacle.save()
    return {'crees': crees, 'mis_a_jour': mis_a_jour, 'rejets': rejets}


def importer_chaines(toiture, fichier_octets, filename, *, releve=None):
    """Importe des chaînes de cotes — IDEMPOTENT par ``libelle`` (AOF30)."""
    apercu = previsualiser(fichier_octets, filename, 'chaines')
    crees = mis_a_jour = 0
    rejets = []
    for ligne in apercu['lignes']:
        if ligne['erreurs']:
            rejets.append(ligne)
            continue
        champs = dict(ligne['champs'])
        libelle = champs.pop('libelle')
        chaine = ChaineCotes.objects.filter(
            company=toiture.company, toiture=toiture, libelle=libelle).first()
        if chaine is None:
            chaine = ChaineCotes(
                company=toiture.company, toiture=toiture, libelle=libelle)
            crees += 1
        else:
            mis_a_jour += 1
        for nom, valeur in champs.items():
            setattr(chaine, nom, valeur)
        if releve is not None:
            chaine.releve = releve
        chaine.recalculer_fermeture()
        chaine.save()
    return {'crees': crees, 'mis_a_jour': mis_a_jour, 'rejets': rejets}
