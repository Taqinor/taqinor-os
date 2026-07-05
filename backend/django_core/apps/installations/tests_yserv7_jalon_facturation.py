"""YSERV7 — Jalons atteints & réception → rappel de facturation d'échéancier.

`JalonProjet.date_reelle`/`atteint` ne consommait RIEN côté facturation : ces
tests couvrent le câblage additif :

  * un jalon lié à une tranche (acompte/intermediaire/solde) non facturée qui
    passe `atteint=True` déclenche EXACTEMENT UNE notification (idempotent —
    ré-atteindre ne double pas) ;
  * une tranche DÉJÀ facturée (`ventes.Facture.type_facture` correspondant,
    statut non annulé) ne déclenche AUCUNE notification ;
  * la réception du chantier (statut RECEPTIONNE) rappelle la tranche SOLDE
    si due ;
  * le sélecteur `chantiers/a-facturer/` liste exactement les tranches dues ;
  * aucune facture n'est jamais créée automatiquement (nudge seulement).

Run :
    python manage.py test apps.installations.tests_yserv7_jalon_facturation -v2
"""
import itertools
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from authentication.models import Company
from apps.crm.models import Client
from apps.ventes.models import Devis, Facture
from apps.installations.models import Installation, JalonProjet
from apps.installations.services import (
    notifier_jalon_a_facturer, notifier_reception_solde_a_facturer,
    chantiers_a_facturer,
)
from apps.notifications.models import Notification

User = get_user_model()
_seq = itertools.count(1)


def make_company():
    n = next(_seq)
    company, _ = Company.objects.get_or_create(
        slug=f'yserv7-co-{n}', defaults={'nom': f'YSERV7 Co {n}'})
    return company


def make_user(company, role='responsable'):
    return User.objects.create_user(
        username=f'yserv7-{next(_seq)}', password='x',
        role_legacy=role, company=company)


def make_client(company):
    n = next(_seq)
    return Client.objects.create(
        company=company, nom='Client', prenom='YSERV7',
        email=f'yserv7-{n}@example.invalid')


def make_devis(company, client):
    n = next(_seq)
    return Devis.objects.create(
        company=company, reference=f'DEV-YSERV7-{n:04d}',
        client=client, statut=Devis.Statut.ACCEPTE,
        taux_tva=Decimal('20'), mode_installation='residentiel')


def make_installation(company, client, devis, statut=Installation.Statut.SIGNE):
    n = next(_seq)
    return Installation.objects.create(
        company=company, reference=f'CHT-YSERV7-{n}', client=client,
        devis=devis, statut=statut)


class TestJalonAtteintNotifie(TestCase):
    def setUp(self):
        self.company = make_company()
        self.user = make_user(self.company)
        self.client_obj = make_client(self.company)
        self.devis = make_devis(self.company, self.client_obj)
        self.inst = make_installation(self.company, self.client_obj, self.devis)

    def _jalon(self, tranche=JalonProjet.TRANCHE_ACOMPTE):
        return JalonProjet.objects.create(
            company=self.company, installation=self.inst,
            phase=JalonProjet.Phase.POSE, libelle='Pose',
            tranche_echeancier=tranche)

    def test_jalon_atteint_notifie_une_fois(self):
        jalon = self._jalon()
        jalon.atteint = True
        jalon.save(update_fields=['atteint'])

        result = notifier_jalon_a_facturer(jalon, self.user)
        self.assertTrue(result)
        notifs = Notification.objects.filter(
            company=self.company, recipient=self.user)
        self.assertEqual(notifs.count(), 1)
        self.assertIn('Acompte', notifs.first().title)

        # Idempotence : ré-appeler ne double pas la notification.
        jalon.refresh_from_db()
        result2 = notifier_jalon_a_facturer(jalon, self.user)
        self.assertFalse(result2)
        self.assertEqual(
            Notification.objects.filter(
                company=self.company, recipient=self.user).count(),
            1)

    def test_pas_de_notification_sans_tranche_liee(self):
        jalon = JalonProjet.objects.create(
            company=self.company, installation=self.inst,
            phase=JalonProjet.Phase.ETUDE, libelle='Étude', atteint=True)
        result = notifier_jalon_a_facturer(jalon, self.user)
        self.assertFalse(result)
        self.assertEqual(
            Notification.objects.filter(company=self.company).count(), 0)

    def test_tranche_deja_facturee_pas_de_notification(self):
        jalon = self._jalon(tranche=JalonProjet.TRANCHE_ACOMPTE)
        jalon.atteint = True
        jalon.save(update_fields=['atteint'])
        Facture.objects.create(
            company=self.company, reference='FAC-YSERV7-0001',
            devis=self.devis, client=self.client_obj,
            type_facture=Facture.TypeFacture.ACOMPTE,
            statut=Facture.Statut.EMISE)

        result = notifier_jalon_a_facturer(jalon, self.user)
        self.assertFalse(result)
        self.assertEqual(
            Notification.objects.filter(company=self.company).count(), 0)

    def test_facture_annulee_compte_encore_comme_due(self):
        jalon = self._jalon(tranche=JalonProjet.TRANCHE_ACOMPTE)
        jalon.atteint = True
        jalon.save(update_fields=['atteint'])
        Facture.objects.create(
            company=self.company, reference='FAC-YSERV7-0002',
            devis=self.devis, client=self.client_obj,
            type_facture=Facture.TypeFacture.ACOMPTE,
            statut=Facture.Statut.ANNULEE)

        result = notifier_jalon_a_facturer(jalon, self.user)
        self.assertTrue(result)

    def test_aucune_facture_creee_automatiquement(self):
        jalon = self._jalon()
        jalon.atteint = True
        jalon.save(update_fields=['atteint'])
        notifier_jalon_a_facturer(jalon, self.user)
        self.assertEqual(
            Facture.objects.filter(devis=self.devis).count(), 0)


