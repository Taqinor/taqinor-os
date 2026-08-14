"""PV81 — la proposition client porte le schéma unifilaire (SVG, sans prix).

Deux garanties :

* le bloc n'existe QUE lorsque la conception électrique (PV41) a été faite —
  jamais une esquisse fabriquée à la volée pour remplir la page ;
* la charge utile publique reste sans AUCUN prix : le moteur électrique n'en
  connaît aucun, et le test le vérifie sur le SVG servi par le jeton.

Run :
    DB_NAME=erp_ventes python manage.py test \
        apps.ventes.tests.test_pv81_proposition_sld -v 2
"""
import uuid
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import Client as DjangoClient, TestCase

from apps.crm.models import Client
from apps.stock.models import Produit
from apps.ventes.models import Devis, LigneDevis, ShareLink
from apps.ventes.public_views import _safe_sld_svg
from authentication.models import Company

User = get_user_model()


class PropositionSldTest(TestCase):
    def setUp(self):
        self.company = Company.objects.create(nom="Acme", slug="pv81-acme")
        self.crm_client = Client.objects.create(
            company=self.company, nom="Client PV81", email="pv81@example.com")
        self.devis = Devis.objects.create(
            company=self.company, reference="DV-PV81-1",
            client=self.crm_client,
            roof_layout={"_pans_geometry": [
                {"label": "Sud", "nb_panneaux": 14, "azimut_deg": 180,
                 "inclinaison_deg": 20}]})
        panneau = Produit.objects.create(
            company=self.company, nom="Panneau PV 550W mono",
            sku="PV81-PAN", prix_vente=Decimal("1234"),
            prix_achat=Decimal("789"), quantite_stock=100)
        onduleur = Produit.objects.create(
            company=self.company, nom="Onduleur réseau 10kW triphasé",
            sku="PV81-OND", prix_vente=Decimal("12345"),
            prix_achat=Decimal("9876"), quantite_stock=10)
        LigneDevis.objects.create(
            devis=self.devis, produit=panneau,
            designation="Panneau PV 550W mono", quantite=14,
            prix_unitaire=Decimal("1234"))
        LigneDevis.objects.create(
            devis=self.devis, produit=onduleur,
            designation="Onduleur réseau 10kW triphasé", quantite=1,
            prix_unitaire=Decimal("12345"))

    def _concevoir(self):
        from apps.ventes.electrical_service import build_electrical_design
        return build_electrical_design(self.devis)

    def _token(self):
        jeton = str(uuid.uuid4())
        ShareLink.objects.create(
            company=self.company, devis=self.devis, token=jeton)
        return jeton

    def test_none_sans_conception_electrique(self):
        self.assertIsNone(self.devis.electrical_design)
        self.assertIsNone(_safe_sld_svg(self.devis))

    def test_svg_apres_conception(self):
        self._concevoir()
        svg = _safe_sld_svg(self.devis)
        self.assertIsNotNone(svg)
        self.assertTrue(svg.startswith('<svg'))
        self.assertTrue(svg.endswith('</svg>'))
        self.assertIn('Schéma unifilaire', svg)
        self.assertIn('Client PV81', svg)      # cartouche : son propre nom
        self.assertIn('DV-PV81-1', svg)

    def test_aucun_prix_dans_le_svg(self):
        self._concevoir()
        svg = _safe_sld_svg(self.devis)
        # Aucun vocabulaire monétaire (les coordonnées SVG, elles, sont des
        # nombres nus : on n'y cherche donc pas des chiffres au hasard mais
        # les MONTANTS tels qu'ils s'écriraient s'ils fuyaient).
        for interdit in ('prix', 'marge', 'mad', 'ttc', 'remise', 'total'):
            self.assertNotIn(interdit, svg.lower())
        for montant in ('1 234', '12 345', '1234,00', '12345,00',
                        '17 276', '29 621'):
            self.assertNotIn(montant, svg)

    def test_servi_par_le_jeton_public(self):
        self._concevoir()
        resp = DjangoClient().get(
            '/api/django/public/proposal/%s/data/' % self._token())
        self.assertEqual(resp.status_code, 200)
        self.assertIn('sld_svg', resp.json())
        self.assertIn('<svg', resp.json()['sld_svg'])

    def test_cle_toujours_presente_meme_sans_design(self):
        # Une clé absente forcerait la page publique à deviner : elle vaut
        # None, jamais rien.
        resp = DjangoClient().get(
            '/api/django/public/proposal/%s/data/' % self._token())
        self.assertEqual(resp.status_code, 200)
        charge = resp.json()
        self.assertIn('sld_svg', charge)
        self.assertIsNone(charge['sld_svg'])

    def test_lecture_pure_aucune_ecriture(self):
        self._concevoir()
        self.devis.refresh_from_db()
        statut, empreinte = self.devis.statut, self.devis.electrical_design_hash
        _safe_sld_svg(self.devis)
        self.devis.refresh_from_db()
        self.assertEqual(self.devis.statut, statut)
        self.assertEqual(self.devis.electrical_design_hash, empreinte)
        self.assertEqual(self.devis.lignes.count(), 2)
