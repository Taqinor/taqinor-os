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
    _is_battery, _is_hybrid_inverter, _is_inverter, _is_reseau_inverter,
    _is_smart_meter, _is_wifi_dongle,
)

SANS_BATTERIE = 'sans_batterie'
AVEC_BATTERIE = 'avec_batterie'


# ── QJR301 — UNE SEULE CONVENTION DE TEXTE POUR CLASSER UNE LIGNE ───────────
#
# Il y en avait QUATRE, avec des divergences prouvées dans les DEUX sens :
# le noyau lisait désignation + nom du produit (``_blob``), les paniers du PDF
# la désignation SEULE (``builder._item_classement``), la répartition du PDF
# une troisième variante (``builder._blob_item``), et le garde-fou legacy une
# quatrième avec ses propres mots-clés en dur. Un mot-clé qui ne vit que dans
# le NOM du produit était donc vu par le noyau et pas par les paniers PDF.
#
# LES DEUX FONCTIONS CI-DESSOUS SONT LA SEULE DÉFINITION. Les adaptateurs
# (LigneDevis ORM ici, dicts d'items dans le moteur) les IMPORTENT ; ils ne les
# recopient plus.

def texte_classement(designation, produit_nom='') -> str:
    """Le texte qui CLASSE une ligne (accessoire ? onduleur ? batterie ?) :
    désignation + nom du produit lié — une désignation éditée à la main ne peut
    pas casser silencieusement le découpage."""
    return f"{designation or ''} {produit_nom or ''}"


def texte_marque(designation, marque='', produit_nom='') -> str:
    """Le texte qui porte la MARQUE d'une ligne : désignation + marque + nom du
    produit lié — les trois champs que le moteur PDF lisait déjà."""
    return f"{designation or ''} {marque or ''} {produit_nom or ''}"


def _blob(ligne) -> str:
    """Adaptateur ``LigneDevis`` de :func:`texte_classement`."""
    produit = getattr(ligne, 'produit', None)
    return texte_classement(getattr(ligne, 'designation', ''),
                            getattr(produit, 'nom', ''))


#: L-2OPT — les deux variantes EXPLICITES de ``LigneDevis.variante`` ('' =
#: ligne commune, soumise au découpage par mots-clés comme avant).
VARIANTE_SANS = 'sans'
VARIANTE_AVEC = 'avec'


def lignes_avec_produit(devis):
    """QJR302 — LES LIGNES DU DEVIS **AVEC** LEUR PRODUIT, SANS REFAIRE LA
    REQUÊTE QUAND L'APPELANT L'A DÉJÀ FAITE.

    ``devis.lignes.select_related('produit').all()`` construit un queryset NEUF :
    il IGNORE le ``_prefetched_objects_cache`` de l'appelant (l'invariant Django
    que ce dépôt documente déjà, cf. ``domain.argent._lignes_du_devis``). Chaque
    devis à deux options d'une liste repayait donc jusqu'à DEUX requêtes — une
    pour le prédicat « deux options », une pour les totaux — qui grandissent
    avec le nombre de devis : un N+1 que le test de budget ne pouvait pas voir
    (ses fixtures étaient toutes mono-option).

    Ici : quand l'appelant a préfetché ``lignes__produit`` (donc quand chaque
    ligne porte DÉJÀ son produit en cache, ou n'en a pas), on sert le cache —
    ZÉRO requête. Sinon on retombe MOT POUR MOT sur la requête d'hier. Aucun
    montant ne change : ce sont les mêmes objets, dans le même ordre.
    """
    cache = getattr(devis, '_prefetched_objects_cache', None) or {}
    if 'lignes' in cache:
        lignes = list(devis.lignes.all())
        if all(li.produit_id is None
               or 'produit' in li._state.fields_cache
               for li in lignes):
            return lignes
    return list(devis.lignes.select_related('produit').all())


def _variante(ligne) -> str:
    """Variante déclarée d'une ligne, '' quand elle n'en porte pas (ligne
    commune, ligne historique, ou objet de test sans le champ)."""
    return getattr(ligne, 'variante', '') or ''


