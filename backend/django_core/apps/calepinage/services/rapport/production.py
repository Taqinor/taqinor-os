"""CALX301 — la section « Production » du rapport : mensuel, PR, P50/P90.

Le constat
==========
La note de calcul n'imprime que 5 lignes annuelles
(``services/note_calcul.py:558-566``) alors que le résultat publie déjà le
mensuel et le détail par pan (``contract_samples/calepinage_resultat.json`` :
``production.mensuel[]`` avec ``mois``/``p50_kwh``, ``production.par_pan[]``
avec ``p50_kwh``, ``performance_ratio``, ``specific_yield_kwh_kwc``,
``shading_annual_loss_pct``) — et ``_construire_note_calcul`` COLLECTE
``par_pan`` (``:313``) sans jamais l'imprimer.

Ce que la section imprime — LU, jamais recalculé
==================================================
* une table 12 mois (``production.mensuel[]``, dans l'ordre SERVI) ;
* une table par pan (``production.par_pan[]``) ;
* le productible spécifique et le PR annuels (``production.total``) ;
* P50/P75/P90 (``production.total``) avec la variabilité interannuelle
  (``annual_variability``) et sa NATURE — mesurée sur N années ou hypothèse,
  le champ ``source`` de la composante ``variabilite_interannuelle`` du
  contrat d'incertitude (``resultat['incertitude']['composantes'][]``,
  CALX144) — jamais une nature devinée quand la composante manque ;
* une phrase qui dit que les quantiles ne valent QUE pour l'annuel (PVsyst :
  P50/P90 sont des valeurs de dépassement annuelles, jamais une garantie sur
  la durée de vie de l'installation).

Rien n'est inventé
===================
Une valeur absente imprime « — » (``nombre_tel_que_servi``), JAMAIS un 0 :
un ``p90_kwh`` non calculé n'est pas une production nulle.
"""
from __future__ import annotations

from decimal import Decimal
from html import escape

from . import nombre_tel_que_servi
from .champs_lisibles import motif_lisible

__all__ = ['CSS_SECTION', 'MENTION_QUANTILES_ANNUELS', 'MOTIF_PAR_DEFAUT',
           'html_de_section', 'mention_borne_haute',
           'texte_non_publie']

#: ACAL50 — le motif imprimé quand un résultat incomplet ne porte pas le sien
#: (jamais une valeur : « non publié » reste « non publié »).
MOTIF_PAR_DEFAUT = 'résultat incomplet'


def _resultat_incomplet(total):
    """ACAL50 / D-ACAL-7 — ``production.total.complete`` est-il FAUX ?

    La complétude est LUE (publiée par la simulation, ACAL49), jamais
    recalculée ici ; une clé absente (résultat antérieur) n'est pas un
    résultat incomplet.
    """
    return isinstance(total, dict) and total.get('complete') is False


def mention_borne_haute(total):
    """La mention « borne haute — N pertes non renseignées », mot pour mot,
    ou ``''`` sur un résultat complet."""
    if not _resultat_incomplet(total):
        return ''
    return str(total.get('mention') or '')


def texte_non_publie(total, cle):
    """« non publié — <motif> » à la place de ``cle`` (PR, P75, P90, P95)
    sur un résultat incomplet ; ``None`` sinon (la valeur s'imprime comme
    avant). Jamais 100 %, jamais 0 : sur un résultat incomplet, la valeur
    n'est jamais imprimée."""
    if not _resultat_incomplet(total):
        return None
    motif = total.get('%s_motif' % cle) or MOTIF_PAR_DEFAUT
    return 'non publié — %s' % motif


def _valeur_ou_non_publie(total, cle):
    texte = texte_non_publie(total, cle)
    if texte is not None:
        return '<span class="non-publie">%s</span>' % escape(texte)
    return nombre_tel_que_servi(total.get(cle))


def _p50_et_mention(total):
    p50 = nombre_tel_que_servi(total.get('p50_kwh'))
    mention = mention_borne_haute(total)
    if not mention:
        return p50
    return '%s <span class="detail mention-borne-haute">%s</span>' % (
        p50, escape(mention))


