"""ARRONDI-100 (fondateur, 02/10/2026) — « tous mes devis finissent par deux
zéros, sans centimes : garde les prix des articles, baisse juste le total au
palier de 100 DH inférieur ».

Cas d'origine : DEV-202609-0116 imprimait 150 000,32 MAD (sans batterie) et
164 000,33 MAD (avec batterie) — des prix saisis TTC à l'écran, stockés HT à
deux décimales (50 000 TTC → 41 666,67 HT), dont la somme laissait des
centimes.

Ce que ces tests verrouillent :

* le noyau (``selectors._canonical_totaux(arrondi_pas=…)``) ramène le TTC au
  multiple de 100 INFÉRIEUR par une baisse de HT, ``ht_net + tva == ttc`` au
  centime, chaque TVA = ``q(base × taux)``, aucune ligne touchée ;
* l'argent d'un devis (``Devis.total_ttc``, ``option_totaux`` par option)
  porte ce palier, et le PDF l'imprime en ligne « Arrondi commercial » ;
* la facture d'un BC et l'avoir total de cette facture reprennent le palier :
  jamais plus que le devis signé, jamais plus que le facturé.

Miroir écran : ``frontend/src/features/ventes/remise.test.mjs`` (mêmes cas).
"""
from decimal import Decimal
from types import SimpleNamespace

from django.contrib.auth import get_user_model
from django.test import SimpleTestCase, TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from apps.ventes.domain.argent import PAS_ARRONDI_DEVIS
from apps.ventes.selectors import _canonical_totaux

User = get_user_model()
_CTR = [0]


def _nxt():
    _CTR[0] += 1
    return _CTR[0]


def _q(x):
    return Decimal(str(x)).quantize(Decimal('0.01'))


def _ligne(qte, pu, taux):
    return SimpleNamespace(
        total_ht=Decimal(str(qte)) * Decimal(str(pu)),
        taux_tva_effectif=Decimal(str(taux)))


# DEV-202609-0116 (prod, lu le 02/10/2026) — option SANS batterie : onduleur
# réseau + lignes communes (les accessoires Huawei sont retirés du panier, QF9).
LIGNES_SANS_0116 = [
    _ligne(1, '30000.00', 20),     # Onduleur injection 30 kW
    _ligne(42, '1200.00', 10),     # Panneaux 715 W (TVA 10 %)
    _ligne(42, '416.67', 20),      # Structures
    _ligne(84, '66.67', 20),       # Socles
    _ligne(160, '10.83', 20),      # Câble solaire
    _ligne(115, '11.67', 20),      # Câble de terre
    _ligne(1, '1666.67', 20),      # Accessoires
    _ligne(1, '8333.33', 20),      # Tableau AC/DC
    _ligne(1, '11666.67', 20),     # Installation
    _ligne(1, '958.33', 20),       # Transport
]
# Option AVEC batterie : l'onduleur hybride (41 666,67) remplace l'injection.
LIGNES_AVEC_0116 = [_ligne(1, '41666.67', 20)] + LIGNES_SANS_0116[1:]


def _totaux(lignes, pas=PAS_ARRONDI_DEVIS, remise='0'):
    return _canonical_totaux(
        lignes, remise_globale_pct=Decimal(remise),
        fallback_taux=Decimal('20'), arrondi_pas=pas)


