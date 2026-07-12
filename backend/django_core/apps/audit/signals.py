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
    # FG15 — écritures « argent » : bon de commande client + encaissements.
    ('ventes', 'BonCommande'),
    ('ventes', 'Paiement'),
    ('installations', 'Installation'),
    ('installations', 'Intervention'),
    ('sav', 'Ticket'),
    ('sav', 'Equipement'),
    # FG15 — contrat de maintenance (engagement récurrent facturable).
    ('sav', 'ContratMaintenance'),
    ('stock', 'Produit'),
    ('stock', 'MouvementStock'),
    # FG15 — chaîne achats fournisseur (argent sortant : commande → réception
    # → facture → paiement).
    ('stock', 'BonCommandeFournisseur'),
    ('stock', 'ReceptionFournisseur'),
    ('stock', 'FactureFournisseur'),
    ('stock', 'PaiementFournisseur'),
    ('parametres', 'CompanyProfile'),
    ('authentication', 'CustomUser'),
    ('roles', 'Role'),
    # FG15 — sécurité : émission/révocation de clés API et de webhooks.
    ('publicapi', 'ApiKey'),
    ('publicapi', 'Webhook'),
    # XPAI23 — piste d'audit paie : constantes sociales/barèmes/rubriques/
    # profils/avances/arrêts/périodes sont des écritures « argent » (FG15).
    ('paie', 'ParametrePaie'),
    ('paie', 'BaremeIR'),
    ('paie', 'Rubrique'),
    ('paie', 'ProfilPaie'),
    ('paie', 'RubriqueEmploye'),
    ('paie', 'AvanceSalarie'),
    ('paie', 'SaisieArret'),
    ('paie', 'PeriodePaie'),
    # VX241(b) — KbArticle (parent est on_delete=CASCADE : une suppression
    # cascade tout un sous-arbre sans une seule ligne au Journal aujourd'hui)
    # et Timesheet (heures facturables d'un projet) n'étaient dans AUCUN des
    # deux mécanismes de traçabilité (ni TRACKED_MODELS, ni un destroy() gardé
    # dédié) — post_save/post_delete génériques suffisent ici, pas de garde
    # d'usage particulier à écrire.
    ('kb', 'KbArticle'),
    ('gestion_projet', 'Timesheet'),
]

# Champs « statut » par modèle (libellé FR via get_<field>_display si dispo).
_STATUS_FIELDS = ('statut', 'stage')

# VX241(c) — ``changes=`` (diff structuré, consommé par
# ``selectors.reconstruct_as_of``) n'était peuplé qu'à 2 call-sites explicites
# dans tout le backend (le reste des lignes UPDATE avaient ``changes=None``).
# Champs de bookkeeping exclus du diff automatique : ils changent à CHAQUE
# sauvegarde sans jamais représenter un changement métier lisible.
_DIFF_NOISE_FIELDS = {'date_modification', 'updated_at', 'modified_at'}
# Longueur max d'une valeur stockée dans le diff — évite qu'un gros champ
# texte (ex. ``KbArticle.corps``) ne fasse exploser ``AuditLog.changes`` à
# chaque édition (même esprit que la troncature de ``object_repr`` à 255).
_DIFF_VALUE_MAXLEN = 300


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


def _truncate_diff_value(value):
    text = '' if value is None else str(value)
    if len(text) > _DIFF_VALUE_MAXLEN:
        return text[:_DIFF_VALUE_MAXLEN] + '…'
    return text


def _diff_from_snapshot(instance, old_values):
    """Diff structuré ``[{field, old, new}, ...]`` entre le snapshot posé en
    ``pre_save`` (``old_values``, dict ``{attname: valeur brute DB}``) et
    l'état courant de ``instance`` — ou ``None`` si rien d'exploitable
    (création, snapshot absent, ou aucun champ concret changé)."""
    if not old_values:
        return None
    changes = []
    for f in instance._meta.concrete_fields:
        name = f.attname
        if name in _DIFF_NOISE_FIELDS or name not in old_values:
            continue
        old = old_values.get(name)
        new = getattr(instance, name, None)
        if old == new:
            continue
        changes.append({
            'field': f.name,
            'old': _truncate_diff_value(old),
            'new': _truncate_diff_value(new),
        })
    return changes or None


def _on_pre_save(sender, instance, **kwargs):
    if not recorder.in_request():
        return
    if not instance.pk:
        return
    field = _status_field_name(instance)
    if field:
        try:
            old = sender.objects.filter(pk=instance.pk).values_list(
                field, flat=True).first()
            instance._audit_old_status = old
        except Exception:
            instance._audit_old_status = None
    # Snapshot complet du ROW (toutes les colonnes concrètes) — UNE requête
    # par sauvegarde, réutilisée en post_save pour le diff automatique.
    try:
        instance._audit_old_values = sender.objects.filter(
            pk=instance.pk).values().first()
    except Exception:
        instance._audit_old_values = None


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
            # ARC16 (pilote #2) — passe par l'entonnoir : ligne AuditLog 1:1
            # (action STATUS, même instance, même détail) + diff structuré
            # ``statut: old → new``. ``chatter=False`` : ce signal générique
            # couvre TOUS les modèles suivis ; le chatter reste géré par chaque
            # app (comportement inchangé, aucune note générique en plus).
            recorder.record_field_change(
                instance, field, old_label, new_label,
                action=AuditLog.Action.STATUS, chatter=False,
                detail=f'Statut : {old_label} → {new_label}')
            return
    changes = _diff_from_snapshot(
        instance, getattr(instance, '_audit_old_values', None))
    recorder.record(AuditLog.Action.UPDATE, instance=instance, changes=changes)


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
        # VX241(c) — branché INCONDITIONNELLEMENT (avant : seulement si le
        # modèle a un champ statut) : le snapshot complet du row sert
        # désormais aussi au diff automatique ``changes=`` de CHAQUE UPDATE,
        # pas seulement au changement de statut.
        pre_save.connect(
            _on_pre_save, sender=model,
            dispatch_uid=f'audit_pre_{app_label}_{model_name}')
