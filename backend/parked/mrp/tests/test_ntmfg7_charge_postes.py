"""NTMFG7 — Ordonnancement à capacité finie : Gantt de charge inter-ordres
par poste.

Critère : le calcul de charge par poste/jour est exact sur fixtures, la
replanification déplace une opération avec avertissement de surcharge non
bloquant, isolation tenant."""
from decimal import Decimal

from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from apps.mrp.models import Gamme, OperationGamme, OrdreFabrication, PosteDeCharge
from apps.mrp.selectors import charge_postes
from apps.mrp.services import confirmer_of, replanifier_operation
from apps.stock.models import Produit

from ._fixtures import make_company, make_user


def auth(user):
    api = APIClient()
    api.credentials(HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(user)}')
    return api


def make_produit(company, nom='Produit'):
    return Produit.objects.create(company=company, nom=nom, prix_vente=0, tva=20)


class ChargePostesTests(TestCase):
    def setUp(self):
        self.company = make_company('mrp-charge-1', 'MRP Charge 1')
        self.produit = make_produit(self.company)
        self.poste = PosteDeCharge.objects.create(
            company=self.company, code='P-CHARGE', nom='Poste charge',
            capacite_heures_jour=Decimal('8'))  # 480 min/jour.
        self.gamme = Gamme.objects.create(
            company=self.company, nom='Gamme charge', produit=self.produit)
        OperationGamme.objects.create(
            gamme=self.gamme, ordre=1, poste_charge=self.poste,
            libelle='Op unique', temps_prepa_min=Decimal('10'),
            temps_unitaire_min=Decimal('5'))

    def test_charge_exacte_sur_fixture(self):
        of = OrdreFabrication.objects.create(
            company=self.company, produit=self.produit, quantite=10,
            gamme=self.gamme)
        confirmer_of(of)
        of.refresh_from_db()
        op = of.operations.first()

        resultats = charge_postes(
            self.company, op.date_planifiee, op.date_planifiee)
        self.assertEqual(len(resultats), 1)
        # temps = 10 + 5*10 = 60 min.
        self.assertEqual(resultats[0]['minutes_planifiees'], '60')
        self.assertEqual(resultats[0]['capacite_minutes'], '480')
        self.assertFalse(resultats[0]['surcharge'])

    def test_charge_agrege_plusieurs_of_meme_jour(self):
        of1 = OrdreFabrication.objects.create(
            company=self.company, produit=self.produit, quantite=50,
            gamme=self.gamme)  # 10 + 5*50 = 260 min.
        confirmer_of(of1)
        of2 = OrdreFabrication.objects.create(
            company=self.company, produit=self.produit, quantite=50,
            gamme=self.gamme)
        confirmer_of(of2)
        jour = of1.operations.first().date_planifiee
        # Force le 2e OF sur le MÊME jour pour tester l'agrégation cross-OF.
        op2 = of2.operations.first()
        op2.date_planifiee = jour
        op2.save(update_fields=['date_planifiee'])

        resultats = charge_postes(self.company, jour, jour)
        self.assertEqual(len(resultats), 1)
        self.assertEqual(resultats[0]['minutes_planifiees'], '520')  # 260*2.
        self.assertTrue(resultats[0]['surcharge'])  # 520 > 480.

    def test_isolation_tenant(self):
        autre_company = make_company('mrp-charge-2', 'MRP Charge 2')
        of = OrdreFabrication.objects.create(
            company=self.company, produit=self.produit, quantite=10,
            gamme=self.gamme)
        confirmer_of(of)
        of.refresh_from_db()
        jour = of.operations.first().date_planifiee
        resultats = charge_postes(autre_company, jour, jour)
        self.assertEqual(resultats, [])


