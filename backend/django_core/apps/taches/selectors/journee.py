"""La journée côté serveur (reference/regles.md « La journée » ; donnees.md invariants 2, 3, 10-13, 32).

Branche les règles PURES de `moteur/classement.py` et `moteur/rythme.py` sur les données réelles ;
aucune règle n'est réécrite ici :

- `taches_de_la_journee(user, jour)` : le préfiltre UNIQUE (invariant 10) — écran, pastille, flux,
  tuile ;
- `lire_journee(user, jour)` : chaque élément (tâche du préfiltre, activité ERP ouverte) placé par
  `classement.placer` dans sa section, chaque section dans son ordre d'affichage (invariant 32) ;
- `compter_journee(user, jour)` : LA pastille (invariant 11) ;
- `progression_du_jour(...)` : la forme PROGRESSION (invariant 13, regles.md « Capacité, progression,
  pastille »).

Heure murale (invariant 14) : `fait_le` et `created_at` sont lus à l'heure locale de la société.
"""
import datetime
import logging
from dataclasses import dataclass, field

from django.db.models import BooleanField, ExpressionWrapper, Q
from django.utils import timezone

from apps.taches.choix import (
    CanalIncitation, ClePreference, FamilleObligation, Moment, SectionJournee, StatutProjet, StatutTache,
    TypeIncitationEcran)
from apps.taches.confidentialite import est_confidentielle
from apps.taches.models.journee import LignePlanJour, PlanJour
from apps.taches.models.projets import RevueProjet
from apps.taches.models.rythme import IncitationCoach, Preference, ReglagesRythme
from apps.taches.models.taches import Tache
from apps.taches.moteur import classement
from apps.taches.moteur.rythme import EtatRythme, compte_du_jour, objectif_affiche
from apps.taches.serializers.formes import FREQUENCES_ROUTINE
from apps.taches.selectors.base import jours_travailles_de, taches_de

logger = logging.getLogger(__name__)

TACHE = classement.TACHE
ACTIVITE = classement.ACTIVITE
OUVERTS = (StatutTache.A_FAIRE, StatutTache.EN_ATTENTE)
CLOS = (StatutTache.FAIT, StatutTache.ANNULE)
PASTILLE_MAX = 99
#: Fenêtre des jours travaillés lue autour de J : assez pour « 2 jours travaillés » et la bande 2 de
#: `cle_tri` (n ≤ 3), et pour l'historique de la capacité (28 jours).
JOURS_AVANT = 28
JOURS_APRES = 60
#: Historique de la capacité (regles.md §3.6) : 9 derniers jours travaillés, ≥ 5 dans les 28 jours.
JOURS_CAPACITE = 9
#: Sections dont les lignes sont rangées d'abord par heure (Prévu, regles.md §3.1).
SECTIONS_A_L_HEURE = classement.SECTIONS_GARDEES
#: Une tâche ouverte bloquée par un prérequis vivant et encore ouvert (invariant 6).
BLOQUEE = (Q(bloquee_par__isnull=False, bloquee_par__is_deleted=False)
           & ~Q(bloquee_par__statut__in=CLOS))


# --- Bornes d'un jour local ---------------------------------------------------------------------

def bornes_du_jour(jour):
    """(début, fin) aware du jour LOCAL `jour` (fuseau de la société)."""
    lendemain = jour + datetime.timedelta(days=1)
    return (timezone.make_aware(datetime.datetime.combine(jour, datetime.time.min)),
            timezone.make_aware(datetime.datetime.combine(lendemain, datetime.time.min)))


def _local(instant):
    """Heure murale naïve d'un instant (None reste None)."""
    if instant is None:
        return None
    if timezone.is_aware(instant):
        instant = timezone.localtime(instant)
    return instant.replace(tzinfo=None)


def _du_compte(modele, user):
    if getattr(user, 'company_id', None) is None or getattr(user, 'pk', None) is None:
        return modele.objects.none()
    return modele.objects.filter(company_id=user.company_id, proprietaire=user)


# --- Le préfiltre (invariant 10) -----------------------------------------------------------------

