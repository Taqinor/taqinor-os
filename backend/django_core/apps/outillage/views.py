import datetime

from rest_framework import viewsets, filters, status
from rest_framework.decorators import action
from rest_framework.response import Response

from authentication.mixins import TenantMixin
from authentication.permissions import IsAnyRole, IsResponsableOrAdmin, IsAdminRole
from apps.core.destroy_mixins import UsageGuardedDestroyMixin

from .models import Outillage, KitOutillage, KitOutillageItem
from .serializers import (
    OutillageSerializer, KitOutillageSerializer, KitOutillageItemSerializer,
)

READ_ACTIONS = ['list', 'retrieve']

# Kits d'outillage par défaut — semés à la première consultation par société.
# Coquilles nommées et vides : le founder y ajoute les outils de son parc.
_DEFAULT_KITS = [
    'Kit pose structure',
    'Kit raccordement électrique',
    'Kit mise en service',
]


def seed_kits_outillage(company):
    """Sème les 3 kits par défaut une seule fois par société (idempotent)."""
    if company is None or KitOutillage.objects.filter(company=company).exists():
        return
    for i, nom in enumerate(_DEFAULT_KITS):
        KitOutillage.objects.get_or_create(
            company=company, nom=nom, defaults={'ordre': i})


class OutillageViewSet(TenantMixin, viewsets.ModelViewSet):
    """Catalogue d'outillage durable (F1). Lecture tout rôle ; écriture
    responsable/admin. Filtrable par statut et emplacement, recherche par
    nom / asset tag / n° de série. JAMAIS de stock vendable."""
    queryset = Outillage.objects.select_related('emplacement').all()
    serializer_class = OutillageSerializer
    filter_backends = [filters.SearchFilter, filters.OrderingFilter]
    search_fields = ['nom', 'asset_tag', 'numero_serie', 'categorie']
    ordering_fields = ['nom', 'statut', 'date_achat', 'date_creation']

    def get_permissions(self):
        if self.action in READ_ACTIONS:
            return [IsAnyRole()]
        if self.action in ['calibrer']:
            return [IsResponsableOrAdmin()]
        return [IsResponsableOrAdmin()]

    def get_queryset(self):
        qs = super().get_queryset()
        params = self.request.query_params
        statut = params.get('statut')
        if statut:
            qs = qs.filter(statut=statut)
        emplacement = params.get('emplacement')
        if emplacement:
            qs = qs.filter(emplacement_id=emplacement)
        # FG80 — filtre « à calibrer » : intervalle > 0 ET date_prochaine <= aujourd'hui.
        a_calibrer = params.get('a_calibrer')
        if a_calibrer in ('1', 'true', 'True'):
            today = datetime.date.today()
            qs = qs.filter(
                intervalle_calibration_mois__gt=0,
                date_prochaine_calibration__lte=today)
        return qs

    # ── FG80 — enregistrement d'une calibration ──────────────────────────────
    @action(detail=True, methods=['post'], url_path='calibrer',
            permission_classes=[IsResponsableOrAdmin])
    def calibrer(self, request, pk=None):
        """FG80 — enregistre une calibration / inspection sur l'outil et recalcule
        `date_prochaine_calibration`. Corps : {"date_calibration": "YYYY-MM-DD"}
        (défaut = aujourd'hui). Émet une notification si la prochaine date est
        dépassée à la sauvegarde."""
        outil = self.get_object()
        date_str = request.data.get('date_calibration')
        try:
            date_cal = (datetime.date.fromisoformat(date_str)
                        if date_str else datetime.date.today())
        except (ValueError, TypeError):
            return Response({'date_calibration': 'Date invalide (YYYY-MM-DD).'},
                            status=status.HTTP_400_BAD_REQUEST)
        outil.date_derniere_calibration = date_cal
        # Recalcul de la prochaine date.
        if outil.intervalle_calibration_mois:
            # Ajoute n mois (approximation : 30.44 jours / mois).
            days = int(outil.intervalle_calibration_mois * 30.44)
            outil.date_prochaine_calibration = (
                date_cal + datetime.timedelta(days=days))
        else:
            outil.date_prochaine_calibration = None
        outil.save(update_fields=[
            'date_derniere_calibration', 'date_prochaine_calibration'])
        # Notification si l'outil sera de nouveau à calibrer dans moins d'un mois.
        if (outil.date_prochaine_calibration and
                outil.date_prochaine_calibration
                <= datetime.date.today() + datetime.timedelta(days=30)):
            try:
                from apps.notifications.services import notify
                # Notifie l'utilisateur courant (responsable qui a enregistré).
                notify(
                    user=request.user,
                    event_type='outillage_calibration_proche',
                    title=f"Calibration proche : {outil.nom}",
                    body=(f"Prochaine calibration le "
                          f"{outil.date_prochaine_calibration}."),
                    company=outil.company,
                )
            except Exception:
                pass  # La notification est un bonus — ne fait jamais échouer la vue.
        return Response(OutillageSerializer(outil).data)


class KitOutillageViewSet(UsageGuardedDestroyMixin, TenantMixin, viewsets.ModelViewSet):
    """Kits d'outillage (F2), gérés dans Paramètres. Lecture tout rôle ;
    écriture admin. Les 3 kits par défaut sont semés à la première liste.
    VX241(b) — AUCUN garde ni ligne AuditLog n'existait avant sur ce
    `destroy()` (un kit encore sélectionné par une préparation d'intervention
    en cours pouvait disparaître silencieusement, ou l'admin ne savait jamais
    QUI a supprimé quel kit) : UsageGuardedDestroyMixin bloque un kit en
    usage (409 FR) et journalise la suppression effective."""
    queryset = KitOutillage.objects.prefetch_related('items__outil').all()
    serializer_class = KitOutillageSerializer

    def get_permissions(self):
        if self.action in READ_ACTIONS:
            return [IsAnyRole()]
        return [IsAdminRole()]

    def list(self, request, *args, **kwargs):
        if request.user.company_id:
            seed_kits_outillage(request.user.company)
        return super().list(request, *args, **kwargs)

    def destroy_guard_message(self, kit):
        # `InterventionPreparation.kit` (apps/installations/models_field.py)
        # est on_delete=SET_NULL — une préparation EN COURS perdrait
        # silencieusement son kit sélectionné sans ce garde.
        if kit.preparations.exists():
            return ("Ce kit est sélectionné par une préparation d'intervention "
                    "— désactivez-le plutôt que de le supprimer.")
        return None


class KitOutillageItemViewSet(TenantMixin, viewsets.ModelViewSet):
    """Outils d'un kit (F2). Company posée côté serveur depuis le kit parent ;
    écriture admin. Filtrable par kit."""
    queryset = KitOutillageItem.objects.select_related('outil', 'kit').all()
    serializer_class = KitOutillageItemSerializer

    def get_permissions(self):
        if self.action in READ_ACTIONS:
            return [IsAnyRole()]
        return [IsAdminRole()]

    def get_queryset(self):
        qs = super().get_queryset()
        kit = self.request.query_params.get('kit')
        if kit:
            qs = qs.filter(kit_id=kit)
        return qs

    def perform_create(self, serializer):
        # La société de l'item suit toujours celle du kit parent.
        serializer.save(company=serializer.validated_data['kit'].company)

    def perform_update(self, serializer):
        kit = serializer.validated_data.get('kit') or serializer.instance.kit
        serializer.save(company=kit.company)
