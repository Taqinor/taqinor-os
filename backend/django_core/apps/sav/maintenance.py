"""T16 — service : génération à la lecture des tickets SAV préventifs dus.

Aucun planificateur : on matérialise les visites dues quand l'utilisateur
consulte la liste « à venir » / déclenche la génération. Idempotent — on avance
`derniere_visite` à la date de la visite générée pour ne pas dupliquer.

FG88 — Planification de tournée maintenance préventive. Les visites préventives
matérialisées (tickets PREVENTIF ouverts) restent sans date ni groupage bien
que le GPS du chantier existe. On expose la file des visites DUES avec leur GPS
(triée par proximité, haversine — aucun service de routage externe) et une
action de planification BULK posant date_tournee + technicien sur un lot de
tickets, scopée société côté serveur.
"""
from datetime import date as _date
from math import asin, cos, radians, sin, sqrt

from django.contrib.auth import get_user_model
from django.http import HttpResponse
from django.utils import timezone
from rest_framework import status
from rest_framework.decorators import action
from rest_framework.exceptions import ValidationError
from rest_framework.response import Response

from authentication.permissions import IsAnyRole, IsResponsableOrAdmin
from core.viewsets import CompanyScopedModelViewSet
from apps.ventes.utils.references import create_with_reference
from .models import ContratMaintenance, Ticket
from .pdf import rapport_maintenance_pdf
from .serializers_maintenance import ContratMaintenanceSerializer


def _haversine_km(lat1, lng1, lat2, lng2):
    """Distance en kilomètres entre deux points GPS (haversine). Renvoie None si
    une coordonnée manque. Math pure — aucun service externe (FG88)."""
    if None in (lat1, lng1, lat2, lng2):
        return None
    try:
        lat1, lng1, lat2, lng2 = float(lat1), float(lng1), float(lat2), float(lng2)
    except (TypeError, ValueError):
        return None
    r = 6371.0
    dlat = radians(lat2 - lat1)
    dlng = radians(lng2 - lng1)
    a = (sin(dlat / 2) ** 2
         + cos(radians(lat1)) * cos(radians(lat2)) * sin(dlng / 2) ** 2)
    return round(2 * r * asin(sqrt(a)), 3)


def tournee_preventive(company, origin_lat=None, origin_lng=None):
    """FG88 — File des visites préventives DUES, enrichie du GPS du chantier et
    triée par proximité (haversine) depuis un point d'origine optionnel.

    Une « visite due » = un ticket PREVENTIF ouvert (NOUVEAU/PLANIFIE/EN_COURS),
    non annulé, de la société. Le GPS est lu via le sélecteur installations
    (jamais un import direct du modèle). Sans point d'origine, l'origine est le
    premier chantier doté d'un GPS (tri relatif : on regroupe les voisins).
    Les tickets sans GPS sont placés en fin de liste (distance None).
    Renvoie une liste de dicts plats (jamais l'instance ORM).
    """
    from apps.installations.selectors import installation_gps_map

    tickets = list(
        Ticket.objects
        .filter(company=company, type=Ticket.Type.PREVENTIF,
                statut__in=Ticket.OPEN_STATUTS, annule=False)
        .select_related('client', 'installation', 'technicien_responsable')
        .order_by('date_ouverture', 'id'))

    gps = installation_gps_map(
        [t.installation_id for t in tickets if t.installation_id])

    # Point d'origine : explicite, sinon le premier chantier géolocalisé.
    if origin_lat is None or origin_lng is None:
        for t in tickets:
            coord = gps.get(t.installation_id)
            if coord and coord[0] is not None and coord[1] is not None:
                origin_lat, origin_lng = coord
                break

    rows = []
    for t in tickets:
        coord = gps.get(t.installation_id) or (None, None)
        lat, lng = coord
        distance = _haversine_km(origin_lat, origin_lng, lat, lng)
        rows.append({
            'id': t.id,
            'reference': t.reference,
            'statut': t.statut,
            'client_id': t.client_id,
            'client_nom': getattr(t.client, 'nom', None),
            'installation_id': t.installation_id,
            'date_ouverture': (t.date_ouverture.isoformat()
                               if t.date_ouverture else None),
            'date_tournee': (t.date_tournee.isoformat()
                             if t.date_tournee else None),
            'technicien_id': t.technicien_responsable_id,
            'technicien': getattr(t.technicien_responsable, 'username', None),
            'gps_lat': str(lat) if lat is not None else None,
            'gps_lng': str(lng) if lng is not None else None,
            'distance_km': distance,
        })

    # Tri par proximité : les chantiers sans distance (GPS manquant) en fin.
    rows.sort(key=lambda r: (r['distance_km'] is None,
                             r['distance_km'] if r['distance_km'] is not None
                             else 0.0))
    return rows


