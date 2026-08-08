"""Socle de ViewSets du module Appels d'offres (``apps.ao``) — AOF3.

Constat corrigé ici : les 8 ViewSets AO héritaient de ``_ComptaBaseViewSet``
(``TenantMixin`` + ``ModelViewSet`` + ``IsResponsableOrAdmin``). Deux
conséquences : ``scripts/check_platform.py`` refuse tout NOUVEAU ``ModelViewSet``
non basé sur ``CompanyScopedModelViewSet`` (SCA4), et surtout tout le palier
Responsable voyait l'intégralité d'un dossier d'appel d'offres alors qu'aucune
permission ``ao_*`` n'existait (régression de confidentialité, cf. AOF2).

``AoBaseViewSet`` = ``core.viewsets.CompanyScopedModelViewSet`` (scoping
``request.user.company`` + ``company`` forcée côté serveur, détection
automatique par le sweep d'isolation multi-tenant) + le chatter générique
``records`` (``ChatterViewSetMixin``, ARC8 — jamais une classe ``*Activity``
maison), gardé par ``ao_voir`` (lecture) / ``ao_gerer`` (écriture).

Composition des permissions
---------------------------
``ScopedPermission`` s'applique TOUJOURS (elle porte ``ao_voir``/``ao_gerer``),
et une ``@action`` qui déclare sa PROPRE garde la voit AJOUTÉE, jamais
substituée. C'est volontaire : les actions de chatter héritées de ``records``
déclarent ``IsAnyRole``/``IsResponsableOrAdmin``, or ces gardes-là
ROUVRIRAIENT sur le chatter d'un AO exactement la fuite que AOF2 ferme (un
Commercial lirait la timeline d'un dossier qu'il n'a pas le droit de voir). En
cumulant, la garde du domaine AO reste le plancher et la garde déclarée par
l'action reste un plafond supplémentaire — aucune déclaration n'est perdue en
silence (cf. ``core.permissions.declared_action_permissions``).
"""
from __future__ import annotations

from django.core.exceptions import ValidationError as DjangoValidationError
from rest_framework import filters, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.settings import api_settings

from apps.records.views import ChatterViewSetMixin
from core.documents import TransitionRefusee
from core.permissions import ScopedPermission, declared_action_permissions
from core.viewsets import CompanyScopedModelViewSet

from . import services
from .models import (
    DossierAO, LigneChecklistPartenaire, PieceAdministrative, PieceDossierAO,
)
from .permissions import AO_GERER, AO_VOIR
from .serializers import (
    DossierAOSerializer, LigneChecklistPartenaireSerializer,
    PieceAdministrativeSerializer, PieceDossierAOSerializer,
)

__all__ = [
    'AoBaseViewSet',
    'DossierAOViewSet',
    'LigneChecklistPartenaireViewSet',
    'PieceAdministrativeViewSet',
    'PieceDossierAOViewSet',
]


class AoBaseViewSet(ChatterViewSetMixin, CompanyScopedModelViewSet):
    """Base UNIQUE des ViewSets du domaine Appels d'offres.

    * société scopée + ``company`` posée côté serveur (jamais lue du corps) ;
    * lecture gardée par ``ao_voir``, écriture par ``ao_gerer`` ;
    * chatter générique ``records`` (``chatter/historique``, ``chatter/noter``).
    """

    read_permission = AO_VOIR
    write_permission = AO_GERER

    def get_permissions(self):
        permissions = [ScopedPermission()]
        declared = declared_action_permissions(self)
        if declared is not None:
            # CUMUL (jamais substitution) — voir le docstring du module.
            permissions.extend(declared)
        return permissions


# ── AOF115 — Dossier de dépôt (kit ``core/documents.py``) ──────────────────

