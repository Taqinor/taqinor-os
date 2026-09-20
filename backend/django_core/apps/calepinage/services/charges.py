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


def courbe_vehicule(*, km_par_jour=None, kwh_par_100km=None,
                    fenetre_recharge=None, longueur=24, heure_de_depart=0,
                    rendement_recharge_pct=None):
    """La charge horaire d'un VÉHICULE ÉLECTRIQUE — tout est saisi.

    Args:
        km_par_jour / kwh_par_100km: la consommation RÉELLE du véhicule,
            SAISIE (aucun défaut : le kWh/100 km est une caractéristique du
            véhicule et de l'usage).
        fenetre_recharge: les heures de recharge, SAISIES.
        rendement_recharge_pct: pertes de charge, SAISIES. Absent ⇒ aucune
            perte appliquée, et le bilan le dit (jamais un rendement supposé).

    Raises:
        ChargeInvalide: paramètre manquant ou illisible, en le NOMMANT.
    """
    km = _obligatoire(km_par_jour, champ='vehicule.km_par_jour',
                      libelle='Le kilométrage quotidien', positif=False)
    conso = _obligatoire(kwh_par_100km, champ='vehicule.kwh_par_100km',
                         libelle='La consommation (kWh/100 km)')
    heures = _fenetre(fenetre_recharge, champ='vehicule.fenetre_recharge',
                      libelle='La fenêtre de recharge')

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

    return {
        'type': 'vehicule',
        'libelle': 'Véhicule électrique',
        'energie_journaliere_kwh': round(energie, 4),
        'courbe': _repartir(energie, heures, longueur=longueur,
                            heure_de_depart=heure_de_depart),
        'parametres': {'km_par_jour': km, 'kwh_par_100km': conso,
                       'fenetre_recharge': heures,
                       'rendement_recharge_pct': rendement_recharge_pct},
        'hypotheses': hypotheses,
    }


def courbe_pac(*, puissance_kw=None, cop=None, heures_fonctionnement=None,
               facteur_saison=None, longueur=24, heure_de_depart=0):
    """La charge horaire d'une POMPE À CHALEUR — tout est saisi.

    Args:
        puissance_kw: la puissance THERMIQUE appelée, SAISIE.
        cop: le coefficient de performance SAISI (aucun COP par défaut : il
            dépend de la machine ET de la température extérieure).
        heures_fonctionnement: les heures de marche, SAISIES.
        facteur_saison: coefficient de saisonnalité SAISI (1 = saison de
            référence). Absent ⇒ 1, et le bilan le dit.
    """
    puissance = _obligatoire(puissance_kw, champ='pac.puissance_kw',
                             libelle='La puissance de la pompe à chaleur')
    coefficient = _obligatoire(cop, champ='pac.cop',
                               libelle='Le COP de la pompe à chaleur')
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
