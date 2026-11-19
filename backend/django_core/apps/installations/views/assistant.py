"""Copilote vague 2 (CHTA2, CHTA3, CHTA5) — routes MINCES de l'assistant sur
les chantiers, greffées sur ``InstallationViewSet`` par ce mixin (même
octroi de lecture, même ``get_queryset`` borné à la société et à la portée,
mêmes gardes : chaque action est rangée dans la liste qui convient de
``InstallationViewSet.get_permissions``).

* ``GET chantiers/{id}/etat-assistant/`` — la fiche compacte
  (``contract_samples/assistant_chantier_etat.json``) ;
* ``GET chantiers/assistant/`` — la liste compacte
  (``contract_samples/assistant_chantiers.json``) ; un paramètre hors liste ou
  hors borne → 400 ``{detail, field, code}`` ;
* ``POST chantiers/{id}/planifier-pose/`` — date + technicien + intervention
  de pose en un geste (``contract_samples/chantier_planifier_pose.json``),
  service :mod:`apps.installations.planification_pose` ; rend la fiche relue.

Les dictionnaires renvoyés sont construits par
:mod:`apps.installations.selectors_assistant` (littéraux, clés de
l'échantillon). Aucun prix, aucun coût, aucune position de personne.
"""
from django.utils import timezone
from django.utils.dateparse import parse_date
from rest_framework.decorators import action
from rest_framework import serializers
from rest_framework.exceptions import ValidationError
from rest_framework.generics import get_object_or_404
from rest_framework.response import Response

from authentication.permissions import IsResponsableOrAdmin, LectureDuModule
from apps.roles.permissions import DroitDeLaGrille
from core.champs_stricts import BooleenStrict, DateStricte, EntierStrict
from core.conflit_etat import ConflitEtat

from .. import planification_pose, selectors_assistant
from ..models import Installation
from . import _openapi as oa

#: Statuts filtrables (canoniques, sauf « Clôturé » : exclu de la liste).
STATUTS_LISTE = tuple(s.value for s in Installation.STATUT_ORDER
                      if s != Installation.Statut.CLOTURE)
Q_MAX = 100

#: Bornes RÉELLES lues par ``_lire_liste`` (le schéma publié = ce que la vue lit) :
#: un identifiant vaut 1..ID_MAX ; la chaîne vide pose le défaut / n'applique rien.
_Q_SCHEMA = {'type': 'string', 'maxLength': Q_MAX, 'pattern': r'^[^\u0000]*$'}
PARAMETRES_LISTE = [
    oa.qs('vue', enum=selectors_assistant.VUES,
          desc='en_cours (défaut), bloques ou poses_semaine.'),
    oa.q('q', _Q_SCHEMA,
         desc='Référence du chantier ou nom du client (100 caractères au plus).'),
    oa.qid('lead', desc="Id du lead d'origine du chantier."),
    oa.qs('statut', enum=STATUTS_LISTE, desc='Statut du chantier (couche propre).'),
    oa.qid('technicien', desc='Id du technicien responsable.'),
    oa.qdv('debut', desc='Un jour de la semaine voulue (poses_semaine) ; ramené au lundi.'),
    oa.q('limite', {'type': 'integer', 'minimum': 1,
                    'maximum': selectors_assistant.LIMITE_MAX},
         desc='Nombre de lignes, 1 à 25 (défaut 10).'),
]

#: Corps publié de ``planifier-pose`` : tel que ``_corps_planifier`` le lit
#: (un champ hors liste est refusé 400 qui le nomme — publié ``additionalProperties: false``).
CORPS_PLANIFIER_SCHEMA = {
    'type': 'object', 'additionalProperties': False,
    'required': ['date_pose_prevue'],
    'properties': {
        'date_pose_prevue': {'type': 'string', 'format': 'date'},
        'date_pose_fin_prevue': {'type': 'string', 'format': 'date', 'nullable': True},
        'technicien': {'type': 'integer', 'minimum': 1, 'maximum': oa.ID_MAX,
                       'nullable': True},
        'creer_intervention': {'type': 'boolean'},
    },
}


def _refus(champ, code, detail):
    return ValidationError({'detail': detail, 'field': champ, 'code': code})


def _entier(params, nom, maxi=oa.ID_MAX):
    brut = params.get(nom)
    if brut in (None, ''):
        return None
    if not brut.isdigit() or not 1 <= int(brut) <= maxi:
        raise _refus(nom, f'{nom}_invalide', f'{nom} : entier entre 1 et {maxi}.')
    return int(brut)


def _lire_liste(params):
    """Paramètres validés de la liste ; ``statut`` et ``technicien`` sont
    appliqués par ``get_queryset`` (mêmes filtres que l'écran)."""
    vue = params.get('vue') or 'en_cours'
    if vue not in selectors_assistant.VUES:
        raise _refus('vue', 'vue_inconnue', 'vue : en_cours, bloques ou poses_semaine.')
    statut = params.get('statut')
    if statut and statut not in STATUTS_LISTE:
        raise _refus('statut', 'statut_inconnu', 'statut : ' + ', '.join(STATUTS_LISTE) + '.')
    q = (params.get('q') or '').strip()
    if len(q) > Q_MAX or '\x00' in q:
        raise _refus('q', 'q_invalide', f'q : {Q_MAX} caractères au plus, sans caractère nul.')
    debut = None
    if params.get('debut'):
        try:
            debut = parse_date(params['debut'])
        except ValueError:
            debut = None
        if debut is None:
            raise _refus('debut', 'debut_invalide', 'debut : une date AAAA-MM-JJ.')
    _entier(params, 'technicien')
    limite = _entier(params, 'limite', selectors_assistant.LIMITE_MAX)
    return {'vue': vue, 'q': q, 'lead': _entier(params, 'lead'), 'debut': debut,
            'limite': limite or selectors_assistant.LIMITE_DEFAUT}