class TestReceptionSoldeNotifie(TestCase):
    def setUp(self):
        self.company = make_company()
        self.user = make_user(self.company)
        self.client_obj = make_client(self.company)
        self.devis = make_devis(self.company, self.client_obj)
        self.inst = make_installation(
            self.company, self.client_obj, self.devis,
            statut=Installation.Statut.INSTALLE)

    def test_reception_notifie_solde_du(self):
        result = notifier_reception_solde_a_facturer(self.inst, self.user)
        self.assertTrue(result)
        jalon = JalonProjet.objects.get(
            installation=self.inst, phase=JalonProjet.Phase.RECEPTION)
        self.assertTrue(jalon.atteint)
        self.assertEqual(jalon.tranche_echeancier, JalonProjet.TRANCHE_SOLDE)
        self.assertEqual(
            Notification.objects.filter(
                company=self.company, recipient=self.user).count(),
            1)

    def test_reception_solde_deja_facturee_pas_de_rappel(self):
        Facture.objects.create(
            company=self.company, reference='FAC-YSERV7-0003',
            devis=self.devis, client=self.client_obj,
            type_facture=Facture.TypeFacture.SOLDE,
            statut=Facture.Statut.EMISE)
        result = notifier_reception_solde_a_facturer(self.inst, self.user)
        self.assertFalse(result)

    def test_reception_via_endpoint_declenche_rappel(self):
        api = APIClient()
        api.credentials(
            HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(self.user)}')
        resp = api.patch(
            f'/api/django/installations/chantiers/{self.inst.id}/',
            {'statut': Installation.Statut.RECEPTIONNE}, format='json')
        self.assertEqual(resp.status_code, 200, resp.content)
        self.assertTrue(
            JalonProjet.objects.filter(
                installation=self.inst, phase=JalonProjet.Phase.RECEPTION,
                atteint=True).exists())
        self.assertEqual(
            Notification.objects.filter(company=self.company).count(), 1)


class TestChantiersAFacturerSelector(TestCase):
    def setUp(self):
        self.company = make_company()
        self.other_company = make_company()
        self.user = make_user(self.company)
        self.client_obj = make_client(self.company)
        self.devis = make_devis(self.company, self.client_obj)
        self.inst = make_installation(self.company, self.client_obj, self.devis)

    def test_liste_exacte_tranches_dues(self):
        JalonProjet.objects.create(
            company=self.company, installation=self.inst,
            phase=JalonProjet.Phase.POSE, libelle='Pose', atteint=True,
            tranche_echeancier=JalonProjet.TRANCHE_ACOMPTE)
        # Jalon non atteint : ne doit pas apparaître.
        JalonProjet.objects.create(
            company=self.company, installation=self.inst,
            phase=JalonProjet.Phase.MES, libelle='MES', atteint=False,
            tranche_echeancier=JalonProjet.TRANCHE_INTERMEDIAIRE)
        # Tranche déjà facturée : ne doit pas apparaître.
        JalonProjet.objects.create(
            company=self.company, installation=self.inst,
            phase=JalonProjet.Phase.RECEPTION, libelle='Réception',
            atteint=True, tranche_echeancier=JalonProjet.TRANCHE_SOLDE)
        Facture.objects.create(
            company=self.company, reference='FAC-YSERV7-0004',
            devis=self.devis, client=self.client_obj,
            type_facture=Facture.TypeFacture.SOLDE,
            statut=Facture.Statut.EMISE)

        result = chantiers_a_facturer(self.company)
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]['tranche'], JalonProjet.TRANCHE_ACOMPTE)
        self.assertEqual(result[0]['installation_id'], self.inst.id)

    def test_isolation_tenant(self):
        other_client = make_client(self.other_company)
        other_devis = make_devis(self.other_company, other_client)
        other_inst = make_installation(
            self.other_company, other_client, other_devis)
        JalonProjet.objects.create(
            company=self.other_company, installation=other_inst,
            phase=JalonProjet.Phase.POSE, libelle='Pose', atteint=True,
            tranche_echeancier=JalonProjet.TRANCHE_ACOMPTE)
        result = chantiers_a_facturer(self.company)
        self.assertEqual(result, [])