class DossierAOViewSet(AoBaseViewSet):
    """Dossiers de dépôt d'AO (AOF115) — statut GARDÉ par la table du kit.

    ``perform_create`` attribue la référence ``AODOS-YYYYMM-0001`` via
    ``core.numbering`` (jamais ``count()+1``). Le chatter générique
    ``records`` est hérité d'``AoBaseViewSet`` : AUCUNE classe ``*Activity``
    maison n'est créée pour ce document.
    """
    queryset = DossierAO.objects.prefetch_related('pieces').all()
    serializer_class = DossierAOSerializer
    filter_backends = [filters.OrderingFilter]
    ordering_fields = ['created_at', 'statut']

    def get_queryset(self):
        qs = super().get_queryset()
        for champ in ('appel_offre', 'statut'):
            valeur = self.request.query_params.get(champ)
            if valeur not in (None, ''):
                qs = qs.filter(**{champ: valeur})
        return qs

    def perform_create(self, serializer):
        """Société posée côté serveur + référence ``AODOS`` race-safe (ARC6)."""
        company = self.request.user.company
        services.creer_dossier_ao(
            company,
            save_fn=lambda reference: serializer.save(
                company=company, reference=reference))

    @action(detail=True, methods=['post'], url_path='changer-statut')
    def changer_statut(self, request, pk=None):
        """Fait avancer le dossier — refus 400 motivé si la porte est fermée."""
        dossier = self.get_object()
        cible = (request.data.get('statut') or '').strip()
        motif = (request.data.get('motif') or '').strip()
        try:
            services.changer_statut_dossier(
                dossier, cible, user=request.user, motif=motif)
        except TransitionRefusee as exc:
            return Response(
                {api_settings.NON_FIELD_ERRORS_KEY: [str(exc)]},
                status=status.HTTP_400_BAD_REQUEST)
        except DjangoValidationError as exc:
            donnees = getattr(exc, 'message_dict', None) or {
                api_settings.NON_FIELD_ERRORS_KEY: exc.messages}
            return Response(donnees, status=status.HTTP_400_BAD_REQUEST)
        return Response(self.get_serializer(dossier).data)

    @action(detail=True, methods=['get'], url_path='completude')
    def completude(self, request, pk=None):
        """Complétude DÉRIVÉE + motifs de refus, en français."""
        dossier = self.get_object()
        manquantes = dossier.pieces_obligatoires_manquantes()
        return Response({
            'complet': dossier.complet,
            'taux_completude': str(dossier.taux_completude),
            'pieces_manquantes': [
                {'code': p.code, 'libelle': p.libelle} for p in manquantes],
            'raisons_de_non_depot': dossier.raisons_de_non_depot(),
        })

    @action(detail=True, methods=['post'], url_path='initialiser-checklist')
    def initialiser_checklist(self, request, pk=None):
        """AOF136 — crée les points de checklist manquants (idempotent)."""
        dossier = self.get_object()
        crees, existants = services.seeder_checklist_partenaire(dossier)
        return Response({'crees': crees, 'deja_presents': existants})

    @action(detail=True, methods=['post'], url_path='controler')
    def controler(self, request, pk=None):
        """AOF146 — exécute la passe de cohérence croisée et la persiste."""
        from .fabrique.coherence import passer_controle

        dossier = self.get_object()
        passe = passer_controle(dossier)
        return Response({
            'empreinte': passe['empreinte'],
            'bloquant': bool(passe['bloquants']),
            'bloquants': passe['bloquants'],
            'avertissements': passe['avertissements'],
            # AOF149 — comptées ET nommées : jamais tues.
            'nombre_hors_controle': passe['nombre_hors_controle'],
            'hors_controle': passe['hors_controle'],
        })

    @action(detail=True, methods=['get'], url_path='controles-avant-depot')
    def controles_avant_depot(self, request, pk=None):
        """AOF176 — la passe de cohérence en LECTURE : un GET n'écrit rien.

        ``controler`` (POST, ci-dessus) reste le chemin qui FIGE la passe en
        base ; celui-ci la rejoue pour l'écran sans toucher une ligne. Les
        deux répondent des mêmes règles et des mêmes pièces hors contrôle —
        un écran qui verrait une autre vérité que la porte de statut serait
        pire qu'un écran absent.
        """
        from .fabrique.coherence import passe_en_lecture

        return Response(passe_en_lecture(self.get_object()))

    # ── PACT25 — les trois chemins enfin OUVERTS ────────────────────────────
    #
    # Ils étaient délibérément fermés tant que `services.producteurs_de_pack`
    # n'existait pas : ouvrir la porte aurait produit un job « terminé » avec
    # zéro pièce, donc un écran affichant « pack prêt » sur une archive vide.
    # Le monteur existe désormais, ET la tâche part en ÉCHEC sur un pack vide
    # ou incomplet — la porte peut s'ouvrir sans mentir.

    @action(detail=True, methods=['post'], url_path='generer-piece')
    def generer_piece(self, request, pk=None):
        """Lance la production du pack en tâche de fond (idempotente).

        Renvoie l'identifiant du ``BackgroundJob`` à suivre via
        ``statut-de-job``. Refus 400 MOTIVÉ quand le dossier ne déclare aucune
        pièce générable : un job sans rien à produire est un faux succès en
        attente.
        """
        dossier = self.get_object()
        try:
            job = services.generer_pack_ao(dossier, user=request.user)
        except DjangoValidationError as exc:
            donnees = getattr(exc, 'message_dict', None) or {
                api_settings.NON_FIELD_ERRORS_KEY: exc.messages}
            return Response(donnees, status=status.HTTP_400_BAD_REQUEST)
        return Response(
            {'job_id': job.pk, 'statut': job.statut,
             'dossier': dossier.pk},
            status=status.HTTP_202_ACCEPTED)

    @action(detail=True, methods=['get'], url_path='statut-de-job')
    def statut_de_job(self, request, pk=None):
        """Suivi d'un job de pack — SCOPÉ SOCIÉTÉ. ``?job=<id>``.

        Un job d'une autre société est INTROUVABLE (404), jamais « interdit » :
        un 403 confirmerait son existence. Même patron que
        ``ResultatCalepinageView``.

        Le job est un PARAMÈTRE DE REQUÊTE, pas un second segment de chemin :
        un ``url_path`` à groupe nommé rend la route illisible aux gardes de
        contrat front↔back (``scripts/check_ao_api_contract.py``), et une route
        qu'un garde ne sait pas lire est une route qu'il ne protège pas.
        """
        from core.models import BackgroundJob

        dossier = self.get_object()
        job_id = request.query_params.get('job')
        if not job_id:
            return Response(
                {api_settings.NON_FIELD_ERRORS_KEY: [
                    'Paramètre `job` requis.']},
                status=status.HTTP_400_BAD_REQUEST)
        job = BackgroundJob.objects.filter(
            pk=job_id, company=dossier.company).first()
        if job is None:
            return Response({'detail': 'Tâche introuvable.'},
                            status=status.HTTP_404_NOT_FOUND)
        return Response({
            'job_id': job.pk,
            'statut': job.statut,
            'progression': job.progress_pct,
            'message_erreur': job.message_erreur,
        })

    @action(detail=True, methods=['get'], url_path='zip')
    def zip(self, request, pk=None):
        """Archive de dépôt — REFUSÉE si un contrôle est rouge ou si vide.

        ``fabrique.pack_zip.ecrire_pack_zip`` porte les deux refus (contrôle
        bloquant, aucune pièce déposable) et écrit le ``MANIFESTE.json`` : on
        ne réimplémente rien ici, on lui fournit enfin ses pièces.
        """
        import io

        from django.http import HttpResponse

        from .fabrique.coherence import empreinte_dossier, passe_en_lecture
        from .fabrique.pack_zip import PackRefuse, ecrire_pack_zip

        dossier = self.get_object()
        empreinte = empreinte_dossier(dossier)
        entrees = services.pieces_du_pack_en_flux(dossier, empreinte=empreinte)
        tampon = io.BytesIO()
        try:
            ecrire_pack_zip(
                tampon, entrees, controle=passe_en_lecture(dossier),
                reference_dossier=dossier.reference or dossier.intitule,
                empreinte_pack=empreinte)
        except PackRefuse as exc:
            return Response(
                {api_settings.NON_FIELD_ERRORS_KEY: [str(exc)]},
                status=status.HTTP_400_BAD_REQUEST)
        except DjangoValidationError as exc:
            return Response(
                {api_settings.NON_FIELD_ERRORS_KEY: exc.messages},
                status=status.HTTP_400_BAD_REQUEST)
        reponse = HttpResponse(tampon.getvalue(),
                               content_type='application/zip')
        nom = (dossier.reference or f'dossier-{dossier.pk}').replace(' ', '-')
        reponse['Content-Disposition'] = f'attachment; filename="{nom}.zip"'
        return reponse

    @action(detail=True, methods=['get'], url_path='controle-administratif')
    def controle_administratif(self, request, pk=None):
        """AOF137 — péremption contrôlée à la DATE DE REMISE DES PLIS."""
        dossier = self.get_object()
        controles = services.controler_pieces_administratives(dossier)
        bloquants = [c for c in controles
                     if c['severite'] == services.SEVERITE_BLOQUANT]
        return Response({
            'date_reference': dossier.date_reference_controle,
            'bloquant': bool(bloquants),
            'controles': controles,
        })


