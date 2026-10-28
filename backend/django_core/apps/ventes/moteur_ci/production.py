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
(règle Z2), jamais une cloche inventée. La table et les formes sont FIGÉES à
``PVGIS_ANGLE_DEG``/``PVGIS_ASPECT_DEG`` : sur ce repli (journées moyennes), une
pente ou un azimut déclarés différents ne changent PAS la production (alerte).
AMOT99 (D-ACI-18=a) — avec la série HORAIRE de l'année type au plan déclaré
(:func:`plan_de_production`), le bloc en dérive tout et le bilan se croise sur
ses 8 760 h (:func:`production_pour_bilan`) ; la méthode est toujours dite.
"""

from itertools import accumulate

from apps.parametres.pvgis_profils import (
    JOURS_PAR_MOIS,
    MOIS_PAR_SAISON,
    PVGIS_ANGLE_DEG,
    PVGIS_ASPECT_DEG,
    PVGIS_LOSS_PCT,
    SERIE_ANNEE_DEBUT,
    SERIE_ANNEE_FIN,
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

#: AMOT99 — pose CIQ7 → montage PVGIS (« free » : rack ventilé ; « building » :
#: aucune ventilation). Surimposition = « entre les deux » (manuel PVGIS) : le
#: cas le MOINS favorable est retenu.
MONTAGE_PVGIS_DE_LA_POSE = {'toiture_inclinee': 'building', 'bac_acier': 'building'}
#: CMP5 — décision fondateur du 27/10/2026 (Reda, D-CMP-4=c) : un toit plat
#: (lesté ou fixé) sans inclinaison déclarée garde 30° plein sud ;
#: l'inclinaison réelle des panneaux se saisit dans le générateur (étude C&I,
#: ``toit.pente_deg``) et passe alors devant ce défaut.
POSES_TOIT_PLAT = frozenset({'toit_plat_leste', 'toit_plat_fixe'})
ANGLE_TOIT_PLAT_DEG = float(PVGIS_ANGLE_DEG)
SOURCE_ANGLE_TOIT_PLAT = ('toit plat sans inclinaison déclarée : 30° (décision fondateur du '
                          '27/10/2026), modifiable dans le générateur')
#: R1 — décision fondateur du 28/10/2026 : 30° reste le défaut ; quand la
#: taille retenue par l'économie ne tient pas sur le toit à 30°, les tables
#: passent en pose RASANTE 10° (densité maximale) pour la loger. Le
#: basculement ne vaut que pour un toit plat SANS pente déclarée (une pente
#: saisie dans le générateur l'emporte toujours, décision du 27/10).
ANGLE_POSE_RASANTE_DEG = 10.0
SOURCE_ANGLE_POSE_RASANTE = ('toit plat sans inclinaison déclarée : pose rasante 10° pour loger '
                             'la taille retenue (décision fondateur du 28/10/2026), modifiable '
                             'dans le générateur')
#: Marqueur du ``toit`` de la série rasante (``toit_rasant``), lu par
#: :func:`plan_de_production` — jamais une pente DÉCLARÉE.
CLE_POSE_RASANTE = 'pose_rasante'
HEURES_AN = 8760
METHODE_8760 = 'horaire_8760'
METHODE_JOURNEES_MOYENNES = 'journees_moyennes'


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
    toit = toit or {}
    pente = toit.get('pente_deg')
    azimut = toit.get('azimut_deg')
    serie = production.get('serie_horaire') or None
    angle = production.get('inclinaison_deg', PVGIS_ANGLE_DEG)
    aspect = production.get('azimut_deg', PVGIS_ASPECT_DEG)
    # CMP5 — la source de l'angle voyage avec le bloc (pose estimée comprise).
    defaut_angle = production.get('inclinaison_source') or 'pvgis_profils.PVGIS_ANGLE_DEG'
    for cle, valeur, declare, defaut in (('inclinaison_deg', angle, pente, defaut_angle),
                                         ('azimut_deg', aspect, azimut, 'pvgis_profils.PVGIS_ASPECT_DEG')):
        lu = serie is not None and declare is not None
        hypotheses.append({'cle': cle, 'valeur': valeur, 'source': 'toit déclaré' if lu else defaut,
                           'statut': 'estimation' if serie is not None and not lu else 'source'})
    hypotheses.append({'cle': 'source_production', 'valeur': source,
                       'statut': 'source', 'source': 'PVGIS'})
    # AMOT99 — la méthode d'autoconsommation retenue est TOUJOURS dite.
    hypotheses.append({'cle': 'methode_autoconsommation', 'valeur': METHODE_8760, 'statut': 'source',
                       'source': 'PVGIS seriescalc %s, année type (mois représentatifs %s), montage '
                                 '« %s » : 8 760 h croisées heure par heure avec le profil déclaré'
                                 % (serie.get('periode'), serie.get('annees_type'), serie.get('montage'))}
                      if serie is not None else
                      {'cle': 'methode_autoconsommation', 'valeur': METHODE_JOURNEES_MOYENNES,
                       'statut': 'estimation',
                       'source': 'série horaire PVGIS indisponible (coordonnées GPS absentes, PVGIS '
                                 'injoignable ou production figée sans série) : repli sur 12 journées '
                                 'moyennes PVGIS (30° plein sud) × types de jour'})
    orientation_differente = (
        (pente is not None and _num(pente) != _num(angle))
        or (azimut is not None and _num(azimut) != _num(aspect)))
    if orientation_differente:
        alertes.append(_alerte('orientation_non_prise_en_compte', 'toit',
                               MESSAGE_ORIENTATION))
    if toit.get('type_pose') in POSES_A_CONFIRMER:
        alertes.append(_alerte('production_a_confirmer_calepinage', 'toit.type_pose',
                               MESSAGE_A_CONFIRMER, niveau='info'))
    return hypotheses, alertes


def bascule_rasante_admissible(toit):
    """R1 — le basculement 30° → pose rasante 10° ne vaut que pour un toit
    plat (``POSES_TOIT_PLAT``) SANS pente déclarée (une pente saisie l'emporte,
    décision du 27/10/2026)."""
    toit = toit or {}
    return toit.get('pente_deg') is None and toit.get('type_pose') in POSES_TOIT_PLAT


def toit_rasant(toit):
    """R1 — le ``toit`` de la série horaire en pose rasante (même pose, même
    azimut, marqueur ``pose_rasante``) quand le basculement est admissible,
    sinon ``None`` (pente déclarée, autre pose : jamais de seconde série)."""
    if not bascule_rasante_admissible(toit):
        return None
    return dict(toit or {}, **{CLE_POSE_RASANTE: True})


def plan_de_production(toit):
    """AMOT99 — plan PVGIS de la série : pente / azimut (PVGIS : 0 = Sud, −90 = Est)
    DÉCLARÉS, sinon ceux de la table (dits en estimation) ; montage selon la pose
    déclarée ou estimée (D-ACI-13, résolue par l'appelant)."""
    toit = toit or {}
    pente, azimut = toit.get('pente_deg'), toit.get('azimut_deg')
    source_angle = None
    if bascule_rasante_admissible(toit):
        if toit.get(CLE_POSE_RASANTE):
            pente, source_angle = ANGLE_POSE_RASANTE_DEG, SOURCE_ANGLE_POSE_RASANTE
        else:
            pente, source_angle = ANGLE_TOIT_PLAT_DEG, SOURCE_ANGLE_TOIT_PLAT
    return {'angle_deg': PVGIS_ANGLE_DEG if pente is None else _num(pente),
            'source_angle': source_angle,
            'aspect_deg': PVGIS_ASPECT_DEG if azimut is None else _num(azimut),
            'montage': MONTAGE_PVGIS_DE_LA_POSE.get(toit.get('type_pose'), 'free')}


def _depuis_serie(serie, plan, derate):
    """AMOT99 — ``(serie_horaire, kwh_kwc_mensuel, jours_types)`` de la série
    8 760 h × ``derate`` (même dérate que la table), ou ``None``."""
    kwh = (serie or {}).get('kwh_kwc') or []
    if len(kwh) != HEURES_AN or not plan:
        return None
    valeurs = [round(_num(v) * derate, 4) for v in kwh]
    mensuel, jours_types, debut = [], [], 0
    for index, jours in enumerate(JOURS_PAR_MOIS):
        mois_h = valeurs[debut:debut + 24 * jours]
        debut += 24 * jours
        mensuel.append(sum(mois_h))
        jours_types.append({'mois': index + 1,
                            'production_kwh_kwc': [sum(mois_h[h::24]) / jours
                                                   for h in range(24)]})
    serie_horaire = {'kwh_kwc': valeurs, 'annees_type': list(serie.get('annees') or []),
                     'montage': plan['montage'],
                     'periode': '%s-%s' % (SERIE_ANNEE_DEBUT, SERIE_ANNEE_FIN)}
    return serie_horaire, mensuel, jours_types


def production_pour_bilan(production):
    """AMOT99 — l'entrée ``production_jours_types`` du bilan : avec la série, la
    production de chaque heure des jours réels du mois, triée et cumulée (une
    fois par étude) ; sans elle, les 12 journées moyennes du bloc (repli dit)."""
    production = production or {}
    serie = (production.get('serie_horaire') or {}).get('kwh_kwc') or []
    if len(serie) != HEURES_AN:
        return production.get('jours_types')
    sortie, debut = [], 0
    for index, jours in enumerate(JOURS_PAR_MOIS):
        triees = [sorted(_num(v) for v in serie[debut + h:debut + 24 * jours:24])
                  for h in range(24)]
        debut += 24 * jours
        sortie.append({'mois': index + 1, 'heures_triees': triees,
                       'cumuls': [list(accumulate(t, initial=0.0)) for t in triees]})
    return sortie


def bloc_production_ci(*, productible_mensuel, formes_saison, derate, coordonnees_figees,
                       source=None, toit=None, calepinage=None, serie=None, plan=None):
    """Bloc ``production`` du contrat ``etude_ci_preview.json`` (par kWc).

    ``coordonnees_figees`` : ``{lat, lon, date_appel}`` figés par l'appelant
    (reproductibilité). ``source`` : libellé PVGIS rendu par la résolution.
    ``toit`` : ``{type_pose, pente_deg, azimut_deg}`` déclarés.
    ``calepinage`` : ``{id, kwh_kwc_mensuel?}`` du calepinage retenu (lu par
    l'orchestrateur via ``apps.calepinage.selectors``) — il passe devant PVGIS.
    ``serie`` / ``plan`` (AMOT99) : l'année type horaire et son plan — le bloc en dérive.

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

    depuis_serie = _depuis_serie(serie, plan, derate) if origine == 'pvgis' else None
    production = {
        'source': origine,
        'coordonnees_figees': dict(coordonnees_figees) if coordonnees_figees else None,
        'inclinaison_deg': plan['angle_deg'] if depuis_serie else PVGIS_ANGLE_DEG,
        'azimut_deg': plan['aspect_deg'] if depuis_serie else PVGIS_ASPECT_DEG,
        'pertes_pct': PVGIS_LOSS_PCT,
        'kwh_kwc_mensuel': [m['prod_mois_kwh'] for m in par_mois],
        'jours_types': [{'mois': m['mois'], 'production_kwh_kwc': m['prod_24h']}
                        for m in par_mois],
        'methode_autoconso': METHODE_8760 if depuis_serie else METHODE_JOURNEES_MOYENNES,
        'serie_horaire': None,
    }
    if depuis_serie and plan.get('source_angle'):
        production['inclinaison_source'] = plan['source_angle']
    if depuis_serie:
        (production['serie_horaire'], production['kwh_kwc_mensuel'],
         production['jours_types']) = depuis_serie

    hyp_prod, al_prod = traces_production(production, source=source, toit=toit)
    hypotheses.extend(hyp_prod)
    alertes.extend(al_prod)
    return production, hypotheses, alertes
