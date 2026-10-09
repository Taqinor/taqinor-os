"""N100(e) — registre de facturation de LICENCE (console fondateur).

Strictement côté ÉDITEUR : tous les endpoints exigent le superuser
(``IsSuperuserConsole``, la même garde que la console tenants SCA22). Aucun
tenant ne voit jamais sa facturation de licence par cette API — ce n'est pas
une surface client.

Frontière volontaire : ces factures n'ont RIEN à voir avec les factures métier
que le tenant émet à ses propres clients (``apps.ventes``). Elles vivent ici,
dans ``adminops``, précisément pour que les deux ne se mélangent jamais.

Aucune passerelle de paiement : « payée » est un pointage MANUEL du fondateur.
"""
from __future__ import annotations

import logging
from datetime import date

from django.http import HttpResponse
from django.utils import timezone
from drf_spectacular.types import OpenApiTypes
from drf_spectacular.utils import (
    OpenApiParameter, extend_schema, inline_serializer,
)
from rest_framework import serializers as drf_serializers
from rest_framework import status
from rest_framework.parsers import JSONParser
from rest_framework.response import Response
from rest_framework.views import APIView

from authentication.models import Company
from authentication.views_console import IsSuperuserConsole

from .models import FactureLicence
from .serializers import FactureLicenceSerializer

logger = logging.getLogger(__name__)


def _premier_jour(valeur):
    """Normalise une PÉRIODE en 1er du mois (``YYYY-MM`` ou ``YYYY-MM-DD``).

    Réservé à ``periode`` — une période de facturation est un mois entier. Ne
    JAMAIS l'utiliser pour une date réelle (``date_paiement``) : elle écraserait
    le jour. Voir ``_date_exacte``."""
    texte = (valeur or '').strip()
    if not texte:
        return None
    morceaux = texte.split('-')
    try:
        annee = int(morceaux[0])
        mois = int(morceaux[1]) if len(morceaux) > 1 else 1
        return date(annee, mois, 1)
    except (ValueError, IndexError):
        return None


def _date_exacte(valeur):
    """Date réelle ``YYYY-MM-DD`` — le JOUR est conservé tel quel."""
    texte = (valeur or '').strip()
    if not texte:
        return None
    try:
        annee, mois, jour = (int(p) for p in texte.split('-')[:3])
        return date(annee, mois, jour)
    except (ValueError, TypeError):
        return None


def _enregistrer_avec_reference(facture):
    """ATOT32 — numérote ET enregistre ``facture`` via
    ``core.numbering.create_with_reference`` (savepoint + nouvel essai sur
    collision de référence), jamais un ``next_reference`` nu suivi d'un
    ``save()`` : deux émissions concurrentes ne portent jamais le même numéro
    (garanti en base par la contrainte unique ``(company, reference)``)."""
    from core.numbering import create_with_reference

    def _save(reference):
        facture.reference = reference
        facture.save()
        return facture

    return create_with_reference(FactureLicence, 'LIC', facture.company, _save)


class FactureLicenceCreerSerializer(drf_serializers.Serializer):
    company = drf_serializers.IntegerField()
    periode = drf_serializers.CharField(help_text='AAAA-MM')
    plan_code = drf_serializers.CharField(required=False, max_length=40)
    montant_ht = drf_serializers.DecimalField(
        max_digits=12, decimal_places=2, required=False)
    tva = drf_serializers.DecimalField(
        max_digits=12, decimal_places=2, required=False)
    montant_ttc = drf_serializers.DecimalField(
        max_digits=12, decimal_places=2, required=False)
    notes = drf_serializers.CharField(required=False, allow_blank=True)
    statut = drf_serializers.CharField(required=False)


class FactureLicenceMarquerPayeeSerializer(drf_serializers.Serializer):
    date_paiement = drf_serializers.CharField(required=False)


