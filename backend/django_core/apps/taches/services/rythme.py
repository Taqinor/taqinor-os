"""Services du rythme (reference/regles.md « Le rythme », « Les sollicitations »).

Les RÈGLES vivent dans `moteur/rythme.py` (pur) ; ce module les branche sur les données réelles : il lit
`ReglagesRythme` et les `PlanJour` clos, construit l'`EtatRythme`, appelle le moteur, réécrit les
champs changés et enregistre le geste annulable (reference/donnees.md §4).

- `regler_rythme` : `POST rythme/`, SEUL chemin du mode (MAJ-6) ; l'objectif dit s'applique tout de
  suite au `PlanJour` de J s'il n'est pas clos (A2.1).
- `etapes_nocturnes` : étape de nuit appelée par `nocturne.executer` (TCH37) ; remplie par TCH70.
"""
import datetime
import re
from dataclasses import fields, replace
from decimal import Decimal
from types import SimpleNamespace

from django.db import transaction
from django.utils import timezone

from apps.taches.choix import (
    CanalIncitation,
    ClePreference,
    FamilleSuggestion,
    ModeRythme,
    ReponseIncitation,
    SourceObjectif,
    SourcePreference,
    StatutJour,
    TypeIncitationEcran,
)
from apps.taches.models.journee import PlanJour
from apps.taches.models.rythme import Preference, ReglagesRythme
from apps.taches.moteur import rythme as moteur
from apps.taches.moteur.gabarits import texte
from apps.taches.selectors.base import _du_compte, taches_de
from apps.taches.selectors.rythme import (
    TYPES_PROPOSITION,
    cartes_de,
    ouvertes,
    plan_du_jour,
    plans_du_rythme,
    preference_de,
    preferences_de,
    reglages_de,
    taches_faites_le,
)
from apps.taches.serializers.formes import FREQUENCES_ROUTINE
from apps.taches.services.gestes import (
    LISTE_BLANCHE,
    enregistrer_geste,
    op_champ,
    op_creation,
    op_suppression_dure,
)
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


# --- POST/DELETE preferences/, GET coach/entete/ (TCH68) -------------------------------------

CLE_INCONNUE = 'Clé inconnue.'
HEURE_ATTENDUE = 'Heure attendue (HH:MM).'
CAPACITE_HORS_BORNES = 'Entre 30 et 720 minutes.'
CONGES_A_L_ENVERS = 'La date de fin précède la date de début.'
UN_JOUR_AU_MOINS = 'Garde au moins un jour travaillé.'
NOTE_TROP_LONGUE = '200 caractères au plus.'
NOTES_TROP_NOMBREUSES = '10 phrases au plus.'
REVUE_INVALIDE = 'Choisis un jour, Auto ou Éteinte.'
CAPACITE_MIN, CAPACITE_MAX = 30, 720
NOTE_LONGUEUR_MAX, NOTES_MAX = 200, 10
JOURS_SEMAINE = 7
ETEINT, AUTO = 'off', 'auto'
_HEURE = re.compile(r'^([01]\d|2[0-3]):[0-5]\d$')


def _invalide(message):
    raise ErreursRythme({'valeur': [message]})


def _entier_borne(valeur, bas, haut, message):
    if isinstance(valeur, bool) or not isinstance(valeur, int) or not bas <= valeur <= haut:
        _invalide(message)
    return valeur


def _heure_ou_off(valeur):
    if valeur == ETEINT or (isinstance(valeur, str) and _HEURE.match(valeur)):
        return valeur
    return _invalide(HEURE_ATTENDUE)


def _heure_seule(valeur):
    if isinstance(valeur, str) and _HEURE.match(valeur):
        return valeur
    return _invalide(HEURE_ATTENDUE)


def _jours_travailles(valeur):
    if not (isinstance(valeur, str) and len(valeur) == JOURS_SEMAINE and set(valeur) <= {'0', '1'}) \
            or '1' not in valeur:
        _invalide(UN_JOUR_AU_MOINS)
    return valeur


def _jours_courts(valeur):
    if not isinstance(valeur, list):
        _invalide(VALEUR_INCONNUE)
    return sorted({_entier_borne(v, 0, JOURS_SEMAINE - 1, VALEUR_INCONNUE) for v in valeur})


def _conges(valeur):
    if not isinstance(valeur, list):
        _invalide(VALEUR_INCONNUE)
    periodes = []
    for periode in valeur:
        try:
            du = datetime.date.fromisoformat(periode['du'])
            au = datetime.date.fromisoformat(periode['au'])
        except (KeyError, TypeError, ValueError):
            _invalide(VALEUR_INCONNUE)
        if au < du:
            _invalide(CONGES_A_L_ENVERS)
        periodes.append({'du': du.isoformat(), 'au': au.isoformat()})
    return periodes


