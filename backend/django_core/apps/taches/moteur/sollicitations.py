"""Sollicitations pures (reference/regles.md §7) : quand, quoi, combien, décroissance.

Module pur : bibliothèque standard seule, aucune base, aucune horloge vivante
(le « maintenant » est toujours passé en argument).
"""
from dataclasses import dataclass
from datetime import datetime, time, timedelta

PLAN_MATIN = 'plan_matin'
RELANCE = 'relance'
BILAN_SOIR = 'bilan_soir'
REVUE_SEMAINE = 'revue_semaine'

# Ordre de priorité quand plusieurs types sont dus au même tick (regles.md §7).
ORDRE_PRIORITE = (PLAN_MATIN, RELANCE, BILAN_SOIR, REVUE_SEMAINE)
TYPES_PLAFONNES = frozenset(ORDRE_PRIORITE)

MOTIF_ECHEANCE = 'echeance'
MOTIF_DERIVE = 'derive'
MOTIF_NEGLIGE = 'neglige'
ORDRE_MOTIFS = (MOTIF_ECHEANCE, MOTIF_DERIVE, MOTIF_NEGLIGE)

ETAT_NORMAL = 'normal'
ETAT_PAUSE = 'pause'

PLAFOND_PAR_JOUR = 3
IGNOREES_AVANT_PAUSE = 14
LARGEUR_TICK = timedelta(minutes=15)
NB_VARIANTES = 3

HEURE_MATIN_DEFAUT = time(8, 30)
HEURE_RELANCE_DEFAUT = time(15, 0)
HEURE_SOIR_DEFAUT = time(18, 0)
HEURE_LIMITE_DEFAUT = time(20, 0)


@dataclass(frozen=True)
class Fenetre:
    """Heures de travail de la société (regles.md §0.1)."""
    debut: time
    fin: time


@dataclass(frozen=True)
class PrefsSollicitation:
    """Ce que `due` doit savoir d'un compte, lu une fois par l'appelant.

    Une heure `None` = type « off ». `revue_semaine` : entier 0-6 (lundi = 0),
    `'auto'` (dernier jour travaillé de la semaine) ou `'off'`.
    """
    heure_matin: object = HEURE_MATIN_DEFAUT
    relance_jour: object = HEURE_RELANCE_DEFAUT
    heure_soir: object = HEURE_SOIR_DEFAUT
    heure_limite: time = HEURE_LIMITE_DEFAUT
    revue_semaine: object = 'auto'
    dernier_jour_travaille_semaine: bool = False
    jour_travaille: bool = True
    en_conge: bool = False
    pauses: tuple = ()
    compte_actif: bool = True
    compte_interne: bool = True
    module_actif: bool = True
    a_reglages_rythme: bool = True
    balayage_actif: bool = True
    plafond_atteint: bool = False
    plan_valide: bool = False
    nb_faites: int = 0
    nb_jour_et_propose: int = 0
    motif_relance: object = None


def variante(ordinal):
    """Rotation des trois formulations : `date.toordinal() % 3`."""
    return ordinal % NB_VARIANTES


def _heure_du_type(type_, prefs):
    """Heure réglée du type, ou `None` (off)."""
    if type_ == PLAN_MATIN:
        return prefs.heure_matin
    if type_ == RELANCE:
        return prefs.relance_jour
    if type_ in (BILAN_SOIR, REVUE_SEMAINE):
        return prefs.heure_soir
    raise ValueError(f'type de sollicitation inconnu : {type_!r}')


def _est_jour_de_revue(maintenant, prefs):
    reglage = prefs.revue_semaine
    if reglage == 'off' or reglage is None:
        return False
    if reglage == 'auto':
        return bool(prefs.dernier_jour_travaille_semaine)
    return maintenant.weekday() == reglage


def _condition_d_envoi(type_, maintenant, prefs):
    """Le « Envoyé si » de chaque type (tableau de regles.md §7)."""
    if type_ == PLAN_MATIN:
        return (not prefs.plan_valide) and prefs.nb_jour_et_propose >= 1
    if type_ == RELANCE:
        return prefs.motif_relance is not None
    revue = _est_jour_de_revue(maintenant, prefs)
    if type_ == REVUE_SEMAINE:
        return revue
    return (not revue) and (prefs.plan_valide or prefs.nb_faites >= 1)


