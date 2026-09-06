"""Branchement du moteur d'automatisations sur les événements PROPRES de l'app.

Deux qualités de branchement, et il faut savoir laquelle on lit :

1. **Le bus d'événements métier (`core.events`, règle M6) — la SEULE source qui
   garantit qu'un contrôle métier a eu lieu.** Un événement du bus est publié
   par le SERVICE propriétaire, au bout de son chemin gardé. AUD823 y a migré
   ``DEVIS_ACCEPTED`` : il s'abonne à ``core.events.devis_accepted``, émis
   exclusivement par ``apps.ventes.domain.cycle_vie`` au terme d'une
   acceptation VALIDÉE (option choisie, sœurs effondrées, aval en transaction).

2. **Les `post_save` bruts sur les modèles** — Lead, Facture, Installation,
   Equipement, Produit. Ils réagissent à un CHANGEMENT D'ÉTAT OBSERVÉ, pas à
   une décision métier : ils tirent pour N'IMPORTE QUEL chemin d'écriture, y
   compris un PATCH non gardé, un import, une commande de shell ou une
   correction manuelle.

   ⚠️ AUD823 — CE N'EST PAS UNE GARANTIE DE LÉGITIMITÉ MÉTIER. Ces cinq
   déclencheurs restent branchés sur ``post_save`` parce qu'aucun événement
   ``core.events`` PROPRIÉTAIRE ne leur correspond aujourd'hui. Toute règle
   bâtie dessus doit être considérée comme « le champ vaut X maintenant », pas
   comme « la transition métier a été validée ». Dès qu'un domaine publie
   l'événement équivalent sur le bus, MIGRER le déclencheur ici plutôt que
   d'ajouter une garde locale — c'est ce qu'a fait ``DEVIS_ACCEPTED``.

   Le défaut concret que cette distinction ferme : ``_devis_saved`` s'exécutait
   pour TOUT ``.save()`` laissant ``statut='accepte'``. Une règle « Lien
   WhatsApp à l'acceptation d'un devis » envoyait donc une confirmation au
   client alors qu'AUCUN contrôle métier n'avait eu lieu — et le défaut se
   rouvrait à chaque future écriture non gardée.

Aucun courtier de messages : tout tourne en processus. Best-effort ABSOLU :
chaque handler enveloppe son travail dans try/except et ne laisse JAMAIS une
exception casser l'enregistrement d'origine. Aucune règle → aucun effet.
"""
import logging

from django.db.models.signals import post_save, pre_save
from django.utils import timezone

from core.events import devis_accepted

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


# ── AUD823 — DEVIS_ACCEPTED : abonné au BUS, plus au post_save brut ────────

def _on_devis_accepted(sender, devis, user=None, ancien_statut=None, **kwargs):
    """Évalue ``DEVIS_ACCEPTED`` sur l'ÉVÉNEMENT MÉTIER, jamais sur un save.

    Avant AUD823, ``_devis_saved`` écoutait ``post_save`` et tirait pour TOUT
    ``.save()`` laissant ``statut='accepte'`` — donc aussi pour un PATCH brut,
    un import ou une correction en base, sans qu'aucun contrôle métier n'ait eu
    lieu. Désormais seul ``core.events.devis_accepted`` déclenche : il est émis
    par l'UNIQUE chemin gardé d'acceptation
    (``apps.ventes.domain.cycle_vie``), au terme de la validation complète.

    ``ancien_statut`` est passé en contexte pour que les conditions de règle
    puissent le lire (aucune règle existante n'en dépend : ajout pur).
    """
    company = getattr(devis, 'company', None)
    if company is None:
        return
    evaluate(TriggerType.DEVIS_ACCEPTED, devis, company, user=user,
             context={'ancien_statut': ancien_statut,
                      'nouveau_statut': getattr(devis, 'statut', None)})


_on_devis_accepted = _safe(_on_devis_accepted)


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

    # AUD823 — le Devis n'est PLUS écouté par post_save : `DEVIS_ACCEPTED`
    # s'abonne au bus M6, seule source qui prouve qu'une acceptation VALIDÉE a
    # eu lieu (l'ancien pre_save/post_save tirait pour n'importe quel chemin
    # d'écriture, y compris un PATCH brut).
    devis_accepted.connect(
        _on_devis_accepted, dispatch_uid='automation_on_devis_accepted')

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
