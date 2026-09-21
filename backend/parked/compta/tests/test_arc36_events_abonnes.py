"""Tests ARC36 — abonnés métier de facture_payee / bon_commande_cree /
abonnement_monitoring_resilie.

Couvre : ``facture_payee`` → lettrage compta du solde (idempotent avec le
chemin YLEDG6) + notification vendeur ; ``bon_commande_cree`` → notification
magasinier/managers (``resolve_recipients``) ; ``abonnement_monitoring_
resilie`` → coupe ``MonitoringConfig.enabled`` (apps/monitoring/receivers.py,
abonné par NOM de signal) ; retrait des 3 entrées d'``ALLOWED_UNCONSUMED``
(YEVNT7 vert) — ``facture_paid`` reste réservé (déprécié pour l'abonnement).
Comportements additifs uniquement : aucun statut document modifié.
"""
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings

from authentication.models import Company
from apps.compta.models import LigneEcriture
from apps.crm.models import Client
from apps.installations.models import Installation
from apps.monitoring.models import AbonnementMonitoring
from apps.monitoring.models import MonitoringConfig as ConfigSupervision
from apps.notifications.models import EventType, Notification
from apps.stock.models import Produit
from apps.ventes.models import BonCommande, Facture, LigneFacture, Paiement
from core import event_coverage
from core.events import (
    abonnement_monitoring_resilie, bon_commande_cree, facture_payee,
)

from apps.compta import receivers  # noqa: F401  (câblage ready())
from apps.monitoring import receivers as monitoring_receivers  # noqa: F401

User = get_user_model()


def make_company(slug, nom):
    return Company.objects.get_or_create(slug=slug, defaults={'nom': nom})[0]


class TestFacturePayeeLettrageCompta(TestCase):
    """facture_payee → compta lettre le 3421 soldé (sans paiement_enregistre)."""

    def setUp(self):
        self.company = make_company('arc36-lettrage', 'ARC36 Lettrage')
        self.cl = Client.objects.create(
            company=self.company, nom='Client', prenom='A36',
            email='arc36@example.com', telephone='+212600000361')
        self.produit = Produit.objects.create(
            company=self.company, nom='Panneau', sku='PAN-ARC36',
            prix_vente=Decimal('1000'), quantite_stock=10,
            tva=Decimal('20.00'))
        self.facture = Facture.objects.create(
            company=self.company, reference='FAC-ARC36-0001',
            client=self.cl, statut=Facture.Statut.EMISE,
            taux_tva=Decimal('20.00'))
        LigneFacture.objects.create(
            facture=self.facture, produit=self.produit,
            designation='Panneau', quantite=Decimal('1'),
            prix_unitaire=Decimal('1000'), taux_tva=Decimal('20.00'))

    @override_settings(COMPTA_AUTO_ECRITURES=True)
    def test_facture_payee_lettre_le_3421(self):
        from apps.compta import services as compta_services
        from core.events import facture_emise
        # Écriture de vente (débit 3421) puis écriture d'encaissement (crédit
        # 3421) posées SANS passer par paiement_enregistre — le lettrage ne
        # peut donc venir QUE du nouvel abonné facture_payee.
        facture_emise.send(
            sender=Facture, instance=self.facture, company=self.company)
        paiement = Paiement.objects.create(
            company=self.company, facture=self.facture,
            montant=Decimal('1200'), date_paiement='2026-07-01',
            mode=Paiement.Mode.VIREMENT)
        compta_services.ecriture_pour_paiement(paiement)
        lignes = LigneEcriture.objects.filter(
            company=self.company, compte__numero='3421')
        self.assertEqual(lignes.count(), 2)
        self.assertTrue(all(not ln.lettrage for ln in lignes))

        facture_payee.send(
            sender=Facture, instance=self.facture, company=self.company)
        lignes = LigneEcriture.objects.filter(
            company=self.company, compte__numero='3421')
        codes = set(lignes.values_list('lettrage', flat=True))
        self.assertEqual(len(codes), 1)
        self.assertNotIn('', codes)

    @override_settings(COMPTA_AUTO_ECRITURES=True)
    def test_reemission_idempotente(self):
        from apps.compta import services as compta_services
        from core.events import facture_emise
        facture_emise.send(
            sender=Facture, instance=self.facture, company=self.company)
        paiement = Paiement.objects.create(
            company=self.company, facture=self.facture,
            montant=Decimal('1200'), date_paiement='2026-07-01',
            mode=Paiement.Mode.VIREMENT)
        compta_services.ecriture_pour_paiement(paiement)
        facture_payee.send(
            sender=Facture, instance=self.facture, company=self.company)
        codes_avant = sorted(LigneEcriture.objects.filter(
            company=self.company, compte__numero='3421',
        ).values_list('lettrage', flat=True))
        # Ré-émission (ex. double chemin paiement_enregistre + facture_payee).
        facture_payee.send(
            sender=Facture, instance=self.facture, company=self.company)
        codes_apres = sorted(LigneEcriture.objects.filter(
            company=self.company, compte__numero='3421',
        ).values_list('lettrage', flat=True))
        self.assertEqual(codes_avant, codes_apres)

    def test_statut_facture_jamais_modifie(self):
        statut_avant = self.facture.statut
        facture_payee.send(
            sender=Facture, instance=self.facture, company=self.company)
        self.facture.refresh_from_db()
        self.assertEqual(self.facture.statut, statut_avant)


