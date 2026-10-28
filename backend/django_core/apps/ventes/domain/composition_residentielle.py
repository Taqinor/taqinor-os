"""Composition RÉSIDENTIELLE — ``composition_residentielle`` et ses deux
helpers privés exclusifs (``_entier_ou_none``, ``_statut_couple_panneau``).

RSIZ (27/10/2026) — DÉPLACEMENT PUR depuis ``apps/ventes/domain/composition.py``
(fichier > 2 000 lignes) : corps recopiés à l'identique, aucun chiffre ne bouge.
``composition.py`` ré-exporte ``composition_residentielle`` : tout importeur
reste identique. Les noms du catalogue sont liés à l'import (comme avant) ;
ceux DÉFINIS dans ``composition.py`` (avertissements, ``LigneKit``…) sont
importés À L'APPEL — anti-cycle, et un ``mock.patch`` de
``apps.ventes.domain.composition.X`` continue d'agir.

NOM DU LOGGER FIGÉ sur ``apps.ventes.services`` (voir ``composition.py``).
"""
from decimal import Decimal
import logging
import math

# Noms du catalogue : liés À L'IMPORT, exactement comme le faisait le bloc
# du bas de ``composition.py`` (catalogue n'importe jamais composition en
# tête : aucun cycle).
from apps.ventes.domain.catalogue import (
    _arrondi_js,
    _batterie_compatible,
    _batterie_en_stock,
    _est_au_metre,
    _est_triphase,
    _filtrer_onduleurs_complets,
    _has_price,
    _marque_correspond,
    _max_modules_par_banc,
    _parse_kw,
    _parse_kwh,
    _parse_watt,
    _plage_batterie_de_l_onduleur,
    _prix_ttc_batterie,
    _sans_accents,
    classer_produit,
    metre_cable_dc_par_paires,
    metre_cable_terre,
    paires_mppt_du_champ,
    plafond_panneaux,
    prix_forfait_ht,
)

logger = logging.getLogger("apps.ventes.services")


def _entier_ou_none(valeur):
    """``int(valeur)`` ou ``None`` — jamais une levée sur une saisie sale."""
    if valeur in (None, ''):
        return None
    try:
        return int(valeur)
    except (TypeError, ValueError):
        return None


def _statut_couple_panneau(panneau, onduleurs):
    """PVCOMPAT — le PIRE verdict d'un panneau face aux onduleurs VENDUS.

    En forme deux options les DEUX onduleurs partent au devis : un panneau qui
    coince avec l'un des deux coince pour le devis entier. L'ordre de sévérité
    est celui du noyau — ``incompatible`` (bloquant matériel) l'emporte sur
    ``reserve`` (production dégradée), qui l'emporte sur ``inconnu`` (fiche
    incomplète), qui l'emporte sur ``compatible``.
    """
    from apps.ventes.compatibilites import (
        STATUT_COMPATIBLE, STATUT_INCOMPATIBLE, STATUT_INCONNU,
        STATUT_RESERVE, verdict_panneau_onduleur)
    severite = {STATUT_INCOMPATIBLE: 3, STATUT_RESERVE: 2,
                STATUT_INCONNU: 1, STATUT_COMPATIBLE: 0}
    pire = (0, STATUT_COMPATIBLE, None)
    for onduleur in onduleurs:
        verdict = verdict_panneau_onduleur(panneau, onduleur)
        rang = severite.get(verdict['statut'], 0)
        if rang > pire[0]:
            pire = (rang, verdict['statut'], (onduleur, verdict))
    return pire[1], pire[2]


def _choisir_panneau(pool, watt):
    """Panneau : wattage demandé d'abord, à défaut le plus proche.

    RSIZ4 — corps EXTRAIT tel quel de :func:`composition_residentielle`.
    ``pool`` est le vivier DÉJÀ restreint à la marque épinglée (PVMRQ). Rend
    ``(tries, exacts, panneau)`` : les deux listes servent au repli PVCOMPAT.
    """
    tries = []
    for produit in pool:
        w = _parse_watt(getattr(produit, 'nom', ''))
        if w is not None:
            tries.append((w, produit))
    exacts = [c for c in tries if c[0] == int(watt)]
    if exacts:
        # Même départage qu'à l'écran : un Canadien Solar passe devant.
        exacts.sort(key=lambda c: 0 if 'canadien' in _sans_accents(
            getattr(c[1], 'nom', '')) else 1)
        return tries, exacts, exacts[0][1]
    if tries:
        return tries, exacts, min(tries, key=lambda c: abs(c[0] - watt))[1]
    return tries, exacts, None


def _hybrides_servis_par_une_batterie(vivier, batteries):
    """RSIZ2 — le vivier d'hybrides réduit à ceux qu'une batterie TARIFÉE ET
    EN STOCK peut servir (tension dans la plage batterie de l'onduleur).

    Mesuré le 27/10/2026 sur un instantané de production : au-delà de
    ~25 kWc la règle des 80 % retenait le Deye 30 kW (batterie HAUTE tension
    160-800 V) alors que la seule batterie tarifée en stock est le Dyness 5 kWh
    BASSE tension — l'option « avec batterie » partait SANS batterie. Réduit
    à des hybrides servables, le choix retombe sur le plus gros hybride basse
    tension, posé en N exemplaires (``quantite_onduleur``). Aucun hybride
    servable ⇒ le vivier est rendu TEL QUEL : la composition prononce alors
    l'avertissement batterie existant (vivier vide / rupture), jamais un
    silence.
    """
    servies = [b for b in (batteries or ()) if _batterie_en_stock(b)]
    retenus = [o for o in vivier if any(
        _batterie_compatible(b, _plage_batterie_de_l_onduleur(o))
        for b in servies)]
    return retenus or list(vivier)


def _paires_mppt(mppt_paires, derivees, nb, kwp, panneau, vendus):
    """RSIZ5 — les paires de câble DC chiffrées : ``mppt_paires`` tel quel
    (règles d'origine), ou le plus grand de lui et du compte DÉRIVÉ."""
    if not derivees:
        return mppt_paires
    try:
        plancher = max(1, int(mppt_paires or 1))
    except (TypeError, ValueError):
        plancher = 1
    return max(plancher, paires_mppt_du_champ(nb, kwp, panneau, vendus))


