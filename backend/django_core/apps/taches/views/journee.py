"""Journée, rituels et pastille (reference/api.md §2, §3.1, §4).

Routes déclarées : une vue pas encore construite lève `PasEncore` (501) ; le schéma OpenAPI de
chaque route est celui de son échantillon de `contract_samples/` (`forme_echantillon`). Les vues
construites lisent le jour (`?jour=`, défaut : aujourd'hui) et l'heure murale, puis délèguent tout à
`services/journee.py`.
"""
import datetime
from contextlib import contextmanager

from django.utils import timezone
from drf_spectacular.types import OpenApiTypes
from drf_spectacular.utils import extend_schema, extend_schema_serializer
from rest_framework import serializers
from rest_framework.exceptions import ValidationError
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.taches.choix import Decision, RaisonPropose, SectionJournee, StatutTache
from apps.taches.entrees import LONGUEUR_ID_MAX, MESSAGE_DATE, Choix, DateBornee, jour_dans_bornes
from apps.taches.moteur import classement
from apps.taches.selectors import journee as sel
from apps.taches.serializers import journee as formes_journee
from apps.taches.serializers.corps import DATE, CorpsTaches, present, valeur
from apps.taches.serializers.formes import TacheEcriteSerializer, charger_items, contexte
from apps.taches.serializers.journee import PLAFOND_LIGNES
from apps.taches.services import journee as services
from apps.taches.views.base import (
    PARSEURS, PERMISSIONS, corps, est_assistant, forme_echantillon, parametre, reponses)
from core.champs_stricts import BooleenStrict, ChaineStricte, EntierStrict
from core.conflit_etat import ConflitEtat
from core.idempotency import IdempotentCreateMixin

JOUR = parametre('jour', OpenApiTypes.DATE, 'Jour (AAAA-MM-JJ) ; défaut : aujourd\'hui.')
TOUT = parametre('tout', OpenApiTypes.BOOL, '1 : « Voir toutes les tâches de mes projets ».')
VRAI = ('1', 'true', 'oui')


def date_de(valeur, champ):
    """Une date AAAA-MM-JJ, ou 400 au champ nommé."""
    try:
        jour = datetime.date.fromisoformat(str(valeur))
    except (TypeError, ValueError):
        raise ValidationError({champ: [MESSAGE_DATE]})
    if not jour_dans_bornes(jour):
        raise ValidationError({champ: [MESSAGE_DATE]})
    return jour


def jour_de(request, champ='jour'):
    """`?jour=` (défaut : aujourd'hui, fuseau de la société)."""
    texte = request.query_params.get(champ)
    return date_de(texte, champ) if texte else timezone.localdate()


def maintenant():
    """Heure murale de la société."""
    return timezone.localtime()


def drapeau(request, champ):
    return (request.query_params.get(champ) or '').lower() in VRAI


def ids_de(request, champ):
    """`?exclure=41,42` → [41, 42] ; un morceau qui n'est pas un nombre est ignoré (lecture seule)."""
    morceaux = (request.query_params.get(champ) or '').split(',')
    return [int(m) for m in (m.strip() for m in morceaux)
            if m.isascii() and m.isdigit() and len(m) <= LONGUEUR_ID_MAX]


def par_compte(request):
    """Espace de clés d'idempotence propre au compte (deux comptes, même clé : deux gestes)."""
    return f'compte-{request.user.pk}'


def valide(classe, donnees):
    serializer = classe(data=donnees)
    serializer.is_valid(raise_exception=True)
    return serializer.validated_data


@contextmanager
def refus_en_400():
    """`services.journee.Refus` → 400 au champ nommé ; un refus d'ÉTAT (`RefusEtat` : bilan fermé, ★ déjà
    posées) → 409, même corps (le schéma ne peut pas dire l'heure qu'il est ni ce qui est déjà posé)."""
    try:
        yield
    except services.RefusEtat as exc:
        raise ConflitEtat(exc.erreurs)
    except services.Refus as exc:
        raise ValidationError(exc.erreurs)


