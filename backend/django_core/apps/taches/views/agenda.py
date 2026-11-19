"""Agenda (reference/api.md §3.1, §4 `agenda/`) : jours (≤ 42), Toute la journée, sans heure, blocs,
échéances, À placer, Mes projets (vues jour et semaine : le même volet), férié ; rendez-vous externes du jour.

Le schéma OpenAPI est celui de l'échantillon `agenda.json`. Les tâches de la période sont chargées
en une passe (`formes.charger_items`) ; la journée d'aujourd'hui (`selectors.journee.lire_journee`)
donne À placer et Mes projets : aucune règle de classement n'est réécrite ici.
"""
import datetime

from django.db.models import Exists, OuterRef, Q
from django.http import Http404
from django.utils import timezone
from drf_spectacular.types import OpenApiTypes
from drf_spectacular.utils import extend_schema
from rest_framework.exceptions import ValidationError
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.notifications.calendar_utils import jours_ouvres_entre
from apps.records.selectors import activites_closes_par
from apps.taches.choix import FamilleObligation, SectionJournee, StatutProjet, StatutTache
from apps.taches.models.taches import Tache
from apps.taches.moteur import classement
from apps.taches.moteur.rythme import compte_du_jour
from apps.taches.selectors import journee as sel
from apps.taches.selectors.base import jours_travailles_de, projets_de, taches_de
from apps.taches.serializers import journee as formes_journee
from apps.taches.serializers.formes import charger_items
from apps.taches.views.base import PERMISSIONS, est_assistant, forme_echantillon, parametre, reponses
from apps.taches.views.journee import MESSAGE_DATE, date_de, maintenant

TACHE = classement.TACHE
JOURS_MAX = 42
MESSAGE_42 = '42 jours au plus.'
MESSAGE_VUE = 'Valeur inconnue.'
VUE_JOUR, VUE_SEMAINE, VUE_MOIS, VUE_A_VENIR = 'jour', 'semaine', 'mois', 'a-venir'
VUES = (VUE_JOUR, VUE_SEMAINE, VUE_MOIS, VUE_A_VENIR)
#: « À venir » : deux semaines à partir d'aujourd'hui.
JOURS_A_VENIR = 14


def _par_defaut(vue, J):
    """(du, au) d'une vue quand la requête ne les donne pas."""
    if vue == VUE_JOUR:
        return J, J
    if vue == VUE_MOIS:
        premier = J.replace(day=1)
        suivant = (premier + datetime.timedelta(days=32)).replace(day=1)
        return premier, suivant - datetime.timedelta(days=1)
    if vue == VUE_A_VENIR:
        return J, J + datetime.timedelta(days=JOURS_A_VENIR - 1)
    lundi = sel.lundi_de(J)
    return lundi, lundi + datetime.timedelta(days=6)


def bornes(params, J):
    """(du, au, vue) lus de `?du=&au=&vue=` ; 400 au champ fautif, « 42 jours au plus. » au-delà."""
    vue = params.get('vue') or VUE_SEMAINE
    if vue not in VUES:
        raise ValidationError({'vue': [MESSAGE_VUE]})
    du, au = _par_defaut(vue, J)
    if params.get('du'):
        debut = date_de(params['du'], 'du')
        du, au = debut, debut + (au - du)
    if params.get('au'):
        au = date_de(params['au'], 'au')
    if au < du:
        raise ValidationError({'au': [MESSAGE_DATE]})
    if (au - du).days + 1 > JOURS_MAX:
        raise ValidationError({'au': [MESSAGE_42]})
    return du, au, vue


def _projet_du_compte(user, valeur):
    """`?projet=` : un id d'un de MES projets (invariant 9 : sinon 404) ; None sans filtre."""
    if not valeur:
        return None
    if not str(valeur).isdigit() or not projets_de(user).filter(pk=int(valeur)).exists():
        raise Http404('Introuvable.')
    return int(valeur)


def taches_de_la_periode(user, du, au, projet_id=None, J=None):
    """Tâches vivantes non abandonnées de `user` prévues ou à échéance dans [du, au] (parent nul,
    projet actif ou triées, une faite quel que soit l'état de son projet : le préfiltre de la journée,
    étendu à la période — revue F2 tour 2 #1). `J` : aujourd'hui — R2-031b (règle C-5, « ce que j'ai posé reste
    posé ») : une tâche OUVERTE d'un projet EN PAUSE prévue CE jour-là reste dans l'agenda du jour ; la pause
    continue de retirer celles des jours à venir."""
    rattachee = (Q(projet__isnull=False, projet__statut=StatutProjet.ACTIF, projet__is_deleted=False)
                 | Q(projet__isnull=True, triee_le__isnull=False))
    if J is not None:
        rattachee |= Q(projet__statut=StatutProjet.EN_PAUSE, projet__is_deleted=False, jour_prevu=J,
                       quelque_jour=False, statut__in=sel.OUVERTS)
    qs = (taches_de(user).filter(parent__isnull=True).filter(rattachee | Q(statut=StatutTache.FAIT))
          .exclude(statut=StatutTache.ANNULE)
          .filter(Q(jour_prevu__range=(du, au)) | Q(echeance__range=(du, au))))
    return qs.filter(projet_id=projet_id) if projet_id is not None else qs


