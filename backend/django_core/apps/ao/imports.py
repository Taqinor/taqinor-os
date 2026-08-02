"""Import CSV/XLSX d'un RELEVÉ de toiture (``apps.ao``) — AOF30.

Besoin réel : un technicien relève une toiture sur tableur, hors ligne, sans
tablette. Sans cette porte, son relevé se resaisit à la main — et une saisie
manuelle de 28 obstacles produit des écarts qu'on ne détecte qu'au calepinage.

Trois spécifications d'import :

* ``obstacles`` — repère, nature, x0, x1, y0, y1, hauteur, provenance ;
* ``chaines`` — libellé, axe, segments, mesure totale, tolérance ;
* ``avis`` — AOF169, l'AMONT du tunnel : les avis de marchés publiés
  (référence acheteur, acheteur, objet, montant estimé, dates de remise et
  d'ouverture, lot, mode de passation) créent les ``AppelOffre``
  correspondants, DÉDUPLIQUÉS par référence acheteur.

**Aucun scraping, jamais** (AOF169 / règle #5 du dépôt). La voie retenue est
l'IMPORT d'un fichier ou la saisie manuelle : aucun appel réseau vers le
portail national des marchés publics — ni vers aucun autre portail — n'existe
dans ce module, et un test de grep l'impose sur tout le paquet (le nom de
domaine lui-même fait partie des motifs interdits, il n'est donc écrit nulle
part ici). La question de la collecte AUTOMATIQUE est
traitée AILLEURS, dans une app séparée (``apps/veille_ao``, Groupe VAO), sous
gate intégral de la règle #5 : fichier ``tos_risk/`` + accord écrit du
fondateur avant la première exécution. Quand ce sas existera, ``importer_avis``
lui empruntera ses lignes au lieu d'un fichier — la fonction de création
(``services.creer_appel_offre_depuis_avis``) est déjà le point de contact
unique prévu pour ça, il n'y aura pas de second parseur à écrire.

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

from .models import AppelOffre, ChaineCotes, ObstacleAO, StatutCote

__all__ = [
    'FIELD_MAPS_AO', 'previsualiser', 'importer_obstacles',
    'importer_chaines', 'importer_avis',
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
    # AOF169 — les en-têtes d'un avis publié. Plusieurs libellés pointent le
    # même champ : un avis est recopié à la main depuis un portail ou un
    # bulletin, jamais exporté d'un gabarit imposé.
    'avis': {
        'reference': 'reference_acheteur',
        'reference_acheteur': 'reference_acheteur',
        'reference_marche': 'reference_acheteur',
        'numero': 'reference_acheteur', 'num_ao': 'reference_acheteur',
        'acheteur': 'acheteur', 'maitre_ouvrage': 'maitre_ouvrage',
        'organisme': 'acheteur', 'administration': 'acheteur',
        'objet': 'objet', 'intitule': 'objet', 'designation': 'objet',
        'lot': 'lot', 'numero_lot': 'lot',
        'montant': 'montant_estime', 'montant_estime': 'montant_estime',
        'estimation': 'montant_estime',
        'caution': 'caution_provisoire',
        'caution_provisoire': 'caution_provisoire',
        'date_limite': 'date_limite', 'date_remise': 'date_limite',
        'remise': 'date_limite', 'echeance': 'date_limite',
        'date_ouverture': 'date_ouverture_plis',
        'date_ouverture_plis': 'date_ouverture_plis',
        'ouverture': 'date_ouverture_plis',
        'mode_passation': 'mode_passation', 'mode': 'mode_passation',
        'type_marche': 'type_marche',
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


_MODES_PASSATION = {v for v, _ in AppelOffre.ModePassation.choices}
_TYPES_MARCHE = {v for v, _ in AppelOffre.TypeMarche.choices}

#: Formats de date acceptés dans un avis — le jour vient EN PREMIER (usage
#: marocain/français). ``%m/%d`` n'est PAS accepté : accepter les deux rendrait
#: « 03/04/2026 » ambigu, et une date de remise mal lue fait rater un dépôt.
_FORMATS_DATE = ('%d/%m/%Y', '%d-%m-%Y', '%Y-%m-%d', '%d.%m.%Y')


def _date(valeur, champ, erreurs):
    """``str`` -> ``date``, ou ``None``. Une date illisible est un REJET."""
    from datetime import date, datetime

    if valeur in (None, ''):
        return None
    if isinstance(valeur, datetime):
        return valeur.date()
    if isinstance(valeur, date):
        return valeur
    texte = str(valeur).strip()
    for fmt in _FORMATS_DATE:
        try:
            return datetime.strptime(texte, fmt).date()
        except ValueError:
            continue
    erreurs.append(
        f'{champ} : « {texte} » n\'est pas une date lisible '
        '(jj/mm/aaaa ou aaaa-mm-jj).')
    return None


def _valider_avis(donnees):
    """AOF169 — ``(champs, erreurs)`` pour une ligne d'avis de marché.

    ``reference_acheteur`` est OBLIGATOIRE : c'est la clé de déduplication.
    Sans elle un ré-import créerait des jumeaux, ce qui est exactement le
    défaut que cette tâche existe pour empêcher.
    """
    erreurs = []
    reference = (donnees.get('reference_acheteur') or '').strip()
    if not reference:
        erreurs.append(
            "référence acheteur : obligatoire (c'est la clé de "
            'déduplication d\'un avis).')
    objet = (donnees.get('objet') or '').strip()
    if not objet:
        erreurs.append("objet : obligatoire (un avis sans objet n'est pas "
                       'exploitable).')
    mode = (donnees.get('mode_passation') or '').strip().lower()
    if mode and mode not in _MODES_PASSATION:
        erreurs.append(f'mode de passation : « {mode} » inconnu.')
        mode = ''
    type_marche = (donnees.get('type_marche') or '').strip().lower()
    if type_marche and type_marche not in _TYPES_MARCHE:
        erreurs.append(f'type de marché : « {type_marche} » inconnu.')
        type_marche = ''

    champs = {
        'reference_acheteur': reference,
        'objet': objet,
        'acheteur': (donnees.get('acheteur') or '').strip(),
        'maitre_ouvrage': (donnees.get('maitre_ouvrage') or '').strip(),
        'lot': (donnees.get('lot') or '').strip(),
        'montant_estime': _decimal(
            donnees.get('montant_estime'), 'montant estimé', erreurs),
        'caution_provisoire': _decimal(
            donnees.get('caution_provisoire'), 'caution provisoire', erreurs),
        'date_limite': _date(
            donnees.get('date_limite'), 'date limite de remise', erreurs),
        'date_ouverture_plis': _date(
            donnees.get('date_ouverture_plis'), "date d'ouverture", erreurs),
        'mode_passation': mode or AppelOffre.ModePassation.APPEL_OUVERT,
        'type_marche': type_marche or AppelOffre.TypeMarche.PUBLIC,
    }
    return champs, erreurs


_VALIDATEURS = {
    'obstacles': _valider_obstacle,
    'chaines': _valider_chaine,
    'avis': _valider_avis,
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


# ── AOF169 — l'AMONT du tunnel : les avis de marchés publiés ───────────────

def importer_avis(company, fichier_octets, filename, *, user=None):
    """Importe des avis de marché — IDEMPOTENT par ``reference_acheteur``.

    Ré-importer le même fichier MET À JOUR les affaires existantes au lieu
    d'en créer des jumelles : un avis paraît, puis paraît RECTIFIÉ, et la
    deuxième parution ne doit pas ouvrir un second dossier.

    La création passe par ``services.creer_appel_offre_depuis_avis`` — point de
    contact UNIQUE, celui-là même qu'empruntera la veille (``apps/veille_ao``)
    quand son sas existera. **Aucun appel réseau ici** (règle #5) : la source
    est un FICHIER, jamais un portail.
    """
    from .services import creer_appel_offre_depuis_avis

    apercu = previsualiser(fichier_octets, filename, 'avis')
    crees = mis_a_jour = 0
    rejets = []
    for ligne in apercu['lignes']:
        if ligne['erreurs']:
            rejets.append(ligne)
            continue
        _ao, cree = creer_appel_offre_depuis_avis(
            company, dict(ligne['champs']), user=user)
        if cree:
            crees += 1
        else:
            mis_a_jour += 1
    return {'crees': crees, 'mis_a_jour': mis_a_jour, 'rejets': rejets}


def saisir_avis(company, avis, *, user=None):
    """Saisie MANUELLE d'un avis (même validation, même déduplication).

    L'écran de saisie et le fichier passent par le MÊME validateur : un avis
    tapé à la main ne doit pas avoir le droit d'être moins propre qu'un avis
    importé. Rend ``(appel_offre, cree, erreurs)`` — ``appel_offre`` vaut
    ``None`` quand la saisie est rejetée.
    """
    from .services import creer_appel_offre_depuis_avis

    champs, erreurs = _valider_avis(avis or {})
    if erreurs:
        return (None, False, erreurs)
    appel_offre, cree = creer_appel_offre_depuis_avis(
        company, champs, user=user)
    return (appel_offre, cree, [])
