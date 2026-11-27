"""ADEV134 (relecture) — la table §2 de la conception, PAR OPTION.

Déplacée telle quelle de ``conception/moteur.py`` (budget du module) : chaque
valeur ``{valeur, unite, source}`` est LUE sur les blocs, les lignes et la
conception électrique du résultat — aucun calcul, aucune écriture.
"""


def _v(valeur, unite=None, source='moteur'):
    return {'valeur': valeur, 'unite': unite, 'source': source}


def options(resultat):
    """``(option retenue, options)`` : agricole ``sans`` ; sinon le scénario
    servable (« Les deux » ⇒ les deux) ; retenue = la recommandée (C&I), sinon
    l'option que décrit le bloc principal (``avec`` à deux options, I7)."""
    from apps.ventes.domain import scenario as S
    params = resultat.etude_params
    if resultat.marche == 'agricole':
        return 'sans', ('sans',)
    scenario = params.get('scenario')
    if scenario == S.SCENARIO_LES_DEUX:
        recommandee = params.get('recommended_option')
        return ('sans' if recommandee == S.SCENARIO_SANS_BATTERIE else 'avec'), ('sans', 'avec')
    option = 'avec' if scenario == S.SCENARIO_AVEC_BATTERIE else 'sans'
    return option, (option,)


def _materiel(resultat, option):
    from apps.ventes.domain.catalogue import classer_produit
    from apps.ventes.quote_engine.lignes_classement import panneaux_et_watt_lu
    lignes = [li for li in resultat.lignes if li.type_ligne == 'produit' and not li.optionnelle
              and (li.variante or '') in ('', option)]
    from apps.ventes.domain.classe_ligne import role_de_ligne  # rôle RANGÉ à l'écriture, puis le nom
    classes = [(li, role_de_ligne(li, lambda li=li: classer_produit(
        getattr(li.produit, 'nom', '') or li.designation)) or '') for li in lignes]
    panneaux = [li for li, c in classes if c == 'panneau']
    onduleurs = [{'produit': li.produit_id, 'designation': li.designation, 'quantite': int(li.quantite)}
                 for li, c in classes if c.startswith('onduleur')]
    batteries = [li.produit_id for li, c in classes if c == 'batterie' and li.produit_id]
    return panneaux, panneaux_et_watt_lu(panneaux), onduleurs, batteries


def _produits(panneaux, onduleurs, batteries):
    """Relecture E5 m4 — l'IDENTIFIANT produit du module, de l'onduleur et de la
    batterie de l'option (``None`` sans ligne) : le calepinage relit le produit par
    lui, jamais par son nom."""
    return {'module_produit': _v(panneaux[0].produit_id if panneaux else None),
            'onduleur_produit': _v(onduleurs[0]['produit'] if onduleurs else None),
            'batterie_produit': _v(batteries[0] if batteries else None)}


def _electrique(design, onduleurs):
    """Chaînes, tension à froid, ratio : seulement pour l'option dont la
    conception électrique rangée porte l'onduleur ; sinon ``None``."""
    onduleur = ((design or {}).get('materiel') or {}).get('onduleur') or {}
    if not design or onduleur.get('designation') not in {o['designation'] for o in onduleurs}:
        return None, None, None
    chaines = design.get('chaines') or []
    longueurs = [c.get('nb_modules') for c in chaines]
    return ({'nombre': len(chaines), 'longueurs': longueurs, 'longueur': max(longueurs, default=None)},
            max((c.get('voc_froid_v') or 0 for c in chaines), default=None), design.get('ratio_dc_ac'))


