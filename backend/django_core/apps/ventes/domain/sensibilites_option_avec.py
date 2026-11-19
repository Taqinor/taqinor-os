"""D-SENS-1 (fondateur 19/11/2026, « Yes, fix it ») — niveau de règles 14 : les
sensibilités de l'option C&I « avec batterie ».

L'option « avec » sert ``economie_flux.sensibilites`` dans la MÊME forme que
l'option réseau (``economie_ci.sensibilites_ci`` : ``{cle, variation_pct,
source, economie_annee1_mad, retour_ans, retour_dixieme_ans, tri_pct,
cumul_25_ans_mad, ecart_retour_ans, ecart_tri_pct[, motif]}``), pour les mêmes
scénarios société (``TariffSettings.sensibilites_ci``) dans le même ordre :

* ``indexation_tarif`` / ``degradation`` / ``tarif_kwh`` — ``sensibilites_ci``
  lui-même, sur les entrées EXACTES du flux central de l'option (remplacement
  de la batterie compris) ; le tarif × (1 + v) passe par la même valorisation
  que l'étude (``economie_ci.valoriser`` sur le bilan AVEC batterie) ;
* ``production`` — l'option est RÉ-ÉVALUÉE (``moteur_ci.batterie.
  evaluer_option_avec``, même charge, même banque, mêmes onduleurs) sur la
  production × (1 + v) : la batterie est re-simulée heure par heure, jamais une
  économie mise à l'échelle ; le flux du scénario est bâti comme le central, le
  remplacement de la batterie suivant le niveau 13 sur le bilan DU scénario.

Un scénario qui ne se calcule pas est servi avec un motif nommé et aucun
chiffre. Calculé une seule fois, pour l'option servie (``etude_ci_batterie.
_bloc``), jamais pour chaque banque candidate du dimensionnement.
"""

#: Le bilan ré-évalué à 100 % ne reproduit pas le central : rien n'est chiffré.
MOTIF_AVEC_NON_REPRODUCTIBLE = (
    "option avec batterie non recalculable à l'identique (étude à rafraîchir) : "
    "scénario non chiffré")
#: L'étude n'a pas transmis son tarif : le scénario tarif n'est pas chiffré.
MOTIF_AVEC_TARIF_ABSENT = (
    "tarif de l'étude indisponible pour l'option avec batterie : scénario non chiffré")
#: Le flux du scénario manque une entrée (économie omise, investissement).
MOTIF_AVEC_FLUX_ABSENT = (
    "flux de l'option avec batterie non chiffré pour ce scénario : scénario non chiffré")


def scenarios_du_devis(company, devis):
    """Les scénarios société (``economie_ci.reglages_economie_ci``, les mêmes que
    l'option réseau) quand le devis suit le niveau 14 ; ``None`` sinon : un
    devis envoyé avant garde l'option « avec » sans sensibilités."""
    from apps.ventes.economie_ci import reglages_economie_ci

    from .regles_calcul import REGLES_SENSIBILITES_1911, regles_au_moins
    if not regles_au_moins(devis, REGLES_SENSIBILITES_1911):
        return None
    return list(reglages_economie_ci(company).get('sensibilites_ci') or [])


def production_a_l_echelle(production, facteur):
    """L'entrée ``production_jours_types`` du bilan (``production_pour_bilan`` :
    12 journées moyennes ou série triée et cumulée) × ``facteur``, heure par
    heure. Aucune écriture sur ``production``."""
    from apps.ventes.moteur_ci.autoconso import _num
    sortie = []
    for bloc in production or []:
        if isinstance(bloc, dict):
            bloc = dict(bloc)
            if bloc.get('production_kwh_kwc') is not None:
                bloc['production_kwh_kwc'] = [_num(v) * facteur for v in bloc['production_kwh_kwc']]
            for cle in ('heures_triees', 'cumuls'):
                if bloc.get(cle) is not None:
                    bloc[cle] = [[_num(v) * facteur for v in rang] for rang in bloc[cle]]
        sortie.append(bloc)
    return sortie


def reevaluateur(kwc, onduleurs, banque, *, hybrides, charge, production, tension,
                 revente_choisie, valoriser):
    """``reevaluer(facteur)`` → l'évaluation de l'option « avec » (même
    ``evaluer_option_avec``, même simulation de la batterie) sur la production
    × ``facteur``. ``production`` : appelable sans argument (lu au premier
    scénario seulement). Composition non passée : le coût n'entre pas ici."""
    lue = {}

    def reevaluer(facteur):
        from apps.ventes.etude_horaire import simuler_batterie_jour
        from apps.ventes.moteur_ci.batterie import evaluer_option_avec
        if 'production' not in lue:
            lue['production'] = production()
        return evaluer_option_avec(
            kwc, onduleurs, None, banque, charge=charge,
            production=production_a_l_echelle(lue['production'], facteur), tension=tension,
            revente_choisie=revente_choisie, valoriser=valoriser, simuler=simuler_batterie_jour,
            hybrides=hybrides)
    return reevaluer


def _retenus(scenarios):
    """Le filtre de ``economie_ci.sensibilites_ci`` (clé connue, source saisie,
    au plus quatre) : la même liste que l'option réseau."""
    from apps.ventes import economie_ci as eco
    return [s for s in scenarios or [] if isinstance(s, dict)
            and s.get('cle') in eco.SENSIBILITE_CLES
            and str(s.get('source') or '').strip()][:eco.SENSIBILITES_MAX]


