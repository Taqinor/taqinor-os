"""Services du rythme (reference/regles.md « Le rythme », « Les sollicitations »).

Les RÈGLES vivent dans `moteur/rythme.py` (pur) ; ce module les branche sur les données réelles : il lit
`ReglagesRythme` et les `PlanJour` clos, construit l'`EtatRythme`, appelle le moteur, réécrit les
champs changés et enregistre le geste annulable (reference/donnees.md §4).

- `regler_rythme` : `POST rythme/`, SEUL chemin du mode (MAJ-6) ; l'objectif dit s'applique tout de
  suite au `PlanJour` de J s'il n'est pas clos (A2.1).
- `etapes_nocturnes` : étape de nuit appelée par `nocturne.executer` (TCH37) ; remplie par TCH70.
"""
import datetime
from dataclasses import fields, replace
from decimal import Decimal

from django.db import transaction
from django.utils import timezone

from apps.taches.choix import ClePreference, ModeRythme, StatutJour
from apps.taches.models.rythme import ReglagesRythme
from apps.taches.moteur import rythme as moteur
from apps.taches.moteur.gabarits import texte
from apps.taches.selectors.rythme import (
    TYPES_PROPOSITION,
    cartes_de,
    ouvertes,
    plan_du_jour,
    plans_du_rythme,
    preference_de,
    reglages_de,
)
from apps.taches.services.gestes import LISTE_BLANCHE, enregistrer_geste, op_champ

VALEUR_INCONNUE = 'Valeur inconnue.'
#: Extras de l'`EtatRythme` calculés ici (pas des colonnes de `ReglagesRythme`).
EXTRAS_ETAT = frozenset({'objectif', 'comptes_bloc', 'comptes_recents', 'taille_mediane_bloc', 'nb_estimees'})
CHAMPS_ETAT = tuple(f.name for f in fields(moteur.EtatRythme) if f.name not in EXTRAS_ETAT)
DECIMALES_REFERENCE = 2


class ErreursRythme(Exception):
    """400 : `erreurs` = `{"<champ>": ["message"]}`."""

    def __init__(self, erreurs):
        super().__init__(erreurs)
        self.erreurs = erreurs


class SansReglages(Exception):
    """Le compte n'a encore créé aucune tâche : pas de `ReglagesRythme` (invariant 29) → 404."""


def aujourdhui():
    """Le jour local (seule horloge du module ; les tests la remplacent)."""
    return timezone.localdate()


# --- ReglagesRythme ↔ EtatRythme -------------------------------------------------------------

def _en_float(valeur):
    return None if valeur is None else float(valeur)


def _en_decimal(valeur):
    return None if valeur is None else Decimal(str(round(float(valeur), DECIMALES_REFERENCE)))


def jours_evalues(plans, jour):
    """`PlanJour` évalués avant `jour`, chronologiques (seul `evalue` entre au rythme, §6.2)."""
    return [p for p in plans if p.statut_jour == StatutJour.EVALUE and p.jour < jour]


def etat_rythme(reglages, plans, jour):
    """L'`EtatRythme` de `reglages` : ses valeurs + les comptes des jours évalués (≤ 42 jours avant J)
    et ceux du bloc en cours (jours évalués depuis `bloc_debut`, 10 au plus)."""
    valeurs = {nom: getattr(reglages, nom) for nom in CHAMPS_ETAT}
    valeurs['tenir_reference'] = _en_float(reglages.tenir_reference)
    evalues = jours_evalues(plans, jour)
    bloc = [p.compte_rythme for p in evalues if reglages.bloc_debut and p.jour >= reglages.bloc_debut]
    etat = moteur.EtatRythme(**valeurs, comptes_recents=tuple(p.compte_rythme for p in evalues),
                             comptes_bloc=tuple(bloc[:moteur.BLOC_JOURS]))
    return replace(etat, objectif=moteur.objectif_affiche(etat)[0])


def ecrire_etat(reglages, etat):
    """Réécrit sur `reglages` les champs que le moteur a changés → opérations annulables (les champs
    de la liste blanche `reglages_rythme`, donnees.md §4 ; les autres sont écrits sans opération)."""
    avant, changes = {}, []
    for nom in CHAMPS_ETAT:
        neuf = getattr(etat, nom)
        if nom == 'tenir_reference':
            neuf = _en_decimal(neuf)
        if getattr(reglages, nom) != neuf:
            avant[nom] = getattr(reglages, nom)
            setattr(reglages, nom, neuf)
            changes.append(nom)
    if not changes:
        return []
    reglages.save(update_fields=[*changes, 'updated_at'])
    blanche = LISTE_BLANCHE['reglages_rythme']
    return [op_champ('reglages_rythme', reglages, nom, avant[nom]) for nom in changes if nom in blanche]


# --- Objectif du jour ------------------------------------------------------------------------

def jours_courts(user):
    """Jours courts DITS (`Preference.jours_courts`, entiers 0-6) ; absents = aucun."""
    preference = preference_de(user, ClePreference.JOURS_COURTS)
    valeur = preference.valeur if preference is not None else []
    return {v for v in valeur if isinstance(v, int) and not isinstance(v, bool)} if isinstance(valeur, list) else set()


def objectif_du_jour(etat, jour, courts):
    """Objectif du `jour` : celui en vigueur, `max(1, N − 1)` un jour court (§6.3) ; `None` en libre."""
    nb = moteur.objectif_affiche(etat)[0]
    if nb is None or jour.weekday() not in courts:
        return nb
    return max(moteur.PALIER_MIN, nb - 1)