def taches_journee_et_periode(user, J, du, au, projet_id=None):
    """UN chargement préchargé pour toute la fenêtre : les tâches du préfiltre de la journée `J`
    ET celles de la période, lues d'un seul tenant (`dans_journee` / `dans_periode` : appartenance,
    sans seconde lecture des rappels, check-lists et sous-tâches). → (tâches de J, tâches de la période)."""
    dans_j = Exists(sel.taches_de_la_journee(user, J).filter(pk=OuterRef('pk')))
    dans_p = Exists(taches_de_la_periode(user, du, au, projet_id, J).filter(pk=OuterRef('pk')))
    qs = taches_de(user).annotate(dans_journee=dans_j, dans_periode=dans_p).filter(
        Q(dans_journee=True) | Q(dans_periode=True))
    toutes = list(charger_items(qs))
    return ([t for t in toutes if t.dans_journee], [t for t in toutes if t.dans_periode])


def _ajouter_periode(journee, taches, focus):
    """Ajoute les tâches de la période à la journée lue (mêmes objets, mêmes `ItemPur`)."""
    cles = []
    for tache in taches:
        cle = (TACHE, tache.pk)
        journee.items.setdefault(cle, sel.item_de_tache(tache, focus))
        journee.objets.setdefault(cle, tache)
        cles.append(cle)
    return cles


def _du_projet(journee, cles, projet_id):
    if projet_id is None:
        return list(cles)
    return [cle for cle in cles if cle[0] == TACHE and journee.items[cle].projet_id == projet_id]


def a_placer(journee, projet_id=None):
    """À placer : tâches du jour sans heure (Essentiel, Prévu, Ce soir), puis À revoir."""
    du_jour = [cle for cle in sel.gardes_ouverts(journee)
               if cle[0] == TACHE and journee.items[cle].heure_debut is None]
    a_revoir = [cle for cle in journee.sections.get(SectionJournee.A_DECIDER, ()) if cle[0] == TACHE]
    return _du_projet(journee, du_jour + a_revoir, projet_id)


def candidates_du_tour(journee, projet_id=None):
    """Le tour complet de Planifier ma semaine : candidates de Proposé sans jour (regles.md §3.4 §6)."""
    candidates = [item for item in journee.items.values()
                  if classement.est_candidate(item, journee.jour) and item.jour_prevu is None]
    return [item for item in candidates if projet_id is None or item.projet_id == projet_id]


def _travailles_de(user, autour, J, du, au):
    """Jours travaillés de [du, au] : tirés de ceux déjà lus autour d'aujourd'hui quand la fenêtre y
    tient (`travailles_autour` : J − 28 .. J + 60), sinon lus."""
    if du >= J - datetime.timedelta(days=sel.JOURS_AVANT) and au <= J + datetime.timedelta(days=sel.JOURS_APRES):
        return {jour for jour in autour if du <= jour <= au}
    return jours_travailles_de(user, du, au)


def faites_par_jour(user, du, au, J):
    """{jour: nombre de « faites » ce jour-là} pour les jours de [du, au] jusqu'à aujourd'hui `J` (R2-102, règle C-12) :
    les tâches PASSÉES à `fait` ce jour local — prévues ce jour-là ou non —, plus les activités ERP qu'il a closes,
    comptées par `compte_du_jour` (sous-tâche et routine = 0, plafond des micro-tâches) : le MÊME nombre que Mon rythme
    et la Revue. Une lecture de tâches et une d'activités pour toute la période (jamais une par jour)."""
    dernier = min(au, J)
    if dernier < du:
        return {}
    debut, _ = sel.bornes_du_jour(du)
    _, fin = sel.bornes_du_jour(dernier)
    taches = (taches_de(user).filter(statut=StatutTache.FAIT, fait_le__gte=debut, fait_le__lt=fin)
              .select_related('recurrence'))
    par_jour, activites = {}, {}
    for tache in taches:
        par_jour.setdefault(timezone.localtime(tache.fait_le).date(), []).append(classement.ItemPur(
            id=tache.pk, statut=tache.statut, parent_id=tache.parent_id, routine=sel._routine(tache),
            estimation_minutes=tache.estimation_minutes))
    # activités de l'ERP closes par lui, moins celles qui portent une tâche (comptées déjà : `activites_closes_du_jour`)
    portees = Tache.all_objects.filter(company_id=user.company_id, activite_origine_id__isnull=False)
    portees = portees.values('activite_origine_id')
    closes = activites_closes_par(user, debut, fin).exclude(pk__in=portees).values_list('pk', 'done_at')
    for pk, fait_a in closes:
        activites.setdefault(timezone.localtime(fait_a).date(), []).append(pk)
    return {jour: compte_du_jour(par_jour.get(jour, []), activites.get(jour, []))[0]
            for jour in sorted({*par_jour, *activites})}


