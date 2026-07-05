"""XACC24 — Validateur RIB marocain (clé mod 97), fondation partagée.

Comme les autres modules de ``core`` (``core.rules``, ``core.forecast``…),
reste une couche de BASE — contrat import-linter
``core-foundation-is-a-base-layer`` : n'importe AUCUNE app métier, aucun
modèle, aucune migration. Fonctions PURES, déterministes, sans base de
données ni réseau.

Le RIB marocain compte 24 chiffres — code banque (5) + code guichet (5) +
numéro de compte (12) + clé (2) — la clé étant calculée par la formule mod 97
standard (poids 89/15/3 appliqués aux trois premiers blocs, complément à 97,
identique au principe du RIB français adapté au découpage marocain). Les
apps métier (``apps.stock`` Fournisseur, ``apps.compta`` CompteTresorerie,
``apps.rh`` DossierEmploye) appellent
:func:`valider_rib`/:func:`cle_rib_valide` pour SIGNALER un RIB invalide en
WARNING — JAMAIS de blocage de saisie historique, cf. ``services``/
``selectors`` de chaque app consommatrice.
"""
import re

_RIB_RE = re.compile(r'^\d{24}$')


def normaliser_rib(rib):
    """Normalise un RIB saisi (retire espaces/tirets). Renvoie une chaîne."""
    if rib is None:
        return ''
    return re.sub(r'[\s\-]', '', str(rib))


def _lettre_vers_chiffre(car):
    """Convertit une lettre en son équivalent chiffré RIB (A/J/S=1, ... table
    standard) ; un chiffre reste inchangé. Le RIB marocain est numérique pur
    (24 chiffres), mais on tolère cette conversion pour rester compatible avec
    un futur usage alphanumérique (IBAN-like) sans jamais lever d'exception.
    """
    if car.isdigit():
        return car
    table = {
        'A': '1', 'J': '1', 'B': '2', 'K': '2', 'S': '2',
        'C': '3', 'L': '3', 'T': '3', 'D': '4', 'M': '4', 'U': '4',
        'E': '5', 'N': '5', 'V': '5', 'F': '6', 'O': '6', 'W': '6',
        'G': '7', 'P': '7', 'X': '7', 'H': '8', 'Q': '8', 'Y': '8',
        'I': '9', 'R': '9', 'Z': '9',
    }
    return table.get(car.upper(), '0')


def cle_rib_valide(rib):
    """Vrai si la clé (2 derniers chiffres) d'un RIB 24 chiffres est cohérente
    (mod 97), Faux sinon — y compris si le format n'est pas 24 chiffres
    (jamais d'exception, toujours un booléen).

    Découpage marocain : banque (5) + guichet (5) + compte (12) + clé (2) =
    24 chiffres. Sur les 22 premiers chiffres (banque + guichet + compte), on
    calcule ``97 - ((89 × banque + 15 × guichet + 3 × compte) mod 97)`` où
    chaque bloc est pris comme un entier ; le résultat DOIT égaler la clé (2
    derniers chiffres) du RIB.
    """
    rib = normaliser_rib(rib)
    if not _RIB_RE.match(rib):
        return False
    banque = int(rib[0:5])
    guichet = int(rib[5:10])
    compte = int(''.join(_lettre_vers_chiffre(c) for c in rib[10:22]))
    cle_attendue = 97 - ((89 * banque + 15 * guichet + 3 * compte) % 97)
    cle_attendue = cle_attendue if cle_attendue != 97 else 0
    cle_fournie = int(rib[22:24])
    return cle_attendue == cle_fournie


def valider_rib(rib):
    """Valide un RIB marocain, renvoie un dict de diagnostic (jamais
    d'exception) : ``{'rib', 'valide', 'erreurs': [...]}``.

    ``erreurs`` est une liste de messages explicites (format incorrect,
    longueur, clé invalide) — VIDE si valide. Utilisé pour un WARNING
    d'affichage, jamais un blocage de saisie historique (les apps
    consommatrices décident de la sévérité).
    """
    rib_norm = normaliser_rib(rib)
    erreurs = []
    if not rib_norm:
        erreurs.append('RIB vide.')
    elif not rib_norm.isdigit():
        erreurs.append('Le RIB doit être composé de 24 chiffres.')
    elif len(rib_norm) != 24:
        erreurs.append(
            f'Le RIB doit compter 24 chiffres (reçu {len(rib_norm)}).')
    elif not cle_rib_valide(rib_norm):
        erreurs.append('Clé RIB incorrecte (contrôle mod 97 échoué).')
    return {'rib': rib_norm, 'valide': not erreurs, 'erreurs': erreurs}
