"""AOF157 — endpoints de l'ÉCONOMIE d'un appel d'offres (DIRECTEUR SEUL).

Module SÉPARÉ des vues AO générales, et gardé par ``CanViewAoRentabilite``
(permission ``ao_rentabilite_voir``, ÉLEVÉE : non octroyable par un
non-administrateur, mappée sur AUCUN rôle Responsable/Commercial/Technicien/
Utilisateur — seuls Directeur et Administrateur la portent par héritage
d'``ALL_PERMISSIONS``).

Le socle reste ``CompanyScopedModelViewSet`` (scoping société + ``company``
posée côté serveur) : la garde de rentabilité s'AJOUTE, elle ne remplace pas
l'isolation multi-tenant.

Le VERROU de l'économie est respecté ici : une économie verrouillée n'accepte
plus d'écriture — une cascade de prix déjà propagée ne se laisse pas modifier
sous les pièces qui la citent.
"""
from __future__ import annotations

import re

from django.http import Http404, HttpResponse
from rest_framework import filters, status
from rest_framework.decorators import action
from rest_framework.exceptions import PermissionDenied
from rest_framework.response import Response

from core.viewsets import CompanyScopedModelViewSet

from .fabrique.rendus.rentabilite_xlsx import MIME_XLSX
from .models import CibleFinanciere, EconomieAO, LigneCoutRevient
from .permissions import CanViewAoRentabilite
from .serializers_directeur import (
    CibleFinanciereSerializer, EconomieAOSerializer,
    LigneCoutRevientSerializer,
)

__all__ = [
    'KIND_RENTABILITE_XLSX',
    'CibleFinanciereViewSet',
    'EconomieAOViewSet',
    'LigneCoutRevientViewSet',
]

#: Type logique du job de production du classeur (``BackgroundJob.kind``).
KIND_RENTABILITE_XLSX = 'ao_rentabilite_xlsx'

#: Caractères conservés dans le nom de fichier proposé au navigateur.
_NOM_SUR = re.compile(r'[^A-Za-z0-9._-]+')


class _BaseDirecteurViewSet(CompanyScopedModelViewSet):
    """Base des vues d'économie : société scopée + ``ao_rentabilite_voir``."""

    permission_classes = [CanViewAoRentabilite]

    def get_permissions(self):
        return [CanViewAoRentabilite()]

    @staticmethod
    def _refuser_si_verrouillee(economie):
        if economie is not None and economie.verrouillee:
            raise PermissionDenied(
                "L'économie de cet appel d'offres est VERROUILLÉE : une "
                'cascade de prix déjà propagée ne se modifie pas sous les '
                'pièces qui la citent.')