class TestFacturePayeeNotifieVendeur(TestCase):
    def setUp(self):
        self.company = make_company('arc36-vendeur', 'ARC36 Vendeur')
        self.vendeur = User.objects.create_user(
            username='arc36-vendeur', password='x', company=self.company,
            role_legacy='normal')
        self.cl = Client.objects.create(
            company=self.company, nom='Client', prenom='V36',
            email='arc36-v@example.com')
        self.facture = Facture.objects.create(
            company=self.company, reference='FAC-ARC36-0002',
            client=self.cl, statut=Facture.Statut.EMISE,
            created_by=self.vendeur)

    def test_notification_vendeur_facture_payee(self):
        facture_payee.send(
            sender=Facture, instance=self.facture, company=self.company)
        notes = Notification.objects.filter(
            company=self.company, recipient=self.vendeur,
            event_type=EventType.FACTURE_PAYEE)
        self.assertEqual(notes.count(), 1)
        self.assertIn(self.facture.reference, notes.first().body)

    def test_sans_createur_aucune_notification_aucun_crash(self):
        facture = Facture.objects.create(
            company=self.company, reference='FAC-ARC36-0003',
            client=self.cl, statut=Facture.Statut.EMISE)
        facture_payee.send(
            sender=Facture, instance=facture, company=self.company)
        self.assertEqual(
            Notification.objects.filter(
                company=self.company,
                event_type=EventType.FACTURE_PAYEE).count(),
            0)


class TestBonCommandeCreeNotifieMagasinier(TestCase):
    def setUp(self):
        self.company = make_company('arc36-bc', 'ARC36 BC')
        # Sans NotificationRoutingRule : repli managers (admin/responsable).
        self.magasinier = User.objects.create_user(
            username='arc36-resp', password='x', company=self.company,
            role_legacy='responsable')
        self.cl = Client.objects.create(
            company=self.company, nom='Client', prenom='BC36',
            email='arc36-bc@example.com')
        self.bc = BonCommande.objects.create(
            company=self.company, reference='BC-ARC36-0001', client=self.cl)

    def test_notification_bon_commande_cree(self):
        bon_commande_cree.send(
            sender=BonCommande, instance=self.bc, company=self.company)
        notes = Notification.objects.filter(
            company=self.company, recipient=self.magasinier,
            event_type=EventType.BON_COMMANDE_CREE)
        self.assertEqual(notes.count(), 1)
        self.assertIn(self.bc.reference, notes.first().body)

    def test_multi_tenant_aucune_fuite(self):
        other_co = make_company('arc36-bc-b', 'ARC36 BC B')
        User.objects.create_user(
            username='arc36-resp-b', password='x', company=other_co,
            role_legacy='responsable')
        bon_commande_cree.send(
            sender=BonCommande, instance=self.bc, company=self.company)
        self.assertEqual(
            Notification.objects.filter(company=other_co).count(), 0)