def _revue(valeur):
    if valeur in (AUTO, ETEINT):
        return valeur
    return _entier_borne(valeur, 0, JOURS_SEMAINE - 1, REVUE_INVALIDE)


def _booleen(valeur):
    if not isinstance(valeur, bool):
        _invalide(VALEUR_INCONNUE)
    return valeur


def _notes(valeur):
    if not isinstance(valeur, list) or not all(isinstance(v, str) for v in valeur):
        _invalide(VALEUR_INCONNUE)
    if len(valeur) > NOTES_MAX:
        _invalide(NOTES_TROP_NOMBREUSES)
    if any(len(v) > NOTE_LONGUEUR_MAX for v in valeur):
        _invalide(NOTE_TROP_LONGUE)
    return valeur


#: Une validation par clé (reference/donnees.md §2.11) ; une clé absente d'ici (anciens noms
#: `jours_off`, `heure_plan_matin`…) est « Clé inconnue. ».
VALIDATIONS = {
    ClePreference.CAPACITE_JOUR_MIN: lambda v: _entier_borne(v, CAPACITE_MIN, CAPACITE_MAX, CAPACITE_HORS_BORNES),
    ClePreference.JOURS_TRAVAILLES: _jours_travailles,
    ClePreference.JOURS_COURTS: _jours_courts,
    ClePreference.CONGES: _conges,
    ClePreference.HEURE_MATIN: _heure_ou_off,
    ClePreference.RELANCE_JOUR: _heure_ou_off,
    ClePreference.HEURE_SOIR: _heure_ou_off,
    ClePreference.HEURE_LIMITE: _heure_seule,
    ClePreference.REVUE_SEMAINE: _revue,
    ClePreference.ESSENTIEL_LE_MATIN: _booleen,
    ClePreference.NOTE_LIBRE: _notes,
}


def valider_preference(cle, valeur):
    """La valeur normalisée de `cle`, ou `ErreursRythme` (`cle` inconnue, `valeur` hors règle)."""
    validation = VALIDATIONS.get(cle)
    if validation is None:
        raise ErreursRythme({'cle': [CLE_INCONNUE]})
    return validation(valeur)


def poser_preference(user, cle, valeur, source):
    """`POST preferences/` : pose ce que `user` a DIT (`source` = `copilote` sous l'en-tête assistant,
    sinon `ecran`) → geste annulable (ou `None` si rien n'a changé)."""
    valeur = valider_preference(cle, valeur)
    with transaction.atomic():
        reglages_de(user, verrou=True)  # sérialise les écritures du compte
        operations = ecrire_preference(user, cle, valeur, source)
        if not operations:
            return None
        return enregistrer_geste(user, 'preference', ClePreference(cle).label, operations)


def retirer_preference(user, cle):
    """`DELETE preferences/{cle}/` : la clé revient à son défaut → geste annulable ; `Introuvable` si
    la clé est inconnue ou n'a jamais été dite."""
    if cle not in VALIDATIONS:
        raise Introuvable()
    with transaction.atomic():
        preference = preference_de(user, cle, verrou=True)
        if preference is None:
            raise Introuvable()
        operation = op_suppression_dure('preference', preference, {
            'cle': preference.cle, 'valeur': preference.valeur, 'source': preference.source})
        preference.delete()
        return enregistrer_geste(user, 'preference', ClePreference(cle).label, [operation])


def faites_aujourdhui(user, jour):
    """Le compte du rythme du `jour` (tâches) : `moteur.compte_du_jour` sur les tâches faites ce
    jour, une routine (quotidienne ou jours ouvrés, intervalle 1) comptée 0."""
    taches = [SimpleNamespace(statut=t.statut, parent_id=t.parent_id, estimation_minutes=t.estimation_minutes,
                              routine=bool(t.recurrence_id and t.recurrence.frequence in FREQUENCES_ROUTINE
                                           and t.recurrence.intervalle == 1))
              for t in taches_faites_le(user, jour)]
    return moteur.compte_du_jour(taches, ())[0]


#: En-tête de tour (textes.md « Boutons des cartes ») : deux lignes, 300 caractères au plus.
ENTETE_MAX = 300
_JOURS_NOMS = ('lundi', 'mardi', 'mercredi', 'jeudi', 'vendredi', 'samedi', 'dimanche')
_JOURS_ABREGES = ('lun.', 'mar.', 'mer.', 'jeu.', 'ven.', 'sam.', 'dim.')


