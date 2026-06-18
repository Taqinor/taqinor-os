"""N58 — vues de la configuration des statuts métier (Paramètres → Statuts).

Couche d'AFFICHAGE uniquement : on surcharge le libellé / l'ordre / la
visibilité des statuts chantier, SAV et bon de commande, par société. Les clés
canoniques et la machine à états restent intactes dans leurs modèles sources.

  * Lecture (`list`, `retrieve`, `effective`) : tout rôle.
  * Écriture (`create`, `update`, `partial_update`, `destroy`, `bulk`) :
    Administrateur ou Responsable promu — jamais le palier limité.

`company` est filtrée et forcée côté serveur (TenantMixin) — jamais lue du
corps de la requête. L'entonnoir du lead (STAGES.py) n'est jamais touché.
"""
from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.response import Response

from authentication.mixins import TenantMixin
from authentication.permissions import IsAdminOrResponsableTier, IsAnyRole

from .models import SettingsAuditLog
from .models_statuses import StatutConfig
from .serializers_statuses import StatutConfigSerializer
from .statuses_defaults import VALID_DOMAINES, default_statuses

READ_ACTIONS = ['list', 'retrieve', 'effective']


def effective_statuses(company, domaine):
    """Liste effective [{cle, libelle, ordre, actif, personnalise}] d'un domaine.

    Part des défauts canoniques (lus à la source) puis applique les surcharges
    ``StatutConfig`` enregistrées pour la société. Renvoie TOUJOURS la liste
    complète et ordonnée — même quand rien n'est enregistré (affichage
    byte-identique aux libellés codés en dur). `personnalise` indique si la
    ligne porte une surcharge.
    """
    overrides = {}
    if company is not None:
        overrides = {
            row.cle: row
            for row in StatutConfig.objects.filter(
                company=company, domaine=domaine)
        }
    rows = []
    for cle, libelle, ordre in default_statuses(domaine):
        ov = overrides.get(cle)
        rows.append({
            'cle': cle,
            'libelle': ov.libelle if ov else libelle,
            'ordre': ov.ordre if ov else ordre,
            'actif': ov.actif if ov else True,
            'libelle_defaut': libelle,
            'personnalise': ov is not None,
        })
    rows.sort(key=lambda r: (r['ordre'], r['cle']))
    return rows


class StatutConfigViewSet(TenantMixin, viewsets.ModelViewSet):
    """Surcharges d'affichage des statuts métier (N58).

    Filtrée par `?domaine=`. La création/màj force `company` côté serveur via
    TenantMixin. La clé canonique n'est jamais altérée (gardée au sérialiseur).
    """
    queryset = StatutConfig.objects.all()
    serializer_class = StatutConfigSerializer

    def get_permissions(self):
        if self.action in READ_ACTIONS:
            return [IsAnyRole()]
        return [IsAdminOrResponsableTier()]

    def get_queryset(self):
        qs = super().get_queryset()
        domaine = self.request.query_params.get('domaine')
        if domaine:
            qs = qs.filter(domaine=domaine)
        return qs

    def _audit(self, field, label, old, new):
        company = self.request.user.company if (
            self.request.user.company_id) else None
        if old == new:
            return
        SettingsAuditLog.log_change(
            company=company, user=self.request.user, section='statuts',
            field=field, field_label=label, old=old, new=new)

    @action(detail=False, methods=['get'])
    def effective(self, request):
        """Liste effective (défauts fusionnés avec les surcharges) d'un domaine.

        `?domaine=chantier|sav|bon_commande` requis.
        """
        domaine = request.query_params.get('domaine')
        if domaine not in VALID_DOMAINES:
            return Response(
                {'detail': 'Paramètre ?domaine= requis (chantier|sav|'
                           'bon_commande).'},
                status=status.HTTP_400_BAD_REQUEST)
        company = request.user.company if request.user.company_id else None
        return Response({
            'domaine': domaine,
            'results': effective_statuses(company, domaine),
        })

    @action(detail=False, methods=['put'])
    def bulk(self, request):
        """Upsert en une fois des surcharges d'un domaine (libellé/ordre/actif).

        Corps : ``{"domaine": "...", "statuts": [{"cle", "libelle", "ordre",
        "actif"}, ...]}``. Seules les clés canoniques connues sont acceptées ;
        `company` est forcée côté serveur. Renvoie la liste effective à jour.
        """
        domaine = request.data.get('domaine')
        if domaine not in VALID_DOMAINES:
            return Response(
                {'detail': 'Domaine inconnu.'},
                status=status.HTTP_400_BAD_REQUEST)
        company = request.user.company if request.user.company_id else None
        if company is None:
            return Response(
                {'detail': 'Société requise.'},
                status=status.HTTP_400_BAD_REQUEST)
        valid = {cle for cle, _, _ in default_statuses(domaine)}
        items = request.data.get('statuts') or []
        if not isinstance(items, list):
            return Response(
                {'detail': 'Champ « statuts » : liste attendue.'},
                status=status.HTTP_400_BAD_REQUEST)
        for item in items:
            cle = (item or {}).get('cle')
            if cle not in valid:
                # On ignore silencieusement une clé inconnue plutôt que de
                # tout rejeter — robuste à un statut retiré côté source.
                continue
            obj, _ = StatutConfig.objects.get_or_create(
                company=company, domaine=domaine, cle=cle)
            before = (obj.libelle, obj.ordre, obj.actif)
            if 'libelle' in item and item['libelle'] is not None:
                obj.libelle = str(item['libelle'])[:120]
            if 'ordre' in item and item['ordre'] is not None:
                try:
                    obj.ordre = max(0, int(item['ordre']))
                except (TypeError, ValueError):
                    pass
            if 'actif' in item:
                obj.actif = bool(item['actif'])
            obj.save()
            if (obj.libelle, obj.ordre, obj.actif) != before:
                self._audit(
                    f'{domaine}.{cle}',
                    f'Statut {domaine} « {cle} »',
                    f'{before[0]} (ordre {before[1]}, '
                    f'{"actif" if before[2] else "masqué"})',
                    f'{obj.libelle} (ordre {obj.ordre}, '
                    f'{"actif" if obj.actif else "masqué"})')
        return Response({
            'domaine': domaine,
            'results': effective_statuses(company, domaine),
        })
