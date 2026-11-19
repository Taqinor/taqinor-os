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

from django.db.models import Count, Q
from django.utils import timezone

from apps.taches.choix import StatutJour, StatutProjet, StatutTache
from apps.taches.confidentialite import nom_pour
from apps.taches.models.journee import PlanJour
from apps.taches.models.projets import ModeleProjet, RevueProjet
from apps.taches.models.rythme import ReglagesRythme
from apps.taches.models.taches import ElementChecklist
from apps.taches.moteur import sante
from apps.taches.moteur.classement import ItemPur, prochaine_action
from apps.taches.moteur.decalage import nb_figees
from apps.taches.moteur.gabarits import texte as gabarit_texte
from apps.taches.moteur.rythme import semaine_courte
from apps.taches.selectors.base import _du_compte, jours_travailles_de, projets_de, sections_de, taches_de
from apps.taches.selectors.journee import JOURS_APRES, JOURS_AVANT, faites_par_jour, taches_de_la_journee

OUVERTS = (StatutTache.A_FAIRE, StatutTache.EN_ATTENTE)
CLOS = (StatutTache.FAIT, StatutTache.ANNULE)
#: Fenêtre maximale (jours) lue pour les jours travaillés : au-delà, rien ne change le verdict.
HORIZON_JOURS = 800
#: Fenêtre de la journée autour de J (la même que celle d'`aujourdhui/`).
JOURNEE_AVANT, JOURNEE_APRES = JOURS_AVANT, JOURS_APRES
#: Semaines lues avant et après celle de la revue pour savoir quels jours de la semaine il travaille
#: d'habitude (« Jours non travaillés »).
SEMAINES_HABITUDE = 4
CHAMPS_TACHE = (
    'id', 'projet_id', 'parent_id', 'statut', 'quelque_jour', 'jour_prevu', 'echeance', 'fait_le',
    'created_at', 'annule_le', 'bloquee_par_id', 'bloquee_par__statut', 'bloquee_par__is_deleted',
    'rang_projet', 'jalon', 'section_id')


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
    section_id: int | None = None


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
        rang_projet=ligne['rang_projet'], jalon=ligne['jalon'], section_id=ligne['section_id'])


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


def compteurs_par_etape(taches):
    """`{section_id: {ouvertes, faites}}` des tâches d'un projet (même compte que le projet entier ;
    `None` = « Sans étape »)."""
    par_etape = {}
    for tache in taches:
        par_etape.setdefault(tache.section_id, []).append(tache)
    return {section_id: _compteurs(liste) for section_id, liste in par_etape.items()}


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
    """« {actifs} projets actifs, {k} ont avancé ces 7 jours » sur les seuls projets actifs nés il y a 7 jours ou plus
    (R3-010 : « 0 a avancé » une minute après leur création était faux) ; aucun → `None` (la phrase est omise)."""
    limite = etat.jour - datetime.timedelta(days=sante.CONSTAT_JOURS)
    actifs = [p.pk for p in etat.projets if p.statut == StatutProjet.ACTIF and _local(p.created_at) <= limite]
    if not actifs:
        return None
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


# --- Les modèles de projet -----------------------------------------------------------------------

def modeles_de(user):
    """Modèles de projet de `user`, dans sa société."""
    return _du_compte(ModeleProjet.objects, user)


def modeles_servis(user, assistant=False):
    """Les modèles de `user` à SERVIR (liste, fiche, renommer, supprimer, instancier). Sous l'en-tête assistant
    (regles.md §8, revue F4 #3) : les seuls modèles ordinaires (`MODELE_ORDINAIRE`) — un modèle confidentiel est tu
    (ni nom ni compteurs) et son id répond comme un id inconnu. Échec fermé : dans le doute, tu."""
    qs = modeles_de(user)
    return qs.filter(MODELE_ORDINAIRE) if assistant else qs


def modele_de(user, pk, assistant=False):
    """Le modèle `pk` servi à `user` (`modeles_servis`), ou `None` (l'id d'un autre compte, ou celui d'un modèle
    confidentiel sous l'en-tête assistant, répond comme un id inconnu)."""
    return modeles_servis(user, assistant=assistant).filter(pk=pk).first()


