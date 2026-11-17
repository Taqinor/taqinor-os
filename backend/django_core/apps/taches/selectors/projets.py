"""Lectures des projets (reference/api.md §3.3 ; regles.md §5 ; spec-4 §3 E, F, H).

`etat_projets(user, jour)` lit UNE FOIS tout ce que la santé, les compteurs, l'« À planifier » et le
constat demandent : les projets vivants de `user`, leurs tâches comptées (en `values()`, jamais une
requête par ligne), leurs étapes, ses réglages et ses jours travaillés. Les calculs sont ceux du module
pur `moteur/sante.py` ; rien n'est recopié ici. Le résultat nourrit la forme PROJET
(`contexte(calculs=…)`).

Toute lecture passe par les sélecteurs de `selectors/base.py` : société ET propriétaire, toujours.
"""
import datetime
from dataclasses import dataclass, field

from django.utils import timezone

from apps.taches.choix import StatutJour, StatutProjet, StatutTache
from apps.taches.confidentialite import nom_pour
from apps.taches.models.journee import PlanJour
from apps.taches.models.projets import RevueProjet
from apps.taches.models.rythme import ReglagesRythme
from apps.taches.moteur import sante
from apps.taches.moteur.classement import ItemPur, prochaine_action
from apps.taches.moteur.gabarits import texte as gabarit_texte
from apps.taches.moteur.rythme import journee_reussie, semaine_courte
from apps.taches.selectors.base import jours_travailles_de, projets_de, sections_de, taches_de
from apps.taches.selectors.journee import JOURS_APRES, JOURS_AVANT

OUVERTS = (StatutTache.A_FAIRE, StatutTache.EN_ATTENTE)
CLOS = (StatutTache.FAIT, StatutTache.ANNULE)
#: Fenêtre maximale (jours) lue pour les jours travaillés : au-delà, rien ne change le verdict.
HORIZON_JOURS = 800
#: Fenêtre de la journée autour de J (la même que celle d'`aujourdhui/`).
JOURNEE_AVANT, JOURNEE_APRES = JOURS_AVANT, JOURS_APRES
CHAMPS_TACHE = (
    'id', 'projet_id', 'parent_id', 'statut', 'quelque_jour', 'jour_prevu', 'echeance', 'fait_le',
    'created_at', 'annule_le', 'bloquee_par_id', 'bloquee_par__statut', 'bloquee_par__is_deleted',
    'rang_projet', 'jalon')


@dataclass(frozen=True)
class TachePure:
    """Ce que `moteur/sante.py` lit d'une tâche (dates locales ; `bloquee_par` = id d'un prérequis encore
    ouvert, sinon `None`)."""
    id: int
    projet_id: int
    parent_id: int | None
    statut: str
    quelque_jour: bool
    bloquee_par: int | None
    jour_prevu: datetime.date | None
    echeance: datetime.date | None
    fait_le: datetime.date | None
    created_at: datetime.date
    annule_le: datetime.date | None
    rang_projet: int | None = None
    jalon: bool = False


@dataclass
class EtatProjets:
    """Les projets vivants de `user` et ce qui en est calculé."""
    jour: datetime.date
    projets: list = field(default_factory=list)
    taches: dict = field(default_factory=dict)
    sections: dict = field(default_factory=dict)
    reglages: object = None
    calculs: dict = field(default_factory=dict)
    constat: dict = field(default_factory=dict)
    #: Jours travaillés de la fenêtre de la journée et projets « de la semaine » : ce que lit
    #: l'explication d'un ITEM servi par la vue d'un projet ou la revue (même calcul que la journée).
    travailles_journee: frozenset = frozenset()
    focus: frozenset = frozenset()

    def taches_de(self, projet_id):
        return self.taches.get(projet_id, [])


def lundi_de(jour):
    """Le lundi de la semaine de `jour`."""
    return jour - datetime.timedelta(days=jour.weekday())


def _local(instant):
    return timezone.localtime(instant).date() if instant is not None else None


