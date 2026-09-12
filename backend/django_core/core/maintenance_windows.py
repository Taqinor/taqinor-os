"""NTOBS9 — fenêtres de maintenance planifiées, annoncées in-app AVANT
qu'elles n'arrivent.

NOMMÉ ``maintenance_windows.py`` (pas ``maintenance.py``) : ce dernier existe
DÉJÀ (NTPLT55, ``MaintenanceModeMiddleware`` + ``core.MaintenanceMode`` — le
mode lecture-seule global de bascule de schéma, une fonctionnalité totalement
distincte) — jamais l'écraser.

Modèle défini ICI (pas directement dans ``core/models.py``) et réexporté en
bas de ``core/models.py`` — même éclatement que ``core/sla.py``/
``core/signed_download.py``. ``core`` reste fondation (contrat import-linter
``core-foundation-is-a-base-layer``) : ``authentication`` est une app de
fondation (CLAUDE.md), la seule importée statiquement ici pour trouver les
admins à notifier.
"""
from __future__ import annotations

from datetime import timedelta

from django.db import models
from django.utils import timezone
from rest_framework import generics, serializers, status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import BasePermission, IsAuthenticated
from rest_framework.response import Response

from .models import TimestampedModel


class MaintenanceWindow(TimestampedModel):
    """Fenêtre de maintenance planifiée (``company`` NULL = annonce système
    large, visible de tous les tenants)."""

    class Impact(models.TextChoices):
        AUCUN = 'aucun', 'Aucun'
        DEGRADE = 'degrade', 'Dégradé'
        INTERRUPTION = 'interruption', 'Interruption'

    class Statut(models.TextChoices):
        PLANIFIE = 'planifie', 'Planifié'
        EN_COURS = 'en_cours', 'En cours'
        TERMINE = 'termine', 'Terminé'
        ANNULE = 'annule', 'Annulé'

    company = models.ForeignKey(
        'authentication.Company', on_delete=models.CASCADE,
        null=True, blank=True, related_name='maintenance_windows',
        verbose_name='Société',
        help_text='NULL = annonce système large (toutes les sociétés).')
    region = models.CharField('Région', max_length=60, blank=True, default='')
    debute_le = models.DateTimeField('Débute le')
    termine_le = models.DateTimeField('Termine le')
    impact = models.CharField(
        'Impact', max_length=20, choices=Impact.choices,
        default=Impact.DEGRADE)
    description = models.TextField('Description', blank=True, default='')
    statut = models.CharField(
        'Statut', max_length=12, choices=Statut.choices,
        default=Statut.PLANIFIE)
    # Anti-double-envoi (par fenêtre, pas par destinataire — cf. NTOBS9).
    notifie_24h_avant = models.BooleanField('Notifié 24h avant', default=False)
    notifie_1h_avant = models.BooleanField('Notifié 1h avant', default=False)

    class Meta:
        verbose_name = 'Fenêtre de maintenance'
        verbose_name_plural = 'Fenêtres de maintenance'
        ordering = ['debute_le']

    def __str__(self):
        cible = f'société {self.company_id}' if self.company_id else 'système'
        return f'Maintenance {cible} — {self.debute_le:%Y-%m-%d %H:%M} ({self.statut})'


# ── Ciblage des admins à notifier ───────────────────────────────────────────

def _est_admin(user):
    if getattr(user, 'is_superuser', False) or getattr(user, 'is_admin_role', False):
        return True
    role = getattr(user, 'role', None)
    return bool(role and role.nom in ('Directeur', 'Administrateur'))


def admins_cibles(company):
    """Admins à notifier pour ``company`` (ou de TOUTES les sociétés actives
    si ``company`` est ``None`` — annonce système large)."""
    from authentication.models import CustomUser

    qs = CustomUser.objects.filter(is_active=True).select_related('role')
    if company is not None:
        qs = qs.filter(company=company)
    return [u for u in qs if _est_admin(u)]


def _notifier_fenetre(fenetre, delai_label):
    """Best-effort : un envoi en échec pour UN admin n'empêche pas les autres.
    Passe par ``core.notify_registry`` (jamais un import direct d'``apps.
    notifications`` — contrat import-linter ``core-foundation-is-a-base-
    layer``) ; ``'maintenance_window_announced'`` reflète
    ``apps.notifications.models.EventType.MAINTENANCE_WINDOW_ANNOUNCED``."""
    from . import notify_registry

    titre = f'Fenêtre de maintenance {delai_label}'
    for admin in admins_cibles(fenetre.company):
        notify_registry.notify(
            admin, 'maintenance_window_announced', titre,
            body=fenetre.description, company=admin.company,
        )


