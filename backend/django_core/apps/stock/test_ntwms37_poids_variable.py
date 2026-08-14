"""NTWMS37 — réception à quantité / poids VARIABLE (catch-weight).

Critère d'acceptation testé : réceptionner un rouleau de câble à poids
variable enregistre la quantité RÉELLE pesée, DISTINCTE de la quantité
commandée — sans casser le flux de réception standard pour les produits non
variables.

Run :
    python manage.py test apps.stock.test_ntwms37_poids_variable -v 2
"""
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from apps.stock.models import (
    BonCommandeFournisseur, Fournisseur, LigneBonCommandeFournisseur,
    LigneReceptionFournisseur, PeseeLigneReception, Produit,
    ReceptionFournisseur,
)
from apps.stock.services import confirm_reception_fournisseur
from apps.stock.services_catch_weight import (
    ecart_pesee_ligne, enregistrer_pesee_ligne_reception,
    quantite_valorisable_ligne, valeur_ligne_reception,
)

User = get_user_model()


def make_company(slug, nom):
    from authentication.models import Company
    company, _ = Company.objects.get_or_create(slug=slug, defaults={'nom': nom})
    return company


def auth(user):
    api = APIClient()
    api.credentials(HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(user)}')
    return api


class Ntwms37Base(TestCase):
    def setUp(self):
        self.company = make_company('ntwms37-co', 'NTWMS37 Co')
        self.autre = make_company('ntwms37-autre', 'NTWMS37 Autre')
        self.admin = User.objects.create_user(
            username='ntwms37_admin', password='x', role_legacy='admin',
            company=self.company)
        self.normal = User.objects.create_user(
            username='ntwms37_normal', password='x', role_legacy='normal',
            company=self.company)
        self.fournisseur = Fournisseur.objects.create(
            company=self.company, nom='Câbles NTWMS37')
        self.cable = Produit.objects.create(
            company=self.company, nom='Câble solaire 6 mm²',
            sku='CAB6-NTWMS37', prix_achat=Decimal('12'),
            prix_vente=Decimal('18'), quantite_stock=0)
        self.onduleur = Produit.objects.create(
            company=self.company, nom='Onduleur 3 kW', sku='OND3-NTWMS37',
            prix_achat=Decimal('6000'), prix_vente=Decimal('8000'),
            quantite_stock=0)

        self.bc = BonCommandeFournisseur.objects.create(
            company=self.company, reference='BCF-NTWMS37-0001',
            fournisseur=self.fournisseur)
        self.ligne_cmd_cable = LigneBonCommandeFournisseur.objects.create(
            bon_commande=self.bc, produit=self.cable, quantite=100,
            prix_achat_unitaire=Decimal('12'))
        self.ligne_cmd_onduleur = LigneBonCommandeFournisseur.objects.create(
            bon_commande=self.bc, produit=self.onduleur, quantite=2,
            prix_achat_unitaire=Decimal('6000'))
        self.reception = ReceptionFournisseur.objects.create(
            company=self.company, reference='REC-NTWMS37-0001',
            bon_commande=self.bc)
        self.ligne_cable = LigneReceptionFournisseur.objects.create(
            reception=self.reception, ligne_commande=self.ligne_cmd_cable,
            produit=self.cable, quantite=100)
        self.ligne_onduleur = LigneReceptionFournisseur.objects.create(
            reception=self.reception, ligne_commande=self.ligne_cmd_onduleur,
            produit=self.onduleur, quantite=2)