def taches_de_la_journee(user, jour):
    """Tâches du préfiltre de la journée de `user` au jour `jour` : vivantes, `parent` nul, non
    bloquées, et soit ouvertes hors « En réserve » d'un projet actif (ou sans projet et triées), soit
    faites ce jour-là (heure locale) QUEL QUE SOIT l'état de leur projet : une faite du jour reste dans
    « Faites », l'essentiel et les gardées faites même si son projet est terminé ou mis en pause le
    jour même — comme `compte_faites` la compte (revue F2 tour 2 #1). Une faite est toujours triée
    (clore pose `triee_le`)."""
    debut, fin = bornes_du_jour(jour)
    rattachee = (Q(projet__isnull=False, projet__statut=StatutProjet.ACTIF, projet__is_deleted=False)
                 | Q(projet__isnull=True, triee_le__isnull=False))
    ouverte = Q(statut__in=OUVERTS, quelque_jour=False)
    faite = Q(statut=StatutTache.FAIT, fait_le__gte=debut, fait_le__lt=fin)
    return (taches_de(user).filter(parent__isnull=True).filter((rattachee & ouverte) | faite)
            .exclude(BLOQUEE))


# --- Construction des types purs (regles.md §0.1) ------------------------------------------------

def _routine(tache):
    regle = tache.recurrence if tache.recurrence_id else None
    return bool(regle and regle.frequence in FREQUENCES_ROUTINE and regle.intervalle == 1)


def _prerequis_ouvert(tache):
    """Id du prérequis encore ouvert (invariant 6), sinon None — sans lecture si la relation est
    déjà chargée, le préfiltre ayant écarté les tâches bloquées."""
    if not tache.bloquee_par_id:
        return None
    prerequis = tache.bloquee_par
    if prerequis is None or prerequis.is_deleted or prerequis.statut in CLOS:
        return None
    return prerequis.pk


def item_de_tache(tache, focus=frozenset()):
    """`ItemPur` d'une `Tache` (projet, récurrence, parent et prérequis déjà chargés)."""
    projet = tache.projet if tache.projet_id else None
    return classement.ItemPur(
        type=TACHE, id=tache.pk, statut=tache.statut, priorite=tache.priorite,
        projet_id=tache.projet_id, projet_priorite=projet.priorite if projet else None,
        projet_rang=projet.rang if projet else None, focus=tache.projet_id in focus,
        section_id=tache.section_id, parent_id=tache.parent_id, rang_projet=tache.rang_projet,
        rang_jour=tache.rang_jour, jour_prevu=tache.jour_prevu, heure_debut=tache.heure_debut,
        moment=tache.moment, echeance=tache.echeance, echeance_heure=tache.echeance_heure,
        quelque_jour=tache.quelque_jour, bloquee_par=_prerequis_ouvert(tache), triee_le=_local(tache.triee_le),
        estimation_minutes=tache.estimation_minutes, duree_reelle_minutes=tache.duree_reelle_minutes,
        reports=tache.reports, reports_tranches=tache.reports_tranches, fait_le=_local(tache.fait_le),
        routine=_routine(tache), recurrente=tache.recurrence_id is not None, jalon=tache.jalon,
        confidentielle=est_confidentielle(tache), created_at=_local(tache.created_at))


def item_d_activite(activite):
    """`ItemPur` d'une activité ERP ouverte (`records.Activity`) : sa date due est son jour."""
    return classement.ItemPur(
        type=ACTIVITE, id=activite.pk, statut=StatutTache.A_FAIRE, jour_prevu=activite.due_date,
        created_at=_local(getattr(activite, 'created_at', None)))


def plan_pur(plan, lignes):
    """`PlanPur` d'un `PlanJour` (ou None) et de ses lignes (lues par `lignes_du_plan`) ; une ★ n'y est
    `essentielle` que si elle compte (`ligne_essentielle`)."""
    if plan is None:
        return None
    return classement.PlanPur(
        jour=plan.jour, planifie_le=plan.planifie_le, cloture_le=plan.cloture_le,
        allege_le=plan.allege_le, objectif_du_jour=plan.objectif_du_jour,
        lignes=tuple(classement.LignePure(
            tache_id=ligne.tache_id, activite_id=ligne.activite_id, prevue_au_plan=ligne.prevue_au_plan,
            faite=ligne.faite, reportee=ligne.reportee, essentielle=ligne_essentielle(ligne),
            creneau=ligne.creneau, rang=ligne.rang) for ligne in lignes))


# --- La journée lue ------------------------------------------------------------------------------

