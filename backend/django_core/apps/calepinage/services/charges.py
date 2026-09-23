"""CAL154 — charges additionnelles DÉCLARÉES : véhicule électrique, PAC.

LE CONSTAT
----------
``ev_charger_sizing`` (``apps/ventes/solar_design.py``) dimensionne une BORNE
mais n'ajoute AUCUNE charge au profil : brancher une voiture ne changeait rien
à la courbe de consommation, donc rien à l'autoconsommation ni à la batterie
vendue. Et aucune pompe à chaleur n'existe côté énergie dans le dépôt.
PV*SOL modélise les VE comme des charges (kilométrage quotidien, temps de
stationnement — https://valentin-software.com/en/products/pvsol-premium/) et
Polysun couple la PAC au PV.

LA RÈGLE POSÉE ICI
------------------
1. **Tout est SAISI.** Aucun kWh/100 km par défaut, aucun COP par défaut :
   une Zoé et un utilitaire ne consomment pas pareil, une PAC air/air et une
   air/eau non plus. Une charge incomplète est REFUSÉE en NOMMANT le champ
   manquant — jamais complétée.
2. **Chaque charge reste VISIBLE séparément** dans le bilan : on doit pouvoir
   dire au client « votre voiture, c'est ça » sans refaire le calcul.
3. **Le retrait d'une charge rend EXACTEMENT le bilan initial** (au kWh
   près) : la courbe de base n'est jamais modifiée sur place, les charges
   s'additionnent dans une copie.
4. **La fenêtre de recharge est saisie**, et l'énergie s'y répartit
   UNIFORMÉMENT — c'est l'hypothèse la plus neutre, et elle est DITE. Une
   courbe de charge « réaliste » inventée serait un chiffre inventé.

Module PUR : aucune base, aucun réseau, aucun prix.
"""
from __future__ import annotations

__all__ = ['ChargeInvalide', 'TYPES_DE_CHARGE', 'ajouter_charges',
           'courbe_pac', 'courbe_vehicule']

TYPES_DE_CHARGE = ('vehicule', 'pac')

#: La répartition employée dans une fenêtre saisie, DITE explicitement.
MENTION_REPARTITION = (
    "L'énergie est répartie UNIFORMÉMENT sur la fenêtre saisie : c'est "
    "l'hypothèse la plus neutre, et elle est annoncée. Aucune courbe de "
    'recharge « réaliste » n’est inventée.')


class ChargeInvalide(ValueError):
    """Une charge additionnelle refusée, en français et en NOMMANT le champ."""

    def __init__(self, message, *, champ=''):
        super().__init__(message)
        self.champ = champ
        self.motif = message


def _obligatoire(valeur, *, champ, libelle, positif=True):
    if valeur is None or valeur == '':
        raise ChargeInvalide(
            f'{libelle} est obligatoire : ce module ne suppose aucune valeur '
            'par défaut pour une charge additionnelle.', champ=champ)
    try:
        nombre = float(valeur)
    except (TypeError, ValueError):
        raise ChargeInvalide(f'{libelle} est illisible (reçu : {valeur!r}).',
                             champ=champ)
    if nombre != nombre:
        raise ChargeInvalide(f'{libelle} est illisible.', champ=champ)
    if positif and nombre <= 0:
        raise ChargeInvalide(
            f'{libelle} doit être strictement positif (reçu : {nombre}).',
            champ=champ)
    if not positif and nombre < 0:
        raise ChargeInvalide(
            f'{libelle} ne peut pas être négatif (reçu : {nombre}).',
            champ=champ)
    return nombre


def _nombre_signe(valeur, *, champ, libelle):
    """Un nombre SAISI, positif OU négatif — une température extérieure,
    par exemple (``_obligatoire`` refuse toujours le négatif, y compris avec
    ``positif=False``, qui ne relâche que la stricte positivité)."""
    if valeur is None or valeur == '':
        raise ChargeInvalide(
            f'{libelle} est obligatoire : ce module ne suppose aucune valeur '
            'par défaut pour une charge additionnelle.', champ=champ)
    try:
        nombre = float(valeur)
    except (TypeError, ValueError):
        raise ChargeInvalide(f'{libelle} est illisible (reçu : {valeur!r}).',
                             champ=champ)
    if nombre != nombre:
        raise ChargeInvalide(f'{libelle} est illisible.', champ=champ)
    return nombre


