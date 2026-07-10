"""FG274-FG275 — ViewSets mise en service & recette IEC 62446.

``resultat`` (recette) et ``ecart_pmax_pct``/``defaut_detecte`` (I-V) sont
DÉRIVÉS côté serveur des essais/mesures (jamais lus du corps). Multi-tenancy :
``company`` forcée serveur (depuis le chantier/devis/recette liés, bornés à la
société de l'utilisateur). Querysets scopés. Aucun prix ; ne change aucun statut
de devis (RULE #4).
"""
from rest_framework.exceptions import ValidationError

from authentication.permissions import IsAnyRole, IsResponsableOrAdmin
from core.viewsets import CompanyScopedModelViewSet  # ARC5
from ..models import (
    CommissioningTest, IVCurveCapture, AsBuiltPack, AttestationConformite,
    TestPerformanceReception, AttestationRE)
from ..serializers_commissioning import (
    CommissioningTestSerializer, IVCurveCaptureSerializer,
    AsBuiltPackSerializer, AttestationConformiteSerializer,
    TestPerformanceReceptionSerializer, AttestationRESerializer)
from ..commissioning import (
    compute_commissioning_result, evaluate_iv_curve, compute_reception_pr,
    compute_co2_evite)

READ_ACTIONS = ['list', 'retrieve']


def _company_or_none(user):
    return getattr(user, 'company', None)


def _refresh_recette_result(recette):
    """Recalcule et persiste le résultat global d'une recette."""
    has_defect = recette.iv_curves.filter(defaut_detecte=True).exists()
    recette.resultat = compute_commissioning_result(
        isolement_ok=recette.isolement_ok,
        polarite_ok=recette.polarite_ok,
        continuite_terre_ok=recette.continuite_terre_ok,
        controle_onduleur_ok=recette.controle_onduleur_ok,
        has_defective_iv=has_defect)
    recette.save(update_fields=['resultat', 'updated_at'])


class CommissioningTestViewSet(CompanyScopedModelViewSet):
    """FG274 — CRUD fiche de recette ; résultat dérivé serveur.

    ARC5 — sweep TenantMixin : base transverse unique (idem pour les 6 viewsets
    de ce module). get_queryset / perform_create / perform_update /
    get_permissions SURCHARGENT la base (scoping direct sur `company`) : scoping
    et matrice 401/403/404 INCHANGÉS (règle #4 : aucun prix, aucun statut de
    devis touché)."""

    queryset = CommissioningTest.objects.select_related(
        'chantier', 'devis', 'created_by').prefetch_related(
        'iv_curves').all()
    serializer_class = CommissioningTestSerializer

    def get_permissions(self):
        if self.action in READ_ACTIONS:
            return [IsAnyRole()]
        return [IsResponsableOrAdmin()]

    def get_queryset(self):
        user = self.request.user
        qs = super().get_queryset()
        if getattr(user, 'company_id', None):
            qs = qs.filter(company=user.company)
        elif not user.is_superuser:
            return qs.none()
        chantier_id = self.request.query_params.get('chantier')
        if chantier_id:
            qs = qs.filter(chantier_id=chantier_id)
        devis_id = self.request.query_params.get('devis')
        if devis_id:
            qs = qs.filter(devis_id=devis_id)
        resultat = self.request.query_params.get('resultat')
        if resultat:
            qs = qs.filter(resultat=resultat)
        return qs

    def _resolve_company(self, validated):
        """Société depuis le chantier/devis lié, bornée à l'utilisateur."""
        user = self.request.user
        company = _company_or_none(user)
        chantier = validated.get('chantier')
        devis = validated.get('devis')
        for obj, field in ((chantier, 'chantier'), (devis, 'devis')):
            if obj is not None and company is not None \
                    and obj.company_id != company.id:
                raise ValidationError({field: 'Référence inconnue.'})
        if company is not None:
            return company
        # Superuser sans société : suivre la société d'un objet lié.
        if chantier is not None:
            return chantier.company
        if devis is not None:
            return devis.company
        raise ValidationError(
            {'company': "Aucune société : recette impossible."})

    def perform_create(self, serializer):
        company = self._resolve_company(serializer.validated_data)
        instance = serializer.save(
            company=company, created_by=self.request.user)
        _refresh_recette_result(instance)

    def perform_update(self, serializer):
        # Société inchangée si non fournie ; sinon re-résolue (tenant safe).
        validated = dict(serializer.validated_data)
        if 'chantier' not in validated:
            validated['chantier'] = serializer.instance.chantier
        if 'devis' not in validated:
            validated['devis'] = serializer.instance.devis
        company = self._resolve_company(validated)
        instance = serializer.save(company=company)
        _refresh_recette_result(instance)


