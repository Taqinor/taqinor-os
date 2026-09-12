"""ViewSets du module GRC & Conformité (NTGRC).

Tout viewset hérite de ``core.viewsets.CompanyScopedModelViewSet`` (ARC2) :
queryset filtré sur ``request.user.company`` et ``company`` imposée côté
serveur dans ``perform_create``/``perform_update``, jamais lue du corps.
"""
from drf_spectacular.utils import extend_schema, inline_serializer
from rest_framework import serializers
from rest_framework.decorators import (
    action, api_view, permission_classes,
)
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from apps.records.views import ChatterViewSetMixin
from authentication.permissions import IsAdminOrResponsableTier
from core.viewsets import CompanyScopedModelViewSet

from .models import (
    AnalyseImpactDPIA, AttestationPolitique, CadreConformite, ControleInterne,
    DeficienceControle, ExigenceCadre, FluxDonnees,
    IncidentSecurite, JournalDestruction, LegalHold,
    ModeleQuestionnaire, PlanTraitementRisque,
    PolitiqueInterne, PolitiqueRetentionObjet,
    QuestionnaireFournisseur, ReponseQuestionnaire, RevueRisque,
    RisqueEntreprise, SousTraitantRGPD, TestControle, ViolationDonnees,
)
from .serializers import (
    AnalyseImpactDPIASerializer,
    AttestationPolitiqueSerializer, CadreConformiteSerializer,
    ControleInterneSerializer,
    DeficienceControleSerializer, ExigenceCadreSerializer,
    FluxDonneesSerializer,
    IncidentSecuriteSerializer,
    JournalDestructionSerializer, LegalHoldSerializer,
    ModeleQuestionnaireSerializer, PlanTraitementRisqueSerializer,
    PolitiqueInterneSerializer, PolitiqueRetentionObjetSerializer,
    PolitiqueVersionSerializer, QuestionnaireFournisseurSerializer,
    ReponseQuestionnaireSerializer, RevueRisqueSerializer,
    RisqueEntrepriseSerializer, SousTraitantRGPDSerializer,
    TestControleSerializer,
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

    @action(detail=False, methods=['get'], url_path='echeance-depassee',
            permission_classes=[IsAdminOrResponsableTier])
    def echeance_depassee(self, request):
        """Violations dont le délai de 72 h est dépassé sans notification."""
        from .selectors import violations_echeance_72h_depassee

        qs = violations_echeance_72h_depassee(request.user.company)
        return Response({'results': self.get_serializer(qs, many=True).data})

    @action(detail=True, methods=['post'], url_path='changer-statut',
            permission_classes=[IsAdminOrResponsableTier])
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
            url_path='generer-dossier-notification',
            permission_classes=[IsAdminOrResponsableTier])
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

    @action(detail=True, methods=['post'], url_path='notifier-cndp',
            permission_classes=[IsAdminOrResponsableTier])
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

    @action(detail=True, methods=['post'],
            permission_classes=[IsAdminOrResponsableTier])
    def lever(self, request, pk=None):
        """Lève le séquestre (les objets redeviennent purgeables)."""
        hold = self.get_object()
        if hold.statut == LegalHold.STATUT_LEVE:
            return Response(
                {'statut': 'Ce séquestre est déjà levé.'}, status=400)
        hold.statut = LegalHold.STATUT_LEVE
        hold.save(update_fields=['statut', 'updated_at'])
        return Response(self.get_serializer(hold).data)

    @action(detail=False, methods=['get'], url_path='objets-sous-hold',
            permission_classes=[IsAdminOrResponsableTier])
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

    @action(detail=False, methods=['get'],
            permission_classes=[IsAdminOrResponsableTier])
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

    @action(detail=False, methods=['get'], url_path='en-retard',
            permission_classes=[IsAdminOrResponsableTier])
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

    @action(detail=False, methods=['get'], url_path='risques-a-revoir',
            permission_classes=[IsAdminOrResponsableTier])
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

    @action(detail=False, methods=['get'], url_path='controles-a-tester',
            permission_classes=[IsAdminOrResponsableTier])
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


