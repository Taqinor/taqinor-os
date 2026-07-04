"""Tests XCTR8 — Cohortes de rétention contrats (logo + revenu, NRR/GRR).

Couvre :
- matrice correcte sur un jeu de test (résiliations + avenants) ;
- mois sans cohorte absent (pas de division par zéro) ;
- endpoint /contrats/contrats/cohortes-retention/.
"""
from datetime import date
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from authentication.models import Company

from apps.crm.models import Client

from apps.contrats import selectors, services
from apps.contrats.models import Contrat, EcheancierContrat

User = get_user_model()

COHORTES = "/api/django/contrats/contrats/cohortes-retention/"


def make_company(slug, nom):
    company, _ = Company.objects.get_or_create(slug=slug, defaults={"nom": nom})
    return company


def make_user(company, username, role="admin"):
    return User.objects.create_user(
        username=username, password="x", company=company, role_legacy=role
    )


def auth(user):
    api = APIClient()
    api.credentials(HTTP_AUTHORIZATION=f"Bearer {AccessToken.for_user(user)}")
    return api


def make_contrat(company, *, date_debut, montant, actif=True):
    cli = Client.objects.create(company=company, nom="Client SARL")
    contrat = Contrat.objects.create(
        company=company, objet="Contrat O&M", montant=montant,
        type_contrat="om", statut=Contrat.Statut.ACTIF if actif else
        Contrat.Statut.RESILIE,
        client_id=cli.id, date_debut=date_debut)
    EcheancierContrat.objects.create(
        company=company, contrat=contrat, periodicite="mensuelle",
        facturation_active=True, statut=EcheancierContrat.Statut.ACTIF,
        montant_total=montant)
    return contrat


class CohortesRetentionTests(TestCase):
    def setUp(self):
        self.co = make_company("cohortes-svc", "CohortesSvc")

    def test_matrice_logo_et_revenu(self):
        # Cohorte janvier 2026 : 2 contrats.
        c1 = make_contrat(
            self.co, date_debut=date(2026, 1, 1), montant=Decimal("1000"))
        make_contrat(
            self.co, date_debut=date(2026, 1, 1), montant=Decimal("1000"))
        today = date(2026, 3, 1)  # 2 mois d'ancienneté.

        # c1 résilié à 1 mois d'ancienneté (perdu à partir de k=1).
        services.resilier_contrat(
            c1, motif="Test", date_effet=date(2026, 2, 1),
            today=date(2026, 2, 1))

        data = selectors.cohortes_retention(self.co, today=today)
        matrice = data['cohortes']['2026-01-01']

        # k=0 : les deux contrats existent encore (c1 pas encore résilié à k=0
        # dans notre reconstruction — statut terminal s'applique globalement).
        self.assertIn(0, matrice)
        self.assertEqual(matrice[0]['nb_contrats'], 2)
        # c1 est désormais résilié (statut terminal) → compté perdu partout.
        self.assertEqual(matrice[0]['nb_actifs'], 1)
        self.assertEqual(matrice[0]['logo_pct'], Decimal('50.00'))

    def test_pas_de_division_par_zero_mois_absent(self):
        """Une cohorte dont AUCUN membre n'atteint le mois k est absente."""
        make_contrat(
            self.co, date_debut=date(2026, 6, 1), montant=Decimal("1000"))
        # Aujourd'hui = mois de création → mois_max = 0, donc k=1 absent.
        data = selectors.cohortes_retention(self.co, today=date(2026, 6, 15))
        matrice = data['cohortes']['2026-06-01']
        self.assertIn(0, matrice)
        self.assertNotIn(1, matrice)

    def test_expansion_peut_depasser_100_pct_nrr(self):
        contrat = make_contrat(
            self.co, date_debut=date(2026, 1, 1), montant=Decimal("1000"))
        services.creer_avenant(
            contrat, objet="Extension", date_effet=date(2026, 1, 15),
            montant_delta=Decimal("500"))
        # Recale l'échéancier au nouveau montant (comme le ferait un cycle
        # normal — l'avenant ajuste Contrat.montant, l'échéancier suit).
        ech = contrat.echeanciers.first()
        ech.montant_total = Decimal("1500")
        ech.save(update_fields=['montant_total'])

        data = selectors.cohortes_retention(self.co, today=date(2026, 1, 20))
        matrice = data['cohortes']['2026-01-01']
        # revenu_pct (NRR) dépasse 100 (mrr courant 1500 / mrr initial 1000).
        self.assertGreater(matrice[0]['revenu_pct'], Decimal('100.00'))
        # revenu_grr_pct est plafonné à 100.
        self.assertEqual(matrice[0]['revenu_grr_pct'], Decimal('100.00'))

    def test_scope_societe(self):
        autre = make_company("cohortes-autre", "CohortesAutre")
        make_contrat(
            autre, date_debut=date(2026, 1, 1), montant=Decimal("999"))
        make_contrat(
            self.co, date_debut=date(2026, 1, 1), montant=Decimal("1000"))
        data = selectors.cohortes_retention(self.co, today=date(2026, 1, 15))
        self.assertEqual(len(data['cohortes']), 1)
        self.assertEqual(
            data['cohortes']['2026-01-01'][0]['nb_contrats'], 1)


class CohortesRetentionApiTests(TestCase):
    def setUp(self):
        self.co = make_company("cohortes-api", "CohortesApi")
        self.admin = make_user(self.co, "cohortes-api-admin")

    def test_endpoint_retourne_matrice(self):
        make_contrat(
            self.co, date_debut=date(2026, 1, 1), montant=Decimal("1000"))
        api = auth(self.admin)
        res = api.get(COHORTES)
        self.assertEqual(res.status_code, 200, res.content)
        self.assertIn('cohortes', res.data)
        self.assertIn('mois_max', res.data)

    def test_role_gate(self):
        commercial = make_user(self.co, "cohortes-api-com", role="commercial")
        api = auth(commercial)
        res = api.get(COHORTES)
        self.assertEqual(res.status_code, 403)
