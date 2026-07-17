"""Viewsets DRF du module ``apps.education``.

Tous les viewsets héritent de ``core.viewsets.CompanyScopedModelViewSet`` :
queryset filtré par ``request.user.company``, ``company`` forcée côté serveur
en création (jamais lue du corps de requête).
"""
from django.http import HttpResponse
from rest_framework import mixins, status, viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import ValidationError
from rest_framework.response import Response

from core.mixins import TenantMixin
from core.viewsets import CompanyScopedModelViewSet

from .models import (
    AnneeScolaire, Classe, CreneauEmploiDuTemps, EcheancierScolarite, Eleve,
    Evaluation, Famille, GrilleTarifaire, Inscription, InscriptionCantine,
    Matiere, MatiereClasse, MenuCantine, Niveau, Note, ParametresEducation,
    Presence, Remise, Seance)
from .serializers import (
    AnneeScolaireSerializer, ClasseSerializer, CreneauEmploiDuTempsSerializer,
    EcheancierScolariteSerializer, EleveSerializer, EvaluationSerializer,
    FamilleSerializer, GrilleTarifaireSerializer,
    InscriptionCantineSerializer, InscriptionSerializer,
    MatiereClasseSerializer, MatiereSerializer, MenuCantineSerializer,
    NiveauSerializer, NoteSerializer, ParametresEducationSerializer,
    PresenceSerializer, RemiseSerializer, SeanceSerializer)


class AnneeScolaireViewSet(CompanyScopedModelViewSet):
    queryset = AnneeScolaire.objects.all()
    serializer_class = AnneeScolaireSerializer


class NiveauViewSet(CompanyScopedModelViewSet):
    queryset = Niveau.objects.all()
    serializer_class = NiveauSerializer


class ClasseViewSet(CompanyScopedModelViewSet):
    """NTEDU1 — une classe affiche son effectif courant vs ``capacite_max``
    (propriété calculée ``Classe.effectif``, jamais un champ dénormalisé)."""

    queryset = Classe.objects.select_related('annee_scolaire', 'niveau').all()
    serializer_class = ClasseSerializer


class FamilleViewSet(CompanyScopedModelViewSet):
    queryset = Famille.objects.all()
    serializer_class = FamilleSerializer


class EleveViewSet(CompanyScopedModelViewSet):
    """NTEDU2 — ``numero_dossier`` attribué côté serveur à la création
    (anti-collision, jamais un ``count()+1``). Les élèves radiés sont exclus
    des listes actives par défaut (``?actifs=1``) mais restent consultables
    en historique (aucune exclusion par défaut du queryset de base)."""

    queryset = Eleve.objects.select_related('famille', 'classe').all()
    serializer_class = EleveSerializer

    def get_queryset(self):
        qs = super().get_queryset()
        if self.request.query_params.get('actifs') == '1':
            qs = qs.exclude(
                statut__in=[Eleve.Statut.RADIE, Eleve.Statut.DIPLOME])
        return qs

    def perform_create(self, serializer):
        super().perform_create(serializer)
        from .services import attribuer_numero_dossier
        attribuer_numero_dossier(serializer.instance)

    @action(detail=True, methods=['get'], url_path='certificat-scolarite')
    def certificat_scolarite(self, request, pk=None):
        """NTEDU18 — certificat de scolarité PDF à la demande, numéroté côté
        serveur (``services.generer_certificat_scolarite`` — jamais un
        ``count()+1``). Nécessite ``annee_scolaire`` en query param (ou
        l'année ACTIVE de la société à défaut)."""
        eleve = self.get_object()
        annee_scolaire_id = request.query_params.get('annee_scolaire')
        if annee_scolaire_id:
            annee_scolaire = AnneeScolaire.objects.filter(
                company=request.user.company, pk=annee_scolaire_id).first()
        else:
            annee_scolaire = AnneeScolaire.objects.filter(
                company=request.user.company,
                statut=AnneeScolaire.Statut.ACTIVE).first()
        if annee_scolaire is None:
            raise ValidationError(
                {'annee_scolaire': 'Année scolaire introuvable.'})

        from .services import generer_certificat_scolarite
        try:
            certificat, pdf_bytes = generer_certificat_scolarite(
                eleve, annee_scolaire, user=request.user)
        except RuntimeError as exc:
            return Response(
                {'detail': str(exc)}, status=status.HTTP_503_SERVICE_UNAVAILABLE)
        resp = HttpResponse(pdf_bytes, content_type='application/pdf')
        resp['Content-Disposition'] = (
            f'attachment; filename="certificat_scolarite_'
            f'{certificat.numero}.pdf"')
        return resp