#: Clé de `contenu` où la confidentialité du modèle est FIGÉE à l'enregistrement (revue F4 #1) : celle du projet
#: d'origine à cet instant ; elle ne dépend plus jamais de ce projet (supprimé, décoché ou rendu confidentiel).
CLE_CONFIDENTIEL = 'confidentiel'
#: Clé de `contenu` où est FIGÉ le nombre de tâches confidentielles que l'enregistrement n'a pas reprises (revue F4
#: #14) ; servie hors de `contenu` (`modele.json`, `modele_instancier.json`), 0 pour un modèle qui ne la porte pas.
CLE_NON_REPRISES = 'confidentielles_non_reprises'
#: Un modèle ORDINAIRE : drapeau figé à `false` ; sans drapeau (modèle enregistré avant lui), échec fermé : ordinaire
#: seulement si son projet d'origine existe encore, vivant et ordinaire (origine inconnue ou supprimée = confidentiel).
MODELE_ORDINAIRE = (
    Q(**{f'contenu__{CLE_CONFIDENTIEL}': False})
    | (~Q(contenu__has_key=CLE_CONFIDENTIEL)
       & Q(cree_depuis__isnull=False, cree_depuis__is_deleted=False, cree_depuis__confidentiel=False)))


def modele_confidentiel(modele):
    """Vrai quand le modèle est confidentiel (`MODELE_ORDINAIRE` faux) : l'assistant ne lit alors ni son contenu
    ni son aperçu, et le projet qui en naît est confidentiel."""
    return not ModeleProjet.objects.filter(
        pk=modele.pk, company_id=modele.company_id).filter(MODELE_ORDINAIRE).exists()


def elements_a_figer(user, projet):
    """`(étapes par rang, tâches par rang, {tâche: libellés de sa check-list}, non reprises)` de `projet` : celles du
    projet, SAUF les tâches confidentielles par leur propre drapeau (jamais copiées dans un modèle ni un double) ;
    `non reprises` = le NOMBRE de tâches que la copie aurait reprises sans cette règle (la confidentielle et ses
    sous-tâches, abandonnées exclues comme partout : `moteur.decalage.nb_figees`) — jamais une perte muette (revue F4
    #14). Une seule lecture des tâches."""
    sections = list(sections_de(user).filter(projet=projet).order_by('rang', 'id'))
    toutes = list(taches_de(user).filter(projet=projet).order_by('rang_projet', 'id'))
    taches = [tache for tache in toutes if not tache.confidentiel]
    listes = {}
    for tache_id, libelle in (ElementChecklist.objects.filter(company_id=user.company_id, tache__in=taches)
                              .order_by('rang', 'id').values_list('tache_id', 'libelle')):
        listes.setdefault(tache_id, []).append(libelle)
    return sections, taches, listes, nb_figees(toutes) - nb_figees(taches)


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
    prevues_aujourdhui: int = 0


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


def _prevues_aujourdhui(user, projets, aujourdhui):
    """`{projet_id: n}` : tâches ouvertes de la journée d'`aujourdhui` (le préfiltre UNIQUE) prévues ce jour-là,
    celles qu'une pause posée maintenant laisse dans la journée (C-5, R2-031). Une seule requête."""
    lignes = (taches_de_la_journee(user, aujourdhui)
              .filter(projet__in=projets, statut__in=OUVERTS, jour_prevu=aujourdhui)
              .order_by().values('projet_id').annotate(n=Count('id')))
    return {ligne['projet_id']: ligne['n'] for ligne in lignes}


def cartes_de_revue(user, etat, lundi, *, aujourdhui=None):
    """Une `CarteRevue` par projet ACTIF, et par projet NON actif (en pause, terminé) qui a sa `RevueProjet` de la
    semaine de `lundi` — la revue rechargée garde le projet qu'on vient de mettre en pause, avec sa décision (R3-009) ;
    un seul ordre : priorité décroissante, puis rang."""
    revues = {r.projet_id: r for r in RevueProjet.objects.filter(
        company_id=user.company_id, proprietaire=user, semaine=lundi)}
    servis = sorted((p for p in etat.projets if p.statut == StatutProjet.ACTIF or p.pk in revues),
                    key=lambda p: (-p.priorite, p.rang, p.pk))
    faites, bloquees = _faites_de_la_semaine(user, servis, lundi), _bloquees_ouvertes(user, servis)
    prevues = _prevues_aujourdhui(user, servis, aujourdhui or timezone.localdate())
    return [CarteRevue(projet=p, faites=faites.get(p.pk, []), bloquees=bloquees.get(p.pk, []),
                       prochaine_id=_prochaine_choisie(etat, p, revues.get(p.pk)), revue=revues.get(p.pk),
                       prevues_aujourdhui=prevues.get(p.pk, 0))
            for p in servis]