def _bilan(resultat, option):
    """``(production, mensuelle, autoconso, couverture, économies, conso,
    forme, source de la forme)`` lus sur le bloc de l'option."""
    params = resultat.etude_params
    if resultat.marche == 'residentiel':
        bloc = (params.get('etude_horaire_sans') if option == 'sans' else None) or params.get('etude_horaire') or {}
        annuel = bloc.get('annuel') or {}
        return (annuel.get('production_kwh'), [m.get('production_kwh') for m in bloc.get('mois') or []],
                annuel.get('taux_autoconso_%s' % option), annuel.get('couverture_%s' % option),
                annuel.get('economie_%s_mad' % option), annuel.get('consommation_kwh'),
                bloc.get('occupation'), 'defaut' if bloc.get('profil_suppose') else 'moteur')
    etude = params.get('etude_ci') or {}
    source = (etude.get('option_avec') or {}) if option == 'avec' else etude
    bilan, economie = source.get('bilan') or {}, source.get('economie_ci') or {}
    mois = bilan.get('par_mois') or []
    return (bilan.get('production_kwh'), [m.get('production_kwh') for m in mois], bilan.get('taux_autoconso'),
            bilan.get('taux_couverture'), (economie.get('economie_annee1') or {}).get('total_mad'),
            sum(m.get('consommation_kwh') or 0 for m in mois) if mois else None,
            (etude.get('profil_charge') or {}).get('archetype'), 'moteur')


def _source_de_la_production(resultat, option):
    """Relecture E6 M1 — la source de la production de ``option`` : ``pose`` quand l'étude a
    tourné sur la base de LA pose (``horaire/productible_pose.SOURCE_POSE``, publiée par le
    bloc), ``plan_par_defaut`` sur celle du plan par défaut d'un lead sans toit (ADEV155,
    niveau 15 seulement : ``SOURCE_PLAN_PAR_DEFAUT``), sinon ``moteur``."""
    from apps.ventes.horaire.productible_pose import SOURCE_PLAN_PAR_DEFAUT, SOURCE_POSE

    servies = {SOURCE_POSE: 'pose', SOURCE_PLAN_PAR_DEFAUT: 'plan_par_defaut'}
    params = resultat.etude_params
    if resultat.marche == 'residentiel':
        bloc = (params.get('etude_horaire_sans') if option == 'sans' else None) or params.get('etude_horaire') or {}
        return servies.get((bloc.get('base_production') or {}).get('source'), 'moteur')
    etude = params.get('etude_ci') or {}
    source = (etude.get('option_avec') or {}) if option == 'avec' else etude
    return next((servies[h['source']] for h in (source.get('hypotheses') or etude.get('hypotheses') or [])
                 if isinstance(h, dict) and h.get('source') in servies), 'moteur')


def _payback(resultat, option, investissement, economie, company):
    """E7d (revue lot 4, M1) — le payback de ``option`` sur ``investissement`` (MAD TTC de
    vente, ``None`` ⇒ ``None``), par LA fonction du payback servi à la lecture
    (``selectors_conception._payback_servi``) : ``payback_publiable``, provision d'onduleur
    des cartes (``offres_tailles._cout_onduleur_ttc``) sur les lignes de l'option du moteur,
    part stockée 0 au modèle horaire résidentiel. Aucun prix d'achat lu."""
    if investissement is None:
        return None, {}
    from apps.ventes import offres_tailles
    from apps.ventes.domain.catalogue import classer_produit
    from apps.ventes.quote_engine.pricing import payback_publiable
    from apps.ventes.utils.options import AVEC_BATTERIE, SANS_BATTERIE, filter_lines_for_option

    devis = resultat.lignes[0].devis if resultat.lignes else None
    lignes = list(resultat.lignes)
    if len(options(resultat)[1]) > 1:
        lignes = filter_lines_for_option(lignes, AVEC_BATTERIE if option == 'avec' else SANS_BATTERIE, devis=devis)
    portees = [li for li in lignes if li.type_ligne == 'produit']
    remise = float(getattr(devis, 'remise_globale', 0) or 0)
    cout = offres_tailles._cout_onduleur_ttc(
        portees, [classer_produit(getattr(li.produit, 'nom', '') or li.designation) for li in portees],
        1 - remise / 100, getattr(devis, 'taux_tva', None), company, devis)
    horaire = {'part_batterie': 0} if resultat.marche == 'residentiel' else {}
    annees = payback_publiable(investissement, economie, stockage=option == 'avec', cout_onduleur_ttc=cout,
                               **horaire)['payback_years']
    # T4-X9-016 — les entrées servies à côté, comme le payback servi à la lecture.
    return annees, entrees_du_payback(investissement, economie, cout,
                                      stockage=option == 'avec' and resultat.marche != 'residentiel')