class EconomieAOViewSet(_BaseDirecteurViewSet):
    """Économie d'un AO — coût de revient, TVA, marge (directeur seul)."""

    queryset = EconomieAO.objects.prefetch_related('lignes', 'cibles').all()
    serializer_class = EconomieAOSerializer
    filter_backends = [filters.OrderingFilter]
    ordering_fields = ['appel_offre']

    def get_queryset(self):
        qs = super().get_queryset()
        appel_offre = self.request.query_params.get('appel_offre')
        if appel_offre not in (None, ''):
            qs = qs.filter(appel_offre=appel_offre)
        return qs

    def perform_update(self, serializer):
        self._refuser_si_verrouillee(serializer.instance)
        super().perform_update(serializer)

    def perform_destroy(self, instance):
        self._refuser_si_verrouillee(instance)
        super().perform_destroy(instance)

    @action(detail=True, methods=['get'])
    def synthese(self, request, pk=None):
        """La chaîne complète, en une lecture — tout est DÉRIVÉ."""
        economie = self.get_object()
        return Response({
            'cout_revient_ht': str(economie.cout_revient_ht),
            'cout_regime_reduit_ht': str(economie.cout_regime_reduit_ht),
            'cout_regime_standard_ht': str(economie.cout_regime_standard_ht),
            'tva_deductible': str(economie.tva_deductible),
            'benefice_net_cible_ht': str(economie.benefice_net_cible_ht),
            'total_ht': str(economie.total_ht),
            'tva_collectee': str(economie.tva_collectee),
            'total_ttc': str(economie.total_ttc),
            'tva_nette_a_reverser': str(economie.tva_nette_a_reverser),
            'marge_pct': str(economie.marge_pct),
            'controle_tresorerie': str(economie.controle_tresorerie),
            'ecart_tresorerie': str(economie.ecart_tresorerie),
            'sous_seuil_psychologique': economie.sous_seuil_psychologique,
        })

    @action(detail=True, methods=['get', 'post'], url_path='telecharger')
    def telecharger(self, request, pk=None):
        """AOF161 — le classeur DIRECTEUR de rentabilité : JOB puis ARTEFACT.

        Le front appelait ``/ao/<id>/rentabilite/telecharger/``, une route que
        personne n'a jamais enregistrée. Le SERVICE, lui, existait des deux
        côtés sans être relié : le rendu ``fabrique.rendus.rentabilite_xlsx``
        et la tâche ``ao.produire_rentabilite_xlsx``. Cette action est le
        chaînon manquant — elle n'invente aucun calcul.

        * ``POST`` lance la production (``core.jobs.submit`` — jamais une file
          maison) et renvoie **202** avec l'identifiant du ``BackgroundJob`` ;
        * ``GET ?job=<id>`` renvoie l'état d'avancement (JSON) ;
        * ``GET ?job=<id>&fichier=1`` relaie les octets du classeur.

        JAMAIS de rendu synchrone dans la requête : un classeur qui parcourt
        tous les postes de coût n'a pas sa place dans le temps d'une requête
        HTTP, et le patron des exports lourds du dépôt est le job de fond.

        Le fichier est relayé PAR CETTE VUE (même origine, ``ao_rentabilite_
        voir`` revérifié à chaque octet par ``get_permissions``) et non par une
        URL présignée remise au navigateur : une clé d'objet partagée
        contournerait toute la permission — et l'hôte MinIO interne est de
        toute façon injoignable depuis un navigateur (leçon B1).
        """
        economie = self.get_object()  # scopé société par CompanyScopedModelViewSet
        if request.method == 'POST':
            return self._lancer_production(request, economie)
        return self._suivre_ou_servir(request, economie)

    def _lancer_production(self, request, economie):
        from core.jobs import submit

        from . import tasks

        try:
            job = submit(
                KIND_RENTABILITE_XLSX, tasks.produire_rentabilite_xlsx_task,
                company=economie.company, user=request.user,
                projet_id=economie.appel_offre_id)
        except Exception:  # noqa: BLE001 — broker injoignable : 503, pas 500.
            return Response(
                {'detail': "La file de traitement est injoignable : le "
                           "classeur n'a pas pu être lancé. Réessayez."},
                status=status.HTTP_503_SERVICE_UNAVAILABLE)
        return Response(
            {'job': job.pk, 'statut': job.statut,
             'progress_pct': job.progress_pct, 'message_erreur': '',
             'pret': False},
            status=status.HTTP_202_ACCEPTED)

    def _suivre_ou_servir(self, request, economie):
        from core.models import BackgroundJob

        job = self._job_demande(request, economie)
        pret = (job.statut == BackgroundJob.STATUT_DONE
                and bool(job.result_file_key))
        etat = {'job': job.pk, 'statut': job.statut,
                'progress_pct': job.progress_pct,
                'message_erreur': job.message_erreur, 'pret': pret}
        if request.query_params.get('fichier') in (None, '', '0', 'false'):
            return Response(etat)
        if not pret:
            etat['detail'] = ("Le classeur n'est pas encore prêt : suivez le "
                              'job avant de le télécharger.')
            return Response(etat, status=status.HTTP_202_ACCEPTED)
        return self._servir_classeur(job, economie)

    def _job_demande(self, request, economie):
        """Le job de production visé, ou 404 — jamais celui d'un autre.

        Le job est borné à la SOCIÉTÉ de l'économie, à l'utilisateur qui l'a
        lancé et au type de job : le classeur d'une autre société est
        introuvable, pas « interdit » (la réponse ne confirme pas son
        existence).
        """
        from core.models import BackgroundJob

        brut = request.query_params.get('job')
        try:
            job_id = int(brut)
        except (TypeError, ValueError):
            raise Http404(
                "Indiquez le job renvoyé par le POST sur cette même économie "
                '(paramètre « job »).')
        job = BackgroundJob.objects.filter(
            pk=job_id, company=economie.company, user=request.user,
            kind=KIND_RENTABILITE_XLSX).first()
        if job is None:
            raise Http404('Production de classeur introuvable.')
        return job

    def _servir_classeur(self, job, economie):
        """Relaie les octets — après avoir vérifié QUEL dossier ils décrivent.

        La clé de l'artefact porte l'appel d'offres produit (``…-ao<id>.xlsx``,
        posée par la tâche). Sans cette vérification, un id de job appartenant
        à un AUTRE dossier de la même société servirait le classeur de cet
        autre dossier sous le NOM de celui-ci : pas une fuite de permission
        (l'économie est company-wide pour un directeur), mais un fichier
        étiqueté faux — le pire des deux, parce qu'il ne se voit pas.
        """
        from apps.records.storage import fetch_attachment

        if not job.result_file_key.endswith(
                f'-ao{economie.appel_offre_id}.xlsx'):
            raise Http404("Ce job n'a pas produit le classeur de cet appel "
                          "d'offres.")
        octets, erreur = fetch_attachment(job.result_file_key)
        if erreur or not octets:
            return Response(
                {'detail': "Le classeur produit est introuvable dans le "
                           'stockage : relancez la production.'},
                status=status.HTTP_404_NOT_FOUND)
        reference = _NOM_SUR.sub('-', economie.appel_offre.reference or '')
        nom = f'rentabilite-{reference or economie.pk}.xlsx'
        reponse = HttpResponse(octets, content_type=MIME_XLSX)
        # PIÈCE INTERNE : téléchargement forcé, jamais un aperçu en ligne.
        reponse['Content-Disposition'] = f'attachment; filename="{nom}"'
        reponse['X-Content-Type-Options'] = 'nosniff'
        return reponse

    @action(detail=True, methods=['post'])
    def verrouiller(self, request, pk=None):
        economie = self.get_object()
        economie.verrouillee = True
        economie.save(update_fields=['verrouillee', 'updated_at'])
        return Response({'verrouillee': True})

    @action(detail=True, methods=['post'])
    def deverrouiller(self, request, pk=None):
        economie = self.get_object()
        economie.verrouillee = False
        economie.save(update_fields=['verrouillee', 'updated_at'])
        return Response({'verrouillee': False})


