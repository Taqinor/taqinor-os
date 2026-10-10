SONDE = {"constat": "C-ACAL-VER-005", "sha": "5ea32b58b",
         "attendu": "pan B à module saisi (400 Wc, sans fiche) : chaîné avec Vmp/module 34 V ou alerte nommant le pan B"}


def sonde(ctx):
    from apps.calepinage.services.chaines import bloc_pose, concevoir_par_pan
    from apps.calepinage.services.electrique import temperatures_site
    F550 = {'vmp_v': 41.6, 'voc_v': 49.8, 'isc_a': 14.0, 'imp_a': 13.2, 'pmax_wc': 550.0,
            'temp_coeff_voc_pct_c': -0.27, 'temp_coeff_pmax_pct_c': -0.35}
    OND = {'n_mppt': 2, 'mppt_v_min': 150.0, 'mppt_v_max': 800.0, 'v_max_abs': 1000.0,
           'i_max_mppt_a': 26.0, 'ac_kw': 10.0, 'phases': 3}
    lay = {'version': 2,
           'modules': [{'id': 'm550', 'produitId': 1, 'pmaxWc': 550, 'libelle': 'M550', 'source': 'fiche'},
                       {'id': 'm400', 'produitId': None, 'pmaxWc': 400, 'libelle': 'M400 saisi', 'source': 'saisie atelier'}],
           'zones': [{'id': 'A', 'label': 'A', 'facingAzimuthDeg': 180.0, 'pitchDeg': 15.0, 'geometry': {'count': 10, 'moduleId': 'm550'}},
                     {'id': 'B', 'label': 'B', 'facingAzimuthDeg': 90.0, 'pitchDeg': 15.0, 'geometry': {'count': 10, 'moduleId': 'm400'}}]}
    c = concevoir_par_pan(lay, module_specs=F550, onduleur_specs=OND,
                          temperatures=temperatures_site(saisie={'temperature_min_c': -5.0, 'temperature_max_c': 70.0}),
                          module_designation='M550', onduleur_designation='Ond 10 kW')
    kwc_b = [p['kwc'] for p in bloc_pose(c)['pans'] if p['pan'] == 'B']
    vmp_b = sorted({round(ch.vmp_stc_v / ch.nb_modules, 2) for ch in c.chaines if ch.pan == 'B'})
    alerte = any('B' in a and '400' in a for a in c.alertes)
    print(f"pan B kWc {kwc_b} chaîné à Vmp/module {vmp_b}, alerte={alerte}")
    return {'repro': (41.6 in vmp_b) and not alerte}
