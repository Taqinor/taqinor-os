"""SPL166 — phase D2 de ``build_quote_data`` : restitution de l'étude (move only).

Déplacés tels quels de ``builder.py`` : le corps de ``build_quote_data`` du
marqueur « QF3 — bloc » jusqu'à l'étiquetage de la série mensuelle (juste
avant la phase E), devenu ``restituer_etude`` (avec sa fonction imbriquée
``_fr_int``) — méthode « Comment nous calculons vos économies », hypothèses,
série mensuelle des factures et son étiquetage —, et ``ligne_tarif_hypothese``
(son seul utilisateur). ``restituer_etude`` reçoit les sorties de la phase D1
en arguments NOMMÉS et rend les siennes dans l'ordre que ``build_quote_data``
dépaquette dans les MÊMES noms locaux ; ``roi`` est muté en place (même objet).
Les imports locaux (``pricing``, ``productible``…) restent locaux, résolus à
l'appel. Rendu pur (règle #4) : aucun statut touché.

Ce module n'importe JAMAIS ``builder`` (cycle).
"""
from __future__ import annotations


def ligne_tarif_hypothese(tarif_txt, util_name, savings_estimated) -> str:
    """Ligne « Tarif électricité » du bloc « Nos hypothèses ».

    M11 (audit adversarial du 19/08/2026) — UN RÉGLAGE SOCIÉTÉ POSÉ PAR DÉFAUT
    N'EST PAS UNE DONNÉE DU CLIENT. Le discriminateur était « ce tarif est-il
    égal à la constante interne 1,75 ? » : dès qu'une société avait touché son
    réglage ``onee_tarif_kwh`` — ou en gardait simplement un autre défaut — le
    document annonçait un tarif « personnalisé pour votre profil de
    consommation ». C'est un forfait maison, commun à tous ses clients, et le
    moteur le SAIT : ``savings_estimated`` reste vrai tant qu'aucun barème réel
    n'a servi. C'est donc ce drapeau qui décide, jamais une comparaison avec une
    constante. Extrait en fonction PURE pour être épinglé par un test.
    """
    if savings_estimated:
        return ("Tarif électricité : référence prudente (estimation) — "
                "transmettez une facture récente et nous recalculons vos "
                "économies par tranches, sur votre barème exact.")
    if util_name:
        return f"Tarif électricité retenu : {tarif_txt} MAD/kWh ({util_name})"
    return (f"Tarif électricité : {tarif_txt} MAD/kWh, saisi pour ce devis — "
            "un calcul par tranches sur facture réelle reste possible.")


