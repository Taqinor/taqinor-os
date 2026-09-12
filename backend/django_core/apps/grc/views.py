"""ViewSets du module GRC & Conformité (NTGRC).

Tout viewset hérite de ``core.viewsets.CompanyScopedModelViewSet`` (ARC2) :
queryset filtré sur ``request.user.company`` et ``company`` imposée côté
serveur dans ``perform_create``/``perform_update``, jamais lue du corps.
"""
from rest_framework.decorators import action
from rest_framework.response import Response

from authentication.permissions import IsAdminOrResponsableTier
from core.viewsets import CompanyScopedModelViewSet

from .models import (
    ControleInterne, JournalDestruction, LegalHold, PlanTraitementRisque,
    PolitiqueRetentionObjet, RevueRisque, RisqueEntreprise, TestControle,
    ViolationDonnees,
)
from .serializers import (
    ControleInterneSerializer, JournalDestructionSerializer,
    LegalHoldSerializer, PlanTraitementRisqueSerializer,
    PolitiqueRetentionObjetSerializer, RevueRisqueSerializer,
    RisqueEntrepriseSerializer, TestControleSerializer,
    ViolationDonneesSerializer,
)


class PolitiqueRetentionObjetViewSet(CompanyScopedModelViewSet):
    """NTGRC4 — CRUD des politiques de rétention par type d'objet.

    Donnée de CONFORMITÉ : réservée au palier admin/responsable, comme les
    registres RGPD de ``core`` (consentement, DSR, traitements CNDP). Pas de
    nouveau code de permission inventé — la même classe que ces registres.
    """

    queryset = PolitiqueRetentionObjet.objects.all()
    serializer_class = PolitiqueRetentionObjetSerializer
    permission_classes = [IsAdminOrResponsableTier]


class JournalDestructionViewSet(CompanyScopedModelViewSet):
    """NTGRC5 — journal APPEND-ONLY des destructions/anonymisations.

    ``http_method_names`` n'expose QUE la lecture et la création : aucune
    route d'update ni de delete n'existe. La garde d'immuabilité vit aussi au
    niveau du modèle, pour qu'aucun autre chemin de code ne puisse réécrire
    une ligne.

    Filtres : ``?type_objet=`` et ``?depuis=`` / ``?jusqu_a=`` (dates ISO).
    """

    queryset = JournalDestruction.objects.all()
    serializer_class = JournalDestructionSerializer
    permission_classes = [IsAdminOrResponsableTier]
    http_method_names = ['get', 'post', 'head', 'options']

    def get_queryset(self):
        qs = super().get_queryset()
        params = self.request.query_params
        type_objet = (params.get('type_objet') or '').strip()
        if type_objet:
            qs = qs.filter(type_objet=type_objet)
        depuis = (params.get('depuis') or '').strip()
        if depuis:
            qs = qs.filter(created_at__date__gte=depuis)
        jusqu_a = (params.get('jusqu_a') or '').strip()
        if jusqu_a:
            qs = qs.filter(created_at__date__lte=jusqu_a)
        return qs

    def perform_create(self, serializer):
        """``company`` ET l'acteur sont posés CÔTÉ SERVEUR, jamais lus du corps."""
        serializer.save(
            company=self.request.user.company,
            executee_par=getattr(self.request.user, 'username', '') or '')


