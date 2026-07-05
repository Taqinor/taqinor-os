"""ZPUR7 — Brouillon de relance programmé + compteur pour les BCF en retard.

Couvre :
  * société non gated (relance_bcf_actif=False) : no-op total ;
  * société gated : un BCF en retard voit un brouillon de relance proposé
    (notification distincte BCF_RELANCE_PROPOSEE) + `nb_relances` incrémenté ;
  * jamais de doublon avec l'alerte buyer XPUR7 (BCF_LATE) ;
  * idempotence : deux lancements le même jour ne proposent pas deux fois ;
  * un BCF non en retard (statut brouillon/reçu/dans les temps) n'est jamais
    relancé.

Run:
    python manage.py test apps.stock.test_zpur7_relance_bcf -v 2
"""
from datetime import timedelta
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.utils import timezone

from authentication.models import Company
from apps.roles.models import Role
from apps.stock.models import (
    AchatsParametres, BonCommandeFournisseur, Fournisseur,
    LigneBonCommandeFournisseur, Produit,
)
from apps.stock.tasks import relancer_bcf_en_retard_task
from apps.notifications.models import Notification, EventType

User = get_user_model()


def _company(slug):
    return Company.objects.create(nom=slug, slug=slug)


def _user(company, username):
    role = Role.objects.create(company=company, nom=f'r-{username}')
    return User.objects.create_user(
        username=username, password='x', company=company, role=role,
        role_legacy='responsable')


class Zpur7Base(TestCase):
    def setUp(self):
        self.company = _company('zpur7-co')
        self.user = _user(self.company, 'zpur7-user')
        self.fournisseur = Fournisseur.objects.create(
            company=self.company, nom='Fournisseur ZPUR7',
            telephone='0600000000')
        self.produit = Produit.objects.create(
            company=self.company, nom='Onduleur ZPUR7', sku='OND-ZPUR7',
            prix_vente=Decimal('2000'), prix_achat=Decimal('1000'))

    def _bcf_en_retard(self, reference='BCF-ZPUR7-0001'):
        hier = timezone.now().date() - timedelta(days=5)
        bcf = BonCommandeFournisseur.objects.create(
            company=self.company, reference=reference,
            fournisseur=self.fournisseur,
            statut=BonCommandeFournisseur.Statut.ENVOYE,
            date_livraison_prevue=hier)
        LigneBonCommandeFournisseur.objects.create(
            bon_commande=bcf, produit=self.produit, quantite=10,
            prix_achat_unitaire=Decimal('1000'), quantite_recue=0)
        return bcf


class TestGateOff(Zpur7Base):
    def test_sans_parametrage_no_op(self):
        self._bcf_en_retard()
        result = relancer_bcf_en_retard_task()
        self.assertEqual(result.get(self.company.id, 0), 0)
        self.assertFalse(Notification.objects.filter(
            company=self.company,
            event_type=EventType.BCF_RELANCE_PROPOSEE).exists())

    def test_parametrage_explicitement_off_no_op(self):
        AchatsParametres.objects.create(
            company=self.company, relance_bcf_actif=False)
        self._bcf_en_retard()
        result = relancer_bcf_en_retard_task()
        self.assertEqual(result.get(self.company.id, 0), 0)


class TestGateOn(Zpur7Base):
    def setUp(self):
        super().setUp()
        AchatsParametres.objects.create(
            company=self.company, relance_bcf_actif=True)

    def test_bcf_en_retard_propose_relance_et_incremente_compteur(self):
        bcf = self._bcf_en_retard()
        result = relancer_bcf_en_retard_task()
        self.assertEqual(result[self.company.id], 1)
        bcf.refresh_from_db()
        self.assertEqual(bcf.nb_relances, 1)
        notifs = Notification.objects.filter(
            company=self.company,
            event_type=EventType.BCF_RELANCE_PROPOSEE)
        self.assertEqual(notifs.count(), 1)
        self.assertIn(bcf.reference, notifs.first().body)

    def test_jamais_de_doublon_avec_alerte_buyer_bcf_late(self):
        self._bcf_en_retard()
        relancer_bcf_en_retard_task()
        self.assertFalse(Notification.objects.filter(
            company=self.company, event_type=EventType.BCF_LATE).exists())

    def test_idempotent_meme_jour(self):
        bcf = self._bcf_en_retard()
        relancer_bcf_en_retard_task()
        relancer_bcf_en_retard_task()
        bcf.refresh_from_db()
        self.assertEqual(bcf.nb_relances, 1)
        notifs = Notification.objects.filter(
            company=self.company,
            event_type=EventType.BCF_RELANCE_PROPOSEE)
        self.assertEqual(notifs.count(), 1)

    def test_bcf_pas_en_retard_jamais_relance(self):
        demain = timezone.now().date() + timedelta(days=5)
        bcf = BonCommandeFournisseur.objects.create(
            company=self.company, reference='BCF-ZPUR7-0002',
            fournisseur=self.fournisseur,
            statut=BonCommandeFournisseur.Statut.ENVOYE,
            date_livraison_prevue=demain)
        LigneBonCommandeFournisseur.objects.create(
            bon_commande=bcf, produit=self.produit, quantite=5,
            prix_achat_unitaire=Decimal('1000'), quantite_recue=0)
        result = relancer_bcf_en_retard_task()
        self.assertEqual(result.get(self.company.id, 0), 0)
        bcf.refresh_from_db()
        self.assertEqual(bcf.nb_relances, 0)

    def test_bcf_brouillon_jamais_relance(self):
        hier = timezone.now().date() - timedelta(days=5)
        bcf = BonCommandeFournisseur.objects.create(
            company=self.company, reference='BCF-ZPUR7-0003',
            fournisseur=self.fournisseur,
            statut=BonCommandeFournisseur.Statut.BROUILLON,
            date_livraison_prevue=hier)
        LigneBonCommandeFournisseur.objects.create(
            bon_commande=bcf, produit=self.produit, quantite=5,
            prix_achat_unitaire=Decimal('1000'), quantite_recue=0)
        result = relancer_bcf_en_retard_task()
        self.assertEqual(result.get(self.company.id, 0), 0)
        bcf.refresh_from_db()
        self.assertEqual(bcf.nb_relances, 0)