@dataclass
class Journee:
    """Une journée lue : éléments, placements, sections ordonnées. Clé d'un élément : (type, id)."""
    user: object
    jour: datetime.date
    reglages: object = None
    plan: object = None
    lignes: list = field(default_factory=list)
    plan_pur: object = None
    travailles: frozenset = frozenset()
    items: dict = field(default_factory=dict)
    objets: dict = field(default_factory=dict)
    placements: dict = field(default_factory=dict)
    sections: dict = field(default_factory=dict)
    erp: bool = True

    def objets_de(self, section):
        """Les objets (Tache ou Activity) d'une section, dans l'ordre d'affichage."""
        return [self.objets[cle] for cle in self.sections.get(section, ())]

    def items_de(self, section):
        return [self.items[cle] for cle in self.sections.get(section, ())]

    def ligne_de(self, cle):
        """La `LignePlanJour` d'un élément, ou None."""
        type_, pk = cle
        for ligne in self.lignes:
            if (ligne.tache_id if type_ == TACHE else ligne.activite_id) == pk:
                return ligne
        return None


def reglages_de(user):
    """La `ReglagesRythme` de `user` (None tant qu'il n'a créé aucune tâche, invariant 29)."""
    return _du_compte(ReglagesRythme, user).first()


def plan_du_jour(user, jour):
    """Le `PlanJour` de `user` pour `jour`, ou None."""
    return _du_compte(PlanJour, user).filter(jour=jour).first()


#: LA règle d'une ★ qui compte (progression, nuit, « 3 au plus. ») : ligne `essentielle` dont la tâche est
#: vivante et non abandonnée — une tâche supprimée ou abandonnée après sa ★ ne laisse pas un « essentiel 0
#: sur 1 » fantôme ni ne prend une des 3 places (revue F2 tour 2 #11).
ESSENTIELLE_VIVANTE = Q(essentielle=True, tache__is_deleted=False) & ~Q(tache__statut=StatutTache.ANNULE)


def lignes_du_plan(plan):
    """Les lignes d'un plan, chacune annotée `essentielle_vivante` (`ESSENTIELLE_VIVANTE`) — une requête ;
    aucune sans plan."""
    if plan is None:
        return []
    vivante = ExpressionWrapper(ESSENTIELLE_VIVANTE, output_field=BooleanField())
    return list(plan.ligneplanjour_set.annotate(essentielle_vivante=vivante))


def ligne_essentielle(ligne):
    """La ligne (lue par `lignes_du_plan`) est-elle une ★ qui compte (`ESSENTIELLE_VIVANTE`) ?"""
    return bool(ligne.essentielle_vivante)


def lignes_de_taches_du_jour(user, jour):
    """`{tache_id: LignePlanJour}` du plan de `user` au `jour` — UNE requête, plan absent = vide. Sert
    `essentielle` / `prevue_au_plan` d'un ITEM rendu hors de la journée (projet, revue)."""
    if getattr(user, 'company_id', None) is None or getattr(user, 'pk', None) is None:
        return {}
    lignes = LignePlanJour.objects.filter(company_id=user.company_id, plan__proprietaire=user, plan__jour=jour,
                                          tache__isnull=False)
    return {ligne.tache_id: ligne for ligne in lignes}


def lundi_de(jour):
    return jour - datetime.timedelta(days=jour.weekday())


def projets_de_la_semaine(user, jour):
    """Ids des projets « de la semaine » de `user` (revue de la semaine de `jour`, `focus`)."""
    return frozenset(_du_compte(RevueProjet, user).filter(semaine=lundi_de(jour), focus=True)
                     .values_list('projet_id', flat=True))


def travailles_autour(user, jour):
    """Jours travaillés de `user` dans [J − 28, J + 60] (un seul appel, regles.md §0)."""
    return frozenset(jours_travailles_de(user, jour - datetime.timedelta(days=JOURS_AVANT),
                                         jour + datetime.timedelta(days=JOURS_APRES)))


def activites_de_la_journee(user, jour, reglages):
    """Activités ERP ouvertes dues au plus tard `jour` (`records.selectors.activites_ouvertes_pour`),
    seulement si « Afficher mes activités ERP » est allumé (défaut : oui)."""
    if reglages is not None and not reglages.erp_dans_journee:
        return []
    from apps.records.selectors import activites_ouvertes_pour
    return list(activites_ouvertes_pour(user, jusquau=jour))


