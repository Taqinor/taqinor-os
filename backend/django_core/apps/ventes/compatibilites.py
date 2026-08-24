# -*- coding: utf-8 -*-
"""PVCOMPAT (fondateur 20/08/2026) — LA COMPATIBILITÉ DEUX À DEUX DU STOCK.

« Il n'y a pas de PV parce que le courant maxi par MPPT de cet onduleur est
sous le courant de nos panneaux. » Cette phrase-là n'existait NULLE PART :
l'écran Stock savait dire si une FICHE était complète, jamais si le produit
était INSTALLABLE avec le reste du catalogue.

Ce module répond à trois questions, et à elles seules :

1. ``verdict_panneau_onduleur`` — ce panneau et cet onduleur vont-ils ensemble ?
2. ``verdict_batterie_onduleur`` — cette batterie s'accroche-t-elle à cet
   onduleur ?
3. ``compatibilites_du_produit`` — la synthèse d'UN produit face à TOUT le
   stock de sa société (contrat committé
   ``apps/stock/contract_samples/produit_compatibilites.json``).

QUATRE RÈGLES GRAVÉES ICI, dans l'ordre où elles comptent :

* **La TAXONOMIE est celle du noyau, jamais une règle maison.** ``incompatible``
  = le noyau prononce un BLOQUANT (``core.electrique.chaines`` : Voc à froid
  au-dessus de la tension maximale absolue, fenêtre de tension vide, ou — depuis
  DEV-202608-0016 — **Isc cumulé au-dessus de la borne de court-circuit PUBLIÉE
  par l'entrée MPPT** : les cas où du matériel casse, où aucune chaîne n'existe,
  ou où le montage sort de la spécification constructeur). ``reserve`` = le
  noyau ne prononce que des ALERTES (production dégradée : écrêtage MPPT, MPPT
  hors plage en été, et l'ÉCRÊTAGE sur l'Imp d'entrée).

  La ligne de partage entre les deux bornes de courant est celle de la FICHE, et
  elle n'est pas cosmétique : dépasser l'**Imp** admissible fait ÉCRÊTER (ça
  s'installe, ça produit moins — alerte) ; dépasser l'**Isc** publié sort de ce
  que le constructeur garantit (incident DEV-202608-0016 : 25 × 710 Wc sur le
  Deye 5 kW mono, 18,59 A d'Isc par chaîne dans une entrée alors donnée pour
  17 A — bloquant). On ne durcit ni n'assouplit AU-DELÀ des deux chiffres de
  fiche : sans borne d'Isc publiée, rien n'est bloqué (le repli prudent reste
  une alerte). L-22A (fondateur 24/08/2026) — cet exemple est désormais
  HISTORIQUE : les deux onduleurs 5 kW du catalogue portent 22 A sur leurs deux
  bornes (« more then 20A so they accept the canadian solar pannels »), donc ce
  couple-là passe. C'est la DONNÉE qui a changé, jamais la règle ci-dessus.
* **Une variable absente rend « inconnu », JAMAIS un faux OK.** Le verdict cite
  alors le LIBELLÉ FRANÇAIS de ce qui manque, pour que le fondateur sache quoi
  saisir.
* **Les raisons sont celles du noyau, mot pour mot.** Il les rédige déjà en
  français avec les chiffres de la fiche (« Imp cumulé 17,6 A > courant d'entrée
  admissible 13,0 A ») ; les réécrire ici ferait une deuxième source de vérité —
  exactement ce que PACT10 interdit.
* **AUCUN PRIX.** Ce module ne lit ni ``prix_vente`` ni ``prix_achat`` : la
  fiche produit du stock est INFORMATIVE, un produit non tarifé s'y affiche et
  s'y juge comme les autres (le garde « prix à renseigner » est celui de la
  COMPOSITION, pas celui de la compatibilité).

Lecture cross-app par SÉLECTEUR uniquement (``apps.stock.selectors``), jamais
un import des modèles de stock.
"""
from __future__ import annotations

import math

from apps.ventes.solar_design import (
    DEFAULT_INVERTER_WINDOW,
    DEFAULT_MODULE,
    fenetre_onduleur_pour_produit,
    specs_module_pour_produit,
    string_design,
    verdicts_chaines,
)