class TestResiliationCoupeSupervision(TestCase):
    def setUp(self):
        self.company = make_company('arc36-monit', 'ARC36 Monit')
        self.cl = Client.objects.create(
            company=self.company, nom='Client', prenom='M36',
            email='arc36-m@example.com')
        self.inst = Installation.objects.create(
            company=self.company, reference='CHT-ARC36-1', client=self.cl,
            statut=Installation.Statut.RECEPTIONNE)
        self.config = ConfigSupervision.objects.create(
            company=self.company, installation=self.inst,
            provider='huawei', enabled=True)
        self.abonnement = AbonnementMonitoring.objects.create(
            company=self.company, client_id=self.cl.id,
            installation_id=self.inst.id)

    def test_resiliation_coupe_la_supervision(self):
        abonnement_monitoring_resilie.send(
            sender=AbonnementMonitoring, abonnement=self.abonnement,
            motif='Client parti', company=self.company)
        self.config.refresh_from_db()
        self.assertFalse(self.config.enabled)

    def test_idempotent_et_sans_installation(self):
        # Ré-émission : déjà coupée → no-op.
        abonnement_monitoring_resilie.send(
            sender=AbonnementMonitoring, abonnement=self.abonnement,
            motif='x', company=self.company)
        abonnement_monitoring_resilie.send(
            sender=AbonnementMonitoring, abonnement=self.abonnement,
            motif='x', company=self.company)
        self.config.refresh_from_db()
        self.assertFalse(self.config.enabled)
        # Abonnement sans installation liée : no-op strict.
        orphelin = AbonnementMonitoring.objects.create(
            company=self.company, client_id=self.cl.id)
        abonnement_monitoring_resilie.send(
            sender=AbonnementMonitoring, abonnement=orphelin,
            motif='x', company=self.company)

    def test_multi_tenant_ne_coupe_pas_une_autre_societe(self):
        other_co = make_company('arc36-monit-b', 'ARC36 Monit B')
        other_cl = Client.objects.create(
            company=other_co, nom='Client', prenom='M36B',
            email='arc36-mb@example.com')
        other_inst = Installation.objects.create(
            company=other_co, reference='CHT-ARC36-B', client=other_cl,
            statut=Installation.Statut.RECEPTIONNE)
        other_config = ConfigSupervision.objects.create(
            company=other_co, installation=other_inst,
            provider='huawei', enabled=True)
        abonnement_monitoring_resilie.send(
            sender=AbonnementMonitoring, abonnement=self.abonnement,
            motif='x', company=self.company)
        other_config.refresh_from_db()
        self.assertTrue(other_config.enabled)


class TestCouvertureYEVNT7(TestCase):
    """Les 3 événements ont ≥1 récepteur et sont sortis d'ALLOWED_UNCONSUMED."""

    def test_les_trois_signaux_ont_un_recepteur(self):
        signaux = event_coverage.declared_signals()
        for nom in ('facture_payee', 'bon_commande_cree',
                    'abonnement_monitoring_resilie'):
            self.assertTrue(
                event_coverage.signal_has_receiver(signaux[nom]),
                f'{nom} devrait avoir au moins un récepteur (ARC36)')

    def test_retires_de_allowed_unconsumed(self):
        for nom in ('facture_payee', 'bon_commande_cree',
                    'abonnement_monitoring_resilie'):
            self.assertNotIn(nom, event_coverage.ALLOWED_UNCONSUMED)

    def test_facture_paid_reste_reserve_deprecie(self):
        # Le signal frère reste émis mais déprécié pour l'abonnement : il
        # doit rester catalogué (sinon YEVNT7 le signalerait orphelin).
        self.assertIn('facture_paid', event_coverage.ALLOWED_UNCONSUMED)

    def test_aucun_orphelin(self):
        self.assertEqual(event_coverage.orphan_signals(), set())