def _fenetre(heures, *, champ, libelle):
    if not heures:
        raise ChargeInvalide(
            f'{libelle} est obligatoire : sans elle, on ne sait pas QUAND la '
            'charge pèse sur la courbe — et le taux d’autoconsommation en '
            'dépend entièrement.', champ=champ)
    lues = []
    for valeur in heures:
        try:
            heure = int(valeur)
        except (TypeError, ValueError):
            raise ChargeInvalide(
                f'{libelle} contient une heure illisible '
                f'(reçu : {valeur!r}).', champ=champ)
        if not 0 <= heure <= 23:
            raise ChargeInvalide(
                f'{libelle} contient une heure hors bornes (reçu : {heure}) : '
                'les heures se comptent de 0 à 23.', champ=champ)
        lues.append(heure)
    return sorted(set(lues))


def _repartir(energie_kwh, heures_actives, *, longueur, heure_de_depart=0):
    """Répartit une énergie JOURNALIÈRE sur les heures saisies, jour après jour."""
    courbe = [0.0] * longueur
    if not heures_actives:
        return courbe
    part = energie_kwh / len(heures_actives)
    actives = set(heures_actives)
    for rang in range(longueur):
        if (int(heure_de_depart) + rang) % 24 in actives:
            courbe[rang] = part
    return courbe


#: Modes de recharge acceptés par CALX261 (parité PV*SOL « Default » /
#: « PV-optimized » — https://help.valentin-software.com/pvsol/en/pages/electric-vehicles/).
MODES_RECHARGE_VEHICULE = ('immediat', 'pv_optimise')


def _placer_sur_surplus(energie_kwh, heures_actives, production_horaire, *,
                        longueur, heure_de_depart):
    """Place ``energie_kwh`` d'abord sur les heures de SURPLUS de production,
    dans la fenêtre saisie (CALX261).

    Le véhicule charge quand même le reliquat que le surplus ne couvre pas —
    ce reliquat vient alors du RÉSEAU, jamais masqué : il est réparti
    UNIFORMÉMENT sur la même fenêtre (exactement comme le mode ``immediat``),
    pendant que la part couverte par le surplus est placée en PRIORITÉ sur
    les heures de plus grand surplus. Un surplus NUL sur toute la fenêtre
    rend donc une courbe IDENTIQUE au mode ``immediat`` — seule la source
    (réseau vs PV) change.

    Returns:
        (courbe, energie_reseau_kwh) — ``courbe`` couvre ``longueur`` heures
        et somme à ``energie_kwh`` ; ``energie_reseau_kwh`` est la part de
        cette énergie que le surplus n'a pas couverte.
    """
    courbe = [0.0] * longueur
    if not heures_actives or energie_kwh <= 0:
        return courbe, max(0.0, energie_kwh)

    productions = list(production_horaire)
    # Un rang de la fenêtre (dans l'ordre de la courbe rendue) associé au
    # surplus de production disponible à cette heure — trié du plus grand
    # surplus au plus petit pour consommer le surplus en priorité.
    candidats = []
    for rang in range(longueur):
        heure_du_jour = (int(heure_de_depart) + rang) % 24
        if heure_du_jour not in heures_actives:
            continue
        surplus = (float(productions[rang]) if rang < len(productions)
                   else 0.0)
        candidats.append((rang, max(0.0, surplus)))

    total_surplus = sum(surplus for _, surplus in candidats)
    couvert_pv = min(energie_kwh, total_surplus)
    energie_reseau = energie_kwh - couvert_pv

    restant = couvert_pv
    for rang, surplus in sorted(candidats, key=lambda item: item[1],
                                reverse=True):
        if restant <= 0:
            break
        place = min(restant, surplus)
        if place > 0:
            courbe[rang] += place
            restant -= place

    if energie_reseau > 0:
        part_reseau = energie_reseau / len(candidats)
        for rang, _ in candidats:
            courbe[rang] += part_reseau

    return courbe, max(0.0, energie_reseau)


