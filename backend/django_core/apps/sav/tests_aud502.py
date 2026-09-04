"""AUD502 — ContratMaintenance expire enfin (décision fondateur D13, 03/09/2026).

Constat d'audit (le ROUGE que ces tests figent) : ``duree_mois`` était un champ
MORT — lu nulle part hors du serializer/PDF. Conséquences mesurées avant
correctif, chacune reproduite ci-dessous par un test qui échouait :

  * ``Ticket.couverture_calculee`` sélectionnait ``ContratMaintenance.objects
    .filter(actif=True)`` SANS regarder l'échéance : un contrat mort depuis des
    mois sortait « CONTRAT » et ``TicketViewSet.facturer`` émettait une facture
    0 DH « couvert » (``test_contrat_expire_hors_grace_ticket_redevient_facturable``
    et ``test_facturer_ticket_sur_contrat_expire_nest_plus_zero_dh``) ;
  * ``is_due()`` ne testait que le drapeau ``actif`` : des visites préventives
    étaient générées à vie (``test_visite_preventive_plus_generee_apres_grace``) ;
  * ``facturation_due()`` idem : facturation récurrente sans fin
    (``test_facturation_recurrente_sarrete_apres_grace``).

D13 : expiration = ``date_debut + duree_mois`` avec une GRÂCE de 30 jours —
pendant la grâce le ticket reste couvert mais le contrat apparaît dans la file
« à renouveler » ; au-delà, il redevient FACTURABLE.

Run :
    docker compose exec django_core python manage.py test apps.sav.tests_aud502 -v 2
"""
from datetime import date, timedelta
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from authentication.models import Company
from apps.crm.models import Client
from apps.installations.models import Installation
from apps.sav.models import ContratMaintenance, PieceConsommee, Ticket
from apps.stock.models import Produit

User = get_user_model()


def auth(user):
    api = APIClient()
    api.credentials(HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(user)}')
    return api