class NoyauArrondiTests(SimpleTestCase):

    def _invariants(self, t):
        self.assertEqual(t['ht_net'] + t['tva'], t['ttc'])
        self.assertEqual(t['ht_brut'] - t['remise'] - t['arrondi'],
                         t['ht_net'])
        self.assertGreaterEqual(t['arrondi'], Decimal('0'))
        self.assertEqual(
            sum((b['ht_net'] for b in t['tva_par_taux']), Decimal('0')),
            t['ht_net'])
        for b in t['tva_par_taux']:
            self.assertEqual(
                b['montant'],
                (b['ht_net'] * Decimal(str(b['taux'])) / 100).quantize(
                    Decimal('0.01'), rounding='ROUND_HALF_UP'))

    def test_dev_202609_0116_sans_batterie(self):
        exact = _totaux(LIGNES_SANS_0116, pas=None)
        self.assertEqual(exact['ttc'], Decimal('150000.32'))
        self.assertEqual(exact['arrondi'], Decimal('0.00'))
        t = _totaux(LIGNES_SANS_0116)
        self.assertEqual(t['ttc'], Decimal('150000.00'))
        self.assertEqual(t['ht_brut'], Decimal('129200.27'))
        self.assertEqual(t['arrondi'], Decimal('0.27'))
        self.assertEqual(t['ht_net'], Decimal('129200.00'))
        self._invariants(t)

    def test_dev_202609_0116_avec_batterie(self):
        self.assertEqual(_totaux(LIGNES_AVEC_0116, pas=None)['ttc'],
                         Decimal('164000.33'))
        t = _totaux(LIGNES_AVEC_0116)
        self.assertEqual(t['ttc'], Decimal('164000.00'))
        self._invariants(t)

    def test_cinquante_sept_dirhams_disparaissent(self):
        # 125 047,50 HT à 20 % = 150 057,00 TTC → 150 000,00.
        t = _totaux([_ligne(1, '125047.50', 20)])
        self.assertEqual(t['ttc'], Decimal('150000.00'))
        self.assertEqual(t['arrondi'], Decimal('47.50'))
        self._invariants(t)

    def test_avec_remise_globale(self):
        t = _totaux(LIGNES_SANS_0116, remise='5')
        self.assertEqual(t['ttc'] % 100, 0)
        exact = _totaux(LIGNES_SANS_0116, pas=None, remise='5')
        self.assertEqual(t['remise'], exact['remise'])
        self.assertLess(exact['ttc'] - t['ttc'], 100)
        self._invariants(t)

    def test_deja_rond_inchange(self):
        t = _totaux([_ligne(10, '1000', 20)])
        self.assertEqual(t['ttc'], Decimal('12000.00'))
        self.assertEqual(t['arrondi'], Decimal('0.00'))

    def test_sans_palier_inchange(self):
        for pas in (None, 0):
            t = _totaux(LIGNES_SANS_0116, pas=pas)
            self.assertEqual(t['ttc'], Decimal('150000.32'))
            self.assertEqual(t['arrondi'], Decimal('0.00'))

    def test_total_sous_le_palier_jamais_ramene_a_zero(self):
        t = _totaux([_ligne(1, '47.50', 20)])
        self.assertEqual(t['ttc'], Decimal('57.00'))
        self.assertEqual(t['arrondi'], Decimal('0.00'))

    def test_second_panier_cede_un_centime(self):
        # Ni le panier 20 % ni le panier 10 % seul n'atteint 24 300,00 : le
        # panier 10 % cède 0,01 HT et le 20 % porte le reste.
        t = _totaux([_ligne(1, '6223.01', 10), _ligne(1, '14609.98', 20)])
        self.assertEqual(t['ttc'], Decimal('24300.00'))
        self.assertEqual(t['arrondi'], Decimal('64.41'))
        paniers = {int(b['taux']): b for b in t['tva_par_taux']}
        self.assertEqual(paniers[10]['ht_net'], Decimal('6223.00'))
        self.assertEqual(paniers[20]['ht_net'], Decimal('14545.58'))
        self._invariants(t)

    def test_mono_taux_10_inatteignable_descend_d_un_palier(self):
        # À 10 % seul, aucune base au centime ne donne 500,00 TTC
        # (454,54 → 499,99 ; 454,55 → 500,01) : palier d'en dessous.
        t = _totaux([_ligne(1, '455.00', 10)])
        self.assertEqual(t['ttc'], Decimal('400.00'))
        self._invariants(t)

    def test_proprietes_sur_un_echantillon_deterministe(self):
        import random
        alea = random.Random(20261002)
        for _ in range(400):
            taux = alea.choice([[10, 20], [20], [10, 20, 20]])
            lignes = [_ligne(alea.randint(1, 40),
                             Decimal(alea.randint(50, 900000)) / 100,
                             alea.choice(taux))
                      for _ in range(alea.randint(1, 8))]
            remise = alea.choice(['0', '0', '5', '7.5', '10'])
            exact = _totaux(lignes, pas=None, remise=remise)
            t = _totaux(lignes, remise=remise)
            self._invariants(t)
            self.assertLessEqual(t['ttc'], exact['ttc'])
            if exact['ttc'] >= 100:
                self.assertEqual(t['ttc'] % 100, 0)
                # Un devis qui porte du 20 % atteint toujours le palier juste
                # en dessous : jamais plus de 100 MAD de baisse.
                self.assertLess(exact['ttc'] - t['ttc'], 100)


