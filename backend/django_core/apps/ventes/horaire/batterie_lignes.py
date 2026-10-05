"""Lecture des lignes batterie d'un devis (SPL256, déplacé de ``etude_horaire.py``).

Appartenance d'une ligne à une option, capacité et banque batterie par
option, puissances, rendement aller-retour (sourcé fiche ou hypothèse) — une
feuille qui ne dépend que du journal. ``etude_horaire`` importe les lecteurs
de ses orchestrateurs POUR USAGE (les ``patch.object(EH, …)`` des tests restent
valides). Déplacement pur : corps octet-identiques (seule la profondeur des
imports relatifs locaux change), prouvé par ``tests/golden/split_eh_bat.json``.
"""
import logging

# Même émetteur de journal qu'avant le déplacement (filtres et tests inchangés).
logger = logging.getLogger("apps.ventes.etude_horaire")


def ligne_dans_option(ligne, option):
    """QJR140 — la ligne appartient-elle à CETTE option du devis ?

    ``LigneDevis.variante`` porte l'appartenance EXPLICITEMENT : ``''`` =
    commune aux deux options (le défaut, et la valeur de toute ligne d'un devis
    mono-option), ``'sans'`` / ``'avec'`` = propre à cette option-là. Une ligne
    commune compte dans les deux ; une ligne variantée ne compte que dans la
    sienne. ``option=None`` ⇒ aucune sélection (toutes les lignes).
    """
    if option is None:
        return True
    return (getattr(ligne, 'variante', '') or '') in ('', option)


def capacite_batterie_du_devis(devis, option='avec'):
    """Capacité UTILE (kWh) réellement chiffrée sur UNE option, ou ``None``.

    Somme les lignes classées ``batterie`` par ``services.classer_produit`` (le
    MÊME classifieur que la composition — jamais une seconde règle de
    reconnaissance) en lisant la capacité utile de chaque fiche
    (``dimensionnement.capacite_utile_batterie``).

    QJR140 (audit QJR79) — LA SOMME EST PRISE PAR OPTION, PLUS SUR LE DEVIS
    ENTIER. Cette fonction additionnait TOUTE ligne classée batterie sans
    distinguer l'option qui la porte, alors que le découpage existe en amont
    (``builder._repartir_options`` / ``_battery_kwh_from_items(avec_items…)``).
    Sur un devis à plusieurs paliers de stockage, elle additionnait donc des
    capacités qui ne coexistent dans AUCUNE option vendue — un chiffre qui ne
    décrit rien de ce que le client peut acheter.

    ``option`` vaut ``'avec'`` par DÉFAUT : c'est l'option qui porte le
    stockage, et le seul contexte où une capacité batterie a un sens. Sur un
    devis mono-option, toutes les lignes valent ``variante=''`` (communes) —
    le résultat est donc byte-identique à l'historique pour tout le parc
    existant ; seuls les devis à deux options RÉELLEMENT variantés changent, et
    c'est précisément le cas que le défaut corrige. ``option=None`` rend
    explicitement la somme BRUTE de toutes les lignes (comportement d'avant,
    pour un appelant qui le veut sciemment).

    ``None`` (et non 0,0) quand l'option ne porte aucune batterie : le moteur
    distingue ainsi « pas de stockage » de « stockage de capacité nulle ».
    """
    try:
        from apps.ventes.dimensionnement import capacite_utile_batterie
        from apps.ventes.services import classer_produit
        total = 0.0
        for ligne in devis.lignes.all():
            if not ligne_dans_option(ligne, option):
                continue
            designation = getattr(ligne, 'designation', '') or ''
            if classer_produit(designation) != 'batterie':
                continue
            kwh = capacite_utile_batterie(
                getattr(ligne, 'produit', None), designation)
            if kwh:
                total += float(kwh) * float(getattr(ligne, 'quantite', 0) or 0)
        return total if total > 0 else None
    except Exception:  # noqa: BLE001 — lignes illisibles ⇒ pas de stockage
        logger.warning('capacité batterie illisible', exc_info=True)
        return None


