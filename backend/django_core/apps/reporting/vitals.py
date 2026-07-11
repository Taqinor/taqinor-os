"""VX61 — Collecte des Web Vitals RÉELS (INP/LCP/CLS/TTFB) mesurés terrain.

Reçoit le beacon `frontend/src/lib/vitals.js` : une ligne
``reporting.VitalMetric`` par métrique par navigation. ``company`` posée
CÔTÉ SERVEUR depuis l'utilisateur authentifié — jamais lue du corps de
requête ; un visiteur non authentifié (ex. avant connexion) est accepté
avec ``company=None`` pour ne jamais perdre un signal terrain. Aucune
lecture n'est exposée ici — l'agrégat p75 par route vit dans
``insights.py`` (à consommer par un futur tableau de bord perf)."""
from django.utils import timezone
from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny
from rest_framework.response import Response

from .models import VitalMetric

# VX61 — fenêtre de rétention par défaut (jours) : une ligne par métrique par
# navigation croît vite ; enregistrée au registre partagé YOPSB10 (voir
# apps.py ready()).
DEFAULT_VITAL_METRIC_RETENTION_DAYS = 90


@api_view(['POST'])
@permission_classes([AllowAny])
def vitals_collect(request):
    """POST une métrique Web Vital ``{name, value, path}``.

    Body: ``{"name": "LCP"|"INP"|"CLS"|"TTFB", "value": <float>, "path":
    "<pathname>"}``. Toujours 201 si le body est exploitable (fire-and-
    forget côté front, `sendBeacon` n'inspecte pas la réponse) ; 400 si
    ``name``/``value`` manquent ou sont invalides."""
    name = request.data.get('name')
    value = request.data.get('value')
    path = request.data.get('path') or ''

    if name not in VitalMetric.Metrique.values:
        return Response(
            {'detail': 'name invalide.'}, status=status.HTTP_400_BAD_REQUEST)
    try:
        value = float(value)
    except (TypeError, ValueError):
        return Response(
            {'detail': 'value invalide.'}, status=status.HTTP_400_BAD_REQUEST)

    # Scoping société posé CÔTÉ SERVEUR — jamais depuis le corps de requête.
    user = request.user if request.user.is_authenticated else None
    company = getattr(user, 'company', None) if user else None

    VitalMetric.objects.create(
        company=company, name=name, value=value, path=str(path)[:255])
    return Response(status=status.HTTP_201_CREATED)


def purge_vital_metrics(now, apply_) -> int:
    """VX61 — politique de rétention YOPSB10 : purge les ``VitalMetric`` au-delà
    de ``DEFAULT_VITAL_METRIC_RETENTION_DAYS``. Contrat ``core.retention`` :
    ``apply_=False`` (dry-run) ne supprime rien, renvoie le compte qui SERAIT
    supprimé."""
    cutoff = now - timezone.timedelta(days=DEFAULT_VITAL_METRIC_RETENTION_DAYS)
    qs = VitalMetric.objects.filter(created_at__lt=cutoff)
    count = qs.count()
    if apply_ and count:
        qs.delete()
    return count