class ReplanifierOperationTests(TestCase):
    def setUp(self):
        self.company = make_company('mrp-replan-1', 'MRP Replan 1')
        self.produit = make_produit(self.company)
        self.poste = PosteDeCharge.objects.create(
            company=self.company, code='P-REPLAN', nom='Poste replan',
            capacite_heures_jour=Decimal('1'))  # 60 min/jour -> facile à saturer.
        self.gamme = Gamme.objects.create(
            company=self.company, nom='Gamme replan', produit=self.produit)
        OperationGamme.objects.create(
            gamme=self.gamme, ordre=1, poste_charge=self.poste,
            libelle='Op replan', temps_prepa_min=Decimal('0'),
            temps_unitaire_min=Decimal('10'))

    def test_replanifier_deplace_et_avertit_en_cas_de_surcharge(self):
        of1 = OrdreFabrication.objects.create(
            company=self.company, produit=self.produit, quantite=5,
            gamme=self.gamme)  # 50 min.
        confirmer_of(of1)
        of2 = OrdreFabrication.objects.create(
            company=self.company, produit=self.produit, quantite=5,
            gamme=self.gamme)
        confirmer_of(of2)
        of1.refresh_from_db()
        op1 = of1.operations.first()
        op2 = of2.operations.first()

        # Déplace op2 sur le même jour que op1 -> 50+50=100 > 60 -> surcharge.
        operation, avertissement = replanifier_operation(
            op2, nouvelle_date=op1.date_planifiee.isoformat(),
            company=self.company)
        self.assertEqual(operation.date_planifiee, op1.date_planifiee)
        self.assertIsNotNone(avertissement)
        self.assertIn('Surcharge', avertissement)

    def test_replanifier_sans_surcharge_pas_d_avertissement(self):
        of = OrdreFabrication.objects.create(
            company=self.company, produit=self.produit, quantite=5,
            gamme=self.gamme)
        confirmer_of(of)
        of.refresh_from_db()
        op = of.operations.first()
        nouveau_jour = (op.date_planifiee.replace(day=1))
        operation, avertissement = replanifier_operation(
            op, nouvelle_date=nouveau_jour.isoformat(), company=self.company)
        self.assertIsNone(avertissement)

    def test_replanifier_refuse_poste_etranger(self):
        autre_company = make_company('mrp-replan-2', 'MRP Replan 2')
        autre_poste = PosteDeCharge.objects.create(
            company=autre_company, code='P-X', nom='Poste étranger')
        of = OrdreFabrication.objects.create(
            company=self.company, produit=self.produit, quantite=5,
            gamme=self.gamme)
        confirmer_of(of)
        of.refresh_from_db()
        op = of.operations.first()
        with self.assertRaises(ValueError):
            replanifier_operation(
                op, nouveau_poste_id=autre_poste.id, company=self.company)


class ChargePostesApiTests(TestCase):
    def setUp(self):
        self.company = make_company('mrp-charge-api-1', 'MRP Charge API 1')
        self.user = make_user(self.company, 'mrp-charge-api-user')
        self.api = auth(self.user)
        self.produit = make_produit(self.company)
        self.poste = PosteDeCharge.objects.create(
            company=self.company, code='P-API', nom='Poste API')
        self.gamme = Gamme.objects.create(
            company=self.company, nom='Gamme API', produit=self.produit)
        OperationGamme.objects.create(
            gamme=self.gamme, ordre=1, poste_charge=self.poste,
            libelle='Op API', temps_unitaire_min=Decimal('1'))

    def test_charge_postes_endpoint(self):
        of = OrdreFabrication.objects.create(
            company=self.company, produit=self.produit, quantite=10,
            gamme=self.gamme)
        confirmer_of(of)
        of.refresh_from_db()
        jour = of.operations.first().date_planifiee.isoformat()
        resp = self.api.get(f'/api/django/mrp/charge-postes/?debut={jour}&fin={jour}')
        self.assertEqual(resp.status_code, 200, resp.data)
        self.assertEqual(len(resp.data), 1)

    def test_replanifier_endpoint(self):
        of = OrdreFabrication.objects.create(
            company=self.company, produit=self.produit, quantite=10,
            gamme=self.gamme)
        confirmer_of(of)
        of.refresh_from_db()
        op = of.operations.first()
        nouvelle_date = op.date_planifiee.replace(day=1).isoformat()
        resp = self.api.patch(
            f'/api/django/mrp/operations-of/{op.id}/replanifier/',
            {'date_planifiee': nouvelle_date}, format='json')
        self.assertEqual(resp.status_code, 200, resp.data)
        self.assertEqual(resp.data['date_planifiee'], nouvelle_date)
        self.assertIn('avertissement', resp.data)
