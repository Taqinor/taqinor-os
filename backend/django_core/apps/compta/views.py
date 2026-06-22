"""Vues de la Comptabilité générale (toutes scopées société, admin-gated).

La compta est INTERNE : aucune donnée n'est exposée côté client. L'accès est
réservé au palier Administrateur/Responsable (``IsResponsableOrAdmin``).
Les viewsets filtrent par ``request.user.company`` (TenantMixin) et posent la
société côté serveur ; aucun prix d'achat ni marge n'apparaît ici.
"""
from django.core.exceptions import ValidationError as DjangoValidationError

from rest_framework import filters, status, viewsets
from rest_framework.decorators import action
from rest_framework.response import Response

from authentication.mixins import TenantMixin
from authentication.permissions import IsResponsableOrAdmin

from . import selectors, services
from .models import (
    BordereauRemise, Caisse, CessionImmobilisation, CompteComptable,
    CompteTresorerie, DotationAmortissement, EcritureComptable, Effet,
    ExerciceComptable, Immobilisation, Journal, LignePrevisionnelTresorerie,
    LigneReleve, MouvementCaisse, PeriodeComptable, PlanComptable,
    RapprochementBancaire, VirementInterne,
)
from .serializers import (
    BordereauRemiseSerializer, CaisseSerializer,
    CessionImmobilisationSerializer, ClotureCaisseSerializer,
    CompteComptableSerializer, CompteTresorerieSerializer,
    DotationAmortissementSerializer, EcritureComptableSerializer,
    EffetSerializer, ExerciceComptableSerializer, ImmobilisationSerializer,
    JournalSerializer, LignePrevisionnelTresorerieSerializer,
    LigneReleveSerializer, MouvementCaisseSerializer, PeriodeComptableSerializer,
    PlanAmortissementSerializer, PlanComptableSerializer,
    RapprochementBancaireSerializer, VirementInterneSerializer,
)


class _ComptaBaseViewSet(TenantMixin, viewsets.ModelViewSet):
    """Base : société scopée + accès Administrateur/Responsable uniquement."""
    permission_classes = [IsResponsableOrAdmin]


class PlanComptableViewSet(_ComptaBaseViewSet):
    """Plan(s) comptable(s) de la société (FG107). Action ``seed`` pour amorcer
    le plan CGNC + les journaux standards (idempotent)."""
    queryset = PlanComptable.objects.all()
    serializer_class = PlanComptableSerializer

    @action(detail=False, methods=['post'])
    def seed(self, request):
        company = request.user.company
        plan = services.seed_plan_comptable(company)
        services.seed_journaux(company)
        return Response(PlanComptableSerializer(plan).data)


class CompteComptableViewSet(_ComptaBaseViewSet):
    """Comptes du plan comptable (FG107). Recherche par numéro/intitulé."""
    queryset = CompteComptable.objects.select_related('plan').all()
    serializer_class = CompteComptableSerializer
    filter_backends = [filters.SearchFilter, filters.OrderingFilter]
    search_fields = ['numero', 'intitule']
    ordering_fields = ['numero', 'classe']

    def get_queryset(self):
        qs = super().get_queryset()
        classe = self.request.query_params.get('classe')
        if classe:
            qs = qs.filter(classe=classe)
        return qs


class JournalViewSet(_ComptaBaseViewSet):
    """Journaux comptables (FG108)."""
    queryset = Journal.objects.select_related('compte_contrepartie').all()
    serializer_class = JournalSerializer
    filter_backends = [filters.OrderingFilter]
    ordering_fields = ['code']