def banque_batterie_du_devis(devis, option='avec'):
    """COUVBAT — la BANQUE de batteries d'UNE option de ce devis, pack par pack.

    Renvoie ``{nb_packs, capacite_utile_totale_kwh, capacite_utile_pack_kwh,
    pack_decharge_kw, pack_charge_kw, ond_decharge_kw, ond_charge_kw}``, ou
    ``None`` quand cette option ne porte AUCUNE ligne batterie (« pas de
    stockage » — jamais un pack de capacité nulle).

    QJR167 (frère non corrigé de QJR140/``capacite_batterie_du_devis``, signalé
    au fold du 30/08) — LA SOMME EST PRISE PAR OPTION, PLUS SUR LE DEVIS ENTIER.
    Cette fonction additionnait TOUTE ligne classée batterie de
    ``devis.lignes.all()`` sans distinguer l'option qui la porte (même bug que
    QJR140, même découpage amont : ``builder._repartir_options``). Sur un devis
    à deux paliers de stockage variantés, elle additionnait donc des capacités
    qui ne coexistent dans AUCUNE option vendue — une banque vendue nulle part,
    qui alimentait pourtant la surface CLIENT du curseur « N batteries »
    (``_couverture_batterie_publique``). Même filtre que QJR140
    (:func:`ligne_dans_option`), même défaut ``'avec'`` (l'option qui porte le
    stockage), même garantie mono-option byte-identique (lignes communes
    ``variante=''`` comptent dans les deux options — le parc existant est
    inchangé) et même repli ``option=None`` pour un appelant qui veut
    sciemment la somme brute.

    LA CAPACITÉ EST UTILE, PAS NOMINALE (règle CAPUTIL) : chaque ligne est lue
    par ``dimensionnement.capacite_utile_batterie`` (fiche ``kwh_usable``,
    sinon ``kwh_nominal × dod_pct``, et seulement en dernier recours le kWh du
    NOM) — jamais un « 5 kWh » codé en dur, qui ne serait qu'un module du
    catalogue du jour. ``capacite_utile_pack_kwh`` est la capacité utile
    MOYENNE d'un pack de CETTE option (total ÷ quantité), c'est-à-dire le
    module que le curseur « N batteries » ajoute réellement.

    Les quatre puissances sont celles de :func:`puissance_batterie_du_devis`
    (elle-même non filtrée par option — hors du périmètre de ce constat, voir
    NOTE ci-dessous), RAMENÉES AU PACK pour les packs (Σ fiches ÷ quantité —
    l'inverse exact du « Σ valeur de fiche × quantité » qui les a construites)
    et laissées telles quelles pour le port batterie de l'onduleur (le même
    onduleur sert toute la banque). ``None`` partout où la fiche ne publie
    rien : le moteur retombe alors sur sa règle conservatrice. Ne lève jamais.
    """
    try:
        from apps.ventes.dimensionnement import capacite_utile_batterie
        from apps.ventes.services import classer_produit
        nb_packs = 0.0
        capacite_totale = 0.0
        for ligne in devis.lignes.all():
            if not ligne_dans_option(ligne, option):
                continue
            designation = getattr(ligne, 'designation', '') or ''
            if classer_produit(designation) != 'batterie':
                continue
            quantite = float(getattr(ligne, 'quantite', 0) or 0)
            if quantite <= 0:
                continue
            nb_packs += quantite
            kwh = capacite_utile_batterie(
                getattr(ligne, 'produit', None), designation)
            if kwh:
                capacite_totale += float(kwh) * quantite
        packs = int(round(nb_packs))
        if packs <= 0 or capacite_totale <= 0:
            return None
        puissances = puissance_batterie_du_devis(devis) or {}

        def _par_pack(cle):
            valeur = puissances.get(cle)
            if not valeur:
                return None
            return float(valeur) / packs

        return {
            'nb_packs': packs,
            'capacite_utile_totale_kwh': capacite_totale,
            'capacite_utile_pack_kwh': capacite_totale / packs,
            'pack_decharge_kw': _par_pack('packs_decharge_kw'),
            'pack_charge_kw': _par_pack('packs_charge_kw'),
            'ond_decharge_kw': (float(puissances['ond_decharge_kw'])
                                if puissances.get('ond_decharge_kw') else None),
            'ond_charge_kw': (float(puissances['ond_charge_kw'])
                              if puissances.get('ond_charge_kw') else None),
        }
    except Exception:  # noqa: BLE001 — lignes illisibles ⇒ pas de banque
        logger.warning('banque batterie illisible', exc_info=True)
        return None