# Les corps reçus SONT les schémas publiés (api-fuzz r2) : listes fermées, bornes et types stricts.
@extend_schema_serializer(component_name='TachesJourneeLigne')
class LigneCorps(CorpsTaches):
    type = Choix(choices=(services.TACHE, services.ACTIVITE))
    id = EntierStrict(min_value=1)


@extend_schema_serializer(component_name='TachesCorpsJourneePlanifier')
class PlanifierCorps(CorpsTaches):
    jour = DateBornee()
    mode = Choix(choices=(services.MODE_EXPRESS,), error_messages={'invalid_choice': services.MESSAGE_MODE})
    lignes = serializers.ListField(child=LigneCorps(), max_length=PLAFOND_LIGNES)
    essentielles = serializers.ListField(child=EntierStrict(min_value=1), required=False, default=list,
                                         max_length=classement.ESSENTIELS_MAX,
                                         error_messages={'max_length': services.MESSAGE_ESSENTIELS})
    triage = serializers.ListField(required=False, default=list)


@extend_schema_serializer(component_name='TachesCorpsJourneeEssentiel')
class EssentielCorps(CorpsTaches):
    tache_id = EntierStrict(min_value=1)
    essentielle = BooleenStrict()


@extend_schema_serializer(component_name='TachesCorpsJourneeAlleger')
class AllegerCorps(CorpsTaches):
    jour = DateBornee()
    garder = serializers.ListField(child=EntierStrict(min_value=1), max_length=PLAFOND_LIGNES)


@extend_schema_serializer(component_name='TachesJourneeChoixBilan')
class ChoixBilanCorps(CorpsTaches):
    id = EntierStrict(min_value=1)
    choix = Choix(choices=services.CHOIX_BILAN, error_messages={'invalid_choice': services.MESSAGE_CHOIX})
    jour = DateBornee(required=False)

    # « Un jour précis » exige son jour (`services.journee._appliquer_choix`).
    regles_croisees = ((valeur('choix', *(c for c in services.CHOIX_BILAN if c != Decision.JOUR)),
                        present('jour', DATE)),)


@extend_schema_serializer(component_name='TachesCorpsJourneeCloturer')
class CloturerCorps(CorpsTaches):
    jour = DateBornee()
    choix = serializers.ListField(child=ChoixBilanCorps(), required=False, default=list,
                                  max_length=PLAFOND_LIGNES)
    le_reste = BooleenStrict(required=False, default=False)
    reflexion = ChaineStricte(required=False, allow_blank=True, default='', max_length=280)


class AujourdhuiVue(APIView):
    """GET aujourdhui/ — LE contrat de la journée (§2)."""

    permission_classes = PERMISSIONS
    parser_classes = PARSEURS

    @extend_schema(parameters=[JOUR, TOUT], responses=reponses(forme_echantillon('aujourdhui'), erreurs=(400,)))
    def get(self, request):
        return Response(services.aujourdhui(request.user, jour_de(request), maintenant(),
                                            tout=drapeau(request, 'tout'), assistant=est_assistant(request)))


class BadgeVue(APIView):
    """GET badge/ — la pastille : ouverts GARDÉS d'Essentiel, Prévu et Ce soir."""

    permission_classes = PERMISSIONS
    parser_classes = PARSEURS

    @extend_schema(responses=reponses(forme_echantillon('badge')))
    def get(self, request):
        return Response(services.badge(request.user, timezone.localdate()))


class VuVue(APIView):
    """POST vu/ — ouverture du jour ; carte de retour."""

    permission_classes = PERMISSIONS
    parser_classes = PARSEURS

    @extend_schema(request=corps('Vu', {'ecran': 'aujourdhui'}),
                   responses=reponses(forme_echantillon('vu'), erreurs=(400,)))
    def post(self, request):
        heure = maintenant()
        return Response(services.vu(request.user, heure.date(), heure))