class PieceDossierAOViewSet(AoBaseViewSet):
    """Pièces d'un dossier de dépôt (AOF115)."""
    queryset = PieceDossierAO.objects.all()
    serializer_class = PieceDossierAOSerializer
    filter_backends = [filters.OrderingFilter]
    ordering_fields = ['ordre', 'code']

    def get_queryset(self):
        qs = super().get_queryset()
        for champ in ('dossier', 'visibilite', 'type_piece', 'obligatoire'):
            valeur = self.request.query_params.get(champ)
            if valeur not in (None, ''):
                qs = qs.filter(**{champ: valeur})
        return qs


class LigneChecklistPartenaireViewSet(AoBaseViewSet):
    """Points de la checklist partenaire (AOF136) — consultables et éditables.

    L'action ``pointer`` trace TOUJOURS le responsable côté serveur : une
    checklist qui ne dit pas qui répond d'un point est un document mort.
    """
    queryset = LigneChecklistPartenaire.objects.all()
    serializer_class = LigneChecklistPartenaireSerializer
    filter_backends = [filters.OrderingFilter]
    ordering_fields = ['ordre', 'bloc', 'code']

    def get_queryset(self):
        qs = super().get_queryset()
        for champ in ('dossier', 'bloc', 'faite', 'obligatoire'):
            valeur = self.request.query_params.get(champ)
            if valeur not in (None, ''):
                qs = qs.filter(**{champ: valeur})
        return qs

    @action(detail=True, methods=['post'])
    def pointer(self, request, pk=None):
        """Pointe (ou dépointe) le point — responsable posé côté serveur."""
        ligne = self.get_object()
        faite = request.data.get('faite', True)
        if isinstance(faite, str):
            faite = faite.strip().lower() not in ('false', '0', 'non', '')
        services.pointer_checklist(
            ligne, faite=bool(faite), user=request.user,
            commentaire=request.data.get('commentaire'))
        return Response(self.get_serializer(ligne).data)


