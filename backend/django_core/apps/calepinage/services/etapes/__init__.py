"""CALX147 — LE REGISTRE DES ÉTAPES de la chaîne de pertes séquentielle.

CE QUE CE PAQUET EST
---------------------
Un seul mécanisme, et rien d'autre : ``services/chaine_pertes.py`` parcourt
``ORDRE_ETAPES`` et demande ICI le module de chaque poste. Une étape vit dans
SON fichier ``services/etapes/<poste>.py`` ; elle n'est jamais écrite dans
l'ordonnanceur, et l'ordonnanceur n'est jamais rouvert pour en ajouter une.

COMMENT UNE LANE D'ÉTAPE S'ENREGISTRE — LA RECETTE COMPLÈTE
-------------------------------------------------------------
1. Elle crée ``services/etapes/<poste>.py`` où ``<poste>`` est EXACTEMENT le
   nom qui figure déjà dans ``chaine_pertes.ORDRE_ETAPES`` (CALX148). Le nom
   est le seul point de rendez-vous : aucune ligne à ajouter nulle part,
   aucun import à déclarer, aucune table à éditer.
2. Elle y écrit une fonction PURE :

       def appliquer(serie, contexte):
           ...
           return serie, etape

   ``serie`` entre et ressort ; ``etape`` est un dict des SIX clés de
   :data:`CLES_ETAPE` (``libelle``, ``gain``, ``source``, ``entree``,
   ``reference``, ``motif_omission``). L'ordonnanceur y ajoute lui-même
   ``rang``, ``etape``, ``kwh_avant``, ``kwh_apres``, ``perte_kwh`` et
   ``perte_pct`` : une étape qui les renseignerait serait REFUSÉE en étant
   nommée. Les deux constructeurs :func:`etape_omise` et
   :func:`etape_appliquee` produisent la forme attendue — les utiliser évite
   d'avoir à connaître les six clés.
3. Entrée absente ⇒ l'étape est OMISE en nommant ce qui manque, et la série
   ressort INCHANGÉE (l'ordonnanceur le vérifie et refuse le contraire).
   Jamais un forfait, jamais un 0 % (D-CALX 7).
4. Une étape qui rend plus d'énergie qu'elle n'en a reçu déclare
   ``gain=True`` ; sans cela l'ordonnanceur la refuse en la nommant.
5. Le module d'étape n'appelle JAMAIS PVGIS lui-même : il lit la série de son
   pan par ``contexte['serie_du_pan']`` (CALX155). Une requête par PLAN,
   jamais par module.

CE QUE ``contexte`` PORTE (le même dict pour toutes les étapes, construit par
``services/simulation.py``, CALX5 — une étape ne lit JAMAIS la base) :

* ``reglages_simulation`` — la section société « simulation » (CALX145),
  ``{clé: {valeur, source, reference}}``. Se lit par :func:`reglage`, qui
  refuse une clé hors ``parametres_cles.registre('simulation')`` ; une clé
  non saisie rend ``None`` et l'étape s'omet en NOMMANT la clé.
* ``fiche_module`` / ``fiche_onduleur`` — les specs produit déjà résolues
  (``apps.stock`` par son sélecteur), ou ``{}``.
* ``site`` — ``{lat, lon, altitude_m, fuseau}`` ; la position du soleil se
  calcule par ``core.calepinage.soleil.position_solaire`` (CALX146), que
  l'étape importe directement (fonction pure du noyau, aucun état).
* ``meteo`` — le bloc de provenance météo (CALX143), dont
  ``horizon.origine`` et le compteur ``appels_pvgis`` (CALX155).
* ``plans`` — les pans du document, chacun au moins
  ``{cle, inclinaison_deg, azimut_pvgis_deg}``.
* ``ombrage`` — les lectures d'ombrage du constructeur (``solar_access``,
  matrice 12×24…), telles que le document les porte.
* ``postes_saisis`` — la LISTE PLATE des postes de pertes saisis
  (``resultat['pertes']``, D-CALX 11). Une étape ne la lit PAS : l'arbitrage
  entre le calculé et le saisi appartient à l'ordonnanceur (CALX149).
* ``serie_du_pan`` — l'accès météo partagé, installé par l'ordonnanceur.
* ``hash_entree`` — l'empreinte du document simulé.

LA SÉRIE, ET L'ÉNERGIE QU'ON Y LIT
------------------------------------
``serie`` est le document de CALX142 : ``{points: [...], pas_minutes,
colonne_energie}``. L'énergie de la série se lit par :func:`energie_kwh`, qui
somme UNE colonne nommée — celle que ``serie['colonne_energie']`` déclare,
sinon la première de :data:`ORDRE_COLONNES_ENERGIE` réellement présente. Une
étape qui change de porteur d'énergie (le continu qui devient de
l'alternatif) le DÉCLARE en posant ``colonne_energie`` sur la série qu'elle
rend : personne ne le devine à sa place. Aucune colonne lisible ⇒ l'énergie
est INCONNUE (``None``), et la cascade publie des ``null``, jamais des zéros.
"""
from __future__ import annotations

