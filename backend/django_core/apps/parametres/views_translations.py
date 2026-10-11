"""N94 — vues des surcharges de traduction (Paramètres → Traductions).

Surface de GESTION DES TRADUCTIONS : relire/ajuster les chaînes d'interface par
langue (fr/en/ar) SANS changement de code. S'appuie sur le cadre i18n N93 côté
frontend (chaque clé pointée surcharge la valeur d'un catalogue statique).

  * Lecture (``list``, ``retrieve``, ``effective``) : tout rôle — le frontend
    la charge au login pour fusionner les surcharges par-dessus les catalogues.
  * Écriture (``create``, ``update``, ``partial_update``, ``destroy``,
    ``bulk``) : Administrateur ou Responsable promu — jamais le palier limité —
    ET porteur de ``localisation_gerer`` (NTI18N40, cf.
    ``apps.parametres.localisation``). Les deux gardes sont ET-liées : le palier
    reste la frontière d'écran, le code permet de RETIRER la seule localisation
    à un rôle personnalisé sans toucher à ``parametres_modifier``.

``company`` est filtrée et forcée côté serveur (TenantMixin) — jamais lue du
corps de la requête. Une clé i18n inconnue est simplement ignorée à l'affichage
côté frontend (le catalogue vit là-bas) ; le serveur n'impose pas de liste
blanche de clés.
"""
from drf_spectacular.types import OpenApiTypes
from drf_spectacular.utils import (
    OpenApiParameter, extend_schema, extend_schema_view, inline_serializer,
)
from rest_framework import serializers, status, viewsets
from rest_framework.parsers import JSONParser
from rest_framework.decorators import action
from rest_framework.response import Response

from authentication.mixins import TenantMixin
from authentication.permissions import IsAdminOrResponsableTier, IsAnyRole

from .localisation import PeutGererLocalisation
from .models import SettingsAuditLog
from .models_translations import TranslationOverride
from .serializers_translations import (
    VALID_LOCALES,
    TranslationOverrideSerializer,
)

READ_ACTIONS = ['list', 'retrieve', 'effective']

_OVERRIDES = inline_serializer('TraductionsEffectives', {
    # {locale: {clé: valeur}}
    'overrides': serializers.DictField(
        child=serializers.DictField(child=serializers.CharField())),
})
_BULK_REQUEST = inline_serializer('TraductionsBulkRequest', {
    'items': inline_serializer('TraductionsBulkLigne', {
        'locale': serializers.ChoiceField(choices=sorted(VALID_LOCALES)),
        'key': serializers.CharField(),
        'value': serializers.CharField(required=False, allow_null=True),
    }, many=True),
})
_XLSX = ('application/vnd.openxmlformats-officedocument.'
         'spreadsheetml.sheet')


@extend_schema_view(list=extend_schema(parameters=[OpenApiParameter(
    'locale', OpenApiTypes.STR, OpenApiParameter.QUERY, required=False,
    enum=sorted(VALID_LOCALES), description='Ne garder que cette langue.')]))
