"""ACAL627 — contrôler UNE chaîne SANS dessin (CAP-D3-10).

« 22 modules sur cet onduleur ? » avant de dessiner : module, onduleur
(fiches du stock de la société), nombre de modules et températures SAISIES
(obligatoires : aucune valeur par défaut, à la différence du contrôle du
devis). La fenêtre vient du noyau, non modifié :
``core/electrique/chaines.py::fenetre_admissible``. Chaque contrôle NOMME sa
borne et sa valeur ; une fiche incomplète rend ``indetermine`` avec les
champs manquants (jamais un faux vert). Lecture pure : rien n'est écrit.
Forme du contrat ``contract_samples/calepinage_controle_chaine.json``.
"""
from __future__ import annotations

__all__ = ['ControleInvalide', 'controle_chaine']

SOURCE = 'fiches module et onduleur'


class ControleInvalide(ValueError):
    """Un refus NOMMÉ (400), ou un produit introuvable (404)."""

    def __init__(self, champ, message, *, introuvable=False):
        super().__init__(message)
        self.champ = champ
        self.introuvable = introuvable


def _volts(valeur):
    return '{:,.0f}'.format(valeur).replace(',', ' ') + ' V'


def _controle(code, libelle, valeur, borne, nom_borne, *, haut, bloquant):
    conforme = None
    if valeur > 0 and borne > 0:
        conforme = valeur <= borne + 1e-9 if haut else valeur >= borne - 1e-9
    return {'code': code, 'libelle': libelle, 'valeur': round(valeur, 1),
            'borne': '%s (%s)' % (nom_borne, _volts(borne)),
            'conforme': conforme, 'bloquant': bloquant, 'source': SOURCE}


def _controler_chaine(module_specs, onduleur_specs, nombre_modules,
                      temperature_min_c, temperature_max_c):
    """Le verdict pur d'une chaîne de ``nombre_modules`` modules."""
    from core.electrique.chaines import fenetre_admissible

    from .chaines import specs_module, specs_onduleur

    module, manque_module = specs_module(module_specs or {})
    onduleur, manque_onduleur = specs_onduleur(onduleur_specs or {})
    manquantes = (['Module : %s' % m for m in manque_module]
                  + ['Onduleur : %s' % m for m in manque_onduleur])
    if manquantes:
        return {'verdict': 'indetermine', 'controles': [],
                'longueur_min': None, 'longueur_max': None,
                'manquantes': manquantes}
    fenetre = fenetre_admissible(module, onduleur, temperature_min_c,
                                 temperature_max_c)
    n = nombre_modules
    demarrage = ("tension de démarrage de l'onduleur"
                 if onduleur.v_demarrage_v is not None
                 else "bas de plage MPPT de l'onduleur (démarrage non publié)")
    controles = [
        _controle('voc_froid', 'Tension à vide à froid de la chaîne',
                  n * fenetre.voc_froid_unitaire_v, onduleur.v_max_abs,
                  "tension maximale absolue de l'onduleur", haut=True,
                  bloquant=True),
        _controle('mppt_haut', 'Tension MPP à froid de la chaîne',
                  n * fenetre.vmp_froid_unitaire_v, onduleur.mppt_v_max,
                  "haut de plage MPPT de l'onduleur", haut=True,
                  bloquant=False),
        _controle('mppt_bas', 'Tension MPP à chaud de la chaîne',
                  n * fenetre.vmp_chaud_unitaire_v, onduleur.mppt_v_min,
                  "bas de plage MPPT de l'onduleur", haut=False,
                  bloquant=False),
        _controle('demarrage', 'Tension MPP à chaud face au démarrage',
                  n * fenetre.vmp_chaud_unitaire_v,
                  onduleur.tension_demarrage_v, demarrage, haut=False,
                  bloquant=True),
    ]
    rouges = [c for c in controles if c['conforme'] is False]
    verdict = ('bloquant' if any(c['bloquant'] for c in rouges)
               else 'alerte' if rouges else 'conforme')
    return {'verdict': verdict, 'controles': controles,
            'longueur_min': fenetre.longueur_min,
            'longueur_max': fenetre.longueur_max, 'manquantes': []}


def _temperature(corps, champ):
    from .valeurs import nombre

    valeur = nombre(corps.get(champ))
    if valeur is None:
        raise ControleInvalide(champ, "« %s » est obligatoire : saisissez la "
                               "température en °C." % champ)
    return valeur


def controle_chaine(company, corps):
    """``_controler_chaine`` sur les fiches du stock de ``company``."""
    from apps.stock.selectors import get_produit_scoped, specs_for_produit

    corps = corps if isinstance(corps, dict) else {}
    tmin = _temperature(corps, 'temperature_min_c')
    tmax = _temperature(corps, 'temperature_max_c')
    nombre_modules = corps.get('nombre_modules')
    if isinstance(nombre_modules, bool) or not isinstance(
            nombre_modules, int) or nombre_modules < 1:
        raise ControleInvalide('nombre_modules', "« nombre_modules » doit "
                               "être un entier strictement positif.")
    fiches = {}
    for champ in ('module_produit', 'onduleur_produit'):
        identifiant = str(corps.get(champ) if not isinstance(
            corps.get(champ), bool) else '')
        if not (identifiant.isascii() and identifiant.isdigit()
                and len(identifiant) < 19):
            raise ControleInvalide(champ, "« %s » attend l'identifiant "
                                   "numérique d'un produit." % champ)
        produit = get_produit_scoped(company, int(identifiant))
        if produit is None:
            raise ControleInvalide(champ, "Produit introuvable dans le "
                                   "catalogue de la société.",
                                   introuvable=True)
        fiches[champ] = specs_for_produit(produit) or {}
    return _controler_chaine(fiches['module_produit'],
                             fiches['onduleur_produit'], nombre_modules, tmin,
                             tmax)