def _blob_marque(ligne) -> str:
    """Adaptateur ``LigneDevis`` de :func:`texte_marque`."""
    produit = getattr(ligne, 'produit', None)
    return texte_marque(getattr(ligne, 'designation', ''),
                        getattr(produit, 'marque', ''),
                        getattr(produit, 'nom', ''))


# ── QJR200 — LES ACCESSOIRES HUAWEI SONT UNE RÈGLE DU NOYAU, PAS DU RENDU ────
#
# QF9 (puis QJR124) avait posé la règle DANS ``quote_engine.builder`` : sur une
# option dont l'onduleur n'est pas Huawei, le Smart Meter et la clé Wi-Fi sont
# retirés EN AMONT, pour que le tableau et les totaux du PDF décrivent le même
# panier. La chaîne monnaie, elle, n'avait AUCUNE règle équivalente : elle
# continuait d'additionner l'accessoire. Sur le devis résidentiel COURANT
# (option réseau Huawei + option hybride Deye), le total imprimé et le total du
# noyau divergeaient donc de 3 000 MAD — deux prix pour la même vente.
#
# LA RÈGLE EST DÉCLARÉE ICI, UNE SEULE FOIS ; le moteur PDF l'IMPORTE (il ne la
# recopie plus). Les paniers d'option du noyau l'appliquent, donc l'échéancier,
# le solde, la pro-forma, la commission et ``Devis.total_ttc`` en héritent.


def est_accessoire_huawei(texte: str) -> bool:
    """True quand ``texte`` désigne un accessoire propre à l'onduleur Huawei
    (Smart Meter ou clé Wi-Fi / dongle)."""
    return bool(_is_smart_meter(texte) or _is_wifi_dongle(texte))


def _panier_sert_huawei(rows, classement, marque) -> bool:
    """QF9 — True quand l'onduleur du PANIER est Huawei.

    Reprise EXACTE de l'ancien ``builder._quote_is_huawei`` : sans onduleur
    identifiable → False (on n'affiche pas ces accessoires par défaut) ; le
    moindre onduleur non-Huawei suffit à les retirer (conservateur).
    """
    onduleurs = [r for r in rows if _is_inverter(classement(r))]
    if not onduleurs:
        return False
    huawei_vu = False
    for r in onduleurs:
        if 'huawei' in (marque(r) or '').lower():
            huawei_vu = True
        else:
            # Un onduleur non-Huawei dans le panier → pas d'accessoires Huawei.
            return False
    return huawei_vu


def retirer_accessoires_huawei(rows, classement=None, marque=None):
    """``rows`` PRIVÉ de ses accessoires Huawei orphelins.

    ``classement(row)`` rend le texte qui CLASSE la ligne (accessoire ?
    onduleur ?) et ``marque(row)`` celui qui porte la marque. Par défaut on lit
    une ``LigneDevis`` (``_blob`` / ``_blob_marque``) ; le moteur PDF fournit
    ses propres lecteurs pour ses dicts d'items — les ADAPTATEURS diffèrent, la
    RÈGLE est celle-ci et il n'y en a pas d'autre.
    """
    classement = classement or _blob
    marque = marque or _blob_marque
    rows = list(rows)
    if _panier_sert_huawei(rows, classement, marque):
        return rows
    return [r for r in rows if not est_accessoire_huawei(classement(r))]


def _garder_dans_sans(li) -> bool:
    """True si ``li`` appartient au panier « sans batterie ».

    F14 — la variante déclarée est EXCLUSIVE et TRANCHE SEULE : une ligne
    ``variante='sans'`` reste dans son panier déclaré MÊME quand son
    ``_blob`` la classerait batterie/hybride par mots-clés (ceinture-bretelles
    du moteur PDF, ``builder._repartir_options`` — la contradiction est
    remontée là-bas en avertissement interne, jamais en retrait de ligne).
    Miroir exact : seule une ligne SANS variante ('') retombe sur les mots-clés.
    """
    v = _variante(li)
    if v == VARIANTE_AVEC:
        return False
    if v == VARIANTE_SANS:
        return True
    return not _is_battery(_blob(li)) and not _is_hybrid_inverter(_blob(li))