def _borner_puissance(courbe, plafond_kw):
    """Plafonne CHAQUE heure de ``courbe`` à ``plafond_kw`` (CALX262).

    L'énergie qui ne tient pas dans la fenêtre à cause de ce plafond est
    rendue à part — JAMAIS masquée : c'est ``energie_non_placee_kwh``, avec
    la mention que la fenêtre est trop courte pour la borne saisie.

    Returns:
        (courbe_bornee, energie_non_placee_kwh)
    """
    bornee = [min(valeur, plafond_kw) for valeur in courbe]
    deborde = sum(valeur - place for valeur, place in zip(courbe, bornee))
    return bornee, max(0.0, deborde)


def courbe_vehicule(*, km_par_jour=None, kwh_par_100km=None,
                    fenetre_recharge=None, longueur=24, heure_de_depart=0,
                    rendement_recharge_pct=None, mode='immediat',
                    production_horaire=None, puissance_borne_kw=None):
    """La charge horaire d'un VÉHICULE ÉLECTRIQUE — tout est saisi.

    Args:
        km_par_jour / kwh_par_100km: la consommation RÉELLE du véhicule,
            SAISIE (aucun défaut : le kWh/100 km est une caractéristique du
            véhicule et de l'usage).
        fenetre_recharge: les heures de recharge, SAISIES.
        rendement_recharge_pct: pertes de charge, SAISIES. Absent ⇒ aucune
            perte appliquée, et le bilan le dit (jamais un rendement supposé).
        mode: ``'immediat'`` (défaut, CALX261) conserve EXACTEMENT le
            comportement d'aujourd'hui — répartition uniforme sur la
            fenêtre. ``'pv_optimise'`` exige ``production_horaire`` et place
            l'énergie d'abord sur les heures de surplus de production dans
            la fenêtre saisie ; le reliquat non couvert par le surplus est
            publié séparément (``energie_reseau_kwh``), jamais masqué.
        production_horaire: la production PV horaire (même longueur que
            ``longueur``), REQUISE quand ``mode='pv_optimise'``.
        puissance_borne_kw: la puissance de la borne de recharge, SAISIE
            (CALX262). Plafonne l'énergie horaire à cette puissance ; le
            reliquat qui ne tient pas dans la fenêtre à cause de ce plafond
            est publié séparément (``energie_non_placee_kwh``) avec la
            mention de la fenêtre trop courte. Absente ⇒ aucun plafond, et
            le bilan le DIT (comportement d'aujourd'hui).

    Raises:
        ChargeInvalide: paramètre manquant ou illisible, en le NOMMANT.
    """
    km = _obligatoire(km_par_jour, champ='vehicule.km_par_jour',
                      libelle='Le kilométrage quotidien', positif=False)
    conso = _obligatoire(kwh_par_100km, champ='vehicule.kwh_par_100km',
                         libelle='La consommation (kWh/100 km)')
    heures = _fenetre(fenetre_recharge, champ='vehicule.fenetre_recharge',
                      libelle='La fenêtre de recharge')

    if mode not in MODES_RECHARGE_VEHICULE:
        raise ChargeInvalide(
            f'Le mode de recharge « {mode} » est inconnu — les modes '
            f'acceptés sont {", ".join(MODES_RECHARGE_VEHICULE)}.',
            champ='vehicule.mode')

    energie = km / 100.0 * conso
    hypotheses = [MENTION_REPARTITION]
    if rendement_recharge_pct is None:
        hypotheses.append(
            'Aucun rendement de recharge saisi : l’énergie prise au réseau '
            'est celle de la batterie du véhicule, sans perte ajoutée.')
    else:
        rendement = _obligatoire(
            rendement_recharge_pct, champ='vehicule.rendement_recharge_pct',
            libelle='Le rendement de recharge')
        if rendement <= 0 or rendement > 100:
            raise ChargeInvalide(
                'Le rendement de recharge se compte en pourcentage entre 0 et '
                f'100 (reçu : {rendement}).',
                champ='vehicule.rendement_recharge_pct')
        energie = energie / (rendement / 100.0)

    plafond = None
    if puissance_borne_kw is not None:
        plafond = _obligatoire(
            puissance_borne_kw, champ='vehicule.puissance_borne_kw',
            libelle='La puissance de la borne de recharge')
    else:
        hypotheses.append(
            'Aucune puissance de borne saisie : aucun plafond horaire '
            "n'est appliqué (comportement d'aujourd'hui).")

    parametres = {
        'km_par_jour': km, 'kwh_par_100km': conso,
        'fenetre_recharge': heures,
        'rendement_recharge_pct': rendement_recharge_pct,
        'mode': mode, 'puissance_borne_kw': puissance_borne_kw,
    }

    if mode == 'pv_optimise':
        if not production_horaire:
            raise ChargeInvalide(
                'Le mode « pv_optimise » a besoin de '
                '« vehicule.production_horaire » (la production PV de '
                'chaque heure) : sans elle, aucun surplus ne peut être '
                'identifié.', champ='vehicule.production_horaire')
        courbe, energie_reseau = _placer_sur_surplus(
            energie, heures, production_horaire, longueur=longueur,
            heure_de_depart=heure_de_depart)
        hypotheses.append(
            "Mode « pv_optimise » : l'énergie est placée d'abord sur les "
            'heures de surplus de production dans la fenêtre saisie ; le '
            "reliquat non couvert par le surplus est publié en "
            '« energie_reseau_kwh », jamais masqué.')
    else:
        courbe = _repartir(energie, heures, longueur=longueur,
                           heure_de_depart=heure_de_depart)
        energie_reseau = 0.0

    energie_non_placee = 0.0
    if plafond is not None:
        courbe, energie_non_placee = _borner_puissance(courbe, plafond)
        if energie_non_placee > 0:
            hypotheses.append(
                'La puissance de la borne saisie ne laisse pas passer '
                'toute l’énergie sur la fenêtre de recharge : la fenêtre '
                'est trop courte pour cette borne — le reliquat est publié '
                'en « energie_non_placee_kwh ».')

    return {
        'type': 'vehicule',
        'libelle': 'Véhicule électrique',
        'energie_journaliere_kwh': round(energie, 4),
        'courbe': [round(valeur, 6) for valeur in courbe],
        'energie_reseau_kwh': round(energie_reseau, 4),
        'energie_non_placee_kwh': round(energie_non_placee, 4),
        'parametres': parametres,
        'hypotheses': hypotheses,
    }


