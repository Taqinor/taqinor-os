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
        # VNT105 — le délégué echeancier._repartir_au_centime est retiré :
        # LE service vit dans facturation.totaux (ATOT6).
        from apps.facturation.totaux import repartir_au_centime
        parts = repartir_au_centime(
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


class PartDeLaVente388Test(_Base):
    """VNT36 — sur le panier RÉEL du 388 (49 000 TTC), la facture de tranche
    imprime sa part CALCULÉE au rendu (« Acompte : 15000.00 MAD TTC (30.61 %
    du prix convenu 49000.00 MAD) » ; la dernière « Solde : 34000.00 MAD TTC
    (reste de la vente) »), jamais lue du libellé ni de
    ``Facture.pourcentage`` ; la TVA ventilée par taux est imprimée."""

    LIBRE = [{'type': 'acompte', 'libelle': 'Acompte', 'unite': 'montant',
              'pct_or_montant': 15000},
             {'type': 'solde', 'libelle': 'Solde', 'unite': 'montant',
              'pct_or_montant': 34000}]

    def _devis_388(self, reference, echeancier):
        from apps.ventes.tests.test_echeancier_somme_total import (
            creer_devis_388)
        from apps.ventes.utils.options import option_totaux
        devis = creer_devis_388(self.company, self.user, self.client_obj,
                                reference, echeancier)
        tot = option_totaux(devis)
        self.assertEqual((tot['ht'], tot['tva'], tot['ttc']),
                         (Decimal('41553.33'), Decimal('7446.67'),
                          Decimal('49000.00')))
        self.assertEqual(
            [(Decimal(str(b['base_ht'])), Decimal(str(b['montant'])))
             for b in tot['tva_par_taux']],
            [(Decimal('8640.00'), Decimal('864.00')),
             (Decimal('32913.33'), Decimal('6582.67'))])
        return devis

    def _html(self, facture):
        from apps.ventes.utils.pdf import (
            _company_context, _render_html, contexte_vente_facture)
        facture.refresh_from_db()
        ctx = _company_context(company=self.company)
        ctx['facture'] = facture
        ctx.update(contexte_vente_facture(facture))
        return _render_html('facture.html', ctx)

    def _paniers(self, facture):
        return [(b['taux'], b['base_ht'], b['montant'])
                for b in facture.tva_par_taux]

    def test_acompte_libre_15000_puis_solde(self):
        devis = self._devis_388('DEV-VNT36-0388', self.LIBRE)
        acompte, solde = self._facturer_tout_388(devis, 2)
        self.assertEqual((acompte.total_ttc, acompte.total_ht,
                          acompte.total_tva),
                         (Decimal('15000.00'), Decimal('12720.41'),
                          Decimal('2279.59')))
        self.assertEqual(self._paniers(acompte), [
            (Decimal('10.00'), Decimal('2644.90'), Decimal('264.49')),
            (Decimal('20.00'), Decimal('10075.51'), Decimal('2015.10'))])
        self.assertEqual((solde.total_ttc, solde.total_ht, solde.total_tva),
                         (Decimal('34000.00'), Decimal('28832.92'),
                          Decimal('5167.08')))
        self.assertEqual(self._paniers(solde), [
            (Decimal('10.00'), Decimal('5995.10'), Decimal('599.51')),
            (Decimal('20.00'), Decimal('22837.82'), Decimal('4567.57'))])
        for i, (base, tva) in enumerate(((Decimal('8640.00'),
                                          Decimal('864.00')),
                                         (Decimal('32913.33'),
                                          Decimal('6582.67')))):
            self.assertEqual(sum(self._paniers(f)[i][1]
                                 for f in (acompte, solde)), base)
            self.assertEqual(sum(self._paniers(f)[i][2]
                                 for f in (acompte, solde)), tva)
        html_acompte = self._html(acompte)
        self.assertIn('Acompte : 15000.00 MAD TTC (30.61 % du prix convenu '
                      '49000.00 MAD)', html_acompte)
        for montant in ('12720.41', '2644.90', '264.49', '10075.51',
                        '2015.10'):
            self.assertIn(f'{montant} MAD', html_acompte)
        html_solde = self._html(solde)
        self.assertIn('Solde : 34000.00 MAD TTC (reste de la vente)',
                      html_solde)
        self.assertNotIn('du prix convenu', html_solde)
        for montant in ('28832.92', '5995.10', '599.51', '22837.82',
                        '4567.57'):
            self.assertIn(f'{montant} MAD', html_solde)
        # Jamais lue du pourcentage stocké ni du libellé de la facture.
        type(acompte).objects.filter(pk=acompte.pk).update(
            pourcentage=Decimal('10'), libelle='Solde 10 %')
        self.assertIn('(30.61 % du prix convenu', self._html(acompte))

    def test_non_regression_acompte_30_pour_cent(self):
        devis = self._devis_388('DEV-VNT36-0030', [
            {'type': 'acompte', 'pct_or_montant': 30},
            {'type': 'materiel', 'pct_or_montant': 60},
            {'type': 'solde', 'pct_or_montant': 10}])
        (acompte,) = self._facturer_tout_388(devis, 1)
        self.assertEqual((acompte.total_ttc, acompte.total_ht,
                          acompte.total_tva),
                         (Decimal('14700.00'), Decimal('12466.00'),
                          Decimal('2234.00')))
        self.assertEqual(self._paniers(acompte), [
            (Decimal('10.00'), Decimal('2592.00'), Decimal('259.20')),
            (Decimal('20.00'), Decimal('9874.00'), Decimal('1974.80'))])
        self.assertIn('Acompte : 14700.00 MAD TTC (30.00 % du prix convenu '
                      '49000.00 MAD)', self._html(acompte))

    def _facturer_tout_388(self, devis, n):
        from apps.ventes.models import Facture
        factures = []
        for _ in range(n):
            r = self.api.post(
                f'/api/django/ventes/devis/{devis.id}/generer-facture/')
            self.assertEqual(r.status_code, 201, r.data)
            factures.append(Facture.objects.get(pk=r.data['id']))
        return factures


class MonoTauxInchangeTest(_Base):
    def test_facture_mono_taux_sans_ventilation(self):
        devis = self._devis('DEV-CIQ215-0020', [
            ('Centrale PV', '100000', '20.00')])
        factures = self._facturer_tout(devis)
        for f in factures:
            self.assertIsNone(f.ventilation_tva)
            self.assertEqual(len(f.tva_par_taux), 1)
            self.assertEqual(f.tva_par_taux[0]['montant'], f.montant_tva)