def reglages_de(user):
    """`ReglagesRythme` de `user` (elle n'existe qu'après sa première tâche) ou `None`."""
    return ReglagesRythme.objects.filter(company_id=user.company_id, proprietaire=user).first()


def _tache_pure(ligne):
    ouvert = (ligne['bloquee_par_id'] is not None and not ligne['bloquee_par__is_deleted']
              and ligne['bloquee_par__statut'] not in CLOS)
    return TachePure(
        id=ligne['id'], projet_id=ligne['projet_id'], parent_id=ligne['parent_id'], statut=ligne['statut'],
        quelque_jour=ligne['quelque_jour'], bloquee_par=ligne['bloquee_par_id'] if ouvert else None,
        jour_prevu=ligne['jour_prevu'], echeance=ligne['echeance'], fait_le=_local(ligne['fait_le']),
        created_at=_local(ligne['created_at']), annule_le=_local(ligne['annule_le']),
        rang_projet=ligne['rang_projet'], jalon=ligne['jalon'])


def _taches_par_projet(user):
    """`{projet_id: [TachePure]}` pour tous les projets vivants de `user` (un seul parcours)."""
    lignes = (taches_de(user).filter(projet__isnull=False, projet__is_deleted=False)
              .order_by('id').values(*CHAMPS_TACHE))
    rendu = {}
    for ligne in lignes:
        rendu.setdefault(ligne['projet_id'], []).append(_tache_pure(ligne))
    return rendu


def _sections_par_projet(user):
    """`{projet_id: [(nom, date_fin)]}`."""
    rendu = {}
    for projet_id, nom, fin in sections_de(user).order_by('rang', 'id').values_list(
            'projet_id', 'nom', 'date_fin'):
        rendu.setdefault(projet_id, []).append((nom, fin))
    return rendu


def _projet_sante(projet, taches, etapes, usage, reglages):
    """Le `ProjetSante` d'un projet ; son nom passe par `nom_pour` (jamais un nom confidentiel brut)."""
    masquer = usage != 'ecran' and projet.confidentiel
    return sante.ProjetSante(
        id=projet.pk, nom=nom_pour(projet, usage, reglages) or '', priorite=projet.priorite, rang=projet.rang,
        statut_depuis=_local(projet.statut_depuis), statut=projet.statut, echeance=projet.echeance,
        etapes=tuple(((nom if not masquer else 'Étape'), fin) for nom, fin in etapes),
        planification_le=_local(projet.planification_le), actionnables=sante.nb_actionnables(taches))


def _fenetre_travaillee(etat):
    """(du, au) des jours travaillés à lire : de J − 28 (ou du plus ancien `statut_depuis` d'un actif) à la
    plus lointaine échéance d'un actif (au moins J)."""
    actifs = [p for p in etat.projets if p.statut == StatutProjet.ACTIF]
    du = min([etat.jour - datetime.timedelta(days=sante.RYTHME_JOURS)]
             + [_local(p.statut_depuis) for p in actifs])
    au = max([etat.jour] + [p.echeance for p in actifs if p.echeance is not None])
    borne = datetime.timedelta(days=HORIZON_JOURS)
    return max(du, etat.jour - borne), min(au, etat.jour + borne)


def _faites_depuis(taches, jour, jours):
    """Tâches faites (tous niveaux) dans ]jour − jours, jour]."""
    debut = jour - datetime.timedelta(days=jours)
    return sum(1 for t in taches if t.statut == StatutTache.FAIT and t.fait_le is not None
               and debut < t.fait_le <= jour)


def _signaux(projet, taches, etat, travailles, negliges, usage):
    """Les signaux d'un projet ACTIF, dans l'ordre d'affichage de regles.md §5."""
    n = etat.reglages.projet_arret_jours if etat.reglages else sante.ARRET_JOURS_DEFAUT
    rythme = etat.reglages.comprendre_mon_rythme if etat.reglages else True
    ps = _projet_sante(projet, taches, etat.sections.get(projet.pk, ()), usage, etat.reglages)
    candidats = (
        sante.echeance_menacee(taches, ps, etat.jour, travailles, rythme=rythme),
        sante.a_l_arret(taches, ps, etat.jour, travailles, n),
        negliges.get(projet.pk),
        sante.sans_prochaine_action(taches),
        sante.tout_fait(taches),
    )
    return [{'code': s.code, 'phrase': s.phrase, 'donnees': s.donnees} for s in candidats if s is not None]