def _ligne_rythme(etat, faites, objectif):
    nb, source, _zone = moteur.objectif_affiche(etat)
    tete = f'Rythme : {ModeRythme(etat.mode).label}'
    if nb is None:
        return f'{tete} · {faites} faite' + ('s' if faites > 1 else '')
    return f'{tete} · objectif {nb} ({SourceObjectif(source).label.lower()}) · {faites} sur {objectif}'


def _dite(cle, valeur):
    """Une préférence dite, en clair et sans contenu libre (jamais `note_libre`)."""
    if cle == ClePreference.HEURE_LIMITE:
        return f"sollicitations jusqu'à {valeur}"
    if cle == ClePreference.JOURS_COURTS:
        noms = ', '.join(_JOURS_NOMS[j] for j in valeur)
        return f"jour{'s' if len(valeur) > 1 else ''} court{'s' if len(valeur) > 1 else ''} : {noms}"
    libelle = ClePreference(cle).label.lower()
    if cle == ClePreference.JOURS_TRAVAILLES:
        valeur = ' '.join(_JOURS_ABREGES[i] for i, c in enumerate(valeur) if c == '1')
    elif cle == ClePreference.CONGES:
        valeur = ', '.join(f"du {p['du']} au {p['au']}" for p in valeur)
    elif cle == ClePreference.REVUE_SEMAINE and isinstance(valeur, int):
        valeur = _JOURS_NOMS[valeur]
    elif cle == ClePreference.ESSENTIEL_LE_MATIN:
        valeur = 'oui' if valeur else 'non'
    return f'{libelle} : {"éteint" if valeur == ETEINT else valeur}'


def entete_coach(user, jour):
    """`GET coach/entete/` : la ligne du rythme et, s'il en a dit, ses préférences — 300 caractères
    au plus pour les deux, formées depuis des clés fermées (jamais un titre, une note, un projet)."""
    reglages = reglages_ou_defauts(user)
    etat = etat_rythme(reglages, plans_du_rythme(user, jour), jour)
    lignes = [_ligne_rythme(etat, faites_aujourdhui(user, jour), objectif_du_jour(etat, jour, jours_courts(user)))]
    dites = [_dite(p.cle, p.valeur) for p in preferences_de(user) if p.cle != ClePreference.NOTE_LIBRE]
    if dites:
        lignes.append('Préférences dites : ' + ' · '.join(dites))
    reste, sortie = ENTETE_MAX, []
    for ligne in lignes:
        sortie.append(ligne[:reste])
        reste -= len(sortie[-1])
    return [ligne for ligne in sortie if ligne]


# --- PATCH reglages/ (TCH69) -----------------------------------------------------------------

NON_MODIFIABLE = 'Non modifiable ici.'
RESERVE_ADMIN = 'Réservé à un administrateur.'
#: Liste blanche de `PATCH reglages/` (reference/api.md §4 `reglages/`) ; tout autre champ → 400.
BOOLEENS_REGLAGES = ('titres_notifications', 'titres_calendrier', 'titres_tuile', 'messages_sans_delai',
                     'suggestions_societe', 'erp_dans_journee', 'comprendre_mon_rythme')
LISTE_BLANCHE_REGLAGES = frozenset({*BOOLEENS_REGLAGES, 'rappel_avant_bloc_min', 'projet_arret_jours',
                                    'familles_suggestions', 'pauses_sollicitations'})
ARRET_MIN, ARRET_MAX = 5, 30  # `projet_arret_jours` (donnees.md §2.10)
MINUTES_MAX = 32767  # borne de `PositiveSmallIntegerField`
#: Cartes du rythme effacées quand « Comprendre mon rythme » est coupé (donnees.md §8).
CARTES_DU_PROFIL = (TypeIncitationEcran.CONSTAT, *TYPES_PROPOSITION)
#: Champs de rythme de `ReglagesRythme` remis à nul (ou zéro) avec le profil (donnees.md §8).
PROFIL_REGLAGES = {'tenir_reference': None, 'tenir_fixee_le': None, 'tenir_silence_jusquau': None,
                   'ref_taille_min': None, 'meilleur_tenu': None, 'echec_niveau': None, 'echec_le': None,
                   'echec_n': 0}
#: Champs de rythme du `PlanJour` effacés avec le profil (donnees.md §8).
PROFIL_PLANS = {'statut_jour': '', 'compte_rythme': 0, 'micro_comptees': 0, 'taille_mediane_min': None}