class EcritureComptableViewSet(_ComptaBaseViewSet):
    """Écritures en partie double (FG108). Filtrable par journal/période."""
    queryset = EcritureComptable.objects.select_related('journal').prefetch_related(
        'lignes__compte').all()
    serializer_class = EcritureComptableSerializer
    filter_backends = [filters.OrderingFilter]
    ordering_fields = ['date_ecriture', 'id']

    def get_queryset(self):
        qs = super().get_queryset()
        params = self.request.query_params
        journal = params.get('journal')
        if journal:
            qs = qs.filter(journal_id=journal)
        date_debut = params.get('date_debut')
        if date_debut:
            qs = qs.filter(date_ecriture__gte=date_debut)
        date_fin = params.get('date_fin')
        if date_fin:
            qs = qs.filter(date_ecriture__lte=date_fin)
        return qs

    def perform_create(self, serializer):
        serializer.save(
            company=self.request.user.company, created_by=self.request.user)


class CompteTresorerieViewSet(_ComptaBaseViewSet):
    """Référentiel des comptes bancaires & caisses (FG121)."""
    queryset = CompteTresorerie.objects.select_related('compte_comptable').all()
    serializer_class = CompteTresorerieSerializer
    filter_backends = [filters.OrderingFilter]
    ordering_fields = ['type_compte', 'libelle']

    @action(detail=True, methods=['get'])
    def solde(self, request, pk=None):
        """Solde courant du compte de trésorerie (solde initial + GL)."""
        treso = self.get_object()
        from decimal import Decimal
        mouvements = selectors.solde_compte(
            request.user.company, treso.compte_comptable)
        total = Decimal(treso.solde_initial) + mouvements
        return Response({
            'solde_initial': treso.solde_initial,
            'mouvements': mouvements,
            'solde': total,
        })


class EtatsComptablesViewSet(viewsets.ViewSet):
    """États de synthèse en LECTURE SEULE (FG110-114) : grand livre, balance,
    CPC, bilan. Admin/Responsable uniquement, scopés société côté selector."""
    permission_classes = [IsResponsableOrAdmin]

    def _periode(self, request):
        params = request.query_params
        return {
            'date_debut': params.get('date_debut') or None,
            'date_fin': params.get('date_fin') or None,
            'validees_seulement': params.get('validees') == '1',
        }

    @action(detail=False, methods=['get'])
    def grand_livre(self, request):
        company = request.user.company
        periode = self._periode(request)
        compte = None
        numero = request.query_params.get('compte')
        if numero:
            compte = CompteComptable.objects.filter(
                company=company, numero=numero).first()
        data = selectors.grand_livre(company, compte=compte, **periode)
        return Response(data)

    @action(detail=False, methods=['get'])
    def balance(self, request):
        data = selectors.balance_generale(
            request.user.company, **self._periode(request))
        return Response(data)

    @action(detail=False, methods=['get'])
    def cpc(self, request):
        data = selectors.cpc(request.user.company, **self._periode(request))
        return Response(data)

    @action(detail=False, methods=['get'])
    def bilan(self, request):
        periode = self._periode(request)
        data = selectors.bilan(
            request.user.company, date_fin=periode['date_fin'],
            validees_seulement=periode['validees_seulement'])
        return Response(data)

    @action(detail=False, methods=['get'], url_path='position-tresorerie')
    def position_tresorerie(self, request):
        """Position de trésorerie consolidée + projection nette (FG122).

        Solde par compte/caisse + total (depuis les comptes de trésorerie et le
        grand livre), enrichi d'une projection nette indicative (AR/AP/paie/TVA).
        Lecture seule, scopée société, Admin/Responsable uniquement.
        """
        periode = self._periode(request)
        company = request.user.company
        position = selectors.position_tresorerie(
            company, date_fin=periode['date_fin'],
            validees_seulement=periode['validees_seulement'])
        projection = selectors.projection_tresorerie(
            company, date_fin=periode['date_fin'],
            validees_seulement=periode['validees_seulement'])
        return Response({
            'comptes': position['comptes'],
            'total': position['total'],
            'projection': projection,
        })

    @action(detail=False, methods=['get'], url_path='previsionnel-tresorerie')
    def previsionnel_tresorerie(self, request):
        """Prévisionnel de trésorerie roulant 13 semaines (FG126).

        Empile les lignes prévues éditables (crédits, leasing, salaires, IS…) et
        les effets ouverts (FG127/FG128) au-dessus de la position actuelle, semaine
        par semaine. Paramètres : ``date_debut`` (défaut aujourd'hui),
        ``nb_semaines`` (défaut 13). Lecture seule, Admin/Responsable.
        """
        company = request.user.company
        nb = request.query_params.get('nb_semaines')
        try:
            nb_semaines = int(nb) if nb else 13
        except (TypeError, ValueError):
            nb_semaines = 13
        data = selectors.previsionnel_tresorerie(
            company,
            date_debut=request.query_params.get('date_debut') or None,
            nb_semaines=max(1, min(nb_semaines, 52)))
        return Response(data)