class PropositionJourneeVue(APIView):
    """GET journee/proposition/ — la proposition du jour, sans écriture."""

    permission_classes = PERMISSIONS
    parser_classes = PARSEURS

    @extend_schema(parameters=[
        JOUR, TOUT,
        parametre('exclure', OpenApiTypes.STR, 'Ids de tâches exclues, séparés par des virgules.'),
        parametre('inclure', OpenApiTypes.STR, 'Ids de tâches ajoutées, séparés par des virgules.'),
    ], responses=reponses(forme_echantillon('journee_proposition'), erreurs=(400,)))
    def get(self, request):
        heure = maintenant()
        return Response(services.proposition_du_jour(
            request.user, jour_de(request), heure, exclure=ids_de(request, 'exclure'),
            inclure=ids_de(request, 'inclure'), tout=drapeau(request, 'tout'), assistant=est_assistant(request)))


# --- Demandes prêtes du Copilote, sans modèle de langage (regles.md §12, A18-M3) ------------------
#
# Deux routes DÉTERMINISTES : elles servent « Aide-moi à prioriser » et « Où j'en suis ? » sans clé
# d'IA ni fournisseur. Lecture allégée de la journée : ni obligations ERP (aucune des deux cartes ne
# les montre), ni « À trier » — d'où des plafonds plus bas que ceux d'`aujourdhui/` (api.md §10).

RAISONS = frozenset(RaisonPropose.values)


def _journee_lue(user, jour):
    """(réglages, journée lue avec la forme ITEM) — la lecture commune des deux demandes."""
    reglages = sel.reglages_de(user)
    travailles = sel.travailles_autour(user, jour)
    journee = sel.lire_journee(user, jour, charger=charger_items, reglages=reglages, travailles=travailles)
    return reglages, journee


def _taches_gardees_ouvertes(journee):
    """Tâches ouvertes gardées (Essentiel, Prévu, Ce soir) : le « gardées ouvertes » de N (§3.4)."""
    return sum(1 for cle in sel.gardes_ouverts(journee) if cle[0] == services.TACHE)


def priorites(user, jour, *, assistant=False):
    """GET journee/priorites/ : toutes les ouvertes non gardées, classées par `classer_priorites`
    (ce qui presse, le tour des projets sans limite, puis À revoir), chacune avec sa raison — ou,
    pour À revoir, son motif ; `garder_n` = N de Proposé, `plus_tard` = geste « Plus tard dans la
    semaine »."""
    reglages, journee = _journee_lue(user, jour)
    compte, _detail = sel.compte_faites(user, jour)
    objectif = services.objectif_du_jour(reglages, jour, sel.preferences_de(user), journee.plan)
    taches = [item for item in journee.items.values() if item.type == services.TACHE]
    classees = classement.classer_priorites(
        taches, jour, journee.travailles, objectif['nb'], compte, _taches_gardees_ouvertes(journee),
        plan=journee.plan_pur)
    cles = [(services.TACHE, item.id) for item, _code in classees.lignes]
    raisons = {(services.TACHE, item.id): code for item, code in classees.lignes if code in RAISONS}
    (cles,), tronque = formes_journee.plafonner([cles])
    rendu = formes_journee.Rendu(journee, assistant=assistant)
    lignes = [{'rang': rang, 'item': forme} for rang, forme in enumerate(rendu.items(cles, raisons), start=1)]
    return {
        'jour': jour.isoformat(), 'objectif': dict(objectif), 'garder_n': classees.garder_n,
        'plus_tard': classees.plus_tard.isoformat() if classees.plus_tard else None,
        'lignes': lignes, 'tronque': tronque,
    }