def _points_cop(cop_points):
    """Valide les points ``{t_ext_c, cop}`` SAISIS — au moins deux, chacun lu.

    Aucune extrapolation n'est permise (CALX264) : ``_interpoler_cop`` a
    besoin d'un jeu de points TRIÉ et NOMBRÉ pour employer le point extrême
    hors plage plutôt que de deviner au-delà.
    """
    points = list(cop_points or [])
    if len(points) < 2:
        raise ChargeInvalide(
            'Le COP par température (« pac.cop_points ») demande au moins '
            f'deux points SAISIS (reçu : {len(points)}) — un seul point ne '
            "permet aucune interpolation, et PV*SOL cite typiquement quatre "
            'points (A2/W35, A-7/W35, A7/W35, A10/W35).',
            champ='pac.cop_points')
    lus = []
    for rang, point in enumerate(points):
        t_ext = _nombre_signe(
            (point or {}).get('t_ext_c'), champ=f'pac.cop_points[{rang}].t_ext_c',
            libelle=f'La température du point {rang} de « cop_points »')
        cop_point = _obligatoire(
            (point or {}).get('cop'), champ=f'pac.cop_points[{rang}].cop',
            libelle=f'Le COP du point {rang} de « cop_points »')
        lus.append({'t_ext_c': t_ext, 'cop': cop_point})
    return sorted(lus, key=lambda point: point['t_ext_c'])