class ViolationDonneesViewSet(CompanyScopedModelViewSet):
    """NTGRC6 — registre des violations de données + délai légal de 72 h.

    Le statut et la date de notification CNDP ne s'écrivent pas au champ :
    ils bougent ENSEMBLE par les actions dédiées, sous garde de transition.
    """

    queryset = ViolationDonnees.objects.all()
    serializer_class = ViolationDonneesSerializer
    permission_classes = [IsAdminOrResponsableTier]

    def perform_create(self, serializer):
        """Référence VD race-safe + société imposée côté serveur."""
        from .services import creer_violation

        champs = dict(serializer.validated_data)
        champs.pop('company', None)
        champs.pop('reference', None)
        serializer.instance = creer_violation(
            self.request.user.company, **champs)

    @action(detail=False, methods=['get'], url_path='echeance-depassee')
    def echeance_depassee(self, request):
        """Violations dont le délai de 72 h est dépassé sans notification."""
        from .selectors import violations_echeance_72h_depassee

        qs = violations_echeance_72h_depassee(request.user.company)
        return Response({'results': self.get_serializer(qs, many=True).data})

    @action(detail=True, methods=['post'], url_path='changer-statut')
    def changer_statut(self, request, pk=None):
        """Fait avancer la violation (``{"statut": "en_analyse"}``)."""
        from .services import (
            TransitionViolationInterdite, changer_statut_violation,
        )

        violation = self.get_object()
        cible = (request.data.get('statut') or '').strip()
        try:
            changer_statut_violation(violation, cible)
        except TransitionViolationInterdite as exc:
            return Response({'statut': str(exc)}, status=400)
        return Response(self.get_serializer(violation).data)

    @action(detail=True, methods=['get', 'post'],
            url_path='generer-dossier-notification')
    def generer_dossier_notification(self, request, pk=None):
        """NTGRC7 — rend le dossier de notification CNDP en PDF.

        Le PDF liste les 8 rubriques réglementaires + l'horodatage de
        génération. Rendu par ``core.pdf`` (ARC11) — jamais le moteur de devis
        (règle #4). L'événement est journalisé en ``audit.AuditLog`` via le bus
        ``core.events`` (aucun import de l'app audit depuis grc).
        """
        from django.http import HttpResponse

        from core.events import document_pdf_generated

        from .services import generer_dossier_notification as _generer

        violation = self.get_object()
        try:
            pdf, contexte = _generer(violation)
        except RuntimeError as exc:
            # WeasyPrint absent (build allégé) : message honnête, jamais 500.
            return Response({'detail': str(exc)}, status=503)

        document_pdf_generated.send(
            sender=self.__class__, instance=violation,
            kind='violation_donnees')

        reponse = HttpResponse(pdf, content_type='application/pdf')
        nom = (contexte['reference'] or 'violation').replace('/', '-')
        reponse['Content-Disposition'] = (
            f'attachment; filename="notification-cndp-{nom}.pdf"')
        return reponse

    @action(detail=True, methods=['post'], url_path='notifier-cndp')
    def notifier_cndp(self, request, pk=None):
        """Enregistre la notification CNDP (date + statut, ensemble)."""
        from .services import TransitionViolationInterdite
        from .services import notifier_cndp as _notifier

        violation = self.get_object()
        try:
            _notifier(violation)
        except TransitionViolationInterdite as exc:
            return Response({'statut': str(exc)}, status=400)
        return Response(self.get_serializer(violation).data)


class LegalHoldViewSet(CompanyScopedModelViewSet):
    """NTGRC8 — mises sous séquestre transverses (legal hold).

    Un séquestre ne se supprime pas : on le LÈVE (l'historique d'un gel est
    lui-même une pièce du dossier). ``statut`` bouge donc par l'action
    ``lever/``, jamais par une écriture de champ.
    """

    queryset = LegalHold.objects.all()
    serializer_class = LegalHoldSerializer
    permission_classes = [IsAdminOrResponsableTier]
    http_method_names = ['get', 'post', 'put', 'patch', 'head', 'options']

    @action(detail=True, methods=['post'])
    def lever(self, request, pk=None):
        """Lève le séquestre (les objets redeviennent purgeables)."""
        hold = self.get_object()
        if hold.statut == LegalHold.STATUT_LEVE:
            return Response(
                {'statut': 'Ce séquestre est déjà levé.'}, status=400)
        hold.statut = LegalHold.STATUT_LEVE
        hold.save(update_fields=['statut', 'updated_at'])
        return Response(self.get_serializer(hold).data)

    @action(detail=False, methods=['get'], url_path='objets-sous-hold')
    def objets_sous_hold(self, request):
        """Objets actuellement gelés, par type (GED comprise)."""
        from .selectors import objets_sous_hold as _couverture

        couverture = _couverture(request.user.company)
        return Response({
            type_objet: sorted(ids)
            for type_objet, ids in sorted(couverture.items())
        })


class RisqueEntrepriseViewSet(CompanyScopedModelViewSet):
    """NTGRC13 — registre des risques d'entreprise (ERM) + matrice 5×5."""

    queryset = RisqueEntreprise.objects.all()
    serializer_class = RisqueEntrepriseSerializer
    permission_classes = [IsAdminOrResponsableTier]

    def perform_create(self, serializer):
        """Référence RQ race-safe + société imposée côté serveur."""
        from .services import creer_risque

        champs = dict(serializer.validated_data)
        champs.pop('company', None)
        champs.pop('reference', None)
        serializer.instance = creer_risque(self.request.user.company, **champs)

    @action(detail=False, methods=['get'])
    def matrice(self, request):
        """Grille 5×5 comptée par case (``?residuelle=1`` pour l'après-
        traitement). Les 25 cases sont toujours présentes."""
        from .selectors import matrice_risques

        residuelle = (request.query_params.get('residuelle') or '').strip() in (
            '1', 'true', 'True', 'oui')
        return Response(matrice_risques(request.user.company,
                                        residuelle=residuelle))