# ── Vocabulaire des verdicts (contrat partagé avec l'écran) ──────────────────
STATUT_COMPATIBLE = 'compatible'
STATUT_RESERVE = 'reserve'
STATUT_INCOMPATIBLE = 'incompatible'
STATUT_INCONNU = 'inconnu'

#: Les statuts qui autorisent l'appariement (l'écran les rend ``ok: true``).
STATUTS_OK = (STATUT_COMPATIBLE, STATUT_RESERVE)

# ── Familles (vocabulaire de ``ventes.services.classer_produit``) ────────────
FAMILLE_PANNEAU = 'panneau'
FAMILLE_BATTERIE = 'batterie'
FAMILLE_ONDULEUR = 'onduleur'
#: ``'onduleur'`` tout court est la famille d'un onduleur DÉCLARÉ par sa fiche
#: (``type_fiche='onduleur'``) dont le NOM ne tranche pas entre réseau et
#: hybride — un micro-onduleur, une référence nue « Deye SUN-10K ».
#: ``classer_produit`` le laisse volontairement non classé (il ne doit jamais
#: être auto-composé) ; ici il DOIT quand même se juger, sans quoi sa fiche
#: produit n'afficherait aucune compatibilité.
FAMILLES_ONDULEUR = ('onduleur_reseau', 'onduleur_hybride', 'onduleur')

# ── Raccordement client (miroir de ``crm.Lead.Raccordement``) ────────────────
PHASE_MONO = 'monophase'
PHASE_TRI = 'triphase'

#: CONTRAT DE FICHE « MODULE » — ce qu'un panneau DOIT porter pour qu'un
#: verdict soit prononçable, et le libellé français affiché quand il manque.
#: Symétrique de ``stock.selectors.CONTRAT_ONDULEUR`` : mêmes intentions, même
#: usage (griser en DISANT pourquoi). Les six variables sont exactement celles
#: que le noyau consomme — ni plus (on ne réclame pas ce qui ne sert pas), ni
#: moins (sans l'une d'elles le noyau devinerait).
CONTRAT_MODULE = (
    ('pmax_wc', 'puissance crête (Wc)'),
    ('vmp_v', 'tension au point de puissance maximale Vmp (V)'),
    ('voc_v', 'tension à vide Voc (V)'),
    ('isc_a', 'courant de court-circuit Isc (A)'),
    ('imp_a', 'courant au point de puissance maximale Imp (A)'),
    ('temp_coeff_voc_pct_c', 'coefficient de température Voc (%/°C)'),
)

#: CONTRAT DE FICHE « BATTERIE » — la tension nominale est LA variable qui
#: décide de l'appairage ; la capacité sert à composer, pas à trancher.
CONTRAT_BATTERIE = (
    ('v_nominal', 'tension nominale (V)'),
    ('kwh_nominal', 'capacité nominale (kWh)'),
)

#: Les variables d'onduleur SANS lesquelles aucun verdict panneau/onduleur
#: n'est prononçable. Sous-ensemble STRICT de ``CONTRAT_ONDULEUR`` (le
#: rendement européen ou la garantie n'entrent dans aucun calcul) — les
#: libellés sont repris du contrat de stock, jamais réécrits.
CLES_ONDULEUR_POUR_VERDICT = (
    'ac_kw', 'n_mppt', 'mppt_v_min', 'mppt_v_max', 'v_max_abs',
    'i_max_mppt_a',
)

#: Bornes du balayage de configurations : on n'essaie que des champs PV dont le
#: ratio DC/AC reste plausible pour l'onduleur (en-dessous il est ridiculement
#: surdimensionné, au-dessus il écrête par construction).
RATIO_DC_AC_MIN = 0.8
RATIO_DC_AC_MAX = 1.4
#: Ratio VISÉ quand plusieurs configurations se valent (au milieu de la plage).
RATIO_DC_AC_CIBLE = 1.15
#: Garde-fou de boucle : un très gros onduleur face à de petits modules
#: donnerait des centaines de comptes ; au-delà, les verdicts ne changent plus.
MAX_CONFIGURATIONS = 60