def _cle_affichage(section, J, travailles):
    """Ordre d'une section (invariant 32) : à l'heure d'abord dans les sections gardées, puis
    `rang_jour`, puis `cle_tri`."""
    cle_tri = classement.cle_tri_pour(J, travailles)
    if section in SECTIONS_A_L_HEURE:
        return lambda item: classement.cle_section(item, J, travailles)
    return lambda item: (item.rang_jour is None, item.rang_jour, cle_tri(item))


def _ranger(journee):
    """Place chaque élément (`classement.placer`) puis ordonne chaque section."""
    par_section = {}
    for cle, item in journee.items.items():
        placement = classement.placer(item, journee.jour, journee.plan_pur, journee.travailles)
        if placement is None:
            continue
        journee.placements[cle] = placement
        par_section.setdefault(placement.section, []).append(item)
    for section, items in par_section.items():
        items.sort(key=_cle_affichage(section, journee.jour, journee.travailles))
        journee.sections[section] = [(item.type, item.id) for item in items]


def lire_journee(user, jour, *, charger=None, reglages=None, travailles=None, taches=None, focus=None):
    """La journée de `user` au jour `jour`. `charger(qs)` charge les tâches (par défaut : les
    relations que lit un `ItemPur`) ; la forme ITEM passe `serializers.formes.charger_items`.
    `taches` : les tâches du préfiltre DÉJÀ chargées par l'appelant (l'agenda les lit d'un seul
    tenant avec celles de sa période) ; `focus` : `projets_de_la_semaine` déjà lu."""
    reglages = reglages if reglages is not None else reglages_de(user)
    plan = plan_du_jour(user, jour)
    lignes = lignes_du_plan(plan)
    journee = Journee(user=user, jour=jour, reglages=reglages, plan=plan, lignes=lignes,
                      plan_pur=plan_pur(plan, lignes),
                      travailles=travailles if travailles is not None else travailles_autour(user, jour),
                      erp=reglages is None or reglages.erp_dans_journee)
    if focus is None:
        focus = projets_de_la_semaine(user, jour)
    if taches is None:
        qs = taches_de_la_journee(user, jour)
        taches = charger(qs) if charger is not None else qs.select_related(
            'projet', 'recurrence', 'parent', 'parent__projet', 'bloquee_par')
    for tache in taches:
        journee.items[(TACHE, tache.pk)] = item_de_tache(tache, focus)
        journee.objets[(TACHE, tache.pk)] = tache
    for activite in activites_de_la_journee(user, jour, reglages):
        journee.items[(ACTIVITE, activite.pk)] = item_d_activite(activite)
        journee.objets[(ACTIVITE, activite.pk)] = activite
    _ranger(journee)
    return journee


# --- La pastille (invariant 11) ------------------------------------------------------------------

def gardes_ouverts(journee):
    """Clés des éléments OUVERTS et GARDÉS d'Essentiel, Prévu et Ce soir (tâches ET activités)."""
    return [cle for section in classement.SECTIONS_GARDEES for cle in journee.sections.get(section, ())
            if journee.items[cle].statut != StatutTache.FAIT]


def compter_journee(user, jour, journee=None):
    """La pastille : éléments ouverts gardés, plafonnés à 99 ; jamais Proposé, À revoir, En attente,
    À trier ni obligations. Sert `badge/`, `aujourdhui/` et `notify(badge=n)`."""
    journee = journee if journee is not None else lire_journee(user, jour)
    return min(PASTILLE_MAX, len(gardes_ouverts(journee)))


# --- Objectif, capacité, faites, progression -----------------------------------------------------

def etat_rythme(reglages):
    """`EtatRythme` des réglages (défauts du moteur sans réglages)."""
    if reglages is None:
        return EtatRythme()
    tenir = reglages.tenir_reference
    return EtatRythme(mode=reglages.mode, comprendre_mon_rythme=reglages.comprendre_mon_rythme,
                      palier=reglages.palier, palier_source=reglages.palier_source,
                      tenir_reference=float(tenir) if tenir is not None else None)