# ── FG115 — Périodes comptables verrouillables ─────────────────────────────

class PeriodeComptableViewSet(_ComptaBaseViewSet):
    """Périodes comptables (FG115) : clôture/réouverture (verrouillage).

    Actions ``cloturer`` / ``rouvrir`` figent ou libèrent la période ; une fois
    verrouillée, les écritures & factures de l'intervalle deviennent immuables.
    """
    queryset = PeriodeComptable.objects.select_related('exercice').all()
    serializer_class = PeriodeComptableSerializer
    filter_backends = [filters.OrderingFilter]
    ordering_fields = ['date_debut', 'date_fin']

    @action(detail=True, methods=['post'])
    def cloturer(self, request, pk=None):
        periode = self.get_object()
        services.cloturer_periode(periode, user=request.user)
        return Response(self.get_serializer(periode).data)

    @action(detail=True, methods=['post'])
    def rouvrir(self, request, pk=None):
        periode = self.get_object()
        try:
            services.rouvrir_periode(periode)
        except DjangoValidationError as exc:
            return Response(
                {'detail': exc.messages[0] if exc.messages else str(exc)},
                status=status.HTTP_400_BAD_REQUEST)
        return Response(self.get_serializer(periode).data)


# ── FG116 / FG117 — Exercices comptables (clôture, OD, à-nouveaux) ──────────

class ExerciceComptableViewSet(_ComptaBaseViewSet):
    """Exercices comptables (FG117) : clôture, réouverture, report d'à-nouveaux.

    Porte aussi l'action ``ecriture-od`` (FG116) : saisie d'une écriture de
    régularisation manuelle (sans document source), refusée si la période est
    verrouillée.
    """
    queryset = ExerciceComptable.objects.prefetch_related('periodes').all()
    serializer_class = ExerciceComptableSerializer
    filter_backends = [filters.OrderingFilter]
    ordering_fields = ['date_debut', 'date_fin']

    @action(detail=True, methods=['post'])
    def cloturer(self, request, pk=None):
        exercice = self.get_object()
        services.cloturer_exercice(exercice, user=request.user)
        return Response(self.get_serializer(exercice).data)

    @action(detail=True, methods=['post'])
    def rouvrir(self, request, pk=None):
        exercice = self.get_object()
        services.rouvrir_exercice(exercice)
        return Response(self.get_serializer(exercice).data)

    @action(detail=True, methods=['post'], url_path='reporter-a-nouveaux')
    def reporter_a_nouveaux(self, request, pk=None):
        """Reporte les soldes de bilan de CET exercice dans ``exercice_cible``.

        Corps : ``{"exercice_cible": <id>}``. L'exercice source (celui de l'URL)
        doit être clôturé ; le report est idempotent.
        """
        exercice_clos = self.get_object()
        cible_id = request.data.get('exercice_cible')
        cible = ExerciceComptable.objects.filter(
            company=request.user.company, id=cible_id).first()
        if cible is None:
            return Response(
                {'detail': 'Exercice cible inconnu.'},
                status=status.HTTP_400_BAD_REQUEST)
        try:
            ecriture = services.reporter_a_nouveaux(
                exercice_clos, cible, user=request.user)
        except DjangoValidationError as exc:
            return Response(
                {'detail': exc.messages[0] if exc.messages else str(exc)},
                status=status.HTTP_400_BAD_REQUEST)
        return Response({
            'exercice': self.get_serializer(cible).data,
            'ecriture_id': ecriture.id if ecriture else None,
        })

    @action(detail=False, methods=['post'], url_path='ecriture-od')
    def ecriture_od(self, request):
        """Crée une écriture de régularisation manuelle (OD) — FG116.

        Corps : ``{date_ecriture, libelle, reference?, lignes:[{compte, debit,
        credit, libelle?}]}``. Σ débit = Σ crédit exigé ; refusée si la période
        est verrouillée.
        """
        company = request.user.company
        data = request.data
        lignes_in = data.get('lignes') or []
        lignes = []
        for lig in lignes_in:
            compte = CompteComptable.objects.filter(
                company=company, id=lig.get('compte')).first()
            if compte is None:
                return Response(
                    {'detail': 'Compte inconnu.'},
                    status=status.HTTP_400_BAD_REQUEST)
            lignes.append({
                'compte': compte,
                'debit': lig.get('debit') or 0,
                'credit': lig.get('credit') or 0,
                'libelle': lig.get('libelle', '') or '',
            })
        try:
            ecriture = services.creer_ecriture_od(
                company, data.get('date_ecriture'),
                data.get('libelle', '') or 'Régularisation', lignes,
                reference=data.get('reference', '') or '',
                created_by=request.user)
        except DjangoValidationError as exc:
            return Response(
                {'detail': exc.messages[0] if exc.messages else str(exc)},
                status=status.HTTP_400_BAD_REQUEST)
        return Response(
            EcritureComptableSerializer(ecriture).data,
            status=status.HTTP_201_CREATED)