CSS_SECTION = (
    '.production-mensuelle td.valeur,.production-par-pan td.valeur,'
    '.production-pluriannuelle td.valeur,'
    '.production-quantiles td.valeur{text-align:right;}'
    '.production-quantiles .detail,.production-totaux .detail'
    '{display:block;font-size:7.5pt;color:#555;}'
)

#: PVsyst : P50/P75/P90 sont des quantiles ANNUELS (valeurs de dépassement),
#: jamais une garantie sur la durée de vie de l'installation.
MENTION_QUANTILES_ANNUELS = (
    "Les valeurs P50, P75 et P90 ci-dessus sont des quantiles ANNUELS : "
    "elles décrivent la variabilité d'une année d'exploitation, pas une "
    "garantie sur la durée de vie de l'installation.")

#: La nature d'une composante d'incertitude (contrat ``calepinage_
#: incertitude.json``, CALX144) — trois origines seulement, aucune quatrième
#: inventée.
_NATURE_SOURCE = {
    'pvgis': 'mesurée sur la série météo',
    'societe': 'hypothèse saisie par la société',
    'texte': 'publication citée',
}

_LIBELLE_MOIS = {
    1: 'Janvier', 2: 'Février', 3: 'Mars', 4: 'Avril', 5: 'Mai', 6: 'Juin',
    7: 'Juillet', 8: 'Août', 9: 'Septembre', 10: 'Octobre', 11: 'Novembre',
    12: 'Décembre',
}


def _ligne(libelle_, valeur):
    return '<tr><th>%s</th><td>%s</td></tr>' % (escape(str(libelle_)), valeur)


def _mois_libelle(mois):
    if mois in _LIBELLE_MOIS:
        return _LIBELLE_MOIS[mois]
    return nombre_tel_que_servi(mois)


def _bloc_totaux(total):
    lignes = [
        # ACAL50 — la mention « borne haute » SOUS le P50 ; le PR d'un
        # résultat incomplet est « non publié — <motif> ».
        _ligne('Production annuelle P50 (kWh)', _p50_et_mention(total)),
        _ligne('Ratio de performance (PR)',
               _valeur_ou_non_publie(total, 'performance_ratio')),
        _ligne('Productible spécifique (kWh/kWc)',
               nombre_tel_que_servi(total.get('specific_yield_kwh_kwc'))),
    ]
    return '<table class="production-totaux generique">%s</table>' % \
        ''.join(lignes)


def _par_mois(blocs, cle):
    """``[{mois, <cle>}]`` -> ``{mois: valeur}``, ou ``None`` si le bloc est
    absent (la colonne est alors omise)."""
    if not blocs:
        return None
    return {e.get('mois'): e.get(cle) for e in blocs if isinstance(e, dict)}


def _table_mensuelle(mensuel, irradiation=None, bilan=None, ghi=None):
    """ACAL452 — ``irradiation`` : ``production.irradiation_mensuelle``
    (liste ``{mois, irradiation_plan_kwh_m2}``) ou ``None`` : sans elle la
    colonne est omise. ACAL708 — ``bilan`` (``production.bilan_mensuel`` :
    ``temperature_ambiante_c``, ``pr``) et ``ghi``
    (``production.gain_inclinaison.ghi_mensuel`` : ``ghi_kwh_m2``) ajoutent
    leurs colonnes ; un bloc absent omet sa colonne, une valeur ``null``
    imprime « — ». Les valeurs sont imprimées telles que servies."""
    par_mois = _par_mois(irradiation, 'irradiation_plan_kwh_m2')
    colonnes = [('Production P50 (kWh)', {m.get('mois'): m.get('p50_kwh')
                                          for m in mensuel})]
    if par_mois is not None:
        colonnes.append(('Irradiation dans le plan (kWh/m²)', par_mois))
    for titre, blocs, cle in (
            ('Irradiation horizontale (kWh/m²)', ghi, 'ghi_kwh_m2'),
            ('Température ambiante (°C)', bilan, 'temperature_ambiante_c'),
            ('PR', bilan, 'pr')):
        valeurs = _par_mois(blocs, cle)
        if valeurs is not None:
            colonnes.append((titre, valeurs))
    lignes = ''.join(
        '<tr><td>%s</td>%s</tr>'
        % (escape(_mois_libelle(m.get('mois'))),
           ''.join('<td class="valeur">%s</td>'
                   % nombre_tel_que_servi(valeurs.get(m.get('mois')))
                   for _, valeurs in colonnes))
        for m in mensuel)
    entete = '<th>Mois</th>' + ''.join(
        '<th>%s</th>' % escape(titre) for titre, _ in colonnes)
    table = ('<table class="production-mensuelle generique"><tr>%s</tr>%s'
             '</table>' % (entete, lignes))
    if par_mois is None:
        table += ('<p class="note">Irradiation mensuelle non publiée par '
                  'cette simulation : relancez-la.</p>')
    return table


