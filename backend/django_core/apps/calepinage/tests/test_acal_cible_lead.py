"""ACAL194 (C-ACAL-004) — la cible d'un calepinage SANS devis vient du lead.

Ce qui est prouvé ici :

* un lead avec facture d'hiver et ville : ``cible`` = le MÊME nombre de
  panneaux que le devis automatique (``build_devis_auto``) pour ce lead,
  ``source: 'factures'`` — plus de bouchon CAL147 rendant ``None`` ;
* ``taille_souhaitee_kwc`` est SOUVERAINE (``source: 'lead'``) ;
* sans facture, le motif du moteur est NOMMÉ (``cible.refus`` et
  avertissement), jamais une puissance devinée ;
* un devis lié garde ``source: 'devis'`` ;
* lecture pure : deux GET rendent la même cible, rien n'est écrit.

Run :
    python manage.py test apps.calepinage.tests.test_acal_cible_lead -v2
"""
from decimal import Decimal

from apps.calepinage.models import Calepinage
from apps.crm.models import Client, Lead
from apps.stock.models import Produit
from apps.ventes.models import Devis

from .test_api_liste import BaseApiCalepinage, url_detail


def url_contexte(pk):
    return f'{url_detail(pk)}design-context/'


class CibleDuLeadTest(BaseApiCalepinage):
    def setUp(self):
        super().setUp()
        # Catalogue minimal (mêmes désignations que seed_catalogue).
        for nom, sku, prix in (
                ('Panneau Jinko 550W', 'A194-PAN', 1100),
                ('Onduleur réseau Huawei 5kW Monophasé', 'A194-ONDR', 14000),
                ('Onduleur hybride Deye 5kW Monophasé', 'A194-ONDH', 17000),
                ('Batterie Dyness 5 kWh', 'A194-BAT', 17000)):
            Produit.objects.create(
                company=self.company, nom=nom, sku=sku,
                prix_vente=Decimal(prix), prix_achat=Decimal('1'),
                quantite_stock=100)

    def _lead(self, **extra):
        extra.setdefault('ville', 'Casablanca')
        extra.setdefault('email', 'cible194@example.com')
        return Lead.objects.create(company=self.company, nom='Cible',
                                   prenom='194', **extra)

    def _calepinage(self, lead, **extra):
        return Calepinage.objects.create(
            company=self.company, lead_id=lead.pk, titre='Cible 194',
            **extra)

    def _contexte(self, calepinage):
        reponse = self.api.get(url_contexte(calepinage.pk))
        self.assertEqual(reponse.status_code, 200, reponse.data)
        return reponse.data

    def test_cible_du_lead_egale_la_taille_du_devis_auto(self):
        from apps.ventes.services import build_devis_auto

        lead = self._lead(facture_hiver=Decimal('1800'))
        cible = self._contexte(self._calepinage(lead))['cible']
        self.assertIsNotNone(cible)
        self.assertEqual(cible['source'], 'factures')
        self.assertIsNone(cible['refus'])

        devis = build_devis_auto(lead=lead, user=self.user,
                                 company=self.company)
        # Même lecture que ``ventes/tests/test_devis_auto`` : la ligne
        # panneau du devis automatique.
        panneaux_devis = int(next(
            li for li in devis.lignes.all()
            if 'Panneau' in li.designation).quantite)
        self.assertGreater(panneaux_devis, 0)
        self.assertEqual(cible['panneaux'], panneaux_devis)
        self.assertEqual(cible['kwc'],
                         round(cible['panneaux'] * cible['panel_watt']
                               / 1000, 2))

    def test_taille_souhaitee_souveraine(self):
        lead = self._lead(facture_hiver=Decimal('1800'),
                          taille_souhaitee_kwc=Decimal('6.5'))
        cible = self._contexte(self._calepinage(lead))['cible']
        self.assertEqual(cible['source'], 'lead')
        # plafond(6 500 / 710) = 10 — la conversion du devis automatique.
        self.assertEqual(cible['panneaux'], 10)
        self.assertEqual(cible['panel_watt'], 710)
        self.assertIsNone(cible['refus'])

    def test_sans_facture_le_motif_est_nomme(self):
        lead = self._lead()
        contexte = self._contexte(self._calepinage(lead))
        cible = contexte['cible']
        self.assertIsNotNone(cible)
        self.assertIsNone(cible['panneaux'])
        self.assertTrue(cible['refus'])
        self.assertIn('Cible de puissance non calculée : ' + cible['refus'],
                      contexte['avertissements'])
        self.assertNotIn('Aucune cible de puissance connue : renseignez-la, '
                         'ou rattachez un devis.',
                         contexte['avertissements'])

    def test_devis_lie_garde_source_devis(self):
        lead = self._lead(facture_hiver=Decimal('1800'))
        client = Client.objects.create(company=self.company, nom='Client 194')
        devis = Devis.objects.create(company=self.company, client=client,
                                     lead=lead, reference='DEV-202610-1940')
        cible = self._contexte(self._calepinage(lead, devis=devis))['cible']
        self.assertEqual(cible['source'], 'devis')
        self.assertIsNone(cible['refus'])

    def test_lecture_pure_et_stable(self):
        lead = self._lead(facture_hiver=Decimal('1800'))
        calepinage = self._calepinage(lead)
        avant = (calepinage.roof_layout, calepinage.updated_at)
        premiere = self._contexte(calepinage)['cible']
        seconde = self._contexte(calepinage)['cible']
        self.assertEqual(premiere, seconde)
        calepinage.refresh_from_db()
        self.assertEqual((calepinage.roof_layout, calepinage.updated_at),
                         avant)
        self.assertFalse(Devis.objects.filter(lead=lead).exists())