class FactureLicenceListView(APIView):
    """GET — registre (filtrable par tenant) ; POST — nouvelle ligne."""

    permission_classes = [IsSuperuserConsole]
    serializer_class = FactureLicenceSerializer
    parser_classes = [JSONParser]

    def _queryset(self, request):
        qs = FactureLicence.objects.select_related('company')
        tenant = request.query_params.get('company')
        if tenant:
            qs = qs.filter(company_id=tenant)
        statut = request.query_params.get('statut')
        if statut:
            qs = qs.filter(statut=statut)
        return qs.order_by('-periode', '-id')

    @extend_schema(
        parameters=[
            OpenApiParameter('company', OpenApiTypes.INT, required=False),
            OpenApiParameter('statut', OpenApiTypes.STR, required=False),
        ],
        responses=inline_serializer('FacturesLicenceListe', {
            'results': FactureLicenceSerializer(many=True),
            'total_du_ttc': drf_serializers.DecimalField(
                max_digits=14, decimal_places=2),
        }))
    def get(self, request):
        factures = list(self._queryset(request))
        total_du = sum(
            f.montant_ttc for f in factures
            if f.statut != FactureLicence.Statut.PAYEE)
        return Response({
            'results': FactureLicenceSerializer(factures, many=True).data,
            'total_du_ttc': total_du,
        })

    @extend_schema(request=FactureLicenceCreerSerializer,
                   responses={201: FactureLicenceSerializer})
    def post(self, request):
        company = Company.objects.filter(
            pk=request.data.get('company')).first()
        if company is None:
            return Response({'detail': 'Société introuvable.'},
                            status=status.HTTP_404_NOT_FOUND)

        periode = _premier_jour(request.data.get('periode'))
        if periode is None:
            return Response(
                {'detail': 'Période invalide (format attendu : AAAA-MM).'},
                status=status.HTTP_400_BAD_REQUEST)

        facture = FactureLicence(
            company=company,
            periode=periode,
            plan_code=(request.data.get('plan_code') or _plan_du_tenant(company))[:40],
            montant_ht=request.data.get('montant_ht') or 0,
            tva=request.data.get('tva') or 0,
            montant_ttc=request.data.get('montant_ttc') or 0,
            notes=(request.data.get('notes') or ''),
        )
        statut = request.data.get('statut')
        if statut in dict(FactureLicence.Statut.choices):
            facture.statut = statut
        if facture.statut != FactureLicence.Statut.BROUILLON:
            facture.date_emission = timezone.localdate()
            _enregistrer_avec_reference(facture)
        else:
            facture.save()
        return Response(FactureLicenceSerializer(facture).data,
                        status=status.HTTP_201_CREATED)


class FactureLicenceMarquerPayeeView(APIView):
    """POST — pointage MANUEL de l'encaissement (idempotent)."""

    permission_classes = [IsSuperuserConsole]
    serializer_class = FactureLicenceSerializer
    parser_classes = [JSONParser]

    @extend_schema(request=FactureLicenceMarquerPayeeSerializer,
                   responses=FactureLicenceSerializer)
    def post(self, request, pk):
        facture = FactureLicence.objects.filter(pk=pk).first()
        if facture is None:
            return Response({'detail': 'Facture introuvable.'},
                            status=status.HTTP_404_NOT_FOUND)
        if facture.statut != FactureLicence.Statut.PAYEE:
            if facture.date_emission is None:
                facture.date_emission = timezone.localdate()
            facture.statut = FactureLicence.Statut.PAYEE
            facture.date_paiement = (
                _date_exacte(request.data.get('date_paiement'))
                or timezone.localdate())
            if facture.reference:
                facture.save()
            else:
                _enregistrer_avec_reference(facture)
        return Response(FactureLicenceSerializer(facture).data)


class FactureLicenceExportCsvView(APIView):
    """GET — export CSV du registre (fondateur uniquement)."""

    permission_classes = [IsSuperuserConsole]

    @extend_schema(
        parameters=[OpenApiParameter('company', OpenApiTypes.INT, required=False)],
        responses={(200, 'text/csv'): OpenApiTypes.STR})
    def get(self, request):
        qs = FactureLicence.objects.select_related('company').order_by(
            '-periode', '-id')
        tenant = request.query_params.get('company')
        if tenant:
            qs = qs.filter(company_id=tenant)

        reponse = HttpResponse(content_type='text/csv; charset=utf-8')
        reponse['Content-Disposition'] = (
            'attachment; filename="facturation-licences.csv"')
        # BOM UTF-8 : Excel (FR) ouvre le fichier avec les accents corrects.
        reponse.write('﻿')
        from apps.records.xlsx import EcrivainCsvNeutralise
        writer = EcrivainCsvNeutralise(reponse, delimiter=';')
        writer.writerow([
            'Référence', 'Société', 'Période', 'Plan', 'Montant HT', 'TVA',
            'Montant TTC', 'Statut', 'Date émission', 'Date paiement',
        ])
        for f in qs:
            writer.writerow([
                f.reference, f.company.nom if f.company else '',
                f.periode.strftime('%Y-%m') if f.periode else '',
                f.plan_code, f.montant_ht, f.tva, f.montant_ttc,
                f.get_statut_display(),
                f.date_emission or '', f.date_paiement or '',
            ])
        return reponse


def _plan_du_tenant(company):
    """Code de plan courant, lu derrière une garde d'import.

    Le modèle `PlanLicence` / `has_feature` appartient à une AUTRE lane : tant
    qu'il n'est pas fondu, on renvoie simplement une chaîne vide au lieu de
    hand-rouler un substitut local."""
    try:
        from apps.parametres.feature_flags import plan_code_for_company
        return plan_code_for_company(company) or ''
    except Exception:  # noqa: BLE001 — la lane plan n'est pas encore fondue
        return ''