class InscriptionViewSet(CompanyScopedModelViewSet):
    """NTEDU3 — workflow d'inscription (validation/affectation/liste
    d'attente). Les actions ``valider``/``refuser``/``affecter_classe``
    passent TOUJOURS par ``services.py`` (jamais une mutation directe de
    statut dans le viewset)."""

    queryset = Inscription.objects.select_related(
        'eleve', 'annee_scolaire', 'classe_demandee', 'classe_affectee').all()
    serializer_class = InscriptionSerializer

    @action(detail=True, methods=['post'], url_path='valider')
    def valider(self, request, pk=None):
        from .services import valider_inscription
        inscription = valider_inscription(self.get_object(), user=request.user)
        return Response(InscriptionSerializer(inscription).data)

    @action(detail=True, methods=['post'], url_path='refuser')
    def refuser(self, request, pk=None):
        from .services import refuser_inscription
        inscription = refuser_inscription(self.get_object(), user=request.user)
        return Response(InscriptionSerializer(inscription).data)

    @action(detail=True, methods=['post'], url_path='affecter-classe')
    def affecter_classe_action(self, request, pk=None):
        from .services import affecter_classe

        classe_id = request.data.get('classe')
        classe = Classe.objects.filter(
            company=request.user.company, pk=classe_id).first()
        if classe is None:
            raise ValidationError({'classe': 'Classe introuvable.'})
        inscription = affecter_classe(
            self.get_object(), classe, user=request.user)
        return Response(InscriptionSerializer(inscription).data)

    @action(detail=False, methods=['post'], url_path='reinscription-masse')
    def reinscription_masse(self, request):
        """NTEDU4 — génère les inscriptions de réinscription (en_attente) sur
        l'année cible pour chaque élève actif de l'année source. IDEMPOTENT :
        relancer deux fois ne duplique jamais rien (``services.
        reinscrire_en_masse``)."""
        from .services import reinscrire_en_masse

        company = request.user.company
        annee_source = AnneeScolaire.objects.filter(
            company=company, pk=request.data.get('annee_source')).first()
        annee_cible = AnneeScolaire.objects.filter(
            company=company, pk=request.data.get('annee_cible')).first()
        if annee_source is None or annee_cible is None:
            raise ValidationError(
                {'detail': 'annee_source/annee_cible introuvable(s).'})

        result = reinscrire_en_masse(
            company=company, annee_source=annee_source, annee_cible=annee_cible)
        return Response({
            'creees': len(result['creees']),
            'deja_existantes': result['deja_existantes'],
            'inscriptions': InscriptionSerializer(
                result['creees'], many=True).data,
        })

    @action(detail=False, methods=['get'], url_path='a-reinscrire')
    def a_reinscrire(self, request):
        """NTEDU4 — filtre « à réinscrire » : inscriptions ``en_attente``
        générées par une réinscription en masse, en attente de confirmation."""
        qs = self.get_queryset().filter(statut=Inscription.Statut.EN_ATTENTE)
        annee_cible = request.query_params.get('annee_cible')
        if annee_cible:
            qs = qs.filter(annee_scolaire_id=annee_cible)
        return Response(InscriptionSerializer(qs, many=True).data)

    @action(
        detail=False, methods=['post'], url_path='confirmer-reinscription')
    def confirmer_reinscription(self, request):
        """NTEDU4 — action bulk « confirmer réinscription » : valide en une
        fois toutes les inscriptions ``ids`` (statut ``en_attente`` issues de
        la réinscription en masse)."""
        from .services import valider_inscription

        ids = request.data.get('ids') or []
        qs = self.get_queryset().filter(
            pk__in=ids, statut=Inscription.Statut.EN_ATTENTE)
        confirmees = [
            valider_inscription(inscription, user=request.user)
            for inscription in qs]
        return Response(InscriptionSerializer(confirmees, many=True).data)

    @action(detail=False, methods=['get'], url_path='liste-attente')
    def liste_attente(self, request):
        """NTEDU5 — liste d'attente d'une classe, triée par position FIFO
        (recalculée côté serveur — jamais une valeur figée)."""
        classe_id = request.query_params.get('classe')
        if not classe_id:
            raise ValidationError({'classe': 'Paramètre requis.'})
        qs = self.get_queryset().filter(
            classe_demandee_id=classe_id,
            statut=Inscription.Statut.LISTE_ATTENTE,
        ).order_by('position_liste_attente', 'date_demande', 'id')
        return Response(InscriptionSerializer(qs, many=True).data)

    @action(detail=True, methods=['post'], url_path='desinscrire')
    def desinscrire_action(self, request, pk=None):
        """NTEDU5 — désinscrit un élève ; si la classe libérée avait une
        liste d'attente, promeut automatiquement le suivant (``services.
        desinscrire``)."""
        from .services import desinscrire

        inscription = desinscrire(self.get_object())
        return Response(InscriptionSerializer(inscription).data)

    @action(detail=False, methods=['post'], url_path='promouvoir')
    def promouvoir(self, request):
        """NTEDU5 — promotion manuelle du 1er de la liste d'attente d'une
        classe (même logique que la promotion automatique post-
        désinscription)."""
        from .services import promouvoir_premier_liste_attente

        classe = Classe.objects.filter(
            company=request.user.company, pk=request.data.get('classe')).first()
        if classe is None:
            raise ValidationError({'classe': 'Classe introuvable.'})
        promu = promouvoir_premier_liste_attente(classe)
        if promu is None:
            return Response(
                {'detail': 'Aucun candidat en liste d\'attente à promouvoir.'},
                status=200)
        return Response(InscriptionSerializer(promu).data)


