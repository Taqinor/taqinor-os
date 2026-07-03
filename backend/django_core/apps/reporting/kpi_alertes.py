"""XPLT6 — alertes de seuil sur KPI AGRÉGÉS configurables.

CRUD company-scopé (`KpiAlerteViewSet`) + évaluation (job Beat quotidien,
`evaluate_all_kpi_alertes`) qui calcule chaque KPI du catalogue FERMÉ à
travers les selectors reporting/compta EXISTANTS, compare au seuil configuré
et notifie une seule fois par franchissement (dédup via `deja_notifie`).

Catalogue fermé (``KpiAlerte.Kpi``) :
  * ``dso``                  — délai moyen de recouvrement, jours
                                (``apps.compta.selectors.pilotage_financier``).
  * ``encours_echu_total``   — Σ des tranches d'âge >30 j de la balance âgée
                                (``apps.reporting.balance_export.balance_agee_rows``,
                                même app).
  * ``valeur_stock_totale``  — valorisation vente du stock
                                (même agrégat que ``apps.reporting.reports.
                                stock_report``).
"""
from decimal import Decimal

from rest_framework import serializers, viewsets

from authentication.permissions import IsResponsableOrAdmin
from core.mixins import TenantMixin

from .models import KpiAlerte


class KpiAlerteSerializer(serializers.ModelSerializer):
    kpi_label = serializers.CharField(source='get_kpi_display', read_only=True)
    operateur_label = serializers.CharField(
        source='get_operateur_display', read_only=True)

    class Meta:
        model = KpiAlerte
        # company posée côté serveur — jamais lue du corps.
        fields = [
            'id', 'nom', 'kpi', 'kpi_label', 'operateur', 'operateur_label',
            'seuil', 'destinataire_role', 'destinataires_utilisateurs',
            'actif', 'deja_notifie', 'derniere_valeur',
            'derniere_evaluation_le', 'created_at', 'updated_at',
        ]
        read_only_fields = [
            'id', 'kpi_label', 'operateur_label', 'deja_notifie',
            'derniere_valeur', 'derniere_evaluation_le', 'created_at',
            'updated_at',
        ]


class KpiAlerteViewSet(TenantMixin, viewsets.ModelViewSet):
    """CRUD des alertes KPI, bornées à la société (réservé admin/responsable
    par cohérence avec les autres réglages de Paramètres)."""
    serializer_class = KpiAlerteSerializer
    permission_classes = [IsResponsableOrAdmin]
    queryset = KpiAlerte.objects.all()


# ── Évaluation des KPI (lecture via selectors EXISTANTS uniquement) ─────────

def _compute_dso(company):
    from apps.compta import selectors as compta_selectors
    data = compta_selectors.pilotage_financier(company)
    dso = data.get('dso')
    return Decimal(str(dso)) if dso is not None else None


def _compute_encours_echu_total(company, user):
    """Σ des tranches >30 j de la balance âgée (même app — pas de selector
    cross-app requis)."""
    from .balance_export import balance_agee_rows
    rows = balance_agee_rows(user)
    if not rows:
        return Decimal('0')
    # La dernière ligne est le pied de page « Total » (b31_60+b61_90+b90_plus).
    total_row = rows[-1]
    if total_row[0] != 'Total':
        return Decimal('0')
    return Decimal(str(total_row[2])) + Decimal(str(total_row[3])) \
        + Decimal(str(total_row[4]))


def _compute_valeur_stock_totale(company):
    """Valorisation vente du stock — même agrégat que
    ``apps.reporting.reports.stock_report`` (même app, pas de selector requis)."""
    from django.db.models import Sum, F, DecimalField
    from django.db.models.functions import Coalesce
    from apps.stock.models import Produit

    qs = Produit.objects.filter(company=company, is_archived=False)
    dec = DecimalField()
    sum_vente = Coalesce(
        Sum(F('prix_vente') * F('quantite_stock'), output_field=dec),
        Decimal('0'))
    return qs.aggregate(t=sum_vente)['t'] or Decimal('0')


_KPI_COMPUTERS = {
    KpiAlerte.Kpi.DSO: lambda company, user: _compute_dso(company),
    KpiAlerte.Kpi.ENCOURS_ECHU_TOTAL: lambda company, user:
        _compute_encours_echu_total(company, user),
    KpiAlerte.Kpi.VALEUR_STOCK_TOTALE: lambda company, user:
        _compute_valeur_stock_totale(company),
}