class ArrondiDevisFactureTests(TestCase):
    """L'argent du devis, son PDF, sa facture de BC et l'avoir total."""

    def setUp(self):
        from apps.crm.models import Client
        from authentication.models import Company
        self.company = Company.objects.create(
            nom='ARR100 Co', slug=f'arr100-{_nxt()}')
        self.user = User.objects.create_user(
            username=f'arr100_{_nxt()}', password='x',
            role_legacy='admin', company=self.company)
        self.api = APIClient()
        self.api.credentials(
            HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(self.user)}')
        self.client_obj = Client.objects.create(
            company=self.company, nom='ARR100', prenom='Client',
            telephone='+212600001100')

    def _devis(self, lignes, statut='brouillon'):
        from apps.stock.models import Produit
        from apps.ventes.models import Devis, LigneDevis
        devis = Devis.objects.create(
            company=self.company, created_by=self.user,
            client=self.client_obj, reference=f'DEV-ARR100-{_nxt()}',
            statut=statut, taux_tva=Decimal('20'))
        for desig, qte, pu, taux in lignes:
            produit = Produit.objects.create(
                company=self.company, nom=desig, sku=f'ARR100-{_nxt()}',
                prix_vente=Decimal(pu), quantite_stock=500)
            LigneDevis.objects.create(
                devis=devis, produit=produit, designation=desig,
                quantite=Decimal(qte), prix_unitaire=Decimal(pu),
                taux_tva=Decimal(taux))
        return devis

    def test_total_du_devis_et_option_au_palier(self):
        from apps.ventes.utils.options import option_totaux
        devis = self._devis([('Kit PV', '1', '125047.50', '20')])
        self.assertEqual(devis.total_ttc, Decimal('150000.00'))
        self.assertEqual(devis.total_ht, Decimal('125000.00'))
        tot = option_totaux(devis)
        self.assertEqual(tot['ttc'], Decimal('150000.00'))
        self.assertEqual(tot['arrondi'], Decimal('47.50'))

    def test_pdf_imprime_la_ligne_arrondi(self):
        from apps.ventes.quote_engine.builder import build_quote_data
        devis = self._devis([
            ('Panneau Canadian Solar 715W', '42', '1200.00', '10'),
            ('Onduleur injection 30kW', '1', '30000.00', '20'),
            ('Installation', '1', '11666.67', '20'),
            ('Structures acier', '42', '416.67', '20'),
        ])
        data = build_quote_data(devis)
        tot = data['totaux_all']
        self.assertEqual(Decimal(str(tot['ttc'])) % 100, 0)
        self.assertGreater(tot['arrondi'], 0)
        self.assertEqual(_q(tot['ttc']), devis.total_ttc)
        from apps.ventes.quote_engine import generate_devis_premium as g
        ancien = g.DISCOUNT_PCT
        g.DISCOUNT_PCT = 0.0
        try:
            html = g._totals_block_rows(tot, colspan=5)
        finally:
            g.DISCOUNT_PCT = ancien
        self.assertIn('Arrondi commercial', html)
        self.assertIn('Total HT', html)
        # La chaîne imprimée s'additionne : Sous-total − Arrondi + TVA = TTC.
        self.assertEqual(
            _q(tot['ht_brut']) - _q(tot['arrondi']) + _q(tot['tva']),
            _q(tot['ttc']))

    def test_facture_de_bc_et_avoir_total_reprennent_le_palier(self):
        from apps.facturation.models import Avoir
        from apps.ventes.models import BonCommande, Devis, Facture
        devis = self._devis([('Kit PV', '1', '125047.50', '20')],
                            statut=Devis.Statut.ACCEPTE)
        bc = BonCommande.objects.create(
            company=self.company, reference=f'BC-ARR100-{_nxt()}',
            devis=devis, client=self.client_obj,
            statut=BonCommande.Statut.CONFIRME)
        resp = self.api.post(
            f'/api/django/ventes/bons-commande/{bc.id}/creer-facture/',
            {}, format='json')
        self.assertEqual(resp.status_code, 201, resp.data)
        facture = Facture.objects.get(bon_commande=bc)
        self.assertEqual(facture.arrondi_pas, 100)
        self.assertEqual(facture.total_ttc, devis.total_ttc)
        self.assertEqual(facture.total_ttc, Decimal('150000.00'))
        self.assertEqual(facture.totaux_affichage['arrondi'],
                         Decimal('47.50'))
        facture.statut = Facture.Statut.EMISE
        facture.save(update_fields=['statut'])

        resp = self.api.post(
            f'/api/django/ventes/factures/{facture.id}/creer-avoir/',
            {'motif': 'Retour total'}, format='json')
        self.assertEqual(resp.status_code, 201, resp.data)
        avoir = Avoir.objects.get(pk=resp.data['id'])
        self.assertEqual(avoir.arrondi_pas, 100)
        self.assertEqual(avoir.total_ttc, facture.total_ttc)

    def test_facture_saisie_a_la_main_jamais_arrondie(self):
        from apps.stock.models import Produit
        from apps.ventes.models import Facture, LigneFacture
        facture = Facture.objects.create(
            company=self.company, reference=f'FAC-ARR100-{_nxt()}',
            client=self.client_obj, statut=Facture.Statut.BROUILLON,
            taux_tva=Decimal('20'))
        produit = Produit.objects.create(
            company=self.company, nom='Prestation', sku=f'ARR100-{_nxt()}',
            prix_vente=Decimal('125047.50'), quantite_stock=5)
        LigneFacture.objects.create(
            facture=facture, produit=produit, designation='Prestation',
            quantite=Decimal('1'), prix_unitaire=Decimal('125047.50'),
            taux_tva=Decimal('20'))
        self.assertEqual(facture.arrondi_pas, 0)
        self.assertEqual(facture.total_ttc, Decimal('150057.00'))