class DeficienceControleViewSet(CompanyScopedModelViewSet):
    """NTGRC18 — constats de déficience + liens risque / CAPA QHSE."""

    queryset = DeficienceControle.objects.select_related(
        'test_controle').all()
    serializer_class = DeficienceControleSerializer
    permission_classes = [IsAdminOrResponsableTier]

    def get_queryset(self):
        qs = super().get_queryset()
        gravite = (self.request.query_params.get('gravite') or '').strip()
        if gravite:
            qs = qs.filter(gravite=gravite)
        statut = (self.request.query_params.get('statut') or '').strip()
        if statut:
            qs = qs.filter(statut=statut)
        return qs


class PolitiqueInterneViewSet(CompanyScopedModelViewSet):
    """NTGRC19 — référentiel des politiques internes versionnées."""

    queryset = PolitiqueInterne.objects.prefetch_related('versions').all()
    serializer_class = PolitiqueInterneSerializer
    permission_classes = [IsAdminOrResponsableTier]

    @action(detail=True, methods=['post'],
            permission_classes=[IsAdminOrResponsableTier])
    def publier(self, request, pk=None):
        """Fige le contenu dans une version immuable et incrémente le n°."""
        from .services import PublicationImpossible, publier_politique

        politique = self.get_object()
        try:
            version = publier_politique(
                politique,
                auteur=getattr(request.user, 'username', '') or '')
        except PublicationImpossible as exc:
            return Response({'contenu': str(exc)}, status=400)
        return Response({
            'politique': self.get_serializer(politique).data,
            'version': PolitiqueVersionSerializer(version).data,
        })

    @action(detail=True, methods=['get'],
            permission_classes=[IsAdminOrResponsableTier])
    def versions(self, request, pk=None):
        """Historique IMMUABLE des versions publiées (plus récente d'abord)."""
        politique = self.get_object()
        return Response({'results': PolitiqueVersionSerializer(
            politique.versions.all(), many=True).data})

    @action(detail=True, methods=['get'], url_path='taux-attestation')
    def taux_attestation(self, request, pk=None):
        """NTGRC20 — taux d'attestation de la version publiée en cours."""
        from .selectors import taux_attestation as _taux

        politique = self.get_object()
        return Response(_taux(request.user.company, politique))


class AttestationPolitiqueViewSet(CompanyScopedModelViewSet):
    """NTGRC20 — registre des attestations de lecture des politiques.

    Journal : on AJOUTE une attestation, on ne réécrit jamais celle de
    quelqu'un d'autre (ni PUT, ni PATCH, ni DELETE). Le registre se consulte
    au palier admin/responsable comme les autres registres de conformité,
    MAIS l'action ``attester/`` est ouverte à tout utilisateur authentifié :
    c'est l'employé lui-même qui atteste, pas son responsable à sa place.
    """

    queryset = AttestationPolitique.objects.select_related('politique').all()
    serializer_class = AttestationPolitiqueSerializer
    permission_classes = [IsAdminOrResponsableTier]
    http_method_names = ['get', 'post', 'head', 'options']

    def get_queryset(self):
        qs = super().get_queryset()
        politique = (self.request.query_params.get('politique') or '').strip()
        if politique.isdigit():
            qs = qs.filter(politique_id=int(politique))
        employe = (self.request.query_params.get('employe_ref') or '').strip()
        if employe:
            qs = qs.filter(employe_ref=employe)
        return qs

    def perform_create(self, serializer):
        """Saisie pour un tiers (attestation papier) — preuve côté serveur."""
        from .services import AttestationImpossible, attester_politique

        donnees = dict(serializer.validated_data)
        donnees.pop('company', None)
        politique = donnees.pop('politique')
        try:
            attestation, _ = attester_politique(
                self.request.user.company, politique,
                employe_ref=donnees.get('employe_ref', ''),
                nom_saisi=donnees.get('nom_saisi', ''),
                attestant_nom=donnees.get('attestant_nom', ''),
                preuve=self._preuve())
        except AttestationImpossible as exc:
            from rest_framework.exceptions import ValidationError

            raise ValidationError({exc.champ: str(exc)})
        serializer.instance = attestation

    def _preuve(self):
        from .services import preuve_requete

        return preuve_requete(self.request)

    @action(detail=False, methods=['post'],
            permission_classes=[IsAuthenticated])
    def attester(self, request):
        """Attestation par l'utilisateur CONNECTÉ (``{politique, nom_saisi}``).

        Le dossier employé est résolu SERVEUR depuis le compte appelant (via
        ``rh.selectors``) : personne n'atteste au nom d'un autre par ce
        chemin. Ré-attester la même version renvoie 200 et la ligne existante
        — idempotent, un double clic ne crée pas deux preuves.
        """
        from apps.rh.selectors import dossier_employe_for_user

        from .services import AttestationImpossible, attester_politique

        company = request.user.company
        brut = (request.data.get('politique')
                if request.data else None)
        try:
            politique_id = int(brut)
        except (TypeError, ValueError):
            return Response(
                {'politique': 'Indiquez la politique à attester.'}, status=400)
        politique = PolitiqueInterne.objects.filter(
            company=company, pk=politique_id).first()
        if politique is None:
            return Response(
                {'politique': "Cette politique n'existe pas pour votre "
                              'société.'}, status=404)

        dossier = dossier_employe_for_user(company, request.user.pk)
        nom = (getattr(request.user, 'get_full_name', lambda: '')()
               or getattr(request.user, 'username', '') or '')
        try:
            attestation, creee = attester_politique(
                company, politique,
                employe_ref=str(dossier.pk) if dossier is not None else '',
                nom_saisi=(request.data.get('nom_saisi') or ''),
                attestant_nom=nom,
                preuve=self._preuve())
        except AttestationImpossible as exc:
            return Response({exc.champ: str(exc)}, status=400)
        return Response(self.get_serializer(attestation).data,
                        status=201 if creee else 200)