class IVCurveCaptureViewSet(CompanyScopedModelViewSet):  # ARC5 (voir note ci-dessus)
    """FG275 — CRUD courbes I-V ; écart & défaut dérivés serveur."""

    queryset = IVCurveCapture.objects.select_related('recette').all()
    serializer_class = IVCurveCaptureSerializer

    def get_permissions(self):
        if self.action in READ_ACTIONS:
            return [IsAnyRole()]
        return [IsResponsableOrAdmin()]

    def get_queryset(self):
        user = self.request.user
        qs = super().get_queryset()
        if getattr(user, 'company_id', None):
            qs = qs.filter(company=user.company)
        elif not user.is_superuser:
            return qs.none()
        recette_id = self.request.query_params.get('recette')
        if recette_id:
            qs = qs.filter(recette_id=recette_id)
        defaut = self.request.query_params.get('defaut')
        if defaut in ('1', 'true', 'True'):
            qs = qs.filter(defaut_detecte=True)
        return qs

    def _resolve_company(self, recette):
        user = self.request.user
        company = _company_or_none(user)
        if recette is None:
            raise ValidationError({'recette': 'Recette requise.'})
        if company is not None and recette.company_id != company.id:
            raise ValidationError({'recette': 'Recette inconnue.'})
        return recette.company

    def _derive(self, serializer):
        ecart, defaut = evaluate_iv_curve(
            pmax_mesure_w=serializer.validated_data.get(
                'pmax_mesure_w',
                getattr(serializer.instance, 'pmax_mesure_w', None)),
            pmax_attendu_w=serializer.validated_data.get(
                'pmax_attendu_w',
                getattr(serializer.instance, 'pmax_attendu_w', None)))
        return ecart, defaut

    def perform_create(self, serializer):
        recette = serializer.validated_data.get('recette')
        company = self._resolve_company(recette)
        ecart, defaut = self._derive(serializer)
        serializer.save(company=company, ecart_pmax_pct=ecart,
                        defaut_detecte=defaut)
        _refresh_recette_result(recette)

    def perform_update(self, serializer):
        recette = serializer.validated_data.get(
            'recette', serializer.instance.recette)
        company = self._resolve_company(recette)
        ecart, defaut = self._derive(serializer)
        serializer.save(company=company, ecart_pmax_pct=ecart,
                        defaut_detecte=defaut)
        _refresh_recette_result(recette)

    def perform_destroy(self, instance):
        recette = instance.recette
        instance.delete()
        _refresh_recette_result(recette)


def _resolve_company_from_links(user, *objects):
    """Société depuis le 1er objet lié non nul, bornée à l'utilisateur.

    Chaque objet (chantier/devis/recette) fourni doit appartenir à la société de
    l'utilisateur ; sinon ValidationError. Renvoie la société de l'utilisateur,
    ou (superuser sans société) celle d'un objet lié. ValidationError si aucune.
    """
    company = _company_or_none(user)
    for obj in objects:
        if obj is not None and company is not None \
                and getattr(obj, 'company_id', None) != company.id:
            raise ValidationError({'detail': 'Référence inconnue.'})
    if company is not None:
        return company
    for obj in objects:
        if obj is not None and getattr(obj, 'company_id', None):
            return obj.company
    raise ValidationError({'company': 'Aucune société : opération impossible.'})


class AsBuiltPackViewSet(CompanyScopedModelViewSet):  # ARC5 (voir note ci-dessus)
    """FG276 — CRUD pack documentaire as-built ; ``company`` forcée serveur."""

    queryset = AsBuiltPack.objects.select_related(
        'chantier', 'devis', 'recette', 'created_by').all()
    serializer_class = AsBuiltPackSerializer

    def get_permissions(self):
        if self.action in READ_ACTIONS:
            return [IsAnyRole()]
        return [IsResponsableOrAdmin()]

    def get_queryset(self):
        user = self.request.user
        qs = super().get_queryset()
        if getattr(user, 'company_id', None):
            qs = qs.filter(company=user.company)
        elif not user.is_superuser:
            return qs.none()
        chantier_id = self.request.query_params.get('chantier')
        if chantier_id:
            qs = qs.filter(chantier_id=chantier_id)
        return qs

    def _company(self, validated, instance=None):
        chantier = validated.get(
            'chantier', getattr(instance, 'chantier', None))
        devis = validated.get('devis', getattr(instance, 'devis', None))
        recette = validated.get('recette', getattr(instance, 'recette', None))
        return _resolve_company_from_links(
            self.request.user, chantier, devis, recette)

    def perform_create(self, serializer):
        company = self._company(serializer.validated_data)
        serializer.save(company=company, created_by=self.request.user)

    def perform_update(self, serializer):
        company = self._company(
            serializer.validated_data, serializer.instance)
        serializer.save(company=company)


