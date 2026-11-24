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
    classes = [(li, classer_produit(getattr(li.produit, 'nom', '') or li.designation) or '') for li in lignes]
    panneaux = [li for li, c in classes if c == 'panneau']
    onduleurs = [{'produit': li.produit_id, 'designation': li.designation, 'quantite': int(li.quantite)}
                 for li, c in classes if c.startswith('onduleur')]
    return panneaux, panneaux_et_watt_lu(panneaux), onduleurs


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


def valeurs(resultat, option, investissement, *, froid):
    """La table §2 de ``option`` ; ``froid`` : le froid du site lu UNE fois par
    ``calculer_conception`` (``compatibilites.froid_du_lead``)."""
    if resultat.marche == 'agricole':
        champ, params = resultat.etude_params.get('champ') or {}, resultat.etude_params
        return {'nb_panneaux': _v(champ.get('nb_panneaux'), 'panneaux'), 'puissance_kwc': _v(champ.get('kwc'), 'kWc'),
                'pompe': _v(resultat.materiel_pompage.get('pompe')),
                'variateur': _v(resultat.materiel_pompage.get('variateur_pompage')),
                'm3_jour': _v(params.get('m3_jour'), 'm³/jour')}
    from apps.ventes.quote_engine.lignes_classement import kwc_des_lignes
    from apps.ventes.quote_engine.pricing import payback_publiable
    panneaux, (nb, watt), onduleurs = _materiel(resultat, option)
    chaines, tension, ratio = _electrique(resultat.conception_electrique, onduleurs)
    production, mensuelle, autoconso, couverture, economies, conso, forme, source_forme = _bilan(resultat, option)
    payback = (payback_publiable(investissement, economies, stockage=option == 'avec')['payback_years']
               if investissement is not None else None)
    devis = resultat.lignes[0].devis if resultat.lignes else None
    return {
        'nb_panneaux': _v(nb, 'panneaux'), 'puissance_kwc': _v(kwc_des_lignes(panneaux, nb, watt, devis), 'kWc'),
        'module': _v(panneaux[0].designation if panneaux else None), 'onduleurs': _v(onduleurs),
        'nombre_onduleurs': _v(sum(o['quantite'] for o in onduleurs), 'onduleurs'),
        'chaines': _v(chaines, 'panneaux'), 'tension_froid': _v(tension, 'V'), 'ratio_dc_ac': _v(ratio),
        'temperature_froid': _v(getattr(froid, 'valeur_c', None), '°C',
                                'moteur' if getattr(froid, 'source', None) else 'defaut'),
        'production_annuelle': _v(production, 'kWh/an'), 'production_mensuelle': _v(mensuelle or None, 'kWh'),
        'autoconsommation': _v(autoconso, 'ratio'), 'couverture': _v(couverture, 'ratio'),
        'economies_annuelles': _v(economies, 'MAD/an'),
        'payback': _v(payback, 'ans', 'devis' if investissement is not None else 'moteur'),
        'consommation_annuelle': _v(conso, 'kWh/an'), 'forme_horaire': _v(forme, None, source_forme),
    }
