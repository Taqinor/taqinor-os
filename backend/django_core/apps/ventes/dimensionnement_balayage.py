"""Balayage des tailles — ``balayer_tailles`` et ses deux helpers privés
exclusifs (``_tranche_du_residuel``, ``_remplissage_rendu``).

RSIZ (27/10/2026) — DÉPLACEMENT PUR depuis ``apps/ventes/dimensionnement.py``
(fichier > 2 000 lignes, budget de croissance nul) : corps recopiés à
l'identique, aucun chiffre ne bouge. ``dimensionnement.py`` ré-exporte
``balayer_tailles`` : tout importeur reste identique. Les noms restés dans
``dimensionnement.py`` (constantes, ``_num``, ``_payback``,
``choisir_recommandation``…) sont importés À L'APPEL — anti-cycle, et un
``mock.patch('apps.ventes.dimensionnement.X')`` continue d'agir.

LOGGER : même nom que celui de ``dimensionnement.py``
(``apps.ventes.dimensionnement``) — un déplacement pur ne change pas le nom
sous lequel une ligne de journal est émise.
"""
from __future__ import annotations

import logging

from apps.ventes.balayage_adaptatif import monter_champ_ve, tableau_adaptatif

logger = logging.getLogger("apps.ventes.dimensionnement")


def _tranche_du_residuel(residuel_kwh_mois, tranches):
    """La tranche du barème où retombe un résiduel — LUE, jamais réécrite ici."""
    from apps.ventes.quote_engine import bareme
    return bareme.tranche_du_kwh_mensuel(residuel_kwh_mois, tranches=tranches)


def _remplissage_rendu(palier_energie):
    """Le bloc ``remplissage`` d'un palier — chargé/capacité, et le PIRE mois.

    C'est la colonne qui rend la règle fondateur du 24/08 LISIBLE : « le
    stockage avec des batteries toujours pleines..... pas rajouter du stockage
    pour ne pas le charger ». Un ratio de 1,0 dit que la banque se remplit
    entièrement ce mois-là ; 0,62 dit qu'elle passe janvier aux deux tiers.
    """
    return {
        'moyen': palier_energie['remplissage_moyen'],
        'pire_mois': palier_energie['remplissage_pire_mois'],
    }