def _interpoler_cop(temperature, points_tries):
    """Le COP à ``temperature`` — interpolation LINÉAIRE, extrapolation INTERDITE.

    Hors plage des points saisis, le point EXTRÊME le plus proche est
    employé et l'appelant est informé (``hors_plage=True``) pour porter la
    mention dans le bilan — jamais un COP prolongé au-delà de ce qui a été
    mesuré/saisi.
    """
    plus_bas, plus_haut = points_tries[0], points_tries[-1]
    if temperature <= plus_bas['t_ext_c']:
        return plus_bas['cop'], temperature < plus_bas['t_ext_c']
    if temperature >= plus_haut['t_ext_c']:
        return plus_haut['cop'], temperature > plus_haut['t_ext_c']
    for gauche, droite in zip(points_tries, points_tries[1:]):
        if gauche['t_ext_c'] <= temperature <= droite['t_ext_c']:
            ecart = droite['t_ext_c'] - gauche['t_ext_c']
            fraction = ((temperature - gauche['t_ext_c']) / ecart
                        if ecart else 0.0)
            cop = gauche['cop'] + (droite['cop'] - gauche['cop']) * fraction
            return cop, False
    return plus_haut['cop'], False  # pragma: no cover — bornes couvrent tout


def courbe_pac(*, puissance_kw=None, cop=None, cop_points=None,
               temperature_horaire=None, heures_fonctionnement=None,
               facteur_saison=None, longueur=24, heure_de_depart=0):
    """La charge horaire d'une POMPE À CHALEUR — tout est saisi.

    Args:
        puissance_kw: la puissance THERMIQUE appelée, SAISIE.
        cop: le coefficient de performance SAISI, CONSTANT sur la journée —
            entrée admise TELLE QUELLE (comportement d'aujourd'hui) quand
            ``cop_points`` est absent.
        cop_points: ``[{t_ext_c, cop}]`` SAISIS (au moins deux) — le COP
            dépend alors de la température de chaque heure active
            (``temperature_horaire``), interpolé LINÉAIREMENT entre les
            points ; hors plage, le point extrême est employé et la mention
            le dit (parité PV*SOL — les points A2/W35, A-7/W35, A7/W35,
            A10/W35 sont un EXEMPLE de saisie cité par la tâche, jamais un
            défaut : https://help.valentin-software.com/pvsol/en/calculation/thermal-system/).
        temperature_horaire: la température extérieure de CHAQUE heure de la
            courbe rendue (même longueur que ``longueur``), REQUISE avec
            ``cop_points`` — sans elle, aucune température par heure n'est
            connue pour interpoler.
        heures_fonctionnement: les heures de marche, SAISIES.
        facteur_saison: coefficient de saisonnalité SAISI (1 = saison de
            référence). Absent ⇒ 1, et le bilan le dit.

    Raises:
        ChargeInvalide: paramètre manquant ou illisible, en le NOMMANT —
            dont un ``cop_points`` à moins de deux points, ou
            ``temperature_horaire`` absent/mal dimensionné alors que
            ``cop_points`` est saisi.
    """
    puissance = _obligatoire(puissance_kw, champ='pac.puissance_kw',
                             libelle='La puissance de la pompe à chaleur')
    heures = _fenetre(heures_fonctionnement,
                      champ='pac.heures_fonctionnement',
                      libelle='Les heures de fonctionnement')

    hypotheses = [MENTION_REPARTITION]
    if facteur_saison is None:
        saison = 1.0
        hypotheses.append(
            'Aucun facteur de saison saisi : la charge est publiée pour la '
            'saison de référence, sans pondération inventée.')
    else:
        saison = _obligatoire(facteur_saison, champ='pac.facteur_saison',
                              libelle='Le facteur de saison', positif=False)

    if cop_points is not None:
        points = _points_cop(cop_points)
        if not temperature_horaire:
            raise ChargeInvalide(
                'Le COP par température (« pac.cop_points ») a besoin de '
                '« pac.temperature_horaire » (une température par heure de '
                'la courbe) : sans elle, aucune interpolation ne sait à '
                'quelle température se placer.',
                champ='pac.temperature_horaire')
        temperatures = list(temperature_horaire)
        if len(temperatures) != longueur:
            raise ChargeInvalide(
                f'« pac.temperature_horaire » compte {len(temperatures)} '
                f'valeur(s) au lieu de {longueur} (la longueur de la '
                'courbe) : une température par heure est requise, aucune '
                'ne peut être devinée.', champ='pac.temperature_horaire')

        courbe = [0.0] * longueur
        hors_plage = False
        cops_actifs = []
        for rang in range(longueur):
            heure_du_jour = (int(heure_de_depart) + rang) % 24
            if heure_du_jour not in heures:
                continue
            cop_heure, cette_borne = _interpoler_cop(
                float(temperatures[rang]), points)
            hors_plage = hors_plage or cette_borne
            courbe[rang] = puissance * saison / cop_heure
            cops_actifs.append(cop_heure)
        if hors_plage:
            hypotheses.append(
                "Au moins une heure active porte une température hors de "
                "la plage des points « cop_points » saisis : le point "
                'extrême le plus proche a été employé, AUCUNE '
                'extrapolation.')
        energie = sum(courbe)
        return {
            'type': 'pac',
            'libelle': 'Pompe à chaleur',
            'energie_journaliere_kwh': round(energie, 4),
            'courbe': [round(valeur, 6) for valeur in courbe],
            'parametres': {
                'puissance_kw': puissance, 'cop': cop,
                'cop_points': points,
                'temperature_horaire': temperatures,
                'heures_fonctionnement': heures,
                'facteur_saison': facteur_saison,
                'cop_moyen_actif': (round(sum(cops_actifs) / len(cops_actifs), 4)
                                    if cops_actifs else None),
            },
            'hypotheses': hypotheses,
        }

    coefficient = _obligatoire(cop, champ='pac.cop',
                               libelle='Le COP de la pompe à chaleur')

    # Énergie ÉLECTRIQUE = énergie thermique ÷ COP.
    energie = puissance * len(heures) * saison / coefficient
    return {
        'type': 'pac',
        'libelle': 'Pompe à chaleur',
        'energie_journaliere_kwh': round(energie, 4),
        'courbe': _repartir(energie, heures, longueur=longueur,
                            heure_de_depart=heure_de_depart),
        'parametres': {'puissance_kw': puissance, 'cop': coefficient,
                       'heures_fonctionnement': heures,
                       'facteur_saison': facteur_saison},
        'hypotheses': hypotheses,
    }


