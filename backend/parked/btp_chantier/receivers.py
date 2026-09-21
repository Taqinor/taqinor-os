"""Abonnements de ``btp_chantier`` aux signaux d'autres apps.

NTCON5 — ré-ouvre automatiquement tout ``VisaDocument`` (statut → soumis)
quand une nouvelle ``ged.DocumentVersion`` est déposée sur le document visé.
Connexion PARESSEUSE via ``django.apps.apps.get_model`` dans
``connect_signals()`` (appelé depuis ``apps.py::ready()``) : aucun import
statique de ``ged.models`` (frontière cross-app, CLAUDE.md), signal Django
natif (``post_save``, ``sender=`` résolu par le registre d'apps) — ``ged``
n'émet pas encore d'événement dédié sur ``core/events.py`` pour ce cas.
"""
import logging

logger = logging.getLogger(__name__)


def _on_document_version_created(sender, instance, created, **kwargs):
    """NTCON5 — ré-ouvre les visas du document sur une NOUVELLE version."""
    if not created:
        return
    document_id = instance.document_id
    if not document_id:
        return
    try:
        from .services import resoumettre_visas_pour_document
        resoumettre_visas_pour_document(document_id)
    except Exception:  # pragma: no cover - défensif, jamais bloquant pour GED
        logger.warning(
            'btp_chantier: resoumission de visa échouée pour document %s',
            document_id, exc_info=True)


def _on_ordre_sous_traitance_pre_save(sender, instance, **kwargs):
    """NTCON16 — soft-guard PPSPS avant qu'un ``installations.
    OrdreSousTraitance`` (FG305) ne passe en ``en_cours``.

    Écrit ZÉRO ligne chez ``installations`` : on s'abonne au signal Django
    natif ``pre_save`` (connexion PARESSEUSE via le registre d'apps, comme
    NTCON5 pour ``ged.DocumentVersion``) et on refuse la TRANSITION vers
    ``en_cours`` quand le sous-traitant n'a pas signé le PPSPS validé du
    chantier. Ne se déclenche QUE sur la transition (un ordre déjà
    ``en_cours`` que l'on re-sauvegarde n'est jamais re-bloqué), et jamais
    pour un chantier sans PPSPS validé.
    """
    if getattr(instance, 'statut', None) != 'en_cours':
        return
    if not instance.pk:
        ancien_statut = None
    else:
        ancien_statut = sender.objects.filter(
            pk=instance.pk).values_list('statut', flat=True).first()
        if ancien_statut == 'en_cours':
            return  # déjà en cours : ce n'est pas une transition
    from .services import verifier_ppsps_avant_demarrage
    verifier_ppsps_avant_demarrage(
        company=getattr(instance, 'company', None),
        chantier_id=getattr(instance, 'chantier_id', None),
        sous_traitant_id=getattr(instance, 'sous_traitant_id', None),
        libelle_ordre=f'l\'ordre {getattr(instance, "reference", "") or ""}'.strip(),
    )


def connect_signals():
    """Point d'entrée appelé depuis ``BtpChantierConfig.ready()``."""
    from django.apps import apps as django_apps
    from django.db.models.signals import post_save, pre_save

    try:
        DocumentVersion = django_apps.get_model('ged', 'DocumentVersion')
    except LookupError:  # pragma: no cover - ged non installé (jamais en prod)
        DocumentVersion = None
    if DocumentVersion is not None:
        post_save.connect(
            _on_document_version_created, sender=DocumentVersion,
            dispatch_uid='btp_chantier_resoumission_visa')

    try:
        OrdreSousTraitance = django_apps.get_model(
            'installations', 'OrdreSousTraitance')
    except LookupError:  # pragma: no cover - installations toujours installé
        return
    pre_save.connect(
        _on_ordre_sous_traitance_pre_save, sender=OrdreSousTraitance,
        dispatch_uid='btp_chantier_guard_ppsps')


connect_signals()
