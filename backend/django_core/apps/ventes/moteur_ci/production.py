"""CIQ109 — production horaire du site par la MÊME chaîne PVGIS que le résidentiel.

Module PUR (aucun import Django, aucune base, aucun appel réseau). Il reçoit
EXACTEMENT les sources du moteur résidentiel, résolues par l'appelant :
``apps.parametres.pvgis_profils.productible_mensuel`` (12 kWh/kWc, PVGIS
``loss=14``) et ``profil_production_journalier`` remis en heure civile par
``vers_heure_locale`` (formes 24 h par saison), plus le MÊME dérate
(``quote_engine.pricing.PRODUCTION_DERATE``, complément vers 20 % de pertes
totales, fondateur 18/08).

:func:`production_jours_types` est la fonction PARTAGÉE : le résidentiel
(``apps/ventes/etude_horaire.jours_types_annee``) l'appelle aussi, avec un
comportement octet-identique — fin du « GHI × 0,8 national » côté C&I.

Sans productible ou sans forme PVGIS : production ``None`` et étude omise
(règle Z2), jamais une cloche inventée. Une seule chaîne PVGIS existe,
FIGÉE à ``PVGIS_ANGLE_DEG``/``PVGIS_ASPECT_DEG`` : une pente ou un azimut
déclarés différents ne changent PAS la production, ils lèvent une alerte.
"""

from apps.parametres.pvgis_profils import (
    JOURS_PAR_MOIS,
    MOIS_PAR_SAISON,
    PVGIS_ANGLE_DEG,
    PVGIS_ASPECT_DEG,
    PVGIS_LOSS_PCT,
)

#: Mois (1-12) → saison PVGIS, dérivé de ``MOIS_PAR_SAISON`` (même découpage
#: que ``etude_horaire.saison_du_mois`` — jamais un second).
_SAISON_DU_MOIS = {
    mois: saison
    for saison, mois_tuple in MOIS_PAR_SAISON.items()
    for mois in mois_tuple
}

#: Types de pose (vocabulaire CIQ7, ``stock/contract_samples/produit_ci.json``)
#: dont la production doit être confirmée au calepinage : bac acier et toit plat.
POSES_A_CONFIRMER = frozenset({'bac_acier', 'toit_plat_leste', 'toit_plat_fixe'})

MESSAGE_ORIENTATION = ('orientation déclarée non prise en compte — production à confirmer '
                       'au calepinage')
MESSAGE_A_CONFIRMER = 'production à confirmer au calepinage'


def _num(valeur, defaut=0.0):
    try:
        return float(valeur)
    except (TypeError, ValueError):
        return float(defaut)


def production_jours_types(kwc, *, productible_mensuel, formes_saison, derate):
    """Les 12 jours moyens de production pour ``kwc`` — fonction PARTAGÉE.

    ``productible_mensuel`` : 12 kWh/kWc/mois PVGIS. ``formes_saison`` :
    ``{saison: forme 24 h (Σ 1)}``. Rend une liste de 12 entrées : ``None``
    pour un mois dont la saison n'a pas de forme, sinon
    ``{mois, saison, jours, prod_mois_kwh, prod_jour_kwh, prod_24h}``.
    """
    puissance = kwc
    sortie = []
    for index in range(12):
        numero = index + 1
        saison = _SAISON_DU_MOIS.get(numero)
        jours = JOURS_PAR_MOIS[index]
        forme_prod = formes_saison.get(saison)
        if forme_prod is None:
            sortie.append(None)
            continue
        prod_mois_kwh = _num(productible_mensuel[index]) * puissance * derate
        prod_jour_kwh = prod_mois_kwh / jours if jours else 0.0
        prod_24h = [part * prod_jour_kwh for part in forme_prod]
        sortie.append({
            'mois': numero,
            'saison': saison,
            'jours': jours,
            'prod_mois_kwh': prod_mois_kwh,
            'prod_jour_kwh': prod_jour_kwh,
            'prod_24h': prod_24h,
        })
    return sortie


def _alerte(code, champ, message, niveau='alerte', interne=False):
    return {'code': code, 'champ': champ, 'message': message,
            'niveau': niveau, 'interne': interne}