def objectif_en_vigueur(reglages):
    """Forme OBJECTIF `{nb, source, mode, zone}` de l'objectif EN VIGUEUR (`moteur.rythme.
    objectif_affiche`), sans le jour court : l'objectif d'UN jour, le seul servi, est
    `services.journee.objectif_du_jour` (revue F2 tour 2 #3)."""
    etat = etat_rythme(reglages)
    nb, source, zone = objectif_affiche(etat)
    return {'nb': nb, 'source': str(source), 'mode': str(etat.mode),
            'zone': list(zone) if zone is not None else None}


def objectif_atteint(compte, objectif):
    """« Objectif atteint » (textes.md, lexique : compte ≥ objectif) : le bilan du soir d'un jour ET la
    revue de la semaine qui le compte (revue F2 tour 2 #4) ; `None` sans objectif. Jamais la « journée
    réussie » (essentiel compris, `moteur.rythme.journee_reussie`)."""
    return None if objectif is None else compte >= objectif


def preferences_de(user):
    """{clé: valeur} de toutes les préférences dites par `user` (une requête)."""
    return {ligne.cle: ligne.valeur for ligne in _du_compte(Preference, user)}


def _minutes_historiques(user, jour, travailles):
    """Minutes faites des jours travaillés des 28 jours avant `jour` (PlanJour.minutes_faites > 0),
    chronologiques."""
    debut = jour - datetime.timedelta(days=JOURS_AVANT)
    lignes = (_du_compte(PlanJour, user).filter(jour__gte=debut, jour__lt=jour, minutes_faites__gt=0)
              .order_by('jour').values_list('jour', 'minutes_faites'))
    return [minutes for d, minutes in lignes if d in travailles]


def capacite_du_jour(user, jour, reglages, preferences, travailles):
    """(minutes, source) : réglage dit, sinon médiane des 9 derniers jours travaillés, sinon 240."""
    reglage = preferences.get(ClePreference.CAPACITE_JOUR_MIN)
    reglage = int(reglage) if isinstance(reglage, (int, float)) and not isinstance(reglage, bool) else None
    historique = [] if reglage is not None else _minutes_historiques(user, jour, travailles)
    comprendre = reglages is None or reglages.comprendre_mon_rythme
    minutes, source = classement.capacite(reglage, historique[-JOURS_CAPACITE:], len(historique), comprendre)
    return minutes, str(source)


def faites_du_jour(user, jour):
    """Tâches de `user` passées à `fait` ce jour local (sous-tâches et projets en pause compris :
    `compte_du_jour` décide ce qui compte, regles.md §6.1)."""
    debut, fin = bornes_du_jour(jour)
    taches = (taches_de(user).filter(statut=StatutTache.FAIT, fait_le__gte=debut, fait_le__lt=fin)
              .select_related('recurrence'))
    return [classement.ItemPur(id=t.pk, statut=t.statut, parent_id=t.parent_id, routine=_routine(t),
                               estimation_minutes=t.estimation_minutes) for t in taches]


def activites_closes_du_jour(user, jour):
    """Ids des activités ERP que `user` a closes le jour local `jour` (`records.selectors.
    activites_closes_par`), MOINS celles qui portent une tâche (conversion d'un à-faire, lien) : la
    tâche compte déjà, une même chose n'est jamais comptée deux fois (une conversion clôt sa source
    sans que rien n'ait été fait). Une requête."""
    if getattr(user, 'company_id', None) is None or getattr(user, 'pk', None) is None:
        return []
    from apps.records.selectors import activites_closes_par
    debut, fin = bornes_du_jour(jour)
    portees = (Tache.all_objects.filter(company_id=user.company_id, activite_origine_id__isnull=False)
               .values('activite_origine_id'))
    return list(activites_closes_par(user, debut, fin).exclude(pk__in=portees).values_list('pk', flat=True))


def compte_faites(user, jour, closes=None):
    """(`compte`, `detail`) de `compte_du_jour` : tâches faites ce jour et activités ERP closes par
    lui ce jour (regles.md §6.1). `closes` : `activites_closes_du_jour` déjà lu par l'appelant (il
    le passe aussi à `progression_du_jour`) — aucune lecture de plus."""
    closes = activites_closes_du_jour(user, jour) if closes is None else closes
    return compte_du_jour(faites_du_jour(user, jour), closes)


