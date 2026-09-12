"""NTSRV43 — Import CSV/XLSX en masse des compétences requises par catégorie.

Besoin réel : un gros client qui migre depuis un autre service-desk arrive
avec 80 catégories de tickets et leur matrice de compétences dans un tableur.
Les saisir une par une dans Paramètres est une demi-journée, et une erreur de
frappe sur une compétence ne se voit qu'au premier ticket mal affecté.

Cible d'import ``sav_categorie_competence``, déclarée par
``apps/sav/platform.py`` (``import_specs``, ARC32) — comme ``obstacles`` /
``chaines`` / ``avis`` d'``apps.ao``, c'est une cible à LECTEUR PROPRE : elle
n'a pas d'entrée dans ``dataimport.FIELD_MAPS`` parce que son écriture n'est
pas une création de fiche à plat mais le peuplement d'un ManyToMany
(``CategorieTicket.competences_requises``, NTSRV6) dont la clé humaine est un
CODE de compétence RH. La lecture bas niveau reste DÉLÉGUÉE à
``apps.dataimport.parsing`` (CSV/XLSX, séparateur, encodage, en-têtes) —
aucun parseur n'est réimplémenté ici.

Trois garanties, alignées sur le patron ``ImportJob`` standard :

1. **APERÇU** — ``previsualiser`` ne touche JAMAIS la base ;
2. **rejets LIGNE À LIGNE avec motif en français** — une compétence RH
   inexistante rapporte « ligne 7 : compétence inconnue » et n'annule pas les
   79 autres lignes ; JAMAIS un échec silencieux global (c'est le critère
   d'acceptation de NTSRV43) ;
3. **idempotence** — ré-importer le même fichier n'ajoute aucun doublon
   (``ManyToMany.add`` est idempotent) et ne retire jamais une compétence déjà
   posée à la main : l'import est ADDITIF.

Multi-tenant : la société est TOUJOURS celle de l'appelant (jamais lue du
fichier). Les compétences RH sont résolues par
``apps.rh.selectors.competences_par_code`` — ``apps.sav`` n'importe jamais
``apps.rh.models``.
"""
from __future__ import annotations

from apps.dataimport.parsing import iter_rows, normalize_header

__all__ = ['FIELD_MAP', 'CIBLE', 'previsualiser', 'importer']

#: Nom de la cible au registre plateforme (``platform.py::import_specs``).
CIBLE = 'sav_categorie_competence'

#: En-tête normalisé → champ logique. Plusieurs libellés courants pointent le
#: même champ : le fichier vient du tableur du client, jamais d'un gabarit
#: imposé.
FIELD_MAP = {
    'categorie': 'categorie',
    'catégorie': 'categorie',
    'categorie_ticket': 'categorie',
    'libelle': 'categorie',
    'libellé': 'categorie',
    'competence': 'competence',
    'compétence': 'competence',
    'code_competence': 'competence',
    'code': 'competence',
    'niveau': 'niveau_min',
    'niveau_min': 'niveau_min',
    'niveau_minimum': 'niveau_min',
    'niveau_requis': 'niveau_min',
}

#: Échelle ``rh.CompetenceEmploye`` : 0 non acquis → 4 expert.
NIVEAU_MIN = 0
NIVEAU_MAX = 4


def _mapper(brute):
    """Ligne brute {en-tête: valeur} → {champ logique: valeur texte}."""
    sortie = {}
    for entete, valeur in (brute or {}).items():
        champ = FIELD_MAP.get(normalize_header(entete))
        if champ and champ not in sortie:
            sortie[champ] = '' if valeur is None else str(valeur).strip()
    return sortie


def _valider(champs):
    """Valide UNE ligne. Renvoie ``(champs, erreurs)`` — erreurs en français,
    chacune NOMMANT le champ fautif (jamais un « ligne invalide » opaque)."""
    erreurs = []
    categorie = (champs.get('categorie') or '').strip()
    competence = (champs.get('competence') or '').strip()
    niveau_brut = (champs.get('niveau_min') or '').strip()

    if not categorie:
        erreurs.append('categorie : libellé de catégorie manquant.')
    if not competence:
        erreurs.append('competence : code de compétence manquant.')

    niveau = None
    if niveau_brut:
        try:
            niveau = int(float(niveau_brut.replace(',', '.')))
        except (TypeError, ValueError):
            erreurs.append(
                f"niveau_min : « {niveau_brut} » n'est pas un nombre "
                f'(échelle {NIVEAU_MIN} à {NIVEAU_MAX}).')
        else:
            if not NIVEAU_MIN <= niveau <= NIVEAU_MAX:
                erreurs.append(
                    f'niveau_min : {niveau} hors échelle '
                    f'({NIVEAU_MIN} à {NIVEAU_MAX}).')
                niveau = None
    return ({'categorie': categorie, 'competence': competence,
             'niveau_min': niveau}, erreurs)


