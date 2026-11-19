"""Formes RYTHME et PROPOSITION (reference/api.md §1 ; textes.md « Mon rythme », « Phrases du rythme »).

- `forme_rythme(user, reglages, jour, …)` : le dict RYTHME servi par `GET rythme/` et rendu par toute
  écriture du rythme (`POST rythme/`, `preferences/`, `propositions/{id}/repondre/`).
- `forme_proposition(carte, …)` : une carte à réponse (`IncitationCoach`) en forme PROPOSITION — texte
  et boutons rendus à la LECTURE par `moteur.gabarits` (aucun texte stocké, I9) ; une carte répondue
  n'a plus de boutons. Réutilisable par la carte du moment (`aujourdhui/`).

Aucun nombre n'est écrit ici : tout vient des `PlanJour` clos et du moteur pur.
"""
import copy
import datetime

from rest_framework import serializers

from apps.taches.choix import ModeRythme, StatutJour, TypeIncitationEcran
from apps.taches.confidentialite import nom_pour
from apps.taches.moteur import rythme as moteur
from apps.taches.moteur.gabarits import boutons, texte
from apps.taches.selectors.base import jours_travailles_de, projets_de
from apps.taches.selectors.rythme import (
    constats_ouverts, masque_travaille, plans_du_rythme, preferences_de, proposition_ouverte,
)
from apps.taches.serializers.formes import PROPOSITION, PropositionSerializer, contexte
from apps.taches.services import revelations
from apps.taches.services.rythme import etat_rythme

#: Jours TRAVAILLÉS (une barre, vide si `sans_donnees`) : la série de Mon rythme (regles.md §6.2).
STATUTS_TRAVAILLES = frozenset({StatutJour.EVALUE, StatutJour.SANS_DONNEES})
#: La fenêtre de la proposition : les 10 derniers jours travaillés.
SERIE_JOURS = moteur.BLOC_JOURS

#: Révélations (textes.md « Révélations ») : une phrase, un seul bouton « OK ».
TEXTES_REVELATION = {
    'mon_iphone': 'Mets tes tâches sur ton iPhone : notifications, calendrier, Siri et tuile.',
    'ranger_copilote': '{n} tâches à trier : le Copilote peut les ranger dans tes projets.',
    'planifier_projet': 'Ton premier projet : le planifier en quelques questions ?',
    'revue': 'Fin de ta première semaine : fais le point, projet par projet.',
}
BOUTONS_REVELATION = (('OK', 'ok'),)
#: Constat d'information (sans action) : un seul bouton « OK » (textes.md §4.2).
CONSTATS_INFORMATION = frozenset({'C5'})
_HORODATAGE = serializers.DateTimeField()


def _date(valeur):
    return valeur.isoformat() if valeur is not None else None


# --- PROPOSITION ----------------------------------------------------------------------------

def _gabarit(carte, assistant):
    """(type de gabarit, clé du texte, clé des boutons) d'une carte d'écran."""
    type_, cle = carte.type, carte.cle
    if type_ == TypeIncitationEcran.PROPOSITION_PALIER:
        return 'carte', f'palier.{cle}', f'palier.{cle}'
    if type_ == TypeIncitationEcran.DERIVE_TENIR:
        return 'carte', f'derive.{cle}', f'derive.{cle}'
    if type_ in (TypeIncitationEcran.GARDE_TAILLE, TypeIncitationEcran.PAUSE):
        return 'carte', type_, type_
    if type_ == TypeIncitationEcran.RETOUR:
        return 'retour', 'carte', 'retour'
    information = 'constat.information' if cle in CONSTATS_INFORMATION else 'constat'
    # Le Copilote ne reçoit jamais le nom d'un projet : C8 sans nom sous l'en-tête assistant.
    return 'constat', ('C8.ecran' if cle == 'C8' and not assistant else cle), information


def _heure(valeur):
    if isinstance(valeur, str):
        return datetime.time.fromisoformat(valeur)
    return valeur


