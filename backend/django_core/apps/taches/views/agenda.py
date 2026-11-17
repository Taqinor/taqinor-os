"""Agenda (reference/api.md §3.1, §4 `agenda/`) : jours (≤ 42), Toute la journée, sans heure, blocs,
échéances, À placer, Mes projets (vue semaine), férié ; rendez-vous externes du jour.

Le schéma OpenAPI est celui de l'échantillon `agenda.json`. Les tâches de la période sont chargées
en une passe (`formes.charger_items`) ; la journée d'aujourd'hui (`selectors.journee.lire_journee`)
donne À placer et Mes projets : aucune règle de classement n'est réécrite ici.
"""
import datetime

from django.db.models import Exists, OuterRef, Q
from django.http import Http404
from drf_spectacular.types import OpenApiTypes
from drf_spectacular.utils import extend_schema
from rest_framework.exceptions import ValidationError
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.notifications.calendar_utils import jours_ouvres_entre
from apps.taches.choix import SectionJournee, StatutProjet, StatutTache
from apps.taches.moteur import classement
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


def taches_de_la_periode(user, du, au, projet_id=None):
    """Tâches vivantes non abandonnées de `user` prévues ou à échéance dans [du, au] (parent nul,
    projet actif ou triées : le préfiltre de la journée, étendu à la période)."""
    rattachee = (Q(projet__isnull=False, projet__statut=StatutProjet.ACTIF, projet__is_deleted=False)
                 | Q(projet__isnull=True, triee_le__isnull=False))
    qs = (taches_de(user).filter(parent__isnull=True).filter(rattachee).exclude(statut=StatutTache.ANNULE)
          .filter(Q(jour_prevu__range=(du, au)) | Q(echeance__range=(du, au))))
    return qs.filter(projet_id=projet_id) if projet_id is not None else qs


def taches_journee_et_periode(user, J, du, au, projet_id=None):
    """UN chargement préchargé pour toute la fenêtre : les tâches du préfiltre de la journée `J`
    ET celles de la période, lues d'un seul tenant (`dans_journee` / `dans_periode` : appartenance,
    sans seconde lecture des rappels, check-lists et sous-tâches). → (tâches de J, tâches de la période)."""
    dans_j = Exists(sel.taches_de_la_journee(user, J).filter(pk=OuterRef('pk')))
    dans_p = Exists(taches_de_la_periode(user, du, au, projet_id).filter(pk=OuterRef('pk')))
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
    rendez_vous, agendas = sel.rendez_vous_pour(user, du, au)
    rendu = formes_journee.Rendu(journee, assistant=assistant, peut_cloturer=obligations.peut_cloturer,
                                 agendas=agendas)
    jours = []
    for n in range((au - du).days + 1):
        jour = du + datetime.timedelta(days=n)
        jours.append(formes_journee.jour_d_agenda(
            rendu, jour, ouvre=jour in travailles, ferie=jour.weekday() < 5 and jour not in ouvres,
            cles_jour=cles, toute_la_journee=obligations.lignes if jour == J else (),
            externes=[r for r in rendez_vous if sel.touche_le_jour(r, jour)]))
    semaine = vue == VUE_SEMAINE
    minutes, source = sel.capacite_du_jour(user, J, reglages, sel.preferences_de(user), journee.travailles)
    return {
        'du': du.isoformat(), 'au': au.isoformat(), 'jours': jours,
        'a_placer': rendu.items(a_placer(journee, projet_id)),
        'mes_projets': formes_journee.mes_projets(rendu, candidates_du_tour(journee, projet_id)) if semaine else [],
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