def _lignes_validees(company, fichier_octets, filename):
    """Lit le fichier et valide chaque ligne, y compris l'EXISTENCE des
    compétences RH et des catégories de la société.

    Renvoie ``(lignes, index_competences, index_categories)`` où ``lignes``
    est la liste ``[{'numero', 'champs', 'erreurs'}]`` dans l'ordre du
    fichier. Aucune écriture."""
    from apps.rh.selectors import competences_par_code
    from .models import CategorieTicket

    _, brutes = iter_rows(fichier_octets, filename)
    lignes = []
    for numero, brute in enumerate(brutes, start=2):  # ligne 1 = en-têtes
        champs, erreurs = _valider(_mapper(brute))
        lignes.append({'numero': numero, 'champs': champs, 'erreurs': erreurs})

    codes = {ligne['champs']['competence'].lower()
             for ligne in lignes if ligne['champs']['competence']}
    index_competences = competences_par_code(company, codes)

    index_categories = {}
    for pk, libelle in (CategorieTicket.objects
                        .filter(company=company)
                        .values_list('id', 'libelle')):
        index_categories[(libelle or '').strip().lower()] = pk

    for ligne in lignes:
        champs = ligne['champs']
        code = (champs['competence'] or '').lower()
        if code and code not in index_competences:
            ligne['erreurs'].append(
                f'competence : « {champs["competence"]} » est inconnue du '
                'référentiel RH de la société (Ressources humaines → '
                'Compétences). Créez-la, ou corrigez le code.')
        libelle_saisi = champs['categorie'] or ''
        libelle = libelle_saisi.lower()
        if libelle and libelle not in index_categories:
            ligne['erreurs'].append(
                f'categorie : « {libelle_saisi} » est absente des catégories '
                'de ticket de la société. Créez-la dans Paramètres, ou '
                'corrigez le libellé.')
    return lignes, index_competences, index_categories


def _recapitulatif(lignes, appliquees=0):
    valides = sum(1 for ligne in lignes if not ligne['erreurs'])
    return {
        'cible': CIBLE,
        'lignes': lignes,
        'total_lignes': len(lignes),
        'valides': valides,
        'rejetees': len(lignes) - valides,
        'appliquees': appliquees,
    }


def previsualiser(company, fichier_octets, filename):
    """APERÇU — ne touche JAMAIS la base (NTSRV43).

    Renvoie ``{'cible', 'lignes': [{'numero', 'champs', 'erreurs'}],
    'total_lignes', 'valides', 'rejetees', 'appliquees': 0}``."""
    lignes, _, _ = _lignes_validees(company, fichier_octets, filename)
    return _recapitulatif(lignes)


def importer(company, fichier_octets, filename):
    """Applique les lignes VALIDES — additif et idempotent (NTSRV43).

    Les lignes en erreur sont rapportées telles quelles et simplement SAUTÉES :
    un fichier de 80 lignes dont 2 sont fautives en applique 78 (jamais un
    rollback global silencieux). Ré-importer le même fichier ne crée aucun
    doublon et ne retire jamais une compétence posée à la main.

    ``niveau_min`` est porté par la CATÉGORIE (``niveau_competence_min``,
    NTSRV6), pas par le couple catégorie×compétence : deux lignes de la même
    catégorie qui exigent des niveaux DIFFÉRENTS sont donc contradictoires et
    la seconde est rejetée avec son motif, plutôt qu'écraser la première en
    silence."""
    from .models import CategorieTicket

    lignes, index_competences, index_categories = _lignes_validees(
        company, fichier_octets, filename)

    niveau_par_categorie = {}
    competences_par_categorie = {}
    for ligne in lignes:
        if ligne['erreurs']:
            continue
        champs = ligne['champs']
        categorie_id = index_categories[champs['categorie'].lower()]
        niveau = champs['niveau_min']
        if niveau is not None:
            precedent = niveau_par_categorie.get(categorie_id)
            if precedent is not None and precedent != niveau:
                ligne['erreurs'].append(
                    f'niveau_min : la catégorie « {champs["categorie"]} » '
                    f'exige déjà le niveau {precedent} dans ce fichier '
                    f'(le niveau minimum est porté par la CATÉGORIE, pas par '
                    f'chaque compétence). Ligne ignorée.')
                continue
            niveau_par_categorie[categorie_id] = niveau
        competences_par_categorie.setdefault(categorie_id, []).append(
            index_competences[champs['competence'].lower()])

    appliquees = 0
    for categorie in CategorieTicket.objects.filter(
            company=company, id__in=competences_par_categorie):
        competences = competences_par_categorie[categorie.pk]
        categorie.competences_requises.add(*competences)
        niveau = niveau_par_categorie.get(categorie.pk)
        if niveau is not None and categorie.niveau_competence_min != niveau:
            categorie.niveau_competence_min = niveau
            categorie.save(update_fields=['niveau_competence_min'])
        appliquees += len(competences)

    return _recapitulatif(lignes, appliquees=appliquees)