class PieceAdministrativeViewSet(AoBaseViewSet):
    """Pièces administratives DATÉES, réutilisables d'un AO à l'autre (AOF137).

    ``rattacher`` ajoute la pièce à un dossier SANS dupliquer le fichier —
    c'est tout l'intérêt d'une pièce scopée société plutôt que scopée dossier.
    """
    queryset = PieceAdministrative.objects.all()
    serializer_class = PieceAdministrativeSerializer
    filter_backends = [filters.OrderingFilter]
    ordering_fields = ['type_piece', 'date_emission']

    def get_queryset(self):
        qs = super().get_queryset()
        for champ in ('type_piece', 'actif'):
            valeur = self.request.query_params.get(champ)
            if valeur not in (None, ''):
                qs = qs.filter(**{champ: valeur})
        dossier = self.request.query_params.get('dossier')
        if dossier not in (None, ''):
            qs = qs.filter(dossiers=dossier)
        return qs

    @action(detail=True, methods=['post'])
    def rattacher(self, request, pk=None):
        """Rattache la pièce à un dossier — un seul octet stocké."""
        piece = self.get_object()
        dossier_id = request.data.get('dossier')
        dossier = DossierAO.objects.filter(
            pk=dossier_id, company=request.user.company).first()
        if dossier is None:
            return Response(
                {'dossier': 'Dossier introuvable pour cette société.'},
                status=status.HTTP_400_BAD_REQUEST)
        try:
            services.rattacher_piece_administrative(
                piece, dossier, user=request.user)
        except DjangoValidationError as exc:
            donnees = getattr(exc, 'message_dict', None) or {
                api_settings.NON_FIELD_ERRORS_KEY: exc.messages}
            return Response(donnees, status=status.HTTP_400_BAD_REQUEST)
        return Response(self.get_serializer(piece).data)

    @action(detail=False, methods=['get'], url_path='a-renouveler')
    def a_renouveler(self, request):
        """Pièces entrant dans leur fenêtre de rappel (J-N)."""
        pieces = services.pieces_administratives_a_renouveler(
            request.user.company)
        return Response(self.get_serializer(pieces, many=True).data)