class PlanifierPoseRequete(serializers.Serializer):
    """CHTA5 — corps de ``planifier-pose`` : RIEN d'autre (jamais un motif de
    passe-outre d'acompte, de réouverture ni de dérogation)."""
    date_pose_prevue = DateStricte()
    date_pose_fin_prevue = DateStricte(required=False, allow_null=True)
    technicien = EntierStrict(min_value=1, max_value=oa.ID_MAX, required=False,
                              allow_null=True)
    creer_intervention = BooleenStrict(required=False, default=True)


CHAMPS_PLANIFIER = ('date_pose_prevue', 'date_pose_fin_prevue', 'technicien',
                    'creer_intervention')


def _corps_planifier(request):
    """Corps validé ; un champ hors liste → 400 qui le nomme (un motif de
    passe-outre envoyé ici n'est jamais lu en silence)."""
    donnees = request.data if hasattr(request.data, 'keys') else {}
    inconnus = sorted(set(donnees) - set(CHAMPS_PLANIFIER))
    if inconnus:
        raise _refus(inconnus[0], 'champ_refuse', f'{inconnus[0]} : champ non accepté '
                     f'(seulement {", ".join(CHAMPS_PLANIFIER)}).')
    return oa.corps_valide(PlanifierPoseRequete, request)


class ChantierAssistantMixin:
    """Actions de l'assistant d'``InstallationViewSet`` (voir le module)."""

    def _chantier_assistant(self):
        """Le chantier ``pk`` DANS la portée de l'écran (404 sinon), sans les
        préchargements de la liste (inutiles à une fiche compacte)."""
        qs = self.get_queryset().prefetch_related(None)
        inst = get_object_or_404(qs, pk=self.kwargs.get('pk'),
                                 company=self.request.user.company)
        self.check_object_permissions(self.request, inst)
        return inst

    # headless: lu par l'action d'assistant `installations.chantier.etat`.
    @oa.extend_schema(responses={200: oa.OBJ, 404: oa.OBJ})
    @action(detail=True, methods=['get'], url_path='etat-assistant',
            permission_classes=[LectureDuModule])
    def etat_assistant(self, request, pk=None):
        """CHTA2 — prêt à poser ? pourquoi ? matériel (quantités), acompte,
        pose, étape suivante, ``a_faire`` et liens. Lecture seule."""
        inst = self._chantier_assistant()
        return Response(selectors_assistant.etat_chantier(
            inst, aujourdhui=timezone.localdate()))

    # headless: lu par l'action d'assistant `installations.chantiers.liste`.
    @oa.extend_schema(parameters=PARAMETRES_LISTE, responses={200: oa.OBJ, 400: oa.OBJ})
    @action(detail=False, methods=['get'], url_path='assistant',
            permission_classes=[LectureDuModule])
    def liste_assistant(self, request):
        """CHTA3 — chantiers en cours, bloqués (sans le besoin matériel) ou
        posés dans la semaine, dans la portée de l'écran. Lecture seule."""
        lus = _lire_liste(request.query_params)
        base = self.get_queryset().prefetch_related(None)
        return Response(selectors_assistant.liste_chantiers(
            base, request.user.company, aujourdhui=timezone.localdate(), **lus))

    # headless: écrit par l'action d'assistant `installations.chantier.planifier`.
    @oa.extend_schema(request=CORPS_PLANIFIER_SCHEMA,
                      responses={200: oa.OBJ, 400: oa.OBJ, 404: oa.OBJ, 409: oa.OBJ})
    @action(detail=True, methods=['post'], url_path='planifier-pose',
            permission_classes=[IsResponsableOrAdmin,
                                DroitDeLaGrille('installation_gerer'),
                                DroitDeLaGrille('intervention_gerer'),
                                DroitDeLaGrille('technicien_assign', champ='technicien')])
    def planifier_pose(self, request, pk=None):
        """CHTA5 — pose la date et le technicien du chantier ET l'intervention
        de pose ; le statut ne change pas ; refus nommés (409 / 400)."""
        inst = self._chantier_assistant()  # 404 AVANT le corps : un autre id = 404
        corps = _corps_planifier(request)
        try:
            inst = planification_pose.planifier_pose(
                inst, request.user, date_pose=corps['date_pose_prevue'],
                date_fin=corps.get('date_pose_fin_prevue'),
                technicien_id=corps.get('technicien'),
                creer_intervention=corps['creer_intervention'],
                aujourdhui=timezone.localdate())
        except planification_pose.PoseRefusee as refus:
            motif = {'detail': refus.detail, 'field': refus.champ, 'code': refus.code}
            raise (ConflitEtat(motif) if refus.statut_http == 409
                   else ValidationError(motif)) from refus
        return Response(selectors_assistant.etat_chantier(
            inst, aujourdhui=timezone.localdate()))