def _hors_service(type_, prefs):
    """Raison de saut tenant au compte ou au module, sinon `None`."""
    if not prefs.module_actif:
        return 'module_eteint'
    if not prefs.balayage_actif:
        return 'coupe_circuit'
    if not (prefs.compte_actif and prefs.compte_interne):
        return 'compte'
    if not prefs.a_reglages_rythme:
        return 'sans_reglages'
    if prefs.en_conge:
        return 'conge'
    if not prefs.jour_travaille:
        return 'jour_non_travaille'
    if type_ in prefs.pauses:
        return 'pause'
    return None


def raison_saut(type_, maintenant, prefs, fenetre):
    """Pourquoi le type est SAUTÉ à ce tick (`None` = il peut partir).

    Sauté signifie jamais différé : le tick suivant sort de la fenêtre de
    15 minutes, donc rien n'est rattrapé plus tard.
    """
    heure = _heure_du_type(type_, prefs)
    if heure is None:
        return 'off'
    raison = _hors_service(type_, prefs)
    if raison:
        return raison
    t = maintenant.time()
    if not (fenetre.debut <= t < fenetre.fin):
        return 'fenetre_fermee'
    if t >= prefs.heure_limite:
        return 'heure_limite'
    if prefs.plafond_atteint:
        return 'plafond'
    if not _condition_d_envoi(type_, maintenant, prefs):
        return 'condition'
    return None


def _dans_le_tick(heure, maintenant):
    debut = datetime.combine(maintenant.date(), heure, tzinfo=maintenant.tzinfo)
    return debut <= maintenant < debut + LARGEUR_TICK


def due(type_, maintenant, prefs, fenetre):
    """Vrai si le tick `maintenant` est dans [heure, heure + 15 min) ET non sauté."""
    heure = _heure_du_type(type_, prefs)
    if heure is None or not _dans_le_tick(heure, maintenant):
        return False
    return raison_saut(type_, maintenant, prefs, fenetre) is None


def departager(types_dus):
    """Deux types dus au même tick : (retenu, sautés), selon `ORDRE_PRIORITE`."""
    ordonnes = [t for t in ORDRE_PRIORITE if t in set(types_dus)]
    if not ordonnes:
        return None, ()
    return ordonnes[0], tuple(ordonnes[1:])


def choisir_relance(candidats):
    """Motif de la relance : échéance, puis dérive, puis projet négligé ; sinon `None`."""
    presents = set(candidats)
    inconnus = presents - set(ORDRE_MOTIFS)
    if inconnus:
        raise ValueError(f'motif de relance inconnu : {sorted(inconnus)!r}')
    for motif in ORDRE_MOTIFS:
        if motif in presents:
            return motif
    return None


def plafond_atteint(journal):
    """Vrai si 3 envois push plafonnés sont déjà partis ce jour.

    `journal` : types des envois push effectivement partis ce jour. Les cartes
    d'écran, les rappels posés et le push de test n'y comptent pas.
    """
    envois = sum(1 for type_ in journal if type_ in TYPES_PLAFONNES)
    return envois >= PLAFOND_PAR_JOUR


def etat_decroissance(ignorees):
    """`'pause'` après 14 ignorées de suite, sinon `'normal'`.

    `ignorees` : suite chronologique de booléens (vrai = ignorée) ; une
    ouverture (faux) remet la série à zéro.
    """
    serie = 0
    for ignoree in ignorees:
        serie = serie + 1 if ignoree else 0
    return ETAT_PAUSE if serie >= IGNOREES_AVANT_PAUSE else ETAT_NORMAL


__all__ = (
    'Fenetre', 'PrefsSollicitation', 'variante', 'due', 'raison_saut', 'departager',
    'choisir_relance', 'plafond_atteint', 'etat_decroissance',
)