def ligne_faite(journee, ligne, closes=()):
    """LA règle d'une ligne de plan faite (progression, nuit, donc revue) : `faite` posée, ou sa tâche
    faite aujourd'hui, ou son activité ERP close par lui aujourd'hui (`closes` =
    `activites_closes_du_jour`, la même lecture que le compte : revue F2 tour 2 #2)."""
    if ligne.faite:
        return True
    if ligne.activite_id is not None:
        return ligne.activite_id in closes
    item = journee.items.get((TACHE, ligne.tache_id)) if ligne.tache_id else None
    return item is not None and item.statut == StatutTache.FAIT


def _prevue_au_jour(item, J):
    """Tâche d'Essentiel ou de Prévu (ouverte ou faite aujourd'hui), hors Ce soir."""
    return (item.type == TACHE and classement.gardee_aujourdhui(item, J) and item.moment != Moment.SOIR)


def _minutes_prevues(journee):
    taches = [i for i in journee.items.values() if _prevue_au_jour(i, journee.jour)
              and (i.statut == StatutTache.A_FAIRE
                   or journee.placements.get((TACHE, i.id), classement.Placement('')).section
                   == SectionJournee.FAITES)]
    return sum(i.estimation_minutes or 0 for i in taches), sum(1 for i in taches if i.estimation_minutes is None)


def progression_du_jour(journee, *, faites, detail, capacite, rendez_vous_minutes=0, reprise=False, closes=()):
    """Forme PROGRESSION (api.md §1) : `faites` = `compte_du_jour` ; `prevues` = faites + éléments
    ouverts gardés ; gardées faites sur les lignes `prevue_au_plan` (`ligne_faite`, `closes` = les
    activités ERP closes du jour, lues pour `faites`)."""
    essentielles = [ligne for ligne in journee.lignes if ligne_essentielle(ligne)]
    au_plan = [ligne for ligne in journee.lignes if ligne.prevue_au_plan]
    minutes, sans = _minutes_prevues(journee)
    capacite_minutes, capacite_source = capacite
    activites = [cle for cle in journee.sections.get(SectionJournee.JOURNEE, ()) if cle[0] == ACTIVITE]
    closes = frozenset(closes)
    return {
        'faites': faites, 'detail': dict(detail), 'prevues': faites + len(gardes_ouverts(journee)),
        'essentiel_faites': sum(1 for ligne in essentielles if ligne_faite(journee, ligne, closes)),
        'essentiel_prevues': len(essentielles),
        'plan_tenues': sum(1 for ligne in au_plan if ligne_faite(journee, ligne, closes)),
        'plan_lignes': len(au_plan), 'minutes_prevues': minutes, 'sans_estimation': sans,
        'capacite_minutes': capacite_minutes, 'capacite_source': capacite_source,
        'rendez_vous_minutes': rendez_vous_minutes,
        'disponible_minutes': classement.temps_disponible(capacite_minutes, rendez_vous_minutes),
        'activites_closes': detail.get('activites_closes', 0), 'activites': len(activites),
        'reprise': bool(reprise),
    }


def reprise_du_jour(user, jour):
    """Le jour `jour` est-il une « Reprise » (carte `retour` du jour, répondue ou non, encore vivante) ?
    Même lecture que la carte du moment d'`aujourdhui/` (une requête)."""
    vivante = Q(expire_le__isnull=True) | Q(expire_le__gte=jour)
    return (_du_compte(IncitationCoach, user).filter(canal=CanalIncitation.ECRAN, jour=jour,
                                                     type=TypeIncitationEcran.RETOUR)
            .filter(vivante).exists())


def progression_courante(user, jour):
    """La PROGRESSION de `user` au `jour` telle qu'`aujourdhui/` la rendrait — servie par toute
    TACHE_ECRITE (cocher, reporter, planifier, créer…) pour que l'écran recale sa ligne sans relire la
    journée. Même calcul (`progression_du_jour` sur la journée lue, `compte_faites`, `capacite_du_jour`,
    rendez-vous, reprise) ; un nombre CONSTANT de requêtes, quel que soit le nombre de tâches."""
    reglages = reglages_de(user)
    travailles = travailles_autour(user, jour)
    journee = lire_journee(user, jour, reglages=reglages, travailles=travailles)
    closes = activites_closes_du_jour(user, jour)
    compte, detail = compte_faites(user, jour, closes)
    capacite = capacite_du_jour(user, jour, reglages, preferences_de(user), travailles)
    rendez_vous, _libelles = rendez_vous_pour(user, jour, jour)
    return progression_du_jour(journee, faites=compte, detail=detail, capacite=capacite,
                               rendez_vous_minutes=minutes_de_rendez_vous(user, jour, rendez_vous),
                               reprise=reprise_du_jour(user, jour), closes=closes)


