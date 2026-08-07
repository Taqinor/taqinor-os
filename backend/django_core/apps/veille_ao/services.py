"""Services (écritures / orchestration) du module « Veille appels d'offres ».

FRONTIÈRE INTER-APPS (import-linter) — une AUTRE app qui a besoin d'écrire
dans ce module ou d'orchestrer une action passe par une fonction de CE fichier
(jamais en important ``apps.veille_ao.models``/``.views`` directement).

VAO10 — les règles d'exclusion. Le principe qui gouverne tout ce fichier :
**aucun filtrage muet**. Quand une règle écarte un avis, l'avis GARDE la trace
de la règle qui l'a écarté, et la règle compte ses applications. Un utilisateur
doit toujours pouvoir répondre à « pourquoi je ne vois pas cet avis ? » et
faire marche arrière en un geste (désactiver la règle).
"""
from __future__ import annotations

from django.db.models import F

from .models import AvisMarche, PorteeExclusion, RegleExclusion, StatutAvis
from .scoring import normaliser


def _valeur_de_l_avis(avis, portee):
    """Le champ de l'avis que cette portée compare."""
    if portee == PorteeExclusion.ACHETEUR:
        return avis.acheteur or ''
    if portee == PorteeExclusion.LIBELLE:
        return avis.objet or ''
    if portee == PorteeExclusion.CATEGORIE:
        return avis.categorie or ''
    if portee == PorteeExclusion.REGION:
        return avis.region or ''
    return ''


def regle_mord(regle, avis):
    """Cette règle écarte-t-elle cet avis ?

    La catégorie est comparée à l'IDENTIQUE (c'est une valeur fermée) ; les
    trois autres portées sont des recherches de sous-chaîne normalisées
    (casse, accents et espaces neutralisés).
    """
    cible = normaliser(_valeur_de_l_avis(avis, regle.portee))
    aiguille = normaliser(regle.valeur)
    if not aiguille or not cible:
        return False
    if regle.portee == PorteeExclusion.CATEGORIE:
        return cible == aiguille
    return aiguille in cible


def regles_actives(company):
    """Les règles actives d'UNE société (jamais tous les tenants)."""
    return list(RegleExclusion.objects.filter(company=company).actives())


def regle_correspondante(avis, regles=None):
    """La PREMIÈRE règle active qui écarte cet avis, ou ``None``.

    Lecture pure : ne modifie ni l'avis ni la règle.
    """
    if regles is None:
        regles = regles_actives(avis.company)
    for regle in regles:
        if regle_mord(regle, avis):
            return regle
    return None


def appliquer_regles_exclusion(avis, regles=None, enregistrer=True):
    """Marque l'avis ``ignore`` s'il est capté par une règle active.

    Renvoie la règle appliquée, ou ``None`` si aucune ne mord.

    Deux garanties non négociables :
      * l'avis ENREGISTRE quelle règle l'a filtré (jamais un filtrage muet) ;
      * la règle incrémente son compteur d'application de façon atomique
        (``F()``), jamais par lecture-modification-écriture.
    """
    regle = regle_correspondante(avis, regles)
    if regle is None:
        return None

    avis.statut = StatutAvis.IGNORE
    avis.regle_exclusion = regle
    if enregistrer:
        avis.save(update_fields=['statut', 'regle_exclusion', 'updated_at'])
        RegleExclusion.objects.filter(pk=regle.pk).update(
            compteur_application=F('compteur_application') + 1)
        regle.refresh_from_db(fields=['compteur_application'])
    return regle


def proposer_regle_pour_avis(avis, portee=PorteeExclusion.ACHETEUR):
    """Propose une règle à partir d'un avis — **sans jamais la créer**.

    « Ignorer » doit APPRENDRE, mais l'apprentissage ne se fait pas en
    douce : l'écran propose, l'utilisateur décide. Cette fonction rend un
    brouillon (portée, valeur, motif suggéré) et n'écrit rien en base.

    ``existe_deja`` dit si une règle identique est déjà enregistrée, pour que
    l'écran propose de la RÉACTIVER plutôt que d'en créer une jumelle.
    """
    valeur = (_valeur_de_l_avis(avis, portee) or '').strip()
    libelle_portee = PorteeExclusion(portee).label
    existante = RegleExclusion.objects.filter(
        company=avis.company, portee=portee, valeur=valeur).first()
    return {
        'portee': portee,
        'portee_libelle': libelle_portee,
        'valeur': valeur,
        'motif_suggere': (
            f'Ignoré depuis un avis — {libelle_portee.lower()} « {valeur} »'
            if valeur else ''),
        'existe_deja': existante is not None,
        'regle_existante_id': existante.pk if existante else None,
        'regle_existante_active': (
            existante.actif if existante is not None else None),
    }


def avis_ignores_par(regle):
    """Les avis que CETTE règle a écartés (pour l'écran de la règle)."""
    return AvisMarche.objects.filter(
        company=regle.company, regle_exclusion=regle)