class AUD502ExpirationContratMaintenanceTest(TestCase):
    def setUp(self):
        self.company, _ = Company.objects.get_or_create(
            slug='sav-aud502', defaults={'nom': 'Sav Co AUD502'})
        self.admin = User.objects.create_user(
            username='aud502_admin', password='x', role_legacy='admin',
            company=self.company)
        self.client_obj = Client.objects.create(
            company=self.company, nom='Client', prenom='AUD502',
            email='aud502-client@example.invalid')
        self.inst = Installation.objects.create(
            company=self.company, reference='CHT-AUD502', client=self.client_obj)
        self.piece = Produit.objects.create(
            company=self.company, nom='Fusible AUD502', sku='FUS-AUD502',
            prix_achat=Decimal('5'), prix_vente=Decimal('50'))
        self.today = date.today()

    def _contrat(self, *, duree_mois, expire_depuis_jours=None, **extra):
        """Contrat dont l'échéance (date_debut + duree_mois) tombe il y a
        ``expire_depuis_jours`` jours (ou dans le futur si None)."""
        if expire_depuis_jours is None:
            date_debut = self.today - timedelta(days=15)
        else:
            date_debut = (self.today - timedelta(days=expire_depuis_jours)
                          - timedelta(days=30 * duree_mois))
        return ContratMaintenance.objects.create(
            company=self.company, client=self.client_obj,
            installation=self.inst, date_debut=date_debut, actif=True,
            duree_mois=duree_mois, **extra)

    def _ticket(self, reference):
        return Ticket.objects.create(
            company=self.company, reference=reference, client=self.client_obj,
            installation=self.inst, type=Ticket.Type.CORRECTIF,
            date_ouverture=self.today, created_by=self.admin)

    # ── ROUGE #1 — couverture d'un contrat expiré hors grâce ────────────────

    def test_contrat_expire_hors_grace_ticket_redevient_facturable(self):
        """Expiré depuis 31 jours (grâce 30 j dépassée) : le ticket n'est plus
        « couvert » — c'était le bug (facture 0 DH à vie)."""
        contrat = self._contrat(duree_mois=12, expire_depuis_jours=31)
        self.assertTrue(contrat.est_expire())
        self.assertFalse(contrat.en_periode_grace())
        self.assertFalse(contrat.est_actif())
        ticket = self._ticket('SAV-AUD502-1')
        self.assertEqual(
            ticket.couverture_calculee(), Ticket.Couverture.FACTURABLE)

    def test_facturer_ticket_sur_contrat_expire_nest_plus_zero_dh(self):
        """Bout en bout : la facture émise sur un ticket dont le seul contrat
        est expiré porte le prix de vente réel, plus 0 DH."""
        self._contrat(duree_mois=12, expire_depuis_jours=45)
        ticket = self._ticket('SAV-AUD502-2')
        PieceConsommee.objects.create(
            company=self.company, ticket=ticket, produit=self.piece, quantite=1)
        resp = auth(self.admin).post(
            f'/api/django/sav/tickets/{ticket.pk}/facturer/')
        self.assertEqual(resp.status_code, 201, resp.data)
        self.assertEqual(resp.data['couverture'], Ticket.Couverture.FACTURABLE)
        from apps.ventes.models import Facture, LigneFacture
        facture = Facture.objects.get(pk=resp.data['facture_id'])
        ligne = LigneFacture.objects.get(facture=facture, produit=self.piece)
        self.assertEqual(ligne.prix_unitaire, Decimal('50.00'))

    # ── Grâce : couvert MAIS à renouveler ───────────────────────────────────

    def test_contrat_dans_la_grace_reste_couvrant(self):
        contrat = self._contrat(duree_mois=12, expire_depuis_jours=10)
        self.assertTrue(contrat.est_expire())
        self.assertTrue(contrat.en_periode_grace())
        self.assertTrue(contrat.est_actif())
        ticket = self._ticket('SAV-AUD502-3')
        self.assertEqual(
            ticket.couverture_calculee(), Ticket.Couverture.CONTRAT)

    def test_contrat_dans_la_grace_apparait_dans_a_renouveler(self):
        contrat = self._contrat(duree_mois=12, expire_depuis_jours=10)
        self.assertTrue(contrat.a_renouveler())
        resp = auth(self.admin).get(
            '/api/django/sav/contrats-maintenance/?a_renouveler=1')
        self.assertEqual(resp.status_code, 200, resp.data)
        rows = resp.data.get('results', resp.data)
        ids = [r['id'] for r in rows]
        self.assertIn(contrat.pk, ids)
        row = next(r for r in rows if r['id'] == contrat.pk)
        self.assertTrue(row['en_periode_grace'])
        self.assertTrue(row['a_renouveler'])
        self.assertEqual(
            row['date_expiration'], contrat.date_expiration().isoformat())

    # ── ROUGE #2 — visites préventives générées à vie ───────────────────────

    def test_visite_preventive_plus_generee_apres_grace(self):
        from apps.sav.maintenance import generer_visites_dues

        self._contrat(duree_mois=12, expire_depuis_jours=60,
                      periodicite=ContratMaintenance.Periodicite.MENSUEL)
        avant = Ticket.objects.filter(company=self.company).count()
        genere = generer_visites_dues(self.company, self.admin)
        self.assertEqual(genere, 0)
        self.assertEqual(
            Ticket.objects.filter(company=self.company).count(), avant)

    def test_visite_preventive_encore_generee_pendant_la_grace(self):
        from apps.sav.maintenance import generer_visites_dues

        self._contrat(duree_mois=12, expire_depuis_jours=5,
                      periodicite=ContratMaintenance.Periodicite.MENSUEL)
        self.assertEqual(generer_visites_dues(self.company, self.admin), 1)

    # ── ROUGE #3 — facturation récurrente sans fin ──────────────────────────

    def test_facturation_recurrente_sarrete_apres_grace(self):
        from apps.sav.services import contrats_maintenance_dus_facturation

        contrat = self._contrat(
            duree_mois=12, expire_depuis_jours=90, facturation_active=True,
            prix=Decimal('1200'),
            periodicite=ContratMaintenance.Periodicite.MENSUEL)
        self.assertFalse(contrat.facturation_due())
        self.assertEqual(
            contrats_maintenance_dus_facturation(self.company), [])

    # ── Non-régression : un contrat SANS duree_mois n'expire jamais ─────────

    def test_contrat_sans_duree_mois_inchange(self):
        contrat = ContratMaintenance.objects.create(
            company=self.company, client=self.client_obj,
            installation=self.inst, date_debut=date(2020, 1, 1), actif=True)
        self.assertIsNone(contrat.date_expiration())
        self.assertFalse(contrat.est_expire())
        self.assertTrue(contrat.est_actif())
        self.assertFalse(contrat.a_renouveler())
        ticket = self._ticket('SAV-AUD502-9')
        self.assertEqual(
            ticket.couverture_calculee(), Ticket.Couverture.CONTRAT)

    def test_date_expiration_ajoute_les_mois(self):
        contrat = ContratMaintenance.objects.create(
            company=self.company, client=self.client_obj,
            date_debut=date(2026, 1, 31), duree_mois=13, actif=True)
        # 31 janv. + 13 mois → 28 févr. (recadrage fin de mois, add_months).
        self.assertEqual(contrat.date_expiration(), date(2027, 2, 28))
        self.assertEqual(contrat.date_fin_grace(), date(2027, 3, 30))