from importlib import import_module

#: Le pas de temps d'une série ``seriescalc`` : PVGIS la publie HEURE PAR
#: HEURE (``services/pvgis_serie.py`` ne lit pas d'autre pas). Ce n'est donc
#: pas un défaut inventé, c'est la cadence de la source — une série qui porte
#: son propre ``pas_minutes`` (CALX142) prime toujours.
PAS_MINUTES_PVGIS = 60

#: Les colonnes de points qui portent une PUISSANCE, et leur facteur vers le
#: kilowatt. Une colonne absente de cette table n'est pas une énergie.
FACTEURS_KW = {
    'p_ac_kw': 1.0,
    'p_dc_kw': 1.0,
    'p_w': 0.001,
}

#: L'ordre de recherche quand la série ne DÉCLARE pas sa colonne d'énergie :
#: du plus aval (l'alternatif livré) au plus amont (la colonne ``p_w`` que
#: ``services/pvgis_serie.py::serie_horaire`` écrit aujourd'hui).
ORDRE_COLONNES_ENERGIE = ('p_ac_kw', 'p_dc_kw', 'p_w')

#: Les SIX clés qu'une étape renseigne. Les six autres (``rang``, ``etape``,
#: ``kwh_avant``, ``kwh_apres``, ``perte_kwh``, ``perte_pct``) sont de
#: l'ordonnanceur seul — c'est ce qui rend la cascade continue par
#: construction et non par discipline.
CLES_ETAPE = ('libelle', 'gain', 'source', 'entree', 'reference',
              'motif_omission')

#: Le motif publié quand le module d'une étape déclarée n'existe pas encore.
MOTIF_NON_LIVREE = (
    "Étape non livrée : le module « {module} » n'existe pas encore dans le "
    'dépôt. La série ressort inchangée — aucun forfait n\'est appliqué.')

__all__ = [
    'PAS_MINUTES_PVGIS', 'FACTEURS_KW', 'ORDRE_COLONNES_ENERGIE',
    'CLES_ETAPE', 'MOTIF_NON_LIVREE', 'chemin_module', 'charger',
    'colonne_energie', 'energie_kwh', 'mettre_a_l_echelle', 'etape_omise',
    'etape_appliquee', 'reglage',
]


def chemin_module(poste):
    """Le chemin d'import du module d'une étape.

    Un seul endroit du dépôt le compose : une lane d'étape n'a jamais à
    écrire ce chemin elle-même.
    """
    return f'{__name__}.{poste}'


def charger(poste):
    """Le module de l'étape ``poste``, ou ``None`` s'il n'est pas livré.

    Résolution PARESSEUSE par le nom : une lane d'étape n'a donc aucune ligne
    à ajouter ici ni dans l'ordonnanceur. ``ModuleNotFoundError`` n'est avalée
    que si c'est BIEN ce module qui manque — une dépendance absente À
    L'INTÉRIEUR d'un module d'étape livré remonte telle quelle, sans quoi une
    étape cassée se lirait « non livrée » et personne ne verrait l'erreur.
    """
    chemin = chemin_module(poste)
    try:
        return import_module(chemin)
    except ModuleNotFoundError as erreur:
        if erreur.name != chemin:
            raise
        return None


