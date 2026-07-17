import json
import zipfile
from io import BytesIO

from django.http import HttpResponse
from rest_framework import viewsets
from rest_framework.decorators import action, api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from . import config_package_service, sandbox_service, selectors
from .health_score import calculer_health_score
from .models import AdminOpsSettings, ConfigPackage, SandboxEnvironment
from .permissions import IsAdministrateur, IsTaqinorSupportOuAdministrateur
from .serializers import (
    AdminOpsSettingsSerializer, ConfigPackageSerializer,
    SandboxEnvironmentSerializer,
)


@api_view(['GET'])
@permission_classes([IsAdministrateur])
def health_score_view(request):
    """NTADM5 — score 0-100 + sous-scores + recommandations, strictement
    scopé société."""
    return Response(calculer_health_score(request.user.company))


@api_view(['GET'])
@permission_classes([IsAdministrateur])
def adoption_view(request):
    """NTADM17 — adoption par module/utilisateur sur `periode` (7/30/90j)."""
    jours = int(request.query_params.get('periode', 30))
    return Response({
        'par_module': selectors.adoption_par_module(request.user.company, jours),
        'par_utilisateur': selectors.adoption_par_utilisateur(
            request.user.company, jours),
    })


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def tracker_usage_view(request):
    """NTADM16 — enregistre un `EvenementUsage` (debounce côté front,
    max 1/minute/écran/utilisateur — le serveur accepte tel quel)."""
    from .models import EvenementUsage
    module = request.data.get('module', '')[:60]
    ecran = request.data.get('ecran', '')[:120]
    if not module:
        return Response({'detail': 'module requis'}, status=400)
    EvenementUsage.objects.create(
        company=request.user.company, module=module, ecran=ecran,
        utilisateur=request.user)
    return Response({'ok': True}, status=201)


class SandboxEnvironmentViewSet(viewsets.ReadOnlyModelViewSet):
    """NTADM10/11/12 — cycle de vie sandbox (Administrateur only)."""

    serializer_class = SandboxEnvironmentSerializer
    permission_classes = [IsAdministrateur]

    def get_queryset(self):
        return SandboxEnvironment.objects.filter(
            company=self.request.user.company).order_by('-date_creation')

    @action(detail=False, methods=['post'])
    def creer(self, request):
        try:
            env = sandbox_service.creer_sandbox(request.user.company, request.user)
        except sandbox_service.SandboxNonAutorise as exc:
            return Response({'detail': str(exc)}, status=403)
        except sandbox_service.SandboxDejaActif as exc:
            return Response({'detail': str(exc)}, status=409)
        self._audit_et_notifier(env, 'création')
        return Response(SandboxEnvironmentSerializer(env).data, status=201)

    @action(detail=True, methods=['post'])
    def prolonger(self, request, pk=None):
        env = self.get_object()
        try:
            env = sandbox_service.prolonger_sandbox(env)
        except ValueError as exc:
            return Response({'detail': str(exc)}, status=400)
        return Response(SandboxEnvironmentSerializer(env).data)

    def _audit_et_notifier(self, env, action_label):
        """NTADM46 — audit + notification systématiques sur chaque action
        sensible de ce groupe."""
        try:
            from apps.audit.recorder import record
            record(
                'create', instance=env, company=env.company, user=env.cree_par,
                detail=f'Sandbox {action_label}')
        except Exception:
            pass
        try:
            from apps.notifications.models import EventType
            from apps.notifications.services import notify
            if env.cree_par is not None:
                notify(
                    env.cree_par, EventType.DIGEST,
                    f'Sandbox {action_label}',
                    body=f"L'environnement sandbox a été {action_label} avec succès.",
                    company=env.company)
        except Exception:
            pass


class ConfigPackageViewSet(viewsets.ReadOnlyModelViewSet):
    """NTADM13/14/15 — export/diff/application de packages de configuration."""

    serializer_class = ConfigPackageSerializer
    permission_classes = [IsAdministrateur]

    def get_queryset(self):
        return ConfigPackage.objects.filter(
            company=self.request.user.company).order_by('-date_creation')

    @action(detail=False, methods=['post'])
    def exporter(self, request):
        nom = request.data.get('nom', 'Configuration')
        package = config_package_service.exporter_config(
            request.user.company, nom=nom, user=request.user)
        self._audit_et_notifier(package, 'export')
        return Response(ConfigPackageSerializer(package).data, status=201)

    @action(detail=False, methods=['post'])
    def previsualiser(self, request):
        contenu = request.data.get('contenu')
        if not isinstance(contenu, dict):
            return Response({'detail': 'contenu (JSON) requis.'}, status=400)
        diff = config_package_service.previsualiser_import(
            request.user.company, contenu)
        from .models import ConfigPackageApplication
        ConfigPackageApplication.objects.create(
            company=request.user.company,
            package_nom=contenu.get('_nom', ''),
            package_version=contenu.get('_version', 1),
            action=ConfigPackageApplication.Action.PREVISUALISATION,
            diff=diff,
            applique_par=request.user if getattr(request.user, 'pk', None) else None)
        return Response(diff)

    @action(detail=False, methods=['post'])
    def appliquer(self, request):
        contenu = request.data.get('contenu')
        if not isinstance(contenu, dict):
            return Response({'detail': 'contenu (JSON) requis.'}, status=400)
        diff = config_package_service.appliquer_import(
            request.user.company, contenu, user=request.user)
        self._audit_et_notifier_import(request.user.company, contenu, request.user)
        return Response(diff)

    def _audit_et_notifier(self, package, action_label):
        try:
            from apps.audit.recorder import record
            record(
                'export', instance=package, company=package.company,
                user=package.cree_par,
                detail=f'Package de configuration {action_label} : {package.nom}')
        except Exception:
            pass
        try:
            from apps.notifications.models import EventType
            from apps.notifications.services import notify
            if package.cree_par is not None:
                notify(
                    package.cree_par, EventType.DIGEST,
                    f'Package de configuration {action_label}',
                    body=package.nom, company=package.company)
        except Exception:
            pass

    def _audit_et_notifier_import(self, company, contenu, user):
        try:
            from apps.audit.recorder import record
            record(
                'update', company=company, user=user,
                detail='Package de configuration importé')
        except Exception:
            pass
        try:
            from apps.notifications.models import EventType
            from apps.notifications.services import notify
            if getattr(user, 'pk', None):
                notify(
                    user, EventType.DIGEST, 'Package de configuration appliqué',
                    body=contenu.get('_nom', ''), company=company)
        except Exception:
            pass


