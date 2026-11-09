# flake8: noqa  (sonde d'audit vérifie AMOT 4e contre-visite, rejouable par scripts/sonde.py — AMET93)
"""AMOT26 (jumeau oublié) : `generate_devis_premium.fnum` garde `int(round(float(v)))` (arrondi au PAIR) et c'est
lui qui imprime l'économie annuelle C&I du une-page (`_cartes_ci_onepage`, `ci/onepage.economie_ttc`), alors que la
couverture C&I (`ci/couverture.py` : `fmt(economies)`) passe par `theme.fmt` → `montants.fmt_dirhams` (HALF_UP).
Économie au centime servie par `economie_ci` (`round(.., 2)`) : 98 930,50 HT / 118 716,50 TTC.
Rendu pur, aucune écriture. Jamais contre la prod.

Réalignée le 05/11/2026 sur AMOT126 : `fnum` reste VOLONTAIREMENT inchangé (10 appelants intouchés) ; c'est
le une-page C&I qui ne l'emploie plus (`ci/onepage.py::argent` = `fmt_dirhams`, sauf devis avant le niveau 12).
La sonde juge donc l'IMPRIMÉ du une-page (vignette économie de `_cartes_ci_onepage` + « soit N MAD TTC » de
`economie_ttc`) contre la couverture (`theme.fmt`), et non plus `fnum` lui-même."""
SONDE = {"constat": "C-AMOT-VER4-040", "sha": "ecd7fcf406",
         "attendu": "une-page C&I : « 98 930 » et « soit 118 716 MAD TTC » (fnum, au pair) ; couverture/theme.fmt et fmt_dirhams : « 98 931 » / « 118 717 » — 1 dirham d'écart entre les deux PDF du même devis ; attendu sain : 98 931 / 118 717 partout",
         "modeles": ["ventes.Devis"]}


def sonde(ctx):
    import re
    from apps.ventes.quote_engine import generate_devis_premium as G
    from apps.ventes.quote_engine.ci import onepage as ci_onepage
    from apps.ventes.quote_engine.residential import theme
    from apps.ventes.quote_engine.montants import fmt_dirhams, poser_regles_origine
    eco, ttc = 98930.5, 118716.5
    chiffres = {'economie_annuelle_mad': eco, 'base_economie': 'HT',
                'economie_annuelle_ttc_mad': ttc, 'production_kwh_an': 150000}

    def plat(h):  # balises retirées, séparateurs de milliers recollés (espace, insécable, fine)
        t = re.sub(r'<[^>]+>', ' ', str(h))
        return re.sub(r'(?<=\d)[\s \xa0,.](?=\d{3}\b)', '', t)

    obs = {}
    poser_regles_origine(False)  # devis au niveau courant (>= 12) : les règles d'AMOT126
    imprime = []
    try:
        cellules = G._cartes_ci_onepage(chiffres)
        obs['onepage_cellules'] = plat(' | '.join(str(c[0]) + ' => ' + str(c[1]) for c in cellules))
        imprime.append(obs['onepage_cellules'])
    except Exception as exc:  # globals du legacy non posés : l'argent du une-page seul
        obs['onepage_cellules_erreur'] = repr(exc)
    obs['argent_eco_onepage'] = plat(ci_onepage.argent(eco, G.fnum))
    obs['economie_ttc_onepage'] = plat(ci_onepage.economie_ttc(chiffres, G.fnum, lambda k, **kw: k))
    imprime += [obs['argent_eco_onepage'], obs['economie_ttc_onepage']]
    obs['theme_fmt_eco'] = plat(theme.fmt(eco))
    obs['theme_fmt_ttc'] = plat(theme.fmt(ttc))
    obs['fmt_dirhams_eco'] = plat(fmt_dirhams(eco))
    obs['fnum_eco_inchange'] = G.fnum(eco)  # information : fnum n'est PAS l'objet d'AMOT126
    # Rendu d'hier (devis avant le niveau 12) : le une-page garde fnum — information seulement.
    poser_regles_origine(False, historique_0411=True)
    obs['argent_eco_historique'] = plat(ci_onepage.argent(eco, G.fnum))
    poser_regles_origine(False)
    print(obs)
    texte = ' | '.join(imprime)
    couverture_saine = '98931' in obs['theme_fmt_eco'] and '118717' in obs['theme_fmt_ttc']
    onepage_sain = ('98931' in texte and '118717' in texte
                    and '98930' not in texte and '118716' not in texte)
    repro = couverture_saine and not onepage_sain
    return {'repro': repro, **obs}