#: Rôles de composition (``composition_residentielle``) qui portent un PORT
#: BATTERIE. Le classifieur de libellés (``classer_produit``) rend les MÊMES
#: deux étiquettes : la sélection des lignes est donc identique qu'on parte
#: d'un devis enregistré ou d'une composition en mémoire.
ROLES_ONDULEUR = ('onduleur_hybride', 'onduleur_reseau')


def _puissance_fiche(produit, cle):
    """Une clé de fiche technique, en float > 0, ou ``None``. Ne lève jamais."""
    from apps.stock.selectors import specs_for_produit
    # ``specs_for_produit`` rend le bloc du ``type_fiche`` À PLAT — pas un dict
    # de blocs. (Le lire comme un dict de blocs a réellement laissé ce moteur
    # muet : la clé cherchée existait, elle n'était jamais atteinte.)
    valeur = (specs_for_produit(produit) or {}).get(cle)
    if valeur in (None, ''):
        return None
    valeur = float(valeur)
    return valeur if valeur > 0 else None


def puissances_batterie_des_lignes(lignes, roles=None):
    """LA source unique des puissances du chemin batterie d'une composition.

    L'ÉTUDE (:func:`etude_horaire_pour_devis`, sur un devis enregistré) et le
    DIMENSIONNEMENT (le balayage DIM2, sur des compositions en mémoire) lisent
    cette MÊME fonction : deux lectures parallèles finiraient par diverger, et
    l'écran recommanderait une capacité calibrée sur un autre client que celui
    que le devis chiffre.

    Ne répond que par des grandeurs réellement fichées
    (``apps.stock.selectors.specs_for_produit``, lecture cross-app par
    sélecteur, jamais ``stock.models``).

    DEUX GOULOTS, ET LA QUANTITÉ COMPTE DANS LES DEUX (fondateur, 24/08/2026 :
    « n'oublie pas de considérer le cas avec deux batteries où c'est 100 A par
    batterie ») :

    * LES PACKS — Σ (valeur de fiche × quantité de la ligne) sur TOUTES les
      lignes batterie, chaque unité à SA valeur : une composition 10 + 5 kWh
      additionne deux fiches différentes. La puissance de décharge est une
      capacité PHYSIQUE de chaque pack, et deux packs en parallèle en
      fournissent bien la somme — même arithmétique que le kW d'onduleur ×
      quantité de la règle des 80 % (``dimensionnement._lire_composition``).
      Un pack dont la fiche ne publie rien compte pour ZÉRO : on ne lui invente
      pas une puissance, et la somme reste donc PROUVÉE, quitte à sous-estimer.
    * LE PORT BATTERIE DE L'ONDULEUR — Σ (valeur de fiche × quantité), même
      règle (deux onduleurs, deux ports).

    La borne servie au moteur est le PLUS PETIT des deux goulots prouvés.

    POURQUOI LA CHARGE NE SERT JAMAIS DE BORNE DE DÉCHARGE. Ce sont deux
    grandeurs distinctes : le Dyness DL5.0C accepte 75 A et en rend 100 — sa
    datasheet publie les deux lignes séparément. Recopier l'une dans l'autre
    inventerait une équivalence que le constructeur ne publie pas. Sans
    décharge publiée, le moteur applique la règle CONSERVATRICE, et le dit.

    ``roles`` (facultatif) : les rôles rendus par ``composition_residentielle``,
    alignés sur ``lignes``. Absents ⇒ les libellés sont classés par
    ``services.classer_produit``, qui rend les mêmes étiquettes.

    Renvoie ``{decharge_kw, charge_kw, packs_decharge_kw, packs_charge_kw,
    ond_decharge_kw, ond_charge_kw, decharge_source, charge_source}`` — les
    ``*_kw`` valant ``None`` quand rien n'est prouvé. Ne lève jamais.
    """
    resultat = {
        'decharge_kw': None, 'charge_kw': None,
        'packs_decharge_kw': None, 'packs_charge_kw': None,
        'ond_decharge_kw': None, 'ond_charge_kw': None,
        'decharge_source': 'aucune_publiee_regle_conservatrice',
        'charge_source': None,
    }
    try:
        from apps.ventes.services import classer_produit
        roles = list(roles or ())
        cumuls = {'packs_decharge_kw': 0.0, 'packs_charge_kw': 0.0,
                  'ond_decharge_kw': 0.0, 'ond_charge_kw': 0.0}
        for index, ligne in enumerate(lignes):
            produit = getattr(ligne, 'produit', None)
            if produit is None:
                continue
            if index < len(roles):
                role = roles[index]
            else:
                role = classer_produit(getattr(ligne, 'designation', '') or '')
            if role == 'batterie':
                champs = (('packs_decharge_kw', 'max_decharge_kw'),
                          ('packs_charge_kw', 'max_charge_kw'))
            elif role in ROLES_ONDULEUR:
                champs = (('ond_decharge_kw', 'bat_max_decharge_kw'),
                          ('ond_charge_kw', 'bat_max_charge_kw'))
            else:
                continue
            quantite = float(getattr(ligne, 'quantite', 0) or 0)
            if quantite <= 0:
                continue
            for cumul, cle in champs:
                valeur = _puissance_fiche(produit, cle)
                if valeur:
                    cumuls[cumul] += valeur * quantite

        for cle, valeur in cumuls.items():
            if valeur > 0:
                resultat[cle] = valeur

        # LE MIN DES GOULOTS PROUVÉS — jamais une borne sur un goulot qu'on ne
        # connaît pas. Un seul des deux publié ⇒ c'est lui, seul.
        for sens, packs, port in (
                ('decharge', 'packs_decharge_kw', 'ond_decharge_kw'),
                ('charge', 'packs_charge_kw', 'ond_charge_kw')):
            prouves = [resultat[packs], resultat[port]]
            prouves = [v for v in prouves if v]
            if prouves:
                resultat['%s_kw' % sens] = min(prouves)
        if resultat['decharge_kw']:
            resultat['decharge_source'] = _source_borne(
                resultat['packs_decharge_kw'], resultat['ond_decharge_kw'],
                'fiche:max_decharge_kw', 'fiche:ond_bat_max_decharge_kw')
        if resultat['charge_kw']:
            resultat['charge_source'] = _source_borne(
                resultat['packs_charge_kw'], resultat['ond_charge_kw'],
                'fiche:max_charge_kw', 'fiche:ond_bat_max_charge_kw')
    except Exception:  # noqa: BLE001 — fiche illisible ⇒ règle conservatrice
        logger.warning('puissances batterie illisibles', exc_info=True)
    return resultat


