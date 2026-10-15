"""VNT100 — actions de lot sur les factures (indicateurs, consolidation,
actions groupées) : actions de ``FactureViewSet`` portées par
``FactureLotActionsMixin``, déplacées telles quelles depuis
``views/facture.py``. Le logger garde le nom ``apps.ventes.views.facture``.
Aucune route dans ``urls.py`` : le routeur les découvre sur le viewset.
"""
import logging

from drf_spectacular.utils import extend_schema, inline_serializer
from rest_framework import serializers as drf_serializers
from rest_framework import status
from rest_framework.decorators import action
from rest_framework.exceptions import ValidationError
from rest_framework.response import Response

from authentication.permissions import IsAnyRole, IsResponsableOrAdmin
from . import openapi_docs as D
from ..models import Facture
from ..serializers_facturation import FactureSerializer

logger = logging.getLogger('apps.ventes.views.facture')

#: Refus de ``consolider_factures`` qui signifie « ressource introuvable ».
_DEVIS_INTROUVABLES = 'Un ou plusieurs devis introuvables.'


def _statut_refus_consolidation(detail):
    """404 pour des devis inconnus de la société ; les autres refus (client
    différent, devis non accepté ou déjà facturé) sont des refus d'ÉTAT, 409
    — la consolidation est l'une des quatre PORTES de facturation, dont les
    refus partagent un seul statut (ATOT, VNT65 ; CI #997 fuzz : plus 400)."""
    motif = detail.get('devis_ids') if isinstance(detail, dict) else None
    if isinstance(motif, (list, tuple)):
        motif = motif[0] if motif else None
    if str(motif or '') == _DEVIS_INTROUVABLES:
        return status.HTTP_404_NOT_FOUND
    return status.HTTP_409_CONFLICT


