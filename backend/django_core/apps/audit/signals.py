"""Capture CRUD + connexion pour le Journal d'activité (Feature G).

Branché sur ``post_save``/``post_delete`` des modèles métier suivis, plus les
connexions/échecs. Ne journalise QUE pendant une requête (voir ``recorder``) :
les écritures ORM hors requête (migrations, seed, tests directs) sont ignorées,
donc rien ne ralentit ni n'interfère avec ces contextes. Best-effort : aucune
exception ne remonte. Les changements de statut sont détectés via un cache posé
en ``pre_save`` (ancienne valeur) puis comparé en ``post_save``.
"""
from django.contrib.auth.signals import user_login_failed
from django.db.models.signals import post_delete, post_save, pre_save
from django.dispatch import receiver

from . import recorder
from .models import AuditLog

# (app_label, ModelName) des objets métier suivis.
TRACKED_MODELS = [
    ('crm', 'Lead'),
    ('crm', 'Client'),
    ('ventes', 'Devis'),
    ('ventes', 'Facture'),
    ('ventes', 'Avoir'),
    ('ventes', 'RelanceLog'),
    ('installations', 'Installation'),
    ('installations', 'Intervention'),
    ('sav', 'Ticket'),
    ('sav', 'Equipement'),
    ('stock', 'Produit'),
    ('stock', 'MouvementStock'),
    ('parametres', 'CompanyProfile'),
    ('authentication', 'CustomUser'),
    ('roles', 'Role'),
]

# Champs « statut » par modèle (libellé FR via get_<field>_display si dispo).
_STATUS_FIELDS = ('statut', 'stage')


def _status_field_name(instance):
    names = {f.name for f in instance._meta.concrete_fields}
    for cand in _STATUS_FIELDS:
        if cand in names:
            return cand
    return None


def _status_display(instance, field):
    getter = getattr(instance, f'get_{field}_display', None)
    if callable(getter):
        try:
            return getter()
        except Exception:
            pass
    return getattr(instance, field, '')


def _on_pre_save(sender, instance, **kwargs):
    if not recorder.in_request():
        return
    field = _status_field_name(instance)
    if not field or not instance.pk:
        return
    try:
        old = sender.objects.filter(pk=instance.pk).values_list(
            field, flat=True).first()
        instance._audit_old_status = old
    except Exception:
        instance._audit_old_status = None


def _on_post_save(sender, instance, created, **kwargs):
    if not recorder.in_request():
        return
    field = _status_field_name(instance)
    if created:
        recorder.record(AuditLog.Action.CREATE, instance=instance)
        return
    # Modification : statut changé → action dédiée, sinon « update ».
    old = getattr(instance, '_audit_old_status', None)
    if field is not None and old is not None:
        new = getattr(instance, field, None)
        if old != new:
            # Rendu lisible via les libellés de choix le cas échéant.
            old_label = dict(instance._meta.get_field(field).flatchoices).get(
                old, old)
            new_label = _status_display(instance, field)
            recorder.record(
                AuditLog.Action.STATUS, instance=instance,
                detail=f'Statut : {old_label} → {new_label}')
            return
    recorder.record(AuditLog.Action.UPDATE, instance=instance)


def _on_post_delete(sender, instance, **kwargs):
    if not recorder.in_request():
        return
    recorder.record(AuditLog.Action.DELETE, instance=instance)


@receiver(user_login_failed)
def _on_login_failed(sender, credentials=None, request=None, **kwargs):
    username = ''
    if credentials:
        username = credentials.get('username') or credentials.get(
            'email') or ''
    recorder.record(
        AuditLog.Action.LOGIN_FAILED, user=None, actor_username=username,
        detail='Tentative de connexion échouée')


def connect():
    """Branche les signaux sur tous les modèles suivis (appelé par AppConfig)."""
    from django.apps import apps as django_apps
    for app_label, model_name in TRACKED_MODELS:
        try:
            model = django_apps.get_model(app_label, model_name)
        except Exception:
            continue
        post_save.connect(_on_post_save, sender=model,
                          dispatch_uid=f'audit_save_{app_label}_{model_name}')
        post_delete.connect(_on_post_delete, sender=model,
                            dispatch_uid=f'audit_del_{app_label}_{model_name}')
        if _model_has_status(model):
            pre_save.connect(
                _on_pre_save, sender=model,
                dispatch_uid=f'audit_pre_{app_label}_{model_name}')


def _model_has_status(model):
    names = {f.name for f in model._meta.concrete_fields}
    return any(c in names for c in _STATUS_FIELDS)