class GrilleTarifaireViewSet(CompanyScopedModelViewSet):
    """NTEDU6 — grille tarifaire par (année scolaire, niveau). Une seule
    ligne ACTIVE par couple : la contrainte base
    (``education_une_grille_active_par_annee_niveau``) est l'arbitre final,
    mais un doublon est refusé en amont en 400 (jamais un 500 IntegrityError)
    par une vérification explicite avant écriture."""

    queryset = GrilleTarifaire.objects.select_related(
        'annee_scolaire', 'niveau').all()
    serializer_class = GrilleTarifaireSerializer

    def _guard_doublon(self, *, annee_scolaire, niveau, active, exclude_id=None):
        if not active:
            return
        qs = GrilleTarifaire.objects.filter(
            company=self.request.user.company, annee_scolaire=annee_scolaire,
            niveau=niveau, active=True)
        if exclude_id is not None:
            qs = qs.exclude(pk=exclude_id)
        if qs.exists():
            raise ValidationError({
                'detail': (
                    'Une grille tarifaire active existe déjà pour cette '
                    'année scolaire et ce niveau.')})

    def perform_create(self, serializer):
        data = serializer.validated_data
        self._guard_doublon(
            annee_scolaire=data['annee_scolaire'], niveau=data['niveau'],
            active=data.get('active', True))
        super().perform_create(serializer)

    def perform_update(self, serializer):
        instance = serializer.instance
        data = serializer.validated_data
        self._guard_doublon(
            annee_scolaire=data.get(
                'annee_scolaire', instance.annee_scolaire),
            niveau=data.get('niveau', instance.niveau),
            active=data.get('active', instance.active),
            exclude_id=instance.id)
        super().perform_update(serializer)