# ── FG118 — Registre des immobilisations ───────────────────────────────────

class ImmobilisationViewSet(_ComptaBaseViewSet):
    """Registre des immobilisations (FG118).

    Inventaire des actifs immobilisés (véhicules, outillage, matériel…) avec
    coût, date d'acquisition, catégorie et TVA. Société scopée + accès
    Administrateur/Responsable. Filtrable par catégorie, recherche sur
    libellé/référence. Pas d'amortissement (hors périmètre) — juste le registre.
    """
    queryset = Immobilisation.objects.all()
    serializer_class = ImmobilisationSerializer
    filter_backends = [filters.SearchFilter, filters.OrderingFilter]
    search_fields = ['libelle', 'reference']
    ordering_fields = ['date_acquisition', 'cout', 'libelle']

    def get_queryset(self):
        qs = super().get_queryset()
        categorie = self.request.query_params.get('categorie')
        if categorie:
            qs = qs.filter(categorie=categorie)
        return qs

    @action(detail=True, methods=['get', 'post'], url_path='plan-amortissement')
    def plan_amortissement(self, request, pk=None):
        """Plan d'amortissement de l'immobilisation (FG119).

        GET : renvoie le plan + son calendrier de dotations (ou 404 si aucun).
        POST : (re)génère le plan. Corps : ``{mode, duree_annees,
        base_amortissable?, date_debut?, coefficient_degressif?}``. Idempotent —
        les dotations déjà postées sont préservées. La société est posée côté
        serveur (jamais du corps).
        """
        immo = self.get_object()  # déjà scopé société par TenantMixin.
        if request.method == 'GET':
            plan = getattr(immo, 'plan_amortissement', None)
            if plan is None:
                return Response(
                    {'detail': "Aucun plan d'amortissement."},
                    status=status.HTTP_404_NOT_FOUND)
            return Response(PlanAmortissementSerializer(
                plan, context={'request': request}).data)
        data = request.data
        try:
            plan = services.generer_plan_amortissement(
                immo,
                mode=data.get('mode') or None,
                duree_annees=data.get('duree_annees') or None,
                base_amortissable=data.get('base_amortissable'),
                date_debut=data.get('date_debut') or None,
                coefficient_degressif=data.get('coefficient_degressif'),
            )
        except DjangoValidationError as exc:
            return Response(
                {'detail': exc.messages[0] if exc.messages else str(exc)},
                status=status.HTTP_400_BAD_REQUEST)
        return Response(
            PlanAmortissementSerializer(
                plan, context={'request': request}).data,
            status=status.HTTP_200_OK)

    @action(detail=True, methods=['post'])
    def ceder(self, request, pk=None):
        """Enregistre et poste la cession / mise au rebut de l'actif (FG120).

        Corps : ``{type_cession?, date_cession, prix_cession?}`` —
        ``type_cession`` (vente/rebut) déduit du prix si absent (0 → rebut). La
        VNC, le cumul d'amortissement et le résultat de cession sont figés côté
        serveur, l'écriture de sortie est postée au grand livre (refusée si la
        période est verrouillée) et l'immobilisation est marquée inactive. La
        société est posée côté serveur (jamais du corps). Renvoie la cession.
        """
        immo = self.get_object()  # déjà scopée société par TenantMixin.
        data = request.data
        try:
            cession = services.enregistrer_cession(
                immo,
                date_cession=data.get('date_cession'),
                prix_cession=data.get('prix_cession'),
                type_cession=data.get('type_cession') or None,
                user=request.user,
            )
            services.poster_cession(cession, user=request.user)
        except DjangoValidationError as exc:
            return Response(
                {'detail': exc.messages[0] if exc.messages else str(exc)},
                status=status.HTTP_400_BAD_REQUEST)
        cession.refresh_from_db()
        return Response(
            CessionImmobilisationSerializer(
                cession, context={'request': request}).data,
            status=status.HTTP_201_CREATED)