class AdminOpsSettingsView(APIView):
    """NTADM33/34 — réglages transverses (Administrateur only)."""

    permission_classes = [IsAdministrateur]

    def get(self, request):
        reglage = AdminOpsSettings.get_or_default(request.user.company)
        return Response(AdminOpsSettingsSerializer(reglage).data)

    def patch(self, request):
        reglage = AdminOpsSettings.get_or_default(request.user.company)
        serializer = AdminOpsSettingsSerializer(
            reglage, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        reglage = serializer.save(company=request.user.company)
        return Response(AdminOpsSettingsSerializer(reglage).data)


@api_view(['GET'])
@permission_classes([IsTaqinorSupportOuAdministrateur])
def diagnostic_view(request):
    """NTADM23 — instantané non-sensible du tenant, aucune fuite cross-tenant."""
    return Response(selectors.diagnostic_tenant(request.user.company))


@api_view(['GET'])
@permission_classes([IsTaqinorSupportOuAdministrateur])
def support_bundle_view(request):
    """NTADM24 — .zip config non-sensible + 100 dernières lignes AuditLog
    anonymisées + résumé health score. AUCUNE donnée client (nom/tel/email)."""
    company = request.user.company
    diagnostic = selectors.diagnostic_tenant(company)
    health = calculer_health_score(company)

    audit_rows = []
    try:
        from apps.audit.models import AuditLog
        for row in AuditLog.objects.filter(company=company).order_by(
                '-created_at').values('action', 'detail', 'created_at')[:100]:
            audit_rows.append({
                'action': row['action'],
                'created_at': row['created_at'].isoformat() if row['created_at'] else None,
                # `detail` textuel générique (jamais un nom/tel/email de
                # tiers — la journalisation AuditLog ne stocke pas ces
                # champs pour ce type d'événement).
                'detail': row['detail'][:200],
            })
    except Exception:
        pass

    buf = BytesIO()
    with zipfile.ZipFile(buf, 'w', zipfile.ZIP_DEFLATED) as zf:
        zf.writestr('diagnostic.json', json.dumps(
            {k: str(v) for k, v in diagnostic.items()}, ensure_ascii=False, indent=2))
        zf.writestr('health_score.json', json.dumps(health, ensure_ascii=False, indent=2))
        zf.writestr('audit_log_100_dernieres.json', json.dumps(
            audit_rows, ensure_ascii=False, indent=2))
    buf.seek(0)
    response = HttpResponse(buf.read(), content_type='application/zip')
    response['Content-Disposition'] = 'attachment; filename="support-bundle.zip"'
    return response


@api_view(['GET'])
@permission_classes([IsAdministrateur])
def journal_admin_pdf_view(request):
    """NTADM27 — journal d'administration imprimable (WeasyPrint interne via
    `core.pdf.render_pdf` — jamais `/proposal`). Portée assumée (voir rapport
    de lane) : entités (NTADM1) + exports de package (NTADM13) — les volets
    plan/sièges (NTADM7/8) sont hors périmètre de cette lane et donc EXCLUS."""
    from core.pdf import render_pdf

    company = request.user.company
    date_debut = request.query_params.get('date_debut', '')
    date_fin = request.query_params.get('date_fin', '')

    from apps.entites.selectors import entites_pour_journal
    entites = entites_pour_journal(company)
    packages_qs = ConfigPackage.objects.filter(company=company).order_by('date_creation')

    lignes = []
    for e in entites:
        lignes.append((e.created_at, f'Entité créée : {e.code} — {e.nom}'))
    for p in packages_qs:
        lignes.append((p.date_creation, f'Package de configuration exporté : {p.nom} v{p.version}'))
    lignes.sort(key=lambda t: t[0])

    lignes_html = ''.join(
        f'<tr><td>{quand:%Y-%m-%d %H:%M}</td><td>{texte}</td></tr>'
        for quand, texte in lignes)
    html = f'''<html><body>
    <h1>Journal d'administration</h1>
    <p>Période : {date_debut or "—"} → {date_fin or "—"}</p>
    <table border="1" cellpadding="4"><thead><tr><th>Date</th><th>Événement</th></tr></thead>
    <tbody>{lignes_html}</tbody></table>
    </body></html>'''
    pdf_bytes = render_pdf(html=html, company=company)
    response = HttpResponse(pdf_bytes, content_type='application/pdf')
    response['Content-Disposition'] = 'attachment; filename="journal-admin.pdf"'
    return response