class RemiseViewSet(CompanyScopedModelViewSet):
    """NTEDU7 — remises fratrie/bourse. Une remise ``fratrie`` détectée
    automatiquement (``services_remises.detecter_remise_fratrie``) arrive
    TOUJOURS en ``brouillon`` — seules les actions ``approuver``/``rejeter``
    changent son statut (jamais une mutation directe via ``PATCH statut``,
    exclu des champs modifiables du serializer)."""

    queryset = Remise.objects.select_related('famille', 'eleve').all()
    serializer_class = RemiseSerializer

    @action(detail=True, methods=['post'], url_path='approuver')
    def approuver(self, request, pk=None):
        remise = self.get_object()
        remise.statut = Remise.Statut.APPROUVEE
        remise.approuve_par = request.user
        remise.save(update_fields=['statut', 'approuve_par'])
        return Response(RemiseSerializer(remise).data)

    @action(detail=True, methods=['post'], url_path='rejeter')
    def rejeter(self, request, pk=None):
        remise = self.get_object()
        remise.statut = Remise.Statut.REJETEE
        remise.approuve_par = request.user
        remise.save(update_fields=['statut', 'approuve_par'])
        return Response(RemiseSerializer(remise).data)


class EcheancierScolariteViewSet(
        TenantMixin, mixins.RetrieveModelMixin, mixins.ListModelMixin,
        viewsets.GenericViewSet):
    """NTEDU8 — échéancier de scolarité, EN LECTURE SEULE : généré
    exclusivement par ``services_echeancier.generer_echeancier`` à la
    validation d'une inscription, jamais créé/modifié directement via l'API."""

    queryset = EcheancierScolarite.objects.select_related(
        'eleve', 'annee_scolaire', 'grille_tarifaire').prefetch_related(
        'lignes').all()
    serializer_class = EcheancierScolariteSerializer


class SeanceViewSet(CompanyScopedModelViewSet):
    queryset = Seance.objects.select_related('classe', 'enseignant').all()
    serializer_class = SeanceSerializer


class PresenceViewSet(CompanyScopedModelViewSet):
    queryset = Presence.objects.select_related('seance', 'eleve').all()
    serializer_class = PresenceSerializer

    @action(detail=False, methods=['post'], url_path='bulk-saisie')
    def bulk_saisie(self, request):
        """NTEDU12 — saisie de présence pour une classe entière EN UN SEUL
        appel API (jamais un appel par élève). Corps attendu :
        ``{"seance": <id>, "presences": [{"eleve": <id>, "statut": "...",
        "justificatif": <id?>}, ...]}``. ``upsert`` (create/update) par
        (seance, eleve) — rejouer le même appel est sans effet de bord
        supplémentaire."""
        company = request.user.company
        seance_id = request.data.get('seance')
        seance = Seance.objects.filter(company=company, pk=seance_id).first()
        if seance is None:
            raise ValidationError({'seance': 'Séance introuvable.'})

        entrees = request.data.get('presences') or []
        valid_statuts = {c for c, _ in Presence.Statut.choices}
        resultats = []
        for entree in entrees:
            eleve_id = entree.get('eleve')
            statut = entree.get('statut', Presence.Statut.PRESENT)
            if statut not in valid_statuts:
                raise ValidationError(
                    {'statut': f'Statut invalide : {statut}.'})
            eleve = Eleve.objects.filter(company=company, pk=eleve_id).first()
            if eleve is None:
                raise ValidationError(
                    {'eleve': f'Élève introuvable : {eleve_id}.'})
            presence, _created = Presence.objects.update_or_create(
                company=company, seance=seance, eleve=eleve,
                defaults={
                    'statut': statut,
                    'justificatif_id': entree.get('justificatif'),
                    'saisi_par': request.user,
                })
            resultats.append(presence)

        return Response(PresenceSerializer(resultats, many=True).data)