class QuestionnaireFournisseurViewSet(CompanyScopedModelViewSet):
    """NTGRC22 — questionnaires de conformité adressés aux fournisseurs."""

    queryset = QuestionnaireFournisseur.objects.prefetch_related(
        'reponses').all()
    serializer_class = QuestionnaireFournisseurSerializer
    permission_classes = [IsAdminOrResponsableTier]

    def get_queryset(self):
        qs = super().get_queryset()
        params = self.request.query_params
        statut = (params.get('statut') or '').strip()
        if statut:
            qs = qs.filter(statut=statut)
        type_q = (params.get('type') or '').strip()
        if type_q:
            qs = qs.filter(type=type_q)
        fournisseur = (params.get('fournisseur_ref') or '').strip()
        if fournisseur:
            qs = qs.filter(fournisseur_ref=fournisseur)
        return qs

    @action(detail=True, methods=['get'])
    def reponses(self, request, pk=None):
        """Les questions/réponses du questionnaire, dans leur ordre."""
        questionnaire = self.get_object()
        return Response({'results': ReponseQuestionnaireSerializer(
            questionnaire.reponses.all(), many=True).data})

    @action(detail=True, methods=['post'], url_path='lien-public')
    def lien_public(self, request, pk=None):
        """NTGRC24 — émet (ou renouvelle) le lien public du fournisseur.

        Renouveler INVALIDE l'ancien lien — c'est voulu : on « relance » un
        fournisseur quand son contact a changé, l'ancien destinataire ne doit
        plus pouvoir répondre.
        """
        from .services import (
            DELAI_LIEN_QUESTIONNAIRE_JOURS, emettre_lien_questionnaire,
        )

        questionnaire = self.get_object()
        try:
            jours = int(request.data.get('jours')
                        or DELAI_LIEN_QUESTIONNAIRE_JOURS)
        except (TypeError, ValueError):
            return Response(
                {'jours': 'Indiquez un nombre de jours valide.'}, status=400)
        emettre_lien_questionnaire(questionnaire, jours=jours)
        return Response({
            'token': questionnaire.token_acces,
            'url': f'/api/django/grc/public/questionnaire/'
                   f'{questionnaire.token_acces}/',
            'expire_le': questionnaire.token_expire_le.isoformat(),
        })

    @action(detail=True, methods=['post'], url_path='changer-statut')
    def changer_statut(self, request, pk=None):
        """Fait avancer le questionnaire (``{"statut": "valide"}``)."""
        from .services import (
            TransitionQuestionnaireInterdite, changer_statut_questionnaire,
        )

        questionnaire = self.get_object()
        cible = (request.data.get('statut') or '').strip()
        try:
            changer_statut_questionnaire(questionnaire, cible)
        except TransitionQuestionnaireInterdite as exc:
            return Response({'statut': str(exc)}, status=400)
        return Response(self.get_serializer(questionnaire).data)


