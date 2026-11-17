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

from apps.taches.choix import (
    CanalIncitation,
    ClePreference,
    ModeRythme,
    ReponseIncitation,
    SourcePreference,
    StatutJour,
    TypeIncitationEcran,
)
from apps.taches.models.rythme import Preference, ReglagesRythme
from apps.taches.moteur import rythme as moteur
from apps.taches.moteur.gabarits import texte
from apps.taches.selectors.base import taches_de
from apps.taches.selectors.rythme import (
    TYPES_PROPOSITION,
    cartes_de,
    ouvertes,
    plan_du_jour,
    plans_du_rythme,
    preference_de,
    reglages_de,
)
from apps.taches.services.gestes import LISTE_BLANCHE, enregistrer_geste, op_champ, op_creation
from apps.taches.services.planification import planifier

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


def appliquer_au_jour(user, jour, etat, *, avant_plan=False):
    """L'objectif s'applique TOUT DE SUITE au `PlanJour` de J s'il existe et n'est pas clos (A2.1).

    `avant_plan` (réponse à une carte, §6.5 point 6) : seulement si le plan du jour n'est pas encore
    validé (`planifie_le` nul) ; sinon la réponse vaut le lendemain (rien n'est écrit sur J)."""
    plan = plan_du_jour(user, jour, verrou=True)
    if plan is None or plan.cloture_le is not None:
        return []
    if avant_plan and plan.planifie_le is not None:
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


# --- Préférences dites (écrites par une carte, l'écran ou le Copilote) -----------------------

def ecrire_preference(user, cle, valeur, source):
    """Pose `cle` = `valeur` (validée par l'appelant) → opérations annulables (création ou valeur)."""
    preference = preference_de(user, cle, verrou=True)
    if preference is None:
        preference = Preference.objects.create(company_id=user.company_id, proprietaire=user, cle=cle,
                                               valeur=valeur, source=source)
        return [op_creation('preference', preference)]
    if preference.valeur == valeur and preference.source == source:
        return []
    avant = preference.valeur
    preference.valeur, preference.source = valeur, source
    preference.save(update_fields=['valeur', 'source', 'dite_le', 'updated_at'])
    return [op_champ('preference', preference, 'valeur', avant)]


# --- POST rythme/propositions/{id}/repondre/ (TCH67) ----------------------------------------

REPONSE_INCONNUE = 'Réponse inconnue.'
#: Refus de suite à partir desquels « Garder ce rythme » s'ajoute à la carte `monter` (§6.5 point 6).
REFUS_AVANT_GARDER = 3
#: Réponses permises par carte (reference/donnees.md §1 « Réponses permises ») ; `ignoree` et
#: `expiree` sont posées par la nuit seule, jamais par cette route.
_R = ReponseIncitation
REPONSES_PALIER = {
    'monter': {_R.OUI, _R.PAS_MAINTENANT},
    'baisser': {_R.OUI, _R.GARDER},
    'premier': {_R.OUI, _R.GARDER},
    'journee_type': {_R.OUI, _R.PAS_MAINTENANT},
}
REPONSES_PAR_TYPE = {
    TypeIncitationEcran.DERIVE_TENIR: {_R.GARDER, _R.PASSER},
    TypeIncitationEcran.GARDE_TAILLE: {_R.TACHES_CHANGEES, _R.OK},
    TypeIncitationEcran.CONSTAT: {_R.OUI, _R.PAS_MAINTENANT},
    TypeIncitationEcran.PAUSE: {_R.REACTIVER, _R.OK},
    TypeIncitationEcran.RETOUR: {_R.REMETTRE_DANS_PROPOSE, _R.UNE_PAR_UNE},
    TypeIncitationEcran.REVELATION: {_R.OK},
}
#: Constat d'information (C5) : « OK » seulement.
REPONSES_CONSTAT_INFORMATION = {_R.OK}
CONSTATS_INFORMATION = frozenset({'C5'})
#: Constats dont « Oui » pose une préférence (regles.md §6.9 « Action proposée »).
CONSTATS_ESSENTIEL_LE_MATIN = frozenset({'C1', 'C2'})