class FactureLotActionsMixin:
    """Les actions qui portent sur plusieurs factures à la fois."""

    @extend_schema(responses=inline_serializer('FacturesKpis', {
        'mois': drf_serializers.CharField(),
        'mois_precedent': drf_serializers.CharField(),
        'encaisse_mois': drf_serializers.CharField(),
        'encaisse_mois_precedent': drf_serializers.CharField(),
        'total_du': drf_serializers.CharField(),
        'nb_impayees': drf_serializers.IntegerField(),
        'total_en_retard': drf_serializers.CharField(),
        'nb_en_retard': drf_serializers.IntegerField(),
        'total_a_echoir_7j': drf_serializers.CharField(),
    }))
    @action(detail=False, methods=['get'], url_path='kpis',
            permission_classes=[IsAnyRole])
    def kpis(self, request):
        """AUD157 (FAC-13) — LES KPI MONÉTAIRES DE L'ÉCRAN FACTURES, calculés
        par le serveur.

        « Encaissé ce mois » était sommé côté écran sur `p.montant` SANS
        filtrer `p.statut` : l'écran comptait des chèques revenus impayés, avec
        une définition différente de `Facture.montant_paye`. Un seul
        propriétaire désormais : `selectors.kpis_factures`, sur le queryset
        DÉJÀ scopé société + portée de visibilité de ce viewset.

        Contrat PACT10 : `apps/ventes/contract_samples/factures_kpis.json`.
        """
        from ..selectors import kpis_factures
        return Response(kpis_factures(self.filter_queryset(
            self.get_queryset())))

    @extend_schema(request=D.ConsoliderRequest,
                   responses={201: FactureSerializer},
                   extensions=D.CORPS_DEVIS_IDS_UNIQUES)
    @action(detail=False, methods=['post'], url_path='consolider',
            permission_classes=[IsResponsableOrAdmin])
    def consolider(self, request):
        """XFAC11 — crée UNE facture consolidée à partir de plusieurs devis
        acceptés du MÊME client. Body : ``{devis_ids: [...]}``."""
        from ..services import consolider_factures

        # CI #997 fuzz — corps validé par le sérialiseur PUBLIÉ (ids entiers
        # JSON ≥ 1, au moins deux) : ``"5"`` ou ``5.0`` étaient relus en
        # silence par ``int()``.
        from ..utils.corps import valider_corps
        devis_ids = valider_corps(request, D.ConsoliderRequest)['devis_ids']
        # ENF11 — ids publiés uniques et positifs : un doublon (consolidait
        # deux fois le même devis) ou un id < 1 est une erreur d'ENTRÉE.
        if len(set(devis_ids)) != len(devis_ids) or any(
                i < 1 for i in devis_ids):
            return Response(
                {'devis_ids': 'Identifiants de devis distincts et '
                              'positifs attendus.'},
                status=status.HTTP_400_BAD_REQUEST)
        try:
            facture = consolider_factures(
                company=request.user.company, devis_ids=devis_ids,
                user=request.user, created_by=request.user,
            )
        except ValidationError as exc:
            # ENF11 — devis inconnus de la société : 404 (un id inconnu
            # n'est pas une donnée invalide).
            return Response(exc.detail, status=_statut_refus_consolidation(
                exc.detail))
        return Response(
            FactureSerializer(facture).data, status=status.HTTP_201_CREATED)

    @extend_schema(request=D.BulkRequest, responses=D.BulkResponse)
    @action(detail=False, methods=['post'], url_path='bulk',
            permission_classes=[IsResponsableOrAdmin])
    def bulk(self, request):
        """FG43 — opérations en masse sur les factures.

        Body :
          - ``action`` ∈ {emettre, relancer, envoyer-email, generer-pdf}
          - ``ids``    : liste d'ids de factures (toutes scopées à la société)

        Renvoie un dict par id : ``{id: {ok: bool, detail: str}}``.
        Les erreurs par facture n'interrompent pas le batch.
        """
        request.user.company
        donnees = request.data if isinstance(request.data, dict) else {}
        action_brute = donnees.get('action')
        # ENF11 — une action qui n'est pas un texte est invalide (jamais un 500).
        action_name = action_brute.strip() if isinstance(action_brute, str) else ''
        ids = donnees.get('ids') or []

        VALID_ACTIONS = {'emettre', 'relancer', 'envoyer-email', 'generer-pdf'}
        if action_name not in VALID_ACTIONS:
            return Response(
                {'detail': (
                    f'Action invalide. Valeurs acceptées : '
                    f'{", ".join(sorted(VALID_ACTIONS))}.'
                )},
                status=status.HTTP_400_BAD_REQUEST,
            )
        if not ids or not isinstance(ids, list):
            return Response(
                {'detail': 'La liste `ids` est requise et doit être non vide.'},
                status=status.HTTP_400_BAD_REQUEST,
            )
        # Borner aux factures de la société (scoping multi-tenant). AFAC55
        # (C-AFAC-048) — ET à la portée du rôle (`get_queryset` : créées par
        # soi / l'équipe) : un id invisible répond « Introuvable. ».
        # ENF11 — le schéma déclare des ids ENTIERS : tout autre élément
        # (texte, objet, booléen) est refusé en 400 avant toute lecture.
        if any(type(brut) is not int for brut in ids):
            return Response({'detail': "ids : liste d'entiers attendue."},
                            status=status.HTTP_400_BAD_REQUEST)
        factures_by_id = {f.id: f for f in self.get_queryset().filter(
            id__in=[i for i in ids if abs(i) < 2 ** 31])}

        results = {}
        for fid_int in ids:
            facture = factures_by_id.get(fid_int)
            if facture is None:
                results[fid_int] = {'ok': False, 'detail': 'Introuvable.'}
                continue
            try:
                if action_name == 'emettre':
                    if facture.statut != Facture.Statut.BROUILLON:
                        results[fid_int] = {
                            'ok': False,
                            'detail': (
                                f'Statut {facture.get_statut_display()} : '
                                'seule une facture brouillon peut être émise.'
                            )}
                    elif not facture.lignes.exists() and not facture.libelle:
                        results[fid_int] = {
                            'ok': False,
                            'detail': 'La facture doit avoir au moins une ligne.'}
                    else:
                        # AUD101 — le bulk passe par LE service unique : il
                        # posait EMISE en silence, sans verrou de période,
                        # sans workflow de revue XFAC18, sans dérivation
                        # d'échéance et sans `facture_emise` (donc sans
                        # écriture au grand livre).
                        from ..domain.facturation_ops import emettre_facture
                        emettre_facture(
                            facture, user=request.user, source='bulk')
                        results[fid_int] = {
                            'ok': True,
                            'detail': 'Émise.',
                            'reference': facture.reference}

                elif action_name == 'relancer':
                    # AFAC46 — LE prédicat partagé (`facture_relancable`) et
                    # LE prochain niveau de la cadence (jamais `niveau=NULL`).
                    from ..recouvrement import (
                        ensure_default_followup_levels, facture_relancable,
                    )
                    relancable, motif_refus = facture_relancable(facture)
                    if not relancable:
                        results[fid_int] = {'ok': False, 'detail': motif_refus}
                    else:
                        from ..domain.recouvrement import prochain_niveau
                        from ..models import RelanceLog
                        ensure_default_followup_levels(facture.company)
                        lvl, _tous = prochain_niveau(facture)
                        RelanceLog.objects.create(
                            company=facture.company, facture=facture,
                            niveau=lvl.ordre if lvl is not None else None,
                            niveau_nom=lvl.nom if lvl is not None else '',
                            note='Relance en masse', created_by=request.user)
                        results[fid_int] = {
                            'ok': True,
                            'detail': 'Relance consignée.',
                            'reference': facture.reference}

                elif action_name == 'envoyer-email':
                    from ..email_service import send_document_email
                    from ..models import EmailLog
                    log = send_document_email(
                        facture, user=request.user, attach_pdf=True)
                    if log.statut == EmailLog.Statut.ECHEC:
                        results[fid_int] = {
                            'ok': False,
                            'detail': log.erreur or 'Envoi impossible.'}
                    else:
                        results[fid_int] = {
                            'ok': True,
                            'detail': f'Email envoyé à {log.to_email}.',
                            'reference': facture.reference}

                elif action_name == 'generer-pdf':
                    from ..tasks import task_generate_facture_pdf
                    task = task_generate_facture_pdf.delay(facture.id)
                    results[fid_int] = {
                        'ok': True,
                        'detail': 'Génération PDF lancée.',
                        'task_id': task.id,
                        'reference': facture.reference}

            except Exception as exc:  # noqa: BLE001 — batch: no single failure kills all
                logger.warning("facture.FactureViewSet.bulk : erreur ignorée (mode dégradé)", exc_info=True)
                results[fid_int] = {'ok': False, 'detail': str(exc)}

        return Response(results)
