"""Vues hors-CRUD du module « Veille appels d'offres ».

VAO23 — ``POST /api/django/veille_ao/collecter/`` : le bouton « Rafraîchir
maintenant » lance **EXACTEMENT** le même job que le beat de nuit.

  Une seule mécanique, DEUX déclencheurs. Jamais un second chemin de collecte
  « pour le bouton » : c'est ainsi qu'on obtient deux comportements divergents
  (le bouton marche, la nuit non — ou l'inverse — et personne ne sait lequel
  croire). Le dispatch passe par ``core.jobs.submit(kind, task, company=…,
  user=…)`` → ``BackgroundJob``, jamais par une file maison : la progression et
  l'échec sont ceux de la plateforme, et l'écran les suit par le sondage
  générique des jobs de fond.

Le drapeau de désarmement (``VEILLE_AO_COLLECTE_ACTIVE=0``) s'applique ICI
AUSSI : le bouton soumet le job, et le job sort sans aucun appel réseau tant
que la collecte n'est pas armée (VAO4). Aucun chemin ne contourne la règle #5.

Toutes les vues de ce fichier sont scopées société côté serveur
(``request.user.company``) — jamais une société lue du corps de la requête.
"""
from __future__ import annotations

from drf_spectacular.utils import extend_schema
from rest_framework import status
from rest_framework.generics import GenericAPIView
from rest_framework.response import Response

from core.permissions import ScopedPermission

from .serializers import (
    AttributionSerializer, LancementCollecteSerializer, SanteVeilleSerializer,
)
from .viewsets import VEILLE_AO_GERER, VEILLE_AO_VOIR

__all__ = ['AttributionView', 'DeclencherCollecteView', 'KIND_COLLECTE',
           'SanteVeilleView']

#: Type logique du job de fond (``BackgroundJob.kind``). Le MÊME quel que soit
#: le déclencheur — c'est ce qui rend les deux chemins comparables dans
#: l'écran « Jobs de fond ».
KIND_COLLECTE = 'veille_ao_collecte'


def _societe(request):
    """La société de l'appelant — lue du JETON, jamais du corps de requête."""
    return getattr(request.user, 'company', None)


class _BaseVeilleView(GenericAPIView):
    """Socle commun : garde ``veille_ao_voir``/``veille_ao_gerer`` + scoping.

    ``get_queryset`` est scopé société même quand la vue n'expose pas de
    liste : c'est la garantie qu'aucune sous-classe ne pourra, par distraction,
    lire le sas d'une AUTRE société — et c'est ce que le balayage d'isolation
    multi-tenant vérifie mécaniquement.
    """

    permission_classes = [ScopedPermission]
    read_permission = VEILLE_AO_VOIR
    write_permission = VEILLE_AO_GERER

    def get_queryset(self):
        from .models import AvisMarche

        return AvisMarche.objects.filter(company=_societe(self.request))

    def societe(self):
        return _societe(self.request)


class DeclencherCollecteView(_BaseVeilleView):
    """``POST /api/django/veille_ao/collecter/`` — déclenchement MANUEL.

    Gated ``veille_ao_gerer`` (``write_permission`` — POST n'est pas une
    méthode sûre) : régler et déclencher la veille décide de ce que TOUTE la
    société voit.

    Un job de collecte déjà en cours pour cette société n'en relance pas un
    second (verrou par état, pas par variable de process) : un double clic ne
    lance pas deux collectes concurrentes. Le job existant est renvoyé tel
    quel, avec ``deja_en_cours=True`` — l'écran continue simplement à le
    suivre au lieu d'afficher une erreur.
    """

    serializer_class = LancementCollecteSerializer

    @extend_schema(request=None, responses=LancementCollecteSerializer)
    def post(self, request, *args, **kwargs):
        from core.jobs import submit
        from core.models import BackgroundJob

        from .tasks import MOTIF_DESARME, collecte_active, collecte_quotidienne

        company = self.societe()

        en_cours = BackgroundJob.objects.filter(
            company=company, kind=KIND_COLLECTE,
            statut__in=[BackgroundJob.STATUT_QUEUED,
                        BackgroundJob.STATUT_RUNNING],
        ).order_by('-created_at').first()
        if en_cours is not None:
            return Response(
                self._charge(en_cours, deja_en_cours=True),
                status=status.HTTP_200_OK)

        # EXACTEMENT la tâche du beat — jamais une variante « pour le bouton ».
        job = submit(KIND_COLLECTE, collecte_quotidienne,
                     company=company, user=request.user,
                     company_id=getattr(company, 'pk', None),
                     user_id=request.user.pk)
        return Response(
            self._charge(job, deja_en_cours=False,
                         armee=collecte_active(),
                         motif='' if collecte_active() else MOTIF_DESARME),
            status=status.HTTP_202_ACCEPTED)

    @staticmethod
    def _charge(job, *, deja_en_cours, armee=None, motif=''):
        """La forme que l'écran consomme (``job_id`` ET ``id`` : le sondage
        générique des jobs de fond retrouve la ligne par ``id``)."""
        from .tasks import collecte_active

        return {
            'id': job.pk,
            'job_id': job.pk,
            'kind': job.kind,
            'statut': job.statut,
            'progress_pct': job.progress_pct,
            'deja_en_cours': deja_en_cours,
            'collecte_active': (collecte_active() if armee is None else armee),
            'motif': motif,
        }


class SanteVeilleView(_BaseVeilleView):
    """``GET /api/django/veille_ao/sante/`` — l'état de la veille en UN appel.

    Agrège, côté SERVEUR : dernière collecte réussie et son ÂGE, avis
    examinés hier, alarme de silence (VAO24), armement de la collecte
    (règle #5). Le bandeau de santé (VAO37) et l'écran de paramètres (VAO35)
    consomment la MÊME réponse — jamais un agrégat recalculé côté client à
    partir de la liste des exécutions, qui divergerait tôt ou tard.

    Lecture : ``veille_ao_voir``. L'état de la veille intéresse tous ceux qui
    la lisent, pas seulement ceux qui la règlent.
    """

    serializer_class = SanteVeilleSerializer

    @extend_schema(responses=SanteVeilleSerializer)
    def get(self, request, *args, **kwargs):
        from .services import sante

        return Response(
            SanteVeilleSerializer(sante(self.societe())).data)


class AttributionView(_BaseVeilleView):
    """``GET /api/django/veille_ao/attribution/`` — d'où vient le chiffre.

    VAO31 : « canal → avis → affaires → gagnés », CALCULÉ côté serveur et
    jamais saisi. L'issue des affaires est lue par le ``selectors.py``
    d'``apps.ao``, jamais par ses modèles.

    Deux axes rendus ENSEMBLE — par source ET par informateur : le second est
    tout l'intérêt de la mesure, puisqu'il rend visible ce que la veille
    automatique ne voit pas. Un agrégat recalculé côté client sur la liste des
    avis ne pourrait pas connaître l'issue des affaires.
    """

    serializer_class = AttributionSerializer

    @extend_schema(responses=AttributionSerializer)
    def get(self, request, *args, **kwargs):
        from .selectors import attribution

        return Response(
            AttributionSerializer(attribution(self.societe())).data)