def _negliges(etat, usage):
    actifs = [p for p in etat.projets if p.statut == StatutProjet.ACTIF]
    sante_actifs = [_projet_sante(p, etat.taches_de(p.pk), etat.sections.get(p.pk, ()), usage, etat.reglages)
                    for p in actifs]
    faites = {p.pk: _faites_depuis(etat.taches_de(p.pk), etat.jour, sante.NEGLIGE_JOURS) for p in actifs}
    return sante.neglige(sante_actifs, faites, etat.jour)


def _compteurs(taches):
    comptees = [t for t in taches if t.parent_id is None and t.statut != StatutTache.ANNULE]
    return {'ouvertes': sum(1 for t in comptees if t.statut in OUVERTS),
            'faites': sum(1 for t in comptees if t.statut == StatutTache.FAIT)}


def _focus(user, jour):
    """Ids des projets « de la semaine » (un seul, invariant 25) pour la semaine de `jour`."""
    return set(RevueProjet.objects.filter(
        company_id=user.company_id, proprietaire=user, semaine=lundi_de(jour), focus=True,
    ).values_list('projet_id', flat=True))


def _calcul_projet(projet, etat, travailles, negliges, focus, usage):
    taches = etat.taches_de(projet.pk)
    compteurs = _compteurs(taches)
    actif = projet.statut == StatutProjet.ACTIF
    ps = _projet_sante(projet, taches, (), usage, etat.reglages)
    return {
        'a_planifier': sante.a_planifier(ps, compteurs['ouvertes']),
        'compteurs': compteurs,
        'sante': _signaux(projet, taches, etat, travailles, negliges, usage) if actif else [],
        'focus_semaine': projet.pk in focus,
    }


def _constat(etat):
    actifs = [p.pk for p in etat.projets if p.statut == StatutProjet.ACTIF]
    faites = {i: _faites_depuis(etat.taches_de(i), etat.jour, sante.CONSTAT_JOURS) for i in actifs}
    rendu = sante.constat_projets(actifs, faites)
    return {'actifs': rendu['actifs'], 'avances_7j': rendu['k']}


def etat_projets(user, jour, *, usage='ecran'):
    """Tout ce que la forme PROJET calcule, pour les projets vivants de `user` au jour `jour`
    (`usage` : `ecran` ou `assistant`, pour les noms cités dans les phrases de santé)."""
    etat = EtatProjets(jour=jour, projets=list(projets_de(user).order_by('rang', 'id')))
    etat.taches, etat.sections, etat.reglages = _taches_par_projet(user), _sections_par_projet(user), reglages_de(user)
    du, au = _fenetre_travaillee(etat)
    # Une seule lecture couvre aussi la fenêtre de la journée (J − 28, J + 60) dont les ITEM ont besoin
    # pour leur explication ; la santé ne voit que sa propre fenêtre, comme avant.
    debut_j, fin_j = jour - datetime.timedelta(days=JOURNEE_AVANT), jour + datetime.timedelta(days=JOURNEE_APRES)
    lus = jours_travailles_de(user, min(du, debut_j), max(au, fin_j))
    travailles = {d for d in lus if du <= d <= au}
    negliges, focus = _negliges(etat, usage), _focus(user, jour)
    etat.travailles_journee = frozenset(d for d in lus if debut_j <= d <= fin_j)
    etat.focus = frozenset(focus)
    for projet in etat.projets:
        etat.calculs[('projet', projet.pk)] = _calcul_projet(projet, etat, travailles, negliges, focus, usage)
    etat.constat = _constat(etat)
    return etat