# ═══════════════════════════════════════════════════════════════════════════
# Lecture des fiches (cross-app PAR SÉLECTEUR, jamais les modèles)
# ═══════════════════════════════════════════════════════════════════════════
def _specs(produit):
    """Specs normalisées d'un produit — ``{}`` si aucune fiche exploitable."""
    if produit is None:
        return {}
    from apps.stock.selectors import specs_for_produit
    return specs_for_produit(produit) or {}


def module_specs_manquantes(produit):
    """Libellés français des variables MODULE absentes de la fiche."""
    specs = _specs(produit)
    return [libelle for cle, libelle in CONTRAT_MODULE
            if specs.get(cle) is None]


def batterie_specs_manquantes(produit):
    """Libellés français des variables BATTERIE absentes de la fiche."""
    specs = _specs(produit)
    return [libelle for cle, libelle in CONTRAT_BATTERIE
            if specs.get(cle) is None]


def _onduleur_specs_manquantes_pour_verdict(produit):
    """Libellés des variables d'onduleur qui empêchent tout VERDICT.

    On repart de ``stock.selectors.CONTRAT_ONDULEUR`` pour le LIBELLÉ (source
    unique) mais on ne retient que les clés que le calcul consomme
    réellement : réclamer la garantie constructeur pour dire si un panneau
    s'y branche serait une exigence inventée.
    """
    from apps.stock.selectors import CONTRAT_ONDULEUR
    specs = _specs(produit)
    return [libelle for cle, libelle in CONTRAT_ONDULEUR
            if cle in CLES_ONDULEUR_POUR_VERDICT and specs.get(cle) is None]


def _verdict(statut, raisons, **extra):
    """Forme CANONIQUE d'un verdict — ``statut`` + ``raisons`` toujours là."""
    resultat = {'statut': statut, 'raisons': list(raisons or [])}
    resultat.update(extra)
    return resultat


def _inconnu(manquantes, sujet):
    """Verdict « inconnu » MOTIVÉ : on NOMME ce qu'il faut saisir."""
    return _verdict(
        STATUT_INCONNU,
        ['%s : %s — complétez la fiche pour trancher'
         % (sujet, ', '.join(manquantes))],
        nb_panneaux=None, nb_chaines=None, longueur_chaine=None, detail='')


# ═══════════════════════════════════════════════════════════════════════════
# 1. Panneau ↔ onduleur
# ═══════════════════════════════════════════════════════════════════════════
def _comptes_plausibles(pmax_wc, ac_kw):
    """Nombres de panneaux dont le ratio DC/AC reste plausible pour l'onduleur.

    Toujours au moins UN compte : si la plage est vide (module énorme devant un
    onduleur minuscule), on retient sa borne basse — mieux vaut un verdict sur
    une configuration serrée qu'aucun verdict du tout.
    """
    watts_ac = float(ac_kw) * 1000.0
    n_min = max(1, int(math.ceil(RATIO_DC_AC_MIN * watts_ac / pmax_wc)))
    n_max = int(math.floor(RATIO_DC_AC_MAX * watts_ac / pmax_wc))
    if n_max < n_min:
        n_max = n_min
    n_max = min(n_max, n_min + MAX_CONFIGURATIONS - 1)
    return list(range(n_min, n_max + 1))


def _distance_au_ratio_cible(n, pmax_wc, ac_kw):
    """Écart d'une configuration au ratio DC/AC visé (départage stable)."""
    return abs((n * pmax_wc / 1000.0) / float(ac_kw) - RATIO_DC_AC_CIBLE)


