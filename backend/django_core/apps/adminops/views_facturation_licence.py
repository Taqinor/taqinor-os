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

import csv
import logging
from datetime import date

from django.http import HttpResponse
from django.utils import timezone
from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import APIView

from authentication.models import Company
from authentication.views_console import IsSuperuserConsole

from .models import FactureLicence
from .serializers import FactureLicenceSerializer

logger = logging.getLogger(__name__)


def _premier_jour(valeur):
    """Normalise une période en 1er du mois (``YYYY-MM`` ou ``YYYY-MM-DD``)."""
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


def _reference_licence(company):
    """Référence via le socle de numérotation (JAMAIS un count()+1)."""
    from core.numbering import next_reference
    return next_reference(FactureLicence, 'LIC', company)


class FactureLicenceListView(APIView):
    """GET — registre (filtrable par tenant) ; POST — nouvelle ligne."""

    permission_classes = [IsSuperuserConsole]
    serializer_class = FactureLicenceSerializer

    def _queryset(self, request):
        qs = FactureLicence.objects.select_related('company')
        tenant = request.query_params.get('company')
        if tenant:
            qs = qs.filter(company_id=tenant)
        statut = request.query_params.get('statut')
        if statut:
            qs = qs.filter(statut=statut)
        return qs.order_by('-periode', '-id')

    def get(self, request):
        factures = list(self._queryset(request))
        total_du = sum(
            f.montant_ttc for f in factures
            if f.statut != FactureLicence.Statut.PAYEE)
        return Response({
            'results': FactureLicenceSerializer(factures, many=True).data,
            'total_du_ttc': total_du,
        })

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
            facture.reference = _reference_licence(company)
            facture.date_emission = timezone.localdate()
        facture.save()
        return Response(FactureLicenceSerializer(facture).data,
                        status=status.HTTP_201_CREATED)


class FactureLicenceMarquerPayeeView(APIView):
    """POST — pointage MANUEL de l'encaissement (idempotent)."""

    permission_classes = [IsSuperuserConsole]
    serializer_class = FactureLicenceSerializer

    def post(self, request, pk):
        facture = FactureLicence.objects.filter(pk=pk).first()
        if facture is None:
            return Response({'detail': 'Facture introuvable.'},
                            status=status.HTTP_404_NOT_FOUND)
        if facture.statut != FactureLicence.Statut.PAYEE:
            if not facture.reference:
                facture.reference = _reference_licence(facture.company)
            if facture.date_emission is None:
                facture.date_emission = timezone.localdate()
            facture.statut = FactureLicence.Statut.PAYEE
            facture.date_paiement = (
                _premier_jour(request.data.get('date_paiement'))
                or timezone.localdate())
            facture.save()
        return Response(FactureLicenceSerializer(facture).data)


class FactureLicenceExportCsvView(APIView):
    """GET — export CSV du registre (fondateur uniquement)."""

    permission_classes = [IsSuperuserConsole]

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
        writer = csv.writer(reponse, delimiter=';')
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