def projets_filtres(user, statut=None):
    """Les projets de `user` du filtre `statut` : `actif`, `en_pause`, `archive` (= terminés ET archivés,
    la vue « Archive ») ; sans filtre, les projets en cours (actifs et en pause)."""
    projets = projets_de(user)
    if statut == 'archive':
        valeurs = (StatutProjet.TERMINE, StatutProjet.ARCHIVE)
    elif statut:
        valeurs = (statut,)
    else:
        valeurs = (StatutProjet.ACTIF, StatutProjet.EN_PAUSE)
    return projets.filter(statut__in=valeurs).order_by('rang', 'id')


def projet_de(user, pk):
    """Le projet vivant `pk` de `user`, ou `None` (l'id d'un autre compte répond comme un id inconnu)."""
    return projets_de(user).filter(pk=pk).first()


# --- La vue d'un projet --------------------------------------------------------------------------

def _item_pur(tache):
    """Le `ItemPur` d'une `TachePure` (ce que lit `classement.prochaine_action`)."""
    return ItemPur(type='tache', id=tache.id, statut=tache.statut, parent_id=tache.parent_id,
                   rang_projet=tache.rang_projet, quelque_jour=tache.quelque_jour, bloquee_par=tache.bloquee_par)


def prochaine_action_id(taches):
    """Id de la prochaine action d'un projet (première tâche à faire, non bloquée, hors réserve, dans
    l'ordre du projet) ou `None`."""
    choisie = prochaine_action([_item_pur(t) for t in taches])
    return choisie.id if choisie is not None else None


def prochain_jalon_id(taches):
    """Id du jalon ouvert de plus petite date (`echeance`, sinon `jour_prevu` ; sans date en dernier)."""
    jalons = [t for t in taches if t.jalon and t.statut in OUVERTS]
    if not jalons:
        return None

    def cle(t):
        date = t.echeance or t.jour_prevu
        return (date is None, date or datetime.date.max, t.id)
    return min(jalons, key=cle).id


def avancement_de(taches):
    """`{faites, total, derniere_faite_le}` (« 12 sur 20 » ; 0 comptée : total 0)."""
    rendu = sante.avancement(taches)
    return {'faites': rendu.faites, 'total': rendu.total,
            'derniere_faite_le': rendu.derniere_faite.isoformat() if rendu.derniere_faite else None}


def burnup_de(taches, jour):
    """`([{semaine (lundi), total, faites}], légende)` par semaine close."""
    rendu = sante.burnup(taches, jour)
    points = [{'semaine': (p.fin - datetime.timedelta(days=6)).isoformat(), 'total': p.total, 'faites': p.faites}
              for p in rendu.points]
    return points, rendu.legende


# --- La revue de la semaine ----------------------------------------------------------------------

CHARGEMENT_TITRE = ('projet', 'parent', 'parent__projet')
CHARGEMENT_ATTENTE = CHARGEMENT_TITRE + ('bloquee_par', 'bloquee_par__projet', 'bloquee_par__parent',
                                         'bloquee_par__parent__projet')


@dataclass
class CarteRevue:
    """Ce que lit une carte de revue : le projet, ses tâches faites cette semaine, ses tâches qui en
    attendent une autre, l'identifiant de sa prochaine action et sa `RevueProjet` de la semaine."""
    projet: object
    faites: list = field(default_factory=list)
    bloquees: list = field(default_factory=list)
    prochaine_id: int | None = None
    revue: object = None


def _par_projet(taches):
    rendu = {}
    for tache in taches:
        rendu.setdefault(tache.projet_id, []).append(tache)
    return rendu


def _faites_de_la_semaine(user, projets, lundi):
    fin = lundi + datetime.timedelta(days=6)
    return _par_projet(
        taches_de(user).filter(projet__in=projets, statut=StatutTache.FAIT, fait_le__date__range=(lundi, fin))
        .select_related(*CHARGEMENT_TITRE).order_by('-fait_le', 'id'))


def _bloquees_ouvertes(user, projets):
    return _par_projet(
        taches_de(user).filter(projet__in=projets, statut__in=OUVERTS, bloquee_par__isnull=False,
                               bloquee_par__is_deleted=False)
        .exclude(bloquee_par__statut__in=CLOS).select_related(*CHARGEMENT_ATTENTE).order_by('rang_projet', 'id'))