class ReponseQuestionnaireViewSet(CompanyScopedModelViewSet):
    """NTGRC22 — réponses d'un questionnaire fournisseur.

    Chaque écriture RECALCULE le questionnaire porteur (score + passage
    automatique à « complété ») : le score ne peut pas diverger de ses
    réponses, parce que personne ne l'écrit à la main.
    """

    queryset = ReponseQuestionnaire.objects.select_related(
        'questionnaire').all()
    serializer_class = ReponseQuestionnaireSerializer
    permission_classes = [IsAdminOrResponsableTier]

    def get_queryset(self):
        qs = super().get_queryset()
        questionnaire = (
            self.request.query_params.get('questionnaire') or '').strip()
        if questionnaire.isdigit():
            qs = qs.filter(questionnaire_id=int(questionnaire))
        return qs

    def _recalculer(self, reponse):
        from .services import recalculer_questionnaire

        if reponse is not None and reponse.questionnaire_id:
            recalculer_questionnaire(reponse.questionnaire)

    def perform_create(self, serializer):
        super().perform_create(serializer)
        self._recalculer(serializer.instance)

    def perform_update(self, serializer):
        super().perform_update(serializer)
        self._recalculer(serializer.instance)

    def perform_destroy(self, instance):
        questionnaire = instance.questionnaire
        super().perform_destroy(instance)
        from .services import recalculer_questionnaire

        recalculer_questionnaire(questionnaire)


class ModeleQuestionnaireViewSet(CompanyScopedModelViewSet):
    """NTGRC23 — trames réutilisables de questionnaire fournisseur."""

    queryset = ModeleQuestionnaire.objects.all()
    serializer_class = ModeleQuestionnaireSerializer
    permission_classes = [IsAdminOrResponsableTier]

    def get_queryset(self):
        qs = super().get_queryset()
        type_m = (self.request.query_params.get('type') or '').strip()
        if type_m:
            qs = qs.filter(type=type_m)
        actif = (self.request.query_params.get('actif') or '').strip()
        if actif in ('1', 'true', 'True', 'oui'):
            qs = qs.filter(actif=True)
        elif actif in ('0', 'false', 'False', 'non'):
            qs = qs.filter(actif=False)
        return qs

    @action(detail=True, methods=['post'])
    def instancier(self, request, pk=None):
        """Crée un questionnaire prérempli depuis ce modèle.

        Corps : ``fournisseur_ref`` (id du ``stock.Fournisseur``, facultatif),
        ``date_echeance`` (ISO, facultative), ``evaluateur``.
        """
        from .services import instancier_questionnaire

        modele = self.get_object()
        donnees = request.data or {}
        fournisseur_ref = str(donnees.get('fournisseur_ref') or '').strip()
        if fournisseur_ref:
            from apps.stock.selectors import get_fournisseur_by_id

            try:
                fournisseur_id = int(fournisseur_ref)
            except (TypeError, ValueError):
                return Response(
                    {'fournisseur_ref': 'La référence fournisseur doit être '
                                        'un identifiant numérique.'},
                    status=400)
            if get_fournisseur_by_id(
                    request.user.company, fournisseur_id) is None:
                return Response(
                    {'fournisseur_ref': "Ce fournisseur n'existe pas pour "
                                        'votre société.'}, status=400)

        questionnaire = instancier_questionnaire(
            modele, fournisseur_ref,
            date_echeance=donnees.get('date_echeance') or None,
            evaluateur=donnees.get('evaluateur') or '')
        return Response(
            QuestionnaireFournisseurSerializer(
                questionnaire, context=self.get_serializer_context()).data,
            status=201)