def _table_par_pan(par_pan):
    lignes = ''.join(
        '<tr><td>%s</td><td class="valeur">%s</td>'
        '<td class="valeur">%s</td><td class="valeur">%s</td>'
        '<td class="valeur">%s</td><td class="valeur">%s</td></tr>'
        % (escape(str(p.get('pan') or '')),
           nombre_tel_que_servi(p.get('modules')),
           nombre_tel_que_servi(p.get('kwc')),
           nombre_tel_que_servi(p.get('p50_kwh')),
           nombre_tel_que_servi(p.get('performance_ratio')),
           nombre_tel_que_servi(p.get('specific_yield_kwh_kwc')))
        for p in par_pan)
    entete = ('<th>Pan</th><th>Modules</th><th>Puissance (kWc)</th>'
              '<th>Production P50 (kWh)</th><th>PR</th>'
              '<th>Productible spécifique (kWh/kWc)</th>')
    return ('<table class="production-par-pan generique"><tr>%s</tr>%s'
            '</table>' % (entete, lignes))


def _table_pluriannuelle(projection, duree):
    """ACAL694 — « Production année par année » : ``production.projection``
    et ``production.duree_de_vie`` TELS QUE SERVIS (aucune arithmétique, aucun
    verdict « garantie tenue »). Un ``motif_omission`` servi remplace la
    table ; sans table ni motif, rien n'est imprimé."""
    duree = duree if isinstance(duree, dict) else {}
    motif = duree.get('motif_omission')
    titre = '<h3>Production année par année</h3>'
    if motif:
        return '%s<p class="note">%s</p>' % (titre, escape(motif_lisible(motif)))
    lignes = [p for p in projection or () if isinstance(p, dict)]
    if not lignes:
        return ''
    garantie = duree.get('garantie')
    garantie = garantie if isinstance(garantie, dict) else {}
    par_annee = {10: garantie.get('pct_a_10_ans'),
                 25: garantie.get('pct_a_25_ans')}
    corps = ''
    for ligne in lignes:
        annee = ligne.get('annee')
        servi = par_annee.get(annee) if annee in par_annee else None
        corps += ('<tr><td>%s</td><td class="valeur">%s</td>'
                  '<td class="valeur">%s</td><td class="valeur">%s</td></tr>'
                  % (nombre_tel_que_servi(annee),
                     nombre_tel_que_servi(ligne.get('p50_kwh')),
                     nombre_tel_que_servi(ligne.get('facteur')),
                     nombre_tel_que_servi(servi)))
    entete = ('<th>Année</th><th>Production P50 (kWh)</th><th>Facteur</th>'
              '<th>Garantie du fabricant (%)</th>')
    return ('%s<table class="production-pluriannuelle generique"><tr>%s</tr>'
            "%s</table><p class=\"note\">L'année est un rang, pas un "
            "millésime.</p>" % (titre, entete, corps))


def _composante_variabilite(incertitude):
    for composante in (incertitude or {}).get('composantes') or ():
        if isinstance(composante, dict) \
                and composante.get('nom') == 'variabilite_interannuelle':
            return composante
    return None


def _nature_variabilite(composante):
    if not composante:
        return escape('source non renseignée')
    source = composante.get('source')
    nature = _NATURE_SOURCE.get(source, escape(str(source)) if source
                                else 'source non renseignée')
    annees = composante.get('annees')
    if annees is not None:
        return escape('%s (%s années)' % (nature, nombre_tel_que_servi(
            annees)))
    return escape(nature)