def ajouter_charges(courbe_de_base, charges):
    """Ajoute les charges déclarées à la courbe — sans jamais la modifier.

    Args:
        courbe_de_base: la courbe horaire du profil (kWh/h).
        charges: les blocs rendus par :func:`courbe_vehicule` /
            :func:`courbe_pac`.

    Returns:
        dict — ``courbe`` (la somme), ``courbe_de_base`` (INTACTE),
        ``charges`` (chacune avec son énergie et sa courbe, VISIBLE à part),
        ``total_base_kwh``, ``total_charges_kwh``, ``total_kwh``.

    Raises:
        ChargeInvalide: une charge dont la courbe n'a pas la longueur de la
            courbe de base (elles ne décrivent alors pas la même période).
    """
    base = [max(0.0, float(valeur)) for valeur in (courbe_de_base or [])]
    cumul = list(base)
    detail = []
    for rang, charge in enumerate(charges or []):
        courbe = charge.get('courbe') or []
        if len(courbe) != len(base):
            raise ChargeInvalide(
                f'La charge « {charge.get("libelle") or rang} » couvre '
                f'{len(courbe)} heure(s) alors que la courbe de base en '
                f'couvre {len(base)} : elles ne décrivent pas la même '
                'période.', champ=f'charges[{rang}]')
        cumul = [total + ajout for total, ajout in zip(cumul, courbe)]
        detail.append({
            'type': charge.get('type'),
            'libelle': charge.get('libelle'),
            'energie_kwh': round(sum(courbe), 4),
            'courbe': list(courbe),
            'hypotheses': list(charge.get('hypotheses') or []),
        })

    return {
        'courbe': cumul,
        # La courbe de base est rendue TELLE QUELLE : retirer les charges,
        # c'est reprendre cette liste — pas soustraire et espérer.
        'courbe_de_base': base,
        'charges': detail,
        'total_base_kwh': round(sum(base), 4),
        'total_charges_kwh': round(sum(c['energie_kwh'] for c in detail), 4),
        'total_kwh': round(sum(cumul), 4),
    }