class MatiereViewSet(CompanyScopedModelViewSet):
    queryset = Matiere.objects.select_related('niveau').all()
    serializer_class = MatiereSerializer


class MatiereClasseViewSet(CompanyScopedModelViewSet):
    """NTEDU14 — coefficient d'une matière POUR une classe donnée (jamais
    global) : la contrainte base ``education_coefficient_unique_par_classe_
    matiere`` garantit une seule ligne par (classe, matière) — deux classes
    du même niveau peuvent porter des coefficients différents."""

    queryset = MatiereClasse.objects.select_related(
        'classe', 'matiere', 'enseignant').all()
    serializer_class = MatiereClasseSerializer


# =============================================================================
# NTEDU15 — Évaluations et notes.
# =============================================================================

class EvaluationViewSet(CompanyScopedModelViewSet):
    queryset = Evaluation.objects.select_related('matiere_classe').all()
    serializer_class = EvaluationSerializer


class NoteViewSet(CompanyScopedModelViewSet):
    queryset = Note.objects.select_related('evaluation', 'eleve').all()
    serializer_class = NoteSerializer

    @action(detail=False, methods=['post'], url_path='bulk-saisie')
    def bulk_saisie(self, request):
        """NTEDU15 — saisie de notes pour une évaluation entière EN UN SEUL
        appel API. Corps attendu : ``{"evaluation": <id>, "notes":
        [{"eleve": <id>, "valeur": <num|null>, "appreciation": "..."}]}``.
        ``upsert`` (create/update) par (evaluation, eleve). AUTH — un
        enseignant ne peut saisir QUE sur ses propres ``matiere_classe``
        (``services.peut_saisir_notes``) ; un admin/superuser contourne."""
        from .services import peut_saisir_notes

        company = request.user.company
        evaluation_id = request.data.get('evaluation')
        evaluation = Evaluation.objects.filter(
            company=company, pk=evaluation_id).select_related(
            'matiere_classe').first()
        if evaluation is None:
            raise ValidationError({'evaluation': 'Évaluation introuvable.'})
        if not peut_saisir_notes(request.user, evaluation.matiere_classe):
            return Response(
                {'detail': (
                    "Vous ne pouvez saisir des notes que sur vos propres "
                    "classes/matières.")},
                status=status.HTTP_403_FORBIDDEN)

        entrees = request.data.get('notes') or []
        resultats = []
        for entree in entrees:
            eleve_id = entree.get('eleve')
            eleve = Eleve.objects.filter(company=company, pk=eleve_id).first()
            if eleve is None:
                raise ValidationError(
                    {'eleve': f'Élève introuvable : {eleve_id}.'})
            note, _created = Note.objects.update_or_create(
                company=company, evaluation=evaluation, eleve=eleve,
                defaults={
                    'valeur': entree.get('valeur'),
                    'appreciation': entree.get('appreciation', ''),
                })
            resultats.append(note)

        return Response(NoteSerializer(resultats, many=True).data)


# =============================================================================
# NTEDU19 — Paramètres école.
# =============================================================================