def _variables(carte, projets):
    donnees = dict(carte.donnees or {})
    if 'heure' in donnees:
        donnees['heure'] = _heure(donnees['heure'])
    if 'projet_id' in donnees:
        donnees['projet'] = (projets or {}).get(donnees['projet_id'])
    return donnees


def _texte_revelation(carte, donnees):
    return TEXTES_REVELATION[carte.cle].format(**donnees), list(BOUTONS_REVELATION)


def rendre_carte(carte, *, assistant=False, projets=None):
    """(texte, boutons `[(libellé, réponse)]`) d'une carte, rendus à la lecture."""
    if carte.type == TypeIncitationEcran.REVELATION:
        return _texte_revelation(carte, revelations.donnees_lues(carte)[0])
    type_, cle_texte, cle_boutons = _gabarit(carte, assistant)
    donnees = _variables(carte, projets)
    return (texte(type_, cle_texte, donnees, nom_pour=nom_pour),
            [tuple(b) for b in boutons(cle_boutons, donnees)])


def projets_cites(user, cartes):
    """`{id: Projet}` des projets cités par des cartes (`donnees.projet_id`), en une requête."""
    ids = {(c.donnees or {}).get('projet_id') for c in cartes} - {None}
    return {p.pk: p for p in projets_de(user).filter(pk__in=ids)} if ids else {}


def forme_proposition(carte, *, assistant=False, projets=None):
    """Une carte en forme PROPOSITION ; répondue, elle n'a plus de boutons. Une révélation est servie
    avec ses nombres lus maintenant (`donnees` comprises) ; ouverte et sans plus rien à dire, `None`."""
    if carte.type == TypeIncitationEcran.REVELATION:
        donnees, vivante = revelations.donnees_lues(carte)
        if not vivante and not carte.reponse:
            return None
        texte_, boutons_ = _texte_revelation(carte, donnees)
        carte = copy.copy(carte)  # la ligne n'est pas réécrite : seule la forme servie porte le compte lu
        carte.donnees = donnees
    else:
        texte_, boutons_ = rendre_carte(carte, assistant=assistant, projets=projets)
    if carte.reponse:
        boutons_ = []
    calculs = {(PROPOSITION, carte.pk): {'texte': texte_, 'boutons': boutons_}}
    return dict(PropositionSerializer(carte, context=contexte(assistant=assistant, calculs=calculs)).data)


# --- RYTHME ---------------------------------------------------------------------------------

def _sans_donnees(jour):
    """Un jour travaillé que la nuit n'a pas évalué : une barre VIDE (`faites` 0, aucun objectif)."""
    return {'jour': _date(jour), 'statut_jour': StatutJour.SANS_DONNEES, 'faites': 0, 'objectif': None,
            'essentiel_faites': 0, 'essentiel_prevues': 0, 'plan_tenues': 0, 'plan_lignes': 0}


def _barre(plan):
    return {'jour': _date(plan.jour), 'statut_jour': plan.statut_jour, 'faites': plan.compte_rythme,
            'objectif': plan.objectif_du_jour, 'essentiel_faites': plan.essentiels_faits,
            'essentiel_prevues': plan.essentiels_choisis, 'plan_tenues': plan.plan_faites,
            'plan_lignes': plan.plan_prevues}


def _serie(user, plans, jour):
    """Les 10 derniers jours TRAVAILLÉS (R2-120, regles.md §6.2) : une entrée par jour travaillé (calendrier de
    la société ∩ ses jours dits − ses congés), du premier jour lu à la veille. Un jour évalué porte ses
    nombres ; un jour travaillé que la nuit n'a pas évalué (aucune ligne, ou ligne sans statut) est servi
    `sans_donnees`, barre vide : jamais un jour absent, jamais un nombre inventé. Un jour que sa ligne dit
    férié (`non_ouvre`) ou en congé n'a pas de barre."""
    if not plans:
        return []
    par_jour = {p.jour: p for p in plans}
    travailles = set(jours_travailles_de(user, min(par_jour), jour - datetime.timedelta(days=1)))
    barres = {}
    for date in travailles | {p.jour for p in plans if p.statut_jour in STATUTS_TRAVAILLES}:
        plan = par_jour.get(date)
        if plan is None or not plan.statut_jour:
            if date in travailles:
                barres[date] = _sans_donnees(date)
        elif plan.statut_jour in STATUTS_TRAVAILLES:
            barres[date] = _barre(plan)
    return [barres[date] for date in sorted(barres)][-SERIE_JOURS:]