def _prochaine_choisie(etat, projet, revue):
    """L'id de l'action choisie à la revue si elle est encore ouverte dans ce projet, sinon la première
    à faire du projet."""
    taches = etat.taches_de(projet.pk)
    if revue is not None and revue.prochaine_action_id is not None:
        choisie = next((t for t in taches if t.id == revue.prochaine_action_id), None)
        if choisie is not None and choisie.statut in OUVERTS:
            return choisie.id
    return prochaine_action_id(taches)


def cartes_de_revue(user, etat, lundi):
    """Une `CarteRevue` par projet ACTIF (priorité décroissante, puis rang) pour la semaine de `lundi`."""
    actifs = sorted((p for p in etat.projets if p.statut == StatutProjet.ACTIF),
                    key=lambda p: (-p.priorite, p.rang, p.pk))
    faites, bloquees = _faites_de_la_semaine(user, actifs, lundi), _bloquees_ouvertes(user, actifs)
    revues = {r.projet_id: r for r in RevueProjet.objects.filter(
        company_id=user.company_id, proprietaire=user, semaine=lundi, projet__in=actifs)}
    return [CarteRevue(projet=p, faites=faites.get(p.pk, []), bloquees=bloquees.get(p.pk, []),
                       prochaine_id=_prochaine_choisie(etat, p, revues.get(p.pk)), revue=revues.get(p.pk))
            for p in actifs]


def _semaine_de_plans(plans, lundi):
    return [p for p in plans if lundi <= p.jour <= lundi + datetime.timedelta(days=6)]


def _jours_evalues(plans):
    return [p for p in plans if p.statut_jour == StatutJour.EVALUE]


def _faites_et_jours(plans):
    evalues = _jours_evalues(plans)
    return sum(p.compte_rythme for p in evalues), len(evalues)


def _jours_reussis(evalues):
    """Nombre de jours « objectif atteint » (`None` si aucun jour n'avait d'objectif)."""
    verdicts = [journee_reussie(p.compte_rythme, p.objectif_du_jour, p.essentiels_choisis, p.essentiels_faits)
                for p in evalues]
    verdicts = [v for v in verdicts if v is not None]
    return sum(1 for v in verdicts if v) if verdicts else None


def bilan_de_semaine(user, lundi, mode):
    """`(semaine_courte, bilan)` de la semaine de `lundi`, lus dans les `PlanJour` clos (jamais un titre).
    `bilan` = `{texte, donnees:{faites, jours, prec}}` ou `None` (semaine courte, ou aucun jour évalué)."""
    plans = list(PlanJour.objects.filter(
        company_id=user.company_id, proprietaire=user,
        jour__range=(lundi - datetime.timedelta(days=7), lundi + datetime.timedelta(days=6))))
    semaine = _semaine_de_plans(plans, lundi)
    if semaine_courte([p.statut_jour for p in semaine]):
        return True, None
    faites, jours = _faites_et_jours(semaine)
    if jours == 0:
        return False, None
    prec_faites, prec_jours = _faites_et_jours(_semaine_de_plans(plans, lundi - datetime.timedelta(days=7)))
    prec = prec_faites if prec_jours else None
    evalues = _jours_evalues(semaine)
    texte = gabarit_texte('revue', 'entete', {
        'debut': lundi, 'fin': lundi + datetime.timedelta(days=4), 'faites': faites, 'jours': jours,
        'prec': prec, 'oa': _jours_reussis(evalues), 'mode': mode,
        'e': sum(p.essentiels_faits for p in evalues), 'je': sum(p.essentiels_choisis for p in evalues),
        'pt': sum(p.plan_faites for p in evalues), 'pl': sum(p.plan_prevues for p in evalues),
        'non_travailles': sum(1 for p in semaine if p.statut_jour in (StatutJour.CONGE, StatutJour.NON_OUVRE))})
    return False, {'texte': texte, 'donnees': {'faites': faites, 'jours': jours, 'prec': prec}}