def lire_agenda(user, du, au, vue, maintenant_, *, projet_id=None, assistant=False):
    """La forme `agenda.json` de `user` pour [du, au]."""
    J = maintenant_.date()
    reglages = sel.reglages_de(user)
    focus = sel.projets_de_la_semaine(user, J)
    du_jour, de_periode = taches_journee_et_periode(user, J, du, au, projet_id)
    journee = sel.lire_journee(user, J, reglages=reglages, travailles=sel.travailles_autour(user, J),
                               taches=du_jour, focus=focus)
    cles = _ajouter_periode(journee, de_periode, focus)
    travailles = _travailles_de(user, journee.travailles, J, du, au)
    ouvres = set(jours_ouvres_entre(user.company, du, au))
    obligations = sel.obligations_du_jour(user, J) if journee.erp and du <= J <= au else sel.Obligations()
    # « Toute la journée » ne porte que les éléments de l'ERP SANS heure (visites, poses, interventions : textes.md
    # §2, SCENARIO §4) ; « Suivi des relances » est une ligne de Prévu d'Aujourd'hui, jamais une bande d'agenda.
    bande = tuple(ligne for ligne in obligations.lignes if ligne['famille'] != FamilleObligation.TOUCHES)
    rendez_vous, agendas = sel.rendez_vous_pour(user, du, au)
    rendu = formes_journee.Rendu(journee, assistant=assistant, peut_cloturer=obligations.peut_cloturer,
                                 agendas=agendas)
    faites = faites_par_jour(user, du, au, J)
    jours = []
    for n in range((au - du).days + 1):
        jour = du + datetime.timedelta(days=n)
        externes = [r for r in rendez_vous if sel.touche_le_jour(r, jour)]
        entree = formes_journee.jour_d_agenda(
            rendu, jour, ouvre=jour in travailles, ferie=jour.weekday() < 5 and jour not in ouvres,
            cles_jour=cles, toute_la_journee=bande if jour == J else (), externes=externes)
        # R2-100 — le temps pris par les rendez-vous (unis, bornés aux heures de travail : invariant 35) : le
        # front retranche cette durée de la capacité du jour, il ne la devine pas.
        entree['rendez_vous_minutes'] = sel.minutes_de_rendez_vous(user, jour, externes)
        # R2-102 — « faites » = finies CE jour-là (règle C-12), le nombre de Mon rythme ; 0 pour un jour à venir
        entree['faites_nb'] = faites.get(jour, 0)
        jours.append(entree)
    # Le volet « À placer » est le même en vue Jour et Semaine (maquettes, SCENARIO §4) : Mes projets y est servi.
    volet = vue in (VUE_JOUR, VUE_SEMAINE)
    minutes, source = sel.capacite_du_jour(user, J, reglages, sel.preferences_de(user), journee.travailles)
    return {
        'du': du.isoformat(), 'au': au.isoformat(), 'jours': jours,
        'a_placer': rendu.items(a_placer(journee, projet_id)),
        'mes_projets': formes_journee.mes_projets(rendu, candidates_du_tour(journee, projet_id)) if volet else [],
        # La capacité d'un jour travaillé (« {h} pour {cap} ») : celle d'aujourd'hui, même calcul que la
        # PROGRESSION d'`aujourdhui/` (réglage dit, sinon médiane des 9 derniers jours travaillés, sinon 240).
        'capacite': {'minutes': minutes, 'source': source},
    }


class AgendaVue(APIView):
    """GET agenda/ — jours, À placer, Mes projets ; rendez-vous externes du jour."""

    permission_classes = PERMISSIONS

    @extend_schema(parameters=[
        parametre('du', OpenApiTypes.DATE, 'Premier jour (AAAA-MM-JJ).'),
        parametre('au', OpenApiTypes.DATE, 'Dernier jour ; 42 jours au plus.'),
        parametre('vue', OpenApiTypes.STR, 'jour, semaine, mois ou a-venir.'),
        parametre('projet', OpenApiTypes.INT, "Id d'un de mes projets."),
    ], responses=reponses(forme_echantillon('agenda'), erreurs=(400, 404)))
    def get(self, request):
        heure = maintenant()
        du, au, vue = bornes(request.query_params, heure.date())
        projet_id = _projet_du_compte(request.user, request.query_params.get('projet'))
        return Response(lire_agenda(request.user, du, au, vue, heure, projet_id=projet_id,
                                    assistant=est_assistant(request)))