def _contexte_du_point(user, heure, *, assistant=False):
    """Le contexte d'une journée pour « Où j'en suis ? » : tout ce que lit `aujourdhui/` SAUF les
    obligations ERP (non montrées) ; `peut_cloturer` reste lu (une activité peut être servie)."""
    jour = heure.date()
    reglages, journee = _journee_lue(user, jour)
    preferences = sel.preferences_de(user)
    closes = tuple(sel.activites_closes_du_jour(user, jour))
    compte, detail = sel.compte_faites(user, jour, closes)
    rendez_vous, agendas = sel.rendez_vous_pour(user, jour, jour)
    return services.Contexte(
        user=user, jour=jour, maintenant=heure, journee=journee,
        obligations=sel.Obligations(peut_cloturer=sel._peut_cloturer(user)), closes=closes,
        preferences=preferences, objectif=services.objectif_du_jour(reglages, jour, preferences, journee.plan),
        compte=compte, detail=detail,
        capacite=sel.capacite_du_jour(user, jour, reglages, preferences, journee.travailles),
        cartes=services._cartes_ouvertes(user, jour), assistant=assistant, rendez_vous=rendez_vous,
        agendas=agendas, rendez_vous_minutes=sel.minutes_de_rendez_vous(user, jour, rendez_vous))


def _ouvertes(journee, section):
    return [cle for cle in journee.sections.get(section, ()) if journee.items[cle].statut != StatutTache.FAIT]


def _prochaine(journee, heure):
    """La première ligne ouverte de Prévu hors essentielles — blocs encore à venir d'abord (heure ≥
    maintenant), puis les lignes sans heure, puis les blocs passés —, sinon de Ce soir, sinon None."""
    a_l_heure = heure.time().replace(second=0, microsecond=0)
    prevu = [cle for cle in _ouvertes(journee, SectionJournee.JOURNEE)
             if not (journee.ligne_de(cle) and journee.ligne_de(cle).essentielle)]
    heures = {cle: journee.items[cle].heure_debut for cle in prevu}
    a_venir = sorted((cle for cle in prevu if heures[cle] is not None and heures[cle] >= a_l_heure),
                     key=lambda cle: (heures[cle], cle[1]))
    sans_heure = [cle for cle in prevu if heures[cle] is None]
    passes = [cle for cle in prevu if heures[cle] is not None and heures[cle] < a_l_heure]
    ordre = a_venir + sans_heure + passes + _ouvertes(journee, SectionJournee.CE_SOIR)
    return ordre[0] if ordre else None


def _rendez_vous_restants(ctx, rendu):
    """Rendez-vous externes du jour qui commencent après maintenant (lecture seule)."""
    from apps.taches.serializers.formes import RendezVousSerializer
    apres = timezone.localtime(ctx.maintenant).replace(tzinfo=None)
    restants = [r for r in ctx.rendez_vous if sel.touche_le_jour(r, ctx.jour) and r.debut > apres]
    return list(RendezVousSerializer(restants, many=True, context=rendu.contexte()).data)


def point(user, heure, *, assistant=False):
    """GET journee/point/ : objectif, progression, essentielles restantes, la prochaine ligne, le
    nombre de gardées ouvertes, les rendez-vous restants et la carte du moment (regles.md §12)."""
    ctx = _contexte_du_point(user, heure, assistant=assistant)
    journee = ctx.journee
    rendu = formes_journee.Rendu(journee, assistant=assistant, peut_cloturer=ctx.obligations.peut_cloturer,
                                 agendas=ctx.agendas)
    prochaine = _prochaine(journee, heure)
    return {
        'jour': ctx.jour.isoformat(),
        'maintenant': heure.replace(microsecond=0).isoformat(),
        'objectif': dict(ctx.objectif),
        'progression': services.progression(ctx),
        'essentiel_restant': rendu.items(_ouvertes(journee, SectionJournee.ESSENTIEL)),
        'prochaine': rendu.items([prochaine])[0] if prochaine is not None else None,
        'restes_nb': len(sel.gardes_ouverts(journee)),
        'rendez_vous_restants': _rendez_vous_restants(ctx, rendu),
        'carte_du_moment': services._carte_du_moment(ctx, services.proposer(ctx)),
    }


