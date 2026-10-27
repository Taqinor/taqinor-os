"""SPL163 — phase D1 de ``build_quote_data`` : chiffrage de l'étude (move only).

Déplacés tels quels de ``builder.py`` : le corps de ``build_quote_data`` du
marqueur « Canonical performance figures » à la fin du bloc « QXMT », devenu
``chiffrer_etude`` (avec ses fonctions imbriquées ``_etude_horaire_pour`` /
``_roi_pour`` et l'import local de ``calculate_savings_roi``), et les helpers de
niveau module qu'il est seul à lire : étude rendue / fraîche, blocs horaires,
ville du devis, ``_nombre`` (que ``builder`` ré-importe pour son propre usage).

``chiffrer_etude`` reçoit ses entrées en arguments NOMMÉS et rend ses sorties
dans l'ordre que ``build_quote_data`` dépaquette dans les MÊMES noms locaux ;
les dicts et listes reçus (items, ``avertissements_internes``) sont mutés en
place — ce sont les mêmes objets. Rendu pur (règle #4) : aucun statut touché.

Ce module n'importe JAMAIS ``builder`` (cycle) : les helpers de classement
viennent de ``lignes_classement``.
"""
from __future__ import annotations

import logging

from .lignes_classement import _battery_kwh_from_items, _cout_onduleur

logger = logging.getLogger(__name__)


#: QJR625 — pour un devis I/C dont l'étude porte sa base ``etude['kwc']``, la
#: base elle-même et les chiffres saisis à partir d'elle. CIQ129 : les
#: dérivées écran v1 (et leur base ``etude_kwc_base``) ont quitté le schéma ;
#: elles sont retirées de l'étude rendue dès l'entrée (``_etude_rendue``).
_DERIVEES_ETUDE_IC_ANCIENNES = ("kwc", "production_annuelle",
                                "economies_annuelles")


def _etude_rendue(etude_params):
    """CIQ129 (D-CIQ-21) — l'étude RENDUE : une COPIE du bloc stocké, sans les
    clés retirées du schéma (``etude_schema.CLES_RETIREES_CI_V1``). Un ancien
    devis qui les porte encore ne les fait plus lire par aucun gabarit ; le
    bloc stocké n'est jamais muté (règle #4)."""
    from ..domain.etude_schema import CLES_RETIREES_CI_V1

    return {cle: valeur for cle, valeur in dict(etude_params or {}).items()
            if cle not in CLES_RETIREES_CI_V1}


def _etude_ic_fraiche(etude, puissance_kwc):
    """QJR625 — ``(etude, perimee)`` : l'étude I/C sans ses chiffres saisis
    quand ils l'ont été pour un autre kWc que celui des lignes.

    Base = ``etude['kwc']``. Écart relatif > ``pricing._HORAIRE_TOLERANCE_KWC``
    ⇒ chiffres retirés d'une COPIE (l'``etude_params`` stocké n'est jamais
    muté). Sans base ou sans puissance des lignes : étude rendue telle quelle.
    """
    from .pricing import _HORAIRE_TOLERANCE_KWC

    base = _nombre(etude.get("kwc"))
    lignes_kwc = _nombre(puissance_kwc)
    if not base or not lignes_kwc:
        return etude, False
    if abs(base - lignes_kwc) / lignes_kwc <= _HORAIRE_TOLERANCE_KWC:
        return etude, False
    sortie = dict(etude)
    for cle in _DERIVEES_ETUDE_IC_ANCIENNES:
        sortie.pop(cle, None)
    return sortie, True


def _etude_horaire_sans_stockage(bloc):
    """BAT-DIFF — copie du bloc horaire où l'option « avec » porte les chiffres
    de « sans » : sans batterie, les deux options autoconsomment pareil.

    Le bloc ``etude_params['etude_horaire']`` peut avoir été calculé AVANT que
    le vendeur ne retire la batterie (édition complète) : ses économies
    « avec » décriraient alors un stockage que le devis ne porte plus. Un bloc
    déjà recalculé sans batterie est un NO-OP exact (avec == sans déjà).
    Fonction pure, ne lève jamais : un bloc illisible est rendu tel quel
    (``pricing._lire_etude_horaire`` le refusera de toute façon).
    """
    if not isinstance(bloc, dict):
        return bloc
    copie = dict(bloc)
    annuel = bloc.get("annuel")
    if isinstance(annuel, dict):
        a = dict(annuel)
        for cle_avec, cle_sans in (
                ("economie_avec_mad", "economie_sans_mad"),
                ("taux_autoconso_avec", "taux_autoconso_sans"),
                ("facture_apres_avec_mad", "facture_apres_sans_mad"),
                ("autoconsomme_avec_kwh", "autoconsomme_sans_kwh"),
                ("couverture_avec", "couverture_sans")):
            if cle_sans in a:
                a[cle_avec] = a[cle_sans]
        copie["annuel"] = a
    mois = bloc.get("mois")
    if isinstance(mois, list):
        copie["mois"] = [
            ({**m, "economie_avec_mad": m.get("economie_sans_mad")}
             if isinstance(m, dict) and "economie_sans_mad" in m else m)
            for m in mois]
    return copie