def planifier_tournee(company, ticket_ids, date_tournee, technicien_id=None):
    """FG88 — Affecte EN LOT une date de tournée (et un technicien optionnel) à
    un ensemble de tickets préventifs de la société.

    Tenant safety : seuls les tickets de `company` sont touchés (les ids
    étrangers sont ignorés silencieusement), et le technicien doit appartenir à
    la même société. Pose date_tournee + technicien_responsable et passe le
    ticket en PLANIFIE s'il était encore NOUVEAU. Renvoie le nombre mis à jour.
    """
    technicien = None
    if technicien_id is not None:
        User = get_user_model()
        technicien = User.objects.filter(
            id=technicien_id, company=company).first()
        if technicien is None:
            raise ValidationError({'technicien': 'Technicien inconnu.'})

    qs = Ticket.objects.filter(
        company=company, id__in=ticket_ids, type=Ticket.Type.PREVENTIF,
        annule=False)
    updated = 0
    for ticket in qs:
        ticket.date_tournee = date_tournee
        fields = ['date_tournee']
        if technicien is not None:
            ticket.technicien_responsable = technicien
            fields.append('technicien_responsable')
        if ticket.statut == Ticket.Statut.NOUVEAU:
            ticket.statut = Ticket.Statut.PLANIFIE
            fields.append('statut')
        ticket.save(update_fields=fields)
        updated += 1
    return updated


def generer_visites_dues(company, user, avance_jours=0):
    """Crée un ticket SAV préventif pour chaque contrat actif dont la visite est
    due, et avance la date de dernière visite. Renvoie le nombre généré.

    YSERV5 — ``avance_jours`` (0 par défaut, comportement historique
    inchangé) décale la comparaison « dû » vers le futur : une visite dont
    l'échéance tombe dans les ``avance_jours`` prochains jours est
    matérialisée dès aujourd'hui (utilisé par la tâche Celery quotidienne
    opt-in, jamais par le bouton manuel qui garde ``avance_jours=0``)."""
    from datetime import timedelta

    horizon = timezone.localdate() + timedelta(days=avance_jours or 0)
    genere = 0
    for contrat in ContratMaintenance.objects.filter(company=company, actif=True):
        if not contrat.is_due(today=horizon):
            continue
        due = contrat.prochaine_visite()

        def _save(ref, c=contrat, d=due):
            return Ticket.objects.create(
                reference=ref, company=company, client=c.client,
                installation=c.installation, type=Ticket.Type.PREVENTIF,
                statut=Ticket.Statut.NOUVEAU, date_ouverture=d,
                description=f'Visite de maintenance préventive (contrat #{c.pk}).',
                created_by=user)

        create_with_reference(Ticket, 'SAV', company, _save)
        contrat.derniere_visite = due
        contrat.save(update_fields=['derniere_visite'])
        genere += 1
    return genere