def entrees_du_payback(investissement, economie, cout_onduleur, *, stockage):
    """T4-X9-016 — ce que le payback servi a pris, servi À CÔTÉ de lui (même option) : le
    montant TTC de l'option, son économie annuelle, la provision d'onduleur, et la phrase du
    calcul (``quote_engine/pricing.compute_cashflow_payback`` : un cumul, jamais un quotient)."""
    from core.money import quantize_mad

    from apps.ventes.quote_engine import pricing

    morceaux = ['production en baisse de %s %%/an' % _pct(pricing.PANEL_DEGRADATION)]
    if pricing.TARIFF_ESCALATION:
        morceaux.append('tarif en hausse de %s %%/an' % _pct(pricing.TARIFF_ESCALATION))
    if stockage:
        morceaux.append('part stockée au rendement de la batterie (%s %%)' % _pct(pricing.BATTERY_ROUNDTRIP))
    if cout_onduleur:
        morceaux.append('onduleur remplacé la %de année' % pricing.INVERTER_REPLACE_YEAR)
    montant = float(quantize_mad(investissement)) if investissement else None
    # T4-X6-006 — ``investissement`` + ``base`` : le montant du calcul et SA base (TTC ici ;
    # HT pour un C&I à TVA récupérable, ``selectors_conception._entrees_flux_ci``).
    return {'investissement': montant, 'base': 'TTC', 'investissement_ttc': montant,
            'economie_annuelle': economie,
            'cout_onduleur_ttc': float(quantize_mad(cout_onduleur)) if cout_onduleur else None,
            'calcul': 'Cumul des économies sur %d ans (%s) jusqu’à couvrir le montant.' % (
                pricing.CASHFLOW_YEARS, ', '.join(morceaux))}


def _pct(fraction):
    return ('%g' % round(float(fraction) * 100, 2)).replace('.', ',')


def valeurs(resultat, option, investissement, *, froid, company=None):
    """La table §2 de ``option`` ; ``froid`` : le froid du site lu UNE fois par
    ``calculer_conception`` (``compatibilites.froid_du_lead``). ACAL2016 :
    ``verdicts`` = les verdicts électriques de l'option, jugés UNE fois ici par la
    règle existante (``porte_calepinage.verdicts_electriques``) et relus partout."""
    if resultat.marche == 'agricole':
        champ, params = resultat.etude_params.get('champ') or {}, resultat.etude_params
        return {'nb_panneaux': _v(champ.get('nb_panneaux'), 'panneaux'), 'puissance_kwc': _v(champ.get('kwc'), 'kWc'),
                'pompe': _v(resultat.materiel_pompage.get('pompe')),
                'variateur': _v(resultat.materiel_pompage.get('variateur_pompage')),
                'm3_jour': _v(params.get('m3_jour'), 'm³/jour')}
    from apps.ventes.quote_engine.lignes_classement import kwc_des_lignes
    panneaux, (nb, watt), onduleurs, batteries = _materiel(resultat, option)
    chaines, tension, ratio = _electrique(resultat.conception_electrique, onduleurs)
    production, mensuelle, autoconso, couverture, economies, conso, forme, source_forme = _bilan(resultat, option)
    source_production = _source_de_la_production(resultat, option)
    if isinstance(investissement, dict):  # E7d (M1) — l'aperçu : un prix par option
        investissement = investissement.get(option)
    payback, entrees_payback = _payback(resultat, option, investissement, economies, company)
    devis = resultat.lignes[0].devis if resultat.lignes else None
    kwc = kwc_des_lignes(panneaux, nb, watt, devis)
    return {
        'nb_panneaux': _v(nb, 'panneaux'), 'puissance_kwc': _v(kwc, 'kWc'),
        'module': _v(panneaux[0].designation if panneaux else None), 'onduleurs': _v(onduleurs),
        'nombre_onduleurs': _v(sum(o['quantite'] for o in onduleurs), 'onduleurs'),
        'chaines': _v(chaines, 'panneaux'), 'tension_froid': _v(tension, 'V'), 'ratio_dc_ac': _v(ratio),
        'temperature_froid': _v(getattr(froid, 'valeur_c', None), '°C',
                                'moteur' if getattr(froid, 'source', None) else 'defaut'),
        'production_annuelle': _v(production, 'kWh/an', source_production),
        'production_mensuelle': _v(mensuelle or None, 'kWh', source_production),
        'autoconsommation': _v(autoconso, 'ratio'), 'couverture': _v(couverture, 'ratio'),
        'economies_annuelles': _v(economies, 'MAD/an'),
        'payback': dict(_v(payback, 'ans', 'devis' if investissement is not None else 'moteur'), **entrees_payback),
        'consommation_annuelle': _v(conso, 'kWh/an'), 'forme_horaire': _v(forme, None, source_forme),
        # Reste d'ACAL2020 — la forme 24 h du moteur résidentiel (``None`` hors résidentiel).
        'forme_horaire_24': _v(resultat.forme_horaire_24 if resultat.marche == 'residentiel' else None,
                               'part', source_forme),
        **_produits(panneaux, onduleurs, batteries),
        'verdicts': _v(_verdicts(resultat, onduleurs, kwc, chaines, company)),
    }


