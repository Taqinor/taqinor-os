"""Branchement du moteur d'automatisations sur les événements PROPRES de l'app.

On écoute ``post_save`` (et ``pre_save`` pour capter l'ancienne valeur) sur les
modèles existants — Lead, Devis, Facture, Installation, Equipement, Produit — et
on appelle ``engine.evaluate`` pour le bon ``TriggerType`` quand l'événement
correspondant se produit. Aucun courtier de messages : tout tourne en processus.

Best-effort ABSOLU : chaque handler enveloppe son travail dans try/except et ne
laisse JAMAIS une exception casser l'enregistrement d'origine. Aucune règle →
aucun effet.
"""
import logging

from django.db.models.signals import post_save, pre_save
from django.utils import timezone

from .engine import evaluate
from .models import TriggerType

logger = logging.getLogger(__name__)

_OLD = '_automation_old'


def _safe(fn):
    """Enveloppe un handler : best-effort, ne lève jamais."""
    def wrapper(*args, **kwargs):
        try:
            return fn(*args, **kwargs)
        except Exception:  # pragma: no cover - filet de sécurité
            logger.exception('automation: handler de signal échoué')
    return wrapper


# ── pre_save : mémorise l'ancienne valeur d'un champ surveillé ─────────────

def _cache_old(field):
    def handler(sender, instance, **kwargs):
        if not instance.pk:
            setattr(instance, _OLD, None)
            return
        try:
            old = sender.objects.filter(pk=instance.pk).values_list(
                field, flat=True).first()
        except Exception:
            old = None
        setattr(instance, _OLD, old)
    return _safe(handler)


# ── post_save handlers par modèle ──────────────────────────────────────────

def _lead_saved(sender, instance, created, **kwargs):
    old = getattr(instance, _OLD, None)
    new = getattr(instance, 'stage', None)
    if created or old == new:
        return
    evaluate(TriggerType.LEAD_STAGE_CHANGE, instance, instance.company,
             context={'new_stage': new, 'old_stage': old})


_lead_saved = _safe(_lead_saved)


def _devis_saved(sender, instance, created, **kwargs):
    old = getattr(instance, _OLD, None)
    new = getattr(instance, 'statut', None)
    # Déclenche quand le devis DEVIENT « accepté » (transition ou création).
    if new != 'accepte':
        return
    if not created and old == 'accepte':
        return
    evaluate(TriggerType.DEVIS_ACCEPTED, instance, instance.company)


_devis_saved = _safe(_devis_saved)


def _installation_saved(sender, instance, created, **kwargs):
    old = getattr(instance, _OLD, None)
    new = getattr(instance, 'statut', None)
    if old == new and not created:
        return
    evaluate(TriggerType.CHANTIER_STATUS, instance, instance.company,
             context={'new_statut': new, 'old_statut': old})


_installation_saved = _safe(_installation_saved)


def _facture_saved(sender, instance, created, **kwargs):
    # Facture en retard : échéance dépassée et pas payée. La détection fine
    # (balayage périodique) reste hors-ligne ; ici on réagit à un save qui
    # laisse la facture dans cet état.
    statut = getattr(instance, 'statut', None)
    echeance = getattr(instance, 'date_echeance', None)
    if statut == 'payee' or echeance is None:
        return
    # Bucket Africa/Casablanca : comparer à la date LOCALE, pas à la date UTC,
    # sinon FACTURE_OVERDUE peut se déclencher un jour trop tôt/tard à minuit.
    if echeance >= timezone.localdate():
        return
    old = getattr(instance, _OLD, None)
    # Évite de re-déclencher si déjà en retard au save précédent (même statut).
    if not created and old == statut:
        return
    evaluate(TriggerType.FACTURE_OVERDUE, instance, instance.company)


_facture_saved = _safe(_facture_saved)


def _equipement_saved(sender, instance, created, **kwargs):
    # Garantie proche expiration : un balayage périodique appellerait
    # evaluate(WARRANTY_EXPIRING, ...). Ici on n'agit pas au save courant pour
    # éviter le bruit ; le hook reste disponible via le moteur.
    return


_equipement_saved = _safe(_equipement_saved)


def _produit_saved(sender, instance, created, **kwargs):
    seuil = getattr(instance, 'seuil_alerte', 0) or 0
    qte = getattr(instance, 'quantite_stock', 0) or 0
    if seuil <= 0 or qte > seuil:
        return
    old = getattr(instance, _OLD, None)
    # Ne déclenche que lorsqu'on FRANCHIT le seuil (pas à chaque save sous seuil).
    if not created and old is not None and old <= seuil:
        return
    evaluate(TriggerType.STOCK_BELOW_THRESHOLD, instance, instance.company)


_produit_saved = _safe(_produit_saved)


def connect():
    """Branche tous les signaux (appelé par AutomationConfig.ready())."""
    from django.apps import apps as django_apps

    def model(app_label, name):
        try:
            return django_apps.get_model(app_label, name)
        except Exception:
            return None

    Lead = model('crm', 'Lead')
    if Lead is not None:
        pre_save.connect(_cache_old('stage'), sender=Lead,
                         dispatch_uid='automation_pre_lead')
        post_save.connect(_lead_saved, sender=Lead,
                          dispatch_uid='automation_post_lead')

    Devis = model('ventes', 'Devis')
    if Devis is not None:
        pre_save.connect(_cache_old('statut'), sender=Devis,
                         dispatch_uid='automation_pre_devis')
        post_save.connect(_devis_saved, sender=Devis,
                          dispatch_uid='automation_post_devis')

    Installation = model('installations', 'Installation')
    if Installation is not None:
        pre_save.connect(_cache_old('statut'), sender=Installation,
                         dispatch_uid='automation_pre_installation')
        post_save.connect(_installation_saved, sender=Installation,
                          dispatch_uid='automation_post_installation')

    Facture = model('facturation', 'Facture')  # ODX17 — déplacé de ventes
    if Facture is not None:
        pre_save.connect(_cache_old('statut'), sender=Facture,
                         dispatch_uid='automation_pre_facture')
        post_save.connect(_facture_saved, sender=Facture,
                          dispatch_uid='automation_post_facture')

    Equipement = model('sav', 'Equipement')
    if Equipement is not None:
        post_save.connect(_equipement_saved, sender=Equipement,
                          dispatch_uid='automation_post_equipement')

    Produit = model('stock', 'Produit')
    if Produit is not None:
        pre_save.connect(_cache_old('quantite_stock'), sender=Produit,
                         dispatch_uid='automation_pre_produit')
        post_save.connect(_produit_saved, sender=Produit,
                          dispatch_uid='automation_post_produit')