class Introuvable(Exception):
    """La carte n'est pas à `user` (ou n'existe pas) : 404, rien d'écrit (invariant 9)."""


class PropositionExpiree(Exception):
    """La carte n'est plus ouverte (répondue ou expirée) : 409 `proposition_expiree`."""


def reponses_permises(carte):
    """L'ensemble des réponses permises à `carte`."""
    if carte.type == TypeIncitationEcran.PROPOSITION_PALIER:
        permises = set(REPONSES_PALIER.get(carte.cle, ()))
        if carte.cle == 'monter' and (carte.donnees or {}).get('refus', 0) >= REFUS_AVANT_GARDER:
            permises.add(_R.GARDER_CE_RYTHME)
        return permises
    if carte.type == TypeIncitationEcran.CONSTAT and carte.cle in CONSTATS_INFORMATION:
        return set(REPONSES_CONSTAT_INFORMATION)
    return set(REPONSES_PAR_TYPE.get(carte.type, ()))


def _palier(etat, carte, reponse, jour):
    """Le nouvel état après la réponse à une carte `proposition_palier` (jamais une baisse imposée :
    seule `oui` à `baisser` descend, un cran, inv. 24)."""
    if reponse == _R.GARDER_CE_RYTHME:
        return moteur.basculer(etat, ModeRythme.TENIR, jour)
    if carte.cle in ('premier', 'journee_type'):
        if reponse == _R.PAS_MAINTENANT:
            return etat
        return moteur.repondre_premier(etat, (carte.donnees or {}).get('type'), reponse)
    # La nuit a clos le bloc (`clore_bloc` sans réponse) ; la réponse applique la décision du bloc.
    return moteur._maj(etat, **moteur._apres_decision(etat, jour, carte.cle, reponse))


def _rythme_repondu(user, reglages, carte, reponse, jour):
    if reglages is None:
        raise SansReglages()
    etat = etat_rythme(reglages, plans_du_rythme(user, jour), jour)
    if carte.type == TypeIncitationEcran.PROPOSITION_PALIER:
        neuf = _palier(etat, carte, reponse, jour)
    elif reponse == _R.PASSER:  # dérive : R = arrondir(moyenne), fixée ce jour (§6.6)
        moyenne = float((carte.donnees or {}).get('moyenne'))
        neuf = replace(etat, tenir_reference=moteur.arrondir(moyenne), tenir_fixee_le=jour)
    else:
        return []
    operations = ecrire_etat(reglages, neuf)
    if neuf.mode != etat.mode:
        abandonner_propositions(user, jour)
    return operations + appliquer_au_jour(user, jour, neuf, avant_plan=True)


def _reactiver(reglages, carte):
    """« Le réactiver » : le type sort de `pauses_sollicitations` (regles.md §7 « Pause »)."""
    if reglages is None:
        return []
    avant = list(reglages.pauses_sollicitations or [])
    reste = [p for p in avant if (p.get('type') if isinstance(p, dict) else p) != carte.cle]
    if reste == avant:
        return []
    reglages.pauses_sollicitations = reste
    reglages.save(update_fields=['pauses_sollicitations', 'updated_at'])
    return [op_champ('reglages_rythme', reglages, 'pauses_sollicitations', avant)]


def _constat_accepte(user, carte):
    """L'action d'un constat accepté qui pose une préférence (source `carte`) ; les autres (C4, C6,
    C7, C8) vivent par la carte acceptée elle-même (I13)."""
    if carte.cle in CONSTATS_ESSENTIEL_LE_MATIN:
        return ecrire_preference(user, ClePreference.ESSENTIEL_LE_MATIN, True, SourcePreference.CARTE)
    if carte.cle == 'C3':
        jour_court = (carte.donnees or {}).get('jour')
        if not isinstance(jour_court, int):
            return []
        valeur = sorted(jours_courts(user) | {jour_court})
        return ecrire_preference(user, ClePreference.JOURS_COURTS, valeur, SourcePreference.CARTE)
    return []


