"""Récepteurs d'événements métier (M6).

Abonne ``ventes`` aux événements du bus ``core.events`` exposés par d'autres
apps/la fondation, pour réagir à un changement d'état sans import direct.
Câblé au démarrage par ``VentesConfig.ready()``.
"""
from django.dispatch import receiver

from core.events import payment_captured, chantier_annule


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