class IncidentSecuriteViewSet(ChatterViewSetMixin, CompanyScopedModelViewSet):
    """NTGRC25/NTGRC26 — incidents de sécurité, escalade et chronologie.

    ``ChatterViewSetMixin`` (ARC8) branche le chatter PLATEFORME sur les URL
    génériques ``chatter/historique`` et ``chatter/noter`` ; les actions
    ``historique``/``noter`` de NTGRC26 exposent la MÊME donnée sous les noms
    attendus par l'écran GRC. Une seule source (``records.Activity``), deux
    chemins — jamais deux journaux qui divergent.
    """

    queryset = IncidentSecurite.objects.all()
    serializer_class = IncidentSecuriteSerializer
    permission_classes = [IsAdminOrResponsableTier]

    def get_queryset(self):
        qs = super().get_queryset()
        params = self.request.query_params
        statut = (params.get('statut') or '').strip()
        if statut:
            qs = qs.filter(statut=statut)
        severite = (params.get('severite') or '').strip()
        if severite:
            qs = qs.filter(severite=severite)
        type_i = (params.get('type') or '').strip()
        if type_i:
            qs = qs.filter(type=type_i)
        return qs

    def perform_create(self, serializer):
        """Référence INC race-safe + société imposée côté serveur."""
        from .services import creer_incident

        champs = dict(serializer.validated_data)
        champs.pop('company', None)
        champs.pop('reference', None)
        serializer.instance = creer_incident(
            self.request.user.company, **champs)

    @action(detail=True, methods=['post'], url_path='changer-statut')
    def changer_statut(self, request, pk=None):
        """Fait avancer l'incident (``{"statut": "en_cours"}``)."""
        from .services import (
            TransitionIncidentInterdite, changer_statut_incident,
        )

        incident = self.get_object()
        cible = (request.data.get('statut') or '').strip()
        try:
            changer_statut_incident(incident, cible, user=request.user)
        except TransitionIncidentInterdite as exc:
            return Response({'statut': str(exc)}, status=400)
        return Response(self.get_serializer(incident).data)

    @action(detail=True, methods=['post'], url_path='escalader-violation')
    def escalader_violation(self, request, pk=None):
        """Crée la violation de données correspondant à cet incident.

        À n'utiliser QUE si des données personnelles sont effectivement
        touchées : c'est cette création qui démarre l'horloge légale de 72 h.
        """
        from .services import (
            EscaladeImpossible, escalader_incident_en_violation,
        )

        incident = self.get_object()
        donnees = request.data or {}
        champs = {}
        for cle in ('nature', 'categories_donnees',
                    'nombre_personnes_estime', 'risque_personnes',
                    'mesures_prises', 'notification_cndp_requise'):
            if cle in donnees and donnees.get(cle) not in (None, ''):
                champs[cle] = donnees[cle]
        try:
            violation = escalader_incident_en_violation(incident, **champs)
        except EscaladeImpossible as exc:
            return Response({'violation_donnees_ref': str(exc)}, status=409)
        return Response({
            'incident': self.get_serializer(incident).data,
            'violation': ViolationDonneesSerializer(violation).data,
        }, status=201)

    @action(detail=True, methods=['get'])
    def historique(self, request, pk=None):
        """NTGRC26 — chronologie de l'incident (plus récent d'abord).

        Lit le chatter PLATEFORME (``records.Activity``, ARC8) et le rend
        dans l'enveloppe uniforme que le frontend consomme déjà pour toutes
        les autres timelines du produit. ``chatter/historique/`` (fourni par
        ``ChatterViewSetMixin``) sert la même donnée sous l'URL générique —
        deux chemins, UNE source.
        """
        from apps.records.serializers import ChatterActivitySerializer

        from .services import chronologie_incident

        incident = self.get_object()
        return Response({'results': ChatterActivitySerializer(
            chronologie_incident(incident), many=True).data})

    @action(detail=True, methods=['post'])
    def noter(self, request, pk=None):
        """NTGRC26 — ajoute une note manuelle (``{"detail": "..."}``).

        L'auteur et la société sont posés CÔTÉ SERVEUR.
        """
        from apps.records.serializers import ChatterActivitySerializer

        from .services import noter_incident

        incident = self.get_object()
        try:
            activite = noter_incident(
                incident, request.data.get('detail'), user=request.user)
        except ValueError:
            return Response(
                {'detail': 'Écrivez la note avant de l\'enregistrer.'},
                status=400)
        return Response(ChatterActivitySerializer(activite).data, status=201)