def _variabilite_en_pourcent(fraction):
    """R3-18 (Q3) — la fraction servie (0,0753) imprimée en pourcentage
    lisible (7,53 %) : un décalage EXACT de la virgule (``Decimal``), jamais
    un arrondi ni un flottant ``* 100`` ; la fraction non numérique reste
    imprimée telle que servie."""
    if isinstance(fraction, bool) or not isinstance(
            fraction, (int, float)):
        return nombre_tel_que_servi(fraction)
    pourcent = format(Decimal(repr(float(fraction))).scaleb(2).normalize(),
                      'f')
    return '%s %%' % nombre_tel_que_servi(float(pourcent))


def _bloc_quantiles(total, incertitude):
    composante = _composante_variabilite(incertitude)
    variabilite = '%s <span class="detail">%s</span>' % (
        _variabilite_en_pourcent(total.get('annual_variability')),
        _nature_variabilite(composante))
    lignes = [
        _ligne('P50 (kWh)', _p50_et_mention(total)),
        _ligne('P75 (kWh)', _valeur_ou_non_publie(total, 'p75_kwh')),
        _ligne('P90 (kWh)', _valeur_ou_non_publie(total, 'p90_kwh')),
        _ligne('P95 (kWh)', _valeur_ou_non_publie(total, 'p95_kwh')),
        _ligne('Variabilité interannuelle', variabilite),
    ]
    return ('<table class="production-quantiles generique">%s</table>'
            '<p class="note">%s</p>'
            % (''.join(lignes), escape(MENTION_QUANTILES_ANNUELS)))


def _signe(pct):
    return '+' if pct > 0 else ''


def _bloc_ecart_devis(ecart, total):
    """ACAL104 (D-ACAL-6) — la production du DEVIS (imprimée au client), le
    P50 de l'étude et l'écart, LUS dans ``resultat.ecart_devis`` (mêmes
    valeurs que le JSON ``GET resultat/``) ; la mention « borne haute » suit
    le P50 quand des pertes ne sont pas renseignées (D-ACAL-7)."""
    if not isinstance(ecart, dict):
        return ''
    pct = ecart.get('ecart_pct')
    texte_pct = ('%s%s %%' % (_signe(pct), nombre_tel_que_servi(pct))
                 if isinstance(pct, (int, float)) else
                 nombre_tel_que_servi(pct))
    lignes = [
        _ligne('Production du devis %s (kWh/an, imprimée au client)'
               % (ecart.get('reference') or ''),
               nombre_tel_que_servi(ecart.get('production_devis_kwh'))),
        _ligne('P50 de l\'étude technique (kWh/an)',
               _p50_et_mention(dict(total or {},
                                    p50_kwh=ecart.get('p50_calepinage_kwh')))),
        _ligne('Écart étude / devis', escape(texte_pct)),
    ]
    return ('<table class="production-ecart-devis generique">%s</table>'
            '<p class="note">%s</p>'
            % (''.join(lignes), escape(ecart.get('mention') or '')))


def html_de_section(contexte):
    """Le corps de la section ``production`` (le titre est posé par
    l'assembleur)."""
    resultat = contexte.get('resultat') or {}
    production = resultat.get('production') or {}
    total = production.get('total') or {}
    mensuel = [m for m in production.get('mensuel') or () if isinstance(
        m, dict)]
    par_pan = [p for p in production.get('par_pan') or () if isinstance(
        p, dict)]
    incertitude = resultat.get('incertitude') or {}

    blocs = [_bloc_totaux(total)]
    if mensuel:
        gain = production.get('gain_inclinaison')
        blocs.append(_table_mensuelle(
            mensuel, production.get('irradiation_mensuelle'),
            production.get('bilan_mensuel'),
            (gain or {}).get('ghi_mensuel')
            if isinstance(gain, dict) else None))
    if par_pan:
        blocs.append(_table_par_pan(par_pan))
    blocs.append(_bloc_quantiles(total, incertitude))
    # ACAL104 — l'écart devis / étude, seulement quand il est servi.
    blocs.append(_bloc_ecart_devis(resultat.get('ecart_devis'), total))
    # ACAL694 — le tableau pluriannuel, en fin de section.
    blocs.append(_table_pluriannuelle(production.get('projection'),
                                      production.get('duree_de_vie')))
    return ''.join(blocs)
