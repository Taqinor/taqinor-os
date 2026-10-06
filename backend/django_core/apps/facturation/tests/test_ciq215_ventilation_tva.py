"""CIQ215 — facture de tranche : la TVA ventilée par taux (base 10 % / TVA
10 % / base 20 % / TVA 20 %) au lieu d'un taux « mélangé » qui n'existe pas
dans la loi.

Run :
    powershell -File scripts/test-backend.ps1 -RestoreDb \\
        -Modules "apps.facturation.tests.test_ciq215_ventilation_tva"
"""
import xml.etree.ElementTree as ET
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import SimpleTestCase, TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

User = get_user_model()

#: Échéancier 30/40/20/10 (jalons C&I).
ECHEANCIER = [
    {'type': 'acompte', 'pct_or_montant': 30, 'jalon': 'commande'},
    {'type': 'intermediaire', 'pct_or_montant': 40,
     'jalon': 'livraison_materiel'},
    {'type': 'intermediaire', 'pct_or_montant': 20,
     'jalon': 'mise_en_service'},
    {'type': 'solde', 'pct_or_montant': 10, 'jalon': 'reception_definitive'},
]


class RepartitionAuCentimeTest(SimpleTestCase):
    def test_plus_fort_reste_somme_exacte(self):
        from apps.ventes.utils.echeancier import _repartir_au_centime
        parts = _repartir_au_centime(
            Decimal('100.00'), {'a': Decimal('1'), 'b': Decimal('1'),
                                'c': Decimal('1')})
        self.assertEqual(sum(parts.values()), Decimal('100.00'))
        self.assertEqual(sorted(parts.values()),
                         [Decimal('33.33'), Decimal('33.33'), Decimal('33.34')])


class _Base(TestCase):
    def setUp(self):
        from apps.crm.models import Client
        from authentication.models import Company
        self.company = Company.objects.get_or_create(
            slug='ciq215-co', defaults={'nom': 'CIQ215 Co'})[0]
        self.client_obj = Client.objects.create(
            company=self.company, nom='Ferme', prenom='CIQ215',
            email='ciq215@example.com')
        self.user = User.objects.create_user(
            username='ciq215_resp', password='x', role_legacy='responsable',
            company=self.company)
        self.api = APIClient()
        self.api.credentials(
            HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(self.user)}')

    def _devis(self, ref, lignes):
        from apps.ventes.models import Devis, LigneDevis
        devis = Devis.objects.create(
            company=self.company, reference=ref, client=self.client_obj,
            statut='accepte', taux_tva=Decimal('20.00'),
            mode_installation='industriel', echeancier=ECHEANCIER)
        for designation, pu, taux in lignes:
            LigneDevis.objects.create(
                devis=devis, designation=designation, quantite=Decimal('1'),
                prix_unitaire=Decimal(pu), remise=Decimal('0'),
                taux_tva=Decimal(taux))
        return devis

    def _facturer_tout(self, devis):
        from apps.ventes.models import Facture
        factures = []
        for _ in ECHEANCIER:
            r = self.api.post(
                f'/api/django/ventes/devis/{devis.id}/generer-facture/')
            self.assertEqual(r.status_code, 201, r.data)
            factures.append(Facture.objects.get(pk=r.data['id']))
        return factures


class VentilationTrancheMixteTest(_Base):
    def setUp(self):
        super().setUp()
        self.devis = self._devis('DEV-CIQ215-0010', [
            ('Pompe solaire', '100000', '10.00'),
            ('Structure', '200000', '20.00'),
        ])
        self.factures = self._facturer_tout(self.devis)

    def test_chaque_facture_porte_deux_paniers_reconcilies(self):
        for f in self.factures:
            paniers = f.tva_par_taux
            self.assertEqual([b['taux'] for b in paniers],
                             [Decimal('10.00'), Decimal('20.00')])
            self.assertEqual(sum(b['base_ht'] for b in paniers), f.total_ht)
            self.assertEqual(sum(b['montant'] for b in paniers), f.total_tva)

    def test_somme_des_factures_egale_le_devis_par_taux(self):
        bases, tvas = {}, {}
        for f in self.factures:
            for b in f.tva_par_taux:
                bases[b['taux']] = bases.get(b['taux'], 0) + b['base_ht']
                tvas[b['taux']] = tvas.get(b['taux'], 0) + b['montant']
        self.assertEqual(bases, {Decimal('10.00'): Decimal('100000.00'),
                                 Decimal('20.00'): Decimal('200000.00')})
        self.assertEqual(tvas, {Decimal('10.00'): Decimal('10000.00'),
                                Decimal('20.00'): Decimal('40000.00')})

    def test_premiere_tranche_au_prorata(self):
        premiere = self.factures[0]
        self.assertEqual(premiere.ventilation_tva, [
            {'taux': '10.00', 'base_ht': '30000.00', 'montant': '3000.00'},
            {'taux': '20.00', 'base_ht': '60000.00', 'montant': '12000.00'},
        ])

    def test_export_dgi_liste_deux_taux(self):
        from apps.ventes.dgi.dgi_export import build_ubl_xml
        xml = build_ubl_xml(self.factures[1])
        if isinstance(xml, bytes):
            xml = xml.decode('utf-8')
        root = ET.fromstring(xml)
        pourcents = [el.text for el in root.iter()
                     if el.tag.endswith('}Percent')]
        self.assertEqual(sorted(set(pourcents)), ['10.00', '20.00'])

    def test_pdf_montre_deux_lignes_de_tva(self):
        from apps.ventes.utils.pdf import _company_context, _render_html
        ctx = _company_context(company=self.company)
        ctx['facture'] = self.factures[0]
        html = _render_html('facture.html', ctx)
        self.assertIn('(10.00%)', html)
        self.assertIn('(20.00%)', html)
        self.assertIn('Base HT (10.00%)', html)
        self.assertIn('voir ventilation', html)
        # Le taux « mélangé » 50 000 ÷ 300 000 = 16,67 % n'est plus imprimé.
        self.assertNotIn('16.67%', html)


class MonoTauxInchangeTest(_Base):
    def test_facture_mono_taux_sans_ventilation(self):
        devis = self._devis('DEV-CIQ215-0020', [
            ('Centrale PV', '100000', '20.00')])
        factures = self._facturer_tout(devis)
        for f in factures:
            self.assertIsNone(f.ventilation_tva)
            self.assertEqual(len(f.tva_par_taux), 1)
            self.assertEqual(f.tva_par_taux[0]['montant'], f.montant_tva)