class CessionImmobilisationViewSet(_ComptaBaseViewSet):
    """Cessions / mises au rebut d'immobilisations (FG120) — lecture seule.

    Les cessions sont enregistrées et postées via l'action ``ceder`` de
    l'immobilisation. Ce viewset les restitue (liste/détail) ; l'action
    ``poster`` re-poste une cession non encore postée (idempotente, refusée en
    période close). Société scopée.
    """
    http_method_names = ['get', 'post', 'head', 'options']
    queryset = CessionImmobilisation.objects.select_related(
        'immobilisation', 'ecriture').all()
    serializer_class = CessionImmobilisationSerializer
    filter_backends = [filters.OrderingFilter]
    ordering_fields = ['date_cession', 'id']

    def get_queryset(self):
        qs = super().get_queryset()
        immobilisation = self.request.query_params.get('immobilisation')
        if immobilisation:
            qs = qs.filter(immobilisation_id=immobilisation)
        type_cession = self.request.query_params.get('type_cession')
        if type_cession:
            qs = qs.filter(type_cession=type_cession)
        return qs

    @action(detail=True, methods=['post'])
    def poster(self, request, pk=None):
        """Poste la cession au grand livre (FG120). Refusée en période close."""
        cession = self.get_object()  # scopée société par TenantMixin.
        try:
            ecriture = services.poster_cession(cession, user=request.user)
        except DjangoValidationError as exc:
            return Response(
                {'detail': exc.messages[0] if exc.messages else str(exc)},
                status=status.HTTP_400_BAD_REQUEST)
        cession.refresh_from_db()
        return Response({
            'cession': self.get_serializer(cession).data,
            'ecriture_id': ecriture.id if ecriture else None,
        })


