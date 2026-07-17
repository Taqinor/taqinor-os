"""Viewsets DRF du module ``apps.education``.

Tous les viewsets héritent de ``core.viewsets.CompanyScopedModelViewSet`` :
queryset filtré par ``request.user.company``, ``company`` forcée côté serveur
en création (jamais lue du corps de requête).
"""
from rest_framework.decorators import action
from rest_framework.exceptions import ValidationError
from rest_framework.response import Response

from core.viewsets import CompanyScopedModelViewSet

from .models import AnneeScolaire, Classe, Eleve, Famille, Inscription, Niveau
from .serializers import (
    AnneeScolaireSerializer, ClasseSerializer, EleveSerializer,
    FamilleSerializer, InscriptionSerializer, NiveauSerializer)


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