class ParametresEducationViewSet(CompanyScopedModelViewSet):
    """NTEDU19 — réglages par défaut de l'établissement. Singleton par
    société (même patron que ``sav.SavSlaSettingsViewSet``) : ``list``
    renvoie l'unique enregistrement (get_or_create), l'écriture passe par
    ``create`` (upsert PATCH-like)."""

    queryset = ParametresEducation.objects.all()
    serializer_class = ParametresEducationSerializer

    def list(self, request, *args, **kwargs):
        company = request.user.company
        if company is None:
            return Response({})
        obj = ParametresEducation.get(company)
        return Response(self.get_serializer(obj).data)

    def create(self, request, *args, **kwargs):
        company = request.user.company
        obj = ParametresEducation.get(company)
        serializer = self.get_serializer(obj, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        serializer.save(company=company)
        return Response(serializer.data, status=status.HTTP_200_OK)


# =============================================================================
# NTEDU21 — Emploi du temps par classe.
# =============================================================================

class CreneauEmploiDuTempsViewSet(CompanyScopedModelViewSet):
    """NTEDU21 — un conflit (classe/enseignant/salle sur un créneau qui
    chevauche déjà un autre créneau actif) est REJETÉ en 400 EXPLICITE par
    ``services_planning.verifier_conflit_creneau`` (jamais un 500 — même
    patron que ``GrilleTarifaireViewSet``)."""

    queryset = CreneauEmploiDuTemps.objects.select_related(
        'classe', 'matiere_classe__matiere', 'matiere_classe__enseignant').all()
    serializer_class = CreneauEmploiDuTempsSerializer

    def get_queryset(self):
        qs = super().get_queryset()
        classe_id = self.request.query_params.get('classe')
        if classe_id:
            qs = qs.filter(classe_id=classe_id)
        return qs

    def perform_create(self, serializer):
        """Conflit vérifié EN AMONT sur une instance NON SAUVEGARDÉE — jamais
        un créer-puis-annuler (même patron que ``GrilleTarifaireViewSet.
        _guard_doublon``)."""
        from .services_planning import verifier_conflit_creneau

        data = serializer.validated_data
        candidat = CreneauEmploiDuTemps(
            company=self.request.user.company, classe=data['classe'],
            matiere_classe=data['matiere_classe'],
            jour_semaine=data['jour_semaine'], heure_debut=data['heure_debut'],
            heure_fin=data['heure_fin'], salle=data.get('salle', ''),
            actif=data.get('actif', True))
        verifier_conflit_creneau(candidat)
        super().perform_create(serializer)

    def perform_update(self, serializer):
        from .services_planning import verifier_conflit_creneau

        instance = serializer.instance
        data = serializer.validated_data
        candidat = CreneauEmploiDuTemps(
            pk=instance.pk, company=instance.company,
            classe=data.get('classe', instance.classe),
            matiere_classe=data.get('matiere_classe', instance.matiere_classe),
            jour_semaine=data.get('jour_semaine', instance.jour_semaine),
            heure_debut=data.get('heure_debut', instance.heure_debut),
            heure_fin=data.get('heure_fin', instance.heure_fin),
            salle=data.get('salle', instance.salle),
            actif=data.get('actif', instance.actif))
        verifier_conflit_creneau(candidat)
        super().perform_update(serializer)


# =============================================================================
# NTEDU25 — Cantine (menus + inscriptions).
# =============================================================================

class MenuCantineViewSet(CompanyScopedModelViewSet):
    queryset = MenuCantine.objects.all()
    serializer_class = MenuCantineSerializer

    @action(detail=False, methods=['get'], url_path='jour')
    def jour(self, request):
        """NTEDU25 — liste cantine du jour (élèves inscrits ce jour + alerte
        allergie si le menu contient un allergène déclaré). Paramètre
        ``date`` (YYYY-MM-DD), défaut aujourd'hui."""
        from datetime import date as date_cls

        from .services_cantine import eleves_cantine_du_jour

        date_str = request.query_params.get('date')
        if date_str:
            try:
                cible = date_cls.fromisoformat(date_str)
            except ValueError:
                raise ValidationError({'date': 'Format attendu : YYYY-MM-DD.'})
        else:
            from django.utils import timezone
            cible = timezone.localdate()

        resultats = eleves_cantine_du_jour(request.user.company, cible)
        return Response([
            {
                'eleve': EleveSerializer(r['eleve']).data,
                'alerte_allergie': r['alerte_allergie'],
            }
            for r in resultats
        ])


class InscriptionCantineViewSet(CompanyScopedModelViewSet):
    queryset = InscriptionCantine.objects.select_related('eleve').all()
    serializer_class = InscriptionCantineSerializer
