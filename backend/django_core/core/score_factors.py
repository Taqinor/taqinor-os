"""NTAI31 — explicabilité des scores : les facteurs contributifs.

Les scorers de ``core`` (``churn_risk``, ``win_probability``,
``payment_delay_risk``) rendaient déjà un dict ``factors``
avec la valeur NORMALISÉE de chaque composante — utile pour les tests, illisible
pour un commercial : « inactivity: 0.8219 » ne dit pas pourquoi le client est à
risque. Ce module fournit la couche d'explication : chaque signal devient une
phrase en langage clair, avec sa contribution SIGNÉE au score final, et les
scorers exposent les TROIS plus déterminants — « risque churn 72 % car : sans
activité depuis 300 jours, contrat expiré depuis 180 jours, 3 tickets SAV
ouverts ».

Deux garanties tenues par construction :

* **Purement déterministe** — aucune base, aucun réseau, aucun aléa : la même
  entrée donne la même liste, dans le même ordre (le tri départage les impacts
  égaux par la clé, jamais par l'ordre d'insertion d'un dict).
* **Dérivé, jamais inventé** — ``impact`` est la contribution RÉELLE de la
  composante au score rendu (sa part dans la moyenne pondérée, ou le delta
  qu'elle a appliqué pour un scorer multiplicatif), pas une importance devinée.

PÉRIMÈTRE — les trois modules cités sont les scorers de ``core`` qui rendent
UN score borné à partir de signaux pondérés, donc les seuls où « classer les
signaux » veut dire quelque chose. Deux autres modules prédictifs de ``core``
restent volontairement hors de cette couche, non par oubli :

* ``core.anomaly`` s'explique DÉJÀ par construction — un ``OutlierCandidate``
  porte sa valeur, la valeur attendue, son z-score signé et sa direction
  (``haut``/``bas``) : ajouter une liste de facteurs y serait redondant ;
* ``core.stock_reorder`` ne rend pas un score mais une DÉCISION chiffrée
  (point de commande, quantité suggérée, date de rupture) — ce sont des
  grandeurs métier directement lisibles, pas des contributions à classer.
"""
from __future__ import annotations

from dataclasses import dataclass

#: Nombre de facteurs exposés par défaut (« ses 3 principaux facteurs »).
LIMITE_FACTEURS = 3

SENS_POSITIF = '+'
SENS_NEGATIF = '-'

#: En-deçà de cette contribution absolue, un facteur n'explique rien et n'est
#: pas exposé (une composante à 0 n'a pas poussé le score).
EPSILON_IMPACT = 0.0001

__all__ = [
    'LIMITE_FACTEURS',
    'SENS_POSITIF',
    'SENS_NEGATIF',
    'Facteur',
    'facteur',
    'top_facteurs',
    'facteurs_ponderes',
    'nombre',
    'jours',
]


@dataclass(frozen=True)
class Facteur:
    """Un signal ayant poussé le score, expliqué en langage clair.

    ``cle`` est l'identifiant stable de la composante (même vocabulaire que le
    dict ``factors`` du scorer) ; ``libelle`` la phrase lisible, valeur
    observée incluse ; ``impact`` la contribution SIGNÉE au score final
    (positive = pousse le score vers le haut) ; ``sens`` le signe, figé pour
    que l'appelant n'ait pas à le recalculer.
    """

    cle: str
    libelle: str
    impact: float
    sens: str

    def as_dict(self):
        """Forme sérialisable (API / gabarit) — jamais de dataclass en JSON."""
        return {
            'cle': self.cle,
            'libelle': self.libelle,
            'impact': self.impact,
            'sens': self.sens,
        }


def facteur(cle, libelle, impact, *, decimales=4):
    """Construit un :class:`Facteur` en arrondissant et en figeant le sens."""
    valeur = round(float(impact), decimales)
    return Facteur(
        cle=cle, libelle=libelle, impact=valeur,
        sens=SENS_NEGATIF if valeur < 0 else SENS_POSITIF)


def top_facteurs(facteurs, limite=LIMITE_FACTEURS):
    """Les ``limite`` facteurs les plus déterminants, du plus fort au plus faible.

    Tri par contribution ABSOLUE décroissante (un facteur qui fait baisser le
    score de 0,2 explique autant qu'un qui le fait monter de 0,2), départagé
    par la clé pour rester STRICTEMENT déterministe. Les contributions
    négligeables sont écartées : elles n'expliquent rien.
    """
    retenus = [f for f in facteurs if abs(f.impact) >= EPSILON_IMPACT]
    retenus.sort(key=lambda f: (-abs(f.impact), f.cle))
    if limite is None:
        return retenus
    return retenus[:max(int(limite), 0)]


def facteurs_ponderes(composantes, poids_total, *, limite=LIMITE_FACTEURS):
    """Facteurs d'un scorer en MOYENNE PONDÉRÉE.

    ``composantes`` est une liste de ``(cle, libelle, valeur_normalisee,
    poids)``. La contribution d'une composante au score rendu est exactement
    ``valeur * poids / poids_total`` — la somme des contributions REDONNE le
    score (avant bornage), donc l'explication ne peut pas mentir sur le calcul.
    """
    if not composantes or not poids_total:
        return []
    facteurs = [
        facteur(cle, libelle, valeur * poids / poids_total)
        for cle, libelle, valeur, poids in composantes
    ]
    return top_facteurs(facteurs, limite=limite)


def nombre(valeur):
    """Formate un nombre pour une phrase : ``3`` et non ``3.0``."""
    try:
        reel = float(valeur)
    except (TypeError, ValueError):
        return str(valeur)
    if reel == int(reel):
        return str(int(reel))
    return f'{reel:g}'


def jours(valeur):
    """``'1 jour'`` / ``'12 jours'`` — l'accord se fait ici, pas dans 4 scorers."""
    texte = nombre(valeur)
    try:
        unitaire = abs(float(valeur)) < 2
    except (TypeError, ValueError):
        unitaire = False
    return f'{texte} jour' if unitaire else f'{texte} jours'
