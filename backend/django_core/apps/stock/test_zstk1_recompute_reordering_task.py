"""ZSTK1 — Action planifiée : recompute réappro + alertes de rupture (cron).

Couvre :
  * un produit sous seuil déclenche exactement UNE notification datée pour
    la société (aucun produit sous seuil = aucune notif) ;
  * idempotence : lancer la tâche deux fois le même jour ne notifie pas deux
    fois ;
  * aucun BCF n'est créé automatiquement (suggestion seulement) ;
  * multi-tenant : les sociétés sont isolées (un produit bas dans l'une ne
    fait pas notifier l'autre).

Run:
    python manage.py test \
        apps.stock.test_zstk1_recompute_reordering_task -v 2
"""
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase

from authentication.models import Company
from apps.roles.models import Role
from apps.stock.models import BonCommandeFournisseur, Produit
from apps.stock.tasks import recompute_reordering_task
from apps.notifications.models import Notification, EventType

User = get_user_model()


def _company(slug):
    return Company.objects.create(nom=slug, slug=slug)


def _user(company, username, permissions=None):
    role = Role.objects.create(
        company=company, nom=f'r-{username}', permissions=permissions or [])
    return User.objects.create_user(
        username=username, password='x', company=company, role=role,
        role_legacy='responsable')


class Zstk1Base(TestCase):
    def setUp(self):
        self.company = _company('zstk1-co')
        self.user = _user(self.company, 'zstk1-user')


class TestRecomputeReordering(Zstk1Base):
    def test_produit_sous_seuil_declenche_une_notification(self):
        Produit.objects.create(
            company=self.company, nom='Câble ZSTK1', sku='CAB-ZSTK1',
            prix_vente=Decimal('50'), quantite_stock=2, seuil_alerte=10)
        result = recompute_reordering_task()
        self.assertEqual(result[self.company.id], 1)
        notifs = Notification.objects.filter(
            company=self.company, event_type=EventType.STOCK_LOW)
        self.assertEqual(notifs.count(), 1)

    def test_aucun_produit_sous_seuil_aucune_notif(self):
        Produit.objects.create(
            company=self.company, nom='Câble haut ZSTK1', sku='CAB-ZSTK1H',
            prix_vente=Decimal('50'), quantite_stock=100, seuil_alerte=10)
        result = recompute_reordering_task()
        self.assertEqual(result[self.company.id], 0)
        self.assertEqual(
            Notification.objects.filter(
                company=self.company,
                event_type=EventType.STOCK_LOW).count(), 0)

    def test_idempotent_deux_appels_meme_jour(self):
        Produit.objects.create(
            company=self.company, nom='Visserie ZSTK1', sku='VIS-ZSTK1',
            prix_vente=Decimal('10'), quantite_stock=1, seuil_alerte=5)
        recompute_reordering_task()
        result2 = recompute_reordering_task()
        self.assertEqual(result2[self.company.id], 0)
        self.assertEqual(
            Notification.objects.filter(
                company=self.company,
                event_type=EventType.STOCK_LOW).count(), 1)

    def test_aucun_bcf_cree_automatiquement(self):
        Produit.objects.create(
            company=self.company, nom='Onduleur ZSTK1', sku='OND-ZSTK1',
            prix_vente=Decimal('2000'), quantite_stock=0, seuil_alerte=5)
        recompute_reordering_task()
        self.assertEqual(
            BonCommandeFournisseur.objects.filter(
                company=self.company).count(), 0)


class TestMultiTenant(Zstk1Base):
    def test_societes_isolees(self):
        autre = _company('zstk1-autre')
        _user(autre, 'zstk1-autre-user')
        Produit.objects.create(
            company=self.company, nom='Panneau ZSTK1', sku='PAN-ZSTK1',
            prix_vente=Decimal('2000'), quantite_stock=1, seuil_alerte=10)
        # `autre` n'a aucun produit sous seuil.
        result = recompute_reordering_task()
        self.assertEqual(result[self.company.id], 1)
        self.assertEqual(result[autre.id], 0)
        self.assertEqual(
            Notification.objects.filter(company=autre).count(), 0)
