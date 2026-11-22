"""ACAL101 (C-ACAL-113) — la provenance « figure du calepinage » de la
production devient une MARQUE explicite (``etude_params['production_source']``)
et UNE fonction rend la production recalée du devis
(``domain.scenario.figure_production_du_devis``).

* création ET resynchro depuis un layout posent ``production_source =
  'calepinage'`` et une production ARRONDIE (8843,66 → 8844, plus 8843) ;
* la figure du calepinage (base 720 W) est recalée sur la puissance des
  LIGNES (8 × 715 W = 5,72 kWc) — quelle que soit sa décimale ;
* une étude sans marque (antérieure à ACAL101) n'est jamais recalée ;
* le sélecteur cross-app ``production_attendue_pour_devis`` (monitoring,
  écart de l'atelier) lit la figure recalée, sans rendre le devis ;
* R2-14 — ``selectors_calepinage.production_imprimee_du_devis`` (présentation
  compacte, document généré) lit la production IMPRIMÉE par le PDF (rendu du
  devis) ; résidentiel, commercial / industriel (``synthese_ci``) et agricole
  (rien).

Sources RÉELLES : ``build_devis_from_layout``, ``sync_devis_from_layout``,
``etude_schema.fusionner`` (validation des clés).

Run:
    powershell -File scripts/test-backend.ps1 -RestoreDb \
        -Modules "apps.ventes.tests.test_acal_figure_production_provenance"
"""
import json
from decimal import Decimal
from pathlib import Path
from types import SimpleNamespace
from unittest import mock

from django.contrib.auth import get_user_model
from django.test import SimpleTestCase, TestCase
from django.utils import timezone

from apps.crm.models import Client
from apps.stock.models import Produit
from apps.ventes.domain.etude_schema import valider
from apps.ventes.domain.scenario import figure_production_du_devis
from apps.ventes.models import Devis, LigneDevis
from apps.ventes.selectors import production_attendue_pour_devis
from apps.ventes.selectors_calepinage import production_imprimee_du_devis
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

    def test_etude_sans_marque_non_recalee(self):
        # Lot 2 critique #9 — aucun chemin n'écrit « saisie » : la production
        # est une clé DÉRIVÉE de propriétaire CALEPINAGE, refusée à l'écran
        # (et aux surcharges, ``overrides.CHAMPS_DERIVES``). Le seul cas
        # non recalé réel est un devis SANS marque (antérieur à ACAL101).
        from apps.ventes.domain.etude_schema import ECRAN, fusionner
        with self.assertRaises(ValueError):
            fusionner({}, proprietaire=ECRAN, production_annuelle=8844)
        devis = self._devis_manuel({'production_annuelle': 8844})
        self.assertEqual(figure_production_du_devis(devis), 8844)
        self.assertEqual(production_attendue_pour_devis(devis.pk),
                         Decimal('8844'))


ETUDE_CI = json.loads((Path(__file__).resolve().parents[1] / 'contract_samples'
                       / 'etude_ci_preview.json').read_text(encoding='utf-8'))['exemple']


class ProductionImprimeeTest(SimpleTestCase):
    """R2-14 (S1) — devis 71 : 3 343 kWh stockés par le calepinage, 3 628
    imprimés par le PDF ; « production imprimée au client » doit dire 3 628.
    Sans base : le rendu ``build_quote_data`` est une doublure."""

    def _imprimee(self, rendu, **etude):
        devis = SimpleNamespace(pk=71, etude_params=etude, roof_layout={})
        cible = 'apps.ventes.quote_engine.builder.build_quote_data'
        with mock.patch(cible, return_value=rendu) as appel:
            valeur = production_imprimee_du_devis(devis)
        appel.assert_called_once_with(devis, {'pdf_mode': 'full'})
        return devis, valeur

    def test_production_stockee_differente_la_phrase_porte_l_imprimee(self):
        devis, valeur = self._imprimee({'mode_installation': 'residentiel', 'prod_kwh': 3628},
                                       production_annuelle=3343, production_source='calepinage')
        with mock.patch('apps.ventes.domain.scenario.puissance_kwc_du_devis', return_value=2.13):
            self.assertEqual(figure_production_du_devis(devis), 3343)  # ce que lisait l'ancien sélecteur
        self.assertEqual(valeur, Decimal('3628'))

    def test_ci_lit_la_synthese_jamais_la_production_par_ville(self):
        """Le PDF C&I (couverture et une-page) imprime 95 425 (moteur C&I) ;
        ``prod_kwh`` (144 000 / 400 000, par ville) n'est imprimé nulle part."""
        from apps.ventes.quote_engine.commercial import sample_data as commercial
        from apps.ventes.quote_engine.industriel import sample_data as industriel
        for rendu in (commercial.build('hotel'), industriel.build()):
            rendu = dict(rendu, puissance_kwc=55, etude=dict(rendu.get('etude') or {}, etude_ci=ETUDE_CI))
            with self.subTest(mode=rendu['mode_installation']):
                self.assertNotEqual(rendu['prod_kwh'], 95425)
                self.assertEqual(self._imprimee(rendu)[1], Decimal('95425'))

    def test_rien_d_imprime_rend_none_jamais_zero(self):
        divergent = {'mode_installation': 'residentiel', 'prod_kwh': 6000, 'deux_options': True,
                     'panneaux_divergents': True, 'prod_kwh_sans': 5000, 'prod_kwh_avec': 6000}
        for rendu in ({'mode_installation': 'agricole', 'prod_kwh': 5000}, divergent,
                      {'mode_installation': 'residentiel', 'prod_kwh': 0},
                      {'mode_installation': 'commercial', 'prod_kwh': 144000}):
            with self.subTest(rendu=rendu):
                self.assertIsNone(self._imprimee(rendu)[1])
        with mock.patch('apps.ventes.quote_engine.builder.build_quote_data',
                        side_effect=RuntimeError('panne')):
            self.assertIsNone(production_imprimee_du_devis(SimpleNamespace(pk=1, etude_params={})))
