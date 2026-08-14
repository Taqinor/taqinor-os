"""PV47 — le bordereau électrique reporté en LIGNES de devis, sur clic.

Trois garanties :

* les lignes n'apparaissent QUE sur l'appel explicite (jamais un effet de bord
  d'un recalcul d'étude — sinon le prix du devis bougerait tout seul) ;
* aucun prix n'est inventé : un produit catalogue sans prix part à 0 avec
  « à chiffrer » dans son intitulé, et une ligne sans produit correspondant
  devient une NOTE (sans prix) + une entrée dans ``manques`` ;
* garde de statut PV15 : brouillon/envoyé seulement, 409 au-delà, et le statut
  n'est jamais ÉCRIT (règle #4).

Run :
    DB_NAME=erp_ventes python manage.py test \
        apps.ventes.tests.test_pv47_boq_lignes -v 2
"""
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import SimpleTestCase, TestCase
from rest_framework.test import APIClient

from apps.crm.models import Client
from apps.stock.models import Categorie, Produit
from apps.ventes import services
from apps.ventes.models import Devis, LigneDevis
from authentication.models import Company

User = get_user_model()

#: Bordereau tel que ``core.electrique`` le rend (désignations RÉELLES).
BOM = [
    {'designation': 'Câble solaire H1Z2Z2-K 1000 V DC (2 conducteurs par '
                    'chaîne, + et −) 6,0 mm²',
     'quantite': 80.0, 'spec': 'chute de tension 0,62 %'},
    {'designation': 'Câble AC U-1000 R2V cuivre (P + N + T, monophasé) '
                    '10,0 mm²',
     'quantite': 45.0, 'spec': 'chute de tension 0,41 %'},
    {'designation': 'PDC1 — Parafoudre DC Type 2 (coffret de chaînes)',
     'quantite': 1, 'spec': 'In 20 kA ; UTE C 15-712-1 §7'},
    {'designation': 'QAC1 — Disjoncteur AC bipolaire courbe C',
     'quantite': 1, 'spec': '32 A / 230 V ; NF C 15-100 §433.1'},
    {'designation': 'Rail de fixation aluminium', 'quantite': 40, 'spec': ''},
    {'designation': 'Pince de fixation (milieu + extrémité)', 'quantite': 44,
     'spec': ''},
]


class AppariementPurTest(SimpleTestCase):
    """L'appariement est du calcul pur — testable sans base."""

    class _P:
        def __init__(self, nom, pk=1, prix=0):
            self.nom = nom
            self.pk = pk
            self.prix_vente = Decimal(str(prix))

    CATALOGUE = [
        _P('Câble solaire H1Z2Z2-K 4 mm² (au mètre)', 1),
        _P('Câble solaire H1Z2Z2-K 6 mm² (au mètre)', 2),
        _P('Câble solaire H1Z2Z2-K 10 mm² (au mètre)', 3),
        _P('Parafoudre DC type 2 1000 V', 4),
        _P('Parafoudre AC type 2', 5),
        _P('Disjoncteur AC courbe C 32 A monophasé', 6),
        _P('Disjoncteur AC courbe C 32 A tétrapolaire', 7),
        _P('Fusible gPV 1000 VDC 15 A', 8),
    ]

    def _apparier(self, designation, spec=''):
        return services._boq_apparier(designation, spec, self.CATALOGUE)

    def test_cable_apparie_par_section(self):
        produit = self._apparier(BOM[0]['designation'], BOM[0]['spec'])
        self.assertIsNotNone(produit)
        self.assertEqual(produit.pk, 2)          # 6 mm², pas 4 ni 10

    def test_cable_ac_sans_equivalent_catalogue(self):
        # Le catalogue PVG3 ne référence que du câble SOLAIRE : pas d'apparie-
        # ment forcé sur une section identique d'une autre famille de câble.
        self.assertIsNone(
            self._apparier(BOM[1]['designation'], BOM[1]['spec']))

    def test_parafoudre_dc_ne_devient_jamais_ac(self):
        produit = self._apparier(BOM[2]['designation'], BOM[2]['spec'])
        self.assertEqual(produit.pk, 4)

    def test_disjoncteur_apparie_calibre_et_polarite(self):
        produit = self._apparier(BOM[3]['designation'], BOM[3]['spec'])
        self.assertEqual(produit.pk, 6)          # 32 A monophasé

    def test_calibre_absent_du_catalogue_nest_pas_approxime(self):
        # 16 A calculé, catalogue 32 A seulement → AUCUN appariement (proposer
        # un autre calibre serait une erreur d'étude déguisée en commodité).
        self.assertIsNone(self._apparier(
            'QAC1 — Disjoncteur AC bipolaire courbe C',
            '16 A / 230 V ; NF C 15-100 §433.1'))

    def test_ligne_non_electrique_ignoree(self):
        for designation in ('Rail de fixation aluminium',
                            'Pince de fixation (milieu + extrémité)',
                            'Crochet / patte de fixation toiture'):
            self.assertIsNone(services._boq_famille(designation), designation)

    def test_porte_fusible_nest_pas_un_fusible(self):
        self.assertEqual(services._boq_famille('Porte-fusible 1000 VDC'),
                         'porte_fusible')
        self.assertEqual(services._boq_famille('Fusible gPV 1000 VDC 15 A'),
                         'fusible')


