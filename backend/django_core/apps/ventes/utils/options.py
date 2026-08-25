"""A3 — l'option retenue à l'acceptation (« Sans batterie » / « Avec batterie »)
est AUTORITATIVE en aval.

La facture (échéancier) et le chantier (nomenclature/BOM) n'utilisent QUE les
lignes de l'option acceptée :

  * « Sans batterie » → exclut les batteries et les onduleurs hybrides ;
  * « Avec batterie » → exclut les onduleurs réseau/injection.

Le découpage réutilise EXACTEMENT les mêmes prédicats que le moteur de devis
(``quote_engine.builder``) pour rester identique au PDF. On ne filtre que pour
un VRAI devis à deux options (réseau ET hybride+batterie) ; un devis à option
unique, un pompage ou une liste libre garde TOUTES ses lignes — comportement
historique strictement inchangé.

Les totaux sont calculés par la MÊME formule que ``Devis.total_ht/total_tva``
(somme des lignes, TVA par ligne), donc au centime près et cohérents avec les
factures existantes ; on ne réimplémente aucun calcul d'argent à la main.
"""
from __future__ import annotations

# Prédicats de classification — partagés avec le moteur de devis. Purs (chaînes).
from apps.ventes.quote_engine.builder import (
    _is_battery, _is_hybrid_inverter, _is_reseau_inverter,
)

SANS_BATTERIE = 'sans_batterie'
AVEC_BATTERIE = 'avec_batterie'


def _blob(ligne) -> str:
    """Désignation + nom du produit lié — le moteur classe sur les deux pour
    qu'une désignation éditée à la main ne casse pas le découpage."""
    produit = getattr(ligne, 'produit', None)
    nom = getattr(produit, 'nom', '') or ''
    desig = getattr(ligne, 'designation', '') or ''
    return f"{desig} {nom}"


#: L-2OPT — les deux variantes EXPLICITES de ``LigneDevis.variante`` ('' =
#: ligne commune, soumise au découpage par mots-clés comme avant).
VARIANTE_SANS = 'sans'
VARIANTE_AVEC = 'avec'


def _variante(ligne) -> str:
    """Variante déclarée d'une ligne, '' quand elle n'en porte pas (ligne
    commune, ligne historique, ou objet de test sans le champ)."""
    return getattr(ligne, 'variante', '') or ''


def filter_lines_for_option(lignes, option):
    """Filtre PUR d'une liste de lignes selon l'option (testable sans Django).

    Miroir exact du split de ``build_quote_data`` : « sans » = ni batterie ni
    onduleur hybride ; « avec » = pas d'onduleur réseau. Toute autre valeur
    (vide / inconnue) renvoie toutes les lignes.

    L-2OPT — LA VARIANTE DÉCLARÉE PASSE DEVANT LES MOTS-CLÉS, et elle est
    EXCLUSIVE : une ligne ``variante='avec'`` ne part JAMAIS dans un document
    aval « sans batterie », et réciproquement. C'est ce qui rend facturable un
    devis dont les deux options n'ont pas le même champ PV — sans elle, les
    panneaux, la structure et la pose des DEUX options seraient commandés,
    puisque les mots-clés les classent « commun ». Une ligne SANS variante
    ('' — toutes celles d'hier) reste soumise aux mots-clés, mot pour mot :
    aucun devis existant ne change de périmètre.
    """
    if option == SANS_BATTERIE:
        return [li for li in lignes
                if _variante(li) != VARIANTE_AVEC
                and not _is_battery(_blob(li))
                and not _is_hybrid_inverter(_blob(li))]
    if option == AVEC_BATTERIE:
        return [li for li in lignes
                if _variante(li) != VARIANTE_SANS
                and not _is_reseau_inverter(_blob(li))]
    return list(lignes)


def has_two_options(devis) -> bool:
    """True si le devis comporte deux VRAIES options (réseau ET hybride+batterie)
    — seul cas où l'option retenue change réellement le périmètre facturé."""
    # L-2OPT — une ligne VARIANTÉE est à elle seule la preuve d'un devis à deux
    # options : elle n'existe que parce que la composition a distingué les deux.
    # Contrôlé AVANT le moteur (une requête, aucun rendu) et sans jamais lever :
    # un devis à deux champs PV doit être filtré même si le PDF échoue.
    try:
        if devis is not None and devis.lignes.exclude(variante='').exists():
            return True
    except Exception:  # noqa: BLE001 — l'aval ne doit jamais casser ici
        pass
    try:
        from apps.ventes.quote_engine.builder import build_quote_data
        data = build_quote_data(devis, {'pdf_mode': 'onepage'})
        return data.get('nb_options', 1) == 2
    except Exception:  # noqa: BLE001 — l'aval ne doit jamais casser sur le PDF
        return False


def option_lines(devis, option=None):
    """Lignes RÉELLES du devis pour l'option retenue (nomenclature du chantier).

    Ne filtre que pour un vrai devis à deux options ; sinon renvoie toutes les
    lignes (option unique, pompage, liste libre → périmètre complet inchangé).
    """
    if option is None:
        option = getattr(devis, 'option_acceptee', '') or ''
    # XSAL5/XSAL14 — la nomenclature aval ne contient QUE des lignes produit
    # effectives : on exclut les lignes de section/note (sans produit) et les
    # options non activées (``compte_dans_totaux``). Une option activée
    # (optionnelle=False) est une ligne produit normale → incluse.
    lignes = [li for li in devis.lignes.select_related('produit').all()
              if li.compte_dans_totaux]
    if not option or not has_two_options(devis):
        return lignes
    return filter_lines_for_option(lignes, option)