class Ntwms37PeseeTests(Ntwms37Base):
    def test_le_releve_reel_est_distinct_de_la_quantite_commandee(self):
        enregistrer_pesee_ligne_reception(
            ligne_reception=self.ligne_cable, user=self.admin,
            unite_variable=True, quantite_reelle='98.400', unite_mesure='m')

        pesee = PeseeLigneReception.objects.get(
            ligne_reception=self.ligne_cable)
        self.assertEqual(pesee.quantite_reelle, Decimal('98.400'))
        self.assertEqual(self.ligne_cable.quantite, 100)
        self.assertTrue(pesee.est_renseignee)
        self.assertEqual(ecart_pesee_ligne(self.ligne_cable),
                         Decimal('-1.600'))

    def test_la_valorisation_utilise_le_poids_reel_quand_renseigne(self):
        enregistrer_pesee_ligne_reception(
            ligne_reception=self.ligne_cable, user=self.admin,
            unite_variable=True, quantite_reelle='98.400', unite_mesure='m')
        self.assertEqual(quantite_valorisable_ligne(self.ligne_cable),
                         Decimal('98.400'))
        self.assertEqual(valeur_ligne_reception(self.ligne_cable),
                         Decimal('98.400') * Decimal('12'))

    def test_une_ligne_sans_releve_garde_la_quantite_nominale(self):
        self.assertEqual(quantite_valorisable_ligne(self.ligne_onduleur),
                         Decimal('2'))
        self.assertEqual(valeur_ligne_reception(self.ligne_onduleur),
                         Decimal('12000'))
        self.assertIsNone(ecart_pesee_ligne(self.ligne_onduleur))

    def test_unite_variable_fausse_ignore_le_releve(self):
        enregistrer_pesee_ligne_reception(
            ligne_reception=self.ligne_cable, user=self.admin,
            unite_variable=False, quantite_reelle='50')
        self.assertEqual(quantite_valorisable_ligne(self.ligne_cable),
                         Decimal('100'))

    def test_le_flux_de_reception_standard_nest_pas_casse(self):
        enregistrer_pesee_ligne_reception(
            ligne_reception=self.ligne_cable, user=self.admin,
            unite_variable=True, quantite_reelle='98.400', unite_mesure='m')

        confirm_reception_fournisseur(self.reception, self.admin)

        # Le compte d'UNITÉS physiques reste celui de la ligne : un touret
        # reste un touret, la pesée ne sert qu'à la valorisation.
        self.cable.refresh_from_db()
        self.onduleur.refresh_from_db()
        self.assertEqual(self.cable.quantite_stock, 100)
        self.assertEqual(self.onduleur.quantite_stock, 2)

    def test_quantite_negative_et_unite_inconnue_sont_refusees(self):
        with self.assertRaises(ValueError):
            enregistrer_pesee_ligne_reception(
                ligne_reception=self.ligne_cable, user=self.admin,
                quantite_reelle='-1')
        with self.assertRaises(ValueError):
            enregistrer_pesee_ligne_reception(
                ligne_reception=self.ligne_cable, user=self.admin,
                quantite_reelle='1', unite_mesure='tonne')

    def test_reception_confirmee_ne_se_repese_plus(self):
        confirm_reception_fournisseur(self.reception, self.admin)
        with self.assertRaises(ValueError):
            enregistrer_pesee_ligne_reception(
                ligne_reception=self.ligne_cable, user=self.admin,
                quantite_reelle='42')

    def test_le_releve_porte_la_societe_de_la_reception(self):
        pesee = enregistrer_pesee_ligne_reception(
            ligne_reception=self.ligne_cable, user=self.admin,
            quantite_reelle='99')
        self.assertEqual(pesee.company_id, self.company.id)
        self.assertNotEqual(pesee.company_id, self.autre.id)


class Ntwms37ApiTests(Ntwms37Base):
    def _base(self):
        return f'/api/django/stock/receptions-fournisseur/{self.reception.id}/'

    def test_saisie_puis_lecture_des_pesees(self):
        api = auth(self.admin)
        res = api.post(
            self._base() + f'lignes/{self.ligne_cable.id}/pesee/',
            {'unite_variable': True, 'quantite_reelle': '98.4',
             'unite_mesure': 'm'}, format='json')
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.data['quantite_nominale'], 100)
        self.assertEqual(res.data['quantite_valorisable'], '98.400')

        liste = api.get(self._base() + 'pesees/')
        self.assertEqual(liste.status_code, 200)
        self.assertEqual(len(liste.data['lignes']), 2)

    def test_ligne_inconnue_renvoie_404(self):
        res = auth(self.admin).post(
            self._base() + 'lignes/999999/pesee/',
            {'quantite_reelle': '1'}, format='json')
        self.assertEqual(res.status_code, 404)

    def test_ecriture_refusee_a_un_role_normal(self):
        res = auth(self.normal).post(
            self._base() + f'lignes/{self.ligne_cable.id}/pesee/',
            {'quantite_reelle': '1'}, format='json')
        self.assertEqual(res.status_code, 403)
