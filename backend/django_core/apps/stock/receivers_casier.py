"""NTWMS39 — récepteur qui alimente l'historique de casier.

Branché depuis ``StockConfig.ready()``. Le modèle source
(``installations.BinLocation``) est résolu par ``apps.get_model`` : aucun
import du module de modèles d'``installations`` (frontière inter-apps).

Best-effort ABSOLU : une erreur de journalisation ne doit JAMAIS empêcher un
magasinier d'enregistrer son casier.
"""
import logging

logger = logging.getLogger(__name__)

_CONNECTE = False


def _valeur(obj, champ):
    return '' if getattr(obj, champ, None) is None else str(getattr(obj, champ))


def _pre_save_bin(sender, instance, **kwargs):
    """Mémorise l'état AVANT écriture (les anciennes valeurs sont perdues
    après le save)."""
    if not instance.pk:
        instance._ntwms39_avant = None
        return
    try:
        instance._ntwms39_avant = sender.objects.filter(
            pk=instance.pk).values(
                'code', 'zone', 'allee', 'casier', 'ordre', 'categorie_id',
                'archived').first()
    except Exception:  # pragma: no cover — défensif
        instance._ntwms39_avant = None


def _post_save_bin(sender, instance, created, **kwargs):
    from .models_historique_casier import CHAMPS_SUIVIS, HistoriqueCasier

    company_id = getattr(instance, 'company_id', None)
    if company_id is None:
        # Le journal est multi-tenant : sans société, on ne journalise pas
        # (plutôt que d'inventer un rattachement).
        return
    try:
        if created:
            HistoriqueCasier.objects.create(
                company_id=company_id, bin=instance,
                action=HistoriqueCasier.Action.CREATION,
                nouvelle_valeur=_valeur(instance, 'code')[:200])
            return
        avant = getattr(instance, '_ntwms39_avant', None)
        if not avant:
            return
        lignes = []
        for champ in CHAMPS_SUIVIS:
            ancien = '' if avant.get(champ) is None else str(avant.get(champ))
            nouveau = _valeur(instance, champ)
            if ancien != nouveau:
                lignes.append(HistoriqueCasier(
                    company_id=company_id, bin=instance,
                    action=HistoriqueCasier.Action.MODIFICATION,
                    champ=champ, ancienne_valeur=ancien[:200],
                    nouvelle_valeur=nouveau[:200]))
        if bool(avant.get('archived')) != bool(
                getattr(instance, 'archived', False)):
            lignes.append(HistoriqueCasier(
                company_id=company_id, bin=instance,
                action=(HistoriqueCasier.Action.ARCHIVAGE
                        if instance.archived
                        else HistoriqueCasier.Action.REACTIVATION),
                champ='archived',
                ancienne_valeur=str(bool(avant.get('archived'))),
                nouvelle_valeur=str(bool(instance.archived))))
        if lignes:
            HistoriqueCasier.objects.bulk_create(lignes)
    except Exception:  # pragma: no cover — best-effort, jamais bloquant
        logger.exception('NTWMS39 journalisation casier impossible (bin=%s)',
                         getattr(instance, 'pk', None))


def register_historique_casier():
    """Branche les deux récepteurs UNE seule fois (idempotent)."""
    global _CONNECTE
    if _CONNECTE:
        return
    from django.apps import apps as django_apps
    from django.db.models.signals import post_save, pre_save

    try:
        modele = django_apps.get_model('installations', 'BinLocation')
    except Exception:  # pragma: no cover — app absente : rien à journaliser
        return
    pre_save.connect(_pre_save_bin, sender=modele,
                     dispatch_uid='stock_ntwms39_pre_save_bin')
    post_save.connect(_post_save_bin, sender=modele,
                      dispatch_uid='stock_ntwms39_post_save_bin')
    _CONNECTE = True
