"""N94 — vues des surcharges de traduction (Paramètres → Traductions).

Surface de GESTION DES TRADUCTIONS : relire/ajuster les chaînes d'interface par
langue (fr/en/ar) SANS changement de code. S'appuie sur le cadre i18n N93 côté
frontend (chaque clé pointée surcharge la valeur d'un catalogue statique).

  * Lecture (``list``, ``retrieve``, ``effective``) : tout rôle — le frontend
    la charge au login pour fusionner les surcharges par-dessus les catalogues.
  * Écriture (``create``, ``update``, ``partial_update``, ``destroy``,
    ``bulk``) : Administrateur ou Responsable promu — jamais le palier limité.

``company`` est filtrée et forcée côté serveur (TenantMixin) — jamais lue du
corps de la requête. Une clé i18n inconnue est simplement ignorée à l'affichage
côté frontend (le catalogue vit là-bas) ; le serveur n'impose pas de liste
blanche de clés.
"""
from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.response import Response

from authentication.mixins import TenantMixin
from authentication.permissions import IsAdminOrResponsableTier, IsAnyRole

from .models import SettingsAuditLog
from .models_translations import TranslationOverride
from .serializers_translations import (
    VALID_LOCALES,
    TranslationOverrideSerializer,
)

READ_ACTIONS = ['list', 'retrieve', 'effective']


class TranslationOverrideViewSet(TenantMixin, viewsets.ModelViewSet):
    """CRUD des surcharges de traduction (N94), company-scopé.

    Filtrable par ``?locale=``. La création/màj force ``company`` côté serveur
    via TenantMixin. La suppression d'une ligne = retour au catalogue statique.
    """
    queryset = TranslationOverride.objects.all()
    serializer_class = TranslationOverrideSerializer

    def get_permissions(self):
        if self.action in READ_ACTIONS:
            return [IsAnyRole()]
        return [IsAdminOrResponsableTier()]

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