class DotationAmortissementViewSet(_ComptaBaseViewSet):
    """Dotations d'amortissement (FG119) — lecture seule + action ``poster``.

    Les dotations sont calculées par le service (jamais saisies à la main) ;
    l'action ``poster`` passe la dotation au grand livre (débit classe 6 / crédit
    classe 28), refusée si la période est verrouillée. Société scopée.
    """
    http_method_names = ['get', 'post', 'head', 'options']
    queryset = DotationAmortissement.objects.select_related(
        'plan__immobilisation', 'ecriture').all()
    serializer_class = DotationAmortissementSerializer
    filter_backends = [filters.OrderingFilter]
    ordering_fields = ['annee', 'plan']

    def get_queryset(self):
        qs = super().get_queryset()
        plan = self.request.query_params.get('plan')
        if plan:
            qs = qs.filter(plan_id=plan)
        immobilisation = self.request.query_params.get('immobilisation')
        if immobilisation:
            qs = qs.filter(plan__immobilisation_id=immobilisation)
        return qs

    @action(detail=True, methods=['post'])
    def poster(self, request, pk=None):
        """Poste la dotation au grand livre (FG119). Refusée en période close."""
        dotation = self.get_object()  # scopée société par TenantMixin.
        try:
            ecriture = services.poster_dotation(dotation, user=request.user)
        except DjangoValidationError as exc:
            return Response(
                {'detail': exc.messages[0] if exc.messages else str(exc)},
                status=status.HTTP_400_BAD_REQUEST)
        dotation.refresh_from_db()
        return Response({
            'dotation': self.get_serializer(dotation).data,
            'ecriture_id': ecriture.id if ecriture else None,
        })


# ── FG123 — Rapprochement bancaire (relevé ↔ écritures) ────────────────────

class RapprochementBancaireViewSet(_ComptaBaseViewSet):
    """Rapprochements bancaires (FG123) : pointer relevé ↔ grand livre.

    Crée un rapprochement par compte de trésorerie/période, ajoute des lignes de
    relevé, pointe chaque ligne contre des lignes du grand livre jusqu'à
    concordance, et expose la synthèse (solde relevé vs solde GL vs écart). C'est
    DISTINCT de l'import de paiements clients (FG42) : aucune écriture n'est
    créée. Société scopée, posée côté serveur ; Admin/Responsable uniquement.
    """
    queryset = RapprochementBancaire.objects.select_related(
        'compte_tresorerie').prefetch_related(
        'lignes_releve__lignes_gl').all()
    serializer_class = RapprochementBancaireSerializer
    filter_backends = [filters.OrderingFilter]
    ordering_fields = ['date_fin', 'date_debut', 'id']

    def get_queryset(self):
        qs = super().get_queryset()
        compte = self.request.query_params.get('compte_tresorerie')
        if compte:
            qs = qs.filter(compte_tresorerie_id=compte)
        statut = self.request.query_params.get('statut')
        if statut:
            qs = qs.filter(statut=statut)
        return qs

    def perform_create(self, serializer):
        serializer.save(
            company=self.request.user.company, created_by=self.request.user)

    @action(detail=True, methods=['get'], url_path='lignes-gl')
    def lignes_gl(self, request, pk=None):
        """Lignes du grand livre pointables sur la période (FG123)."""
        rapprochement = self.get_object()  # scopé société par TenantMixin.
        return Response(selectors.lignes_gl_pointables(rapprochement))

    @action(detail=True, methods=['get'])
    def resume(self, request, pk=None):
        """Synthèse : solde relevé vs solde GL vs écart (FG123)."""
        rapprochement = self.get_object()  # scopé société par TenantMixin.
        return Response(selectors.resume_rapprochement(rapprochement))

    @action(detail=True, methods=['post'], url_path='ligne-releve')
    def ligne_releve(self, request, pk=None):
        """Ajoute une ligne de relevé bancaire (FG123).

        Corps : ``{date_operation, libelle, montant, reference?}``. ``montant``
        signé (+ entrée, − sortie). Société héritée du rapprochement.
        """
        rapprochement = self.get_object()  # scopé société par TenantMixin.
        data = request.data
        try:
            ligne = services.ajouter_ligne_releve(
                rapprochement,
                date_operation=data.get('date_operation'),
                libelle=data.get('libelle', '') or '',
                montant=data.get('montant'),
                reference=data.get('reference', '') or '',
            )
        except DjangoValidationError as exc:
            return Response(
                {'detail': exc.messages[0] if exc.messages else str(exc)},
                status=status.HTTP_400_BAD_REQUEST)
        return Response(
            LigneReleveSerializer(ligne).data,
            status=status.HTTP_201_CREATED)

    @action(detail=True, methods=['post'], url_path='pointer')
    def pointer(self, request, pk=None):
        """Pointe une ligne de relevé contre des lignes du grand livre (FG123).

        Corps : ``{ligne_releve: <id>, lignes_gl: [<id>, ...]}``. Remplace les
        lignes GL appariées ; la ligne devient ``rapprochee`` si l'écart est nul.
        Toutes les lignes restent scopées à la société du rapprochement.
        """
        rapprochement = self.get_object()  # scopé société par TenantMixin.
        data = request.data
        ligne = LigneReleve.objects.filter(
            company=request.user.company, rapprochement=rapprochement,
            id=data.get('ligne_releve')).first()
        if ligne is None:
            return Response(
                {'detail': 'Ligne de relevé inconnue.'},
                status=status.HTTP_400_BAD_REQUEST)
        try:
            ligne = services.pointer_ligne_releve(
                ligne, data.get('lignes_gl') or [])
        except DjangoValidationError as exc:
            return Response(
                {'detail': exc.messages[0] if exc.messages else str(exc)},
                status=status.HTTP_400_BAD_REQUEST)
        return Response(LigneReleveSerializer(ligne).data)

    @action(detail=True, methods=['post'])
    def cloturer(self, request, pk=None):
        """Clôture le rapprochement quand tout concorde (FG123)."""
        rapprochement = self.get_object()  # scopé société par TenantMixin.
        try:
            services.cloturer_rapprochement(rapprochement)
        except DjangoValidationError as exc:
            return Response(
                {'detail': exc.messages[0] if exc.messages else str(exc)},
                status=status.HTTP_400_BAD_REQUEST)
        rapprochement.refresh_from_db()
        return Response(self.get_serializer(rapprochement).data)