class AnalyseImpactDPIAViewSet(CompanyScopedModelViewSet):
    """NTGRC27 — analyses d'impact (AIPD) des traitements à haut risque."""

    queryset = AnalyseImpactDPIA.objects.all()
    serializer_class = AnalyseImpactDPIASerializer
    permission_classes = [IsAdminOrResponsableTier]

    def get_queryset(self):
        qs = super().get_queryset()
        params = self.request.query_params
        statut = (params.get('statut') or '').strip()
        if statut:
            qs = qs.filter(statut=statut)
        traitement = (params.get('traitement_ref') or '').strip()
        if traitement:
            qs = qs.filter(traitement_ref=traitement)
        return qs

    @action(detail=True, methods=['post'])
    def valider(self, request, pk=None):
        """Valide l'analyse (statut + date de validation, ensemble)."""
        from .services import ValidationDPIAImpossible, valider_dpia

        analyse = self.get_object()
        try:
            valider_dpia(analyse)
        except ValidationDPIAImpossible as exc:
            return Response({exc.champ: str(exc)}, status=400)
        return Response(self.get_serializer(analyse).data)

    @action(detail=True, methods=['post'], url_path='demander-revision')
    def demander_revision(self, request, pk=None):
        """Repasse l'analyse en « à réviser » (le traitement a changé)."""
        from .services import demander_revision_dpia

        analyse = self.get_object()
        demander_revision_dpia(analyse)
        return Response(self.get_serializer(analyse).data)

    @action(detail=False, methods=['get'], url_path='traitements-sans-dpia')
    def traitements_sans_dpia(self, request):
        """Traitements à HAUT RISQUE sans AIPD validée (le trou à combler)."""
        from .selectors import traitements_dpia_manquante

        manquants = traitements_dpia_manquante(request.user.company)
        return Response({'results': [
            {
                'traitement_ref': str(entree['traitement'].pk),
                'code': entree['traitement'].code,
                'finalite': entree['traitement'].finalite,
                'analyse': (self.get_serializer(entree['analyse']).data
                            if entree['analyse'] is not None else None),
            }
            for entree in manquants
        ]})


class SousTraitantRGPDViewSet(CompanyScopedModelViewSet):
    """NTGRC35 — sous-traitants au sens de l'art. 28 RGPD / loi 09-08."""

    queryset = SousTraitantRGPD.objects.all()
    serializer_class = SousTraitantRGPDSerializer
    permission_classes = [IsAdminOrResponsableTier]

    def get_queryset(self):
        qs = super().get_queryset()
        params = self.request.query_params
        risque = (params.get('niveau_risque') or '').strip()
        if risque:
            qs = qs.filter(niveau_risque=risque)
        clause = (params.get('clause_signee') or '').strip()
        if clause in ('1', 'true', 'True', 'oui'):
            qs = qs.filter(clause_signee=True)
        elif clause in ('0', 'false', 'False', 'non'):
            qs = qs.filter(clause_signee=False)
        return qs

    @action(detail=False, methods=['get'], url_path='sans-clause')
    def sans_clause(self, request):
        """Sous-traitants sans clause signée — les plus risqués d'abord."""
        from .selectors import sous_traitants_sans_clause

        qs = sous_traitants_sans_clause(request.user.company)
        return Response({'results': self.get_serializer(qs, many=True).data})


class CadreConformiteViewSet(CompanyScopedModelViewSet):
    """NTGRC33 — cadres de conformité suivis + taux de couverture."""

    queryset = CadreConformite.objects.all()
    serializer_class = CadreConformiteSerializer
    permission_classes = [IsAdminOrResponsableTier]

    def get_queryset(self):
        qs = super().get_queryset()
        actif = (self.request.query_params.get('actif') or '').strip()
        if actif in ('1', 'true', 'True', 'oui'):
            qs = qs.filter(actif=True)
        elif actif in ('0', 'false', 'False', 'non'):
            qs = qs.filter(actif=False)
        return qs

    @action(detail=True, methods=['get'])
    def couverture(self, request, pk=None):
        """Taux de couverture du cadre (couvertes / total) + détail."""
        from .selectors import taux_couverture

        cadre = self.get_object()
        return Response(taux_couverture(request.user.company, cadre))

    @action(detail=True, methods=['get'])
    def exigences(self, request, pk=None):
        """Les exigences du cadre, dans l'ordre de leur code."""
        cadre = self.get_object()
        return Response({'results': ExigenceCadreSerializer(
            cadre.exigences.all(), many=True).data})


