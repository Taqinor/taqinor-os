import datetime

from django.db.models import Q
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


class OutillageViewSet(UsageGuardedDestroyMixin, TenantMixin,
                       viewsets.ModelViewSet):
    """Catalogue d'outillage durable (F1). Lecture tout rôle ; écriture
    responsable/admin. Filtrable par statut et emplacement, recherche par
    nom / asset tag / n° de série. JAMAIS de stock vendable."""
    queryset = Outillage.objects.select_related('emplacement').all()
    serializer_class = OutillageSerializer
    # ACHT79 — l'outillage relève du module « installations » pour les droits :
    # `IsResponsableOrAdmin` exige alors un code d'ÉCRITURE de ce module (un
    # Admin RH, qui porte des codes d'écriture ailleurs, n'écrit plus ici).
    permission_module = 'installations'
    filter_backends = [filters.SearchFilter, filters.OrderingFilter]
    search_fields = ['nom', 'asset_tag', 'numero_serie', 'categorie']
    ordering_fields = ['nom', 'statut', 'date_achat', 'date_creation']

    def get_permissions(self):
        if self.action in READ_ACTIONS:
            return [IsAnyRole()]
        if self.action in ['calibrer']:
            return [IsResponsableOrAdmin()]
        return [IsResponsableOrAdmin()]

    def destroy_guard_message(self, outil):
        """ACHT73 — un outil référencé par un retour d'outillage, un kit, une
        préparation d'intervention ou une fiche de recette (instrument) ne se
        supprime pas : l'historique disparaîtrait (CASCADE) ou perdrait son
        instrument. Le statut « Perdu » / « En réparation » le retire du
        parc sans rien effacer."""
        from apps.installations.selectors import nb_fiches_recette_instrument
        usages = []
        for libelle, nb in (
                ("retour(s) d'outillage", outil.tool_returns.count()),
                ('kit(s)', outil.kit_items.count()),
                ("préparation(s) d'intervention",
                 outil.preparation_lignes.count()),
                ('fiche(s) de recette (instrument)',
                 nb_fiches_recette_instrument(outil.company, outil.pk))):
            if nb:
                usages.append(f'{nb} {libelle}')
        if usages:
            return ("Outil utilisé par " + ', '.join(usages)
                    + " — marquez-le « Perdu » ou « En réparation » plutôt "
                      "que de le supprimer.")
        return None

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
            # ACHT74 — MÊME règle que le badge `a_calibrer` : intervalle > 0 ET
            # (jamais calibré OU échéance dépassée).
            today = datetime.date.today()
            qs = qs.filter(
                Q(date_prochaine_calibration__isnull=True)
                | Q(date_prochaine_calibration__lte=today),
                intervalle_calibration_mois__gt=0)
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
        # ACHT74 — une calibration ne se date ni dans le futur ni avant la
        # précédente.
        if date_cal > datetime.date.today():
            return Response(
                {'date_calibration': 'Date de calibration dans le futur.'},
                status=status.HTTP_400_BAD_REQUEST)
        if (outil.date_derniere_calibration is not None
                and date_cal < outil.date_derniere_calibration):
            return Response(
                {'date_calibration': (
                    'Date antérieure à la dernière calibration '
                    f'({outil.date_derniere_calibration}).')},
                status=status.HTTP_400_BAD_REQUEST)
        outil.date_derniere_calibration = date_cal
        # `Outillage.save()` dérive `date_prochaine_calibration` (vrais mois).
        outil.save(update_fields=[
            'date_derniere_calibration', 'date_prochaine_calibration'])
        # ACHT75 — notification réelle (type d'événement déclaré, erreurs
        # journalisées) si la prochaine échéance est à 30 jours ou moins ; le
        # helper est partagé avec la tâche quotidienne (aucun doublon).
        if (outil.date_prochaine_calibration and
                outil.date_prochaine_calibration
                <= datetime.date.today() + datetime.timedelta(days=30)):
            from .tasks import notifier_calibration_proche
            notifier_calibration_proche(outil, [request.user])
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
