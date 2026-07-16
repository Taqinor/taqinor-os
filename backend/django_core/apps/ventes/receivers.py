"""Récepteurs d'événements métier (M6).

Abonne ``ventes`` aux événements du bus ``core.events`` exposés par d'autres
apps/la fondation, pour réagir à un changement d'état sans import direct.
Câblé au démarrage par ``VentesConfig.ready()``.
"""
from django.db.models.signals import post_delete, post_save
from django.dispatch import receiver

from core.events import payment_captured, chantier_annule, effet_rejete


# ── QX24 — cohérence de l'étude quand les lignes changent ────────────────────
def _qx24_refresh_etude_on_ligne_change(sender, instance, **kwargs):
    """QX24 — à chaque save/delete d'une ``LigneDevis``, recalcule le payback
    dérivé de l'étude pour qu'il reste cohérent avec le total courant.

    Best-effort ; ne bloque jamais une écriture de ligne. No-op si le devis lié
    n'a pas d'économies stockées (rien à dériver)."""
    devis = getattr(instance, 'devis', None)
    if devis is None:
        return
    try:
        from . import services as ventes_services
        ventes_services.refresh_etude_consistency(devis)
    except Exception:  # noqa: BLE001 — jamais bloquant
        pass


def _qx24_refresh_etude_on_devis_change(sender, instance, created, update_fields,
                                        **kwargs):
    """QX24 — recalcule le payback quand la REMISE GLOBALE d'un devis change.

    Anti-récursion : ``refresh_etude_consistency`` sauvegarde le devis avec
    ``update_fields=['etude_params']`` — on ignore donc tout save dont les
    champs mis à jour ne contiennent PAS ``remise_globale`` (le save interne du
    correctif n'y touche jamais), ce qui coupe la boucle."""
    if created:
        return
    # Ne réagit qu'à un changement EXPLICITE de remise_globale (jamais au save
    # interne du correctif qui n'écrit que etude_params → pas de récursion).
    if update_fields is None or 'remise_globale' not in set(update_fields):
        return
    try:
        from . import services as ventes_services
        ventes_services.refresh_etude_consistency(instance)
    except Exception:  # noqa: BLE001
        pass


def _register_qx24_signals():
    from .models import Devis, LigneDevis
    post_save.connect(
        _qx24_refresh_etude_on_ligne_change, sender=LigneDevis,
        dispatch_uid='ventes_qx24_ligne_saved')
    post_delete.connect(
        _qx24_refresh_etude_on_ligne_change, sender=LigneDevis,
        dispatch_uid='ventes_qx24_ligne_deleted')
    post_save.connect(
        _qx24_refresh_etude_on_devis_change, sender=Devis,
        dispatch_uid='ventes_qx24_devis_saved')


@receiver(chantier_annule, dispatch_uid="ventes_alert_on_chantier_annule")
def _alert_devis_on_chantier_annule(sender, installation, user, company,
                                    **kwargs):
    """YSERV9 — à l'annulation d'un chantier (``apps.installations``), pose
    une activité/alerte (NOTE) sur le devis lié pour que le responsable
    décide avoir vs retenue sur un acompte déjà encaissé.

    NE change JAMAIS de statut (devis/facture restent intacts — règle #4,
    STATUT PRESERVATION) : simple note au chatter. No-op si le chantier n'a
    pas de devis lié (rien à signaler)."""
    from .models import Devis, DevisActivity

    devis_id = getattr(installation, 'devis_id', None)
    if not devis_id:
        return
    devis = Devis.objects.filter(id=devis_id, company=company).first()
    if devis is None:
        return
    ref = getattr(installation, 'reference', installation.pk)
    DevisActivity.objects.create(
        company=company, devis=devis, kind=DevisActivity.Kind.NOTE,
        user=user,
        body=(f'Chantier {ref} annulé — vérifier un éventuel avoir/retenue '
              "sur l'acompte encaissé."))


@receiver(effet_rejete, dispatch_uid="ventes_reopen_facture_on_effet_rejete")
def _reopen_facture_on_effet_rejete(sender, effet, paiement_id, frais,
                                    company, **kwargs):
    """YLEDG10 — un effet À RECEVOIR (chèque client) rejeté par la banque
    route vers le rejet de paiement existant (YLEDG5,
    ``services.rejeter_paiement``) : rouvre la facture, trace les frais,
    émet ``paiement_rejete`` (que compta consomme déjà pour délettrer,
    YLEDG6). Idempotent (``rejeter_paiement`` refuse un 2ᵉ rejet du même
    paiement — best-effort, ne remonte jamais d'exception ici). No-op si le
    paiement n'existe plus / n'est pas de cette société."""
    from .models import Paiement
    from . import services as ventes_services

    paiement = Paiement.objects.filter(
        id=paiement_id, company=company).first()
    if paiement is None or paiement.statut == Paiement.Statut.REJETE:
        return
    try:
        ventes_services.rejeter_paiement(
            paiement=paiement,
            motif=f"Chèque rejeté (effet #{effet.id})",
            frais=frais or None)
    except ventes_services.PaiementRejectError:
        pass


@receiver(payment_captured, dispatch_uid="ventes_materialize_paiement_on_payment_captured")
def _materialize_paiement_on_payment_captured(sender, transaction, company, **kwargs):
    """YLEDG12 — une transaction carte CAPTURÉE (FG370, core/payment.py)
    matérialise un ``Paiement`` si elle cible une ``Facture`` de la même
    société.

    ``core.PaymentTransaction`` documente déjà cette promesse (« pour que
    l'app comptable rapproche vers Paiement ») mais rien ne l'abonnait — sans
    passerelle carte configurée, ``payment_captured`` n'est jamais émis, donc
    ce récepteur reste no-op. Idempotent par référence externe (une
    transaction = un paiement, jamais deux) : réutilise le même bornage que
    le webhook PaymentLink (jamais de sur-paiement). Cross-company refusé
    (silencieusement ignoré — la cible appartient à une autre société)."""
    from decimal import Decimal

    from .models import Facture, Paiement

    target = getattr(transaction, 'target', None)
    if not isinstance(target, Facture):
        return
    if target.company_id != company.id:
        return
    if target.statut == Facture.Statut.ANNULEE:
        return

    external_ref = (transaction.external_ref or '')[:120]
    # Idempotence : une transaction déjà matérialisée en Paiement ne l'est
    # jamais deux fois (recapture webhook, ré-émission du signal…).
    if external_ref and Paiement.objects.filter(
            facture=target, reference=external_ref,
            mode=Paiement.Mode.CARTE).exists():
        return

    from django.db import transaction as db_transaction
    from django.utils import timezone

    with db_transaction.atomic():
        locked = Facture.objects.select_for_update().get(pk=target.pk)
        if locked.statut == Facture.Statut.ANNULEE:
            return
        reste = locked.montant_du
        montant = transaction.montant
        if montant > reste:
            montant = reste
        if montant <= Decimal('0'):
            return
        Paiement.objects.create(
            company=locked.company,
            facture=locked,
            montant=montant,
            date_paiement=timezone.localdate(),
            mode=Paiement.Mode.CARTE,
            reference=external_ref,
            note='Paiement carte en ligne (transaction capturée).',
        )
        locked.refresh_from_db()
        if locked.montant_du <= Decimal('0') \
                and locked.statut != Facture.Statut.ANNULEE:
            locked.statut = Facture.Statut.PAYEE
            locked.save(update_fields=['statut'])
            from core.events import facture_paid
            facture_paid.send(
                sender=Facture, facture=locked, montant=montant,
                company=locked.company)