class ExigenceCadreViewSet(CompanyScopedModelViewSet):
    """NTGRC33 — exigences d'un cadre et leur mapping vers les contrôles."""

    queryset = ExigenceCadre.objects.select_related('cadre').all()
    serializer_class = ExigenceCadreSerializer
    permission_classes = [IsAdminOrResponsableTier]

    def get_queryset(self):
        qs = super().get_queryset()
        params = self.request.query_params
        cadre = (params.get('cadre') or '').strip()
        if cadre.isdigit():
            qs = qs.filter(cadre_id=int(cadre))
        statut = (params.get('statut_couverture') or '').strip()
        if statut:
            qs = qs.filter(statut_couverture=statut)
        controle = (params.get('controle_ref') or '').strip()
        if controle:
            qs = qs.filter(controle_ref=controle)
        return qs


class FluxDonneesViewSet(CompanyScopedModelViewSet):
    """NTGRC30 — cartographie des flux de données personnelles."""

    queryset = FluxDonnees.objects.all()
    serializer_class = FluxDonneesSerializer
    permission_classes = [IsAdminOrResponsableTier]

    def get_queryset(self):
        qs = super().get_queryset()
        params = self.request.query_params
        destination = (params.get('destination') or '').strip()
        if destination:
            qs = qs.filter(destination=destination)
        traitement = (params.get('traitement_ref') or '').strip()
        if traitement:
            qs = qs.filter(traitement_ref=traitement)
        hors = (params.get('transfert_hors_maroc') or '').strip()
        if hors in ('1', 'true', 'True', 'oui'):
            qs = qs.filter(transfert_hors_maroc=True)
        elif hors in ('0', 'false', 'False', 'non'):
            qs = qs.filter(transfert_hors_maroc=False)
        return qs

    @action(detail=False, methods=['get'], url_path='hors-maroc')
    def hors_maroc(self, request):
        """Transferts internationaux à surveiller (sans garantie d'abord)."""
        from .selectors import flux_hors_maroc

        qs = flux_hors_maroc(request.user.company)
        return Response({'results': self.get_serializer(qs, many=True).data})


# PACT7 — un agrégat DOIT déclarer sa forme. Sans cette déclaration, le schéma
# OpenAPI publierait cet endpoint « objet vide » : un schéma qui ment est pire
# qu'un schéma absent, parce qu'un garde-fou qui s'y fie produit des rouges sur
# du code correct. Les clés ci-dessous sont EXACTEMENT celles de
# `selectors.tableau_bord_dpo` (et de contract_samples/tableau_bord_dpo.json).
@extend_schema(responses=inline_serializer('GrcTableauBordDpo', {
    'dsr_ouverts': serializers.IntegerField(),
    'dsr_en_retard': serializers.IntegerField(),
    'dsr_details': inline_serializer('GrcTableauBordDpoDsr', {
        'type': serializers.CharField(),
        'statut': serializers.CharField(),
        'echeance': serializers.CharField(allow_null=True),
        # Entier SIGNÉ : négatif = en retard (jamais écrêté à zéro).
        'jours_restants': serializers.IntegerField(allow_null=True),
    }, many=True),
    'violations_72h': serializers.IntegerField(),
    'violations_72h_depassees': serializers.IntegerField(),
    'consentements_retires_mois': serializers.IntegerField(),
    'politiques_non_attestees': serializers.IntegerField(),
    'controles_a_tester': serializers.IntegerField(),
    'risques_critiques': serializers.IntegerField(),
    'traitements_sans_dpia': serializers.IntegerField(),
    'calcule_le': serializers.CharField(),
}))
@api_view(['GET'])
@permission_classes([IsAdminOrResponsableTier])
def tableau_bord_dpo(request):
    """NTGRC28 — les SEPT compteurs de conformité du DPO, en UN appel.

    Agrégat LECTURE SEULE, scopé à ``request.user.company`` (jamais une
    société lue du corps ou de la requête). Aucune donnée personnelle n'y
    figure : des comptes et des échéances, jamais un nom ni un email.
    """
    from .selectors import tableau_bord_dpo as _cockpit

    return Response(_cockpit(request.user.company))


def _periode_depuis_requete(donnees):
    """Fenêtre ``{debut, fin}`` lue de la requête (ISO), ou dates vides.

    Une date illisible est traitée comme ABSENTE plutôt que rejetée : une
    recherche e-discovery ne doit pas échouer sur une faute de frappe de
    fenêtre — elle doit chercher, et dire sur quelle fenêtre elle a cherché
    (la réponse renvoie toujours la période effectivement appliquée).
    """
    from django.utils.dateparse import parse_datetime

    fenetre = {}
    for cle in ('debut', 'fin'):
        brut = (donnees.get(cle) or '').strip()
        fenetre[cle] = parse_datetime(brut) if brut else None
    return fenetre