def traces_production(production, *, source=None, toit=None):
    """Hypothèses et alertes qui ACCOMPAGNENT un bloc ``production``.

    Rendues pour une production PVGIS (jamais pour celle d'un calepinage) :
    inclinaison/azimut PVGIS, libellé de la source, et les alertes du toit
    déclaré (orientation différente, pose à confirmer). CAD177 — fonction
    séparée pour que le rafraîchisseur (CIQ119), qui REPREND une
    ``production_figee`` au lieu de rappeler PVGIS, rende les mêmes traces :
    sinon un ré-enregistrement sans aucun changement retirait ces lignes de
    ``etude_ci`` (CIQ334/CIQ346, nocturne 37803204581).

    Rend ``(hypotheses, alertes)``.
    """
    hypotheses, alertes = [], []
    if not production or production.get('source') != 'pvgis':
        return hypotheses, alertes
    hypotheses.append({'cle': 'inclinaison_deg', 'valeur': PVGIS_ANGLE_DEG,
                       'statut': 'source', 'source': 'pvgis_profils.PVGIS_ANGLE_DEG'})
    hypotheses.append({'cle': 'azimut_deg', 'valeur': PVGIS_ASPECT_DEG,
                       'statut': 'source', 'source': 'pvgis_profils.PVGIS_ASPECT_DEG'})
    hypotheses.append({'cle': 'source_production', 'valeur': source,
                       'statut': 'source', 'source': 'PVGIS'})
    toit = toit or {}
    pente = toit.get('pente_deg')
    azimut = toit.get('azimut_deg')
    orientation_differente = (
        (pente is not None and _num(pente) != PVGIS_ANGLE_DEG)
        or (azimut is not None and _num(azimut) != PVGIS_ASPECT_DEG))
    if orientation_differente:
        alertes.append(_alerte('orientation_non_prise_en_compte', 'toit',
                               MESSAGE_ORIENTATION))
    if toit.get('type_pose') in POSES_A_CONFIRMER:
        alertes.append(_alerte('production_a_confirmer_calepinage', 'toit.type_pose',
                               MESSAGE_A_CONFIRMER, niveau='info'))
    return hypotheses, alertes


def bloc_production_ci(*, productible_mensuel, formes_saison, derate, coordonnees_figees,
                       source=None, toit=None, calepinage=None):
    """Bloc ``production`` du contrat ``etude_ci_preview.json`` (par kWc).

    ``coordonnees_figees`` : ``{lat, lon, date_appel}`` figés par l'appelant
    (reproductibilité). ``source`` : libellé PVGIS rendu par la résolution.
    ``toit`` : ``{type_pose, pente_deg, azimut_deg}`` déclarés.
    ``calepinage`` : ``{id, kwh_kwc_mensuel?}`` du calepinage retenu (lu par
    l'orchestrateur via ``apps.calepinage.selectors``) — il passe devant PVGIS.

    Rend ``(production | None, hypotheses, alertes)``.
    """
    alertes = []
    hypotheses = []
    if not productible_mensuel or len(productible_mensuel) != 12 or not formes_saison:
        alertes.append(_alerte(
            'production_indisponible', 'production',
            'Profil PVGIS indisponible : production non calculée, étude omise.',
            niveau='bloquant'))
        return None, hypotheses, alertes

    mensuel_calepinage = (calepinage or {}).get('kwh_kwc_mensuel')
    par_mois = production_jours_types(
        1.0, productible_mensuel=productible_mensuel, formes_saison=formes_saison,
        derate=derate)
    if any(m is None for m in par_mois):
        alertes.append(_alerte(
            'production_indisponible', 'production',
            'Forme PVGIS manquante pour une saison : production non calculée, étude omise.',
            niveau='bloquant'))
        return None, hypotheses, alertes

    if mensuel_calepinage and len(mensuel_calepinage) == 12:
        # Production par pan du calepinage retenu : son niveau mensuel, la forme PVGIS.
        par_mois = [
            dict(m, prod_mois_kwh=_num(v), prod_jour_kwh=_num(v) / m['jours'],
                 prod_24h=[p * _num(v) / m['jours'] for p in formes_saison[m['saison']]])
            for m, v in zip(par_mois, mensuel_calepinage)
        ]
        origine = 'calepinage'
    else:
        origine = 'pvgis'

    production = {
        'source': origine,
        'coordonnees_figees': dict(coordonnees_figees) if coordonnees_figees else None,
        'inclinaison_deg': PVGIS_ANGLE_DEG,
        'azimut_deg': PVGIS_ASPECT_DEG,
        'pertes_pct': PVGIS_LOSS_PCT,
        'kwh_kwc_mensuel': [m['prod_mois_kwh'] for m in par_mois],
        'jours_types': [{'mois': m['mois'], 'production_kwh_kwc': m['prod_24h']}
                        for m in par_mois],
    }

    hyp_prod, al_prod = traces_production(production, source=source, toit=toit)
    hypotheses.extend(hyp_prod)
    alertes.extend(al_prod)
    return production, hypotheses, alertes