def _garder_dans_avec(li) -> bool:
    """True si ``li`` appartient au panier « avec batterie » — miroir de
    ``_garder_dans_sans`` (F14)."""
    v = _variante(li)
    if v == VARIANTE_SANS:
        return False
    if v == VARIANTE_AVEC:
        return True
    return not _is_reseau_inverter(_blob(li))


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

    F14 (26/08/2026) — CORRECTIF : avant ce correctif, une ligne DÉCLARÉE
    ('sans'/'avec') restait quand même filtrée par les mots-clés en second
    passage (ex. une batterie taguée 'sans' était retirée du panier « sans »
    malgré sa déclaration), ce qui contredisait ce docstring ET le moteur PDF
    canonique (``quote_engine.builder._repartir_options``, ligne 499-541 :
    la déclaration prime, point final). La ligne était alors facturée par le
    PDF mais absente de l'échéancier/nomenclature écran — divergence F14.

    QJR200 (31/08/2026) — LE PANIER D'OPTION APPLIQUE LA RÈGLE QF9. Un panier
    dont l'onduleur n'est pas Huawei perd ses accessoires Huawei orphelins
    (Smart Meter, clé Wi-Fi), EXACTEMENT comme le panier du PDF : sans quoi le
    total du noyau (échéancier, solde, pro-forma, commission, ``total_ttc``)
    additionnait une ligne que le document n'imprime pas. La règle ne
    s'applique qu'aux paniers NOMMÉS : une option inconnue ou vide rend toutes
    les lignes, comportement historique inchangé (le devis mono-option, le
    pompage et la liste libre ne bougent pas d'un centime).

    QJR300 (01/09/2026) — CETTE PORTÉE EST LA RÈGLE, ET LE DOCUMENT S'Y ALIGNE.
    Le moteur PDF retirait l'accessoire INCONDITIONNELLEMENT (paniers d'option
    ET liste libre), donc AUSSI sur les devis où ce noyau ne le retire pas :
    sur un devis mono-option à onduleur non-Huawei portant un Smart Meter, le
    total imprimé / affiché / public tombait SOUS le total qui pilote
    l'échéancier, le solde, la commission et ``Devis.total_ttc`` — deux prix
    pour la même vente. Direction tranchée (D12 « les lignes du vendeur sont
    souveraines » + zéro-chiffre-inventé) : ``quote_engine.builder`` n'applique
    plus QF9 que dans le cas DEUX-OPTIONS, comme ici. Une ligne accessoire d'un
    devis mono-option ou d'une liste libre est donc IMPRIMÉE **et** FACTURÉE.
    """
    if option == SANS_BATTERIE:
        return retirer_accessoires_huawei(
            [li for li in lignes if _garder_dans_sans(li)])
    if option == AVEC_BATTERIE:
        return retirer_accessoires_huawei(
            [li for li in lignes if _garder_dans_avec(li)])
    return list(lignes)


def has_two_options(devis) -> bool:
    """ALIAS DÉPRÉCIÉ de :func:`deux_options_declarees` (QJR55).

    Ce nom répondait à la MÊME question avec des règles DIFFÉRENTES : il
    traversait ``build_quote_data`` (le moteur PDF complet) pour lire son
    ``nb_options``. Lequel des deux prédicats s'exécutait décidait si la liste
    montrait le total d'UNE option ou la somme sans signification des DEUX —
    et il coûtait un rendu de document à chaque lecture d'argent.

    Il n'y a plus qu'UNE règle, celle de :func:`deux_options_declarees`.
    Conservé comme alias parce que plusieurs appelants l'importent par ce nom ;
    à retirer quand ils auront migré.
    """
    return deux_options_declarees(devis)


def option_effective(devis) -> str:
    """QJR24 / D9 — L'OPTION QUE SUIT L'ARGENT D'UN DEVIS.

    Décision fondateur D9 du 29/08/2026 :

      * APRÈS acceptation → l'option acceptée (comportement A3, inchangé) ;
      * AVANT acceptation → l'option du TOTAL AFFICHÉ, c'est-à-dire celle mise
        en avant : l'option AVEC (``quote_engine.builder`` pose
        ``display_total = totaux_avec['ttc']`` dès qu'il y a deux options —
        LANE CHOIX-AVEC du 25/08, d'où la liste, le une-page et le PDF tirent
        déjà le MÊME nombre).

    PLUS JAMAIS la somme des deux paniers : jusqu'ici, un devis à deux options
    non accepté renvoyait ``''`` ici, donc AUCUN filtre, donc un solde et un
    échéancier construits sur l'addition des deux options — un montant qui
    n'existe dans aucun document et que le client ne paiera jamais.

    Un devis à option unique (ou pompage / liste libre) renvoie ``''`` : aucun
    filtre, périmètre complet, comportement historique strictement inchangé.

    COÛT — un devis NON accepté consulte le prédicat « deux options » (avant,
    l'option vide le court-circuitait). QJR55 a ramené ce prédicat à UNE règle
    LÉGÈRE (:func:`deux_options_declarees`, deux requêtes, aucun rendu) : la
    lecture de l'argent d'un devis ne traverse plus le moteur PDF.
    """
    acceptee = getattr(devis, 'option_acceptee', '') or ''
    if acceptee:
        return acceptee
    return AVEC_BATTERIE if has_two_options(devis) else ''


def option_lines(devis, option=None):
    """Lignes RÉELLES du devis pour l'option retenue (nomenclature du chantier).

    Ne filtre que pour un vrai devis à deux options ; sinon renvoie toutes les
    lignes (option unique, pompage, liste libre → périmètre complet inchangé).

    QJR24/D9 — l'option par défaut est celle d'``option_effective`` (acceptée,
    sinon celle du total affiché) : les LIGNES et l'ARGENT décrivent toujours
    la même vente, jamais l'une les deux options et l'autre une seule.
    """
    if option is None:
        option = option_effective(devis)
    # XSAL5/XSAL14 — la nomenclature aval ne contient QUE des lignes produit
    # effectives : on exclut les lignes de section/note (sans produit) et les
    # options non activées (``compte_dans_totaux``). Une option activée
    # (optionnelle=False) est une ligne produit normale → incluse.
    lignes = [li for li in lignes_avec_produit(devis)
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


def option_totaux(devis, option=None, lignes=None) -> dict:
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

    NPLUS1 (27/08/2026) — ``lignes`` accepte les lignes DÉJÀ CHARGÉES par
    l'appelant (patron YOPSB13, cf. ``utils/echeancier.factures_actives``) : le
    chemin d'acceptation publique appelait cette fonction deux fois de suite,
    chaque appel refaisant sa propre requête lignes+produit sur des lignes qui
    ne bougent pas pendant l'acceptation. Paramètre ABSENT (tous les autres
    appelants) ⇒ la requête d'hier, résultat identique.

    QJR24 (29/08/2026) — L'OPTION PAR DÉFAUT N'EST PLUS « aucune ». Un devis à
    deux options NON accepté tombait ici sur ``option = ''`` : aucun filtre,
    donc les totaux de l'ADDITION des deux options — c'est ce montant sans
    signification qui alimentait le solde et l'échéancier affichés. La
    résolution passe désormais par ``option_effective`` (décision fondateur
    D9). Un devis accepté et un devis à option unique sont inchangés.
    """
    if option is None:
        option = option_effective(devis)
    if lignes is None:
        lignes = lignes_avec_produit(devis)
    else:
        lignes = list(lignes)
    if option and has_two_options(devis):
        lignes = filter_lines_for_option(lignes, option)
    return _totaux_canoniques(devis, lignes)


# ── Repli SANS MOTEUR — l'affichage de la liste (PVAB, fondateur 20/08) ──────

def deux_options_declarees(devis) -> bool:
    """QJR55 — LE prédicat « devis à deux options ». Il n'y en a plus qu'un.

    Miroir volontairement PRUDENT de la décision de ``build_quote_data``
    (PV86) : l'alternative doit être DÉCLARÉE (``etude_params['scenario']``)
    ET les lignes doivent réellement porter les deux familles — onduleur
    réseau d'un côté, onduleur hybride AVEC batterie de l'autre (Z1 : sans
    batterie réelle, jamais deux options).

    L-2OPT — UNE LIGNE VARIANTÉE COURT-CIRCUITE TOUT : elle n'existe que parce
    que la composition a DÉJÀ distingué les deux options, et c'est une preuve
    plus forte que la déclaration. Ce contrôle vivait dans ``has_two_options``
    et est repris ici, sinon un devis à deux champs PV dont
    ``etude_params['scenario']`` a été perdu (le trou que QJR66 referme côté
    écran) redeviendrait « mono-option » et son argent redeviendrait la somme
    des DEUX paniers.

    NE TRAVERSE PLUS LE MOTEUR PDF. ``has_two_options`` rendait ce verdict en
    construisant tout le document (``build_quote_data``) : lequel des deux
    prédicats s'exécutait décidait si la liste montrait le total d'UNE option
    ou la somme sans signification des deux, et chaque lecture d'argent d'un
    devis mono-option payait un rendu complet (``models.Devis.total_ttc`` →
    ``domain.argent`` → ``option_effective`` → ici).

    Ne lève JAMAIS : dans le doute il répond False, et l'affichage retombe sur
    le total complet — le comportement d'avant.

    NPLUS1 (29/08/2026, QJR51) — LE SCAN DES VARIANTES SE FAIT EN PYTHON, PAS
    EN SQL. Ce contrôle s'écrivait ``devis.lignes.exclude(variante='')
    .exists()`` : chaîner ``exclude`` construit un nouveau queryset, donc une
    requête NEUVE qui IGNORE le ``prefetch_related('devis__lignes')`` de
    l'appelant — et comme ``Devis.total_ttc`` traverse ce prédicat depuis la
    décision D2, la liste des leads repayait cette requête pour CHAQUE devis
    (moitié de la régression « 23 (5 leads) → 33 (10 leads) »). ``.all()`` nu
    est la seule forme que le gestionnaire de relation sert depuis
    ``_prefetched_objects_cache``. Le verdict est IDENTIQUE au bit :
    ``LigneDevis.variante`` est un ``CharField(blank=True, default='')`` NON
    NULLABLE, donc « exclure la chaîne vide » et « une variante non vide en
    Python » désignent exactement les mêmes lignes. Sans prefetch, c'est une
    requête comme avant (un SELECT complet au lieu d'un ``EXISTS`` — les
    lignes sont de toute façon relues juste après par l'appelant).
    """
    try:
        if devis is not None and any(
                _variante(li) for li in devis.lignes.all()):
            return True
    except Exception:  # noqa: BLE001 — l'aval ne doit jamais casser ici
        pass
    scenario = (getattr(devis, 'etude_params', None) or {}).get('scenario')
    if scenario not in ('Sans batterie', 'Avec batterie',
                        'Les deux (Sans + Avec)'):
        return False
    try:
        blobs = [_blob(li)
                 for li in lignes_avec_produit(devis)
                 if li.compte_dans_totaux]
    except Exception:  # noqa: BLE001 — l'aval ne doit jamais casser ici
        return False
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
    lignes = lignes_avec_produit(devis)
    sans = _totaux_canoniques(
        devis, filter_lines_for_option(lignes, SANS_BATTERIE))
    avec = _totaux_canoniques(
        devis, filter_lines_for_option(lignes, AVEC_BATTERIE))
    return {
        'total': float(avec['ttc'] if avec.get('ttc') else sans['ttc']),
        'nb_options': 2,
        'comparaison_repli': {'sans': sans, 'avec': avec},
    }