# ── FG124 — Caisse / petty cash (journal d'espèces) ────────────────────────

class CaisseViewSet(_ComptaBaseViewSet):
    """Caisses d'espèces (petty cash) pour les achats terrain (FG124).

    Tient un journal d'espèces par caisse : entrées/sorties (avec justificatif
    et pièce) via l'action ``mouvement``, journal + solde courant via
    ``journal``/``resume``, et clôture de caisse (comptage physique, écart) via
    ``cloturer``. Le ``compte_tresorerie`` lié doit être de type caisse. Société
    scopée, posée côté serveur ; Admin/Responsable uniquement.
    """
    queryset = Caisse.objects.select_related('compte_tresorerie').all()
    serializer_class = CaisseSerializer
    filter_backends = [filters.OrderingFilter]
    ordering_fields = ['libelle', 'date_creation']

    def get_queryset(self):
        qs = super().get_queryset()
        actif = self.request.query_params.get('actif')
        if actif in ('0', '1'):
            qs = qs.filter(actif=(actif == '1'))
        return qs

    def perform_create(self, serializer):
        serializer.save(company=self.request.user.company)

    @action(detail=True, methods=['get', 'post'])
    def mouvement(self, request, pk=None):
        """Liste ou enregistre un mouvement d'espèces de la caisse (FG124).

        GET : renvoie le journal d'espèces (mouvements + solde cumulé), filtrable
        par ``date_debut``/``date_fin``.
        POST : enregistre une entrée/sortie. Corps : ``{sens, montant,
        date_mouvement, motif, justificatif?, piece?, compte_contrepartie?,
        poster?}``. ``montant`` strictement positif ; refusé à une date clôturée.
        Si ``poster`` est vrai, l'écriture de caisse est passée au grand livre
        (refusée si la période comptable est verrouillée). Société côté serveur.
        """
        caisse = self.get_object()  # scopée société par TenantMixin.
        if request.method == 'GET':
            params = request.query_params
            return Response(selectors.journal_caisse(
                caisse,
                date_debut=params.get('date_debut') or None,
                date_fin=params.get('date_fin') or None))
        data = request.data
        contrepartie = None
        cp_id = data.get('compte_contrepartie')
        if cp_id:
            contrepartie = CompteComptable.objects.filter(
                company=request.user.company, id=cp_id).first()
            if contrepartie is None:
                return Response(
                    {'detail': 'Compte de contrepartie inconnu.'},
                    status=status.HTTP_400_BAD_REQUEST)
        try:
            mouvement = services.enregistrer_mouvement_caisse(
                caisse,
                sens=data.get('sens'),
                montant=data.get('montant'),
                date_mouvement=data.get('date_mouvement'),
                motif=data.get('motif', '') or '',
                justificatif=data.get('justificatif', '') or '',
                piece=data.get('piece', '') or '',
                compte_contrepartie=contrepartie,
                poster=bool(data.get('poster')),
                user=request.user,
            )
        except DjangoValidationError as exc:
            return Response(
                {'detail': exc.messages[0] if exc.messages else str(exc)},
                status=status.HTTP_400_BAD_REQUEST)
        return Response(
            MouvementCaisseSerializer(mouvement).data,
            status=status.HTTP_201_CREATED)

    @action(detail=True, methods=['post'], url_path='poster-mouvement')
    def poster_mouvement(self, request, pk=None):
        """Poste un mouvement existant au grand livre (FG124).

        Corps : ``{mouvement: <id>}``. Refusé si la période comptable est
        verrouillée. Idempotent. Le mouvement doit appartenir à la caisse.
        """
        caisse = self.get_object()  # scopée société par TenantMixin.
        mouvement = MouvementCaisse.objects.filter(
            company=request.user.company, caisse=caisse,
            id=request.data.get('mouvement')).first()
        if mouvement is None:
            return Response(
                {'detail': 'Mouvement inconnu.'},
                status=status.HTTP_400_BAD_REQUEST)
        try:
            ecriture = services.poster_mouvement_caisse(
                mouvement, user=request.user)
        except DjangoValidationError as exc:
            return Response(
                {'detail': exc.messages[0] if exc.messages else str(exc)},
                status=status.HTTP_400_BAD_REQUEST)
        mouvement.refresh_from_db()
        return Response({
            'mouvement': MouvementCaisseSerializer(mouvement).data,
            'ecriture_id': ecriture.id if ecriture else None,
        })

    @action(detail=True, methods=['get'])
    def resume(self, request, pk=None):
        """Synthèse de la caisse : solde initial/entrées/sorties/courant (FG124)."""
        caisse = self.get_object()  # scopée société par TenantMixin.
        date_fin = request.query_params.get('date_fin') or None
        return Response(selectors.resume_caisse(caisse, date_fin=date_fin))

    @action(detail=True, methods=['get', 'post'])
    def cloturer(self, request, pk=None):
        """Liste les clôtures ou clôture la caisse (cash count) — FG124.

        GET : renvoie l'historique des clôtures de la caisse.
        POST : effectue une clôture. Corps : ``{date_cloture, solde_compte,
        commentaire?}``. Le solde théorique et l'écart sont figés côté serveur ;
        les mouvements ≤ ``date_cloture`` deviennent immuables. La société est
        posée côté serveur (jamais du corps).
        """
        caisse = self.get_object()  # scopée société par TenantMixin.
        if request.method == 'GET':
            return Response(ClotureCaisseSerializer(
                caisse.clotures.all(), many=True).data)
        data = request.data
        try:
            cloture = services.cloturer_caisse(
                caisse,
                date_cloture=data.get('date_cloture'),
                solde_compte=data.get('solde_compte'),
                commentaire=data.get('commentaire', '') or '',
                user=request.user,
            )
        except DjangoValidationError as exc:
            return Response(
                {'detail': exc.messages[0] if exc.messages else str(exc)},
                status=status.HTTP_400_BAD_REQUEST)
        return Response(
            ClotureCaisseSerializer(cloture).data,
            status=status.HTTP_201_CREATED)
