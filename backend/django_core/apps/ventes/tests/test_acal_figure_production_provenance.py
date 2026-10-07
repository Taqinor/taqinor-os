"""ACAL101 (C-ACAL-113) — la provenance « figure du calepinage » de la
production devient une MARQUE explicite (``etude_params['production_source']``)
et UNE fonction rend la production recalée du devis
(``domain.scenario.figure_production_du_devis``).

* création ET resynchro depuis un layout posent ``production_source =
  'calepinage'`` et une production ARRONDIE (8843,66 → 8844, plus 8843) ;
* la figure du calepinage (base 720 W) est recalée sur la puissance des
  LIGNES (8 × 715 W = 5,72 kWc) — quelle que soit sa décimale ;
* une étude SAISIE (``production_source = 'saisie'``) n'est jamais recalée ;
* le sélecteur cross-app ``production_attendue_pour_devis`` (monitoring) lit
  la figure recalée.

Sources RÉELLES : ``build_devis_from_layout``, ``sync_devis_from_layout``,
``etude_schema.fusionner`` (validation des clés).

Run:
    powershell -File scripts/test-backend.ps1 -RestoreDb \
        -Modules "apps.ventes.tests.test_acal_figure_production_provenance"
"""
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.utils import timezone

from apps.crm.models import Client
from apps.stock.models import Produit
from apps.ventes.domain.etude_schema import valider
from apps.ventes.domain.scenario import figure_production_du_devis
from apps.ventes.models import Devis, LigneDevis
from apps.ventes.selectors import production_attendue_pour_devis
from apps.ventes.services import build_devis_from_layout, sync_devis_from_layout
from authentication.models import Company

User = get_user_model()
MONTH = timezone.now().strftime('%Y%m')


def _layout(annuel=8843.66, panneaux=8, savings=7000):
    return {'scenario': 'reseau', 'panelWatt': 720,
            'result': {'panels': panneaux,
                       'kwc': round(panneaux * 0.72, 2),
                       'annualKwh': annuel, 'savings': savings}}


class ProductionProvenanceTest(TestCase):
    def setUp(self):
        self.company = Company.objects.create(nom='ACAL101 Co',
                                              slug='acal101-co')
        self.user = User.objects.create_user(
            username='acal101', password='x', company=self.company,
            role_legacy='responsable')
        self.client_obj = Client.objects.create(company=self.company,
                                                nom='Client ACAL101')
        self.panneau = Produit.objects.create(
            company=self.company, nom='Panneau Canadian Solar 715W',
            sku='A101-PAN', prix_vente=Decimal('1200'),
            prix_achat=Decimal('800'), quantite_stock=100)
        Produit.objects.create(
            company=self.company, nom='Onduleur réseau Growatt 10kW',
            sku='A101-OND', prix_vente=Decimal('14000'),
            prix_achat=Decimal('9000'), quantite_stock=100)

    def _devis_manuel(self, etude, layout=None, panneaux=8):
        self.n = getattr(self, 'n', 0) + 1
        devis = Devis.objects.create(
            company=self.company, reference=f'DEV-{MONTH}-10{self.n:02d}',
            client=self.client_obj, statut='brouillon',
            taux_tva=Decimal('20'), created_by=self.user,
            roof_layout=layout if layout is not None else _layout(),
            etude_params=etude)
        LigneDevis.objects.create(
            devis=devis, produit=self.panneau, designation=self.panneau.nom,
            quantite=Decimal(str(panneaux)), prix_unitaire=Decimal('1200'),
            remise=Decimal('0'))
        return devis

    def test_decimale_haute_marquee_calepinage(self):
        # Création (pipeline) : marque + arrondi.
        devis = build_devis_from_layout(
            layout=_layout(), user=self.user, company=self.company,
            client=self.client_obj)
        devis.refresh_from_db()
        etude = devis.etude_params or {}
        self.assertEqual(etude.get('production_source'), 'calepinage')
        self.assertEqual(etude.get('production_annuelle'), 8844)
        self.assertEqual(valider({'production_source':
                                  etude['production_source']}), [])
        # Resynchro (reconcilier) : même marque, même arrondi.
        resultat = sync_devis_from_layout(devis, _layout(annuel=9101.5),
                                          self.user)
        self.assertFalse(resultat['inchange'])
        devis.refresh_from_db()
        etude = devis.etude_params or {}
        self.assertEqual(etude.get('production_source'), 'calepinage')
        self.assertEqual(etude.get('production_annuelle'), 9102)
        # Un second sync sans changement : « inchangé ».
        self.assertTrue(sync_devis_from_layout(
            devis, _layout(annuel=9101.5), self.user)['inchange'])

    def test_figure_recalee_sur_les_lignes(self):
        attendu = int(round(8843.66 * 5.72 / 5.76))
        for annuel in (8843.49, 8843.5, 8843.66, 8843.1):
            with self.subTest(annuel=annuel):
                devis = self._devis_manuel(
                    {'production_annuelle': int(round(annuel)),
                     'production_source': 'calepinage'},
                    layout=_layout(annuel=annuel))
                figure = figure_production_du_devis(devis)
                self.assertEqual(figure,
                                 int(round(annuel * 5.72 / 5.76)))
                self.assertNotEqual(figure, int(round(annuel)))
        self.assertEqual(attendu, 8782)
        # Le sélecteur cross-app (monitoring) lit la figure recalée.
        self.assertEqual(production_attendue_pour_devis(devis.pk),
                         Decimal(str(int(round(8843.1 * 5.72 / 5.76)))))

    def test_etude_saisie_non_recalee(self):
        devis = self._devis_manuel({'production_annuelle': 8844,
                                    'production_source': 'saisie'})
        self.assertEqual(figure_production_du_devis(devis), 8844)
        self.assertEqual(production_attendue_pour_devis(devis.pk),
                         Decimal('8844'))
        # Sans marque (devis d'avant ACAL101) : jamais recalée non plus.
        Devis.objects.filter(pk=devis.pk).update(
            etude_params={'production_annuelle': 8844})
        devis.refresh_from_db()
        self.assertEqual(figure_production_du_devis(devis), 8844)