class PrioritesVue(APIView):
    """GET journee/priorites/ — « Aide-moi à prioriser »."""

    permission_classes = PERMISSIONS
    parser_classes = PARSEURS

    @extend_schema(parameters=[JOUR], responses=reponses(forme_echantillon('priorites'), erreurs=(400,)))
    def get(self, request):
        return Response(priorites(request.user, jour_de(request), assistant=est_assistant(request)))


class PointVue(APIView):
    """GET journee/point/ — « Où j'en suis ? »."""

    permission_classes = PERMISSIONS
    parser_classes = PARSEURS

    @extend_schema(responses=reponses(forme_echantillon('point')))
    def get(self, request):
        return Response(point(request.user, maintenant(), assistant=est_assistant(request)))


class PlanifierJourneeVue(IdempotentCreateMixin, APIView):
    """POST journee/planifier/ — « Garder ces N » (mode `express`)."""

    permission_classes = PERMISSIONS
    parser_classes = PARSEURS

    @extend_schema(request=PlanifierCorps, responses=reponses(forme_echantillon('journee_ecrite'), erreurs=(400,)))
    def post(self, request):
        return self._avec_idempotence(request, lambda: self._planifier(request), suffixe=par_compte(request))

    def _planifier(self, request):
        corps_ = valide(PlanifierCorps, request.data)
        with refus_en_400():
            return Response(services.planifier_express(
                request.user, corps_['jour'], maintenant(), lignes=corps_['lignes'],
                essentielles=corps_['essentielles'], mode=corps_['mode'], assistant=est_assistant(request)))


class EssentielVue(APIView):
    """POST journee/essentiel/ — ★."""

    permission_classes = PERMISSIONS
    parser_classes = PARSEURS

    @extend_schema(request=EssentielCorps,
                   responses=reponses(TacheEcriteSerializer, erreurs=(400, 404)))
    def post(self, request):
        corps_ = valide(EssentielCorps, request.data)
        with refus_en_400():
            ecrite = services.marquer_essentielle(request.user, corps_['tache_id'], corps_['essentielle'],
                                                  maintenant())
        contexte_ = contexte(assistant=est_assistant(request))
        return Response(TacheEcriteSerializer(ecrite, context=contexte_).data)


class AllegerVue(IdempotentCreateMixin, APIView):
    """POST journee/alleger/ — garder k, le reste aux projets sans report."""

    permission_classes = PERMISSIONS
    parser_classes = PARSEURS

    @extend_schema(request=AllegerCorps,
                   responses=reponses(forme_echantillon('journee_ecrite'), erreurs=(400,)))
    def post(self, request):
        return self._avec_idempotence(request, lambda: self._alleger(request), suffixe=par_compte(request))

    def _alleger(self, request):
        corps_ = valide(AllegerCorps, request.data)
        return Response(services.alleger(request.user, corps_['jour'], maintenant(), garder=corps_['garder'],
                                         assistant=est_assistant(request)))


class ClotureVue(APIView):
    """GET journee/cloture/ — le contenu du bilan du soir."""

    permission_classes = PERMISSIONS
    parser_classes = PARSEURS

    @extend_schema(parameters=[JOUR], responses=reponses(forme_echantillon('journee_cloture'), erreurs=(400,)))
    def get(self, request):
        with refus_en_400():
            return Response(services.cloture(request.user, jour_de(request), maintenant(),
                                             assistant=est_assistant(request)))


class CloturerVue(IdempotentCreateMixin, APIView):
    """POST journee/cloturer/ — clore la journée."""

    permission_classes = PERMISSIONS
    parser_classes = PARSEURS

    @extend_schema(request=CloturerCorps, responses=reponses(forme_echantillon('journee_cloturee'), erreurs=(400,)))
    def post(self, request):
        return self._avec_idempotence(request, lambda: self._cloturer(request), suffixe=par_compte(request))

    def _cloturer(self, request):
        corps_ = valide(CloturerCorps, request.data)
        with refus_en_400():
            return Response(services.cloturer(request.user, corps_['jour'], maintenant(), choix=corps_['choix'],
                                              le_reste=corps_['le_reste'], reflexion=corps_['reflexion']))