#: I7 (30/09/2026) — les clés d'``etude_params`` qui portent un bloc horaire,
#: le PRINCIPAL d'abord. ``etude_horaire_sans`` n'existe que sur un devis dont
#: les deux options portent des champs PV différents (L-2OPT) ; le principal
#: décrit alors l'option AVEC (``domain.etudes.puissances_etude_horaire``).
CLES_BLOCS_HORAIRES = ("etude_horaire", "etude_horaire_sans")


def bloc_horaire_pour_kwc(etude, kwc):
    """I7 — le bloc horaire RANGÉ qui décrit CETTE puissance.

    Un bloc porte UNE puissance ; un devis à champs PV divergents en range
    donc un par option. On rend celui dont le kWc est le plus proche de
    ``kwc`` DANS la tolérance du moteur (``pricing._HORAIRE_TOLERANCE_KWC`` —
    la même garde que celle qui refuserait le bloc ensuite, jamais un second
    seuil). Aucun bloc ne correspond ⇒ le bloc PRINCIPAL, que
    ``pricing._lire_etude_horaire`` refusera alors comme avant I7 : ce
    sélecteur ne rend jamais valide un bloc périmé, il évite seulement de
    présenter le mauvais. Fonction pure, ne lève jamais.
    """
    from .pricing import _HORAIRE_TOLERANCE_KWC
    etude = etude or {}
    principal = etude.get(CLES_BLOCS_HORAIRES[0])
    try:
        cible = float(kwc or 0)
    except (TypeError, ValueError):
        return principal
    if cible <= 0:
        return principal
    meilleur, ecart_min = None, None
    for cle in CLES_BLOCS_HORAIRES:
        bloc = etude.get(cle)
        if not isinstance(bloc, dict):
            continue
        try:
            kwc_bloc = float(bloc.get("kwc") or 0)
        except (TypeError, ValueError):
            continue
        ecart = abs(kwc_bloc - cible) / cible
        if (kwc_bloc > 0 and ecart <= _HORAIRE_TOLERANCE_KWC
                and (ecart_min is None or ecart < ecart_min)):
            meilleur, ecart_min = bloc, ecart
    return meilleur if meilleur is not None else principal


def _libelle_ville(ville, reference):
    """QJR591 — « {ville}, près de {reference} » quand elles diffèrent."""
    ville = (ville or '').strip()
    reference = (reference or '').strip()
    if ville and reference and ville.lower() != reference.lower():
        return f"{ville}, près de {reference}"
    return reference or ville


def _ville_du_devis(devis, etude):
    """QJR591 — ``(ville de calcul, libellé méta)`` du devis.

    Lit d'abord ``etude_params['ville_calcul']`` (figée au chiffrage par
    ``pipeline.rafraichir_etudes``) ; ne retombe sur le lead
    (``crm.selectors.ville_effective``, QJR586) que pour un devis qui ne la
    porte pas encore. Ne lève jamais : un PDF ne casse pas là-dessus.
    """
    figee = (etude or {}).get("ville_calcul") if isinstance(etude, dict) else None
    if isinstance(figee, dict):
        reference = (figee.get("reference") or "").strip()
        return reference, _libelle_ville(figee.get("ville"), reference)
    try:
        _lead = getattr(devis, "lead", None)
        if _lead is None:
            return "", ""
        # VREF (fondateur 07/09/2026) — la ville ERP de RATTACHEMENT d'un
        # douar hors gazetier pilote le productible PVGIS (QJR586 : un point).
        from apps.crm.selectors import ville_effective
        reference = ville_effective(_lead)
        return reference, _libelle_ville(getattr(_lead, "ville", ""), reference)
    except Exception:  # noqa: BLE001 — un PDF ne casse jamais là-dessus (D-ENF22-BLE001)
        logger.warning("builder._ville_du_devis : erreur ignorée (mode dégradé)", exc_info=True)
        return "", ""


def _nombre(valeur) -> float:
    """``float`` tolérant : ``0.0`` sur None / vide / non numérique.

    PVUNI — les figures du calepinage arrivent d'un JSON client (roofPro) : une
    valeur absente ou mal typée ne doit jamais lever, elle vaut « pas de figure ».
    """
    try:
        return float(valeur)
    except (TypeError, ValueError):
        return 0.0


def _cout_onduleur_paye(devis, items, blob):
    """RPDF12 — provision de remplacement = le prix que le client PAIE pour
    l'onduleur : la remise globale du devis s'applique aussi à cette ligne
    (devis 1344 : 36 000 imprimés, 34 200 payés). Niveau de règles 3
    seulement : un devis déjà envoyé garde la provision qu'il a imprimée."""
    cout = _cout_onduleur(items, blob)
    remise = _nombre(getattr(devis, "remise_globale", None))
    if cout and remise > 0 and _regles_2710(devis):
        return round(cout * (1 - remise / 100), 2)
    return cout


def _regles_2710(devis):
    """RHOR6 — vrai si ce devis est rendu au niveau de règles 3."""
    from apps.ventes.domain.regles_calcul import (
        REGLES_CORRIGEES_2710, regles_au_moins)
    return regles_au_moins(devis, REGLES_CORRIGEES_2710)