class ContratMaintenanceViewSet(CompanyScopedModelViewSet):
    """Contrats de maintenance (T16). Lecture tout rôle, écriture responsable/
    admin. ?due=1 → seulement les contrats dont la visite est due."""
    queryset = ContratMaintenance.objects.select_related(
        'client', 'installation').all()
    serializer_class = ContratMaintenanceSerializer

    def get_permissions(self):
        if self.action in ('list', 'retrieve', 'a_venir', 'tournee'):
            return [IsAnyRole()]
        return [IsResponsableOrAdmin()]

    def _check_tenant(self, serializer):
        """Tenant safety : le client et le chantier ciblés (FK inscriptibles)
        doivent appartenir à la société du user — sinon un contrat lierait les
        enregistrements d'une autre société (et la visite/PDF générés
        fuiteraient le chantier étranger)."""
        from rest_framework.exceptions import ValidationError
        company = self.request.user.company
        cid = getattr(company, 'id', None)
        client = serializer.validated_data.get('client')
        installation = serializer.validated_data.get('installation')
        if client is not None and client.company_id != cid:
            raise ValidationError({'client': 'Client inconnu.'})
        if installation is not None and installation.company_id != cid:
            raise ValidationError({'installation': 'Chantier inconnu.'})

    def perform_create(self, serializer):
        self._check_tenant(serializer)
        serializer.save(company=self.request.user.company)

    def perform_update(self, serializer):
        self._check_tenant(serializer)
        serializer.save()

    def get_queryset(self):
        qs = super().get_queryset()
        if self.request.query_params.get('due') in ('1', 'true'):
            ids = [c.id for c in qs if c.is_due()]
            qs = qs.filter(id__in=ids)
        return qs

    @action(detail=False, methods=['post'], url_path='generer-dus',
            permission_classes=[IsResponsableOrAdmin])
    def generer_dus(self, request):
        """Matérialise (à la demande, sans planificateur) les tickets préventifs
        des contrats dont la visite est due."""
        n = generer_visites_dues(request.user.company, request.user)
        return Response({'ok': True, 'tickets_generes': n},
                        status=status.HTTP_200_OK)

    @action(detail=False, methods=['get'], url_path='tournee',
            permission_classes=[IsAnyRole])
    def tournee(self, request):
        """FG88 — File des visites préventives DUES à planifier.

        GET /sav/contrats-maintenance/tournee/[?lat=..&lng=..]

        Renvoie les tickets préventifs ouverts de la société avec le GPS du
        chantier, triés par proximité (haversine) depuis le point d'origine
        fourni (?lat/?lng) ou, à défaut, le premier chantier géolocalisé. Aucun
        service de routage externe."""
        def _coord(name):
            raw = (request.query_params.get(name) or '').strip()
            if not raw:
                return None
            try:
                return float(raw)
            except ValueError:
                return None

        rows = tournee_preventive(
            request.user.company, _coord('lat'), _coord('lng'))
        return Response({'count': len(rows), 'results': rows},
                        status=status.HTTP_200_OK)

    @action(detail=False, methods=['post'], url_path='planifier-tournee',
            permission_classes=[IsResponsableOrAdmin])
    def planifier_tournee(self, request):
        """FG88 — Affecte EN LOT date + technicien à un lot de visites.

        POST /sav/contrats-maintenance/planifier-tournee/
        body: {ticket_ids: [int], date_tournee: "AAAA-MM-JJ",
               technicien_id: int|null}

        Pose date_tournee (+ technicien optionnel) sur les tickets préventifs
        de la société et passe NOUVEAU → PLANIFIE. La société n'est jamais lue
        du corps : seuls les tickets de l'utilisateur sont touchés."""
        ticket_ids = request.data.get('ticket_ids') or []
        if not isinstance(ticket_ids, list) or not ticket_ids:
            return Response({'ok': False, 'detail': 'ticket_ids requis.'},
                            status=status.HTTP_400_BAD_REQUEST)
        raw_date = (request.data.get('date_tournee') or '').strip()
        try:
            date_tournee = _date.fromisoformat(raw_date)
        except (ValueError, TypeError):
            return Response(
                {'ok': False, 'detail': 'date_tournee invalide (AAAA-MM-JJ).'},
                status=status.HTTP_400_BAD_REQUEST)
        technicien_id = request.data.get('technicien_id')
        try:
            n = planifier_tournee(
                request.user.company, ticket_ids, date_tournee, technicien_id)
        except ValidationError as exc:
            return Response({'ok': False, 'detail': exc.detail},
                            status=status.HTTP_400_BAD_REQUEST)
        return Response({'ok': True, 'tickets_planifies': n},
                        status=status.HTTP_200_OK)

    @action(detail=True, methods=['post'], url_path='facturer',
            permission_classes=[IsResponsableOrAdmin])
    def facturer(self, request, pk=None):
        """FG40 — Émet une facture de maintenance récurrente pour ce contrat.

        POST /sav/contrats-maintenance/{id}/facturer/

        Crée une Facture (statut=EMISE) via ventes.services.creer_facture_contrat
        et avance `derniere_facturation`. La facturation doit être activée
        (`facturation_active=True`) et un prix doit être renseigné sur le contrat.

        XCTR5 — chaque tentative (succès/échec) est journalisée dans le journal
        de facturation récurrente de ``apps.contrats`` (source_type=
        ``sav_maintenance``) : best-effort, une erreur de journalisation ne
        bloque JAMAIS la facturation elle-même.

        Réponse 201 : {ok: true, facture_reference: str, facture_id: int}
        """
        from django.utils import timezone

        contrat = self.get_object()
        periode = timezone.localdate().strftime('%Y-%m')
        try:
            from apps.ventes.services import creer_facture_contrat
            facture = creer_facture_contrat(
                contrat=contrat,
                user=request.user,
                company=request.user.company,
            )
        except ValueError as exc:
            self._journaliser_cycle_best_effort(
                request.user.company, contrat.pk, periode,
                statut_echec=True, motif=str(exc))
            return Response({'ok': False, 'detail': str(exc)},
                            status=status.HTTP_400_BAD_REQUEST)
        except Exception:
            import logging
            logging.getLogger(__name__).warning(
                'facturer: erreur inattendue (contrat #%s)', pk, exc_info=True)
            self._journaliser_cycle_best_effort(
                request.user.company, contrat.pk, periode,
                statut_echec=True, motif='Erreur inattendue lors de la facturation.')
            return Response(
                {'ok': False, 'detail': 'Erreur inattendue lors de la facturation.'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR)
        self._journaliser_cycle_best_effort(
            request.user.company, contrat.pk, periode,
            statut_echec=False, facture_id=facture.id)
        return Response(
            {
                'ok': True,
                'facture_reference': facture.reference,
                'facture_id': facture.id,
            },
            status=status.HTTP_201_CREATED)

    @staticmethod
    def _journaliser_cycle_best_effort(company, contrat_id, periode, *,
                                       statut_echec, motif='',
                                       facture_id=None):
        """Journalise UN cycle de facturation SAV dans le journal contrats — XCTR5.

        Frontière cross-app (CLAUDE.md) : appelle EXCLUSIVEMENT
        ``apps.contrats.services`` (jamais ses ``models``/``views``), import
        FONCTION-LOCAL pour éviter tout cycle au chargement. BEST-EFFORT : une
        erreur de journalisation (garde anti-doublon incluse) ne doit JAMAIS
        remonter — la facturation SAV elle-même est déjà terminée.
        """
        try:
            from apps.contrats import services as contrats_services
            from apps.contrats.models import CycleFacturationLog

            statut = (
                CycleFacturationLog.Statut.ECHEC if statut_echec
                else CycleFacturationLog.Statut.GENERE)
            contrats_services.enregistrer_cycle(
                company,
                source_type=CycleFacturationLog.SourceType.SAV_MAINTENANCE,
                source_id=contrat_id,
                periode=periode,
                statut=statut,
                motif=motif,
                facture_id=facture_id,
            )
        except Exception:  # pragma: no cover - défensif (best-effort)
            pass

    @action(detail=True, methods=['get'], url_path='rapport-pdf',
            permission_classes=[IsResponsableOrAdmin])
    def rapport_pdf(self, request, pk=None):
        """N47 — rapport court de visite de maintenance (PDF, client-facing).

        Sans prix d'achat. ?date=AAAA-MM-JJ pour la date de visite (défaut :
        dernière visite enregistrée)."""
        contrat = self.get_object()
        raw = (request.query_params.get('date') or '').strip()
        try:
            visite = _date.fromisoformat(raw) if raw else None
        except ValueError:
            visite = None
        pdf_bytes = rapport_maintenance_pdf(contrat, visite)
        resp = HttpResponse(pdf_bytes, content_type='application/pdf')
        resp['Content-Disposition'] = (
            f'attachment; filename="maintenance-contrat-{contrat.pk}.pdf"')
        return resp

    @action(detail=True, methods=['get'], url_path='rentabilite',
            permission_classes=[IsResponsableOrAdmin])
    def rentabilite(self, request, pk=None):
        """XSAV18 — P&L de CE contrat (revenu FG40 vs coût tickets liés).

        Admin-only (`prix_achat_voir`) — jamais client-facing, jamais dans un
        PDF. 403 explicite sans la permission (pas de champ silencieusement
        absent)."""
        if not request.user.can_view_buy_prices:
            return Response(
                {'detail': 'Coût interne réservé (permission prix_achat_voir).'},
                status=status.HTTP_403_FORBIDDEN)
        from .selectors import rentabilite_contrat
        contrat = self.get_object()
        return Response(rentabilite_contrat(contrat))

    @action(detail=False, methods=['get'], url_path='rentabilite',
            permission_classes=[IsResponsableOrAdmin])
    def rentabilite_liste(self, request):
        """XSAV18 — Rentabilité de TOUS les contrats, classée par marge
        croissante (les contrats vendus à perte en premier). Admin-only."""
        if not request.user.can_view_buy_prices:
            return Response(
                {'detail': 'Coût interne réservé (permission prix_achat_voir).'},
                status=status.HTTP_403_FORBIDDEN)
        from .selectors import rentabilite_contrats
        data = rentabilite_contrats(request.user.company)
        return Response({'results': data})