def _totaux_canoniques(devis, lignes) -> dict:
    """Totaux canoniques d'une liste de lignes de CE devis — le cœur partagé
    d'``option_totaux`` et du repli sans moteur (``totaux_affichage_repli``) :
    HT brut → remise globale → TVA par taux → TTC, au centime."""
    from apps.ventes.selectors import _canonical_totaux
    can = _canonical_totaux(
        lignes,
        remise_globale_pct=getattr(devis, 'remise_globale', 0) or 0,
        fallback_taux=devis.taux_tva)
    return {
        'ht': can['ht_net'], 'tva': can['tva'], 'ttc': can['ttc'],
        'ht_brut': can['ht_brut'], 'remise': can['remise'],
    }


def option_totaux(devis, option=None) -> dict:
    """Totaux HT / TVA / TTC (Decimals, centime) pour l'option retenue.

    QX1 — SOURCE UNIQUE DE LA MONNAIE : les totaux passent désormais par la
    chaîne canonique ``selectors._canonical_totaux`` (HT brut → **remise
    globale** → TVA par taux → TTC), EXACTEMENT comme le PDF client
    (``quote_engine/builder``). La ``remise_globale`` du devis est donc honorée
    de bout en bout : échéancier, solde et bon de commande héritent
    automatiquement de la remise (avant QX1 elle était perdue → sur-facturation).

    ``ht`` / ``tva`` / ``ttc`` sont les valeurs **NETTES** (après remise). Le
    détail brut/remise est aussi exposé (``ht_brut``, ``remise``) pour les
    documents qui affichent la ligne « Remise globale » (BC). Sans option double
    et sans remise, les valeurs restent identiques au comportement historique.
    """
    if option is None:
        option = getattr(devis, 'option_acceptee', '') or ''
    if not option or not has_two_options(devis):
        lignes = list(devis.lignes.select_related('produit').all())
    else:
        lignes = filter_lines_for_option(
            list(devis.lignes.select_related('produit').all()), option)
    return _totaux_canoniques(devis, lignes)


# ── Repli SANS MOTEUR — l'affichage de la liste (PVAB, fondateur 20/08) ──────

def deux_options_declarees(devis) -> bool:
    """Prédicat LÉGER « devis à deux options », sans le moteur PDF.

    Miroir volontairement PRUDENT de la décision de ``build_quote_data``
    (PV86) : l'alternative doit être DÉCLARÉE (``etude_params['scenario']``)
    ET les lignes doivent réellement porter les deux familles — onduleur
    réseau d'un côté, onduleur hybride AVEC batterie de l'autre (Z1 : sans
    batterie réelle, jamais deux options). Consommé UNIQUEMENT quand le
    moteur lève : dans le doute il répond False et l'affichage retombe sur le
    total stocké, comme avant.
    """
    scenario = (getattr(devis, 'etude_params', None) or {}).get('scenario')
    if scenario not in ('Sans batterie', 'Avec batterie',
                        'Les deux (Sans + Avec)'):
        return False
    blobs = [_blob(li) for li in devis.lignes.select_related('produit').all()
             if li.compte_dans_totaux]
    return (any(_is_reseau_inverter(b) for b in blobs)
            and any(_is_hybrid_inverter(b) for b in blobs)
            and any(_is_battery(b) for b in blobs))


def totaux_affichage_repli(devis) -> dict:
    """Repli de ``display_totals`` quand ``build_quote_data`` lève.

    L'incident (DEV-202608-0015) : le repli historique renvoyait
    ``devis.total_ttc`` — pour un devis à deux options, la SOMME des deux
    paniers, un montant qui n'existe dans AUCUN document — sans badge (le
    ``nb_options: 1`` du repli masquait tout). Ici : deux options déclarées →
    le total de l'option mise en avant, par la même chaîne canonique que le
    PDF, et ``comparaison_repli`` porte les deux totaux pour l'affichage
    « A / B » de la liste. Mono-option → total stocké, historique inchangé.

    F1 (26/08/2026) — LE REPLI SUIT LA CHAÎNE CANONIQUE. Ce repli servait
    encore le total de l'option 1 (« Sans batterie ») alors que la chaîne
    canonique a basculé sur l'option AVEC le 25/08 (LANE CHOIX-AVEC :
    ``builder.display_total`` = ``totaux_avec['ttc']`` dès qu'il y a deux
    options, pour que la liste, le une-page et le PDF portent la MÊME option).
    Le jour où le moteur lève, la liste passait donc silencieusement d'un
    total à l'autre. Repli sur « sans » gardé quand « avec » n'a pas de total
    lisible — jamais rien d'inventé.
    """
    if not deux_options_declarees(devis):
        return {'total': float(devis.total_ttc), 'nb_options': 1}
    lignes = list(devis.lignes.select_related('produit').all())
    sans = _totaux_canoniques(
        devis, filter_lines_for_option(lignes, SANS_BATTERIE))
    avec = _totaux_canoniques(
        devis, filter_lines_for_option(lignes, AVEC_BATTERIE))
    return {
        'total': float(avec['ttc'] if avec.get('ttc') else sans['ttc']),
        'nb_options': 2,
        'comparaison_repli': {'sans': sans, 'avec': avec},
    }
