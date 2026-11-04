# flake8: noqa  (sonde d'audit vérifie AMOT 4e contre-visite, rejouable par scripts/sonde.py — AMET93)
"""AMOT26 (jumeau oublié) : `generate_devis_premium.fnum` garde `int(round(float(v)))` (arrondi au PAIR) et c'est
lui qui imprime l'économie annuelle C&I du une-page (`_cartes_ci_onepage`, `ci/onepage.economie_ttc`), alors que la
couverture C&I (`ci/couverture.py` : `fmt(economies)`) passe par `theme.fmt` → `montants.fmt_dirhams` (HALF_UP).
Économie au centime servie par `economie_ci` (`round(.., 2)`) : 98 930,50 HT / 118 716,50 TTC.
Rendu pur, aucune écriture. Jamais contre la prod."""
SONDE = {"constat": "C-AMOT-VER4-040", "sha": "ecd7fcf406",
         "attendu": "une-page C&I : « 98 930 » et « soit 118 716 MAD TTC » (fnum, au pair) ; couverture/theme.fmt et fmt_dirhams : « 98 931 » / « 118 717 » — 1 dirham d'écart entre les deux PDF du même devis ; attendu sain : 98 931 / 118 717 partout",
         "modeles": ["ventes.Devis"]}


def sonde(ctx):
    import re
    from apps.ventes.quote_engine import generate_devis_premium as G
    from apps.ventes.quote_engine.ci import onepage as ci_onepage
    from apps.ventes.quote_engine.residential import theme
    from apps.ventes.quote_engine.montants import fmt_dirhams
    eco, ttc = 98930.5, 118716.5
    chiffres = {'economie_annuelle_mad': eco, 'base_economie': 'HT',
                'economie_annuelle_ttc_mad': ttc, 'production_kwh_an': 150000}
    obs = {}
    try:
        cellules = G._cartes_ci_onepage(chiffres)
        txt = ' | '.join(str(c[0]) + ' => ' + str(c[1]) for c in cellules)
        obs['onepage_cellules'] = re.sub(r'<[^>]+>', ' ', txt)
    except Exception as exc:  # globals du legacy non posés
        obs['onepage_cellules_erreur'] = repr(exc)
    obs['fnum_eco'] = G.fnum(eco)
    obs['fnum_ttc'] = G.fnum(ttc)
    obs['economie_ttc_onepage'] = re.sub(r'<[^>]+>', ' ', ci_onepage.economie_ttc(chiffres, G.fnum, lambda k, **kw: k))
    obs['theme_fmt_eco'] = theme.fmt(eco)
    obs['theme_fmt_ttc'] = theme.fmt(ttc)
    obs['fmt_dirhams_eco'] = fmt_dirhams(eco)
    print(obs)
    chiffre = lambda s: re.sub(r'\D', '', s)
    repro = (chiffre(obs['fnum_eco']) == '98930' and chiffre(obs['theme_fmt_eco']) == '98931'
             and chiffre(obs['fnum_ttc']) == '118716' and chiffre(obs['theme_fmt_ttc']) == '118717')
    return {'repro': repro, **obs}