# --- Les obligations du jour (donnees.md §5 `obligations_du_jour`, TCH55) ------------------------

#: Adresse de chaque famille quand la source n'en donne pas (spec-6a §3.5 ; textes.md §2.2).
URL_VISITES = '/visites'
URL_RELANCES = '/crm/relances'
TITRE_TOUCHES = 'Suivi des relances'
#: Familles servies, dans leur ordre d'affichage. `pose` (`reporting.calendar.evenements_assignes`)
#: n'existe pas encore dans le dépôt : la famille est absente tant qu'il manque (dit au rapport).
FAMILLES_LUES = (FamilleObligation.VISITE, FamilleObligation.INTERVENTION, FamilleObligation.TOUCHES)
KIND_INTERVENTION = 'intervention_du_jour'


@dataclass(frozen=True)
class Obligations:
    """Les obligations ERP du jour : lignes (forme d'`aujourdhui.json` « obligations »), familles en
    échec (absentes, jamais une erreur à l'écran) et `peut_cloturer` des activités ERP."""
    lignes: tuple = ()
    echecs: tuple = ()
    peut_cloturer: bool = False


def _obligation(famille, id, titre, jour, url, **extra):
    return {'famille': str(famille), 'id': id, 'titre': titre, 'jour': jour.isoformat(), 'url': url, **extra}


def _visites(user, jour):
    """Visites DU JOUR dont `user` est le commercial (`visites.selectors`), si `visites_voir`."""
    if not user.has_erp_permission('visites_voir'):
        return []
    from apps.visites.selectors import ma_journee_du_commercial
    journee = ma_journee_du_commercial(user.company, user, aujourdhui=jour)
    return [_obligation(FamilleObligation.VISITE, v['id'], f"Visite — {v['lead_nom']}", jour, URL_VISITES)
            for v in journee['visites'] if v['date_prevue'] == jour.isoformat()]


def _interventions(user, jour):
    """Interventions du jour (ou en retard) de `user` (`installations.selectors.affectations_pour`) ;
    le titre est celui que l'ERP donne à la ligne."""
    from apps.installations.selectors import affectations_pour
    return [_obligation(FamilleObligation.INTERVENTION, None, item['title'], jour, item.get('link'))
            for item in affectations_pour(user) if item.get('kind') == KIND_INTERVENTION]


def _touches(user, jour):
    """« Suivi des relances : n » — touches dues aujourd'hui + en retard dont `user` est le
    responsable (`owner=user` : un admin ne compte pas l'équipe), si `crm_voir`."""
    if not user.has_erp_permission('crm_voir'):
        return []
    from apps.crm.selectors import relance_etapes_dues
    du_jour = relance_etapes_dues(user.company, user, scope='today', owner=user, today=jour).count()
    en_retard = relance_etapes_dues(user.company, user, scope='overdue', owner=user, today=jour).count()
    if du_jour + en_retard == 0:
        return []
    return [_obligation(FamilleObligation.TOUCHES, None, TITRE_TOUCHES, jour, URL_RELANCES,
                        nb=du_jour + en_retard, en_retard=en_retard)]


_LECTEURS = {
    FamilleObligation.VISITE: _visites,
    FamilleObligation.INTERVENTION: _interventions,
    FamilleObligation.TOUCHES: _touches,
}


def _peut_cloturer(user):
    from apps.records.selectors import peut_cloturer_activites
    try:
        return bool(peut_cloturer_activites(user))
    except Exception:  # noqa: BLE001 — une source ERP en échec ne casse jamais la journée
        logger.warning('taches : peut_cloturer illisible pour le compte %s', user.pk, exc_info=True)
        return False


