"""Vues de la Paie marocaine (toutes scopées société, admin-gated).

La paie est INTERNE : aucune donnée n'est exposée côté client. L'accès est
réservé au palier Administrateur/Responsable (``IsResponsableOrAdmin``).
Les viewsets filtrent par ``request.user.company`` (TenantMixin) et posent la
société côté serveur.
"""
from rest_framework import filters, status, viewsets
from rest_framework.decorators import action
from rest_framework.response import Response

from authentication.mixins import TenantMixin
from authentication.permissions import IsResponsableOrAdmin

from .models import (
    AvanceSalarie,
    BaremeIR,
    BulletinPaie,
    CumulAnnuel,
    ElementVariable,
    ParametrePaie,
    PeriodePaie,
    ProfilPaie,
    Rubrique,
    RubriqueEmploye,
)
from .serializers import (
    AvanceSalarieSerializer,
    BaremeIRSerializer,
    BulletinPaieSerializer,
    CumulAnnuelSerializer,
    ElementVariableSerializer,
    ParametrePaieSerializer,
    PeriodePaieSerializer,
    ProfilPaieSerializer,
    RubriqueEmployeSerializer,
    RubriqueSerializer,
)
from .services import (
    TransitionPeriodeInterdite,
    calculer_bulletin,
    changer_statut,
    ensure_defaults,
    ensure_rubriques_defaut,
    ensure_rubriques_standard,
    generer_bulletin,
    importer_elements_rh,
    recalculer_cumul_annuel,
    valider_bulletin,
)


class _PaieBaseViewSet(TenantMixin, viewsets.ModelViewSet):
    """Base : société scopée + accès Administrateur/Responsable uniquement."""
    permission_classes = [IsResponsableOrAdmin]


class ParametrePaieViewSet(_PaieBaseViewSet):
    """Paramètres sociaux versionnés (PAIE2).

    PAIE3 — l'action ``seed-defaults`` provisionne (idempotent) les valeurs
    légales 2026 (paramètres + barème IR) pour la société de l'utilisateur,
    ``valide_par_fondateur=False``. La validation/surcharge se fait ensuite
    par un PATCH classique sur la ligne (``valide_par_fondateur`` et les taux
    sont en écriture).
    """
    queryset = ParametrePaie.objects.all()
    serializer_class = ParametrePaieSerializer
    filter_backends = [filters.OrderingFilter]
    ordering_fields = ['date_effet', 'id']

    @action(detail=False, methods=['post'], url_path='seed-defaults')
    def seed_defaults(self, request):
        """Provisionne les valeurs légales 2026 pour la société (idempotent)."""
        created = ensure_defaults(request.user.company)
        return Response(created, status=status.HTTP_200_OK)


class BaremeIRViewSet(_PaieBaseViewSet):
    """Barèmes IR versionnés et leurs tranches (PAIE4)."""
    queryset = BaremeIR.objects.prefetch_related('tranches').all()
    serializer_class = BaremeIRSerializer
    filter_backends = [filters.SearchFilter, filters.OrderingFilter]
    search_fields = ['libelle']
    ordering_fields = ['date_effet', 'id']


class RubriqueViewSet(_PaieBaseViewSet):
    """Catalogue des rubriques de paie paramétrables (PAIE6).

    Société scopée, accès Administrateur/Responsable. L'action
    ``seed-defaults`` provisionne (idempotent, additif) un jeu de rubriques
    standard (salaire de base, prime, heures sup, CNSS, AMO, IR, avance) pour
    la société, sans jamais écraser une rubrique déjà éditée.
    """
    queryset = Rubrique.objects.all()
    serializer_class = RubriqueSerializer
    filter_backends = [filters.SearchFilter, filters.OrderingFilter]
    search_fields = ['code', 'libelle']
    ordering_fields = ['ordre', 'code', 'id']

    @action(detail=False, methods=['post'], url_path='seed-defaults')
    def seed_defaults(self, request):
        """Provisionne les rubriques de base pour la société (idempotent)."""
        created = ensure_rubriques_defaut(request.user.company)
        return Response(created, status=status.HTTP_200_OK)

    @action(detail=False, methods=['post'], url_path='seed-standard')
    def seed_standard(self, request):
        """Provisionne le catalogue standard étendu (PAIE7) — idempotent.

        Sème les rubriques de base PLUS le catalogue standard (transport,
        panier, ancienneté, CIMR…), sans écraser une rubrique déjà éditée.
        """
        created = ensure_rubriques_standard(request.user.company)
        return Response(created, status=status.HTTP_200_OK)