def chiffrer_etude(*, _blob, _corrige, _mode_ci, avec_batterie_differee,
                   avec_items, avec_ok, avertissements_internes, deux_options,
                   devis, devis_etude_override, has_batterie, mode,
                   option_servie, opts, panneaux_divergents, puissance_kwc,
                   puissance_kwc_avec, puissance_kwc_sans, sans_items,
                   total_avec, total_sans):
    from .pricing import calculate_savings_roi

    # ── Canonical performance figures: ONE source of truth ───────────────────
    # When the quote carries a stored étude (industrial), its consumption-driven
    # production/savings are canonical; payback and prix/kWc are recomputed from
    # the canonical totals so edited lines can never desynchronize the document.
    # CIQ129 — sans les clés retirées du schéma (jamais relues, D-CIQ-21).
    etude = _etude_rendue(devis_etude_override)
    if _mode_ci:
        # CIQ210 — la toiture ne fournit au C&I que géométrie et production :
        # une économie écrite par un calepinage synchronisé (ou une étude
        # d'écran) n'apparaît NULLE PART dans le document ; l'argent C&I vient
        # du seul bloc ``economie_ci``.
        etude.pop("economies_annuelles", None)
    # ── QJR625 — UNE ÉTUDE I/C CALCULÉE POUR UN AUTRE KWC N'EST PAS IMPRIMÉE ─
    # Les chiffres saisis d'une étude I/C décrivent le kWc de sa base
    # (``etude['kwc']`` ; CIQ129 : les dérivées écran v1 et ``etude_kwc_base``
    # ne sont plus rendues — le moteur C&I recalcule ``etude_ci``).
    # Une ligne corrigée depuis (D-QJR5-1 : republication sur le même lien)
    # les rend fausses : au-delà de la tolérance du moteur horaire, ils sont
    # OMISES (jamais recalculées ici — zéro chiffre inventé) et l'équipe en est
    # avertie. Sans base connue : comportement inchangé. Rendu seul (règle #4).
    if (mode or "").strip().lower() in ("industriel", "commercial"):
        etude, _etude_perimee = _etude_ic_fraiche(etude, puissance_kwc)
        if _etude_perimee:
            avertissements_internes.append(
                "étude industrielle périmée — relancer l'étude")
    # AGR303 — plus de surcharge de l'énergie actuelle par une option de
    # rendu : l'étude rendue est l'étude STOCKÉE (énergie déclarée et datée,
    # D-AGR-5 ; le bloc AGR3 porte la dépense déclarée).
    # QJ13 — tarif : le barème de la SOCIÉTÉ (ci-dessous), sinon la grille
    # nationale du distributeur. AMOT47 (C-AMOT-008) — les lectures
    # ``etude.tarif_kwh`` / ``etude.tarif_tranches`` sont SUPPRIMÉES : aucune
    # clé du schéma ``etude_params`` ne les écrit (aucun écran, aucune API),
    # le commentaire qui les disait « éditables par le vendeur » mentait.
    _tranches_override = None
    _utility = etude.get("distributeur")  # "onee" | "lydec" | "redal"
    # ORDRE FONDATEUR (19/08/2026) — barème ONEE résidentiel RÉGLABLE par
    # société (« correct all prices and keep them changable in the settings »).
    # Si le fondateur a ÉDITÉ le
    # barème de sa société (Paramètres → Tarification & ROI, apps/parametres
    # TariffSettings), on l'utilise ; sinon aucun changement — pricing.py garde
    # ses défauts 2026 codés en dur. N'agit que sur ONEE (le réglage ne couvre
    # que le barème résidentiel national, jamais Lydec/Redal estimés).
    #
    # QJR409 — LES DEUX RÉGLAGES TARIFAIRES DE LA SOCIÉTÉ VIENNENT DU LECTEUR
    # EXISTANT (``etude_horaire._reglages_tarifaires``), plus d'une seconde
    # lecture recopiée ici. Il rend le COUPLE ``(tranches, charges_fixes)`` :
    # la moitié « tranches » remplace mot pour mot le bloc qui vivait ici (même
    # sélecteur, même reconstruction en ``TrancheTable``), et la moitié
    # « charges fixes » — le réglage ``redevance_compteur_mad_mois`` — n'avait
    # AUCUN chemin jusqu'au modèle « factures », alors que le modèle « horaire »
    # l'honore depuis toujours : le même client voyait DEUX « Facture actuelle »
    # différentes selon le modèle qui gagne. Ne lève jamais.
    _co_charges_fixes = None
    try:
        from apps.ventes.etude_horaire import _reglages_tarifaires
        _co_tranches, _co_charges_fixes = _reglages_tarifaires(
            getattr(devis, "company", None))
    except Exception:  # noqa: BLE001 — un PDF/une liste ne casse jamais ici (D-ENF22-BLE001)
        logger.warning("builder.build_quote_data : erreur ignorée (mode dégradé)", exc_info=True)
        _co_tranches = None
    # COUV-HOR/CAD167 — Q7 : TOUT distributeur (ONEE, Lydec, Redal, SRM,
    # « autre ») lit LA grille nationale, éditable par société. Réservée à
    # vide/'onee', la grille société était contournée dès qu'un SRM tarifait
    # (grille codée en dur, 1,6229 au lieu du 1,5958 de la société).
    if _co_tranches and not _tranches_override:
        _tranches_override = _co_tranches
    _conso_annuelle = etude.get("conso_annuelle")  # from industrial étude if available
    # Autoconsommation overrides (seller/study can refine these)
    _autoconso_sans = float(etude.get("autoconso_sans") or 0) or None
    _autoconso_avec = float(etude.get("autoconso_avec") or 0) or None
    from .pricing import AUTOCONSO_SANS, AUTOCONSO_AVEC
    # DC2 — repères ROI de la société (source unique CompanyProfile via le
    # sélecteur parametres) : productible annuel et tarif ONEE de repli. Le
    # productible pilote la production annuelle et donc le ROI, même à l'écran ;
    # le tarif ONEE ne s'applique qu'en dernier repli (aucune donnée de conso),
    # de sorte que le simulateur et le PDF ne divergent plus.
    # QX7c/QX38 — ville du client depuis le lead lié (lead.ville). Accès attribut
    # sur l'instance liée (aucun import crm.models) ; vide si pas de lead/ville.
    # Sert au productible PVGIS par ville (QX38) ET à la ligne meta du PDF (QX7c).
    # QJR591 — la ville FIGÉE au chiffrage (``etude_params['ville_calcul']``,
    # consignée par ``pipeline.rafraichir_etudes``) : corriger la ville du
    # lead ne change plus la production d'un devis déjà chiffré. Repli sur
    # ``ville_effective`` (QJR586) pour un devis qui ne la porte pas encore.
    _client_city, _client_city_libelle = _ville_du_devis(devis, etude)

    _tariff = {}
    try:
        from apps.parametres.selectors import tariff_for
        _tariff = tariff_for(getattr(devis, "company", None))
    except Exception:  # noqa: BLE001 — un PDF/une liste ne casse jamais ici (D-ENF22-BLE001)
        # QJR158 (d) — CET ÉCHEC PARLE. Muet, il faisait retomber le document
        # sur le productible de repli SANS que rien, nulle part, n'indique que
        # le repère de la société n'avait pas pu être lu : une production
        # publiée 25 % trop basse (« ≈ N kWh par kWc et par an ») était
        # indistinguable d'un calcul normal. Le PDF ne casse toujours pas.
        logger.warning(
            "barème société illisible (devis %s) — repli productible",
            getattr(devis, "reference", None), exc_info=True)
        _tariff = {}
    # ── QX38 — productible CANONIQUE (source unique PVGIS par ville) ──────────
    # CompanyProfile.productible_kwh_kwc devient un OVERRIDE éditable, pas un
    # modèle physique concurrent : vide (NULL), on lit le productible PVGIS de
    # la ville du lead/devis (aligné écran/PDF/web) ; renseigné (1 600 compris
    # — AMOT64), il prime. Repli sûr : sur toute
    # erreur, on garde l'ancien productible du tarif (comportement inchangé).
    _co_productible = _tariff.get("productible_kwh_kwc") or None
    try:
        from .productible import productible_for_city
        _productible = productible_for_city(
            _client_city, override=_co_productible)
    except Exception:  # noqa: BLE001 — un PDF ne casse jamais là-dessus (D-ENF22-BLE001)
        # QJR158 (d) — MÊME RAISON : sans société pour le surcharger,
        # ``_co_productible`` vaut ``None`` et c'est le repli de ``pricing``
        # qui sert. Il vaut désormais le repli CANONIQUE du dépôt (1651), et
        # cette ligne dit qu'on y est arrivé par une erreur.
        logger.warning(
            "productible par ville illisible (devis %s, ville %r) — repli",
            getattr(devis, "reference", None), _client_city, exc_info=True)
        _productible = _co_productible
    _onee_tarif = _tariff.get("onee_tarif_kwh") or None

    def _etude_horaire_pour(kwc):
        """I7 — le bloc horaire rangé pour ``kwc``, ramené « sans stockage »
        sur une option « avec » servie sans batterie (BAT-DIFF)."""
        bloc = bloc_horaire_pour_kwc(etude, kwc)
        return (_etude_horaire_sans_stockage(bloc) if avec_batterie_differee
                else bloc)

    roi_kwargs = dict(
        conso_annuelle_kwh=float(_conso_annuelle) if _conso_annuelle else None,
        utility=_utility or None,
        tranches_override=_tranches_override or None,
        # QJR409 — la redevance de compteur RÉGLÉE par la société atteint enfin
        # le modèle « factures » : sans elle, sa « Facture actuelle » comptait
        # les lignes fixes SOURCÉES par défaut pendant que le modèle horaire
        # comptait celles de la société. ``None`` ⇒ défauts du barème, sortie
        # byte-identique à avant.
        charges_fixes_mad=_co_charges_fixes,
        autoconso_sans=_autoconso_sans if _autoconso_sans else AUTOCONSO_SANS,
        # BAT-DIFF — option « avec » SANS stockage : même taux que « sans »
        # (rien n'est décalé). Le forfait 0,85 « faute de capacité » et le
        # taux forcé par le vendeur (saisi en pensant à une batterie) sont
        # tous deux écartés — c'est exactement le chiffre inventé que Z1
        # interdit. Sinon : comportement byte-identique à avant.
        autoconso_avec=(
            (_autoconso_sans if _autoconso_sans else AUTOCONSO_SANS)
            if avec_batterie_differee
            else (_autoconso_avec if _autoconso_avec else AUTOCONSO_AVEC)),
        # ORDRE FONDATEUR (18/08) — capacité batterie RÉELLE de l'option 2 :
        # le taux d'autoconsommation « avec batterie » en est dérivé
        # (60 % + capacité × 1 cycle/jour) au lieu d'un forfait 85 %. Un taux
        # explicitement forcé par le vendeur (etude_params.autoconso_avec)
        # reste souverain : on ne dérive alors rien.
        battery_kwh=(None if (_autoconso_avec or avec_batterie_differee)
                     else (_battery_kwh_from_items(avec_items, _blob) or None)),
        productible=_productible,
        fallback_tarif_kwh=_onee_tarif,
        # M9 — l'abattement de rendement batterie ne s'applique qu'à une option
        # qui porte VRAIMENT du stockage (il l'était inconditionnellement).
        stockage_present=has_batterie,
        # Q1 — provision de remplacement onduleur = prix TTC RÉEL de la ligne
        # onduleur de chaque option ; aucune ligne ⇒ aucune provision.
        inverter_cost_sans=_cout_onduleur_paye(devis, sans_items, _blob),
        inverter_cost_avec=_cout_onduleur_paye(devis, avec_items, _blob),
        # CJ2a (ORDRE FONDATEUR) — le bloc du moteur HORAIRE, quand le devis en
        # porte un : les économies deviennent l'intégration réelle production ×
        # consommation, mois par mois, au lieu du forfait 60 %. Absent ⇒
        # ``calculate_savings_roi`` garde EXACTEMENT son comportement d'avant.
        # BAT-DIFF — un bloc calculé AVANT le retrait de la batterie porterait
        # encore ses économies « avec » : on les ramène à « sans ».
        # I7 — le bloc de LA puissance chiffrée (un par option sur un devis
        # divergent) ; ``_roi_pour`` plus bas choisit celui de chaque colonne.
        etude_horaire=_etude_horaire_pour(puissance_kwc),
        # Décision fondateur 08/10/2026 — AMOT58 (rendement batterie déduit
        # une fois) et AMOT27 (forme mensuelle GHI) pour les seuls nouveaux
        # rendus ; règles d'origine : le calcul d'hier.
        rendement_une_fois=_corrige,
        forme_mensuelle_ghi=_corrige,
        regles_2710=_regles_2710(devis),
    )
    # M2 — puissance inconnue ⇒ production et économies le sont aussi (elles en
    # dérivent toutes). ``calculate_savings_roi`` rend alors des zéros ; le
    # drapeau ``puissance_inconnue`` fait OMETTRE ces vignettes au rendu, au
    # lieu d'imprimer « 0 kWh » / « 0 MAD/an » / « Retour en 0 ans ».
    roi = calculate_savings_roi(puissance_kwc or 0, total_sans, total_avec,
                                **roi_kwargs)
    # ── F1/L-2OPT (26/08/2026) — LA CHAÎNE ÉCONOMIQUE SE CALCULE PAR OPTION ──
    # ``calculate_savings_roi`` dérive TOUT (production, autoconsommation,
    # économies, payback, cashflow 25 ans) d'UN SEUL kWc. Depuis que les deux
    # options peuvent porter des champs PV de tailles différentes, l'appel
    # unique chiffrait les DEUX colonnes du comparatif sur la taille d'UNE
    # seule : sur un devis 22/26, la colonne « Sans batterie » annonçait les
    # économies de 18,46 kWc (≈ +18 %) et un retour sur investissement
    # d'autant trop court — deux chiffres faux, montrés au client.
    # On rejoue donc la dérivation une fois PAR OPTION, chacune sur SON kWc, et
    # chaque côté du dict garde ses propres chiffres. Les métadonnées communes
    # (tarif, modèle d'économies, facture actuelle, hypothèses de cashflow) ne
    # dépendent pas de la puissance : elles restent celles de l'appel
    # principal, qui décrit la branche mise en avant par le document.
    # Options égales — tout l'existant — ⇒ AUCUN second appel, byte-identique.
    prod_kwh_sans = prod_kwh_avec = roi["prod_kwh"]
    # QJR28 — modèle d'économies RÉELLEMENT employé par chaque colonne, quand
    # les deux options sont chiffrées séparément. None ⇒ une seule dérivation,
    # donc un seul modèle : celui du document (cas de tous les devis non
    # divergents, rendu byte-identique).
    _modeles_par_option = None
    if panneaux_divergents:
        def _roi_pour(kwc):
            # Jamais deux fois le même calcul : la branche déjà chiffrée par
            # l'appel principal est réutilisée telle quelle.
            if kwc == puissance_kwc:
                return roi
            # I7 — chaque colonne lit le bloc horaire de SA puissance.
            return calculate_savings_roi(
                kwc or 0, total_sans, total_avec,
                **dict(roi_kwargs, etude_horaire=_etude_horaire_pour(kwc)))

        _roi_s = _roi_pour(puissance_kwc_sans)
        _roi_a = _roi_pour(puissance_kwc_avec)
        for _cle in ("eco_s_ann", "roi_s", "eco_s_monthly", "cashflow_sans",
                     "net_gain_sans", "facture_avec_s", "autoconso_sans",
                     "couverture_sans"):
            roi[_cle] = _roi_s[_cle]
        for _cle in ("eco_a_ann", "eco_a_cumul", "roi_a", "eco_a_monthly",
                     "cashflow_avec", "net_gain_avec", "facture_avec_a",
                     "autoconso_avec", "couverture_avec"):
            roi[_cle] = _roi_a[_cle]
        # ERR-QAC-PAYBACK-JAMAIS-REMBOURSE-25-ANS — le drapeau suit SA colonne.
        roi["roi_s_jamais"] = bool(_roi_s.get("roi_s_jamais"))
        roi["roi_a_jamais"] = bool(_roi_a.get("roi_a_jamais"))
        prod_kwh_sans = _roi_s["prod_kwh"]
        prod_kwh_avec = _roi_a["prod_kwh"]
        # ── QJR28 — DEUX COLONNES, DEUX MOTEURS : LE DOCUMENT LE DIT ────────
        # Le bloc d'étude horaire porte LA puissance pour laquelle il a été
        # calculé, et ``pricing`` le refuse (garde de fraîcheur) dès que
        # l'option rejouée ne fait plus cette puissance. Sur un devis à
        # champs PV divergents, la colonne qui ne correspond pas au bloc
        # retombait donc EN SILENCE sur le forfait « estimation » pendant que
        # le document continuait de déclarer ``savings_model='horaire'`` et
        # ``savings_estimated=False`` pour tout le tableau. On enregistre ici
        # le modèle EFFECTIF de chaque colonne : plus aucun modèle n'est
        # déclaré au nom d'une autre colonne.
        # I7 (30/09/2026) — chaque colonne a désormais SON bloc
        # (``etude_horaire_sans`` pour l'option SANS) ; cette déclaration reste
        # le filet d'un devis dont l'un des deux blocs manque encore.
        _modeles_par_option = {
            "sans": (_roi_s.get("savings_model", "estimation"),
                     bool(_roi_s.get("savings_estimated"))),
            "avec": (_roi_a.get("savings_model", "estimation"),
                     bool(_roi_a.get("savings_estimated"))),
        }
    # AMOT15 (C-AMOT-013, D-ACAL-6) — la production VUE PAR LE CLIENT est
    # celle du moteur devis : une production posée par le CALEPINAGE
    # (``production_source``) n'est plus recopiée ni dans ``roi`` ni dans
    # l'étude rendue. Une production SAISIE par un humain reste souveraine.
    from apps.ventes.domain.etude_schema import (
        PRODUCTION_CALEPINAGE as _PROD_CALEPINAGE)
    _prod_du_calepinage = bool(
        _corrige
        and (devis_etude_override or {}).get("production_source")
        == _PROD_CALEPINAGE)
    if etude.get("production_annuelle"):
        if not _prod_du_calepinage:
            roi["prod_kwh"] = int(etude["production_annuelle"])
        # Une production SAISIE par un humain est UN chiffre, pas deux : elle
        # vaut pour les deux options (comme les économies d'étude juste en
        # dessous). Sans ce réalignement, le une-page aurait pu servir une
        # production dérivée pendant que la page 1 sert celle de l'étude.
        prod_kwh_sans = prod_kwh_avec = roi["prod_kwh"]
        # ── QJR410 (a) / S8-F6 — LE CHIFFRE DÉCRIT L'OPTION QUE LE DOCUMENT
        # TITRE ────────────────────────────────────────────────────────────
        # ``_ref_total`` était clavé sur ``sans_ok`` : sur un document dont
        # l'option titrée est « avec » (deux options — le total mis en avant
        # est celui de l'option AVEC — ou mono-option « avec »), la carte
        # « Prix par kWc » et le payback décrivaient l'option SANS. Un chiffre
        # CLIENT qui décrit une offre que le document ne porte pas. La bascule
        # suit EXACTEMENT celle de ``display_total`` (« avec » dès que le
        # document met cette option en avant), pour qu'il n'y ait qu'une
        # vérité par document.
        # CIQ302 — un C&I qui titre l'offre réseau seule n'est pas « avec ».
        _titree_avec = (False if option_servie == 'sans'
                        else bool(deux_options or avec_ok))
        _ref_total = total_avec if _titree_avec else total_sans
        # CIQ301 — la branche « étude saisie » (économie imposée + fractions
        # mensuelles RÉSIDENTIELLES ``_sf``) ne s'applique PLUS au C&I : ses
        # économies viendront du moteur C&I (``synthese_ci.argent``, CIQ307),
        # jamais d'une clé d'étude reprise ni d'une saisonnalité résidentielle.
        if etude.get("economies_annuelles") and not _mode_ci and not _corrige:
            # Règles d'origine (devis envoyé avant AMOT15) : l'économie saisie
            # collée après coup, payback LINÉAIRE — le chemin d'hier.
            eco = int(etude["economies_annuelles"])
            roi["eco_s_ann"] = eco
            roi["eco_a_ann"] = eco
            roi["eco_a_cumul"] = eco
            roi["roi_s"] = round(_ref_total / eco, 1) if eco > 0 else 0.0
            roi["roi_a"] = roi["roi_s"]
            roi["roi_s_jamais"] = roi["roi_a_jamais"] = False
            from .pricing import CLE_SOLAIRE_MENSUELLE_HISTORIQUE as _sf
            roi["eco_s_monthly"] = [round(eco * f) for f in _sf]
            roi["eco_a_monthly"] = list(roi["eco_s_monthly"])
        elif etude.get("economies_annuelles") and not _mode_ci:
            eco = int(etude["economies_annuelles"])
            # AMOT15 — l'économie saisie entre dans LA chaîne de calcul
            # (``calculate_savings_roi(economie_imposee=…)``) : payback de
            # chaque option = croisement de SA courbe (son prix, dégradation,
            # provision onduleur), gain net = fin de courbe — plus de payback
            # linéaire ni d'économie collée après coup.
            _roi_eco = calculate_savings_roi(
                puissance_kwc or 0, total_sans, total_avec,
                **dict(roi_kwargs, economie_imposee=eco))
            for _cle in ("eco_s_ann", "eco_a_ann", "eco_a_cumul", "roi_s",
                         "roi_a", "roi_s_jamais", "roi_a_jamais",
                         "eco_s_monthly", "eco_a_monthly", "cashflow_sans",
                         "cashflow_avec", "net_gain_sans", "net_gain_avec"):
                roi[_cle] = _roi_eco[_cle]
        # L'étude rendue reprend les valeurs canoniques (jamais deux versions)
        etude["production_annuelle"] = roi["prod_kwh"]
        if etude.get("economies_annuelles") and not _mode_ci:
            etude["economies_annuelles"] = roi["eco_s_ann"]
            # QJR410 (a) — le payback était CÂBLÉ EN DUR sur le ROI « sans ».
            etude["payback"] = roi["roi_a"] if _titree_avec else roi["roi_s"]
        # ── QJR160 — LE PRIX PAR KWC DÉCRIT UNE OFFRE, PAS UN MÉLANGE ───────
        # ``_ref_total`` est le TTC de l'option 1 (« sans » quand elle est
        # servable) tandis que ``puissance_kwc`` a été recalé sur le kWc de
        # l'option 2 dès que les champs PV divergent (repli documenté
        # ``panneaux_divergents``, plus haut) : le quotient ne décrivait alors
        # AUCUNE des deux offres. On apparie donc le total et le kWc de la
        # MÊME branche. Et sur un document qui chiffre DEUX options de tailles
        # différentes, aucun prix au kWc unique n'a de sens : la carte est
        # OMISE plutôt que de faire choisir au client entre deux vérités.
        # QJR410 (a) — le kWc suit la MÊME branche que ``_ref_total``.
        _kwc_ref = (puissance_kwc_avec if _titree_avec else puissance_kwc_sans)
        if not _kwc_ref or _kwc_ref <= 0:
            _kwc_ref = puissance_kwc
        if deux_options and panneaux_divergents:
            etude.pop("prix_kwc", None)
        elif (_kwc_ref or 0) > 0:
            etude["prix_kwc"] = round(_ref_total / _kwc_ref)

    # ── QXMT — UN DOSSIER MT NE PORTE JAMAIS UN CHIFFRE BT ───────────────────
    #
    # ``solar.js`` pose ``etude_params['tension_raccordement'] = 'MT'`` sur un
    # dossier raccordé en moyenne tension et, faute de répartition horaire,
    # laisse délibérément ``economies_annuelles`` à ``None`` — l'ÉCRAN affiche
    # alors « économies et payback volontairement omis ». Le PDF, lui, ne lisait
    # AUCUNE de ces clés : ``if etude.get("economies_annuelles")`` étant faux,
    # le bloc d'étude n'écrasait rien et ``calculate_savings_roi`` (tarif BT
    # ONEE) restait la source des économies et du payback rendus au client.
    # Le client recevait donc un chiffre BT sur un dossier MT — exactement le
    # « chiffre BT déguisé en chiffre MT » que le commentaire de solar.js
    # interdit.
    #
    # Deux sorties, jamais un chiffre inventé entre les deux :
    #   · sans économies d'étude → ``masquer_economies`` : les renderers OMETTENT
    #     le bloc ROI/économies (pas un « 0 », pas un chiffre BT) ;
    #   · avec économies d'étude → ``tarif_mt_mention`` : la source du barème
    #     voyage AVEC le chiffre, comme MENTION_82_21 voyage avec l'injection.
    _tension_racc = str(etude.get("tension_raccordement") or "").strip().lower()
    _dossier_mt = _tension_racc == "mt"
    # CIQ301 — en C&I, une économie d'étude n'est jamais reprise (ci-dessus) :
    # un dossier MT commercial/industriel garde donc TOUJOURS son motif MT.
    masquer_economies = bool(_dossier_mt
                             and (_mode_ci
                                  or not etude.get("economies_annuelles")))
    tarif_mt_mention = ""
    # ── CIQ210 — LE C&I EST CHIFFRÉ PAR ``economie_ci`` (D-CIQ-0) ───────────
    # Commercial / industriel : le bloc vient du moteur C&I (valorisation
    # horaire au tarif du POSTE, tarif déclaré ou grille ONEE étiquetée
    # « repli ») — jamais ``calculate_savings_roi`` (60 %), ``onee_tarif_kwh``
    # (1,75), une économie de calepinage ni les fractions ``_sf``. Le masque
    # suit le STATUT du bloc (``omis`` ⇒ masqué, motif nommé) et la mention MT
    # n'accompagne que des économies valorisées au Tarif Général MT. Le
    # moteur ne fait que LIRE (règle #4). Le bloc PUBLIC (sans vue interne)
    # est posé sur ``data['economie_ci']`` plus bas.
    _economie_ci = None
    if _mode_ci:
        try:
            from apps.ventes.economie_ci import (
                economie_ci_pour_devis, economie_ci_publique)
            _economie_ci = economie_ci_publique(economie_ci_pour_devis(
                devis, getattr(devis, "company", None)))
        except Exception:  # noqa: BLE001 — un PDF ne casse jamais là-dessus (D-ENF22-BLE001)
            logger.exception("economie_ci: échec (devis %s)",
                             getattr(devis, "reference", "?"))
            _economie_ci = None
        _statut_ci = (_economie_ci or {}).get("statut")
        masquer_economies = _statut_ci != "calcule"
        _dossier_mt = bool(
            _statut_ci == "calcule"
            and ((_economie_ci.get("tarif") or {}).get("contrat")
                 == "mt_general"))
    if _dossier_mt and not masquer_economies:
        try:
            from .ci.mentions import mention_tarif_mt
            # AMOT81 — MENTION_MT (ONEE) seulement quand la GRILLE est la
            # source ; un tarif lu sur la facture du client le dit.
            tarif_mt_mention = mention_tarif_mt(
                (_economie_ci or {}).get("tarif") if _mode_ci else None,
                langue=opts.get('langue_sortie'))
        except Exception:  # noqa: BLE001 — un PDF ne casse jamais là-dessus (D-ENF22-BLE001)
            logger.warning("builder.build_quote_data : erreur ignorée (mode dégradé)", exc_info=True)
            tarif_mt_mention = ""

    # ── QF2 — modèle « deux factures » (économies réelles, par tranche) ──────
    # Le modèle effectivement utilisé pour les économies affichées :
    #   'factures'   — facture_sans − facture_avec, par tranche (données réelles)
    #   'etude'      — économies imposées par l'étude stockée (bloc ci-dessus)
    #   'estimation' — ancienne approximation production × autoconso × prix,
    #                  toujours étiquetée comme estimation (aucun chiffre inventé).
    savings_model = roi.get("savings_model", "estimation")
    if (etude.get("production_annuelle") and etude.get("economies_annuelles")
            and not _mode_ci):
        savings_model = "etude"
    # QJR28 — la DÉCLARATION par colonne. Une étude saisie par un humain
    # impose UN chiffre aux deux options : les deux colonnes sont alors
    # 'etude'. Sinon, chaque colonne déclare le modèle qui l'a réellement
    # chiffrée (identique au modèle du document tant que rien ne diverge).
    _sm_defaut = (savings_model, bool(roi.get("savings_estimated")))
    if savings_model == "etude" or not _modeles_par_option:
        savings_model_sans = savings_model_avec = _sm_defaut[0]
        savings_estimated_sans = savings_estimated_avec = _sm_defaut[1]
    else:
        savings_model_sans, savings_estimated_sans = _modeles_par_option["sans"]
        savings_model_avec, savings_estimated_avec = _modeles_par_option["avec"]
    if savings_model == "factures":
        # Persistance dans les paramètres d'étude RENDUS : la page étude et la
        # proposition web reprennent exactement les mêmes chiffres (une seule
        # source). Rendu seulement — aucun statut, aucune écriture en base.
        etude["facture_annuelle_sans_solaire"] = roi["facture_sans"]
        etude["facture_annuelle_avec_solaire_opt1"] = roi["facture_avec_s"]
        etude["facture_annuelle_avec_solaire_opt2"] = roi["facture_avec_a"]
        etude["economie_reelle_opt1"] = roi["eco_s_ann"]
        etude["economie_reelle_opt2"] = roi["eco_a_ann"]
        # ── QJR425 / DR7 — LA NOTE DE MÉTHODE ATTEINT ENFIN LA SURFACE QUI
        # PORTE LES MONTANTS ─────────────────────────────────────────────────
        # ``calculate_savings_roi`` RENDAIT déjà ``factures_note_methode``
        # (QJR157) et PERSONNE ne le lisait : la note qui dit sur quelle base
        # les douze mois ont été tarifés — la traçabilité qu'exige la règle
        # checked-facts — n'était publiée par AUCUNE surface, et
        # ``pricing.NOTE_DOUZE_MOIS`` restait inatteignable depuis l'ERP.
        # Elle voyage désormais AVEC les montants qu'elle décrit, sur la même
        # surface d'étude. Aucun montant ne bouge : la note s'AJOUTE (règle
        # permanente 1 — cette tâche câble, elle ne recalcule rien).
        # Note ABSENTE ⇒ AUCUNE clé (jamais une note vide, jamais un texte par
        # défaut, règle Z2).
        if roi.get("factures_note_methode"):
            etude["factures_note"] = roi["factures_note_methode"]
    return (_client_city, _client_city_libelle, _co_productible,
            _conso_annuelle, _economie_ci, _utility, etude, masquer_economies,
            prod_kwh_avec, prod_kwh_sans, roi, savings_estimated_avec,
            savings_estimated_sans, savings_model, savings_model_avec,
            savings_model_sans, tarif_mt_mention)