@api_view(['GET', 'POST'])
@permission_classes([IsAdminOrResponsableTier])
def e_discovery(request):
    """NTGRC31 — recherche transverse horodatée (+ mise sous séquestre).

    ``GET`` : ``?terme=...&apps=crm_client,audit_log&debut=...&fin=...``
    renvoie les résultats groupés par app.

    ``POST`` : mêmes paramètres dans le corps, plus un objet ``legal_hold``
    (``{nom, motif, demandeur, base_juridique}``) qui CRÉE un séquestre
    couvrant les résultats gelables. Les types que le séquestre ne sait pas
    réellement geler (le journal d'activité) sont listés dans
    ``types_ignores`` — jamais passés sous silence.
    """
    # NTGRC31 — l'e-discovery vit dans son PROPRE module (jamais réexporté
    # depuis `selectors.py`) : voir la docstring de `ediscovery.py`.
    from .ediscovery import rechercher_e_discovery
    from .services import placer_resultats_sous_hold

    donnees = request.data if request.method == 'POST' else request.query_params
    donnees = donnees or {}
    terme = (donnees.get('terme') or '').strip()
    if not terme:
        return Response(
            {'terme': 'Indiquez le terme à rechercher (email, téléphone ou '
                      'mot-clé).'}, status=400)

    brut_apps = donnees.get('apps')
    if isinstance(brut_apps, str):
        apps_demandees = [a.strip() for a in brut_apps.split(',') if a.strip()]
    elif isinstance(brut_apps, (list, tuple)):
        apps_demandees = [str(a).strip() for a in brut_apps if str(a).strip()]
    else:
        apps_demandees = None

    resultat = rechercher_e_discovery(
        request.user.company, terme, apps=apps_demandees,
        periode=_periode_depuis_requete(donnees), user=request.user)

    if request.method == 'GET':
        return Response(resultat)

    demande_hold = donnees.get('legal_hold') or {}
    if not isinstance(demande_hold, dict) or not demande_hold:
        return Response(resultat)

    hold, ignores = placer_resultats_sous_hold(
        request.user.company, resultat['resultats'],
        nom=demande_hold.get('nom') or f'E-discovery « {terme} »',
        motif=demande_hold.get('motif'),
        demandeur=(demande_hold.get('demandeur')
                   or getattr(request.user, 'username', '') or ''),
        base_juridique=demande_hold.get('base_juridique') or '')
    resultat['types_ignores'] = ignores
    resultat['legal_hold'] = (
        LegalHoldSerializer(hold).data if hold is not None else None)
    return Response(resultat, status=201 if hold is not None else 200)


@api_view(['GET'])
@permission_classes([IsAdminOrResponsableTier])
def dossier_conformite(request):
    """NTGRC32 — ZIP du dossier de conformité (6 exports + manifeste SHA-256).

    Scopé à ``request.user.company``. Le ZIP ne contient AUCUN prix d'achat et
    aucune donnée personnelle brute non nécessaire : le journal de destruction
    n'y expose que des identifiants techniques et des empreintes.
    """
    from django.http import HttpResponse

    from .services import construire_dossier_conformite

    company = request.user.company
    octets, manifeste = construire_dossier_conformite(company)
    reponse = HttpResponse(octets, content_type='application/zip')
    horodatage = manifeste['genere_le'][:10]
    reponse['Content-Disposition'] = (
        f'attachment; filename="dossier-conformite-{horodatage}.zip"')
    reponse['X-Empreinte-Globale'] = manifeste['empreinte_globale']
    return reponse


@api_view(['GET'])
@permission_classes([IsAdminOrResponsableTier])
def score_conformite(request):
    """NTGRC29 — score de maturité conformité (0-100) + détail par critère.

    Agrégat LECTURE SEULE, scopé à ``request.user.company``. Le total ET le
    détail pondéré partent du même calcul : un score sans son détail ne dit
    pas quoi corriger, et deux calculs séparés finissent toujours par se
    contredire.
    """
    from .selectors import score_conformite as _score

    return Response(_score(request.user.company))