class ProfilPaieViewSet(_PaieBaseViewSet):
    """Profils de paie des employés (PAIE8) — société scopée, palier paie.

    ``OneToOne`` vers ``rh.DossierEmploye`` ; le salaire de base est SENSIBLE
    (jamais exposé côté client). ``company`` posée côté serveur.
    """
    queryset = ProfilPaie.objects.select_related('employe').all()
    serializer_class = ProfilPaieSerializer
    filter_backends = [filters.SearchFilter, filters.OrderingFilter]
    search_fields = ['employe__nom', 'employe__prenom', 'employe__matricule']
    ordering_fields = ['date_creation', 'id']


class RubriqueEmployeViewSet(_PaieBaseViewSet):
    """Rubriques récurrentes par employé (PAIE9) — société scopée."""
    queryset = RubriqueEmploye.objects.select_related(
        'profil', 'rubrique').all()
    serializer_class = RubriqueEmployeSerializer
    filter_backends = [filters.OrderingFilter]
    ordering_fields = ['date_creation', 'id']


class PeriodePaieViewSet(_PaieBaseViewSet):
    """Périodes de paie — run mensuel + cycle de statuts (PAIE10).

    Le ``statut`` n'avance que par l'action ``changer-statut`` (cycle progressif
    brouillon→calculée→validée→clôturée). L'action ``importer-elements-rh``
    (PAIE11) matérialise les éléments variables RH du mois.
    """
    queryset = PeriodePaie.objects.all()
    serializer_class = PeriodePaieSerializer
    filter_backends = [filters.OrderingFilter]
    ordering_fields = ['annee', 'mois', 'date_creation', 'id']

    @action(detail=True, methods=['post'], url_path='changer-statut')
    def changer_statut(self, request, pk=None):
        """Fait avancer la période vers le ``statut`` demandé (PAIE10)."""
        periode = self.get_object()
        nouveau = request.data.get('statut')
        try:
            changer_statut(periode, nouveau)
        except TransitionPeriodeInterdite as exc:
            return Response(
                {'detail': str(exc)}, status=status.HTTP_400_BAD_REQUEST)
        return Response(
            self.get_serializer(periode).data, status=status.HTTP_200_OK)

    @action(detail=True, methods=['post'], url_path='importer-elements-rh')
    def importer_elements_rh(self, request, pk=None):
        """Importe les éléments variables RH du mois (PAIE11)."""
        periode = self.get_object()
        try:
            importes = importer_elements_rh(periode)
        except TransitionPeriodeInterdite as exc:
            return Response(
                {'detail': str(exc)}, status=status.HTTP_400_BAD_REQUEST)
        return Response({'importes': importes}, status=status.HTTP_200_OK)

    @action(detail=True, methods=['get'], url_path='bulletin')
    def bulletin(self, request, pk=None):
        """Calcule (sans persister) le bulletin d'un profil pour la période.

        PAIE12 — paramètre de requête ``profil`` (id) requis ;
        ``personnes_a_charge`` facultatif. Renvoie le détail du calcul. Donnée
        SENSIBLE : palier paie uniquement.
        """
        periode = self.get_object()
        profil_id = request.query_params.get('profil')
        if not profil_id:
            return Response(
                {'detail': 'Paramètre "profil" requis.'},
                status=status.HTTP_400_BAD_REQUEST)
        try:
            profil = ProfilPaie.objects.get(
                pk=profil_id, company=request.user.company)
        except (ProfilPaie.DoesNotExist, ValueError):
            return Response(
                {'detail': 'Profil inconnu.'},
                status=status.HTTP_404_NOT_FOUND)
        try:
            pac = int(request.query_params.get('personnes_a_charge', 0))
        except (TypeError, ValueError):
            pac = 0
        resultat = calculer_bulletin(profil, periode, personnes_a_charge=pac)
        return Response(resultat, status=status.HTTP_200_OK)


class ElementVariableViewSet(_PaieBaseViewSet):
    """Éléments variables du mois (PAIE11) — société scopée."""
    queryset = ElementVariable.objects.select_related(
        'periode', 'profil', 'rubrique').all()
    serializer_class = ElementVariableSerializer
    filter_backends = [filters.OrderingFilter]
    ordering_fields = ['periode', 'profil', 'id']


