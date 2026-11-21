"""CALX358 — les LECTURES du catalogue de systèmes de fixation, dans l'app.

Le catalogue (``SystemeFixation``/``ComposantFixation``, migration ``0014``)
vit DANS ``apps.calepinage`` et prépare le remplacement de ``KitCalepinage``
(SOLMVP15) sans rien retirer au module d'appels d'offres : aucun import de ce
module ici, ``services/kits.py`` intact (D-CALX 2). ``selectors.py`` n'est pas
rouvert : les lectures du catalogue passent par CE fichier.

LA RÈGLE DE QUANTITÉ, DÉCLARÉE UNE FOIS
---------------------------------------
Chaque composant porte une ``regle`` SAISIE :
``{base, facteur?, diviseur?, libelle_facteur?, libelle_diviseur?}``.

* ``base`` — une grandeur LUE sur le document (``BASES`` ci-dessous) ou la
  quantité d'un AUTRE composant du même système (``role:<rôle>``, pour
  « crochets par mètre de rail ») ;
* ``facteur`` / ``diviseur`` — des nombres SAISIS par la société (> 0).
  Une clé ABSENTE ne fait pas partie de la formule ; une clé PRÉSENTE à
  ``null`` est un paramètre DÉCLARÉ mais NON SAISI : la ligne sort à
  ``null`` en le nommant (CALX359), jamais une quantité de repli ;
* ``libelle_facteur`` / ``libelle_diviseur`` — le nom en clair du paramètre
  (« rails par rangée », « entraxe des crochets (m) »), repris dans la
  formule publiée et dans le manquant.

Ce fichier ne porte AUCUN nombre : il déclare un vocabulaire et le valide.
"""
from __future__ import annotations

#: Les grandeurs de base LUES sur le document (CALX359 les calcule), avec le
#: libellé français repris dans la formule publiée.
BASES = {
    'modules': 'modules posés',
    'rangees': 'rangées',
    'pans': 'pans',
    'jonctions': 'jonctions entre modules voisins',
    'extremites': 'extrémités de rangées',
    'longueur_rangees_m': 'longueur des rangées (m)',
}

#: Préfixe d'une base qui désigne la quantité d'un autre composant.
PREFIXE_ROLE = 'role:'

#: Les clés ADMISES d'une règle.
CLES_REGLE = ('base', 'facteur', 'diviseur', 'libelle_facteur',
              'libelle_diviseur')

#: ACAL566 — les couvertures qu'un système peut servir : le vocabulaire du
#: lead (``Lead.TypeToiture``, parité testée), jamais une liste à part.
COUVERTURES = ('terrasse_beton', 'tole_metal', 'tuiles', 'bac_acier',
               'fibrociment', 'autre')

__all__ = [
    'BASES', 'PREFIXE_ROLE', 'CLES_REGLE', 'COUVERTURES', 'erreur_de_regle',
    'erreur_de_couvertures',
    'systemes_actifs', 'systeme_de_societe', 'composants_du_systeme',
]


def _roles_admis():
    from ..models import ComposantFixation

    return tuple(ComposantFixation.Role.values)


def _nombre_saisi(valeur):
    return (isinstance(valeur, (int, float))
            and not isinstance(valeur, bool))


def erreur_de_regle(regle):
    """Le message FRANÇAIS qui refuse ``regle``, ou ``''`` si elle est
    recevable. ``{}``/``None`` = règle non saisie : recevable (la ligne
    sortira non calculée, en le disant)."""
    if regle in (None, {}):
        return ''
    if not isinstance(regle, dict):
        return ("La règle de quantité se saisit en objet "
                "{base, facteur, diviseur} "
                f"(reçu : {type(regle).__name__}).")
    inconnues = sorted(set(regle) - set(CLES_REGLE))
    if inconnues:
        return (f"Clé de règle inconnue : « {', '.join(inconnues)} ». Clés "
                f"admises : {', '.join(CLES_REGLE)}.")
    base = regle.get('base')
    if not isinstance(base, str) or not base.strip():
        return ("La règle de quantité nomme sa grandeur de base (« base ») : "
                f"{', '.join(BASES)}, ou « {PREFIXE_ROLE}<rôle> ».")
    if base.startswith(PREFIXE_ROLE):
        if base[len(PREFIXE_ROLE):] not in _roles_admis():
            return (f"« {base} » ne désigne aucun rôle de composant "
                    f"(rôles : {', '.join(_roles_admis())}).")
    elif base not in BASES:
        return (f"Grandeur de base inconnue : « {base} ». Bases admises : "
                f"{', '.join(BASES)}, ou « {PREFIXE_ROLE}<rôle> ».")
    for cle in ('facteur', 'diviseur'):
        if cle not in regle or regle[cle] is None:
            continue
        valeur = regle[cle]
        if not _nombre_saisi(valeur) or valeur <= 0:
            return (f"« {cle} » attend un nombre strictement positif, ou "
                    f"null tant qu'il n'est pas saisi (reçu : {valeur!r}).")
    for cle in ('libelle_facteur', 'libelle_diviseur'):
        if cle in regle and not isinstance(regle[cle], str):
            return f"« {cle} » est un texte."
    return ''


def erreur_de_couvertures(couvertures):
    """ACAL566 — le message qui refuse ``couvertures``, ou ``''`` (liste de
    clés de :data:`COUVERTURES`, sans doublon ; vide = non déclarée)."""
    if couvertures in (None, []):
        return ''
    if not isinstance(couvertures, list):
        return ("Les couvertures se saisissent en liste "
                f"(reçu : {type(couvertures).__name__}).")
    inconnues = [str(c) for c in couvertures if c not in COUVERTURES]
    if inconnues:
        return (f"Couverture inconnue : « {', '.join(inconnues)} ». "
                f"Couvertures admises : {', '.join(COUVERTURES)}.")
    if len(set(couvertures)) != len(couvertures):
        return "Une couverture est déclarée deux fois."
    return ''


def systemes_actifs(company):
    """Les systèmes ACTIFS de la société, dans l'ordre du catalogue.

    ÉQUIVALENCE (D12) : une société qui n'a rien saisi reçoit une liste vide.
    """
    from ..models import SystemeFixation

    if company is None:
        return []
    return list(SystemeFixation.objects.filter(company=company, actif=True)
                .order_by('libelle', 'id'))


def systeme_de_societe(company, systeme_id):
    """Le système ``systeme_id`` de la société (actif ou non), ou ``None`` —
    un système d'une autre société est INTROUVABLE, jamais « interdit »."""
    from ..models import SystemeFixation

    if company is None or systeme_id in (None, ''):
        return None
    try:
        identifiant = int(systeme_id)
    except (TypeError, ValueError):
        return None
    return SystemeFixation.objects.filter(company=company,
                                          pk=identifiant).first()


def composants_du_systeme(systeme):
    """Les composants du système, dans l'ordre du catalogue."""
    if systeme is None or not getattr(systeme, 'pk', None):
        return []
    return list(systeme.composants.filter(company_id=systeme.company_id)
                .order_by('ordre', 'id'))