def _trace(nb, serie):
    """« {N} faites ou plus {tenus} jour(s) sur {sur} » sur la série (« jour » à 0 ou 1, comme la revue) ;
    `None` sans objectif ni série."""
    if nb is None or not serie:
        return None
    tenus = sum(1 for jour in serie if jour['faites'] >= nb)
    return f"{nb} faites ou plus {tenus} jour{'s' if tenus > 1 else ''} sur {len(serie)}"


def _bloc(etat):
    """Le bloc en cours (POUSSER seulement) : jours évalués, jours à N ou plus, sur 10."""
    if etat.mode != ModeRythme.POUSSER:
        return None
    palier = etat.palier if etat.palier is not None else moteur.PALIER_DEFAUT
    comptes = etat.comptes_bloc if etat.bloc_debut is not None else etat.comptes_recents[-moteur.BLOC_JOURS:]
    return {'jours': len(comptes), 'tenus': sum(1 for c in comptes if c >= palier), 'sur': moteur.BLOC_JOURS}


def _tenir(etat):
    """« Garder ce rythme » : la référence R (provisoire tant qu'elle n'est pas fixée) et le silence."""
    if etat.mode != ModeRythme.TENIR:
        return None
    return {'reference': etat.tenir_reference, 'provisoire': etat.tenir_fixee_le is None,
            'fixee_le': _date(etat.tenir_fixee_le), 'silence_jusquau': _date(etat.tenir_silence_jusquau)}


def _repere(etat, comprendre):
    p60 = moteur.repere_p60(etat.comptes_recents) if comprendre else None
    return None if p60 is None else {'p60': p60, 'jours': moteur.REPERE_JOURS}


def _preferences(user):
    return [{'cle': p.cle, 'valeur': p.valeur, 'source': p.source,
             'dite_le': _HORODATAGE.to_representation(p.dite_le)} for p in preferences_de(user)]


def _cartes(user, jour, assistant):
    proposition = proposition_ouverte(user, jour)
    constats = constats_ouverts(user, jour)
    projets = projets_cites(user, [*constats, *([proposition] if proposition else [])])
    rendue = forme_proposition(proposition, assistant=assistant, projets=projets) if proposition else None
    return rendue, [forme_proposition(c, assistant=assistant, projets=projets) for c in constats]


def forme_rythme(user, reglages, jour, *, assistant=False, geste_id=None):
    """Le dict RYTHME de `user` au `jour` (`reglages` : la `ReglagesRythme`, enregistrée ou défauts)."""
    plans = plans_du_rythme(user, jour)
    etat = etat_rythme(reglages, plans, jour)
    nb, source, zone = moteur.objectif_affiche(etat)
    # Revue F2 tour 2 #6 : « Comprendre mon rythme » coupé, ni série ni trace (donc `trace` nulle).
    serie = _serie(user, plans, jour) if reglages.comprendre_mon_rythme else []
    proposition, constats = _cartes(user, jour, assistant)
    return {
        'mode': etat.mode,
        'comprendre_mon_rythme': reglages.comprendre_mon_rythme,
        'objectif': {'nb': nb, 'source': source, 'mode': etat.mode, 'zone': list(zone) if zone else None},
        'trace': _trace(nb, serie),
        'bloc': _bloc(etat),
        'tenir': _tenir(etat),
        'proposition': proposition,
        'serie': serie,
        'constats': constats,
        'repere': _repere(etat, reglages.comprendre_mon_rythme),
        'preferences': _preferences(user),
        'jours_travailles': masque_travaille(user),
        'geste_id': geste_id,
    }