def _remettre_dans_propose(user, carte):
    """Retour d'absence : les tâches de la carte à `jour_prevu` nul, sans report (§4.8)."""
    operations = []
    for tache in taches_de(user).filter(pk__in=(carte.donnees or {}).get('ids', [])):
        planifier(tache, acteur=user, jour_prevu=None, compter_report=False, collecte=operations)
    return operations


def _effets(user, reglages, carte, reponse, jour):
    """Ce que la réponse ÉCRIT (opérations annulables) ; rien pour une réponse sans effet."""
    if carte.type in (TypeIncitationEcran.PROPOSITION_PALIER, TypeIncitationEcran.DERIVE_TENIR):
        return _rythme_repondu(user, reglages, carte, reponse, jour)
    if carte.type == TypeIncitationEcran.PAUSE and reponse == _R.REACTIVER:
        return _reactiver(reglages, carte)
    if carte.type == TypeIncitationEcran.CONSTAT and reponse == _R.OUI:
        return _constat_accepte(user, carte)
    if carte.type == TypeIncitationEcran.RETOUR and reponse == _R.REMETTRE_DANS_PROPOSE:
        return _remettre_dans_propose(user, carte)
    return []


def _carte_a_repondre(user, carte_id, reponse, jour):
    carte = cartes_de(user).select_for_update().filter(pk=carte_id, canal=CanalIncitation.ECRAN).first()
    if carte is None:
        raise Introuvable()
    if reponse not in reponses_permises(carte):
        raise ErreursRythme({'reponse': [REPONSE_INCONNUE]})
    if carte.reponse or carte.repondu_le is not None or (carte.expire_le is not None and carte.expire_le < jour):
        raise PropositionExpiree()
    return carte


def _libelle_choisi(carte, reponse):
    """Le texte du geste = le libellé du bouton choisi (textes.md « Cartes à réponse »)."""
    from apps.taches.serializers.rythme import rendre_carte  # import local : la forme lit ce module
    _texte, boutons = rendre_carte(carte)
    return next((libelle for libelle, choix in boutons if choix == reponse), '')


def repondre_carte(user, carte_id, reponse, jour):
    """Répond `reponse` à la carte `carte_id` de `user` → (carte relue, geste).

    Sous verrou (réglages puis carte) : deux réponses concurrentes ne comptent jamais deux refus.
    Lève `Introuvable` (404), `ErreursRythme` (400 « Réponse inconnue. »), `PropositionExpiree` (409).
    """
    with transaction.atomic():
        reglages = reglages_de(user, verrou=True)
        carte = _carte_a_repondre(user, carte_id, reponse, jour)
        message = _libelle_choisi(carte, reponse)
        operations = _effets(user, reglages, carte, reponse, jour)
        avant_reponse, avant_le = carte.reponse, carte.repondu_le
        carte.reponse, carte.repondu_le = reponse, timezone.now()
        carte.save(update_fields=['reponse', 'repondu_le', 'updated_at'])
        operations += [op_champ('incitation_coach', carte, 'reponse', avant_reponse),
                       op_champ('incitation_coach', carte, 'repondu_le', avant_le)]
        geste = enregistrer_geste(user, 'decision', message, operations)
    return carte, geste


def etapes_nocturnes(company_id, jour):
    """Nuit du `jour` : jour clos, blocs, propositions, dérive, constats (si « Comprendre mon
    rythme »), révélation `revue`, cartes expirées, push `ignoree`, pauses à 14 (api.md §9). Livrée
    vide par TCH37, remplie par TCH70."""
    return None
