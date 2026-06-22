"""FG17 — vues des modèles d'e-mail éditables (Paramètres → E-mails).

Parité avec les modèles WhatsApp (``MessageTemplate``) mais côté e-mail : par
société et par clé, un SUJET + un CORPS éditables. Couche de RENDU uniquement —
aucun statut n'est touché.

  * Lecture (``list``, ``retrieve``, ``effective``) : tout rôle.
  * Écriture (``create``, ``update``, ``partial_update``, ``destroy``, ``bulk``) :
    Administrateur ou Responsable promu — jamais le palier limité.

``company`` est filtrée et forcée côté serveur (TenantMixin) — jamais lue du
corps de la requête. L'action e-mail de l'automation reste sur son sujet codé en
dur : le câblage est laissé à une autre lane (on ne fournit ici que le
modèle + l'API + l'aide ``EmailTemplate.get_template``).
"""
from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.response import Response

from authentication.mixins import TenantMixin
from authentication.permissions import IsAdminOrResponsableTier, IsAnyRole

from .models import SettingsAuditLog
from .models_email import (
    EMAIL_TEMPLATE_DEFAULTS,
    EMAIL_TEMPLATE_PLACEHOLDERS,
    EmailTemplate,
)
from .serializers_email import EmailTemplateSerializer

READ_ACTIONS = ['list', 'retrieve', 'effective']


def effective_email_templates(company):
    """Liste effective [{cle, label, sujet, corps, defaut_*, placeholders}].

    Part des défauts (``EMAIL_TEMPLATE_DEFAULTS``) puis applique la version
    personnalisée de la société quand elle existe. Renvoie TOUJOURS la liste
    complète et ordonnée — même quand rien n'est enregistré.
    """
    rows = {}
    if company is not None:
        rows = {
            r.cle: r for r in EmailTemplate.objects.filter(company=company)
        }
    out = []
    for cle, label in EmailTemplate.Cle.choices:
        row = rows.get(cle)
        default = EMAIL_TEMPLATE_DEFAULTS.get(cle, {'sujet': '', 'corps': ''})
        out.append({
            'cle': cle,
            'label': label,
            'sujet': (row.sujet if row and row.sujet else default['sujet']),
            'corps': (row.corps if row and row.corps else default['corps']),
            'sujet_defaut': default['sujet'],
            'corps_defaut': default['corps'],
            'personnalise': row is not None,
            'placeholders': EMAIL_TEMPLATE_PLACEHOLDERS.get(cle, []),
        })
    return out


class EmailTemplateViewSet(TenantMixin, viewsets.ModelViewSet):
    """Modèles d'e-mail éditables (FG17).

    Filtrée et company forcée côté serveur (TenantMixin). L'upsert par clé est
    exposé via ``effective`` (lecture fusionnée) et ``bulk`` (écriture en masse).
    """
    queryset = EmailTemplate.objects.all()
    serializer_class = EmailTemplateSerializer

    def get_permissions(self):
        if self.action in READ_ACTIONS:
            return [IsAnyRole()]
        return [IsAdminOrResponsableTier()]

    def _audit(self, field, label, old, new):
        company = self.request.user.company if (
            self.request.user.company_id) else None
        if old == new:
            return
        SettingsAuditLog.log_change(
            company=company, user=self.request.user, section='emails',
            field=field, field_label=label, old=old, new=new)

    @action(detail=False, methods=['get'])
    def effective(self, request):
        """Liste effective (défauts fusionnés avec les versions société)."""
        company = request.user.company if request.user.company_id else None
        return Response({'results': effective_email_templates(company)})

    @action(detail=False, methods=['put'])
    def bulk(self, request):
        """Upsert en masse des modèles d'e-mail (sujet/corps), par clé.

        Corps : ``{"templates": [{"cle", "sujet", "corps"}, ...]}``. Seules les
        clés connues sont acceptées ; ``company`` est forcée côté serveur. Un
        placeholder non whitelisté pour la clé est rejeté. Renvoie la liste
        effective à jour.
        """
        company = request.user.company if request.user.company_id else None
        if company is None:
            return Response(
                {'detail': 'Société requise.'},
                status=status.HTTP_400_BAD_REQUEST)
        valid = {c for c, _ in EmailTemplate.Cle.choices}
        items = request.data.get('templates')
        if not isinstance(items, list):
            return Response(
                {'detail': 'Champ « templates » : liste attendue.'},
                status=status.HTTP_400_BAD_REQUEST)
        for item in items:
            item = item or {}
            cle = item.get('cle')
            if cle not in valid:
                # Clé inconnue ignorée silencieusement (robuste à une clé retirée).
                continue
            # Validation des placeholders avant écriture (mêmes règles que le
            # sérialiseur de création) — rejette toute la requête si fautif.
            ser = EmailTemplateSerializer(data={
                k: v for k, v in item.items() if k in ('cle', 'sujet', 'corps')
            })
            ser.is_valid(raise_exception=True)
            obj, _ = EmailTemplate.objects.get_or_create(
                company=company, cle=cle)
            before = (obj.sujet, obj.corps)
            if 'sujet' in item and item['sujet'] is not None:
                obj.sujet = str(item['sujet'])[:255]
            if 'corps' in item and item['corps'] is not None:
                obj.corps = str(item['corps'])
            obj.save()
            if (obj.sujet, obj.corps) != before:
                self._audit(
                    cle, f"Modèle d'e-mail « {cle} »",
                    f'{before[0]} | {before[1]}',
                    f'{obj.sujet} | {obj.corps}')
        return Response({'results': effective_email_templates(company)})