def colonne_energie(serie):
    """La colonne de points qui porte l'énergie, ou ``None``.

    La DÉCLARATION de la série prime ; à défaut, la première colonne connue
    réellement présente dans les points. Rien n'est deviné au-delà.
    """
    if not isinstance(serie, dict):
        return None
    declaree = serie.get('colonne_energie')
    if declaree:
        return declaree if declaree in FACTEURS_KW else None
    points = serie.get('points') or []
    if not points or not isinstance(points[0], dict):
        return None
    for nom in ORDRE_COLONNES_ENERGIE:
        if nom in points[0]:
            return nom
    return None


def energie_kwh(serie):
    """L'énergie de la série en kWh, ou ``None`` si elle est INCONNUE.

    ``None`` n'est pas zéro : une série dont aucune colonne n'est lisible n'a
    pas une production nulle, elle a une production qu'on ne sait pas lire.
    La cascade publie alors des ``null`` (contrat CALX141), jamais des 0.
    """
    nom = colonne_energie(serie)
    if nom is None:
        return None
    facteur = FACTEURS_KW[nom]
    pas_minutes = serie.get('pas_minutes') or PAS_MINUTES_PVGIS
    heures = float(pas_minutes) / 60.0
    total = 0.0
    for point in serie.get('points') or []:
        valeur = point.get(nom)
        if valeur is None:
            continue
        try:
            total += float(valeur)
        except (TypeError, ValueError):
            continue
    return total * facteur * heures


def mettre_a_l_echelle(serie, facteur):
    """Une COPIE de la série dont la colonne d'énergie est multipliée.

    Pure : ni la série reçue ni ses points ne sont modifiés — deux étapes qui
    partagent la même série d'entrée ne peuvent donc pas se marcher dessus.
    """
    nom = colonne_energie(serie)
    if nom is None:
        return serie
    coefficient = float(facteur)
    points = []
    for point in serie.get('points') or []:
        valeur = point.get(nom)
        if valeur is None:
            points.append(point)
            continue
        copie = dict(point)
        try:
            copie[nom] = float(valeur) * coefficient
        except (TypeError, ValueError):
            points.append(point)
            continue
        points.append(copie)
    suite = dict(serie)
    suite['points'] = points
    suite['colonne_energie'] = nom
    return suite


def etape_omise(libelle, motif, *, champ=''):
    """Une étape OMISE : nommée, motivée, et sans le moindre chiffre.

    ``champ`` nomme l'entrée qui manque — c'est ce qui permet à l'écran de
    pointer LE champ à saisir au lieu d'un « non calculé » générique.
    """
    texte = motif.strip()
    if champ:
        texte = f'{texte} Champ manquant : « {champ} ».'
    return {
        'libelle': libelle,
        'gain': False,
        'source': None,
        'entree': None,
        'reference': None,
        'motif_omission': texte,
    }


def etape_appliquee(libelle, *, source, entree, reference='', gain=False):
    """Une étape APPLIQUÉE : elle nomme d'où vient l'entrée qu'elle a utilisée.

    ``source`` est obligatoire et non vide : une étape qui s'applique sans
    pouvoir dire d'où vient son chiffre est refusée par l'ordonnanceur.
    """
    return {
        'libelle': libelle,
        'gain': bool(gain),
        'source': source,
        'entree': entree,
        'reference': reference,
        'motif_omission': '',
    }


def reglage(contexte, cle):
    """Le réglage société ``cle`` de la section « simulation », ou ``None``.

    La clé DOIT figurer au registre de CALX145 : une clé hors registre est
    une faute de frappe de l'étape, pas une absence de saisie — elle est donc
    refusée en la nommant. Une clé du registre jamais saisie rend ``None`` :
    l'étape s'omet alors en nommant la clé, sans rien supposer.
    """
    from apps.calepinage.services.parametres_cles import (
        SECTION_SIMULATION, registre)

    connues = registre(SECTION_SIMULATION)
    if cle not in connues:
        raise KeyError(
            f'La clé de réglage « {cle} » ne figure pas au registre de la '
            f'section « {SECTION_SIMULATION} » (CALX145) : ajoutez-la EN FIN '
            f'de CLES_SIMULATION avant de la lire.')
    valeurs = (contexte or {}).get('reglages_simulation') or {}
    saisie = valeurs.get(cle)
    if not isinstance(saisie, dict):
        return None
    if saisie.get('valeur') is None or not saisie.get('source'):
        return None
    return saisie