def obligations_du_jour(user, jour):
    """Obligations ERP du jour de `user` (lecture seule, par les seules portes publiques des apps) ;
    une famille dont la source lève est ABSENTE et nommée dans `echecs`."""
    if getattr(user, 'company_id', None) is None:
        return Obligations()
    lignes, echecs = [], []
    for famille in FAMILLES_LUES:
        try:
            lignes.extend(_LECTEURS[famille](user, jour))
        except Exception:  # noqa: BLE001 — famille en échec = absente (spec-6a §3.5)
            logger.warning('taches : famille %s illisible pour le compte %s', famille, user.pk, exc_info=True)
            echecs.append(str(famille))
    return Obligations(lignes=tuple(lignes), echecs=tuple(echecs), peut_cloturer=_peut_cloturer(user))


# --- Rendez-vous des agendas externes (donnees.md invariant 35, TCH122) ---------------------------

FENETRE_CACHE_SECONDES = 15 * 60


def fenetre_de_travail(company, jour):
    """Heures de travail de la société le jour `jour`, mises en cache 15 minutes par (société, jour)
    comme les rendez-vous qu'elles bornent (0 requête de plus à chaud)."""
    from django.core.cache import cache

    from apps.taches.moteur.ics import Fenetre
    cle = f'taches:fenetre:{getattr(company, "pk", None)}:{jour.isoformat()}'
    connue = cache.get(cle)
    if connue is None:
        fenetre = _fenetre_lue(company, jour)
        cache.set(cle, (fenetre.debut.isoformat(), fenetre.fin.isoformat()), FENETRE_CACHE_SECONDES)
        return fenetre
    return Fenetre(datetime.time.fromisoformat(connue[0]), datetime.time.fromisoformat(connue[1]))


def _fenetre_lue(company, jour):
    """`crm.horaires.fenetre_du_jour` (la fenêtre des messages que lit aussi `notifications`) ;
    repli 08:30-19:00 de `notifications.selectors`."""
    from apps.notifications.selectors import REPLI_FERMETURE, REPLI_OUVERTURE
    from apps.taches.moteur.ics import Fenetre
    try:
        from apps.crm import horaires
        plage = horaires.fenetre_du_jour(jour, company, canal='whatsapp')
    except Exception:  # noqa: BLE001 — horaires illisibles : la fenêtre de repli, jamais une erreur
        logger.warning('taches : heures de travail illisibles (société %s)', getattr(company, 'pk', '?'),
                       exc_info=True)
        plage = None
    if not plage:
        return Fenetre(REPLI_OUVERTURE, REPLI_FERMETURE)
    return Fenetre(plage[0], plage[1])


def touche_le_jour(rdv, jour):
    """Le rendez-vous occupe-t-il une partie du jour local `jour` ?"""
    debut = datetime.datetime.combine(jour, datetime.time.min)
    fin = debut + datetime.timedelta(days=1)
    return rdv.debut < fin and (rdv.fin > debut or rdv.debut >= debut)


def rendez_vous_pour(user, du, au):
    """(rendez-vous de [du, au] dans l'ordre de début, {agenda_id: libellé}) des agendas ACTIFS de
    `user`, lus par `agenda_externe` (texte en cache 15 min, index des agendas en cache : 0 requête
    de plus une fois le cache chaud). Un agenda en échec n'apporte rien (son état est dit ailleurs).
    Tous les agendas partagent UNE échéance réseau (`DELAI_ECRAN`) : 3 agendas lents ne coûtent pas 30 s."""
    from apps.taches import agenda_externe
    agendas = agenda_externe.agendas_actifs(user)
    evenements = []
    fin = agenda_externe.horloge() + agenda_externe.DELAI_ECRAN
    for agenda in agendas:
        try:
            evenements.extend(agenda_externe.lire_agenda_externe(agenda, du, au, fin=fin))
        except Exception:  # noqa: BLE001 — un agenda illisible ne casse jamais la journée
            logger.warning('taches : agenda externe %s illisible', agenda.pk, exc_info=True)
    libelles = {agenda.pk: agenda.libelle or agenda.hote for agenda in agendas}
    return tuple(sorted(evenements, key=lambda r: (r.debut, r.cle))), libelles


def minutes_de_rendez_vous(user, jour, evenements):
    """Minutes de rendez-vous horodatés de `jour`, unies et bornées aux heures de travail
    (`moteur.ics.minutes_rendez_vous`) — retranchées de la capacité (invariant 35)."""
    from apps.taches.moteur.ics import minutes_rendez_vous
    if not evenements:
        return 0
    return minutes_rendez_vous(evenements, jour, fenetre_de_travail(user.company, jour))