def balayer_tailles(*, company, conso_kwh_mensuelles, tranches,
                    charges_fixes_mad, ville=None, lat=None,
                    lon=None, occupation=None, equipements=None, phase=None,
                    taux_tva=None, gamme_nom_devis=None,
                    structure_type='acier', structure_produit_id=None,
                    min_panneaux=None,
                    max_panneaux=None, source_conso=None,
                    cible_falaise_kwh_mois=None, jour_reference=None,
                    hors_reseau=False, mppt_paires=1, perte_ombrage_pct=None,
                    regles_2710=True):
    """Le TABLEAU complet : une ligne par taille candidate, DEUX dimensions.

    ``tranches`` / ``charges_fixes_mad`` sont KEYWORD-REQUIS (QJR46). Ils
    portaient un défaut ``None`` (grille nationale) que TOUS les appelants
    laissaient jouer, pendant qu'``etude_horaire_pour_devis`` et
    ``quote_engine/builder`` appliquaient la surcharge de la société : le
    dimensionnement et le devis valorisaient le MÊME kWh sur deux barèmes, et
    le choix était invisible au site d'appel puisque les kwargs étaient OMIS
    plutôt que refusés. Passer explicitement ``tranches=None,
    charges_fixes_mad=None`` reste possible — c'est alors un choix ÉCRIT.

    Pour chaque taille (granularité = UN panneau du catalogue) :

    1. compose le kit RÉEL via ``services.composition_residentielle`` — donc
       avec la règle des 80 % du fondateur, le raccordement du client et les
       verdicts PVCOMPAT — SANS batterie ;
    2. calcule les économies par le MOTEUR HORAIRE (jamais un forfait) ;
    3. **DIM2 — puis BALAIE LE STOCKAGE** : au lieu d'UNE variante « avec
       batterie » dictée par les kWc, il évalue une ÉCHELLE de capacités du
       catalogue et retient la meilleure par payback.

    LA RÈGLE QUI BORNE LE STOCKAGE (fondateur, 24/08/2026) : « le stockage avec
    des batteries toujours pleines..... pas rajouter du stockage pour ne pas le
    charger ». Un palier n'est CANDIDAT que si sa capacité utile tient dans le
    surplus quotidien du MOIS LE PLUS FAIBLE — sinon on vendrait des kWh de
    batterie qui dorment en janvier. Conséquence VOULUE : le champ et le
    stockage montent ENSEMBLE, et une grosse banque derrière un petit champ est
    REFUSÉE, avec son taux de remplissage affiché pour que le refus se lise.

    Renvoie une liste de dicts ordonnée par taille croissante. Une taille dont
    la composition est impossible (catalogue incomplet) porte
    ``composable=False`` + ses avertissements : elle reste VISIBLE dans le
    tableau — on montre le trou, on ne le cache pas.
    """
    # RSIZ (27/10/2026) — DÉPLACEMENT PUR : les noms restés dans
    # ``apps.ventes.dimensionnement`` sont lus à l'APPEL (import local : aucun
    # cycle, et un ``mock.patch`` de l'ancien module agit comme avant).
    from apps.ventes.dimensionnement import (
        MAX_PALIERS_STOCKAGE,
        MAX_PANNEAUX_BALAYAGE,
        RATIO_ONDULEUR_MIN,
        TOLERANCE_CAPACITE_KWH,
        _arrondi,
        _kwh_txt,
        _lire_composition,
        _meilleur_palier,
        _num,
        _payback,
        _ratio_onduleur,
        _taux_sans_devis,
        bornes_candidates,
        choisir_recommandation,
        choisir_recommandation_avec,
        paliers_stockage_candidats,
        residuel_minimal,
        verdict_bloquant,
    )
    from apps.parametres.pvgis_profils import productible_mensuel
    from apps.ventes.etude_horaire import (
        balayer_stockage_horaire,
        calculer_etude_horaire,
    )
    from apps.ventes.horaire.ve_nocturne import (
        equipements_sans_recharge_ve_nocturne,
        plancher_batterie_recharge_ve,
        recharge_ve_nocturne_kwh_jour,
    )
    from apps.ventes.horaire.batterie_lignes import (
        # L-DECH — SOURCE UNIQUE : l'étude d'un devis et ce balayage lisent la
        # MÊME lecture de fiches, jamais deux implémentations parallèles.
        puissances_batterie_des_lignes,
    )
    from apps.ventes.domain.etape_composer import (
        ContexteSonde,
        composer_sonde,
        reglages_de_composition,
        sonder_wattage,
    )

    mensuel = productible_mensuel(ville=ville, lat=lat, lon=lon)
    if not mensuel:
        return []
    productibles, _source = mensuel
    productible_annuel = sum(_num(v) for v in productibles)

    conso_annuelle = sum(_num(v) for v in (conso_kwh_mensuelles or ()))
    if conso_annuelle <= 0:
        return []

    # QJR605 — Catalogue et réglages lus UNE fois pour tout le balayage, puis
    # CHAQUE taille composée par ``pipeline.composer_sonde`` — le même
    # constructeur que le devis (gamme, phase, MPPT, TVA, hors-réseau,
    # structure), jamais un appel direct qui en oublierait un.
    import dataclasses
    sonde_ctx = ContexteSonde(
        company=company,
        reglages=reglages_de_composition(company, gamme_nom_devis),
        gamme_nom_devis=gamme_nom_devis,
        structure_type=structure_type,
        structure_produit_id=structure_produit_id,
        phase=phase, mppt_paires=mppt_paires or 1,
        taux_tva=_taux_sans_devis(taux_tva, company),
        hors_reseau=bool(hors_reseau),
        # RSIZ2/3/5 — un devis existant aux règles < 3 garde ses règles.
        regles_2710=bool(regles_2710))

    # Watt du panneau RÉELLEMENT retenu par le catalogue — LA sonde partagée
    # avec l'échelle de paliers et les cartes de taille. Le jour où le
    # catalogue change de panneau, la granularité du balayage suit toute seule.
    panel_watt = _num(sonder_wattage(sonde_ctx))
    if panel_watt <= 0:
        return []
    sonde_ctx = dataclasses.replace(sonde_ctx, panel_watt=panel_watt)

    # AMOT30 — LE constructeur unique des arguments du moteur horaire.
    # QJR45 — LA DATE EST UNE ENTRÉE, PAS L'HORLOGE. Le même jour de
    # référence sert l'étude SANS batterie et le mini-balayage du
    # stockage : deux dates différentes dans un même tableau feraient
    # comparer deux Ramadans.
    # RSIZ7 — + ombrage du calepinage (``None`` = lead : rien ne bouge).
    from apps.ventes.domain.entrees import kwargs_moteur_ombre
    etude_kwargs = kwargs_moteur_ombre({
        'conso_kwh_mensuelles': conso_kwh_mensuelles, 'ville': ville,
        'lat': lat, 'lon': lon, 'occupation': occupation,
        'equipements': equipements, 'tranches': tranches,
        'charges_fixes_mad': charges_fixes_mad,
        'jour_reference': jour_reference,
        'perte_ombrage_pct': perte_ombrage_pct,
    })

    # QJR612 — CAD170 RÉELLEMENT APPLIQUÉ (décision fondateur 30/09/2026 :
    # « add more panels so battery is always charged »). Une recharge VE
    # NOCTURNE impose un PLANCHER au stockage retenu : base = l'optimum du même
    # lead SANS la couche VE nocturne (pas de double compte) + la recharge.
    # Le plancher ne fait que RETIRER des candidats sous lui : la règle
    # « batteries toujours pleines » ci-dessous reste le seul juge du
    # remplissage, si bien qu'une banque relevée n'existe qu'aux tailles de
    # champ qui la remplissent — la grille champ × stockage
    # (``choisir_recommandation_avec``) TIRE alors les panneaux nécessaires.
    # Sans recharge nocturne : ``None``, rien ne change à l'octet près.
    etude_kwargs_sans_ve = None
    if recharge_ve_nocturne_kwh_jour(equipements) > 0:
        etude_kwargs_sans_ve = dict(
            etude_kwargs,
            equipements=equipements_sans_recharge_ve_nocturne(equipements))
    # REPLI (jamais silencieux) : si AUCUNE taille balayée ne remplit le
    # plancher, on retient à chaque taille la PLUS GRANDE banque qui s'y remplit
    # encore, marquée ``plafonne`` — jamais une batterie qui ne se charge pas.
    etat_plancher = {'repli': False, 'candidats_vus': False}

    def _composer(panneaux, kwc, avec_batterie, cible_kwh, journal):
        """Une composition catalogue, ou ``None`` — jamais une exception."""
        try:
            return composer_sonde(
                sonde_ctx, panneaux, avec_batterie=avec_batterie,
                cible_kwh=cible_kwh, avertissements=journal)
        except Exception:  # noqa: BLE001 — une taille impossible ne stoppe rien (D-ENF22-BLE001)
            logger.warning('composition impossible à %s panneaux', panneaux,
                           exc_info=True)
            return None

    cache = {}

    def evaluer(panneaux):
        """La LIGNE du tableau pour cette taille — mémoïsée.

        La mémoïsation n'est pas un détail de performance : ``bornes_candidates``
        SONDE des tailles au-delà de la parité pour savoir jusqu'où étendre le
        balayage, et le tableau final les réévaluerait toutes une seconde fois.
        """
        if panneaux in cache:
            return cache[panneaux]
        cache[panneaux] = ligne = _evaluer_taille(panneaux)
        return ligne

    def _evaluer_taille(panneaux):
        kwc = panneaux * panel_watt / 1000.0

        # ── 1. La variante SANS batterie : elle décide de la composabilité ──
        avert_sans = []
        lignes_sans = _composer(panneaux, kwc, False, None, avert_sans)
        composable = lignes_sans is not None
        if not composable:
            avert_sans.append('composition impossible à %d panneaux' % panneaux)
        vue_sans = (_lire_composition(lignes_sans, taux_tva, company)
                    if composable else {})

        # ── 2. La SONDE « avec batterie » : verdicts électriques + vivier ──
        # LES DEUX VARIANTES ONT LEURS PROPRES VERDICTS, ET IL FAUT LES GARDER
        # SÉPARÉS. Cas réel du catalogue (trou documenté n° 2) : le panneau
        # 710 Wc passe avec l'onduleur RÉSEAU 5 kW (réserve d'écrêtage) mais
        # est HORS SPÉCIFICATION avec l'HYBRIDE 5 kW (Isc 18,6 A > 17,0 A). Un
        # sac d'avertissements commun ferait rejeter une taille dont l'option
        # réseau est parfaitement saine — ou pire, laisserait vendre une option
        # batterie impossible.
        avert_avec = []
        sonde_batterie = _composer(panneaux, kwc, True, None, avert_avec)
        if sonde_batterie is None:
            avert_avec.append('composition impossible à %d panneaux' % panneaux)
        capacites_vivier = list(
            getattr(sonde_batterie, 'capacites_batterie_vivier', ()) or ())

        bloquants_sans = [a for a in avert_sans if verdict_bloquant(a)]
        bloquants_avec = [a for a in avert_avec if verdict_bloquant(a)]

        # ── 3. L'étude SANS batterie — les colonnes de base de la ligne ──
        etude = calculer_etude_horaire(
            kwc=kwc, batterie_kwh_utile=0, source_conso=source_conso,
            **etude_kwargs)
        if etude is None:
            return None
        annuel = etude['annuel']

        cout_sans = vue_sans.get('cout_ttc') or 0.0
        eco_sans = annuel['economie_sans_mad']
        residuel_sans = round(annuel['import_sans_kwh'] / 12.0, 2)

        # ── 4. DIM2 — LE MINI-BALAYAGE DU STOCKAGE ──
        # L'option batterie N'EXISTE PAS quand son couple est hors spec : on ne
        # chiffre pas une installation que l'électricité interdit (règle L1,
        # « refuser l'impossible »).
        paliers = []
        palier_refuse = None
        stockage = None
        stockage_tronque = False
        avert_stockage = []
        plancher_ve = None
        if sonde_batterie is not None and not bloquants_avec:
            (paliers, palier_refuse, stockage, stockage_tronque,
             avert_stockage, plancher_ve) = _balayer_stockage_de_la_taille(
                panneaux, kwc, capacites_vivier, eco_sans)
        if etude_kwargs_sans_ve is not None and plancher_ve is None:
            # Stockage non évalué à cette taille : le plancher reste NOMMÉ,
            # sans aucune taille inventée.
            plancher_ve = plancher_batterie_recharge_ve(0.0, equipements, ())

        meilleur = _meilleur_palier(paliers)
        batterie_disponible = meilleur is not None

        onduleur = vue_sans.get('onduleur_kw')
        ratio = _ratio_onduleur(onduleur, kwc)

        avertissements = list(avert_sans)
        for message in list(avert_avec) + list(avert_stockage):
            if message not in avertissements:
                avertissements.append(message)

        residuel_retenu = (meilleur['residuel_kwh_mois'] if batterie_disponible
                           else residuel_sans)
        ligne = {
            'panneaux': panneaux,
            'panel_watt': round(panel_watt, 1),
            'kwc': round(kwc, 3),
            'composable': composable,
            'production_annuelle_kwh': annuel['production_kwh'],
            'consommation_annuelle_kwh': annuel['consommation_kwh'],
            'taux_autoconso_sans': annuel['taux_autoconso_sans'],
            'taux_autoconso_avec': (meilleur['taux_autoconso']
                                    if batterie_disponible else None),
            'couverture_sans': annuel['couverture_sans'],
            'couverture_avec': (meilleur['couverture']
                                if batterie_disponible else None),
            'economie_sans_mad': eco_sans,
            'economie_avec_mad': (meilleur['economie_mad']
                                  if batterie_disponible else None),
            'cout_sans_ttc': cout_sans,
            'cout_avec_ttc': (meilleur['cout_ttc'] if batterie_disponible
                              else None),
            'payback_sans_annees': _arrondi(_payback(cout_sans, eco_sans)),
            'payback_avec_annees': (meilleur['payback_annees']
                                    if batterie_disponible else None),
            'batterie_disponible': batterie_disponible,
            'batterie_kwh': (meilleur['capacite_kwh'] if batterie_disponible
                             else 0.0),
            # ── DIM2 — LA FALAISE, RENDUE VISIBLE ──
            'residuel_sans_kwh_mois': residuel_sans,
            'tranche_apres_sans': _tranche_du_residuel(residuel_sans, tranches),
            'residuel_avec_kwh_mois': (meilleur['residuel_kwh_mois']
                                       if batterie_disponible else None),
            'tranche_apres_avec': (meilleur['tranche_apres']
                                   if batterie_disponible else None),
            'residuel_kwh_mois': residuel_retenu,
            'tranche_apres': _tranche_du_residuel(residuel_retenu, tranches),
            # ── DIM2 — LE MINI-BALAYAGE, ET SON REFUS ──
            'balayage_stockage': paliers,
            'stockage_refuse': palier_refuse,
            'stockage_plafond_kwh': (stockage or {}).get('plafond_stockage_kwh'),
            'stockage_plafond_motif': (stockage or {}).get('plafond_motif'),
            'stockage_surplus_jour_min_kwh': (
                (stockage or {}).get('surplus_jour_min_kwh')),
            'stockage_surplus_jour_min_mois': (
                (stockage or {}).get('surplus_jour_min_mois')),
            'stockage_tronque': stockage_tronque,
            'remplissage': (meilleur['remplissage'] if batterie_disponible
                            else None),
            'avertissements_sans': list(avert_sans),
            'avertissements_avec': list(avert_avec) + list(avert_stockage),
            'verdicts_bloquants_sans': bloquants_sans,
            'verdicts_bloquants_avec': bloquants_avec,
            'onduleur': vue_sans.get('onduleur'),
            'onduleur_kw': onduleur,
            'onduleur_kw_unitaire': vue_sans.get('onduleur_kw_unitaire'),
            'onduleur_quantite': vue_sans.get('onduleur_quantite'),
            'onduleur_triphase': vue_sans.get('onduleur_triphase'),
            'ratio_onduleur_kwc': round(ratio, 3) if ratio else None,
            'regle_80_pct_respectee': (
                bool(ratio is not None and ratio >= RATIO_ONDULEUR_MIN)),
            'avertissements': avertissements,
            'lignes_sans': vue_sans.get('lignes', []),
            'lignes_avec': (meilleur['lignes'] if batterie_disponible else []),
        }
        if plancher_ve is not None:
            # QJR612 — clé ADDITIVE, posée seulement sur un lead à recharge
            # VE nocturne : un lead sans VE garde la forme d'hier à l'octet.
            ligne['plancher_recharge_ve'] = plancher_ve
        return ligne

    def _balayer_stockage_de_la_taille(panneaux, kwc, capacites_vivier,
                                       eco_sans):
        """(paliers retenus, palier refusé, bloc moteur, tronqué,
        avertissements, plancher VE nocturne ou ``None``)."""
        cibles = paliers_stockage_candidats(capacites_vivier)
        if not cibles:
            return [], None, None, False, [], None

        # Chaque cible NOMINALE du catalogue est COMPOSÉE pour de vrai : c'est
        # la composition qui dit le prix ET la capacité UTILE réellement
        # livrée (fiche technique), jamais l'étiquette du produit.
        compositions = []
        vues = {}
        # L-DECH — LES BORNES DE PUISSANCE, PALIER PAR PALIER. Chaque cible est
        # une composition DIFFÉRENTE (15 kWh = trois modules de 5 — une banque
        # est toujours HOMOGÈNE, fondateur 26/08/2026 ; 20 kWh = deux 10) :
        # la décharge disponible s'additionne avec les packs, et le port
        # batterie de l'onduleur la re-borne. Lues par la MÊME fonction que
        # l'étude complète (``puissances_batterie_des_lignes``) sur les lignes
        # RÉELLES de cette composition — jamais une valeur moyenne recopiée
        # d'un palier à l'autre. C'est le câblage qui manquait : ce balayage
        # appelait le moteur SANS aucune borne, si bien que l'écran de
        # dimensionnement créditait le stockage d'une puissance que l'étude du
        # même devis lui refusait.
        bornes_par_capacite = {}
        for cible in cibles:
            journal = []
            lignes = _composer(panneaux, kwc, True, cible, journal)
            if lignes is None:
                continue
            vue = _lire_composition(lignes, taux_tva, company)
            capacite = _num(vue.get('batterie_kwh'))
            if capacite <= 0 or capacite in vues:
                continue
            vues[capacite] = (cible, vue)
            compositions.append(capacite)
            puissances = puissances_batterie_des_lignes(
                lignes, roles=getattr(lignes, 'roles', None))
            bornes_par_capacite[round(capacite, 3)] = {
                'decharge_kw': puissances['packs_decharge_kw'],
                'decharge_onduleur_kw': puissances['ond_decharge_kw'],
                'charge_kw': puissances['charge_kw'],
            }
        if not compositions:
            return [], None, None, False, [], None

        energie = balayer_stockage_horaire(
            kwc=kwc, capacites_kwh=compositions,
            puissances_par_capacite=bornes_par_capacite, **etude_kwargs)
        if energie is None:
            return [], None, None, False, [], None

        # QJR612 — le plancher VE nocturne de CETTE taille (``None`` sans
        # recharge nocturne : chemin d'hier, inchangé).
        plancher = None
        seuil = 0.0
        if etude_kwargs_sans_ve is not None:
            plancher = _plancher_ve_de_la_taille(
                kwc, compositions, vues, bornes_par_capacite)
            seuil = _num((plancher or {}).get('taille_retenue_kwh'))

        retenus, refuse, tronque = _retenir_paliers(
            energie, compositions, vues, eco_sans, seuil)

        if plancher is not None:
            candidats = retenus
            if candidats:
                etat_plancher['candidats_vus'] = True
            retenus = [p for p in candidats
                       if p['capacite_kwh'] + TOLERANCE_CAPACITE_KWH >= seuil]
            if etat_plancher['repli'] and candidats:
                # REPLI : aucune taille du balayage ne remplit le plancher —
                # la PLUS GRANDE banque qui se remplit encore ici, nommée.
                plus_grande = max(candidats, key=lambda p: p['capacite_kwh'])
                retenus = [plus_grande]
                plancher = dict(plancher, plafonne=True, motif=(
                    'plancher de %s kWh (recharge VE nocturne comprise) '
                    'qu\'aucune taille de champ balayée ne remplit chaque '
                    'jour : on retient la plus grande banque qui se remplit '
                    'encore (%s kWh) — jamais une batterie qui ne se charge '
                    'pas.' % (_kwh_txt(seuil),
                              _kwh_txt(plus_grande['capacite_kwh']))))

        avertissements = []
        if tronque:
            avertissements.append(
                'Balayage du stockage tronqué à %d paliers à %d panneaux : le '
                'plafond physique (%.1f kWh) autorise davantage — augmenter '
                'MAX_PALIERS_STOCKAGE pour voir la suite.'
                % (MAX_PALIERS_STOCKAGE, panneaux,
                   _num(energie['plafond_stockage_kwh'])))
        return retenus, refuse, energie, tronque, avertissements, plancher

    def _plancher_ve_de_la_taille(kwc, compositions, vues, bornes):
        """Le plancher VE nocturne à CE champ : base = l'optimum (meilleur
        payback, batteries toujours pleines) du même lead SANS la couche VE
        nocturne, sur les MÊMES compositions réelles — puis + la recharge."""
        base = 0.0
        etude_nv = calculer_etude_horaire(
            kwc=kwc, batterie_kwh_utile=0, source_conso=source_conso,
            **etude_kwargs_sans_ve)
        energie_nv = balayer_stockage_horaire(
            kwc=kwc, capacites_kwh=compositions,
            puissances_par_capacite=bornes, **etude_kwargs_sans_ve)
        if etude_nv is not None and energie_nv is not None:
            retenus_nv, _refuse, _tronque = _retenir_paliers(
                energie_nv, compositions, vues,
                etude_nv['annuel']['economie_sans_mad'], 0.0)
            meilleur_nv = _meilleur_palier(retenus_nv)
            if meilleur_nv is not None:
                base = _num(meilleur_nv['capacite_kwh'])
        return plancher_batterie_recharge_ve(base, equipements, compositions)

    def _retenir_paliers(energie, compositions, vues, eco_sans, seuil):
        """(paliers retenus, palier refusé, tronqué) — la règle « batteries
        toujours pleines » appliquée palier par palier.

        ``seuil`` (QJR612) : sous le plancher VE nocturne, la coupe à marginal
        nul ne s'applique pas encore — on monte jusqu'au plancher, TANT QUE la
        banque se remplit. ``0.0`` ⇒ comportement d'hier."""
        par_capacite = {p['capacite_kwh']: p for p in energie['paliers']}
        retenus = []
        refuse = None
        precedente = eco_sans
        tronque = False
        for capacite in sorted(compositions):
            brut = par_capacite.get(round(capacite, 2))
            if brut is None:
                continue
            cible, vue = vues[capacite]
            palier = _palier_rendu(cible, capacite, vue, brut, precedente)
            # RÈGLE FONDATEUR — « batteries toujours pleines » : un palier qui
            # ne se remplit pas tous les jours n'est pas un candidat. Le
            # PREMIER refusé est CONSERVÉ comme preuve lisible du refus.
            if not brut['se_remplit_tous_les_jours']:
                if refuse is None:
                    palier['motif_refus'] = (
                        '%s kWh refusé : capacité utile %.2f kWh au-dessus du '
                        'plafond de remplissage %.2f kWh (le surplus quotidien '
                        'du mois %s, le plus faible de l\'année) — la batterie '
                        'n\'y serait chargée qu\'à %.1f %%, et on n\'ajoute pas '
                        'du stockage qu\'on ne charge pas.'
                        % (_kwh_txt(capacite), capacite,
                           _num(energie['plafond_remplissage_kwh']),
                           energie['surplus_jour_min_mois'],
                           _num(brut['remplissage_pire_mois'].get('ratio')) * 100))
                    refuse = palier
                break
            if len(retenus) >= MAX_PALIERS_STOCKAGE:
                tronque = True
                break
            retenus.append(palier)
            # COUPE À MARGINAL NUL : le palier qui n'apporte plus un dirham est
            # GARDÉ (il PROUVE le retournement, comme le panneau de marge de
            # ``bornes_candidates``), mais on n'explore pas au-delà — sauf sous
            # le plancher VE nocturne (QJR612), qu'on doit encore atteindre.
            if (palier['economie_marginale_mad'] <= 0
                    and palier['capacite_kwh'] + TOLERANCE_CAPACITE_KWH
                    >= seuil):
                break
            precedente = brut['economie_mad']
        return retenus, refuse, tronque

    def _palier_rendu(cible, capacite, vue, brut, economie_precedente):
        cout = _num(vue.get('cout_ttc'))
        economie = brut['economie_mad']
        return {
            'capacite_kwh': round(capacite, 2),
            'capacite_cible_kwh': cible,
            'cout_ttc': round(cout, 2),
            'economie_mad': economie,
            'economie_marginale_mad': round(
                economie - _num(economie_precedente), 2),
            'payback_annees': _arrondi(_payback(cout, economie)),
            'residuel_kwh_mois': brut['residuel_kwh_mois'],
            'tranche_apres': _tranche_du_residuel(
                brut['residuel_kwh_mois'], tranches),
            'couverture': brut['couverture'],
            'taux_autoconso': brut['taux_autoconso'],
            'remplissage': _remplissage_rendu(brut),
            'lignes': vue.get('lignes', []),
            'lignes_batterie': [ligne for ligne in vue.get('lignes', [])
                                if ligne.get('role') == 'batterie'],
        }

    def sonder_residuel(panneaux):
        """Le PLUS BAS résiduel atteignable à cette taille — pour les bornes.

        « Avec le stockage MAX exploré », pas avec le stockage au meilleur
        payback : la question posée aux bornes est « cette taille peut-elle
        franchir la marche ? », donc on lui donne toutes ses chances.
        """
        if panneaux > MAX_PANNEAUX_BALAYAGE:
            return None
        ligne = evaluer(panneaux)
        return None if ligne is None else residuel_minimal(ligne)

    borne_min, borne_max = bornes_candidates(
        conso_annuelle_kwh=conso_annuelle,
        productible_annuel_kwh_kwc=productible_annuel,
        panel_watt=panel_watt,
        cible_residuel_kwh_mois=cible_falaise_kwh_mois,
        sonde_residuel=sonder_residuel)
    if borne_max <= 0:
        return []
    debut = int(min_panneaux) if min_panneaux else borne_min
    fin = int(max_panneaux) if max_panneaux else borne_max
    debut = max(1, debut)
    fin = max(debut, fin)
    # GARDE-FOU (jamais silencieux) — voir MAX_PANNEAUX_BALAYAGE.
    plafond_atteint = fin > MAX_PANNEAUX_BALAYAGE
    if plafond_atteint:
        fin = max(debut, MAX_PANNEAUX_BALAYAGE)
        logger.warning(
            'balayage plafonné à %d panneaux (borne calculée : %d) — '
            'consommation probablement aberrante',
            MAX_PANNEAUX_BALAYAGE, borne_max)

    # 23/10/2026 — BALAYAGE ADAPTATIF (module ``balayage_adaptatif``) : dense
    # et byte-identique sous le seuil, grille grossière + raffinement au-delà ;
    # le marquage QJR411 d'un balayage tronqué y vit aussi.
    choisirs = (choisir_recommandation, choisir_recommandation_avec)
    tableau = tableau_adaptatif(evaluer, debut, fin, plafond_atteint, choisirs,
                                MAX_PANNEAUX_BALAYAGE)
    if (etude_kwargs_sans_ve is not None and etat_plancher['candidats_vus']
            and not plafond_atteint
            and not any(ligne.get('balayage_stockage') for ligne in tableau)):
        # QJR612 — « add more panels so battery is always charged » : le champ
        # monte au-delà de ``fin`` jusqu'à la première taille qui remplit la
        # banque relevée (``balayage_adaptatif.monter_champ_ve``). Jamais pour
        # un lead sans recharge nocturne (``etude_kwargs_sans_ve`` = ``None``).
        tableau = monter_champ_ve(
            evaluer, tableau, debut, fin, plafond_atteint, choisirs,
            MAX_PANNEAUX_BALAYAGE)
    if (etude_kwargs_sans_ve is not None and etat_plancher['candidats_vus']
            and not any(ligne.get('balayage_stockage') for ligne in tableau)):
        # QJR612 — REPLI : le plancher VE nocturne n'est rempli à AUCUNE taille
        # balayée. Plutôt que de perdre toute option batterie, chaque taille
        # retient la plus grande banque qui s'y remplit encore (``plafonne``).
        etat_plancher['repli'] = True
        cache.clear()
        tableau = tableau_adaptatif(
            evaluer, debut, fin, plafond_atteint, choisirs,
            MAX_PANNEAUX_BALAYAGE)
    return tableau