def _resolve_representative_user(company):
    """Un utilisateur actif de la société pour porter le scope des selectors
    qui exigent un ``user`` (ex. ``balance_agee_rows``). Préfère un
    admin/responsable actif ; dégrade proprement à None (KPI ignoré) si
    aucun utilisateur exploitable."""
    from django.contrib.auth import get_user_model
    User = get_user_model()
    return (User.objects
            .filter(company=company, is_active=True)
            .order_by('id')
            .first())


def evaluate_kpi_alerte(alerte, *, now=None):
    """XPLT6 — évalue UNE alerte : calcule le KPI, compare au seuil, notifie
    au FRANCHISSEMENT (jamais en répétition tant que ``deja_notifie`` est
    vrai), et RÉ-ARME la dédup dès que la valeur repasse du bon côté.

    Renvoie ``(valeur, franchi, notifie)``. Ne lève jamais : une source
    manquante dégrade à ``valeur=None`` (jamais de franchissement)."""
    from django.utils import timezone

    computer = _KPI_COMPUTERS.get(alerte.kpi)
    if computer is None:
        return None, False, False

    user = _resolve_representative_user(alerte.company)
    if user is None:
        return None, False, False

    try:
        valeur = computer(alerte.company, user)
    except Exception:  # pragma: no cover - dégradation défensive
        valeur = None

    franchi = alerte.est_franchi(valeur)
    notifie = False

    if franchi and not alerte.deja_notifie:
        _notify_kpi_alerte(alerte, valeur)
        alerte.deja_notifie = True
        notifie = True
    elif not franchi and alerte.deja_notifie:
        # Repassé sous (ou au-dessus) le seuil → ré-arme pour la prochaine
        # notification au prochain re-franchissement.
        alerte.deja_notifie = False

    alerte.derniere_valeur = valeur
    alerte.derniere_evaluation_le = timezone.now() if now is None else now
    alerte.save(update_fields=[
        'deja_notifie', 'derniere_valeur', 'derniere_evaluation_le'])
    return valeur, franchi, notifie


def _notify_kpi_alerte(alerte, valeur):
    """Notifie les destinataires configurés (rôle legacy + utilisateurs
    précis). Réutilise ``apps.notifications.services.notify`` — best-effort,
    ne lève jamais."""
    from apps.notifications.services import notify
    from apps.notifications.models import EventType

    title = f'Alerte KPI : {alerte.get_kpi_display()}'
    body = (f'{alerte.get_kpi_display()} a franchi le seuil '
            f'({alerte.get_operateur_display()} {alerte.seuil}) : '
            f'valeur actuelle {valeur}.')

    recipients = list(alerte.destinataires_utilisateurs.all())
    if alerte.destinataire_role:
        from django.contrib.auth import get_user_model
        User = get_user_model()
        recipients += list(User.objects.filter(
            company=alerte.company, is_active=True,
            role_legacy=alerte.destinataire_role))

    seen_ids = set()
    for user in recipients:
        if user.id in seen_ids:
            continue
        seen_ids.add(user.id)
        try:
            notify(user, EventType.DIGEST, title, body=body,
                   company=alerte.company)
        except Exception:  # pragma: no cover - défensif, best-effort
            continue


def evaluate_all_kpi_alertes(now=None):
    """XPLT6 — évalue toutes les alertes ACTIVES de toutes les sociétés.

    Appelée par le job Beat quotidien. Chaque alerte est isolée (une erreur
    n'interrompt jamais les suivantes)."""
    results = []
    for alerte in KpiAlerte.objects.filter(actif=True).select_related('company'):
        try:
            valeur, franchi, notifie = evaluate_kpi_alerte(alerte, now=now)
            results.append({
                'alerte_id': alerte.id, 'valeur': valeur,
                'franchi': franchi, 'notifie': notifie,
            })
        except Exception:  # pragma: no cover - défensif
            continue
    return results


try:
    from celery import shared_task

    @shared_task(name='reporting.evaluate_kpi_alertes')
    def evaluate_kpi_alertes_task():
        """XPLT6 — tâche Beat quotidienne d'évaluation des alertes KPI."""
        evaluate_all_kpi_alertes()
except ImportError:  # pragma: no cover - celery absent en environnement de test
    pass