def _detail_chaines(n, mod, inv, verdicts):
    """La PHRASE française qui explique la configuration retenue.

    Tous les nombres viennent du noyau (tensions unitaires × longueur de
    chaîne, courants de la fiche) : aucune valeur n'est reconstituée ici.
    """
    from core.electrique.types import fr_a, fr_v

    design = string_design(n, module=mod, inverter=inv)
    tensions = design.get('voltages') or {}
    longueur = verdicts['longueur_chaine'] or design['panels_per_string']
    nb_chaines = verdicts['nb_chaines'] or design['strings']

    controles = design.get('checks') or {}
    clauses = []
    if tensions.get('voc_cold') is not None:
        # Les VALEURS CALCULÉES gardent leur décimale (``fr_v``) ; les bornes
        # DÉCLARÉES par la fiche s'écrivent comme elles y figurent (``_v_txt``),
        # sinon « 425 V » deviendrait « 425,0 V » — un chiffre que le fondateur
        # ne reconnaîtrait pas sur sa propre fiche constructeur.
        clauses.append(
            'Voc à froid %s %s la limite %s V'
            % (fr_v(tensions['voc_cold']),
               'sous' if controles.get('voc_cold_under_vmax', True)
               else 'AU-DESSUS de',
               _v_txt(inv['v_max'])))
        mppt_ok = (controles.get('vmp_cold_under_mppt_max', True)
                   and controles.get('vmp_hot_over_mppt_min', True))
        clauses.append(
            'plage MPPT %s-%s V %s'
            % (_v_txt(inv['v_mppt_min']), _v_txt(inv['v_mppt_max']),
               'respectée' if mppt_ok else 'NON respectée'))
    imp = float(mod.get('imp_a') or 0.0)
    i_max = float(inv.get('i_max_mppt_a') or 0.0)
    if imp > 0 and i_max > 0:
        n_mppt = max(1, int(inv.get('n_mppt') or 1))
        # Répartition la plus égale possible : l'entrée la plus chargée porte
        # ⌈nb_chaines / n_mppt⌉ chaînes (même calcul que le noyau).
        par_entree = -(-nb_chaines // n_mppt) * imp
        clauses.append(
            '%s par entrée MPPT %s %s admissibles'
            % (fr_a(par_entree),
               'sous les' if par_entree <= i_max else 'AU-DESSUS des',
               fr_a(i_max)))
    entete = '%d chaîne(s) de %d' % (nb_chaines, longueur)
    return entete + (' — ' + ', '.join(clauses) if clauses else '')


def verdict_panneau_onduleur(panneau, onduleur):
    """PVCOMPAT — ce panneau et cet onduleur vont-ils ensemble ?

    On balaie les champs PV dont le ratio DC/AC reste plausible pour l'onduleur
    et on demande au NOYAU son verdict pour chacun :

    * une configuration SANS bloquant ni alerte existe → ``compatible`` ;
    * sinon, une configuration sans BLOQUANT existe → ``reserve``, et les
      raisons sont les alertes du noyau (écrêtage, courant d'entrée dépassé…) ;
    * sinon → ``incompatible``, raisons = les bloquants du noyau ;
    * une variable de fiche manque → ``inconnu``, jamais un faux OK.

    Retourne ``{statut, raisons, nb_panneaux, nb_chaines, longueur_chaine,
    detail}``. ``statut``/``raisons`` sont le contrat ; les quatre autres clés
    servent au bilan d'installabilité (composition proposée). Ne lève jamais.
    """
    manquantes_module = module_specs_manquantes(panneau)
    if manquantes_module:
        return _inconnu(manquantes_module,
                        'fiche technique du panneau incomplète')
    manquantes_ond = _onduleur_specs_manquantes_pour_verdict(onduleur)
    if manquantes_ond:
        return _inconnu(manquantes_ond,
                        "fiche technique de l'onduleur incomplète")

    mod = {**DEFAULT_MODULE, **specs_module_pour_produit(panneau)}
    inv = {**DEFAULT_INVERTER_WINDOW, **fenetre_onduleur_pour_produit(onduleur)}
    pmax_wc = float(mod['puissance_w'])
    ac_kw = float(inv['ac_kw'])
    if pmax_wc <= 0 or ac_kw <= 0:
        return _inconnu(['puissance crête (Wc)', 'puissance AC (kW)'],
                        'puissances non exploitables')

    meilleur_reserve = None
    meilleur_bloque = None
    for n in _comptes_plausibles(pmax_wc, ac_kw):
        verdicts = verdicts_chaines(n, module=mod, inverter=inv)
        ecart = _distance_au_ratio_cible(n, pmax_wc, ac_kw)
        if verdicts['bloquants']:
            if meilleur_bloque is None or ecart < meilleur_bloque[0]:
                meilleur_bloque = (ecart, n, verdicts)
            continue
        if not verdicts['alertes']:
            return _verdict(
                STATUT_COMPATIBLE, [],
                nb_panneaux=n,
                nb_chaines=verdicts['nb_chaines'],
                longueur_chaine=verdicts['longueur_chaine'],
                detail=_detail_chaines(n, mod, inv, verdicts))
        # Départage des configurations « sous réserve » : le moins d'alertes
        # d'abord, puis la plus proche du ratio DC/AC visé.
        cle = (len(verdicts['alertes']), ecart)
        if meilleur_reserve is None or cle < meilleur_reserve[0]:
            meilleur_reserve = (cle, n, verdicts)

    if meilleur_reserve is not None:
        _, n, verdicts = meilleur_reserve
        return _verdict(
            STATUT_RESERVE, verdicts['alertes'],
            nb_panneaux=n,
            nb_chaines=verdicts['nb_chaines'],
            longueur_chaine=verdicts['longueur_chaine'],
            detail=_detail_chaines(n, mod, inv, verdicts))

    if meilleur_bloque is not None:
        _, n, verdicts = meilleur_bloque
        return _verdict(
            STATUT_INCOMPATIBLE, verdicts['bloquants'],
            nb_panneaux=None, nb_chaines=None, longueur_chaine=None, detail='')

    # Aucune configuration testée (ne peut arriver que sur des puissances
    # aberrantes) — on ne prétend pas savoir.
    return _inconnu(['puissance crête (Wc)', 'puissance AC (kW)'],
                    'aucune configuration plausible à évaluer')


# ═══════════════════════════════════════════════════════════════════════════
# 2. Batterie ↔ onduleur
# ═══════════════════════════════════════════════════════════════════════════
def verdict_batterie_onduleur(batterie, onduleur):
    """PVCOMPAT — cette batterie s'accroche-t-elle à cet onduleur ?

    UNE SEULE RÈGLE ÉLECTRIQUE dans tout le dépôt : celle de
    ``ventes.services._batterie_compatible`` (« la tension nominale tombe dans
    la plage batterie déclarée par l'onduleur »). Cette fonction la DÉLÈGUE, ne
    la recopie pas — c'est ce qui garantit que l'écran et la composition ne
    peuvent pas diverger.

    LA SEULE DIFFÉRENCE, VOULUE : là où la composition doit produire QUELQUE
    CHOSE et retombe donc sur le repli par mot-clé quand l'onduleur ne déclare
    aucune plage, l'écran n'a rien à produire — il dit ``inconnu`` et NOMME la
    variable à saisir. Un écran qui affirme « compatible » sur la foi d'un mot
    dans un nom serait précisément le faux OK que ce lot interdit.

    Retourne ``{statut, raisons}``. Ne lève jamais.
    """
    from apps.ventes.services import _plage_batterie_de_l_onduleur
    from core.electrique.types import fr_v

    plage = _plage_batterie_de_l_onduleur(onduleur)
    if plage is None:
        return _verdict(
            STATUT_INCONNU,
            ["plage de tension batterie (V) non déclarée par l'onduleur — "
             'complétez sa fiche pour trancher'])
    v_min, v_max = plage
    if v_max <= 0:
        return _verdict(
            STATUT_INCOMPATIBLE,
            ['cet onduleur ne prend aucune batterie (plage batterie déclarée '
             '« aucune »)'])

    from apps.ventes.services import (
        _batterie_compatible, _tension_nominale_batterie)

    # Le LIBELLÉ vient du contrat de fiche batterie (source unique), jamais
    # d'une phrase retapée. 0 est traité comme une absence : une batterie de
    # 0 V n'existe pas, c'est une saisie à reprendre.
    libelle_tension = dict(CONTRAT_BATTERIE)['v_nominal']
    tension = _tension_nominale_batterie(batterie)
    if tension is None or tension <= 0:
        return _verdict(
            STATUT_INCONNU,
            ['tension nominale inconnue (fiche technique sans « %s ») — '
             'complétez la fiche pour trancher' % libelle_tension])
    if _batterie_compatible(batterie, plage):
        return _verdict(
            STATUT_COMPATIBLE, [],
            detail='%s nominale dans la plage batterie %s-%s V de l\'onduleur'
                   % (fr_v(tension), _v_txt(v_min), _v_txt(v_max)))
    return _verdict(
        STATUT_INCOMPATIBLE,
        ['tension nominale %s hors de la plage batterie %s-%s V de l\'onduleur'
         % (fr_v(tension), _v_txt(v_min), _v_txt(v_max))])


def _v_txt(volts):
    """« 160.0 » → « 160 » — même écriture que ``services._v_txt``."""
    try:
        f = float(volts)
    except (TypeError, ValueError):
        return str(volts)
    return str(int(f)) if f == int(f) else ('%g' % f)


# ═══════════════════════════════════════════════════════════════════════════
# 3. La synthèse d'UN produit face à tout le stock (contrat PACT10)
# ═══════════════════════════════════════════════════════════════════════════
def _famille(produit):
    """Famille catalogue — RÉUTILISE le classifieur existant, jamais un
    nouveau jeu de mots-clés (deux classifieurs = deux vérités).

    REPLI sur le ``type_fiche`` DÉCLARÉ quand le nom ne tranche pas : un
    produit dont la fiche dit « onduleur » EST un onduleur, même si son nom ne
    dit ni « réseau » ni « hybride ». Une déclaration explicite pèse plus lourd
    qu'un mot-clé, et cet écran doit juger tout ce que le stock contient — il
    ne compose rien, donc rien ne l'oblige à la prudence de l'auto-composition.
    """
    from apps.ventes.services import classer_produit
    famille = classer_produit(getattr(produit, 'nom', ''))
    if famille:
        return famille
    type_fiche = getattr(
        getattr(produit, 'fiche_technique', None), 'type_fiche', '') or ''
    return {'module': FAMILLE_PANNEAU, 'batterie': FAMILLE_BATTERIE,
            'onduleur': FAMILLE_ONDULEUR}.get(type_fiche)


def _entree_produit(produit, verdict):
    """Une ligne ``{id, nom, ok, raison}`` du contrat.

    ``reserve`` compte comme OK — le produit s'installe — mais sa raison est
    REPRISE : un appairage qui écrête n'est pas un appairage muet.
    """
    statut = verdict['statut']
    raisons = verdict.get('raisons') or []
    return {
        'id': getattr(produit, 'id', None),
        'nom': getattr(produit, 'nom', '') or '',
        'ok': statut in STATUTS_OK,
        'raison': ' ; '.join(raisons),
    }


def _fiche_incomplete(produit, famille):
    """Les variables de contrat qui manquent à CE produit (libellés français)."""
    if famille in FAMILLES_ONDULEUR:
        from apps.stock.selectors import onduleur_specs_manquantes
        return list(onduleur_specs_manquantes(produit))
    if famille == FAMILLE_PANNEAU:
        return module_specs_manquantes(produit)
    if famille == FAMILLE_BATTERIE:
        return batterie_specs_manquantes(produit)
    return []


def _bilan_onduleur(onduleur, panneaux, batteries, verdicts_panneaux,
                    verdicts_batteries):
    """Le BILAN d'installabilité d'un onduleur : la composition qu'il rejoindrait.

    On retient le premier panneau ``compatible`` du stock ; à défaut le premier
    ``reserve`` (il s'installe, avec sa réserve DITE dans le détail). Aucun
    panneau retenu ⇒ « non installable », et le motif NOMME la contrainte au
    lieu de dire « rien ne va ».
    """
    composition = []
    problemes = []

    retenu = None
    for produit in panneaux:
        verdict = verdicts_panneaux[id(produit)]
        if verdict['statut'] == STATUT_COMPATIBLE:
            retenu = (produit, verdict)
            break
        if retenu is None and verdict['statut'] == STATUT_RESERVE:
            retenu = (produit, verdict)

    if retenu is not None:
        produit, verdict = retenu
        detail = verdict.get('detail') or ''
        if verdict['statut'] == STATUT_RESERVE and verdict.get('raisons'):
            detail = (detail + ' — sous réserve : '
                      + ' ; '.join(verdict['raisons'])).strip(' —')
        composition.append({
            'role': FAMILLE_PANNEAU,
            'produit_id': getattr(produit, 'id', None),
            'nom': getattr(produit, 'nom', '') or '',
            'quantite': verdict.get('nb_panneaux') or 0,
            'detail': detail,
        })
    else:
        motifs = []
        for produit in panneaux:
            for raison in verdicts_panneaux[id(produit)].get('raisons') or []:
                if raison not in motifs:
                    motifs.append(raison)
        problemes.append(
            'aucun panneau du stock ne convient'
            + (' : ' + ' ; '.join(motifs[:3]) if motifs
               else " : aucun panneau au catalogue de cette société"))

    # ── Batterie : seulement si l'onduleur en accepte une ──
    from apps.ventes.services import _plage_batterie_de_l_onduleur
    plage = _plage_batterie_de_l_onduleur(onduleur)
    if plage is not None and plage[1] > 0:
        retenue = next(
            (p for p in batteries
             if verdicts_batteries[id(p)]['statut'] == STATUT_COMPATIBLE),
            None)
        if retenue is not None:
            composition.append({
                'role': FAMILLE_BATTERIE,
                'produit_id': getattr(retenue, 'id', None),
                'nom': getattr(retenue, 'nom', '') or '',
                'quantite': 1,
                'detail': verdicts_batteries[id(retenue)].get('detail') or '',
            })
        else:
            problemes.append(
                'aucune batterie du stock ne convient à la plage batterie '
                '%s-%s V de cet onduleur'
                % (_v_txt(plage[0]), _v_txt(plage[1])))

    installable = retenu is not None
    return installable, {
        'verdict': 'installable' if installable else 'non installable',
        'composition': composition,
        'problemes': problemes,
    }


def compatibilites_du_produit(produit, company):
    """PVCOMPAT — la fiche « Compatibilités » d'un produit, forme CONTRACTUELLE.

    Forme rendue (contrat committé
    ``apps/stock/contract_samples/produit_compatibilites.json``) ::

        {produit: {id, nom, famille},
         fiche_incomplete: [libellés français],
         installable: bool,
         bilan: null | {verdict, composition: [...], problemes: [...]},
         familles: [{famille, produits: [{id, nom, ok, raison}]}]}

    Le VIVIER est le catalogue visible par la société (le sien + les produits
    globaux), non archivé — Y COMPRIS les produits sans prix : cet écran est
    INFORMATIF, et un produit « prix à renseigner » a une fiche technique et une
    compatibilité comme les autres. Le garde de prix reste celui de la
    composition, il n'a rien à faire ici.

    ``bilan`` n'est rendu QUE pour un onduleur (c'est lui qui porte la
    contrainte électrique de tout le reste) ; il vaut ``null`` ailleurs, jamais
    une clé absente. Lecture seule, aucune écriture, aucun prix. Ne lève jamais
    sur des fiches incomplètes.
    """
    from apps.ventes.services import catalogue_de_la_societe

    famille = _famille(produit)
    catalogue = [p for p in catalogue_de_la_societe(company)
                 if getattr(p, 'id', None) != getattr(produit, 'id', None)]
    panneaux = [p for p in catalogue if _famille(p) == FAMILLE_PANNEAU]
    batteries = [p for p in catalogue if _famille(p) == FAMILLE_BATTERIE]
    onduleurs = [p for p in catalogue if _famille(p) in FAMILLES_ONDULEUR]

    familles = []
    bilan = None
    installable = False

    if famille in FAMILLES_ONDULEUR:
        verdicts_panneaux = {id(p): verdict_panneau_onduleur(p, produit)
                             for p in panneaux}
        verdicts_batteries = {id(p): verdict_batterie_onduleur(p, produit)
                              for p in batteries}
        familles = [
            {'famille': FAMILLE_PANNEAU,
             'produits': [_entree_produit(p, verdicts_panneaux[id(p)])
                          for p in panneaux]},
            {'famille': FAMILLE_BATTERIE,
             'produits': [_entree_produit(p, verdicts_batteries[id(p)])
                          for p in batteries]},
        ]
        installable, bilan = _bilan_onduleur(
            produit, panneaux, batteries, verdicts_panneaux,
            verdicts_batteries)
    elif famille == FAMILLE_PANNEAU:
        entrees = [_entree_produit(o, verdict_panneau_onduleur(produit, o))
                   for o in onduleurs]
        familles = [{'famille': FAMILLE_ONDULEUR, 'produits': entrees}]
        installable = any(e['ok'] for e in entrees)
    elif famille == FAMILLE_BATTERIE:
        entrees = [_entree_produit(o, verdict_batterie_onduleur(produit, o))
                   for o in onduleurs]
        familles = [{'famille': FAMILLE_ONDULEUR, 'produits': entrees}]
        installable = any(e['ok'] for e in entrees)

    return {
        'produit': {
            'id': getattr(produit, 'id', None),
            'nom': getattr(produit, 'nom', '') or '',
            'famille': famille,
        },
        'fiche_incomplete': _fiche_incomplete(produit, famille),
        'installable': bool(installable),
        'bilan': bilan,
        'familles': familles,
    }


# ═══════════════════════════════════════════════════════════════════════════
# 4. Ce que la COMPOSITION doit savoir dire
# ═══════════════════════════════════════════════════════════════════════════
def normaliser_phase(valeur):
    """``'monophase'`` / ``'triphase'`` / ``None`` depuis un raccordement lead.

    Tolère les deux écritures qui circulent (``mono``/``monophase``,
    ``tri``/``triphase``) ; « inconnu », vide ou toute autre valeur rend
    ``None`` — c'est-à-dire « le client n'a rien déclaré », et la composition
    garde alors son comportement d'avant, à l'octet près.
    """
    texte = str(valeur or '').strip().lower()
    if texte.startswith('mono'):
        return PHASE_MONO
    if texte.startswith('tri'):
        return PHASE_TRI
    return None


def est_triphase_produit(produit):
    """L'onduleur est-il TRIPHASÉ ? Sa fiche d'abord, son nom à défaut.

    La fiche (``ond_phases``, PV5) est une donnée MESURÉE ; le nom n'est qu'un
    indice — mais c'est celui que ``services._est_triphase`` utilise déjà, donc
    le repli reste exactement l'existant.
    """
    phases = _specs(produit).get('phases')
    if phases is not None:
        try:
            return int(phases) == 3
        except (TypeError, ValueError):
            pass
    from apps.ventes.services import _est_triphase
    return _est_triphase(getattr(produit, 'nom', ''))


def avertissement_raccordement(phase):
    """Le message FRANÇAIS quand le raccordement déclaré n'a pas pu être tenu.

    Une seule formulation, partagée par tous les chemins de composition : le
    commercial doit lire la MÊME phrase quel que soit le bouton utilisé (même
    principe que ``services.avertissement_vivier_batterie_vide``).
    """
    if phase == PHASE_MONO:
        return ('Réseau monophasé déclaré — aucun onduleur monophasé à cette '
                'puissance au catalogue, composition en triphasé À VALIDER '
                'avec le client.')
    return ('Réseau triphasé déclaré — aucun onduleur triphasé à cette '
            'puissance au catalogue, composition en monophasé À VALIDER '
            'avec le client.')


def avertissement_panneau_onduleur(panneau, onduleur, verdict):
    """Le message FRANÇAIS d'un couple panneau/onduleur qui coince.

    Il NOMME les deux produits et reprend TEL QUEL le motif du noyau : c'est
    la phrase que le fondateur voulait lire (« pas de PV parce que le courant
    maxi par MPPT de cet onduleur est sous le courant de nos panneaux »).
    """
    entete = ('Couple %s / %s %s'
              % (getattr(panneau, 'nom', '') or 'panneau',
                 getattr(onduleur, 'nom', '') or 'onduleur',
                 'INCOMPATIBLE' if verdict['statut'] == STATUT_INCOMPATIBLE
                 else 'à vérifier'))
    raisons = ' ; '.join(verdict.get('raisons') or [])
    return ('%s : %s.' % (entete, raisons)) if raisons else ('%s.' % entete)