class LigneCoutRevientViewSet(_BaseDirecteurViewSet):
    """Postes du coût de revient (directeur seul)."""

    queryset = LigneCoutRevient.objects.all()
    serializer_class = LigneCoutRevientSerializer
    filter_backends = [filters.OrderingFilter]
    ordering_fields = ['ordre', 'poste']

    def get_queryset(self):
        qs = super().get_queryset()
        for champ in ('economie', 'poste', 'regime_tva'):
            valeur = self.request.query_params.get(champ)
            if valeur not in (None, ''):
                qs = qs.filter(**{champ: valeur})
        return qs

    def perform_create(self, serializer):
        self._refuser_si_verrouillee(
            serializer.validated_data.get('economie'))
        super().perform_create(serializer)

    def perform_update(self, serializer):
        self._refuser_si_verrouillee(serializer.instance.economie)
        super().perform_update(serializer)


class CibleFinanciereViewSet(_BaseDirecteurViewSet):
    """Cibles de bénéfice VERSIONNÉES (directeur seul).

    Une nouvelle cible incrémente la version, désactive la précédente et
    TRACE son auteur côté serveur : un mouvement de prix se justifie.
    """

    queryset = CibleFinanciere.objects.all()
    serializer_class = CibleFinanciereSerializer
    filter_backends = [filters.OrderingFilter]
    ordering_fields = ['version']

    def get_queryset(self):
        qs = super().get_queryset()
        economie = self.request.query_params.get('economie')
        if economie not in (None, ''):
            qs = qs.filter(economie=economie)
        return qs

    def create(self, request, *args, **kwargs):
        from . import services_directeur

        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        economie = serializer.validated_data['economie']
        if economie.company_id != request.user.company_id:
            raise PermissionDenied("Économie hors de votre société.")
        self._refuser_si_verrouillee(economie)
        cible = services_directeur.nouvelle_cible(
            economie,
            benefice_net_cible_ht=serializer.validated_data[
                'benefice_net_cible_ht'],
            motif=serializer.validated_data.get('motif', ''),
            arrondi_psychologique=serializer.validated_data.get(
                'arrondi_psychologique'),
            seuil_psychologique=serializer.validated_data.get(
                'seuil_psychologique'),
            ligne_ajustement=serializer.validated_data.get(
                'ligne_ajustement'),
            user=request.user)
        return Response(self.get_serializer(cible).data,
                        status=status.HTTP_201_CREATED)