#: Relecture E6 m2 — champ imposé → (clé ``*_produit`` comparée, valeurs dites ``impose``,
#: entrée nommée dans ``entrees_utilisees``, clé de la valeur qui porte le NOM du produit).
_IMPOSES = (('panneau_produit_id', 'module_produit', ('module', 'module_produit'), 'module_designe', 'module'),
            ('onduleur_produit_id', 'onduleur_produit', ('onduleurs', 'onduleur_produit'),
             'onduleur_designe', 'onduleurs'))


def dire_l_impose(resultat, provenance, *, pose_a_la_main=False):
    """Relecture E6 m2 — chaque valeur posée par un humain (``resultat.imposes_retenus`` :
    matériel désigné, compte d'une pose ajustée à la main) porte la source ``impose`` sur
    les options qui la portent, et l'entrée figure dans ``entrees_utilisees`` (le produit
    par son NOM ; ``provenance`` : ``calepinage`` ou ``saisie`` pour l'aperçu)."""
    imposes = resultat.imposes_retenus or {}
    for cle, produit, cles, entree, nom in _IMPOSES:
        try:
            pk = int(imposes.get(cle))
        except (TypeError, ValueError):
            continue
        portees = [v for v in resultat.valeurs.values() if (v.get(produit) or {}).get('valeur') == pk]
        for v in portees:
            for c in cles:
                v[c]['source'] = 'impose'
        if portees:
            lu = portees[0][nom]['valeur']
            resultat.entrees_utilisees[entree] = {
                'valeur': (lu[0].get('designation') if isinstance(lu, list) and lu else lu), 'source': provenance}
    nombre = imposes.get('nb_panneaux') if pose_a_la_main else None
    if nombre:
        for v in resultat.valeurs.values():
            if (v.get('nb_panneaux') or {}).get('valeur') == nombre:
                for c in ('nb_panneaux', 'puissance_kwc'):
                    v[c]['source'] = 'impose'
        resultat.entrees_utilisees['pose'] = {'valeur': nombre, 'source': provenance}


def _verdicts(resultat, onduleurs, kwc, chaines, company):
    """ACAL2016 — jugés pour l'option dont la conception électrique porte l'onduleur ;
    sinon les trois verdicts valent ``None`` et ``non_calcule`` DIT pourquoi (jamais un
    « conforme » muet) : la fiche à compléter, ou l'option que la conception sert."""
    from apps.ventes.conception.porte_calepinage import verdicts_electriques
    verdicts = verdicts_electriques(company, resultat.conception_electrique, onduleurs, kwc) if chaines else None
    if verdicts is not None:
        return dict(verdicts, non_calcule=None)
    if resultat.motifs_electriques or not resultat.conception_electrique:
        motif = ' ; '.join(resultat.motifs_electriques) or 'Conception électrique non calculée.'
    else:
        motif = "Conception électrique calculée pour l'autre option seulement (onduleur différent)."
    return {'ratio_dc_ac': None, 'capacite_hybride': None, 'longueur_chaine': None, 'non_calcule': motif}