class TranslationOverrideViewSet(TenantMixin, viewsets.ModelViewSet):
    """CRUD des surcharges de traduction (N94), company-scopé.

    Filtrable par ``?locale=``. La création/màj force ``company`` côté serveur
    via TenantMixin. La suppression d'une ligne = retour au catalogue statique.
    """
    queryset = TranslationOverride.objects.all()
    serializer_class = TranslationOverrideSerializer
    parser_classes = [JSONParser]  # ENF8 (D2) — aucun upload

    def get_permissions(self):
        if self.action in READ_ACTIONS:
            return [IsAnyRole()]
        return [IsAdminOrResponsableTier(), PeutGererLocalisation()]

    def get_queryset(self):
        qs = super().get_queryset()
        locale = self.request.query_params.get('locale')
        if locale:
            qs = qs.filter(locale=locale)
        return qs

    def _company(self):
        return (self.request.user.company
                if self.request.user.company_id else None)

    def _audit(self, locale, key, old, new):
        if old == new:
            return
        SettingsAuditLog.log_change(
            company=self._company(), user=self.request.user,
            section='traductions', field=f'{locale}.{key}',
            field_label=f'Traduction {locale} « {key} »', old=old, new=new)

    def perform_create(self, serializer):
        super().perform_create(serializer)
        obj = serializer.instance
        self._audit(obj.locale, obj.key, '', obj.value)

    def perform_update(self, serializer):
        old = serializer.instance.value
        super().perform_update(serializer)
        obj = serializer.instance
        self._audit(obj.locale, obj.key, old, obj.value)

    def perform_destroy(self, instance):
        locale, key, old = instance.locale, instance.key, instance.value
        super().perform_destroy(instance)
        self._audit(locale, key, old, '')

    @extend_schema(responses=_OVERRIDES)
    @action(detail=False, methods=['get'])
    def effective(self, request):
        """Surcharges de la société sous la forme ``{locale: {key: value}}``.

        Endpoint léger appelé par le frontend au login pour fusionner les
        surcharges par-dessus les catalogues statiques N93. Renvoie ``{}`` (ou
        des locales vides) quand rien n'est enregistré → aucune régression.
        """
        company = self._company()
        return Response({
            'overrides': TranslationOverride.overrides_for_company(company),
        })

    @extend_schema(request=_BULK_REQUEST, responses=_OVERRIDES)
    @action(detail=False, methods=['put'])
    def bulk(self, request):
        """Upsert/suppression en une fois de plusieurs surcharges.

        Corps : ``{"items": [{"locale", "key", "value"}, ...]}``. Une valeur
        vide ("" ou null) SUPPRIME la surcharge (retour au catalogue statique).
        ``company`` est forcée côté serveur. Renvoie ``{overrides}`` à jour.
        """
        company = self._company()
        if company is None:
            return Response(
                {'detail': 'Société requise.'},
                status=status.HTTP_400_BAD_REQUEST)
        items = request.data.get('items')
        if not isinstance(items, list):
            return Response(
                {'detail': 'Champ « items » : liste attendue.'},
                status=status.HTTP_400_BAD_REQUEST)
        for item in items:
            locale = (item or {}).get('locale')
            key = ((item or {}).get('key') or '').strip()
            if locale not in VALID_LOCALES or not key:
                # Ligne invalide ignorée (robuste à une clé/locale vide).
                continue
            value = (item or {}).get('value')
            if value is None or str(value).strip() == '':
                # Suppression = retour au catalogue statique.
                existing = TranslationOverride.objects.filter(
                    company=company, locale=locale, key=key).first()
                if existing is not None:
                    old = existing.value
                    existing.delete()
                    self._audit(locale, key, old, '')
                continue
            obj, _ = TranslationOverride.objects.get_or_create(
                company=company, locale=locale, key=key)
            old = obj.value
            obj.value = str(value)
            obj.save()
            self._audit(locale, key, old, obj.value)
        return Response({
            'overrides': TranslationOverride.overrides_for_company(company),
        })

    @extend_schema(responses={(200, _XLSX): OpenApiTypes.BINARY})
    @action(detail=False, methods=['get'], url_path='glossaire-export')
    def glossaire_export(self, request):
        """NTI18N46 — classeur XLSX du glossaire, pour relecture hors ligne.

        Un onglet par domaine (statuts / unités / mentions légales) ; une case
        de traduction EN ou AR absente est peinte en rouge. Action d'écriture au
        sens des permissions (hors ``READ_ACTIONS``) : le fichier porte les
        textes contractuels de la société, et la relecture linguistique est
        précisément ce que ``localisation_gerer`` gouverne (NTI18N40).
        """
        from .glossaire_export import reponse_export

        return reponse_export(self._company())
