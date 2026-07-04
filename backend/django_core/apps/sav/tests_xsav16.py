"""XSAV16 — Journal d'immobilisation (downtime) + disponibilité %.

Couvre :
  * chevauchement refusé (fenêtre en cours, et fenêtre close qui couvre le
    nouveau début) ;
  * disponibilité % correcte sur fixtures datées ;
  * la clôture du ticket referme automatiquement (idempotent) le downtime lié.

Run :
    docker compose exec django_core python manage.py test apps.sav.tests_xsav16 -v 2
"""
from datetime import timedelta

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.utils import timezone
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from authentication.models import Company
from apps.crm.models import Client
from apps.installations.models import Installation
from apps.stock.models import Produit
from apps.sav.models import Equipement, Ticket
from apps.sav.services import (
    DowntimeOverlapError, disponibilite_equipement, ouvrir_downtime,
)

User = get_user_model()


def make_company(slug='sav-xsav16', nom='Sav Co XSAV16'):
    company, _ = Company.objects.get_or_create(slug=slug, defaults={'nom': nom})
    return company


def auth(user):
    api = APIClient()
    api.credentials(HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(user)}')
    return api


class XSAV16DowntimeTest(TestCase):
    def setUp(self):
        self.company = make_company()
        self.admin = User.objects.create_user(
            username='xsav16_admin', password='x', role_legacy='admin',
            company=self.company)
        self.client_obj = Client.objects.create(
            company=self.company, nom='Client', prenom='Test',
            email='xsav16-client@example.invalid')
        self.inst = Installation.objects.create(
            company=self.company, reference='CHT-XSAV16', client=self.client_obj)
        self.produit = Produit.objects.create(
            company=self.company, nom='Onduleur DT', sku='OND-DT-XSAV16',
            prix_achat=300, prix_vente=600)
        self.equip = Equipement.objects.create(
            company=self.company, produit=self.produit, installation=self.inst,
            created_by=self.admin)

    def _ticket(self):
        return Ticket.objects.create(
            company=self.company, reference=f'SAV-XSAV16-{Ticket.objects.count()}',
            client=self.client_obj, installation=self.inst,
            equipement=self.equip, type=Ticket.Type.CORRECTIF,
            created_by=self.admin)

    # ── Chevauchement refusé ─────────────────────────────────────────────────

    def test_chevauchement_fenetre_en_cours_refuse(self):
        now = timezone.now()
        ouvrir_downtime(company=self.company, equipement=self.equip, debut=now)
        with self.assertRaises(DowntimeOverlapError):
            ouvrir_downtime(
                company=self.company, equipement=self.equip,
                debut=now + timedelta(hours=1))

    def test_chevauchement_fenetre_close_refuse(self):
        base = timezone.now() - timedelta(days=10)
        dt = ouvrir_downtime(
            company=self.company, equipement=self.equip, debut=base)
        dt.clore(fin=base + timedelta(days=2))
        with self.assertRaises(DowntimeOverlapError):
            ouvrir_downtime(
                company=self.company, equipement=self.equip,
                debut=base + timedelta(days=1))

    def test_nouvelle_fenetre_apres_cloture_acceptee(self):
        base = timezone.now() - timedelta(days=10)
        dt = ouvrir_downtime(
            company=self.company, equipement=self.equip, debut=base)
        dt.clore(fin=base + timedelta(days=2))
        # Nouvelle fenêtre après la fermeture (pas de chevauchement).
        dt2 = ouvrir_downtime(
            company=self.company, equipement=self.equip,
            debut=base + timedelta(days=3))
        self.assertIsNotNone(dt2.id)

    # ── Disponibilité % ──────────────────────────────────────────────────────

    def test_disponibilite_correcte_sur_fixtures(self):
        debut_periode = timezone.now() - timedelta(days=30)
        fin_periode = timezone.now()
        # 30 jours = 720h ; downtime de 72h (3 jours) dans la période.
        dt_debut = debut_periode + timedelta(days=10)
        dt = ouvrir_downtime(
            company=self.company, equipement=self.equip, debut=dt_debut)
        dt.clore(fin=dt_debut + timedelta(hours=72))

        data = disponibilite_equipement(
            self.equip, debut_periode=debut_periode, fin_periode=fin_periode)
        self.assertAlmostEqual(data['duree_periode_heures'], 720, delta=1)
        self.assertAlmostEqual(data['duree_downtime_heures'], 72, delta=0.1)
        # dispo % = (1 - 72/720) * 100 = 90.0
        self.assertAlmostEqual(data['disponibilite_pct'], 90.0, delta=0.1)

    def test_disponibilite_100_sans_downtime(self):
        debut_periode = timezone.now() - timedelta(days=30)
        fin_periode = timezone.now()
        data = disponibilite_equipement(
            self.equip, debut_periode=debut_periode, fin_periode=fin_periode)
        self.assertEqual(data['disponibilite_pct'], 100.0)

    # ── Clôture ticket ferme le downtime lié ────────────────────────────────

    def test_cloture_ticket_ferme_downtime_lie(self):
        ticket = self._ticket()
        dt = ouvrir_downtime(
            company=self.company, equipement=self.equip,
            debut=timezone.now() - timedelta(hours=5), ticket=ticket)
        self.assertIsNone(dt.fin)

        api = auth(self.admin)
        resp = api.patch(
            f'/api/django/sav/tickets/{ticket.id}/',
            {'statut': 'resolu'}, format='json')
        self.assertEqual(resp.status_code, 200, resp.content)
        dt.refresh_from_db()
        self.assertIsNotNone(dt.fin)

    def test_cloture_ticket_idempotente_ne_recree_pas_erreur(self):
        ticket = self._ticket()
        dt = ouvrir_downtime(
            company=self.company, equipement=self.equip,
            debut=timezone.now() - timedelta(hours=5), ticket=ticket)
        api = auth(self.admin)
        api.patch(
            f'/api/django/sav/tickets/{ticket.id}/',
            {'statut': 'resolu'}, format='json')
        dt.refresh_from_db()
        fin_apres_premiere_cloture = dt.fin
        # Second PATCH statut identique -> ne doit pas planter ni changer fin.
        resp = api.patch(
            f'/api/django/sav/tickets/{ticket.id}/',
            {'statut': 'cloture'}, format='json')
        self.assertEqual(resp.status_code, 200, resp.content)
        dt.refresh_from_db()
        self.assertEqual(dt.fin, fin_apres_premiere_cloture)

    # ── API downtime sur l'équipement ────────────────────────────────────────

    def test_api_ouvre_et_liste_downtime(self):
        api = auth(self.admin)
        resp = api.post(
            f'/api/django/sav/equipements/{self.equip.id}/downtime/',
            {'motif': 'Panne onduleur'})
        self.assertEqual(resp.status_code, 201, resp.content)
        self.assertTrue(resp.data['en_cours'])

        resp = api.get(f'/api/django/sav/equipements/{self.equip.id}/downtime/')
        self.assertEqual(resp.status_code, 200, resp.content)
        self.assertEqual(len(resp.data), 1)

    def test_api_ouvre_refuse_chevauchement(self):
        api = auth(self.admin)
        resp = api.post(
            f'/api/django/sav/equipements/{self.equip.id}/downtime/',
            {'motif': 'Panne 1'})
        self.assertEqual(resp.status_code, 201, resp.content)
        resp2 = api.post(
            f'/api/django/sav/equipements/{self.equip.id}/downtime/',
            {'motif': 'Panne 2'})
        self.assertEqual(resp2.status_code, 400, resp2.content)

    def test_api_disponibilite_endpoint(self):
        api = auth(self.admin)
        resp = api.get(
            f'/api/django/sav/equipements/{self.equip.id}/disponibilite/')
        self.assertEqual(resp.status_code, 200, resp.content)
        self.assertIn('disponibilite_pct', resp.data)