class ReserveAdministrateur(Exception):
    """`suggestions_societe` modifié par un non-administrateur : 403, rien d'écrit."""


def _type_pause(pause):
    return pause.get('type') if isinstance(pause, dict) else pause


def _pauses(valeur, reglages):
    """« Réactiver » : la liste dite ne peut que RETIRER des types en pause (la nuit seule en ajoute)."""
    actuelles = list(reglages.pauses_sollicitations or [])
    if not isinstance(valeur, list):
        raise ErreursRythme({'pauses_sollicitations': [VALEUR_INCONNUE]})
    gardes = {_type_pause(p) for p in valeur}
    if not gardes <= {_type_pause(p) for p in actuelles}:
        raise ErreursRythme({'pauses_sollicitations': [VALEUR_INCONNUE]})
    return [p for p in actuelles if _type_pause(p) in gardes]


def _valeur_reglage(champ, valeur, reglages):
    """La valeur validée de `champ` (liste blanche), ou `ErreursRythme`."""
    erreur = ErreursRythme({champ: [VALEUR_INCONNUE]})
    if champ in BOOLEENS_REGLAGES:
        if not isinstance(valeur, bool):
            raise erreur
        return valeur
    if champ == 'projet_arret_jours':
        if isinstance(valeur, bool) or not isinstance(valeur, int) or not ARRET_MIN <= valeur <= ARRET_MAX:
            raise erreur
        return valeur
    if champ == 'rappel_avant_bloc_min':
        if valeur is not None and (isinstance(valeur, bool) or not isinstance(valeur, int)
                                   or not 1 <= valeur <= MINUTES_MAX):
            raise erreur
        return valeur
    if champ == 'familles_suggestions':
        if not isinstance(valeur, list) or not set(valeur) <= set(FamilleSuggestion.values):
            raise erreur
        return [f for f in FamilleSuggestion.values if f in valeur]
    return _pauses(valeur, reglages)


def _valeurs_reglages(donnees, reglages, est_admin):
    hors_liste = {champ: [NON_MODIFIABLE] for champ in donnees if champ not in LISTE_BLANCHE_REGLAGES}
    if hors_liste:
        raise ErreursRythme(hors_liste)
    if 'suggestions_societe' in donnees and not est_admin:
        raise ReserveAdministrateur()
    return {champ: _valeur_reglage(champ, valeur, reglages) for champ, valeur in donnees.items()}


def effacer_profil(user, reglages):
    """« Comprendre mon rythme » coupé : rien n'est plus calculé ni GARDÉ (donnees.md §8) — cartes
    du rythme supprimées, état de « Garder ce rythme » et mémoires remis à nul, champs de rythme des
    `PlanJour` effacés. Le mode et l'objectif restent."""
    cartes_de(user).filter(type__in=CARTES_DU_PROFIL).delete()
    for champ, valeur in PROFIL_REGLAGES.items():
        setattr(reglages, champ, valeur)
    _du_compte(PlanJour.objects, user).update(**PROFIL_PLANS, updated_at=timezone.now())
    return list(PROFIL_REGLAGES)


def modifier_reglages(user, donnees, *, est_admin):
    """`PATCH reglages/` (liste blanche, sans geste) → réglages relus. `titres_notifications` pose
    `titres_notifications_demande_le` (question du 1er rappel, A17-T4). Lève `ErreursRythme` (400),
    `ReserveAdministrateur` (403), `SansReglages` (404)."""
    if not hasattr(donnees, 'items'):
        raise ErreursRythme({'non_field_errors': [VALEUR_INCONNUE]})
    with transaction.atomic():
        reglages = reglages_de(user, verrou=True)
        if reglages is None:
            raise SansReglages()
        valeurs = _valeurs_reglages(dict(donnees.items()), reglages, est_admin)
        coupe = reglages.comprendre_mon_rythme and valeurs.get('comprendre_mon_rythme') is False
        for champ, valeur in valeurs.items():
            setattr(reglages, champ, valeur)
        ecrits = [*valeurs, 'updated_at']
        if 'titres_notifications' in valeurs:
            reglages.titres_notifications_demande_le = timezone.now()
            ecrits.append('titres_notifications_demande_le')
        if coupe:
            ecrits += effacer_profil(user, reglages)
        reglages.save(update_fields=ecrits)
    return reglages


def etapes_nocturnes(company_id, jour):
    """Nuit du `jour` : jour clos, blocs, propositions, dérive, constats (si « Comprendre mon
    rythme »), révélation `revue`, cartes expirées, push `ignoree`, pauses à 14 (api.md §9). Livrée
    vide par TCH37, remplie par TCH70."""
    return None
