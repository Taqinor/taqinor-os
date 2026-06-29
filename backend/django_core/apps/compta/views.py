"""Vues de la Comptabilité générale (toutes scopées société, admin-gated).

La compta est INTERNE : aucune donnée n'est exposée côté client. L'accès est
réservé au palier Administrateur/Responsable (``IsResponsableOrAdmin``).
Les viewsets filtrent par ``request.user.company`` (TenantMixin) et posent la
société côté serveur ; aucun prix d'achat ni marge n'apparaît ici.
"""
import csv
import io

from django.core.exceptions import ValidationError as DjangoValidationError
from django.http import HttpResponse

from rest_framework import filters, status, viewsets
from rest_framework.decorators import action
from rest_framework.response import Response

from authentication.mixins import TenantMixin
from authentication.permissions import IsResponsableOrAdmin

from . import selectors, services
from .models import (
    BaremeIndemnite, BordereauRemise, Caisse, CessionImmobilisation,
    CompteComptable, CompteTresorerie, DeclarationTVA, DotationAmortissement,
    EcritureComptable, Effet, ExerciceComptable, Immobilisation,
    IndemniteChantier, Journal, LignePrevisionnelTresorerie, LigneReleve,
    MouvementCaisse, NoteFrais, PaymentRun, PeriodeComptable, PlanComptable,
    Rapprochement, RapprochementBancaire, RetenueSource, VirementInterne,
)
from .serializers import (
    BaremeIndemniteSerializer, BordereauRemiseSerializer, CaisseSerializer,
    CessionImmobilisationSerializer, ClotureCaisseSerializer,
    CompteComptableSerializer, CompteTresorerieSerializer,
    DeclarationTVASerializer, DotationAmortissementSerializer,
    EcritureComptableSerializer, EffetSerializer, ExerciceComptableSerializer,
    ImmobilisationSerializer, IndemniteChantierSerializer, JournalSerializer,
    LignePrevisionnelTresorerieSerializer, LigneReleveSerializer,
    MouvementCaisseSerializer, NoteFraisSerializer, PaymentRunSerializer,
    PeriodeComptableSerializer, PlanAmortissementSerializer,
    PlanComptableSerializer, RapprochementBancaireSerializer,
    RapprochementSerializer, RetenueSourceSerializer, VirementInterneSerializer,
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

    @action(detail=False, methods=['get'], url_path='balance-agee-fournisseurs')
    def balance_agee_fournisseurs(self, request):
        """Balance âgée fournisseurs (FG132) : encours dû par fournisseur,
        bucketé 0–30 / 31–60 / 61–90 / 90+ jours depuis le grand livre (compte
        4411). Miroir AP de la balance âgée clients. Paramètres :
        ``date_reference`` (défaut aujourd'hui), ``validees`` (1 → écritures
        validées seulement). Lecture seule, scopée société, Admin/Responsable.
        """
        data = selectors.balance_agee_fournisseurs(
            request.user.company,
            date_reference=request.query_params.get('date_reference') or None,
            validees_seulement=request.query_params.get('validees') == '1')
        return Response(data)

    @action(detail=False, methods=['get'],
            url_path='releve-fournisseur/(?P<tiers_id>[0-9]+)')
    def releve_fournisseur(self, request, tiers_id=None):
        """Relevé de compte d'un fournisseur (FG132) : mouvements chronologiques
        du compte 4411 pour l'auxiliaire ``tiers_id`` + solde dû. Miroir AP du
        relevé client. Paramètres : ``date_debut`` / ``date_fin`` / ``validees``.
        Lecture seule, scopée société, Admin/Responsable.
        """
        periode = self._periode(request)
        data = selectors.releve_fournisseur(
            request.user.company, int(tiers_id),
            date_debut=periode['date_debut'], date_fin=periode['date_fin'],
            validees_seulement=periode['validees_seulement'])
        return Response(data)

    @action(detail=False, methods=['get'], url_path='releve-deductions-tva')
    def releve_deductions_tva(self, request):
        """Relevé de déductions détaillé — annexe TVA exigée par la DGI (FG138).

        Liste ligne par ligne chaque pièce ouvrant droit à déduction de TVA sur
        la période (date, référence/pièce, journal, tiers fournisseur, base HT,
        TVA, taux), déduite du grand livre (comptes 3455…). La somme des TVA
        reconcilie avec la TVA déductible de la déclaration (FG137). Paramètres :
        ``date_debut`` / ``date_fin`` (la période de la déclaration), ``validees``
        (1 → écritures validées seulement) et ``export=csv`` pour l'export CSV.
        Lecture seule, scopée société, Admin/Responsable.
        """
        periode = self._periode(request)
        company = request.user.company
        data = selectors.releve_deductions_tva(
            company, date_debut=periode['date_debut'],
            date_fin=periode['date_fin'],
            validees_seulement=periode['validees_seulement'])
        if request.query_params.get('export') == 'csv':
            return self._export_deductions_csv(data)
        return Response(data)

    @staticmethod
    def _export_deductions_csv(data):
        """Sérialise le relevé de déductions TVA (FG138) en CSV (DGI)."""
        buffer = io.StringIO()
        writer = csv.writer(buffer, delimiter=';')
        writer.writerow(['Relevé de déductions de TVA (annexe DGI)'])
        writer.writerow(
            ['Période', f"{data['date_debut'] or ''} → {data['date_fin'] or ''}"])
        writer.writerow([])
        writer.writerow(
            ['Date', 'Référence', 'Journal', 'Libellé', 'Tiers',
             'Base HT', 'TVA', 'Taux %'])
        for ligne in data['lignes']:
            taux = ligne['taux']
            writer.writerow([
                ligne['date'], ligne['reference'], ligne['journal'],
                ligne['libelle'], ligne['tiers'], ligne['base_ht'],
                ligne['tva'], '' if taux is None else taux])
        writer.writerow([])
        writer.writerow(
            ['Totaux', '', '', '', '', data['totaux']['base_ht'],
             data['totaux']['tva'], ''])
        resp = HttpResponse(
            buffer.getvalue(), content_type='text/csv; charset=utf-8')
        resp['Content-Disposition'] = (
            'attachment; filename="releve_deductions_tva_'
            f"{data['date_debut'] or 'periode'}_{data['date_fin'] or ''}.csv\"")
        return resp


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


# ── FG125 — Virements internes entre comptes de trésorerie ─────────────────

class VirementInterneViewSet(_ComptaBaseViewSet):
    """Virements internes entre comptes de trésorerie (FG125).

    Banque↔banque/caisse en écriture à deux jambes. La création valide les
    comptes (mêmes société, différents) ; l'action ``poster`` passe l'écriture
    équilibrée au grand livre (refusée en période close). Société scopée.
    """
    queryset = VirementInterne.objects.select_related(
        'compte_source', 'compte_destination', 'ecriture').all()
    serializer_class = VirementInterneSerializer
    filter_backends = [filters.OrderingFilter]
    ordering_fields = ['date_virement', 'id']

    def get_queryset(self):
        qs = super().get_queryset()
        posted = self.request.query_params.get('posted')
        if posted in ('0', '1'):
            qs = qs.filter(posted=(posted == '1'))
        return qs

    def perform_create(self, serializer):
        serializer.save(
            company=self.request.user.company, created_by=self.request.user)

    @action(detail=True, methods=['post'])
    def poster(self, request, pk=None):
        """Poste le virement au grand livre (FG125). Refusé en période close."""
        virement = self.get_object()  # scopé société par TenantMixin.
        try:
            ecriture = services.poster_virement(virement, user=request.user)
        except DjangoValidationError as exc:
            return Response(
                {'detail': exc.messages[0] if exc.messages else str(exc)},
                status=status.HTTP_400_BAD_REQUEST)
        virement.refresh_from_db()
        return Response({
            'virement': self.get_serializer(virement).data,
            'ecriture_id': ecriture.id if ecriture else None,
        })


# ── FG126 — Prévisionnel de trésorerie roulant 13 semaines ─────────────────

class LignePrevisionnelTresorerieViewSet(_ComptaBaseViewSet):
    """Lignes prévues éditables du prévisionnel de trésorerie (FG126).

    Saisie manuelle des flux attendus (crédits, leasing, salaires, acomptes IS…)
    empilés au-dessus de la projection AR/AP. La projection consolidée roulante
    13 semaines est servie par ``etats/previsionnel-tresorerie``. Société scopée.
    """
    queryset = LignePrevisionnelTresorerie.objects.all()
    serializer_class = LignePrevisionnelTresorerieSerializer
    filter_backends = [filters.OrderingFilter]
    ordering_fields = ['date_prevue', 'id']

    def get_queryset(self):
        qs = super().get_queryset()
        categorie = self.request.query_params.get('categorie')
        if categorie:
            qs = qs.filter(categorie=categorie)
        return qs

    def perform_create(self, serializer):
        serializer.save(company=self.request.user.company)


# ── FG127 / FG128 — Effets (chèques / traites) ─────────────────────────────

class EffetViewSet(_ComptaBaseViewSet):
    """Portefeuille d'effets à recevoir (FG127) & à payer (FG128).

    Chèques/traites avec échéance/banque/statut (portefeuille→remis→encaissé→
    impayé pour les effets à recevoir ; portefeuille→payé→impayé pour les effets
    à payer). Actions ``encaisser``/``payer``/``rejeter`` font évoluer le statut
    et passent l'écriture au grand livre (refusée en période close). Société
    scopée, posée côté serveur.
    """
    queryset = Effet.objects.select_related('bordereau').all()
    serializer_class = EffetSerializer
    filter_backends = [filters.SearchFilter, filters.OrderingFilter]
    search_fields = ['numero', 'tireur', 'banque']
    ordering_fields = ['date_echeance', 'date_emission', 'montant', 'id']

    def get_queryset(self):
        qs = super().get_queryset()
        params = self.request.query_params
        sens = params.get('sens')
        if sens:
            qs = qs.filter(sens=sens)
        statut = params.get('statut')
        if statut:
            qs = qs.filter(statut=statut)
        return qs

    def perform_create(self, serializer):
        serializer.save(
            company=self.request.user.company, created_by=self.request.user)

    @action(detail=True, methods=['post'])
    def encaisser(self, request, pk=None):
        """Encaisse un effet à recevoir : remis/portefeuille → encaissé (FG127)."""
        effet = self.get_object()  # scopé société par TenantMixin.
        try:
            effet = services.encaisser_effet(
                effet,
                date_encaissement=request.data.get('date_encaissement') or None,
                user=request.user)
        except DjangoValidationError as exc:
            return Response(
                {'detail': exc.messages[0] if exc.messages else str(exc)},
                status=status.HTTP_400_BAD_REQUEST)
        return Response(self.get_serializer(effet).data)

    @action(detail=True, methods=['post'])
    def payer(self, request, pk=None):
        """Paie un effet à payer fournisseur : portefeuille → payé (FG128)."""
        effet = self.get_object()  # scopé société par TenantMixin.
        try:
            effet = services.payer_effet(
                effet,
                date_paiement=request.data.get('date_paiement') or None,
                user=request.user)
        except DjangoValidationError as exc:
            return Response(
                {'detail': exc.messages[0] if exc.messages else str(exc)},
                status=status.HTTP_400_BAD_REQUEST)
        return Response(self.get_serializer(effet).data)

    @action(detail=True, methods=['post'])
    def rejeter(self, request, pk=None):
        """Constate l'impayé / rejet d'un effet (FG130).

        Corps : ``{date_rejet?, frais_rejet?, commentaire?}``. Rouvre le montant
        dû et comptabilise les frais de rejet. Refusé en période close.
        """
        effet = self.get_object()  # scopé société par TenantMixin.
        try:
            effet = services.rejeter_effet(
                effet,
                date_rejet=request.data.get('date_rejet') or None,
                frais_rejet=request.data.get('frais_rejet'),
                commentaire=request.data.get('commentaire', '') or '',
                user=request.user)
        except DjangoValidationError as exc:
            return Response(
                {'detail': exc.messages[0] if exc.messages else str(exc)},
                status=status.HTTP_400_BAD_REQUEST)
        return Response(self.get_serializer(effet).data)


# ── FG129 — Bordereau de remise en banque ──────────────────────────────────

class BordereauRemiseViewSet(_ComptaBaseViewSet):
    """Bordereaux de remise en banque d'effets à recevoir (FG129).

    Regroupe des effets pour un dépôt groupé + écriture de remise. La création
    rattache les effets (corps ``{compte_tresorerie, date_remise, reference?,
    effet_ids: [...]}``) ; l'action ``poster`` passe l'écriture et fait basculer
    les effets en ``remis``. Société scopée, posée côté serveur.
    """
    http_method_names = ['get', 'post', 'head', 'options']
    queryset = BordereauRemise.objects.select_related(
        'compte_tresorerie', 'ecriture').prefetch_related('effets').all()
    serializer_class = BordereauRemiseSerializer
    filter_backends = [filters.OrderingFilter]
    ordering_fields = ['date_remise', 'id']

    def get_queryset(self):
        qs = super().get_queryset()
        statut = self.request.query_params.get('statut')
        if statut:
            qs = qs.filter(statut=statut)
        return qs

    def create(self, request, *args, **kwargs):
        data = request.data
        company = request.user.company
        treso = CompteTresorerie.objects.filter(
            company=company, id=data.get('compte_tresorerie')).first()
        if treso is None:
            return Response(
                {'detail': 'Compte de trésorerie inconnu.'},
                status=status.HTTP_400_BAD_REQUEST)
        try:
            bordereau = services.creer_bordereau(
                company, treso,
                date_remise=data.get('date_remise'),
                effet_ids=data.get('effet_ids') or [],
                reference=data.get('reference', '') or '',
                user=request.user)
        except DjangoValidationError as exc:
            return Response(
                {'detail': exc.messages[0] if exc.messages else str(exc)},
                status=status.HTTP_400_BAD_REQUEST)
        return Response(
            self.get_serializer(bordereau).data,
            status=status.HTTP_201_CREATED)

    @action(detail=True, methods=['post'])
    def poster(self, request, pk=None):
        """Poste le bordereau au grand livre (FG129). Refusé en période close."""
        bordereau = self.get_object()  # scopé société par TenantMixin.
        try:
            ecriture = services.poster_bordereau(bordereau, user=request.user)
        except DjangoValidationError as exc:
            return Response(
                {'detail': exc.messages[0] if exc.messages else str(exc)},
                status=status.HTTP_400_BAD_REQUEST)
        bordereau.refresh_from_db()
        return Response({
            'bordereau': self.get_serializer(bordereau).data,
            'ecriture_id': ecriture.id if ecriture else None,
        })


# ── FG131 — Rapprochement 3 voies (BC ↔ réception ↔ facture fournisseur) ────

class RapprochementViewSet(_ComptaBaseViewSet):
    """Rapprochements 3 voies avant paiement (FG131).

    Confronte commandé (BC) ↔ reçu (réception) ↔ facturé (facture fournisseur)
    — les trois documents vivent dans ``apps.stock`` et sont lus via ses
    sélecteurs (jamais dupliqués). La création (corps ``{bon_commande,
    tolerance?, note?}``) passe par le service qui valide le BCF de la société
    et évalue immédiatement l'écart. ``evaluer`` rafraîchit les montants ;
    ``valider`` pose le bon-à-payer (refusé tant qu'un écart bloquant subsiste).
    Société scopée, posée côté serveur.
    """
    queryset = Rapprochement.objects.select_related(
        'bon_commande', 'bon_commande__fournisseur', 'valide_par').all()
    serializer_class = RapprochementSerializer
    filter_backends = [filters.OrderingFilter]
    ordering_fields = ['date_creation', 'date_evaluation', 'ecart', 'id']

    def get_queryset(self):
        qs = super().get_queryset()
        params = self.request.query_params
        statut = params.get('statut')
        if statut:
            qs = qs.filter(statut=statut)
        bon_commande = params.get('bon_commande')
        if bon_commande:
            qs = qs.filter(bon_commande_id=bon_commande)
        return qs

    def create(self, request, *args, **kwargs):
        data = request.data
        company = request.user.company
        serializer = self.get_serializer(data=data)
        serializer.is_valid(raise_exception=True)
        try:
            rapp = services.creer_rapprochement_3voies(
                company,
                bon_commande_id=serializer.validated_data['bon_commande'].id,
                tolerance=serializer.validated_data.get('tolerance'),
                note=serializer.validated_data.get('note', '') or '',
                user=request.user)
        except DjangoValidationError as exc:
            return Response(
                {'detail': exc.messages[0] if exc.messages else str(exc)},
                status=status.HTTP_400_BAD_REQUEST)
        return Response(
            self.get_serializer(rapp).data, status=status.HTTP_201_CREATED)

    @action(detail=True, methods=['post'])
    def evaluer(self, request, pk=None):
        """Rafraîchit les trois montants et recalcule l'écart/statut (FG131)."""
        rapp = self.get_object()  # scopé société par TenantMixin.
        try:
            rapp = services.evaluer_rapprochement(rapp)
        except DjangoValidationError as exc:
            return Response(
                {'detail': exc.messages[0] if exc.messages else str(exc)},
                status=status.HTTP_400_BAD_REQUEST)
        return Response(self.get_serializer(rapp).data)

    @action(detail=True, methods=['post'])
    def valider(self, request, pk=None):
        """Pose le bon-à-payer (FG131). Refusé tant qu'un écart bloque."""
        rapp = self.get_object()  # scopé société par TenantMixin.
        try:
            rapp = services.valider_rapprochement(
                rapp, user=request.user,
                commentaire=request.data.get('commentaire', '') or '')
        except DjangoValidationError as exc:
            return Response(
                {'detail': exc.messages[0] if exc.messages else str(exc)},
                status=status.HTTP_400_BAD_REQUEST)
        return Response(self.get_serializer(rapp).data)


# ── FG133 / FG134 — Campagnes de règlement fournisseurs + fichier virement ──

class PaymentRunViewSet(_ComptaBaseViewSet):
    """Campagnes de règlement fournisseurs (FG133) + export virement (FG134).

    Regroupe une sélection de dettes fournisseur dues à régler en un lot. La
    création (corps ``{date_paiement, mode_paiement?, compte_tresorerie?,
    reference?, note?, lignes: [{tiers_id, montant, reference?, date_echeance?,
    beneficiaire?, rib?, iban?}]}``) passe par le service, qui complète les
    bénéficiaires/coordonnées depuis le sélecteur de stock et calcule le total.
    ``figer`` fige la proposition (brouillon → proposée) ; ``poster`` passe
    l'écriture EN LOT (débit 4411 par ligne / crédit 5141 banque) et solde les
    dettes ; ``fichier-virement`` exporte l'ordre de virement bancaire (CSV).
    Société scopée, posée côté serveur ; suppression interdite une fois postée.
    """
    http_method_names = ['get', 'post', 'delete', 'head', 'options']
    queryset = PaymentRun.objects.select_related(
        'compte_tresorerie', 'ecriture').prefetch_related('lignes').all()
    serializer_class = PaymentRunSerializer
    filter_backends = [filters.OrderingFilter]
    ordering_fields = ['date_paiement', 'date_creation', 'total', 'id']

    def get_queryset(self):
        qs = super().get_queryset()
        params = self.request.query_params
        statut = params.get('statut')
        if statut:
            qs = qs.filter(statut=statut)
        mode = params.get('mode_paiement')
        if mode:
            qs = qs.filter(mode_paiement=mode)
        return qs

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        vd = serializer.validated_data
        compte = vd.get('compte_tresorerie')
        try:
            run = services.creer_payment_run(
                request.user.company,
                date_paiement=vd['date_paiement'],
                mode_paiement=vd.get('mode_paiement'),
                compte_tresorerie=compte,
                reference=vd.get('reference', '') or '',
                note=vd.get('note', '') or '',
                lignes=vd.get('lignes') or [],
                user=request.user)
        except DjangoValidationError as exc:
            return Response(
                {'detail': exc.messages[0] if exc.messages else str(exc)},
                status=status.HTTP_400_BAD_REQUEST)
        return Response(
            self.get_serializer(run).data, status=status.HTTP_201_CREATED)

    def destroy(self, request, *args, **kwargs):
        run = self.get_object()  # scopé société par TenantMixin.
        if run.posted:
            return Response(
                {'detail': 'Une campagne postée ne peut être supprimée.'},
                status=status.HTTP_400_BAD_REQUEST)
        return super().destroy(request, *args, **kwargs)

    @action(detail=True, methods=['post'])
    def figer(self, request, pk=None):
        """Fige la proposition de règlement (brouillon → proposée, FG133)."""
        run = self.get_object()  # scopé société par TenantMixin.
        try:
            run = services.figer_payment_run(run)
        except DjangoValidationError as exc:
            return Response(
                {'detail': exc.messages[0] if exc.messages else str(exc)},
                status=status.HTTP_400_BAD_REQUEST)
        return Response(self.get_serializer(run).data)

    @action(detail=True, methods=['post'])
    def poster(self, request, pk=None):
        """Poste la campagne au grand livre EN LOT (FG133). Refusé en période
        close ; idempotent. Renvoie la campagne postée."""
        run = self.get_object()  # scopé société par TenantMixin.
        try:
            services.poster_payment_run(run, user=request.user)
        except DjangoValidationError as exc:
            return Response(
                {'detail': exc.messages[0] if exc.messages else str(exc)},
                status=status.HTTP_400_BAD_REQUEST)
        run.refresh_from_db()
        return Response(self.get_serializer(run).data)

    @action(detail=True, methods=['get'], url_path='fichier-virement')
    def fichier_virement(self, request, pk=None):
        """Exporte l'ordre de virement bancaire de la campagne (FG134).

        Fichier CSV (un virement par ligne : bénéficiaire, RIB/IBAN, montant,
        devise, référence, motif). Refusé si la campagne n'est pas en virement
        ou si une ligne n'a aucune coordonnée bancaire. Lecture seule.
        """
        run = self.get_object()  # scopé société par TenantMixin.
        try:
            data = services.fichier_virement(run)
        except DjangoValidationError as exc:
            return Response(
                {'detail': exc.messages[0] if exc.messages else str(exc)},
                status=status.HTTP_400_BAD_REQUEST)
        buffer = io.StringIO()
        writer = csv.writer(buffer, delimiter=';')
        writer.writerow(data['headers'])
        writer.writerows(data['rows'])
        resp = HttpResponse(
            buffer.getvalue(), content_type='text/csv; charset=utf-8')
        resp['Content-Disposition'] = (
            f'attachment; filename="virements_{run.reference or run.id}.csv"')
        return resp


# ── FG135 — Notes de frais & remboursements employés ───────────────────────

class NoteFraisViewSet(_ComptaBaseViewSet):
    """Notes de frais & remboursements employés (FG135).

    Saisie d'une dépense avancée par un employé avec justificatif photo, puis
    cycle de validation/remboursement par les actions de service : ``soumettre``
    (brouillon → soumise), ``valider`` (poste la charge : débit classe 6 /
    crédit 4432 personnel-créditeur), ``rejeter`` (motif figé) et ``rembourser``
    (poste le paiement : débit 4432 / crédit trésorerie). Société scopée, posée
    côté serveur ; Admin/Responsable uniquement. Le justificatif accepte un
    upload de fichier (multipart) ; aucune écriture de statut directe par le
    corps.
    """
    queryset = NoteFrais.objects.select_related(
        'employe', 'compte_charge', 'compte_tresorerie',
        'ecriture_charge', 'ecriture_remboursement').all()
    serializer_class = NoteFraisSerializer
    filter_backends = [filters.SearchFilter, filters.OrderingFilter]
    search_fields = ['reference', 'motif']
    ordering_fields = ['date_frais', 'montant', 'statut', 'id']

    def get_queryset(self):
        qs = super().get_queryset()
        params = self.request.query_params
        statut = params.get('statut')
        if statut:
            qs = qs.filter(statut=statut)
        employe = params.get('employe')
        if employe:
            qs = qs.filter(employe_id=employe)
        categorie = params.get('categorie')
        if categorie:
            qs = qs.filter(categorie=categorie)
        return qs

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        vd = serializer.validated_data
        try:
            note = services.creer_note_frais(
                request.user.company,
                employe=vd['employe'],
                date_frais=vd['date_frais'],
                montant=vd['montant'],
                motif=vd.get('motif', '') or '',
                categorie=vd.get('categorie'),
                justificatif=vd.get('justificatif'),
                compte_charge=vd.get('compte_charge'),
                user=request.user)
        except DjangoValidationError as exc:
            return Response(
                {'detail': exc.messages[0] if exc.messages else str(exc)},
                status=status.HTTP_400_BAD_REQUEST)
        return Response(
            self.get_serializer(note).data, status=status.HTTP_201_CREATED)

    @action(detail=True, methods=['post'])
    def soumettre(self, request, pk=None):
        """Soumet la note pour validation (brouillon → soumise) — FG135."""
        note = self.get_object()  # scopée société par TenantMixin.
        try:
            note = services.soumettre_note_frais(note)
        except DjangoValidationError as exc:
            return Response(
                {'detail': exc.messages[0] if exc.messages else str(exc)},
                status=status.HTTP_400_BAD_REQUEST)
        return Response(self.get_serializer(note).data)

    @action(detail=True, methods=['post'])
    def valider(self, request, pk=None):
        """Valide la note et poste la charge au grand livre (FG135).

        Corps : ``{compte_charge?}``. Refusé en période close. Idempotent.
        """
        note = self.get_object()  # scopée société par TenantMixin.
        compte_charge = None
        cc_id = request.data.get('compte_charge')
        if cc_id:
            compte_charge = CompteComptable.objects.filter(
                company=request.user.company, id=cc_id).first()
            if compte_charge is None:
                return Response(
                    {'detail': 'Compte de charge inconnu.'},
                    status=status.HTTP_400_BAD_REQUEST)
        try:
            note = services.valider_note_frais(
                note, user=request.user, compte_charge=compte_charge)
        except DjangoValidationError as exc:
            return Response(
                {'detail': exc.messages[0] if exc.messages else str(exc)},
                status=status.HTTP_400_BAD_REQUEST)
        return Response(self.get_serializer(note).data)

    @action(detail=True, methods=['post'])
    def rejeter(self, request, pk=None):
        """Rejette une note soumise (soumise → rejetée), motif figé — FG135."""
        note = self.get_object()  # scopée société par TenantMixin.
        try:
            note = services.rejeter_note_frais(
                note, motif_rejet=request.data.get('motif_rejet', '') or '',
                user=request.user)
        except DjangoValidationError as exc:
            return Response(
                {'detail': exc.messages[0] if exc.messages else str(exc)},
                status=status.HTTP_400_BAD_REQUEST)
        return Response(self.get_serializer(note).data)

    @action(detail=True, methods=['post'])
    def rembourser(self, request, pk=None):
        """Rembourse la note validée et poste le paiement (FG135).

        Corps : ``{compte_tresorerie, date_remboursement?, mode_remboursement?}``.
        Le compte de trésorerie payeur doit appartenir à la société. Refusé en
        période close. Idempotent.
        """
        note = self.get_object()  # scopée société par TenantMixin.
        treso = CompteTresorerie.objects.filter(
            company=request.user.company,
            id=request.data.get('compte_tresorerie')).first()
        if treso is None:
            return Response(
                {'detail': 'Compte de trésorerie inconnu.'},
                status=status.HTTP_400_BAD_REQUEST)
        try:
            note = services.rembourser_note_frais(
                note, compte_tresorerie=treso,
                date_remboursement=request.data.get('date_remboursement')
                or None,
                mode_remboursement=request.data.get('mode_remboursement')
                or None,
                user=request.user)
        except DjangoValidationError as exc:
            return Response(
                {'detail': exc.messages[0] if exc.messages else str(exc)},
                status=status.HTTP_400_BAD_REQUEST)
        return Response(self.get_serializer(note).data)


class BaremeIndemniteViewSet(_ComptaBaseViewSet):
    """Barèmes d'indemnités km/per-diem chantier (FG136).

    Société scopée, posée côté serveur ; Admin/Responsable uniquement. Un seul
    barème peut être marqué « par défaut » actif par société : le poser sur un
    barème démote automatiquement l'ancien défaut (jamais d'erreur de
    contrainte).
    """
    queryset = BaremeIndemnite.objects.all()
    serializer_class = BaremeIndemniteSerializer
    filter_backends = [filters.OrderingFilter]
    ordering_fields = ['libelle', 'defaut', 'id']

    def _demote_other_defaults(self, company, keep_id=None):
        qs = BaremeIndemnite.objects.filter(
            company=company, defaut=True, actif=True)
        if keep_id is not None:
            qs = qs.exclude(id=keep_id)
        qs.update(defaut=False)

    def perform_create(self, serializer):
        company = self.request.user.company
        if serializer.validated_data.get('defaut') and \
                serializer.validated_data.get('actif', True):
            self._demote_other_defaults(company)
        serializer.save(company=company)

    def perform_update(self, serializer):
        company = self.request.user.company
        will_default = serializer.validated_data.get(
            'defaut', serializer.instance.defaut)
        will_actif = serializer.validated_data.get(
            'actif', serializer.instance.actif)
        if will_default and will_actif:
            self._demote_other_defaults(
                company, keep_id=serializer.instance.id)
        serializer.save(company=company)


class IndemniteChantierViewSet(_ComptaBaseViewSet):
    """Indemnités kilométriques & per-diem chantier (FG136).

    Saisie d'un déplacement chantier (employé, barème, GPS départ/chantier,
    jours, aller-retour) : la distance (haversine) et les montants sont calculés
    AUTOMATIQUEMENT côté serveur. Cycle de validation/remboursement par les
    actions de service : ``soumettre``, ``valider`` (poste la charge : débit
    classe 6 / crédit 4432), ``rejeter`` (motif figé), ``rembourser`` (poste le
    paiement). Société scopée, posée côté serveur ; Admin/Responsable
    uniquement ; aucune écriture de statut/montant directe par le corps.
    """
    queryset = IndemniteChantier.objects.select_related(
        'employe', 'bareme', 'compte_charge', 'compte_tresorerie',
        'ecriture_charge', 'ecriture_remboursement').all()
    serializer_class = IndemniteChantierSerializer
    filter_backends = [filters.SearchFilter, filters.OrderingFilter]
    search_fields = ['reference', 'libelle_chantier']
    ordering_fields = ['date_deplacement', 'montant_total', 'statut', 'id']

    def get_queryset(self):
        qs = super().get_queryset()
        params = self.request.query_params
        statut = params.get('statut')
        if statut:
            qs = qs.filter(statut=statut)
        employe = params.get('employe')
        if employe:
            qs = qs.filter(employe_id=employe)
        return qs

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        vd = serializer.validated_data
        try:
            indem = services.creer_indemnite_chantier(
                request.user.company,
                employe=vd['employe'],
                date_deplacement=vd['date_deplacement'],
                bareme=vd.get('bareme'),
                site_lat=vd.get('site_lat'),
                site_lng=vd.get('site_lng'),
                depart_lat=vd.get('depart_lat'),
                depart_lng=vd.get('depart_lng'),
                aller_retour=vd.get('aller_retour', True),
                nombre_jours=vd.get('nombre_jours', 1),
                libelle_chantier=vd.get('libelle_chantier', '') or '',
                user=request.user)
        except DjangoValidationError as exc:
            return Response(
                {'detail': exc.messages[0] if exc.messages else str(exc)},
                status=status.HTTP_400_BAD_REQUEST)
        return Response(
            self.get_serializer(indem).data, status=status.HTTP_201_CREATED)

    @action(detail=True, methods=['post'])
    def soumettre(self, request, pk=None):
        """Soumet l'indemnité pour validation (brouillon → soumise) — FG136."""
        indem = self.get_object()  # scopée société par TenantMixin.
        try:
            indem = services.soumettre_indemnite_chantier(indem)
        except DjangoValidationError as exc:
            return Response(
                {'detail': exc.messages[0] if exc.messages else str(exc)},
                status=status.HTTP_400_BAD_REQUEST)
        return Response(self.get_serializer(indem).data)

    @action(detail=True, methods=['post'])
    def valider(self, request, pk=None):
        """Valide l'indemnité et poste la charge au grand livre (FG136).

        Corps : ``{compte_charge?}``. Refusé en période close. Idempotent.
        """
        indem = self.get_object()  # scopée société par TenantMixin.
        compte_charge = None
        cc_id = request.data.get('compte_charge')
        if cc_id:
            compte_charge = CompteComptable.objects.filter(
                company=request.user.company, id=cc_id).first()
            if compte_charge is None:
                return Response(
                    {'detail': 'Compte de charge inconnu.'},
                    status=status.HTTP_400_BAD_REQUEST)
        try:
            indem = services.valider_indemnite_chantier(
                indem, user=request.user, compte_charge=compte_charge)
        except DjangoValidationError as exc:
            return Response(
                {'detail': exc.messages[0] if exc.messages else str(exc)},
                status=status.HTTP_400_BAD_REQUEST)
        return Response(self.get_serializer(indem).data)

    @action(detail=True, methods=['post'])
    def rejeter(self, request, pk=None):
        """Rejette une indemnité soumise (soumise → rejetée) — FG136."""
        indem = self.get_object()  # scopée société par TenantMixin.
        try:
            indem = services.rejeter_indemnite_chantier(
                indem, motif_rejet=request.data.get('motif_rejet', '') or '',
                user=request.user)
        except DjangoValidationError as exc:
            return Response(
                {'detail': exc.messages[0] if exc.messages else str(exc)},
                status=status.HTTP_400_BAD_REQUEST)
        return Response(self.get_serializer(indem).data)

    @action(detail=True, methods=['post'])
    def rembourser(self, request, pk=None):
        """Rembourse l'indemnité validée et poste le paiement (FG136).

        Corps : ``{compte_tresorerie, date_remboursement?}``. Le compte payeur
        doit appartenir à la société. Refusé en période close. Idempotent.
        """
        indem = self.get_object()  # scopée société par TenantMixin.
        treso = CompteTresorerie.objects.filter(
            company=request.user.company,
            id=request.data.get('compte_tresorerie')).first()
        if treso is None:
            return Response(
                {'detail': 'Compte de trésorerie inconnu.'},
                status=status.HTTP_400_BAD_REQUEST)
        try:
            indem = services.rembourser_indemnite_chantier(
                indem, compte_tresorerie=treso,
                date_remboursement=request.data.get('date_remboursement')
                or None,
                user=request.user)
        except DjangoValidationError as exc:
            return Response(
                {'detail': exc.messages[0] if exc.messages else str(exc)},
                status=status.HTTP_400_BAD_REQUEST)
        return Response(self.get_serializer(indem).data)


# ── FG137 — Préparation de la déclaration de TVA ───────────────────────────

class DeclarationTVAViewSet(_ComptaBaseViewSet):
    """Préparation de la déclaration de TVA (FG137).

    Liste/consulte les déclarations préparées et expose deux actions :
    ``preparer`` (POST) calcule la TVA collectée − déductible sur une période
    depuis le grand livre et FIGE un snapshot ``DeclarationTVA`` (régime
    mensuel/trimestriel, méthode débit/encaissement, crédit antérieur), et
    ``export`` (GET) renvoie le détail en CSV. Société scopée, posée côté
    serveur ; Admin/Responsable uniquement. La création directe (POST sur la
    collection) passe par ``preparer`` afin que les montants soient toujours
    dérivés du GL (le corps ne peut jamais les imposer).
    """
    queryset = DeclarationTVA.objects.select_related('created_by').all()
    serializer_class = DeclarationTVASerializer
    filter_backends = [filters.SearchFilter, filters.OrderingFilter]
    search_fields = ['reference', 'libelle']
    ordering_fields = ['date_fin', 'date_debut', 'tva_a_declarer', 'id']

    def get_queryset(self):
        qs = super().get_queryset()
        params = self.request.query_params
        regime = params.get('regime')
        if regime:
            qs = qs.filter(regime=regime)
        statut = params.get('statut')
        if statut:
            qs = qs.filter(statut=statut)
        return qs

    def _preparer(self, request):
        """Valide le corps et fige la déclaration depuis le GL (FG137)."""
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        vd = serializer.validated_data
        declaration = services.preparer_declaration_tva(
            request.user.company,
            date_debut=vd['date_debut'],
            date_fin=vd['date_fin'],
            regime=vd.get('regime') or DeclarationTVA.Regime.MENSUEL,
            methode=vd.get('methode') or DeclarationTVA.Methode.DEBIT,
            credit_anterieur=vd.get('credit_anterieur') or 0,
            libelle=vd.get('libelle', '') or '',
            validees_seulement=request.query_params.get('validees') == '1',
            user=request.user)
        return declaration

    def create(self, request, *args, **kwargs):
        """POST sur la collection = préparation (montants dérivés du GL)."""
        try:
            declaration = self._preparer(request)
        except DjangoValidationError as exc:
            return Response(
                {'detail': exc.messages[0] if exc.messages else str(exc)},
                status=status.HTTP_400_BAD_REQUEST)
        return Response(
            self.get_serializer(declaration).data,
            status=status.HTTP_201_CREATED)

    @action(detail=False, methods=['post'])
    def preparer(self, request):
        """Prépare et fige une déclaration de TVA sur une période (FG137).

        Corps : ``{date_debut, date_fin, regime?, methode?, credit_anterieur?,
        libelle?}``. La TVA collectée/déductible et le montant à déclarer sont
        calculés depuis le grand livre côté serveur. Renvoie la déclaration figée.
        """
        try:
            declaration = self._preparer(request)
        except DjangoValidationError as exc:
            return Response(
                {'detail': exc.messages[0] if exc.messages else str(exc)},
                status=status.HTTP_400_BAD_REQUEST)
        return Response(
            self.get_serializer(declaration).data,
            status=status.HTTP_201_CREATED)

    @action(detail=True, methods=['get'])
    def export(self, request, pk=None):
        """Exporte la déclaration de TVA en CSV (FG137).

        Une ligne par poste (TVA collectée, TVA déductible, crédit antérieur,
        TVA à déclarer, crédit reportable) + l'en-tête de période/régime/méthode.
        Lecture seule, scopée société.
        """
        decl = self.get_object()  # scopée société par TenantMixin.
        buffer = io.StringIO()
        writer = csv.writer(buffer, delimiter=';')
        writer.writerow(['Déclaration de TVA', decl.reference or decl.id])
        writer.writerow(['Période', f'{decl.date_debut} → {decl.date_fin}'])
        writer.writerow(['Régime', decl.get_regime_display()])
        writer.writerow(['Méthode', decl.get_methode_display()])
        writer.writerow([])
        writer.writerow(['Poste', 'Montant'])
        writer.writerow(['TVA collectée', decl.tva_collectee])
        writer.writerow(['TVA déductible', decl.tva_deductible])
        writer.writerow(['Crédit de TVA antérieur', decl.credit_anterieur])
        writer.writerow(['TVA à déclarer', decl.tva_a_declarer])
        writer.writerow(['Crédit de TVA reportable', decl.credit_reportable])
        resp = HttpResponse(
            buffer.getvalue(), content_type='text/csv; charset=utf-8')
        resp['Content-Disposition'] = (
            f'attachment; filename="declaration_tva_'
            f'{decl.reference or decl.id}.csv"')
        return resp


class RetenueSourceViewSet(_ComptaBaseViewSet):
    """Retenue à la source (RAS) sur honoraires/prestations (FG139).

    Enregistre/consulte les retenues à la source et expose le bordereau de
    versement : ``bordereau`` (GET) regroupe les RAS d'une période par
    prestataire et donne le total à reverser au Trésor (``export=csv`` pour le
    CSV), ``export`` (GET, détail) liste les retenues de la période en CSV, et
    ``verser`` (POST) marque une retenue comme versée. La création POST calcule
    le montant retenu côté serveur (base × taux %) ; le corps ne peut jamais
    l'imposer. Société scopée, posée côté serveur ; Admin/Responsable uniquement.
    """
    queryset = RetenueSource.objects.select_related('created_by').all()
    serializer_class = RetenueSourceSerializer
    filter_backends = [filters.SearchFilter, filters.OrderingFilter]
    search_fields = ['reference', 'piece', 'tiers_nom', 'identifiant_fiscal']
    ordering_fields = ['date_piece', 'montant', 'base', 'id']

    def get_queryset(self):
        qs = super().get_queryset()
        params = self.request.query_params
        statut = params.get('statut')
        if statut:
            qs = qs.filter(statut=statut)
        type_prestation = params.get('type_prestation')
        if type_prestation:
            qs = qs.filter(type_prestation=type_prestation)
        date_debut = params.get('date_debut')
        if date_debut:
            qs = qs.filter(date_piece__gte=date_debut)
        date_fin = params.get('date_fin')
        if date_fin:
            qs = qs.filter(date_piece__lte=date_fin)
        return qs

    def create(self, request, *args, **kwargs):
        """POST = enregistre une RAS (montant retenu dérivé côté serveur)."""
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        vd = serializer.validated_data
        try:
            ras = services.enregistrer_retenue_source(
                request.user.company,
                date_piece=vd['date_piece'],
                base=vd.get('base') or 0,
                taux=vd.get('taux'),
                type_prestation=vd.get('type_prestation'),
                tiers_type=vd.get('tiers_type', '') or '',
                tiers_id=vd.get('tiers_id'),
                tiers_nom=vd.get('tiers_nom', '') or '',
                identifiant_fiscal=vd.get('identifiant_fiscal', '') or '',
                piece=vd.get('piece', '') or '',
                libelle=vd.get('libelle', '') or '',
                user=request.user)
        except DjangoValidationError as exc:
            return Response(
                {'detail': exc.messages[0] if exc.messages else str(exc)},
                status=status.HTTP_400_BAD_REQUEST)
        return Response(
            self.get_serializer(ras).data, status=status.HTTP_201_CREATED)

    @action(detail=True, methods=['post'])
    def verser(self, request, pk=None):
        """Marque la retenue comme versée au Trésor (FG139)."""
        ras = self.get_object()  # scopée société par TenantMixin.
        services.marquer_ras_versee(ras)
        return Response(self.get_serializer(ras).data)

    def _periode(self, request):
        params = request.query_params
        return {
            'date_debut': params.get('date_debut') or None,
            'date_fin': params.get('date_fin') or None,
            'statut': params.get('statut') or None,
        }

    @action(detail=False, methods=['get'])
    def bordereau(self, request):
        """Bordereau de versement de la RAS : totaux par prestataire (FG139).

        Regroupe les retenues de la période ``[date_debut ; date_fin]`` (bornées
        sur la date de pièce) par prestataire et donne le total à reverser au
        Trésor. Paramètres : ``date_debut`` / ``date_fin`` / ``statut`` et
        ``export=csv`` pour le CSV. Lecture seule, scopée société,
        Admin/Responsable.
        """
        periode = self._periode(request)
        data = selectors.bordereau_versement_ras(
            request.user.company, **periode)
        if request.query_params.get('export') == 'csv':
            return self._export_bordereau_csv(data)
        return Response(data)

    @staticmethod
    def _export_bordereau_csv(data):
        """Sérialise le bordereau de versement de la RAS (FG139) en CSV."""
        buffer = io.StringIO()
        writer = csv.writer(buffer, delimiter=';')
        writer.writerow(['Bordereau de versement — Retenue à la source'])
        writer.writerow(
            ['Période', f"{data['date_debut'] or ''} → {data['date_fin'] or ''}"])
        writer.writerow([])
        writer.writerow(
            ['Prestataire', 'Identifiant fiscal', 'Nb pièces', 'Base',
             'Montant retenu'])
        for ligne in data['lignes']:
            writer.writerow([
                ligne['tiers_nom'], ligne['identifiant_fiscal'],
                ligne['nb_pieces'], ligne['base'], ligne['montant']])
        writer.writerow([])
        writer.writerow(
            ['Totaux', '', data['totaux']['nb_pieces'],
             data['totaux']['base'], data['totaux']['montant']])
        writer.writerow(['Total à verser', '', '', '', data['total_a_verser']])
        resp = HttpResponse(
            buffer.getvalue(), content_type='text/csv; charset=utf-8')
        resp['Content-Disposition'] = (
            'attachment; filename="bordereau_versement_ras_'
            f"{data['date_debut'] or 'periode'}_{data['date_fin'] or ''}.csv\"")
        return resp

    @action(detail=False, methods=['get'])
    def export(self, request):
        """Exporte le détail des RAS d'une période en CSV (FG139).

        Une ligne par retenue (date, pièce, prestataire, IF, type, base, taux,
        montant retenu, net à payer). Paramètres : ``date_debut`` / ``date_fin``
        / ``statut``. Lecture seule, scopée société, Admin/Responsable.
        """
        periode = self._periode(request)
        data = selectors.retenues_source_periode(
            request.user.company, **periode)
        buffer = io.StringIO()
        writer = csv.writer(buffer, delimiter=';')
        writer.writerow(['Retenues à la source (détail)'])
        writer.writerow(
            ['Période', f"{data['date_debut'] or ''} → {data['date_fin'] or ''}"])
        writer.writerow([])
        writer.writerow(
            ['Date', 'Référence', 'Pièce', 'Prestataire', 'Identifiant fiscal',
             'Type', 'Base', 'Taux %', 'Montant retenu', 'Net à payer'])
        for ligne in data['lignes']:
            writer.writerow([
                ligne['date_piece'], ligne['reference'], ligne['piece'],
                ligne['tiers_nom'], ligne['identifiant_fiscal'],
                ligne['type_prestation'], ligne['base'], ligne['taux'],
                ligne['montant'], ligne['net_a_payer']])
        writer.writerow([])
        writer.writerow(
            ['Totaux', '', '', '', '', '', data['totaux']['base'], '',
             data['totaux']['montant'], data['totaux']['net']])
        resp = HttpResponse(
            buffer.getvalue(), content_type='text/csv; charset=utf-8')
        resp['Content-Disposition'] = (
            'attachment; filename="retenues_source_'
            f"{data['date_debut'] or 'periode'}_{data['date_fin'] or ''}.csv\"")
        return resp