def restituer_etude(*, _client_city, _co_productible, _corrige, _utility,
                    etude, puissance_kwc, roi, savings_model,
                    savings_model_avec, savings_model_sans, scenario):
    # ── QF3 — bloc « Comment nous calculons vos économies » ──────────────────
    # Méthode + exemple chiffré compact, calculés UNE fois ici : le PDF premium
    # et la proposition web (/proposal) rendent EXACTEMENT le même bloc.
    def _fr_int(n):
        return f"{int(round(n)):,}".replace(",", " ")

    _sm_eco_ref = roi["eco_a_ann"] if scenario == "Avec batterie" else roi["eco_s_ann"]
    if savings_model == "factures":
        _sm_avec = (roi["facture_avec_a"] if scenario == "Avec batterie"
                    else roi["facture_avec_s"])
        savings_method = {
            "model": "factures",
            "facture_actuelle": roi["facture_sans"],
            "facture_avec_solaire": _sm_avec,
            "economie": roi["facture_sans"] - _sm_avec,
            "approximatif": bool(roi.get("factures_approximatif")),
            # Le barème résidentiel n'est PAS purement progressif : au-delà de
            # 150 kWh/mois il est SÉLECTIF (toute la consommation du mois au
            # tarif de sa tranche), et c'est exactement ce qui rend l'économie
            # réelle plus grande — en repassant sous une marche, le client
            # re-tarife TOUT son résiduel. La phrase doit dire ce que le moteur
            # fait (pricing.ONEE_TRANCHES), pas l'inverse.
            "ligne_methode": (
                "Facture recalculée au barème réel du distributeur "
                "(progressif ≤ 150 kWh/mois, puis sélectif : toute la conso du "
                "mois au tarif de SA tranche) : facture actuelle moins facture "
                "résiduelle après autoconsommation — jamais un prix moyen "
                "inventé."),
            # QRES40 — MAD partout (le document n'emploie jamais « DH » :
            # une seule unité monétaire, aucune hésitation possible).
            "exemple": (
                f"Facture actuelle ≈ {_fr_int(roi['facture_sans'])} MAD/an → "
                f"avec solaire ≈ {_fr_int(_sm_avec)} MAD/an → économie ≈ "
                f"{_fr_int(roi['facture_sans'] - _sm_avec)} MAD/an"),
            # QJR425 / DR7 — la note de méthode voyage AVEC le chiffre qu'elle
            # décrit (« sur quelle base ces douze mois ont-ils été tarifés »).
            # ``None`` quand le moteur n'en a produit aucune — jamais un texte
            # par défaut.
            "note_methode": roi.get("factures_note_methode") or None,
        }
    elif savings_model == "horaire":
        # ── QJR27 — LE BLOC DÉCRIT LA MÉTHODE RÉELLEMENT EMPLOYÉE ───────────
        # Le modèle HORAIRE (CJ2a : production PVGIS du site intégrée heure par
        # heure contre la courbe de consommation du client, chaque mois
        # valorisé au barème) est le PLUS FORT du moteur, et il est ancré sur
        # une facture RÉELLE. Faute de branche, il tombait dans le repli
        # « estimation » : le bloc annonçait au client une approximation et lui
        # RÉCLAMAIT une facture qu'il avait déjà fournie, pendant que la
        # couverture du même PDF affichait « calculée ». Une phrase de méthode
        # fausse, plus une demande d'un document déjà reçu.
        _sm_sans_h = roi.get("facture_sans")
        _sm_avec_h = (roi.get("facture_avec_a") if scenario == "Avec batterie"
                      else roi.get("facture_avec_s"))
        # L'exemple chiffré n'existe que si les DEUX factures sont lisibles :
        # sans elles on garde la phrase de méthode, jamais un montant fabriqué.
        _paire_h = bool(_sm_sans_h) and _sm_avec_h is not None
        savings_method = {
            "model": "horaire",
            "facture_actuelle": _sm_sans_h if _paire_h else None,
            "facture_avec_solaire": _sm_avec_h if _paire_h else None,
            "economie": ((_sm_sans_h - _sm_avec_h) if _paire_h
                         else _sm_eco_ref),
            "approximatif": False,
            "ligne_methode": (
                "Économies intégrées heure par heure : la production solaire "
                "de votre site (données PVGIS) confrontée à votre courbe de "
                "consommation, mois par mois, chaque mois valorisé au barème "
                "réel du distributeur. Le point de départ est VOTRE facture — "
                "c'est la méthode la plus fine de ce document."),
            "exemple": ((
                f"Facture actuelle ≈ {_fr_int(_sm_sans_h)} MAD/an → "
                f"avec solaire ≈ {_fr_int(_sm_avec_h)} MAD/an → économie ≈ "
                f"{_fr_int(_sm_sans_h - _sm_avec_h)} MAD/an")
                if _paire_h else None),
        }
    elif savings_model == "etude":
        savings_method = {
            "model": "etude",
            "facture_actuelle": None,
            "facture_avec_solaire": None,
            "economie": _sm_eco_ref,
            "approximatif": False,
            # AMOT15 — la phrase dit la source RÉELLE : économie SAISIE dans
            # l'étude, retour et gain net CALCULÉS sur elle option par option.
            "ligne_methode": (
                "Économies saisies dans l'étude de consommation enregistrée "
                "avec ce devis ; le retour sur investissement et le gain net "
                "sur 25 ans en sont calculés pour chaque option (prix de "
                "l'option, dégradation des panneaux, remplacement de "
                "l'onduleur)." if _corrige else
                "Économies issues de l'étude de consommation enregistrée avec "
                "ce devis (production et économies calculées sur votre profil "
                "réel)."),
            "exemple": None,
        }
    else:
        savings_method = {
            "model": "estimation",
            "facture_actuelle": None,
            "facture_avec_solaire": None,
            "economie": _sm_eco_ref,
            "approximatif": True,
            "ligne_methode": (
                "Estimation : production annuelle × part autoconsommée × tarif "
                "kWh (loi 82-21 : seul l'autoconsommé est valorisé — détail "
                "dans nos hypothèses). Fournissez une facture réelle pour un "
                "calcul par tranche exact."),
            "exemple": None,
        }

    # ── QK4 — « Nos hypothèses » : transparence des hypothèses d'économies ────
    # Surface côté client les hypothèses derrière les économies : tarif MAD/kWh
    # utilisé, source du barème (Q7 : UNE grille nationale, le nom du
    # distributeur n'est plus qu'un libellé), autoconsommation d'abord
    # (loi 82-21, injection OFF —
    # rachat BT résidentiel différé par l'ANRE), base de production/dégradation.
    # Toutes les valeurs viennent de roi/etude (une source) ; dégrade proprement.
    _util_labels = {"onee": "ONEE", "lydec": "Lydec", "redal": "Redal",
                    "amendis": "Amendis"}
    _util_key = (str(_utility).strip().lower() if _utility else "")
    # CAD167 — un distributeur nommé hors table tarife sur la grille nationale :
    # sans libellé, le bloc hypothèses le disait « saisi pour ce devis ».
    _util_name = _util_labels.get(_util_key) or (
        "SRM" if _util_key.startswith("srm_")
        else ("national" if _util_key else ""))
    # Q7 — plus aucun barème « approximatif » : les trois distributeurs lisent
    # la grille nationale (éditable par société). Le drapeau reste, toujours
    # faux, pour ne casser aucun consommateur de la charge utile.
    _util_approx = False
    # M10/M11 — LE MODÈLE D'ÉCONOMIES EST-IL UNE ESTIMATION ? ``savings_estimated``
    # est calculé par ``calculate_savings_roi`` (aucun barème réel n'a servi)
    # mais n'était lu par AUCUN renderer : le document ne distinguait pas une
    # économie calculée sur le barème réel du client d'une économie estimée.
    _savings_estimated = bool(roi.get("savings_estimated"))
    _tarif_val = roi.get("tarif_kwh")
    _tarif_txt = (f"{_tarif_val:.2f}".replace(".", ",")
                  if isinstance(_tarif_val, (int, float)) else None)
    _prod_factor = roi.get("productible")
    # ── QJR18 — LE PRODUCTIBLE IMPRIMÉ EST CELUI DE CE DOCUMENT ─────────────
    # ``roi['productible']`` CHANGE DE SENS selon le modèle d'économies : sur
    # le chemin ordinaire c'est le productible du repère (déjà net des 14 %
    # PVGIS, à qui il reste le complément ``PRODUCTION_DERATE`` à appliquer),
    # mais sur le chemin ÉTUDE HORAIRE ``pricing`` y pose
    # ``production_annuelle / kwc`` — une valeur DÉJÀ NETTE. Lui réappliquer
    # le derate appliquait les pertes une SECONDE fois : le « ≈ N kWh par kWc
    # et par an » imprimé tombait ~7 % sous la production annuelle imprimée
    # sur la MÊME page (et la pastille PVGIS de la ville avec lui).
    # On le dérive donc de la SEULE source qui fait foi — la production
    # annuelle RENDUE ÷ la puissance rendue : les deux nombres du document se
    # réconcilient alors par construction, quel que soit le modèle, y compris
    # quand une étude saisie a écrasé la production. Puissance inconnue ⇒
    # ancien calcul (le productible est alors resté brut, aucun double emploi).
    _prod_net_kwc = None
    if (puissance_kwc or 0) > 0 and roi.get("prod_kwh"):
        _prod_net_kwc = float(roi["prod_kwh"]) / float(puissance_kwc)
    elif _prod_factor:
        from .pricing import PRODUCTION_DERATE as _DERATE_REPLI
        _prod_net_kwc = float(_prod_factor) * _DERATE_REPLI
    hypotheses = []
    if savings_model == "factures" and _util_name:
        hypotheses.append(
            f"Tarif électricité : barème {_util_name} par tranche"
            + " (barème national)")
    elif _tarif_txt:
        # QRES16 (fondateur, 2026-07-18) — ne JAMAIS présenter le défaut
        # interne du simulateur comme un « tarif retenu » réfléchi : le 1,75
        # historique (constants.KWH_PRICE, marqué « ne pas afficher dans les
        # PDF/UI ») s'imprimait tel quel via ce bloc et fragilisait la
        # confiance. Un tarif ÉGAL au défaut est présenté comme référence de
        # calcul avec le chemin vers l'exactitude (facture → barème par
        # tranches) ; un tarif réellement personnalisé reste affiché comme
        # tel ; le cas barème (« factures ») garde sa ligne dédiée ci-dessus.
        # QRES55 (fondateur, 2026-07-18) — le tarif de référence interne ne
        # s'affiche JAMAIS en chiffres sur le document (ni « 1,75 » ni un
        # autre) : la ligne dit la MÉTHODE et le chemin vers l'exactitude.
        # Seul un tarif réellement personnalisé (saisi pour CE devis, différent
        # du défaut) reste affiché, car c'est la donnée du client.
        # Z3 × M11 — MÊME défaut, deux correctifs : on garde le plus
        # STRICT (M11). Z3 avait identifié la cause — la garde QRES55
        # comparait le tarif à ``constants.KWH_PRICE`` (1,75, l'ANCIEN
        # défaut, plus jamais utilisé comme prix) au lieu du repli
        # réellement appliqué ``_FALLBACK_KWH_PRICE`` (1,20) : l'égalité
        # n'arrivant jamais, la branche « personnalisé » s'exécutait
        # TOUJOURS. M11 va plus loin sur trois points : le drapeau
        # ``savings_estimated`` est testé EN PREMIER (un tarif estimé ne
        # peut plus être habillé en « tarif retenu (ONEE) »), la ligne
        # PORTE le mot « (estimation) », et la branche restante dit
        # « saisi pour ce devis » au lieu de revendiquer un « profil de
        # consommation » que le moteur n'a jamais analysé.
        hypotheses.append(ligne_tarif_hypothese(
            _tarif_txt, _util_name, _savings_estimated))
    # QRES55 — formulations COMPACTES (le fondateur veut la même transparence
    # « en plus petit ») : une idée, une ligne courte.
    # AMOT25 (C-AMOT-025) — LA mention sourcée unique (``constants_82_21``,
    # identique au C&I, CIQ201) : plus de « plafond d'injection 20 %
    # intégré » ni de « rachat BT non publié », phrases que le calcul ne fait
    # pas.
    from .constants_82_21 import MENTION_BT as _MENTION_BT
    hypotheses.append(
        f"{_MENTION_BT}. Seuls les kWh autoconsommés réduisent la facture.")
    if _prod_net_kwc:
        # Production NETTE affichée, la même que TOUS les calculs du document :
        # pertes système de 20 % AU TOTAL (ordre fondateur 18/08). Le chiffre
        # rendu doit dire le total réel — l'ancienne mention « 14 % » était
        # doublement fausse (elle nommait les seules pertes PVGIS alors que le
        # moteur en retranchait 14 % de plus, soit 26 % cumulés).
        # QJR18 — la valeur vient de ``_prod_net_kwc`` (production rendue ÷
        # puissance rendue), plus d'un second derate appliqué au productible.
        from .pricing import SYSTEM_LOSS_TOTAL as _LOSS
        hypotheses.append(
            f"Production estimée : ≈ {_fr_int(_prod_net_kwc)} "
            f"kWh par kWc et par an, pertes système de "
            f"{int(round(_LOSS * 100))} % déduites.")
    # Q6 — le productible PVGIS de la ville du client, prêt à imprimer, ou None.
    # Deux conditions STRICTES : la ville doit être dans la table PVGIS (le
    # calcul, lui, retombe silencieusement sur Casablanca — pas l'affichage),
    # et aucun réglage société ne doit avoir forcé la valeur (ce ne serait plus
    # une donnée PVGIS). Sinon : None ⇒ omission.
    _productible_net_pvgis = None
    _ville_pvgis = None
    _ville_pvgis_est_reference = False
    if _prod_net_kwc:
        # QJR127 — on publie la ville de RÉFÉRENCE, jamais la ville du client.
        # ``ville_reconnue`` répond « oui » pour les 15 villes d'ALIAS (Settat,
        # Kénitra, Témara…) qui ne sont PAS dans la table PVGIS : la pastille
        # imprimait « à Settat (donnée PVGIS) » avec la valeur de Casablanca et
        # l'annexe publiait ``{'source': 'PVGIS', 'ville': 'Settat'}`` — le
        # « national moyen déguisé en donnée locale » que le docstring de la
        # fonction interdit lui-même.
        from .productible import (est_ville_de_reference as _est_ref,
                                  ville_reference as _ville_ref)
        # AMOT64 — toute valeur société renseignée (1 600 compris) force le
        # productible : ce n'est plus une donnée PVGIS ⇒ la phrase s'omet.
        _force_societe = bool(_co_productible and float(_co_productible) > 0)
        _ref = _ville_ref(_client_city)
        if _ref and not _force_societe:
            # QJR18 — MÊME valeur nette que la ligne d'hypothèse ci-dessus :
            # deux phrases du même document ne peuvent pas annoncer deux
            # productibles différents pour la même installation.
            _productible_net_pvgis = int(round(_prod_net_kwc))
            _ville_pvgis = _ref
            # Vrai quand la ville du client EST elle-même dans la table : le
            # rendu peut alors dire « à <ville> » sans autre précision ; sinon
            # il DIT que c'est la ville de référence la plus proche.
            _ville_pvgis_est_reference = _est_ref(_client_city)

    _ac_s = roi.get("autoconso_sans")
    _ac_a = roi.get("autoconso_avec")
    if _ac_s and _ac_a:
        hypotheses.append(
            f"Autoconsommation retenue : {int(round(_ac_s * 100))} % sans "
            f"batterie · {int(round(_ac_a * 100))} % avec batterie.")
    # QX39 — hypothèses du cashflow 25 ans (dégradation/escalade/batterie),
    # documentées et rendues sur le PDF/la proposition. Le payback vient
    # désormais du croisement du cumul à zéro, pas d'un ratio année-1.
    # QRES1 — dédoublonnage SÉMANTIQUE : le bloc cumulait trois formulations de
    # la loi 82-21 (la sienne, celle de savings_method, celle du cashflow) —
    # une idée n'apparaît qu'une fois, le mur de texte de la page 3 disparaît.
    _cf_assum = roi.get("cashflow_assumptions") or {}
    for _n in (_cf_assum.get("notes") or []):
        _n = str(_n).strip()
        if not _n or _n in hypotheses:
            continue
        if "82-21" in _n and any("82-21" in h for h in hypotheses):
            continue
        hypotheses.append(_n)
    # QRES59 — « toute hausse vous profite » ne se dit qu'UNE fois (la note
    # cashflow ci-dessus) : la ligne finale reste sobre.
    hypotheses.append("Estimations non contractuelles.")
    hypotheses_block = {
        "titre": "Nos hypothèses",
        "items": hypotheses,
        "tarif_kwh": _tarif_val,
        "tarif_kwh_txt": _tarif_txt,
        "tranche_source": _util_name or None,
        "tranche_approximatif": bool(_util_approx),
        "autoconso_first": True,
        "productible_kwh_kwc": (int(round(_prod_factor)) if _prod_factor
                                else None),
        # ── Q6 (décision fondateur du 20/08/2026) — LA DONNÉE LOCALE REMPLACE
        # LE SLOGAN. Le PDF affichait « 3 000 h/an d'ensoleillement », un
        # chiffre national arrondi qui ne décrit ni ce client ni ce devis.
        # Le productible PVGIS de SA ville est déjà en machine : c'est lui
        # qu'on imprime, en production NETTE (la même que tous les calculs du
        # document). Ville hors table PVGIS, ou productible forcé par un
        # réglage société : la phrase s'OMET — jamais une moyenne nationale
        # présentée comme la donnée du client.
        "productible_net_kwh_kwc": _productible_net_pvgis,
        # QJR127 — ville de RÉFÉRENCE de la table PVGIS (jamais la ville du
        # client quand elle n'y figure pas), + le drapeau qui dit si les deux
        # coïncident. L'annexe technique (``calepinage_options``) lit la même
        # clé : elle cesse elle aussi de publier une ville hors table.
        "productible_ville": _ville_pvgis,
        "productible_ville_est_reference": _ville_pvgis_est_reference,
    }

    # ── M1 (audit adversarial du 19/08/2026) — PLUS AUCUN PROXY DE FACTURE ────
    # Les 12 factures mensuelles du client sont une DONNÉE, jamais un calcul.
    # Elles viennent de ``etude_params.factures_mensuelles_reelles``, semé par
    # le devis auto résidentiel (frontend/.../autoQuote.js) depuis la facture
    # hiver/été du lead. Quand elles manquent : ``None`` — et la page 1 (« votre
    # facture baisse de N % », « ≈ X MAD/mois aujourd'hui ») N'EST PAS RENDUE.
    #
    # CE QUI EST MORT ICI : ``facture ≈ économies option 2 / taux
    # d'autoconsommation``. Ce proxy fabriquait la facture à partir de
    # l'économie SUPPOSÉE, elle-même dérivée du même taux : le « −85 % » de la
    # page 1 n'était donc que le taux forfaitaire redéguisé en promesse, et le
    # « ≈ X MAD/mois aujourd'hui » un rétro-calcul présenté comme la facture du
    # client. Circulaire de bout en bout, et imprimé comme un fait.
    # Le lot Z avait déjà supprimé le cas « aucun ancrage réel » ; l'audit
    # prouve que le proxy tirait ENCORE dès que le tarif était réel mais les
    # factures absentes. Il n'y a plus de repli du tout.
    #
    # DÉGRADATION (voulue, déjà en place) : ``residential/renderer._augment``
    # refuse une série absente (Unsupported) → le moteur rend le format legacy,
    # dont la carte mensuelle omet les barres de facture ; la page publique ne
    # sert plus la série ni la synthèse. Aucun chemin n'invente de chiffre.
    # Garde stricte sur la donnée réelle : exactement 12 valeurs numériques
    # strictement positives, sinon rien.
    _factures_reelles = etude.get("factures_mensuelles_reelles")
    factures_mensuelles = None
    if isinstance(_factures_reelles, (list, tuple)) and len(_factures_reelles) == 12:
        try:
            _candidats = [float(v) for v in _factures_reelles]
            if all(v > 0 for v in _candidats):
                factures_mensuelles = [round(v) for v in _candidats]
        except (TypeError, ValueError):
            factures_mensuelles = None

    # ── CJ2b (ORDRE FONDATEUR, 21/08/2026) — LE BLOC HORAIRE EST UN ANCRAGE ───
    # « bring [the annual saving chart per month] back to the quote pdf because
    # it disappeared from there ».
    #
    # POURQUOI IL AVAIT DISPARU. Z2/M1 ont eu raison de supprimer le proxy :
    # sans les douze factures du lead, la série « avant » était fabriquée à
    # partir de l'économie SUPPOSÉE, donc circulaire. Résultat : sur l'immense
    # majorité des devis — où le client donne UNE facture d'hiver, pas douze —
    # ``factures_reelles`` restait faux, ``masquer_synthese`` vrai, et TOUTE la
    # couche économique du document (le −N %, l'avant/après, la couverture, le
    # graphe mensuel) disparaissait avec le proxy. La règle est juste ; il
    # manquait la troisième source, ni douze factures ni invention.
    #
    # CETTE SOURCE EXISTE DEPUIS CJ2a. Le bloc ``etude_params['etude_horaire']``
    # part du montant RÉELLEMENT payé par le client, l'inverse au barème pour
    # obtenir des kWh, intègre heure par heure la production PVGIS de SA ville
    # contre SA courbe de consommation, puis revalorise chaque mois au barème.
    # Les douze ``facture_avant_mad`` qu'il porte sont donc une DÉRIVATION
    # TRAÇABLE d'une saisie réelle — exactement le second cas autorisé par la
    # règle « zéro chiffre inventé ». Le proxy tué par M1 partait de l'économie
    # supposée et y revenait ; celui-ci part de la facture payée.
    #
    # Z2 N'EST PAS AFFAIBLIE : un devis SANS rien (ni facture, ni conso saisie,
    # ni localisation PVGIS) n'a pas de bloc horaire du tout — ``etude_horaire``
    # vaut None, cette branche ne tire pas, et le document omet sa couche
    # économique comme avant. On n'élargit l'ancrage qu'aux devis qui portent
    # une VRAIE facture.
    #
    # La garde de fraîcheur kWc (``pricing._HORAIRE_TOLERANCE_KWC``, 2 %) est
    # déjà appliquée en amont par ``_lire_etude_horaire`` : une série qui décrit
    # une AUTRE puissance ne remonte jamais jusqu'ici.
    factures_source = "lead_12_mois" if factures_mensuelles is not None else None
    if factures_mensuelles is None and roi.get("factures_avant_monthly"):
        factures_mensuelles = list(roi["factures_avant_monthly"])
        factures_source = "etude_horaire"

    # ── ERR-QAC-GRAPHE-MENSUEL-CLE-SOLAIRE — LE GRAPHE = LA CARTE ────────────
    # Hors modèle « horaire », ``pricing`` répartit l'économie annuelle par la
    # clé solaire FIXE sans regarder les factures ; le graphe mensuel plancher
    # ensuite chaque mois à sa facture, donc l'économie que la clé attribuait
    # au-delà de la facture des mois d'été disparaissait du graphe, du « X →
    # Y MAD/an » et du −N % — mais restait dans la carte option (``eco_*_ann``).
    # Deux économies annuelles sur la même page. Quand les douze factures sont
    # connues, la série est re-répartie par la MÊME clé PLAFONNÉE à la facture
    # de chaque mois (helper pur ``pricing.repartir_economie_plafonnee``) :
    # Σ des douze mois = économie de la carte, aucun mois > sa facture.
    # ``eco_*_ann``, payback et cashflow ne bougent pas (ils ne lisent pas la
    # série). Le modèle « horaire » garde ses douze mois RÉELLEMENT calculés.
    if factures_mensuelles is not None:
        from .pricing import repartir_economie_plafonnee
        for _modele_opt, _cle_ann, _cle_mois in (
                (savings_model_sans, "eco_s_ann", "eco_s_monthly"),
                (savings_model_avec, "eco_a_ann", "eco_a_monthly")):
            if _modele_opt == "horaire":
                continue
            from .pricing import (CLE_SOLAIRE_MENSUELLE,
                                  CLE_SOLAIRE_MENSUELLE_HISTORIQUE)
            _serie = repartir_economie_plafonnee(
                roi.get(_cle_ann), factures_mensuelles,
                cle=(CLE_SOLAIRE_MENSUELLE if _corrige
                     else CLE_SOLAIRE_MENSUELLE_HISTORIQUE))
            if _serie is not None:
                roi[_cle_mois] = _serie

    # ÉTIQUETAGE (motif Z2). La série est ancrée dans une facture réelle, mais
    # sa VARIATION d'un mois à l'autre n'est mesurée que lorsque le client a
    # donné douze points (douze factures) ou douze relevés kWh. Avec une seule
    # facture d'hiver — le cas courant — la consommation est répétée sur les
    # douze mois : le niveau est réel, la variation est une hypothèse. Le
    # document le DIT au lieu de laisser croire à douze mesures.
    _source_conso = roi.get("source_consommation")
    factures_mensuelles_estimation = bool(
        factures_source == "etude_horaire"
        and _source_conso in ("facture_hiver", "facture_hiver_ete"))
    return (_source_conso, factures_mensuelles, factures_mensuelles_estimation,
            factures_source, hypotheses_block, savings_method)