def composition_residentielle(produits, *, kwc, panel_watt, nb_panneaux=0,
                              avec_batterie=False, structure_type='acier',
                              structure_produit_id=None,
                              taux_tva=Decimal('20'), avertissements=None,
                              deux_options=False, marques=None,
                              ordre_lignes=None, mppt_paires=1, phase=None,
                              batterie_cible_kwh=None,
                              batterie_module_kwh=None,
                              hors_reseau=False, modeles=None,
                              paires_mppt_derivees=False):
    """Le KIT résidentiel COMPLET composé depuis un catalogue.

    ``modeles`` (ACAL63, C-ACAL-042) — les modèles POSÉS par le calepinage,
    ``[{produit_id, watt, count}]`` (``geometrie.modeles_designes``). Dès
    qu'une FICHE est désignée, le devis vend UNE ligne panneau PAR MODÈLE : la
    fiche désignée prime sur le moins cher du wattage ET sur la marque
    épinglée (PVMRQ — l'écart de marque est DIT), un modèle sans fiche suit la
    règle du wattage ; le compte vendu = la somme des modèles. Une fiche
    absente ou non tarifée n'est jamais remplacée (le refus nommé est
    prononcé par ``pipeline.verifier``). ``None`` (LE DÉFAUT) ⇒ composition
    byte-identique à l'historique.

    U3 (fondateur 20/08/2026) — CETTE FONCTION EST LA SOURCE DE VÉRITÉ de la
    composition résidentielle. Elle porte désormais TOUTES les règles qui
    n'existaient que dans ``solar.js::autoFillLines`` :

      · ``marques`` — PVMRQ, carte ``{rôle: marque}`` DÉJÀ résolue par
        l'appelant (via ``marque_preferee``, seule voie de lecture du réglage
        gammes ; cette fonction reste PURE et ne requête rien). Une marque
        épinglée restreint le vivier de son rôle À ELLE SEULE ; sans candidat,
        le vivier est VIDE — jamais un repli silencieux sur une autre marque —
        et le rôle est consigné dans ``.marques_manquantes``.
      · ``ordre_lignes`` — PVORD, séquence de rôles préférée ; absente, l'ordre
        canonique du simulateur est rendu tel quel.
      · ``mppt_paires`` — C4/PVCBL, nombre de paires de câble DC descendantes
        (60 m par paire) ; repli fondateur explicite à 1 paire.
      · ``paires_mppt_derivees`` — RSIZ5 : vrai (règles de calcul ≥ 3, cf.
        ``regles_calcul.regles_au_moins``), les paires sont DÉRIVÉES du champ
        et des onduleurs vendus (:func:`catalogue.paires_mppt_du_champ`),
        ``mppt_paires`` n'étant plus qu'un PLANCHER. ``False`` (LE DÉFAUT)
        ⇒ ``mppt_paires`` tel quel, byte-identique à l'historique.
      · ``phase`` — PVCOMPAT, le RACCORDEMENT déclaré par le client
        (``'monophase'`` / ``'triphase'``, cf.
        ``compatibilites.normaliser_phase``). Monophasé : les onduleurs
        triphasés sortent du vivier ; triphasé : le départage à puissance égale
        préfère DUREMENT le triphasé. ``None`` (défaut) ⇒ aucun filtre, donc
        comportement byte-identique à l'historique.

    PVCOMPAT (fondateur 20/08/2026) — LE COUPLE PANNEAU/ONDULEUR EST VÉRIFIÉ.
    Le panneau et l'onduleur étaient choisis INDÉPENDAMMENT (l'un au wattage
    demandé, l'autre à la puissance) et rien ne vérifiait qu'ils allaient
    ensemble : « il n'y a pas de PV parce que le courant maxi par MPPT de cet
    onduleur est sous le courant de nos panneaux » ne pouvait pas être dit. Le
    verdict du noyau électrique est désormais consulté APRÈS les deux choix :
    un couple INCOMPATIBLE fait chercher un autre panneau du vivier (marque
    épinglée respectée) ; à défaut, le choix d'origine est CONSERVÉ — jamais
    une composition morte — et le problème est ANNONCÉ par ``avertissements``.

    Le résultat est une ``CompositionLignes`` : une LISTE de ``LigneKit`` (tout
    appelant historique la lit sans rien changer) qui porte en plus les
    métadonnées de la composition (``nb_panneaux``, ``panel_watt_reel``,
    ``kwc_reel``, ``roles``, ``marques_manquantes``) — le dry-run les rend à
    l'écran.

    ``deux_options`` (U2, fondateur 20/08/2026) — compose la forme DEUX
    OPTIONS que la proposition résidentielle rend déjà : les DEUX onduleurs
    (réseau ET hybride) et les batteries dans UN seul devis. C'est le
    découpage que lisent ``optionTotalsTTC`` (écran) et le moteur PDF :
      · option « sans batterie » = tout SAUF batterie + onduleur hybride ;
      · option « avec batterie »  = tout SAUF onduleur réseau.
    Le client compare, puis choisit. Sans ce drapeau (défaut), la composition
    reste MONO-OPTION et byte-identique à l'historique : ``avec_batterie``
    décide seul quel onduleur est vendu — c'est ce que veut le calepinage 3D,
    où le scénario a DÉJÀ été arrêté à l'écran.

    Fonction PURE : elle ne requête rien, n'écrit rien, ne touche aucun statut.
    ``produits`` est un itérable de produits DÉJÀ cantonnés à la société
    appelante (voir ``catalogue_de_la_societe``) ; les produits sans prix de
    vente en sont écartés d'entrée de jeu.

    ``taux_tva`` — le taux du DEVIS. Il servait à reconvertir en HT les trois
    prix forfaitaires que le simulateur exprimait en TTC ; depuis L-FORFAIT
    (fondateur 24/08/2026) ces forfaits sont dictés EN HT et lus au catalogue
    (``stock.Produit.prix_fixe_ht`` / ``prix_par_panneau_ht``), donc plus rien
    ici ne convertit quoi que ce soit. Le paramètre est CONSERVÉ — tous les
    appelants le passent et la TVA reste celle du devis — mais il n'influence
    plus aucun montant composé.

    ``batterie_cible_kwh`` (DIM2, fondateur 24/08/2026) — capacité de stockage
    VISÉE, en kWh, servie par les modules du catalogue. ``None`` (LE DÉFAUT,
    épinglé par un test) ⇒ la règle historique du simulateur reste seule maître
    à bord : ``cible = max(5, arrondi(kwp / 5) × 5)``. **Le devis automatique ne
    passe JAMAIS ce paramètre** : sa batterie reste une conséquence des kWc,
    exactement comme avant. Seul le TABLEAU de dimensionnement
    (``apps.ventes.dimensionnement``) l'utilise, pour EXPLORER le stockage comme
    une deuxième dimension et montrer au fondateur ce qu'une banque plus grande
    changerait — explorer n'est pas décider.

    ``batterie_module_kwh`` (BATHOMO, fondateur 26/08/2026 — « if the quote has
    5 kWh batteries the web page should only show 5 kWh batteries ; and we can
    go up to 30 or 40 kWh using 5 kWh batteries, no problem ») — IMPOSE le
    calibre (``5`` ou ``10``) de la banque, plutôt que de laisser le choix « au
    plus proche de la cible » ci-dessous décider. Un appelant qui connaît déjà
    le module RÉELLEMENT engagé par un devis (lu sur ses LIGNES vendues, jamais
    redeviné ici) l'impose ainsi pour toute l'échelle qu'il explore : la banque
    grandit alors en N modules de CE calibre — jusqu'à 6-8 packs de 5 kWh pour
    atteindre 30-40 kWh — sans jamais glisser vers l'autre calibre au passage
    d'un multiple de 10 (où le choix « au plus proche » préfère normalement le
    plus gros module). ``None`` (LE DÉFAUT) ⇒ comportement inchangé : le
    calibre le plus proche de ``cible_kwh`` décide, égalité tranchée pour le
    plus gros. Calibre imposé absent du catalogue ⇒ repli silencieux sur ce
    même choix « au plus proche » — jamais une banque vide du seul fait d'un
    calibre non stocké.

    ``hors_reseau`` (QJR-OFFGRID, fondateur 01/09/2026) — le site est ISOLÉ :
    aucun raccordement ONEE, donc AUCUN onduleur réseau ni hybride ne peut
    être vendu. La composition passe alors sur la TROISIÈME famille
    d'onduleur — ``onduleur_offgrid``, même règle des 80 % que les deux
    autres — et le stockage devient OBLIGATOIRE (sans batterie, un site isolé
    n'a pas d'électricité la nuit). Forme MONO-OPTION de type « avec » : le
    drapeau ``deux_options`` est sans objet et il est ignoré. **Aucun repli sur
    un hybride** : sans onduleur autonome tarifé au catalogue, la ligne
    onduleur est ABSENTE et l'appelant refuse (``pipeline.verifier``) — jamais
    un composant substitué en silence (règle fondateur des chiffres vérifiés).
    ``False`` (LE DÉFAUT) ⇒ composition byte-identique à l'historique.

    ``structure_produit_id`` (STKCAT1/STKCAT7, fondateur 16/09/2026) — LE
    PRODUIT DE STRUCTURE CHOISI, par son id ``stock.Produit``. Il est
    PRIORITAIRE sur ``structure_type`` (désormais un ALIAS DÉPRÉCIÉ) dès qu'il
    est fourni ; les deux ne se combinent JAMAIS. Le produit est résolu DANS
    la liste ``produits`` déjà scopée société (donc un id d'une autre société
    ne résout rien) et APRÈS la garde de prix ; ni le filtre par mot-clé
    acier/alu ni la marque épinglée du rôle ne s'y appliquent — un choix
    explicite ne se re-choisit pas. Le RÔLE ÉMIS suit alors le NOM du produit
    retenu (``structure_acier`` / ``structure_alu`` s'il porte encore le
    mot-clé, le rôle générique ``structure`` sinon — cf.
    :func:`role_structure_du_produit` et le contrat
    ``contract_samples/devis_composition.json``). ``None`` (LE DÉFAUT) ⇒
    composition byte-identique à l'historique.

    ``avertissements`` (optionnel) est LE CANAL de cette fonction : une liste
    que l'appelant fournit et que la composition enrichit sur place quand elle
    a dû composer AUTREMENT que demandé — aujourd'hui le seul cas est un vivier
    batterie VIDE alors que ``avec_batterie`` était demandé. Sans ce canal, un
    devis « avec batterie » pouvait partir SANS aucune ligne batterie et sans
    que personne ne l'apprenne. Absent (``None``) ⇒ comportement inchangé.

    Rend la liste ORDONNÉE des ``LigneKit`` à créer, dans l'ordre canonique du
    simulateur, quantités nulles exclues. Liste vide si la puissance est nulle.
    """
    # RSIZ (27/10/2026) — DÉPLACEMENT PUR : les noms DÉFINIS dans
    # ``composition.py`` sont lus à l'APPEL (import local : aucun cycle, et
    # un ``mock.patch`` de ``domain.composition.X`` agit comme avant).
    from apps.ventes.domain.composition import (
        CompositionLignes,
        LigneKit,
        TYPE_EQUIPEMENT_STRUCTURE,
        _type_equipement,
        _vivier_onduleurs_par_phase,
        avertissement_aucun_onduleur_triphase,
        avertissement_phase_supposee_triphasee,
        avertissement_batterie_pin_sans_correspondance,
        avertissement_batterie_plafond_banc,
        avertissement_batterie_rupture_stock,
        avertissement_vivier_batterie_vide,
        ordonner_par_role,
        quantites_derivees_du_compte,
        role_structure_du_produit,
    )
    kwp = float(kwc or 0)
    if kwp <= 0:
        return []
    from apps.ventes.domain.lignes import LAYOUT_WATT_REPLI
    watt = float(panel_watt or 0) or float(LAYOUT_WATT_REPLI)

    # QJR-OFFGRID — un site ISOLÉ n'a qu'UNE composition possible : onduleur
    # autonome + stockage. La forme deux options (réseau / hybride) n'a alors
    # aucun sens et le drapeau batterie n'est plus une question.
    # QJR400 — LA RÈGLE VIENT DU NOYAU (``utils.options.deux_options_composables``),
    # elle n'est plus écrite ici : c'est le MÊME propriétaire que le prédicat
    # « devis à deux options » du document.
    from apps.ventes.utils.options import deux_options_composables
    hors_reseau = bool(hors_reseau)
    deux_options = deux_options_composables(deux_options, hors_reseau)
    if hors_reseau:
        avec_batterie = True
    # U2 — en forme DEUX OPTIONS, le stockage fait partie du devis : les
    # batteries sont composées même si ``avec_batterie`` est faux, puisque
    # c'est l'option « avec » qui les porte. (RSIZ2 : lu dès le choix de
    # l'hybride, d'où sa place ici.)
    veut_batterie = bool(avec_batterie or deux_options)

    # Catalogue indexé par catégorie. Le filtre de prix passe ICI, une fois
    # pour toutes : aucune branche ne peut ensuite coter un produit non tarifé.
    #
    # STKCAT7 — DEUX rails mènent au vivier ``structure`` :
    #   · le NOM (``classer_produit``), le rail historique ;
    #   · la CATÉGORIE TYPÉE (``Categorie.type_equipement == 'structure'``,
    #     rail ouvert par STKCAT2), pour les produits qu'AUCUN mot-clé ne
    #     trahit — une « Pergola acier 4×3 » EST une structure, mais son nom
    #     ne contient pas « structure » (cause racine de « Pergola
    #     introuvable », audit L3 stock ↔ CRM ↔ devis du 16/09/2026).
    #
    # Les structures NOMMÉES sont tenues à part (``structures_nommees``), et
    # c'est ce vivier-là — celui d'hier — que le toggle acier/alu voit. Une
    # composition SANS ``structure_produit_id`` est donc byte-identique à
    # celle d'hier, et une pergola ne se choisit QUE par son id explicite,
    # jamais par un mot-clé de son nom.
    cible_structure = _entier_ou_none(structure_produit_id)
    structure_par_id = None
    par_type = {}
    structures_nommees = []
    # ACAL63 — les fiches TARIFÉES par id, pour les modules désignés.
    tarifes_par_pk = {}
    for produit in produits:
        if not _has_price(produit):
            continue
        tarifes_par_pk[getattr(produit, 'pk', None)] = produit
        # La résolution PAR ID se fait dans la liste ``produits`` DÉJÀ scopée
        # société par l'appelant, et APRÈS la garde de prix : un id qui
        # désignerait un produit non tarifé — ou celui d'une autre société —
        # ne résout RIEN (et la composition retombe alors sur le toggle).
        if (cible_structure is not None
                and getattr(produit, 'pk', None) == cible_structure):
            structure_par_id = produit
        categorie = classer_produit(getattr(produit, 'nom', ''))
        if categorie == 'structure':
            structures_nommees.append(produit)
        elif (categorie is None
                and _type_equipement(produit) == TYPE_EQUIPEMENT_STRUCTURE):
            categorie = 'structure'
        if categorie:
            par_type.setdefault(categorie, []).append(produit)

    # ── PVMRQ (U3) — restriction par marque épinglée ────────────────────────
    # Miroir EXACT de ``_filtrerParMarque`` (solar.js) : sans préférence, le
    # vivier passe TEL QUEL ; avec une préférence sans aucun candidat, le
    # vivier est VIDE et le rôle est consigné UNE fois (jamais un repli
    # silencieux sur une autre marque — ordre fondateur #5).
    carte_marques = marques if isinstance(marques, dict) else {}
    marques_manquantes = []
    _roles_signales = set()

    def par_marque(pool, role):
        source = list(pool or [])
        marque = str(carte_marques.get(role) or '').strip()
        if not marque:
            return source
        filtres = [p for p in source if _marque_correspond(p, marque)]
        if not filtres and role not in _roles_signales:
            _roles_signales.add(role)
            marques_manquantes.append({'role': role, 'marque': marque})
        return filtres

    def premier(categorie):
        pool = par_marque(par_type.get(categorie), categorie)
        return pool[0] if pool else None

    # ── Panneaux : compte explicite, sinon dérivé de la puissance ──
    # U1 — dérivation AU PLAFOND (``plafond_panneaux``) : 5 kWc en 710 Wc font
    # 8 panneaux, jamais 7. Un compte fourni explicitement est déjà un ENTIER
    # de panneaux ; il garde son arrondi au plus proche.
    nb = (_arrondi_js(nb_panneaux) if float(nb_panneaux or 0) > 0
          else max(1, plafond_panneaux(kwp * 1000 / watt)))

    # ── Onduleur : plus petit modèle ≥ 80 % de la puissance, sinon le plus
    # gros du catalogue ; à puissance égale, Triphasé au-delà de 10 kW ──
    seuil = kwp * 0.8

    # PVCOMPAT — le raccordement déclaré, normalisé une seule fois.
    from apps.ventes.compatibilites import (
        PHASE_MONO, PHASE_TRI, avertissement_raccordement, normaliser_phase)
    phase_client = normaliser_phase(phase)

    # RSIZ4 — TOUT avertissement de cette composition est AUSSI recueilli
    # ici et rendu sur le résultat (``.avertissements_composition``), que
    # l'appelant ait fourni un canal ou non.
    recueil = []

    def _avertir(message):
        """Consigne un avertissement UNE fois (deux onduleurs, un message)."""
        if message not in recueil:
            recueil.append(message)
        if avertissements is None:
            logger.warning('PVCOMPAT: %s', message)
            return
        if message not in avertissements:
            avertissements.append(message)

    # PVCOMPAT — catégories dont le vivier a dû IGNORER le raccordement
    # déclaré. On ne prévient PAS ici : les deux catégories sont toujours
    # explorées (réseau ET hybride) alors qu'une seule part au devis en forme
    # mono-option — avertir depuis le vivier ferait crier l'onduleur invendu.
    # Le message est prononcé plus bas, pour les seules catégories VENDUES.
    replis_phase = {}
    # L-TRI — catégories dont le vivier TRIPHASÉ est VIDE alors que le client
    # est triphasé : la composition a REFUSÉ de coter un monophasé. Même
    # discipline que ``replis_phase`` — on ne prononce le message que pour les
    # catégories réellement VENDUES.
    refus_tri = {}

    def choisir_onduleur(categorie):
        candidats = []
        # PVOND — VERROU DE COMPLÉTUDE, miroir de solar.js::pickInverter : un
        # onduleur au contrat incomplet est écarté de l'auto-composition AVANT
        # le tri par puissance, exactement comme à l'écran.
        # PVCOMPAT/L-TRI — puis le RACCORDEMENT du client réduit le vivier :
        # monophasé (les triphasés sortent, repli toléré) comme triphasé (les
        # monophasés sortent, AUCUN repli).
        complets = _filtrer_onduleurs_complets(
            par_marque(par_type.get(categorie), categorie))
        vivier, replie = _vivier_onduleurs_par_phase(complets, phase_client)
        # RSIZ2 — un hybride qu'AUCUNE batterie tarifée en stock ne sert ne
        # porte pas l'option « avec » (le 30 kW HV face au seul Dyness LV).
        vivier = (_hybrides_servis_par_une_batterie(
            vivier, par_type.get('batterie'))
            if categorie == 'onduleur_hybride' and veut_batterie
            else vivier)
        replis_phase[categorie] = replie
        refus_tri[categorie] = False
        for produit in vivier:
            kw = _parse_kw(getattr(produit, 'nom', ''))
            if kw and kw > 0:
                candidats.append((kw, getattr(produit, 'id', 0) or 0, produit))
        if not candidats:
            # L-TRI — distinguer « catalogue vide pour cette catégorie »
            # (silence historique) de « il y avait des onduleurs, mais AUCUN
            # triphasé » : ce second cas est un REFUS, et un refus se dit.
            refus_tri[categorie] = bool(
                phase_client == PHASE_TRI and complets)
            return None, None
        candidats.sort(key=lambda c: (c[0], c[1]))
        # Le plus petit modèle ≥ 80 % du kWc : sur un vivier déjà réduit au
        # raccordement du client, ce PLANCHER ne peut plus faire changer de
        # phase — un petit kWc prend simplement le plus petit triphasé.
        valides = [c for c in candidats if c[0] >= seuil] or [candidats[-1]]
        meilleure = valides[0][0]
        memes = [c for c in valides if c[0] == meilleure]
        # PVCOMPAT — un raccordement DÉCLARÉ passe devant l'heuristique
        # « ≥ 10 kW ⇒ triphasé » : le client sait de quel abonnement il dispose,
        # la puissance n'en est qu'un indice. Sans déclaration, l'heuristique
        # historique décide seule, à l'identique.
        if phase_client == PHASE_TRI:
            prefere_tri = True
        elif phase_client == PHASE_MONO:
            prefere_tri = False
        else:
            prefere_tri = meilleure >= 10
        assortis = [c for c in memes
                    if _est_triphase(getattr(c[2], 'nom', '')) == prefere_tri]
        retenu = (assortis or memes)[0]
        return retenu[2], retenu[0]

    def quantite_onduleur(kw):
        """Un onduleur suffit dès qu'il couvre le seuil ; sinon on en met assez
        pour absorber le champ (blocs entiers, jamais moins d'un)."""
        if not kw or kw >= seuil:
            return 1
        return max(1, int(math.ceil(kwp / kw)))

    if hors_reseau:
        # QJR-OFFGRID — les deux familles RACCORDÉES ne sont même pas
        # explorées : rien ne pourrait les vendre ici, et les explorer
        # ferait prononcer des avertissements de raccordement sur des
        # onduleurs qui ne partent pas au devis.
        onduleur_reseau = onduleur_hybride = None
        kw_reseau = kw_hybride = None
        onduleur, kw_onduleur = choisir_onduleur('onduleur_offgrid')
    else:
        onduleur_reseau, kw_reseau = choisir_onduleur('onduleur_reseau')
        onduleur_hybride, kw_hybride = choisir_onduleur('onduleur_hybride')
        onduleur = onduleur_hybride if avec_batterie else onduleur_reseau
        kw_onduleur = kw_hybride if avec_batterie else kw_reseau
    # L'onduleur qui PORTE le stockage : l'hybride sur un site raccordé,
    # l'autonome sur un site isolé. C'est lui qui dicte la plage batterie.
    onduleur_stockage = onduleur if hors_reseau else onduleur_hybride

    # PVCOMPAT — le raccordement n'a pas pu être tenu SUR UN ONDULEUR VENDU :
    # on le dit UNE fois. Un repli sur une catégorie qui ne part pas au devis
    # (l'hybride d'un devis « sans batterie », par exemple) ne concerne
    # personne et reste muet.
    _categories_vendues = (
        ('onduleur_offgrid',) if hors_reseau
        else (('onduleur_reseau', 'onduleur_hybride') if deux_options
              else (('onduleur_hybride',) if avec_batterie
                    else ('onduleur_reseau',))))
    _onduleurs_par_categorie = {
        'onduleur_reseau': onduleur_reseau,
        'onduleur_hybride': onduleur_hybride,
        'onduleur_offgrid': onduleur if hors_reseau else None,
    }
    if phase_client and any(
            replis_phase.get(categorie)
            and _onduleurs_par_categorie.get(categorie) is not None
            for categorie in _categories_vendues):
        _avertir(avertissement_raccordement(PHASE_MONO))
    # L-TRI — le raccordement TRIPHASÉ n'a AUCUN onduleur au catalogue sur une
    # catégorie VENDUE : la composition part sans onduleur (jamais un
    # monophasé), et elle le DIT — sinon le devis mentirait par omission.
    if phase_client == PHASE_TRI and any(
            refus_tri.get(categorie) for categorie in _categories_vendues):
        _avertir(avertissement_aucun_onduleur_triphase())
    # RSIZ6 — raccordement INCONNU : l'onduleur triphasé VENDU vient de
    # l'heuristique « ≥ 10 kW » seule ; le commercial doit le vérifier.
    if not phase_client and any(
            _est_triphase(getattr(
                _onduleurs_par_categorie.get(categorie), 'nom', '') or '')
            for categorie in _categories_vendues
            if _onduleurs_par_categorie.get(categorie) is not None):
        _avertir(avertissement_phase_supposee_triphasee())

    # ── Panneau : wattage demandé d'abord, à défaut le plus proche ──
    # PVMRQ — la marque épinglée restreint le vivier AVANT le rapprochement de
    # wattage : la substitution « wattage le plus proche » ne joue plus que
    # DANS la marque retenue, jamais hors d'elle (miroir de l'écran).
    # RSIZ4 — corps extrait tel quel dans :func:`_choisir_panneau`.
    tries, exacts, panneau = _choisir_panneau(
        par_marque(par_type.get('panneau'), 'panneau'), watt)

    # ── PVCOMPAT — LE COUPLE PANNEAU / ONDULEUR EST VÉRIFIÉ ────────────────
    # Les deux choix ci-dessus sont INDÉPENDANTS : rien ne garantissait qu'ils
    # allaient ensemble. On demande au noyau électrique son verdict et on agit
    # SANS JAMAIS produire une composition morte :
    #   · incompatible → on cherche un autre panneau du vivier (le vivier DÉJÀ
    #     restreint par la marque épinglée : on ne contourne pas une consigne
    #     de gamme pour réparer une incompatibilité) ; si aucun ne va, on GARDE
    #     le choix d'origine et on DIT le problème ;
    #   · réserve      → on garde et on DIT (écrêtage : ça s'installe, ça
    #     produit moins — le client doit l'apprendre du devis, pas du toit) ;
    #   · inconnu      → on se tait : la fiche incomplète est déjà signalée
    #     ailleurs (verrou de complétude), le répéter ne dirait rien de neuf.
    onduleurs_vendus = [o for o in (
        (onduleur_reseau, onduleur_hybride) if deux_options else (onduleur,))
        if o is not None]
    if panneau is not None and onduleurs_vendus:
        from apps.ventes.compatibilites import (
            STATUT_INCOMPATIBLE, STATUT_RESERVE,
            avertissement_panneau_onduleur)
        statut, coince = _statut_couple_panneau(panneau, onduleurs_vendus)
        if statut == STATUT_INCOMPATIBLE:
            # Repli ORDONNÉ : d'abord les wattages exacts (l'ordre de départage
            # de l'écran), puis les plus proches — la même préférence que le
            # choix initial, appliquée aux candidats restants.
            replis = [c[1] for c in exacts] + [
                c[1] for c in sorted(tries, key=lambda c: abs(c[0] - watt))]
            vus = set()
            for candidat in replis:
                if id(candidat) in vus or candidat is panneau:
                    vus.add(id(candidat))
                    continue
                vus.add(id(candidat))
                statut_bis, coince_bis = _statut_couple_panneau(
                    candidat, onduleurs_vendus)
                if statut_bis != STATUT_INCOMPATIBLE:
                    _avertir(
                        'Panneau remplacé pour compatibilité électrique : '
                        '« %s » ne se raccorde pas à l\'onduleur retenu, '
                        '« %s » a été composé à la place.'
                        % (getattr(panneau, 'nom', '') or '?',
                           getattr(candidat, 'nom', '') or '?'))
                    panneau, statut, coince = candidat, statut_bis, coince_bis
                    break
        if statut in (STATUT_INCOMPATIBLE, STATUT_RESERVE) and coince:
            _avertir(avertissement_panneau_onduleur(
                panneau, coince[0], coince[1]))

    # ── ACAL63 — UNE LIGNE PANNEAU PAR MODÈLE DÉSIGNÉ ─────────────────────
    # Le calepinage a posé des modules PRÉCIS (``modules[].produitId``) : le
    # devis vend CES fiches-là, une ligne par modèle, au compte posé — jamais
    # le moins cher du wattage, jamais un seul panneau pour tout le site.
    panneaux_designes = None
    designes = [m for m in (modeles or ())
                if isinstance(m, dict) and int(m.get('count') or 0) > 0]
    if any(m.get('produit_id') for m in designes):
        panneaux_designes = []
        marque_panneau = str(carte_marques.get('panneau') or '').strip()
        for modele in designes:
            n_modele = int(modele.get('count') or 0)
            if modele.get('produit_id'):
                choisi = tarifes_par_pk.get(
                    _entier_ou_none(modele.get('produit_id')))
                if choisi is None:
                    # Fiche absente / non tarifée : refus NOMMÉ prononcé par
                    # ``pipeline.verifier`` — jamais un remplaçant ici.
                    continue
                if marque_panneau and not _marque_correspond(
                        choisi, marque_panneau):
                    _avertir(
                        'Le module désigné par le calepinage « %s » n\'est '
                        'pas de la marque épinglée « %s » : le module désigné '
                        'a été retenu.'
                        % (getattr(choisi, 'nom', '') or '?', marque_panneau))
            else:
                w_modele = int(_entier_ou_none(modele.get('watt')) or watt)
                au_watt = [c for c in tries if c[0] == w_modele]
                choisi = (au_watt[0][1] if au_watt
                          else (min(tries, key=lambda c: abs(c[0] - w_modele))[1]
                                if tries else None))
                if choisi is None:
                    continue
            panneaux_designes.append((choisi, n_modele))
            # PVCOMPAT — chaque modèle est jugé face aux onduleurs vendus ; un
            # module DÉSIGNÉ n'est jamais remplacé, le problème est DIT.
            if onduleurs_vendus:
                from apps.ventes.compatibilites import (
                    STATUT_INCOMPATIBLE, STATUT_RESERVE,
                    avertissement_panneau_onduleur)
                statut_m, coince_m = _statut_couple_panneau(
                    choisi, onduleurs_vendus)
                if statut_m in (STATUT_INCOMPATIBLE, STATUT_RESERVE) \
                        and coince_m:
                    _avertir(avertissement_panneau_onduleur(
                        choisi, coince_m[0], coince_m[1]))
        if panneaux_designes:
            nb = sum(n for _, n in panneaux_designes)
            panneau = panneaux_designes[0][0]

    # ── Batteries : cible = kWc arrondi au multiple de 5 (5 kWh au minimum),
    # servie en modules HOMOGÈNES (un seul calibre par banque — voir la garde
    # plus bas, après le choix du vivier) ──
    # TOLÉRANCE DEUX ORTHOGRAPHES : la marque s'écrit « Dyness » (correction
    # fondateur 2026-08-18) ; un produit encore nommé « Deyness » (base non
    # migrée, saisie manuelle, fixture ancienne) doit rester reconnu, sans quoi
    # le vivier retomberait sur TOUTES les batteries du catalogue.
    # DIM2 — une cible EXPLICITE (balayage du stockage) prime sur la règle
    # kWc ; sans elle, la règle historique décide seule, à l'octet près.
    if batterie_cible_kwh is not None and float(batterie_cible_kwh) > 0:
        cible_kwh = max(5, _arrondi_js(float(batterie_cible_kwh) / 5) * 5)
    else:
        cible_kwh = max(5, _arrondi_js(kwp / 5) * 5)
    # PVOND — GARDE BATTERIE PILOTÉ PAR LA DONNÉE (remplace le mot-clé PVG4) :
    # une batterie n'entre au vivier que si sa TENSION NOMINALE tombe dans la
    # PLAGE BATTERIE de l'onduleur retenu ci-dessus. Le repli par mot-clé
    # « haute tension » ne joue QUE lorsque L'ONDULEUR ne déclare aucune plage
    # (catalogue non renseigné : comportement d'hier, byte-identique) ; dès
    # qu'une plage existe, une candidate sans tension mesurée est EXCLUE.
    # Sur un devis SANS batterie, ``onduleur`` vaut l'onduleur réseau : la
    # question ne se pose pas (le vivier n'est lu que si ``avec_batterie``).
    # U2 — la batterie pend TOUJOURS à l'onduleur HYBRIDE : en forme deux
    # options, c'est lui qui décide de la plage, jamais l'onduleur réseau de
    # l'option « sans ».
    # QJR-OFFGRID — sur un site isolé, c'est l'onduleur AUTONOME qui porte le
    # stockage (``onduleur_stockage``), jamais l'hybride (absent ici).
    _plage_bat = _plage_batterie_de_l_onduleur(
        onduleur_stockage if veut_batterie else onduleur)
    # PVMRQ — la compatibilité ÉLECTRIQUE se calcule sur le vivier COMPLET
    # (c'est elle qui alimente l'avertissement « vivier vide », un motif
    # DISTINCT de « marque introuvable ») ; la marque ne restreint qu'ENSUITE.
    # Même ordre que l'écran et que ``_pick_product`` : garde métier d'abord.
    # BATHOMO (26/08/2026, F1 recalé) — DEUX VIVIERS, PAS UN. La
    # COMPATIBILITÉ (tension) est un fait électrique qui s'applique TOUJOURS ;
    # le STOCK, lui, ne s'applique QU'AU CHOIX ÉCONOMIQUE (une composition
    # SANS pin — une NOUVELLE sélection). Un devis qui vend DÉJÀ un calibre
    # (``batterie_module_kwh``) l'a COMMIS : la loi fondateur est « la page
    # suit les articles du devis », donc le pin reste composable même si son
    # stock est tombé à 0 depuis — repeindre la banque en 10 kWh (un module
    # que ce devis ne vend PAS) serait exactement la violation que ce
    # correctif devait éliminer, et avec les DEUX calibres à 0 la page
    # mourrait sur un devis pourtant déjà signé. SCOPÉ AU RÔLE BATTERIE SEUL :
    # aucun autre rôle (panneaux/onduleurs) n'a cette garde de stock — un
    # filtre global casserait la composition pour un catalogue au stock non
    # suivi (cf. ``_batterie_en_stock``).
    batteries_compat = [(_parse_kwh(getattr(p, 'nom', '')), p)
                        for p in par_marque(
                            [p for p in par_type.get('batterie') or []
                             if _batterie_compatible(p, _plage_bat)],
                            'batterie')]
    dyness_compat = [b for b in batteries_compat
                     if any(marque in _sans_accents(getattr(b[1], 'nom', ''))
                            for marque in ('dyness', 'deyness'))]
    vivier_compat = dyness_compat or batteries_compat
    # Le vivier ÉCONOMIQUE (nouvelle sélection, sans pin) : compatible ET en
    # stock — sous-ensemble du vivier compatible, jamais un second filtrage
    # indépendant (une marque non stockée reste hors des deux).
    vivier_stock = [(cap, p) for cap, p in vivier_compat
                    if _batterie_en_stock(p)]
    # A1 — ``bat5_compat``/``bat10_compat`` (le vivier COMPATIBLE, 5/10 SEUL)
    # ont disparu : le pin résout désormais N'IMPORTE QUEL calibre du vivier
    # compatible (recherche directe dans ``vivier_compat``, voir plus bas) —
    # seul le repli ÉCONOMIQUE (sans pin) reste borné à 5/10, et lui reste
    # STOCK-gaté.
    bat5_stock = next((p for cap, p in vivier_stock if cap == 5), None)
    bat10_stock = next((p for cap, p in vivier_stock if cap == 10), None)
    # ── BANQUE HOMOGÈNE + ÉCONOMIE DE CALIBRE (fondateur 26/08/2026) ──
    # JAMAIS un mélange de calibres dans la même banque : c'est électriquement
    # interdit (des modules 5 kWh et 10 kWh en parallèle/série ne s'équilibrent
    # pas), et c'est ce mélange, composé côté serveur, qui a fait retirer le
    # Dyness 10 kWh du stock de production (cf. ``apps.stock.management.
    # commands.seed_catalogue``).
    #
    # Pour CHAQUE calibre disponible (en stock, compatible, et dont le
    # plafond ``bat_max_modules_par_banc`` n'est pas dépassé — cf.
    # ``_max_modules_par_banc``), UNE SEULE candidate homogène est générée :
    # le plus petit N de modules IDENTIQUES qui ATTEINT OU DÉPASSE
    # ``cible_kwh`` (plafond arrondi, jamais un manque — « extra batteries
    # might add extra panels with extra cost, that is still fine »). Parmi
    # les candidates retenues, celle au prix TTC TOTAL LE PLUS BAS gagne,
    # égalité tranchée par le MOINS de modules (fondateur 26/08/2026 :
    # l'économie décide, pas une préférence de calibre — 2×5 kWh à 28 000
    # TTC bat 1×10 kWh à 30 000 pour une cible de 10 kWh dès que les modules
    # 5 kWh sont moins chers au kWh). C'est ce qui fait grandir la banque en
    # 5 kWh, sans jamais glisser vers le 10 kWh, tant que ce dernier reste
    # plus cher au kWh — et REDEVENIR compétitif tout seul si son prix ou
    # son stock changent. Aucun mélange n'est jamais formé : au plus UN des
    # deux compteurs ci-dessous est non nul.
    #
    # ``batterie_module_kwh`` COURT-CIRCUITE ce choix économique quand
    # l'appelant impose un calibre précis (module déjà engagé par un devis) :
    # la banque grandit alors en N modules de CE seul calibre, jamais l'autre
    # — c'est ce qui garantit que l'échelle explorée pour UN devis ne bascule
    # jamais vers un autre calibre que celui qu'il vend déjà. LE PIN LIT LE
    # VIVIER COMPATIBLE (F1) — jamais le vivier stock : le module déjà engagé
    # reste composable même hors stock, SEULE la sélection ÉCONOMIQUE (sans
    # pin) est stock-gatée.

    def _candidat(calibre, produit):
        """Une candidate homogène ``(prix_ttc, n, calibre, produit)`` pour ce
        calibre, ou ``None`` si son plafond fondateur de modules est dépassé."""
        n = max(1, int(math.ceil(cible_kwh / calibre - 1e-9)))
        plafond = _max_modules_par_banc(produit)
        if plafond is not None and n > plafond:
            return None
        prix_ttc = _prix_ttc_batterie(produit, n, taux_tva)
        return (round(prix_ttc, 2), n, calibre, produit)

    calibre_impose = None
    if batterie_module_kwh is not None:
        try:
            calibre_impose = float(batterie_module_kwh)
        except (TypeError, ValueError):
            calibre_impose = None

    # A1 (revue adversariale Fable, 26/08/2026) — LE PIN N'EST PLUS UN
    # WHITELIST 5/10. ``module_batterie_du_devis`` (dimensionnement.py, F6)
    # rend N'IMPORTE QUEL calibre positif lu sur les lignes du devis (le
    # Deye BOS-B-Pack16, 16 kWh, est un produit RÉEL des gammes) : un pin qui
    # ne matchait QUE 5.0/10.0 laissait un devis 16 kWh retomber en silence
    # sur le choix économique 5/10 — repeindre la banque dans un calibre que
    # ce devis ne vend PAS, exactement la violation que ce chantier devait
    # fermer. Résolution par CALIBRE LE PLUS PROCHE dans le vivier COMPATIBLE
    # (tolérance ±1 kWh, la même que ``_compter_modules_batterie``/
    # ``module_batterie_du_devis``), pour N'IMPORTE QUEL calibre du vivier —
    # jamais restreinte à 5/10.
    #
    # PIN SANS CORRESPONDANCE ⇒ AUCUN REPLI ÉCONOMIQUE (nouveauté A1) :
    # « honest absence beats a wrong pairing » (Fable) — si le calibre déjà
    # vendu n'existe même pas dans le vivier compatible (ex. un système HAUTE
    # TENSION jamais composable sous un onduleur basse tension), retomber sur
    # le choix économique 5/10 fabriquerait une banque d'un AUTRE calibre que
    # celui du devis. La composition part alors SANS batterie (même chemin
    # honnête que le vivier vide), et — en amont — l'échelle de paliers
    # (``dimensionnement.echelle_paliers_batterie``) omet purement ses rangs
    # au lieu d'en proposer dans le mauvais calibre : chaque cible sondée
    # retombe sur une capacité nulle, ``reels`` reste vide, la fonction rend
    # ``[]``. Un pin qui MATCHE mais dont le plafond de modules rejette la
    # seule candidate possible garde en revanche le repli économique
    # ci-dessous (F3, comportement inchangé — un plafond n'est pas une
    # absence de calibre).
    candidat_impose = None
    pin_sans_correspondance = False
    if calibre_impose is not None:
        correspondance = next(
            ((cap, p) for cap, p in vivier_compat
             if abs(cap - calibre_impose) < 1.0), None)
        if correspondance is not None:
            cap_trouve, produit_trouve = correspondance
            candidat_impose = _candidat(cap_trouve, produit_trouve)
        else:
            pin_sans_correspondance = True

    candidats = []
    if candidat_impose is not None:
        candidats = [candidat_impose]
    elif not pin_sans_correspondance:
        # Aucun calibre imposé, OU un calibre imposé dont le plafond de
        # modules interdit la seule candidate qu'il permettrait : repli sur
        # le choix économique parmi les calibres 5/10 EN STOCK — jamais une
        # banque vide du seul fait d'un calibre non stocké ou plafonné, MAIS
        # jamais non plus un calibre hors stock ressuscité par ce repli
        # (F1 : le repli économique reste stock-gaté, seul le PIN d'origine
        # bypassait le stock).
        for calibre, produit in ((5, bat5_stock), (10, bat10_stock)):
            if produit is None:
                continue
            candidat = _candidat(calibre, produit)
            if candidat is not None:
                candidats.append(candidat)

    if veut_batterie and not candidats:
        # AUCUNE candidate — via le pin ou l'économie : la composition part
        # sans batterie (jamais une banque fabriquée), mais elle le DIT —
        # sinon le devis mentait par omission. C'est CETTE garde qui rend
        # l'option « avec batterie » honnêtement non-servable (``avec_ok``/
        # ``variantes_servables``, quote_engine/builder.py) : aucune ligne
        # batterie n'est composée, donc ``has_batterie`` retombe à faux tout
        # seul — aucune machinerie neuve à câbler ici.
        #
        # F5 — LE DIAGNOSTIC SUIT LA VRAIE CAUSE (quatre messages distincts,
        # jamais « changez d'onduleur » quand le vrai geste est de
        # réapprovisionner, d'augmenter un plafond, ou de vérifier le
        # calibre) :
        #   0. (A1) le devis vend DÉJÀ un calibre précis, et ce calibre
        #      N'EXISTE PAS dans le vivier compatible → message dédié,
        #      jamais confondu avec « aucune batterie compatible » (le
        #      vivier peut très bien porter D'AUTRES calibres compatibles).
        #   1. vivier COMPATIBLE vide → aucune batterie ne convient à cet
        #      onduleur (tension) : le message historique.
        #   2. vivier compatible non vide mais vivier STOCK vide, et aucun
        #      pin n'a résolu (F3/F1) → rupture de stock.
        #   3. sinon (du stock existait ou un pin compatible existait) mais
        #      ``candidats`` est quand même vide → le plafond de modules a
        #      rejeté toutes les candidates possibles (F3).
        if pin_sans_correspondance:
            message = avertissement_batterie_pin_sans_correspondance(
                calibre_impose)
        elif not vivier_compat:
            message = avertissement_vivier_batterie_vide(_plage_bat)
        elif not vivier_stock and candidat_impose is None:
            message = avertissement_batterie_rupture_stock()
        else:
            message = avertissement_batterie_plafond_banc()
        # RSIZ4 — même canal que les autres avertissements (recueil + liste
        # de l'appelant, ou journal quand il n'en porte aucune).
        _avertir(message)

    bat5 = bat10 = None
    nb5, nb10 = 0, 0
    if candidats:
        candidats.sort(key=lambda c: (c[0], c[1]))
        _prix_retenu, n_retenu, calibre_retenu, produit_retenu = candidats[0]
        # ``produit_retenu`` — jamais ``bat5_stock``/``bat10_stock`` : un pin
        # (F1) résout depuis le vivier COMPATIBLE, qui peut désigner un
        # produit hors stock que le vivier stock-gaté ne connaît pas.
        if calibre_retenu == 5:
            bat5, nb5 = produit_retenu, n_retenu
        else:
            bat10, nb10 = produit_retenu, n_retenu

    # ── Structure : l'ID EXPLICITE d'abord, sinon le type demandé ─────────
    # STKCAT1/STKCAT7 — ``structure_produit_id`` est PRIORITAIRE sur
    # ``structure_type`` (l'ALIAS DÉPRÉCIÉ) dès qu'il est fourni : les deux ne
    # se combinent JAMAIS. Un id désigne le produit LUI-MÊME, donc ni le
    # filtre par mot-clé acier/alu ni la marque épinglée du rôle ne
    # s'appliquent — le commercial a déjà choisi, on ne re-choisit pas à sa
    # place (et un vivier vidé par une épingle ne peut donc pas lui reprendre
    # son produit).
    # PVMRQ — SANS id, le comportement est celui d'hier au caractère près :
    # DEUX rôles distincts (``structure_acier`` / ``structure_alu``, comme
    # ``ROLES_AUTO_COMPOSITION``), chacun avec sa marque épinglée appliquée
    # sur le sous-vivier déjà filtré par mot-clé (même patron que l'écran).
    # Une par panneau, comme avant.
    voulu = ('alu' if _sans_accents(structure_type).startswith('alu')
             else 'acier')
    if structure_par_id is not None:
        structure = structure_par_id
    else:
        structure = next(iter(par_marque(
            [p for p in structures_nommees
             if voulu in _sans_accents(getattr(p, 'nom', ''))],
            'structure_alu' if voulu == 'alu' else 'structure_acier')), None)
    # RÈGLE D'ÉMISSION DU RÔLE (contrat ``devis_composition.json``) : le rôle
    # suit le NOM DU PRODUIT RETENU, jamais le toggle demandé.
    role_structure = role_structure_du_produit(structure, voulu)

    # ── Câbles Nexans 6 mm² AU MÈTRE (C4/PVCBL, fondateur 18-19/08) ─────────
    # VERROU DE CONDITIONNEMENT : le métrage est en MÈTRES, donc un produit
    # conditionné en ROULEAU/touret (« … (100m) ») ne doit JAMAIS entrer au
    # vivier — même chiffré, même seul candidat. L'incident fondateur du 19/08
    # (60 « unités » d'un rouleau de 100 m = 71 400 MAD de câble) vient
    # exactement de là. Sans candidat au mètre : aucune ligne, jamais un repli
    # silencieux sur un autre conditionnement.
    def choisir_cable(role):
        pool = par_marque(
            [p for p in par_type.get(role) or []
             if _est_au_metre(getattr(p, 'nom', ''))], role)
        # Préférence NEXANS : un fournisseur confirmé par le fondateur, pas une
        # préférence de gamme — elle joue DANS le vivier déjà filtré.
        return next(
            (p for p in pool
             if 'nexans' in _sans_accents(getattr(p, 'nom', ''))),
            next(iter(pool), None))

    cable_dc = choisir_cable('cable_dc')
    cable_terre = choisir_cable('cable_terre')

    # ── Paliers de 5 kWc — ne servent plus QUE au métrage du câble de terre ──
    blocs = max(1, _arrondi_js(kwp / 5))

    # ── L-FORFAIT (fondateur 24/08/2026) — les trois forfaits se cotent AU
    # PANNEAU, depuis le BARÈME PORTÉ PAR LE PRODUIT (cf. ``prix_forfait_ht``) :
    # plus de marches par bloc de 5 kWc, et plus aucune conversion TTC→HT —
    # c'est pourquoi ``taux_tva`` ne sert plus ici.
    #
    # Le barème est appliqué à ces TROIS rôles NOMMÉMENT, jamais dans
    # ``ajouter`` : une part « par panneau » posée par erreur sur un produit
    # vendu à la quantité (panneau, structure, socle…) se multiplierait alors
    # DEUX fois — une fois dans le prix, une fois dans la quantité.
    produit_accessoires = premier('accessoires')
    produit_tableau = premier('tableau')
    produit_installation = premier('installation')

    # ── Smart Meter + clé Wifi : UNIQUEMENT derrière un onduleur Huawei ──
    # (miroir du garde ``info_hw`` de l'ancien simulateur). L'écran teste les
    # DEUX onduleurs parce qu'il les propose tous les deux ; ici un seul est
    # vendu, donc c'est celui-là qui décide.
    # U2 — en forme DEUX OPTIONS les deux onduleurs sont vendus : le garde
    # Huawei teste alors les DEUX, exactement comme l'écran (autoFillLines),
    # sinon l'option Huawei partirait sans son Smart Meter.
    def _est_huawei(produit):
        return 'huawei' in _sans_accents(
            '%s %s' % (getattr(produit, 'marque', '') or '',
                       getattr(produit, 'nom', '') or ''))

    huawei = (_est_huawei(onduleur_reseau) or _est_huawei(onduleur_hybride)
              if deux_options else _est_huawei(onduleur))

    taguees = []

    def ajouter(role, produit, quantite, prix_ht=None):
        """Ajoute une ligne — sauf produit absent du catalogue ou quantité nulle.

        PVORD — chaque ligne est TAGUÉE de son rôle avant l'assemblage final,
        pour que ``ordre_lignes`` puisse la reclasser sans jamais reclassifier
        une désignation après coup.
        """
        if produit is None or quantite <= 0:
            return
        taguees.append((role, LigneKit(
            produit=produit,
            designation=produit.nom,
            quantite=int(quantite),
            prix_unitaire=(Decimal(produit.prix_vente) if prix_ht is None
                           else prix_ht))))

    # Ordre canonique du simulateur (onduleur, accessoires Huawei, panneaux,
    # batteries, structures, socles, forfaits, transport).
    # U2 — forme DEUX OPTIONS : les DEUX onduleurs entrent au devis (le PDF et
    # l'écran répartissent ensuite chaque ligne dans l'option qui la concerne).
    # Forme mono-option : un seul, celui qu'``avec_batterie`` a désigné.
    if deux_options:
        ajouter('onduleur_reseau', onduleur_reseau,
                quantite_onduleur(kw_reseau))
        ajouter('onduleur_hybride', onduleur_hybride,
                quantite_onduleur(kw_hybride))
    else:
        role_ond = ('onduleur_offgrid' if hors_reseau
                    else ('onduleur_hybride' if avec_batterie
                          else 'onduleur_reseau'))
        ajouter(role_ond, onduleur, quantite_onduleur(kw_onduleur))
    ajouter('smart_meter', premier('smart_meter'), 1 if huawei else 0)
    ajouter('wifi_dongle', premier('wifi_dongle'), 1 if huawei else 0)
    if panneaux_designes:
        # ACAL63 — une ligne par modèle (même fiche répétée ⇒ une ligne).
        cumul = {}
        for produit_m, n_m in panneaux_designes:
            cle_m = getattr(produit_m, 'pk', None) or id(produit_m)
            if cle_m in cumul:
                cumul[cle_m] = (produit_m, cumul[cle_m][1] + n_m)
            else:
                cumul[cle_m] = (produit_m, n_m)
        for produit_m, n_m in cumul.values():
            ajouter('panneau', produit_m, n_m)
    else:
        ajouter('panneau', panneau, nb)
    if veut_batterie:
        ajouter('batterie', bat5, nb5)
        ajouter('batterie', bat10, nb10)
    # QJR403 — LES QUANTITÉS DÉRIVÉES DU COMPTE DE PANNEAUX PASSENT PAR LEUR
    # DÉFINITION UNIQUE (:func:`quantites_derivees_du_compte`), pour que le
    # chemin MODE_ECRIRE puisse les RE-DÉRIVER sans écrire une seconde formule.
    _derivees = quantites_derivees_du_compte(nb)
    ajouter(role_structure, structure, _derivees['structure'])
    ajouter('socle', premier('socle'), _derivees['socle'])
    # C4/PVCBL — métrage AU MÈTRE : le DC suit les paires de MPPT, la terre
    # suit les paliers de 5 kWc (25 m de base + 15 m par palier).
    # RSIZ5 — paires DÉRIVÉES du champ et des onduleurs vendus (niveau 3).
    ajouter('cable_dc', cable_dc, metre_cable_dc_par_paires(_paires_mppt(
        mppt_paires, paires_mppt_derivees, nb, kwp, panneau,
        [(o, quantite_onduleur(k)) for o, k in (
            ((onduleur_reseau, kw_reseau), (onduleur_hybride, kw_hybride))
            if deux_options else ((onduleur, kw_onduleur),))
         if o is not None])))
    ajouter('cable_terre', cable_terre, metre_cable_terre(blocs))
    # L-FORFAIT — une SEULE ligne par forfait, quantité 1, dont le prix
    # unitaire EST le total du barème (désignations inchangées). Barème absent
    # du produit ⇒ ``prix_forfait_ht`` rend ``None`` et ``ajouter`` retombe sur
    # le ``prix_vente`` catalogue, comme n'importe quelle autre ligne.
    ajouter('accessoires', produit_accessoires, 1,
            prix_forfait_ht(produit_accessoires, nb))
    ajouter('tableau', produit_tableau, 1,
            prix_forfait_ht(produit_tableau, nb))
    ajouter('installation', produit_installation, 1,
            prix_forfait_ht(produit_installation, nb))
    ajouter('transport', premier('transport'), 1)

    # ── PVORD — ordre PAR DÉFAUT des lignes ────────────────────────────────
    taguees = ordonner_par_role(taguees, ordre_lignes)

    lignes = CompositionLignes(ligne for _, ligne in taguees)
    lignes.roles = [role for role, _ in taguees]
    lignes.nb_panneaux = nb
    # Le wattage RÉELLEMENT retenu peut différer de celui demandé (substitution
    # « le plus proche » quand le catalogue n'a pas la puissance demandée) : on
    # rend le vrai, pour que personne n'affiche un kWc théorique divergent.
    _watt_reel = _parse_watt(getattr(panneau, 'nom', '')) if panneau else None
    lignes.panel_watt_reel = _watt_reel or watt
    lignes.kwc_reel = round(nb * float(lignes.panel_watt_reel) / 1000.0, 3)
    if panneaux_designes:
        # ACAL63 — kWc des lignes = kWc du dessin : la somme modèle par modèle.
        lignes.kwc_reel = round(sum(
            n_m * float(_parse_watt(getattr(p_m, 'nom', '')) or watt)
            for p_m, n_m in panneaux_designes) / 1000.0, 3)
    lignes.blocs = blocs
    lignes.marques_manquantes = marques_manquantes
    lignes.avertissements_composition = list(recueil)
    # DIM2 — LES CAPACITÉS RÉELLEMENT DISPONIBLES, en kWh nominaux, telles que
    # le vivier batterie les a retenues (compatibilité de tension avec
    # l'onduleur hybride comprise). Le balayage du stockage lit CETTE liste
    # pour construire ses paliers : sans elle il devrait redevine
    # « 5 et 10 kWh », c'est-à-dire recréer un second catalogue en dur qui
    # divergerait au premier module ajouté.
    lignes.capacites_batterie_vivier = sorted(
        {float(cap) for cap, _p in vivier_compat if cap and float(cap) > 0})
    return lignes