def notifier_fenetres_a_venir(now=None):
    """NTOBS9 — job beat (15 min) : notifie 24h et 1h avant une fenêtre
    ``planifie``, jamais deux fois pour le même seuil (flags par fenêtre)."""
    now = now or timezone.now()
    fenetres = MaintenanceWindow.objects.filter(
        statut=MaintenanceWindow.Statut.PLANIFIE, debute_le__gt=now)

    notifies = 0
    for fenetre in fenetres:
        delta = fenetre.debute_le - now
        if delta <= timedelta(hours=24) and not fenetre.notifie_24h_avant:
            _notifier_fenetre(fenetre, 'dans 24h')
            fenetre.notifie_24h_avant = True
            fenetre.save(update_fields=['notifie_24h_avant', 'updated_at'])
            notifies += 1
        if delta <= timedelta(hours=1) and not fenetre.notifie_1h_avant:
            _notifier_fenetre(fenetre, 'dans 1h')
            fenetre.notifie_1h_avant = True
            fenetre.save(update_fields=['notifie_1h_avant', 'updated_at'])
            notifies += 1
    return notifies


# ── API ──────────────────────────────────────────────────────────────────

class MaintenanceWindowSerializer(serializers.ModelSerializer):
    class Meta:
        model = MaintenanceWindow
        fields = [
            'id', 'company', 'region', 'debute_le', 'termine_le', 'impact',
            'description', 'statut', 'created_at',
        ]
        read_only_fields = ['statut']


class IsDirecteurOrAdmin(BasePermission):
    """NTOBS9 — création/annulation réservée Directeur/Administrateur (même
    patron local que les autres apps — jamais un import cross-app)."""

    def has_permission(self, request, view):
        u = request.user
        return bool(u and u.is_authenticated and _est_admin(u))


class MaintenanceWindowListCreateView(generics.ListCreateAPIView):
    """GET/POST /api/django/core/maintenance-windows/ — Directeur/
    Administrateur uniquement (cross-tenant : gestion souvent système-wide).

    Un Directeur/Administrateur d'UN tenant reste néanmoins BORNÉ à sa propre
    société : ``company`` est forcée côté serveur à la sienne, sauf pour un
    superutilisateur (le fondateur/opérateur plateforme), seul habilité à
    poser ``company=None`` (annonce système large) ou une autre société."""

    serializer_class = MaintenanceWindowSerializer
    permission_classes = [IsAuthenticated, IsDirecteurOrAdmin]
    pagination_class = None
    queryset = MaintenanceWindow.objects.all().order_by('-debute_le')

    def perform_create(self, serializer):
        if getattr(self.request.user, 'is_superuser', False):
            serializer.save()
        else:
            serializer.save(company=self.request.user.company)


@api_view(['POST'])
@permission_classes([IsAuthenticated, IsDirecteurOrAdmin])
def annuler_fenetre(request, pk):
    """POST /api/django/core/maintenance-windows/<pk>/annuler/ — annule une
    fenêtre et notifie (retrait de la bannière + information des admins)."""
    try:
        fenetre = MaintenanceWindow.objects.get(pk=pk)
    except MaintenanceWindow.DoesNotExist:
        return Response(status=status.HTTP_404_NOT_FOUND)
    fenetre.statut = MaintenanceWindow.Statut.ANNULE
    fenetre.save(update_fields=['statut', 'updated_at'])
    _notifier_annulation(fenetre)
    return Response(MaintenanceWindowSerializer(fenetre).data)


def _notifier_annulation(fenetre):
    """Passe par ``core.notify_registry`` — voir ``_notifier_fenetre`` ci-dessus."""
    from . import notify_registry

    for admin in admins_cibles(fenetre.company):
        notify_registry.notify(
            admin, 'maintenance_window_announced',
            'Fenêtre de maintenance annulée',
            body=fenetre.description, company=admin.company,
        )


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def fenetres_actives(request):
    """GET /api/django/core/maintenance-windows/actives/ — fenêtres à venir
    (≤72h) ou en cours, pertinentes pour la société de l'appelant (ou
    système-wide) — pour la bannière in-app du shell applicatif (tout rôle
    authentifié, scopée côté serveur)."""
    company = getattr(request.user, 'company', None)
    now = timezone.now()
    horizon = now + timedelta(hours=72)
    from django.db.models import Q

    qs = MaintenanceWindow.objects.filter(
        Q(company__isnull=True) | Q(company=company),
        statut__in=[MaintenanceWindow.Statut.PLANIFIE,
                    MaintenanceWindow.Statut.EN_COURS],
        debute_le__lte=horizon, termine_le__gte=now,
    ).order_by('debute_le')
    return Response(MaintenanceWindowSerializer(qs, many=True).data)
