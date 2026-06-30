"""FG274-FG275 — ViewSets mise en service & recette IEC 62446.

``resultat`` (recette) et ``ecart_pmax_pct``/``defaut_detecte`` (I-V) sont
DÉRIVÉS côté serveur des essais/mesures (jamais lus du corps). Multi-tenancy :
``company`` forcée serveur (depuis le chantier/devis/recette liés, bornés à la
société de l'utilisateur). Querysets scopés. Aucun prix ; ne change aucun statut
de devis (RULE #4).
"""
from rest_framework import viewsets
from rest_framework.exceptions import ValidationError

from authentication.permissions import IsAnyRole, IsResponsableOrAdmin
from ..models import CommissioningTest, IVCurveCapture
from ..serializers_commissioning import (
    CommissioningTestSerializer, IVCurveCaptureSerializer)
from ..commissioning import (
    compute_commissioning_result, evaluate_iv_curve)

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


class CommissioningTestViewSet(viewsets.ModelViewSet):
    """FG274 — CRUD fiche de recette ; résultat dérivé serveur."""

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


class IVCurveCaptureViewSet(viewsets.ModelViewSet):
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