def _semaine_de_plans(plans, lundi):
    return [p for p in plans if lundi <= p.jour <= lundi + datetime.timedelta(days=6)]


def _jours_evalues(plans):
    return [p for p in plans if p.statut_jour == StatutJour.EVALUE]


def _jours_de_semaine_travailles(user, lundi):
    """Jours de la semaine (0 = lundi … 6 = dimanche) qu'il travaille d'HABITUDE : ceux où tombe au moins
    un de ses jours travaillés (`jours_travailles_de`, la source de toute l'app) dans les semaines autour
    de celle de la revue — un férié ou un congé retire une date, jamais un jour de la semaine de toutes."""
    ecart = datetime.timedelta(weeks=SEMAINES_HABITUDE)
    return {d.weekday() for d in jours_travailles_de(user, lundi - ecart, lundi + datetime.timedelta(days=6) + ecart)}


def _non_travailles(user, lundi, semaine):
    """« Jours non travaillés : n » : jours de la semaine en congé ou fériés (`conge`, `non_ouvre`) qu'il
    travaille d'habitude — jamais le samedi ni le dimanche d'un compte qui ne les travaille pas : la même
    semaine dit la même chose le vendredi soir et le lundi (revue F2 tour 2 #4)."""
    repos = [p for p in semaine if p.statut_jour in (StatutJour.CONGE, StatutJour.NON_OUVRE)]
    if not repos:
        return 0
    habituels = _jours_de_semaine_travailles(user, lundi)
    return sum(1 for p in repos if p.jour.weekday() in habituels)


def bilan_de_semaine(user, lundi, mode, *, aujourdhui=None):
    """`(semaine_courte, bilan)` de la semaine de `lundi` (jamais un titre). `bilan` = `{texte, donnees:{faites,
    jours, prec}}` ou `None` (semaine courte, ou rien de fait ni de jugé). R3-003 (choix C-16) : `faites` = LA somme
    `faites_par_jour` du lundi à aujourd'hui, week-end et aujourd'hui compris — celle de l'Agenda et de « Faites
    cette semaine » —, `prec` la même sur la semaine d'avant (`None` sans faite ni jour jugé), `jours` = jours où il a
    fait au moins une chose ; l'essentiel et la semaine courte viennent des `PlanJour` clos. Plus d'« Objectif
    atteint X jours sur N » ni de « gardées ». La tête dit « Cette semaine » seulement si `lundi` est celui de la
    semaine d'`aujourdhui` (défaut : le jour local) ; une semaine passée garde ses dates « Du lun. 9 au ven. 13 »."""
    aujourdhui = aujourdhui or timezone.localdate()
    precedent, dimanche = lundi - datetime.timedelta(days=7), lundi + datetime.timedelta(days=6)
    plans = list(PlanJour.objects.filter(company_id=user.company_id, proprietaire=user,
                                         jour__range=(precedent, dimanche)))
    semaine = _semaine_de_plans(plans, lundi)
    if semaine_courte([p.statut_jour for p in semaine]):
        return True, None
    par_jour = faites_par_jour(user, precedent, dimanche, aujourdhui)
    cette_semaine = [n for jour, n in par_jour.items() if jour >= lundi]
    faites, jours = sum(cette_semaine), sum(1 for n in cette_semaine if n > 0)
    evalues = _jours_evalues(semaine)
    if faites == 0 and not evalues:
        return False, None
    prec = sum(n for jour, n in par_jour.items() if jour < lundi)
    if prec == 0 and not _jours_evalues(_semaine_de_plans(plans, precedent)):
        prec = None
    texte = gabarit_texte('revue', 'entete', {
        'debut': lundi, 'fin': lundi + datetime.timedelta(days=4), 'faites': faites, 'jours': jours,
        'prec': prec, 'mode': mode, 'courante': lundi == lundi_de(aujourdhui),
        'e': sum(p.essentiels_faits for p in evalues), 'je': sum(p.essentiels_choisis for p in evalues),
        'non_travailles': _non_travailles(user, lundi, semaine)})
    return False, {'texte': texte, 'donnees': {'faites': faites, 'jours': jours, 'prec': prec}}