def _ligne(sc, bloc, base, economie, motif=None):
    """Une ligne du contrat ``economie_ci.json`` ; sous un motif, aucun chiffre."""
    from apps.ventes import economie_ci as eco
    from apps.ventes.economie_ci_options import retour_au_dixieme
    bloc = None if motif else bloc
    ligne = {'cle': sc['cle'], 'variation_pct': float(str(sc.get('variation_pct')).replace(',', '.')),
             'source': str(sc['source']).strip(),
             'economie_annee1_mad': None if motif else eco._montant(economie),
             'retour_ans': eco._indicateur(bloc, 'retour_ans'),
             'retour_dixieme_ans': retour_au_dixieme(bloc),
             'tri_pct': eco._indicateur(bloc, 'tri_pct'),
             'cumul_25_ans_mad': ((bloc or {}).get('flux') or [{}])[-1].get('cumul_mad'),
             'ecart_retour_ans': eco._ecart(eco._indicateur(bloc, 'retour_ans'), base.get('retour_ans')),
             'ecart_tri_pct': eco._ecart(eco._indicateur(bloc, 'tri_pct'), base.get('tri_pct'))}
    if motif is not None:
        ligne['motif'] = motif
    return ligne


def _reproduit(controle, evaluation):
    """Vrai si l'évaluation à 100 % retrouve le central (économie, production,
    énergie restituée par la batterie — donc ses cycles par an)."""
    from apps.ventes.economie_ci_options import _proche
    if not isinstance(controle, dict):
        return False
    a, b = controle.get('bilan') or {}, evaluation.get('bilan') or {}
    return (_proche(controle.get('economie'), evaluation.get('economie'))
            and _proche(a.get('production_kwh'), b.get('production_kwh'))
            and _proche((a.get('batterie') or {}).get('restitue_kwh_an'),
                        (b.get('batterie') or {}).get('restitue_kwh_an')))


def flux_du_scenario_production(sc, reevaluer, *, complet, flux_de):
    """``(flux, economie)`` du scénario production : l'option ré-évaluée sur
    la production × (1 + v), valorisée (``complet``), puis son flux 25 ans par
    ``flux_de`` (le remplacement de la batterie lu sur le bilan DU scénario) ;
    ``(None, economie)`` quand le flux manque une entrée."""
    v = float(str(sc.get('variation_pct')).replace(',', '.'))
    evaluation = reevaluer(1.0 + v / 100.0)
    economie = complet(evaluation['bilan'])
    return flux_de(evaluation, economie, None), economie


def _economie_principale(economie, cle_base):
    eco1 = (economie or {}).get('economie_annee1') or {}
    return eco1.get('total_mad_ttc' if cle_base == 'ttc' else 'total_mad')


def _lignes_production(scenarios, evaluation, base, cle_base, *, reevaluer, complet, flux_de):
    principal = 'flux_ttc' if cle_base == 'ttc' else 'flux_ht'
    motif = None if reevaluer is not None and complet is not None and _reproduit(
        reevaluer(1.0), evaluation) else MOTIF_AVEC_NON_REPRODUCTIBLE
    lignes = []
    for sc in scenarios:
        if motif is not None:
            lignes.append(_ligne(sc, None, base, None, motif))
            continue
        flux, economie = flux_du_scenario_production(sc, reevaluer, complet=complet, flux_de=flux_de)
        lignes.append(_ligne(sc, (flux or {}).get(principal), base, _economie_principale(economie, cle_base),
                             None if flux else MOTIF_AVEC_FLUX_ABSENT))
    return lignes


def sensibilites_option_avec(scenarios, evaluation, economie, flux, *, flux_de, reevaluer,
                             complet, valorisation):
    """La liste ``economie_flux.sensibilites`` de l'option « avec » (voir le
    module). ``flux`` : le flux central servi ; ``flux_de(evaluation, economie,
    collecteur)`` : le flux 25 ans de l'option (``etude_ci_batterie.
    _flux_option_avec``) ; ``reevaluer`` : :func:`reevaluateur` (None ⇒ motif) ;
    ``complet`` : la valorisation complète ; ``valorisation`` : ``{tarif,
    tarif_declare, apercu(bilan)}`` de l'étude (None ⇒ tarif non chiffré)."""
    from apps.ventes import economie_ci as eco
    scenarios = _retenus(scenarios)
    if not scenarios or not isinstance(flux, dict):
        return []
    cle_base = 'ttc' if flux.get('base') == eco.BASE_TTC else 'ht'
    base = flux.get('flux_ttc' if cle_base == 'ttc' else 'flux_ht') or {}
    collecteur = {}
    flux_de(evaluation, economie, collecteur)
    entrees = collecteur.get(cle_base)
    autres = [s for s in scenarios if s['cle'] != 'production' and entrees
              and (s['cle'] != 'tarif_kwh' or valorisation)]
    calcules = iter(eco.sensibilites_ci(
        entrees, valorisation['apercu'](evaluation['bilan']) if valorisation else {},
        (valorisation or {}).get('tarif') or {}, {'sensibilites_ci': autres},
        tarif_declare=(valorisation or {}).get('tarif_declare'), cle_base=cle_base)[0] if autres else [])
    production = iter(_lignes_production(
        [s for s in scenarios if s['cle'] == 'production'], evaluation, base, cle_base,
        reevaluer=reevaluer, complet=complet, flux_de=flux_de))
    return [next(production) if s['cle'] == 'production'
            else next(calcules) if s in autres
            else _ligne(s, None, base, None, MOTIF_AVEC_TARIF_ABSENT if entrees else MOTIF_AVEC_FLUX_ABSENT)
            for s in scenarios]