class AttestationConformiteViewSet(CompanyScopedModelViewSet):  # ARC5 (voir note ci-dessus)
    """FG277 — CRUD attestation de conformité électrique."""

    queryset = AttestationConformite.objects.select_related(
        'chantier', 'recette', 'created_by').all()
    serializer_class = AttestationConformiteSerializer

    def get_permissions(self):
        if self.action in READ_ACTIONS:
            return [IsAnyRole()]
        return [IsResponsableOrAdmin()]

    def get_queryset(self):
        user = self.request.user
        qs = super().get_queryset()
        if getattr(user, 'company_id', None):
            qs = qs.filter(company=user.company)
        elif not user.is_superuser:
            return qs.none()
        chantier_id = self.request.query_params.get('chantier')
        if chantier_id:
            qs = qs.filter(chantier_id=chantier_id)
        statut = self.request.query_params.get('statut')
        if statut:
            qs = qs.filter(statut=statut)
        return qs

    def _company(self, validated, instance=None):
        chantier = validated.get(
            'chantier', getattr(instance, 'chantier', None))
        recette = validated.get('recette', getattr(instance, 'recette', None))
        return _resolve_company_from_links(
            self.request.user, chantier, recette)

    def perform_create(self, serializer):
        company = self._company(serializer.validated_data)
        serializer.save(company=company, created_by=self.request.user)

    def perform_update(self, serializer):
        company = self._company(
            serializer.validated_data, serializer.instance)
        serializer.save(company=company)


class TestPerformanceReceptionViewSet(CompanyScopedModelViewSet):  # ARC5 (voir note ci-dessus)
    """FG278 — CRUD test PR de réception ; pr/ecart/verdict dérivés serveur."""

    queryset = TestPerformanceReception.objects.select_related(
        'chantier', 'recette', 'created_by').all()
    serializer_class = TestPerformanceReceptionSerializer

    def get_permissions(self):
        if self.action in READ_ACTIONS:
            return [IsAnyRole()]
        return [IsResponsableOrAdmin()]

    def get_queryset(self):
        user = self.request.user
        qs = super().get_queryset()
        if getattr(user, 'company_id', None):
            qs = qs.filter(company=user.company)
        elif not user.is_superuser:
            return qs.none()
        chantier_id = self.request.query_params.get('chantier')
        if chantier_id:
            qs = qs.filter(chantier_id=chantier_id)
        verdict = self.request.query_params.get('verdict')
        if verdict:
            qs = qs.filter(verdict=verdict)
        return qs

    def _company(self, validated, instance=None):
        chantier = validated.get(
            'chantier', getattr(instance, 'chantier', None))
        recette = validated.get('recette', getattr(instance, 'recette', None))
        return _resolve_company_from_links(
            self.request.user, chantier, recette)

    def _derive(self, serializer):
        v = serializer.validated_data
        inst = serializer.instance

        def _get(field):
            return v.get(field, getattr(inst, field, None))

        return compute_reception_pr(
            energie_mesuree_kwh=_get('energie_mesuree_kwh'),
            energie_attendue_kwh=_get('energie_attendue_kwh'),
            pr_mesure=_get('pr_mesure'),
            pr_attendu=_get('pr_attendu'),
            pr_seuil_acceptation=_get('pr_seuil_acceptation'))

    def perform_create(self, serializer):
        company = self._company(serializer.validated_data)
        pr_m, ecart, verdict = self._derive(serializer)
        serializer.save(company=company, created_by=self.request.user,
                        pr_mesure=pr_m, ecart_pct=ecart, verdict=verdict)

    def perform_update(self, serializer):
        company = self._company(
            serializer.validated_data, serializer.instance)
        pr_m, ecart, verdict = self._derive(serializer)
        serializer.save(company=company, pr_mesure=pr_m,
                        ecart_pct=ecart, verdict=verdict)


class AttestationREViewSet(CompanyScopedModelViewSet):  # ARC5 (voir note ci-dessus)
    """FG287 — CRUD attestation d'énergie renouvelable ; CO₂ dérivé serveur."""

    queryset = AttestationRE.objects.select_related(
        'chantier', 'created_by').all()
    serializer_class = AttestationRESerializer

    def get_permissions(self):
        if self.action in READ_ACTIONS:
            return [IsAnyRole()]
        return [IsResponsableOrAdmin()]

    def get_queryset(self):
        user = self.request.user
        qs = super().get_queryset()
        if getattr(user, 'company_id', None):
            qs = qs.filter(company=user.company)
        elif not user.is_superuser:
            return qs.none()
        chantier_id = self.request.query_params.get('chantier')
        if chantier_id:
            qs = qs.filter(chantier_id=chantier_id)
        statut = self.request.query_params.get('statut')
        if statut:
            qs = qs.filter(statut=statut)
        return qs

    def _company(self, validated, instance=None):
        chantier = validated.get(
            'chantier', getattr(instance, 'chantier', None))
        return _resolve_company_from_links(self.request.user, chantier)

    def _derive(self, serializer):
        energie = serializer.validated_data.get(
            'energie_kwh', getattr(serializer.instance, 'energie_kwh', None))
        return compute_co2_evite(energie_kwh=energie)

    def perform_create(self, serializer):
        company = self._company(serializer.validated_data)
        facteur, co2 = self._derive(serializer)
        serializer.save(company=company, created_by=self.request.user,
                        facteur_co2_kg_kwh=facteur, co2_evite_t=co2)

    def perform_update(self, serializer):
        company = self._company(
            serializer.validated_data, serializer.instance)
        facteur, co2 = self._derive(serializer)
        serializer.save(company=company, facteur_co2_kg_kwh=facteur,
                        co2_evite_t=co2)
