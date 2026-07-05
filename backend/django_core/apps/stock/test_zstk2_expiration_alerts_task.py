"""ZSTK2 — Action planifiée : alertes de péremption des lots (cron).

Couvre :
  * un lot expirant sous la fenêtre configurée (défaut 30 j) déclenche une
    notification datée UNIQUE pour la société ;
  * un lot lointain (hors fenêtre) ne déclenche rien ;
  * fenêtre configurable (`CompanyProfile.jours_alerte_peremption`) ;
  * idempotence : lancer la tâche deux fois le même jour ne notifie pas
    deux fois ;
  * scoping : les sociétés sont isolées.

Run:
    python manage.py test apps.stock.test_zstk2_expiration_alerts_task -v 2
"""
from datetime import timedelta
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.utils import timezone

from authentication.models import Company
from apps.roles.models import Role
from apps.parametres.models import CompanyProfile
from apps.stock.models import (
    BonCommandeFournisseur, Fournisseur, LigneBonCommandeFournisseur,
    LigneReceptionFournisseur, Produit, ReceptionFournisseur,
)
from apps.stock.tasks import expiration_alerts_task
from apps.notifications.models import Notification, EventType

User = get_user_model()


def _company(slug):
    return Company.objects.create(nom=slug, slug=slug)


def _user(company, username):
    role = Role.objects.create(company=company, nom=f'r-{username}')
    return User.objects.create_user(
        username=username, password='x', company=company, role=role,
        role_legacy='responsable')


class Zstk2Base(TestCase):
    def setUp(self):
        self.company = _company('zstk2-co')
        self.user = _user(self.company, 'zstk2-user')
        self.fournisseur = Fournisseur.objects.create(
            company=self.company, nom='Fournisseur ZSTK2')
        self.produit = Produit.objects.create(
            company=self.company, nom='Batterie ZSTK2', sku='BAT-ZSTK2',
            prix_vente=Decimal('3000'))

    def _reception_avec_peremption(
            self, date_peremption, quantite=5,
            reference='REC-ZSTK2-0001'):
        bcf = BonCommandeFournisseur.objects.create(
            company=self.company, reference=f'BCF-{reference}',
            fournisseur=self.fournisseur,
            statut=BonCommandeFournisseur.Statut.ENVOYE)
        ligne = LigneBonCommandeFournisseur.objects.create(
            bon_commande=bcf, produit=self.produit, quantite=quantite,
            prix_achat_unitaire=Decimal('1000'), quantite_recue=quantite)
        rec = ReceptionFournisseur.objects.create(
            company=self.company, reference=reference, bon_commande=bcf,
            statut=ReceptionFournisseur.Statut.CONFIRME)
        LigneReceptionFournisseur.objects.create(
            reception=rec, ligne_commande=ligne, produit=self.produit,
            quantite=quantite, date_peremption=date_peremption)
        return rec


class TestFenetreDefaut(Zstk2Base):
    def test_lot_expirant_sous_30j_notifie(self):
        bientot = timezone.now().date() + timedelta(days=15)
        self._reception_avec_peremption(bientot)
        result = expiration_alerts_task()
        self.assertEqual(result[self.company.id], 1)
        notifs = Notification.objects.filter(
            company=self.company,
            event_type=EventType.STOCK_EXPIRATION_SOON)
        self.assertEqual(notifs.count(), 1)

    def test_lot_lointain_non_notifie(self):
        loin = timezone.now().date() + timedelta(days=200)
        self._reception_avec_peremption(loin)
        result = expiration_alerts_task()
        self.assertEqual(result.get(self.company.id, 0), 0)
        self.assertFalse(Notification.objects.filter(
            company=self.company,
            event_type=EventType.STOCK_EXPIRATION_SOON).exists())


class TestFenetreConfigurable(Zstk2Base):
    def test_fenetre_reduite_exclut_un_lot_hors_fenetre(self):
        profile = CompanyProfile.get(company=self.company)
        profile.jours_alerte_peremption = 10
        profile.save(update_fields=['jours_alerte_peremption'])
        dans_20j = timezone.now().date() + timedelta(days=20)
        self._reception_avec_peremption(dans_20j)
        result = expiration_alerts_task()
        self.assertEqual(result.get(self.company.id, 0), 0)

    def test_fenetre_elargie_inclut_un_lot(self):
        profile = CompanyProfile.get(company=self.company)
        profile.jours_alerte_peremption = 100
        profile.save(update_fields=['jours_alerte_peremption'])
        dans_60j = timezone.now().date() + timedelta(days=60)
        self._reception_avec_peremption(dans_60j)
        result = expiration_alerts_task()
        self.assertEqual(result[self.company.id], 1)


class TestIdempotence(Zstk2Base):
    def test_deux_lancements_meme_jour_une_seule_notif(self):
        bientot = timezone.now().date() + timedelta(days=15)
        self._reception_avec_peremption(bientot)
        expiration_alerts_task()
        expiration_alerts_task()
        notifs = Notification.objects.filter(
            company=self.company,
            event_type=EventType.STOCK_EXPIRATION_SOON)
        self.assertEqual(notifs.count(), 1)


class TestScopingSociete(Zstk2Base):
    def test_societes_isolees(self):
        autre = _company('zstk2-autre')
        _user(autre, 'zstk2-autre-user')
        bientot = timezone.now().date() + timedelta(days=15)
        self._reception_avec_peremption(bientot)
        result = expiration_alerts_task()
        self.assertEqual(result.get(autre.id, 0), 0)
        self.assertFalse(Notification.objects.filter(
            company=autre,
            event_type=EventType.STOCK_EXPIRATION_SOON).exists())
