"""VAO9 — le score d'un avis, et la liste des mots qui l'ont déclenché.

Deux exigences de conception, toutes les deux volontaires :

1. **Aucun mot-clé littéral dans ce fichier.** Les mots-clés sont de la
   DONNÉE (``MotCleVeille``) : ajouter « ombrière photovoltaïque » doit être
   un geste d'écran, pas un déploiement. Une garde de test vérifie qu'aucun
   littéral de mot-clé métier ne réapparaît ici.
2. **On stocke POURQUOI l'avis est remonté.** Un score nu est un oracle :
   l'utilisateur doit voir la liste des mots déclenchés, sinon il ne peut ni
   corriger le réglage ni faire confiance au tri.

Ce module est PUR : il ne lit ni n'écrit la base. Il reçoit des mots-clés
déjà chargés et rend un couple ``(score, mots_declenches)``.
"""
from __future__ import annotations

import unicodedata

from .models import SCORE_MAX, MotCleVeille


def normaliser(texte):
    """Casse, accents et espaces neutralisés — la comparaison doit survivre à
    « PHOTOVOLTAÏQUE », « photovoltaique » et aux doubles espaces.
    """
    if not texte:
        return ''
    decompose = unicodedata.normalize('NFKD', str(texte))
    sans_accent = ''.join(
        c for c in decompose if not unicodedata.combining(c))
    return ' '.join(sans_accent.lower().split())


def texte_analysable(objet='', acheteur=''):
    """Le texte sur lequel les mots-clés sont cherchés : objet + acheteur.

    L'acheteur compte : « ONEE — Branche Eau » ou « Commune de … » oriente le
    tri autant que l'objet.
    """
    return normaliser(f'{objet} {acheteur}')


def calculer_score(objet='', acheteur='', mots_cles=()):
    """Renvoie ``(score, mots_declenches)`` pour un avis.

    * ``mots_cles`` : itérable de ``MotCleVeille`` (déjà filtré sur ``actif``
      par l'appelant, ou par ``mots_cles_actifs``).
    * le score est la somme pondérée des mots déclenchés, **bornée** à
      ``SCORE_MAX`` : un avis qui déclenche huit mots n'est pas huit fois plus
      intéressant qu'un avis qui en déclenche deux.
    * ``mots_declenches`` est la liste des LIBELLÉS d'origine (accentués,
      lisibles), dédoublonnée et triée pour être stable d'une collecte à
      l'autre.
    """
    texte = texte_analysable(objet, acheteur)
    if not texte:
        return 0, []

    total = 0
    declenches = []
    vus = set()
    for mot in mots_cles:
        aiguille = normaliser(mot.libelle)
        if not aiguille or aiguille not in texte:
            continue
        if aiguille in vus:
            continue
        vus.add(aiguille)
        declenches.append(mot.libelle)
        total += int(mot.poids or 0)

    return min(total, SCORE_MAX), sorted(declenches)


def mots_cles_actifs(company):
    """Les mots-clés actifs d'UNE société (jamais tous les tenants)."""
    return list(MotCleVeille.objects.filter(company=company).actifs())


def scorer_avis(avis, mots_cles=None):
    """Calcule et POSE le score + les mots déclenchés sur un ``AvisMarche``.

    Ne sauvegarde pas : l'appelant décide quand écrire (la collecte écrit une
    fois par avis, dans sa propre transaction).
    """
    if mots_cles is None:
        mots_cles = mots_cles_actifs(avis.company)
    avis.score, avis.mots_cles_declenches = calculer_score(
        avis.objet, avis.acheteur, mots_cles)
    return avis