class BulletinPaieViewSet(TenantMixin, viewsets.ReadOnlyModelViewSet):
    """Bulletins de paie matérialisés (PAIE17) — snapshot immuable.

    Lecture seule via l'API : un bulletin se crée/recalcule par l'action
    ``generer`` et se fige par l'action ``valider``. Les montants ne sont JAMAIS
    écrits directement (snapshot). Société scopée, palier paie uniquement.
    """
    permission_classes = [IsResponsableOrAdmin]
    queryset = BulletinPaie.objects.select_related(
        'periode', 'profil').prefetch_related('lignes').all()
    serializer_class = BulletinPaieSerializer
    filter_backends = [filters.OrderingFilter]
    ordering_fields = ['date_creation', 'periode', 'profil', 'id']

    @action(detail=False, methods=['post'], url_path='generer')
    def generer(self, request):
        """Matérialise (ou recalcule) le bulletin d'un profil pour une période.

        Corps : ``periode`` (id), ``profil`` (id), ``personnes_a_charge``
        (facultatif). Un bulletin déjà VALIDÉ ne peut être régénéré (400).
        """
        periode_id = request.data.get('periode')
        profil_id = request.data.get('profil')
        if not periode_id or not profil_id:
            return Response(
                {'detail': 'Champs "periode" et "profil" requis.'},
                status=status.HTTP_400_BAD_REQUEST)
        try:
            periode = PeriodePaie.objects.get(
                pk=periode_id, company=request.user.company)
            profil = ProfilPaie.objects.get(
                pk=profil_id, company=request.user.company)
        except (PeriodePaie.DoesNotExist, ProfilPaie.DoesNotExist, ValueError):
            return Response(
                {'detail': 'Période ou profil inconnu.'},
                status=status.HTTP_404_NOT_FOUND)
        try:
            pac = int(request.data.get('personnes_a_charge', 0))
        except (TypeError, ValueError):
            pac = 0
        try:
            bulletin = generer_bulletin(profil, periode, personnes_a_charge=pac)
        except BulletinPaie.BulletinVerrouille as exc:
            return Response(
                {'detail': str(exc)}, status=status.HTTP_400_BAD_REQUEST)
        return Response(
            self.get_serializer(bulletin).data, status=status.HTTP_200_OK)

    @action(detail=True, methods=['post'], url_path='valider')
    def valider(self, request, pk=None):
        """Valide le bulletin → fige le snapshot (immuable, PAIE17)."""
        bulletin = self.get_object()
        valider_bulletin(bulletin)
        return Response(
            self.get_serializer(bulletin).data, status=status.HTTP_200_OK)


class AvanceSalarieViewSet(_PaieBaseViewSet):
    """Avances / prêts salariés (PAIE28) — société scopée, palier paie.

    L'avance se rembourse automatiquement par retenue mensuelle sur le bulletin
    (calcul dans ``calculer_bulletin`` ; imputation effective à la validation du
    bulletin). ``montant_rembourse`` n'est jamais écrit via l'API.
    """
    queryset = AvanceSalarie.objects.select_related('profil').all()
    serializer_class = AvanceSalarieSerializer
    filter_backends = [filters.OrderingFilter]
    ordering_fields = ['date_debut', 'date_creation', 'id']


class CumulAnnuelViewSet(TenantMixin, viewsets.ReadOnlyModelViewSet):
    """Cumuls annuels de paie par employé (PAIE27) — lecture seule.

    Le cumul est un agrégat MATÉRIALISÉ recalculé depuis les bulletins validés
    via l'action ``recalculer`` (corps : ``profil`` id, ``annee``). Jamais saisi
    directement. Société scopée, palier paie uniquement (donnée SENSIBLE).
    """
    permission_classes = [IsResponsableOrAdmin]
    queryset = CumulAnnuel.objects.select_related('profil').all()
    serializer_class = CumulAnnuelSerializer
    filter_backends = [filters.OrderingFilter]
    ordering_fields = ['annee', 'profil', 'date_calcul', 'id']

    @action(detail=False, methods=['post'], url_path='recalculer')
    def recalculer(self, request):
        """Recalcule le cumul annuel d'un profil pour une année (PAIE27).

        Corps : ``profil`` (id) et ``annee`` requis. Agrège les bulletins
        validés de l'année. Idempotent.
        """
        profil_id = request.data.get('profil')
        annee = request.data.get('annee')
        if not profil_id or not annee:
            return Response(
                {'detail': 'Champs "profil" et "annee" requis.'},
                status=status.HTTP_400_BAD_REQUEST)
        try:
            profil = ProfilPaie.objects.get(
                pk=profil_id, company=request.user.company)
            annee = int(annee)
        except (ProfilPaie.DoesNotExist, ValueError, TypeError):
            return Response(
                {'detail': 'Profil ou année invalide.'},
                status=status.HTTP_404_NOT_FOUND)
        cumul = recalculer_cumul_annuel(profil, annee)
        return Response(
            self.get_serializer(cumul).data, status=status.HTTP_200_OK)