def _source_borne(packs, port, source_packs, source_port):
    """QUI a borné : les packs, le port, ou les deux à égalité.

    Un plafond muet est un plafond incompris — c'est la même exigence que le
    ``plafond_motif`` du balayage DIM2. Le devis qui restitue moins doit
    pouvoir DIRE lequel des deux goulots l'a décidé.
    """
    if packs and port:
        if packs < port:
            return source_packs
        if port < packs:
            return source_port
        return '%s+%s' % (source_packs, source_port)
    return source_packs if packs else source_port


#: QJR137 — étiquette de source quand AUCUNE fiche batterie ne publie son
#: rendement aller-retour : le moteur applique l'hypothèse de référence
#: ``pricing.BATTERY_ROUNDTRIP`` et le DIT (chaîne lue par les hypothèses
#: affichées, jamais un silence).
RENDEMENT_SOURCE_HYPOTHESE = 'hypothese:pricing.BATTERY_ROUNDTRIP'


RENDEMENT_SOURCE_FICHE = 'fiche:bat_rendement_ar_pct'


def rendement_batterie_des_lignes(lignes, roles=None):
    """QJR137 — le rendement aller-retour PUBLIÉ des batteries d'une composition.

    La CAPACITÉ d'une banque est lue sur les fiches depuis PV5 ; le RENDEMENT
    ALLER-RETOUR, lui, restait un forfait de code (0,90) qu'aucun champ ne
    pouvait porter — alors qu'il borne ``restitue_kwh``, donc l'économie « avec
    batterie » montrée au client. ``bat_rendement_ar_pct`` (QJR137) le porte
    désormais ; cette fonction le lit par le sélecteur de ``stock`` (jamais
    ``stock.models``), comme les puissances juste au-dessus.

    RÈGLE DE COMBINAISON — PROUVÉE OU RIEN. Un rendement ne s'invente ni ne se
    moyenne : deux packs de rendements différents forment une banque dont le
    rendement réel dépend de la répartition des flux, que rien ne publie. On
    retient donc le MINIMUM des valeurs publiées (borne conservatrice, du même
    esprit que le ``min()`` des deux goulots de puissance), et il faut que
    TOUTES les lignes batterie en publient une : une seule fiche muette rend le
    rendement de la banque non prouvé, donc ``None``.

    Renvoie ``{rendement, source}`` — ``rendement`` valant ``None`` quand rien
    n'est prouvé, et ``source`` disant alors que l'hypothèse de référence
    s'applique. Ne lève jamais.
    """
    resultat = {'rendement': None, 'source': RENDEMENT_SOURCE_HYPOTHESE}
    try:
        from apps.ventes.services import classer_produit
        roles = list(roles or ())
        publies = []
        lignes_batterie = 0
        for index, ligne in enumerate(lignes or ()):
            if index < len(roles):
                role = roles[index]
            else:
                role = classer_produit(getattr(ligne, 'designation', '') or '')
            if role != 'batterie':
                continue
            quantite = float(getattr(ligne, 'quantite', 0) or 0)
            if quantite <= 0:
                continue
            lignes_batterie += 1
            produit = getattr(ligne, 'produit', None)
            if produit is None:
                continue
            pct = _puissance_fiche(produit, 'rendement_ar_pct')
            if pct and 0 < pct <= 100:
                publies.append(pct / 100.0)
        if lignes_batterie and len(publies) == lignes_batterie:
            resultat['rendement'] = min(publies)
            resultat['source'] = RENDEMENT_SOURCE_FICHE
    except Exception:  # noqa: BLE001 — fiche illisible ⇒ hypothèse déclarée
        logger.warning('rendement batterie illisible', exc_info=True)
        return {'rendement': None, 'source': RENDEMENT_SOURCE_HYPOTHESE}
    return resultat


def rendement_batterie_du_devis(devis):
    """:func:`rendement_batterie_des_lignes` sur les lignes d'un devis."""
    try:
        return rendement_batterie_des_lignes(devis.lignes.all())
    except Exception:  # noqa: BLE001 — lignes illisibles ⇒ hypothèse déclarée
        logger.warning('lignes du devis illisibles', exc_info=True)
        return {'rendement': None, 'source': RENDEMENT_SOURCE_HYPOTHESE}


def puissance_batterie_du_devis(devis):
    """:func:`puissances_batterie_des_lignes` sur les lignes d'un devis."""
    try:
        return puissances_batterie_des_lignes(devis.lignes.all())
    except Exception:  # noqa: BLE001 — lignes illisibles ⇒ règle conservatrice
        logger.warning('lignes du devis illisibles', exc_info=True)
        return {'decharge_kw': None, 'charge_kw': None,
                'packs_decharge_kw': None, 'packs_charge_kw': None,
                'ond_decharge_kw': None, 'ond_charge_kw': None,
                'decharge_source': 'aucune_publiee_regle_conservatrice',
                'charge_source': None}