class PlanTraitementRisqueViewSet(CompanyScopedModelViewSet):
    """NTGRC14 — plans de traitement du risque + suivi des retards."""

    queryset = PlanTraitementRisque.objects.select_related('risque').all()
    serializer_class = PlanTraitementRisqueSerializer
    permission_classes = [IsAdminOrResponsableTier]

    @action(detail=False, methods=['get'], url_path='en-retard')
    def en_retard(self, request):
        """Plans dont l'échéance est passée et qui ne sont pas faits."""
        from .selectors import plans_en_retard

        qs = plans_en_retard(request.user.company)
        return Response({'results': self.get_serializer(qs, many=True).data})


class RevueRisqueViewSet(CompanyScopedModelViewSet):
    """NTGRC15 — revues périodiques du risque (journal + cadence).

    Créer une revue AVANCE la prochaine date de revue sur le risque, via le
    service : la cadence vit à un seul endroit.
    """

    queryset = RevueRisque.objects.select_related('risque').all()
    serializer_class = RevueRisqueSerializer
    permission_classes = [IsAdminOrResponsableTier]
    # Une revue est une ligne de JOURNAL : on en ajoute une, on ne réécrit pas
    # l'histoire d'une revue déjà tenue.
    http_method_names = ['get', 'post', 'head', 'options']

    def perform_create(self, serializer):
        from .services import enregistrer_revue

        champs = dict(serializer.validated_data)
        champs.pop('company', None)
        risque = champs.pop('risque')
        serializer.instance = enregistrer_revue(
            self.request.user.company, risque, **champs)

    @action(detail=False, methods=['get'], url_path='risques-a-revoir')
    def risques_a_revoir(self, request):
        """Risques dont la revue est due (``?within=<jours>``)."""
        from .selectors import risques_a_revoir as _dus

        try:
            within = int(request.query_params.get('within') or 0)
        except (TypeError, ValueError):
            within = 0
        qs = _dus(request.user.company, within=within)
        return Response({
            'results': RisqueEntrepriseSerializer(qs, many=True).data})


class ControleInterneViewSet(CompanyScopedModelViewSet):
    """NTGRC16 — bibliothèque des contrôles internes (SOX-lite)."""

    queryset = ControleInterne.objects.all()
    serializer_class = ControleInterneSerializer
    permission_classes = [IsAdminOrResponsableTier]

    def get_queryset(self):
        qs = super().get_queryset()
        domaine = (self.request.query_params.get('domaine') or '').strip()
        if domaine:
            qs = qs.filter(domaine=domaine)
        actif = (self.request.query_params.get('actif') or '').strip()
        if actif in ('1', 'true', 'True', 'oui'):
            qs = qs.filter(actif=True)
        elif actif in ('0', 'false', 'False', 'non'):
            qs = qs.filter(actif=False)
        return qs


class TestControleViewSet(CompanyScopedModelViewSet):
    """NTGRC17 — tests de contrôle planifiés + preuves.

    Un test qui conclut « déficient » ouvre AUTOMATIQUEMENT un risque lié, via
    le service (idempotent).
    """

    queryset = TestControle.objects.select_related('controle').all()
    serializer_class = TestControleSerializer
    permission_classes = [IsAdminOrResponsableTier]

    def perform_create(self, serializer):
        from .services import enregistrer_test_controle

        champs = dict(serializer.validated_data)
        champs.pop('company', None)
        controle = champs.pop('controle')
        serializer.instance = enregistrer_test_controle(
            self.request.user.company, controle, **champs)

    def perform_update(self, serializer):
        """Un test requalifié « déficient » ouvre aussi son risque."""
        from .services import ouvrir_risque_sur_deficience

        test = serializer.save(company=self.request.user.company)
        ouvrir_risque_sur_deficience(test)

    @action(detail=False, methods=['get'], url_path='controles-a-tester')
    def controles_a_tester(self, request):
        """Contrôles actifs dont le test est dû (``?within=<jours>``)."""
        from .selectors import controles_a_tester as _dus

        try:
            within = int(request.query_params.get('within') or 0)
        except (TypeError, ValueError):
            within = 0
        dus = _dus(request.user.company, within=within)
        return Response({'results': [
            {
                'controle': ControleInterneSerializer(d['controle']).data,
                'echeance': (d['echeance'].isoformat()
                             if d['echeance'] else None),
                'jamais_teste': d['dernier_test'] is None,
            }
            for d in dus
        ]})