def appliquer_au_jour(user, jour, etat):
    """L'objectif s'applique TOUT DE SUITE au `PlanJour` de J s'il existe et n'est pas clos (A2.1)."""
    plan = plan_du_jour(user, jour, verrou=True)
    if plan is None or plan.cloture_le is not None:
        return []
    neuf = objectif_du_jour(etat, jour, jours_courts(user))
    if plan.objectif_du_jour == neuf:
        return []
    avant = plan.objectif_du_jour
    plan.objectif_du_jour = neuf
    plan.save(update_fields=['objectif_du_jour', 'updated_at'])
    return [op_champ('plan_jour', plan, 'objectif_du_jour', avant)]


def abandonner_propositions(user, jour):
    """Une bascule abandonne la proposition en attente (§6.7) : elle sort de « ouverte » ce jour
    (`expire_le` = veille) ; la nuit la marque `expiree` (seule à poser cette réponse)."""
    veille = jour - datetime.timedelta(days=1)
    ouvertes(cartes_de(user), jour).filter(type__in=TYPES_PROPOSITION).update(
        expire_le=veille, updated_at=timezone.now())


# --- POST rythme/ ----------------------------------------------------------------------------

def _entier(valeur):
    if isinstance(valeur, bool):
        raise ErreursRythme({'objectif': [moteur.OBJECTIF_INVALIDE]})
    try:
        return int(valeur)
    except (TypeError, ValueError):
        raise ErreursRythme({'objectif': [moteur.OBJECTIF_INVALIDE]})


def _lire_corps(donnees):
    mode = donnees.get('mode')
    if mode not in ModeRythme.values:
        raise ErreursRythme({'mode': [VALEUR_INCONNUE]})
    objectif = donnees.get('objectif')
    objectif = None if objectif is None else _entier(objectif)
    sens = donnees.get('sens') or None
    if sens is not None and sens not in (moteur.SENS_PLUS, moteur.SENS_MOINS):
        raise ErreursRythme({'sens': [VALEUR_INCONNUE]})
    return mode, objectif, sens


def _cle_confirmation(etat, neuf, objectif, sens):
    """La phrase de confirmation du geste (textes.md « Confirmations de geste »), ou `None`."""
    if objectif is not None:
        return 'objectif_dit'
    if sens is not None:
        return sens
    if neuf.mode == etat.mode:
        return None
    if neuf.mode == ModeRythme.TENIR:
        return 'garder_ce_rythme' if neuf.tenir_fixee_le else 'garder_ce_rythme.provisoire'
    return 'en_faire_plus' if neuf.mode == ModeRythme.POUSSER else 'sans_objectif'


def confirmation(etat, neuf, objectif, sens):
    """Le texte du geste (toast « … · Annuler ») ; vide si rien n'a changé."""
    cle = _cle_confirmation(etat, neuf, objectif, sens)
    if cle is None:
        return ''
    nb, _source, zone = moteur.objectif_affiche(neuf)
    donnees = {'nb': nb}
    if zone is not None:
        donnees.update(R=float(neuf.tenir_reference), bas=zone[0], haut=zone[1])
    return texte('confirmation', cle, donnees)


def _nouvel_etat(etat, mode, objectif, sens, jour):
    if mode == ModeRythme.POUSSER and (objectif is not None or sens is not None):
        try:
            return moteur.objectif_dit(etat, nombre=objectif, sens=sens, jour=jour)
        except moteur.ObjectifInvalide as exc:
            raise ErreursRythme(exc.erreurs)
    return moteur.basculer(etat, mode, jour)


def regler_rythme(user, donnees, jour):
    """`POST rythme/` `{"mode","objectif"?,"sens"?}` → (réglages relus, geste ou `None`).

    Le nombre dit (1-12) ou « plus »/« moins » passe par `moteur.objectif_dit` (le mode devient
    `pousser`) ; un autre mode par `moteur.basculer`. Lève `ErreursRythme` (400), `SansReglages` (404).
    """
    mode, objectif, sens = _lire_corps(donnees)
    with transaction.atomic():
        reglages = reglages_de(user, verrou=True)
        if reglages is None:
            raise SansReglages()
        etat = etat_rythme(reglages, plans_du_rythme(user, jour), jour)
        neuf = _nouvel_etat(etat, mode, objectif, sens, jour)
        operations = ecrire_etat(reglages, neuf)
        if neuf.mode != etat.mode:
            abandonner_propositions(user, jour)
        operations += appliquer_au_jour(user, jour, neuf)
        geste = None
        if operations:
            geste = enregistrer_geste(user, 'rythme', confirmation(etat, neuf, objectif, sens), operations)
    return reglages, geste


def reglages_ou_defauts(user):
    """La `ReglagesRythme` de `user`, ou une instance NON enregistrée aux valeurs par défaut (lecture
    d'un compte qui n'a encore créé aucune tâche : rien n'est créé, invariant 29)."""
    reglages = reglages_de(user)
    if reglages is not None:
        return reglages
    return ReglagesRythme(company_id=user.company_id, proprietaire=user)


def etapes_nocturnes(company_id, jour):
    """Nuit du `jour` : jour clos, blocs, propositions, dérive, constats (si « Comprendre mon
    rythme »), révélation `revue`, cartes expirées, push `ignoree`, pauses à 14 (api.md §9). Livrée
    vide par TCH37, remplie par TCH70."""
    return None
