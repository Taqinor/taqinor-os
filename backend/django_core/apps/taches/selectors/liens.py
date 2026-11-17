"""Liens ERP d'une tâche, vérifiés (reference/donnees.md §5, invariant 23 ; conception/spec-6a-erp.md §3).

Trois fonctions, une seule vérité :

- `url_de_cible(cible, id)` : l'adresse ÉCRAN de l'objet, depuis les gabarits de
  `contract_samples/liens_cibles.json` (les mêmes que `entityRoutes.js`) ; `None` hors gabarit.
- `libelle_de_cible(user, cible, id)` : le libellé de l'objet tel que `user` a le droit de le voir,
  ou `None` (cible hors `CibleLiable`, inconnue, d'une autre société ou hors portée : la même
  réponse dans tous les cas — un refus vaut un introuvable, jamais un indice).
- `cible_visible(user, cible, id)` : vrai ssi un libellé existe.

Visibilité et libellé passent par les SEULES portes publiques des apps cibles
(`apps.crm.selectors_libelles.libelles_crm`, `apps.ventes.selectors_libelles.libelles_ventes`,
patron `agent/views.py` « libellés des objets nommés ») : aucun modèle d'une autre app n'est lu ici.
Appelants : TCH14 (forme LIEN), TCH36 (création), TCH49, TCH75, TCH102.
"""
import json
from functools import lru_cache
from pathlib import Path

from apps.taches.choix import CibleLiable

FICHIER_GABARITS = Path(__file__).resolve().parent.parent / 'contract_samples' / 'liens_cibles.json'
#: Longueur de `Tache.lien_libelle`.
LONGUEUR_LIBELLE = 200
#: Plus grand identifiant d'une clé primaire entière.
ID_MAX = 2 ** 31 - 1

#: cible → (app qui la possède, nom du paramètre de sa porte publique).
_PORTES = {
    CibleLiable.LEAD.value: ('crm', 'lead'),
    CibleLiable.CLIENT.value: ('crm', 'client'),
    CibleLiable.DEVIS.value: ('ventes', 'devis'),
}


@lru_cache(maxsize=1)
def gabarits():
    """`{cible: gabarit}` lus UNE fois dans `liens_cibles.json` (clé `exemple`)."""
    document = json.loads(FICHIER_GABARITS.read_text(encoding='utf-8'))
    return dict(document['exemple'])


def identifiant(valeur):
    """`valeur` en entier strictement positif, ou `None` (booléen, texte, négatif, trop grand)."""
    if isinstance(valeur, bool) or not isinstance(valeur, int):
        return None
    return valeur if 0 < valeur <= ID_MAX else None


def est_liable(cible):
    """Vrai ssi `cible` (« app.modele ») est une `CibleLiable`."""
    return cible in _PORTES


def url_de_cible(cible, id):
    """Adresse écran de l'objet (`/crm/leads?lead=9`), ou `None` hors gabarit ou id invalide."""
    gabarit = gabarits().get(cible) if isinstance(cible, str) else None
    pk = identifiant(id)
    if gabarit is None or pk is None:
        return None
    return gabarit.format(id=pk)


def _par_la_porte(user, app, cle, pk):
    if app == 'crm':
        from apps.crm.selectors_libelles import libelles_crm
        return libelles_crm(user, **{cle: pk})
    from apps.ventes.selectors_libelles import libelles_ventes
    return libelles_ventes(user, **{cle: pk})


def libelle_de_cible(user, cible, id):
    """Libellé de l'objet vu par `user` (≤ 200 caractères), ou `None` si `user` ne le voit pas."""
    pk = identifiant(id)
    if not est_liable(cible) or pk is None or user is None:
        return None
    app, cle = _PORTES[cible]
    libelle = _par_la_porte(user, app, cle, pk).get(cle)
    return None if libelle is None else str(libelle)[:LONGUEUR_LIBELLE]


def cible_visible(user, cible, id):
    """Vrai ssi `user` voit l'objet (`cible`, `id`) : refus et introuvable répondent pareil."""
    return libelle_de_cible(user, cible, id) is not None