class AjouterBoqEndpointTest(TestCase):
    def setUp(self):
        self.company = Company.objects.create(nom="Acme", slug="pv47-acme")
        self.user = User.objects.create_user(
            username="pv47_resp", password="x",
            role_legacy="responsable", company=self.company)
        self.api = APIClient()
        self.api.force_authenticate(self.user)
        self.crm_client = Client.objects.create(
            company=self.company, nom="Client PV47", email="pv47@example.com")
        self.cat_cables = Categorie.objects.create(
            company=self.company, nom='Câbles')
        self.cat_prot = Categorie.objects.create(
            company=self.company, nom='Protection & accessoires')
        # SKU PVG3 : référencés, PRIX VIDES tant que le fondateur ne les a pas
        # renseignés.
        self.cable6 = Produit.objects.create(
            company=self.company, categorie=self.cat_cables,
            nom='Câble solaire H1Z2Z2-K 6 mm² (au mètre)',
            sku='CAB-H1Z2Z2-6-M', prix_vente=Decimal('0'),
            prix_achat=Decimal('0'), quantite_stock=5000)
        self.parafoudre_dc = Produit.objects.create(
            company=self.company, categorie=self.cat_prot,
            nom='Parafoudre DC type 2 1000 V', sku='PARA-DC-T2-1000',
            prix_vente=Decimal('0'), prix_achat=Decimal('0'),
            quantite_stock=100)
        self.disjoncteur = Produit.objects.create(
            company=self.company, categorie=self.cat_prot,
            nom='Disjoncteur AC courbe C 32 A monophasé',
            sku='DISJ-AC-C-32-1P', prix_vente=Decimal('450'),
            prix_achat=Decimal('300'), quantite_stock=100)

    def _make_devis(self, statut=Devis.Statut.BROUILLON, bom=None):
        devis = Devis.objects.create(
            company=self.company, reference="DV-PV47-%s" % statut,
            client=self.crm_client, statut=statut,
            electrical_design={'bom': BOM if bom is None else bom})
        panneau = Produit.objects.create(
            company=self.company, nom='Panneau PV 550W mono',
            sku='PV47-PAN-%s' % statut, prix_vente=Decimal('1000'),
            prix_achat=Decimal('600'), quantite_stock=100)
        LigneDevis.objects.create(
            devis=devis, produit=panneau, designation='Panneau PV 550W mono',
            quantite=20, prix_unitaire=Decimal('1000'))
        return devis

    def _url(self, devis):
        return ("/api/django/ventes/devis/%s/ajouter-boq-electrique/"
                % devis.id)

    def test_lignes_creees_seulement_sur_le_clic(self):
        devis = self._make_devis()
        self.assertEqual(devis.lignes.count(), 1)      # rien d'automatique
        resp = self.api.post(self._url(devis), {}, format="json")
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.data['creees'], 4)       # 2 câbles + 2 organes
        self.assertEqual(devis.lignes.count(), 5)

    def test_produit_sans_prix_part_a_zero_et_le_dit(self):
        devis = self._make_devis()
        self.api.post(self._url(devis), {}, format="json")
        ligne = devis.lignes.get(produit=self.cable6)
        self.assertEqual(ligne.prix_unitaire, Decimal('0'))
        self.assertIn('à chiffrer', ligne.designation)
        self.assertEqual(ligne.type_ligne, LigneDevis.TypeLigne.PRODUIT)

    def test_produit_avec_prix_garde_son_prix_sans_mention(self):
        devis = self._make_devis()
        self.api.post(self._url(devis), {}, format="json")
        ligne = devis.lignes.get(produit=self.disjoncteur)
        self.assertEqual(ligne.prix_unitaire, Decimal('450'))
        self.assertNotIn('à chiffrer', ligne.designation)

    def test_sans_correspondance_une_note_et_un_manque(self):
        devis = self._make_devis()
        resp = self.api.post(self._url(devis), {}, format="json")
        manques = [m['designation'] for m in resp.data['manques']]
        self.assertTrue(any('Câble AC' in m for m in manques))
        note = devis.lignes.get(type_ligne=LigneDevis.TypeLigne.NOTE)
        self.assertIsNone(note.produit)
        self.assertIsNone(note.prix_unitaire)
        self.assertIn('à chiffrer', note.designation)

    def test_lignes_non_electriques_ignorees(self):
        devis = self._make_devis()
        self.api.post(self._url(devis), {}, format="json")
        designations = list(
            devis.lignes.values_list('designation', flat=True))
        self.assertFalse(any('Rail' in d for d in designations))
        self.assertFalse(any('Pince' in d for d in designations))

    def test_second_clic_ne_duplique_pas(self):
        devis = self._make_devis()
        self.api.post(self._url(devis), {}, format="json")
        avant = devis.lignes.count()
        resp = self.api.post(self._url(devis), {}, format="json")
        self.assertEqual(resp.data['creees'], 0)
        self.assertTrue(resp.data['deja_presentes'])
        self.assertEqual(devis.lignes.count(), avant)

    def test_garde_de_statut_409(self):
        for statut in (Devis.Statut.ACCEPTE, Devis.Statut.REFUSE,
                       Devis.Statut.EXPIRE):
            with self.subTest(statut=statut):
                devis = self._make_devis(statut=statut)
                resp = self.api.post(self._url(devis), {}, format="json")
                self.assertEqual(resp.status_code, 409)
                self.assertEqual(devis.lignes.count(), 1)
                devis.refresh_from_db()
                self.assertEqual(devis.statut, statut)  # jamais ÉCRIT

    def test_envoye_reste_modifiable(self):
        devis = self._make_devis(statut=Devis.Statut.ENVOYE)
        resp = self.api.post(self._url(devis), {}, format="json")
        self.assertEqual(resp.status_code, 200)
        self.assertGreater(resp.data['creees'], 0)

    def test_sans_conception_electrique_400(self):
        devis = Devis.objects.create(
            company=self.company, reference="DV-PV47-VIDE",
            client=self.crm_client)
        resp = self.api.post(self._url(devis), {}, format="json")
        self.assertEqual(resp.status_code, 400)
        self.assertEqual(devis.lignes.count(), 0)

    def test_scope_societe_404(self):
        autre = Company.objects.create(nom="Autre", slug="pv47-autre")
        devis = Devis.objects.create(
            company=autre, reference="DV-PV47-AUTRE",
            client=self.crm_client, electrical_design={'bom': BOM})
        resp = self.api.post(self._url(devis), {}, format="json")
        self.assertEqual(resp.status_code, 404)
        self.assertEqual(devis.lignes.count(), 0)

    def test_aucun_prix_achat_dans_la_reponse(self):
        devis = self._make_devis()
        resp = self.api.post(self._url(devis), {}, format="json")
        blob = repr(resp.data).lower()
        self.assertNotIn('prix_achat', blob)
        self.assertNotIn('marge', blob)
