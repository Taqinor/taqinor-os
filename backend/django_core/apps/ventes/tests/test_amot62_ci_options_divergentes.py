# -*- coding: utf-8 -*-
"""AMOT62 (C-AMOT-052) — la synthèse C&I décrit UNE option.

Devis commercial « Les deux » à panneaux variantés : 50 panneaux 710 W
``sans`` (35,5 kWc) / 70 ``avec`` (49,7 kWc). La sonde VC lci8 imprimait la
production de l'étude 49,7 kWc (79 482 kWh) à côté de 35,5 kWc.

* l'étude C&I est calculée pour l'option SERVIE (CIQ302 : l'offre réseau
  seule) — ``taille.retenue_kwc == 35.5`` ;
* ``synthese._systeme`` omet production et taux (motif publié) si le kWc
  servi s'écarte de plus de 2 % du kWc de l'étude ;
* un devis ``regles_calcul = 1`` (envoyé avant le 08/10) garde son étude
  d'origine (décision fondateur : nouveaux rendus seulement).

PVGIS simulé comme CIQ119 (table vendorisée de Casablanca).

Test-du-test : remettre ``kwc, _kwc_sans = …`` sans usage de l'option servie
⇒ ``test_etude_pour_option_servie`` rougit.
"""
from decimal import Decimal

from apps.stock.models import FicheTechnique, Produit
from apps.ventes.domain.etude_ci import rafraichir_etude_ci_devis
from apps.ventes.models import Devis, LigneDevis
from apps.ventes.quote_engine.builder import build_quote_data
from apps.ventes.quote_engine.ci import synthese as synth
from apps.ventes.tests.test_ciq119_rafraichir_ci import ENTREES, _Base


class CiOptionsDivergentesTests(_Base):
    @classmethod
    def setUpTestData(cls):
        super().setUpTestData()
        cls.hybride = Produit.objects.create(
            company=cls.co, nom='Onduleur hybride Deye 50kW Triphasé',
            prix_vente=Decimal('60000'), prix_achat=Decimal('45000'),
            role_devis='onduleur_hybride')
        FicheTechnique.objects.create(
            company=cls.co, produit=cls.hybride, type_fiche='onduleur',
            ond_ac_kw=Decimal(50), ond_phases=3, ond_n_mppt=4,
            ond_mppt_v_min=Decimal('200'), ond_mppt_v_max=Decimal('1000'),
            ond_v_max_abs=Decimal('1100'), ond_i_max_mppt_a=Decimal('30'),
            ond_rendement_euro_pct=Decimal('97.6'))
        cls.batterie = Produit.objects.create(
            company=cls.co, nom='Batterie Dyness 10 kWh',
            prix_vente=Decimal('25000'), prix_achat=Decimal('18000'),
            role_devis='batterie')

    def _devis_divergent(self, ref='DEV-AMOT62-01'):
        devis = Devis.objects.create(
            company=self.co, reference=ref, client=self.client_obj,
            statut='brouillon', taux_tva=Decimal('20'),
            mode_installation='commercial',
            etude_params=dict(ENTREES, mode='commercial',
                              scenario='Les deux (Sans + Avec)'))
        for produit, designation, qte, pu, variante in (
                (self.panneau, 'Panneau 710W', '50', '1272.73', 'sans'),
                (self.panneau, 'Panneau 710W', '70', '1272.73', 'avec'),
                (self.ond50, 'Onduleur réseau Huawei 50kW Triphasé', '1',
                 '40000', 'sans'),
                (self.hybride, 'Onduleur hybride Deye 50kW Triphasé', '1',
                 '60000', 'avec'),
                (self.batterie, 'Batterie Dyness 10 kWh', '1', '25000',
                 'avec')):
            LigneDevis.objects.create(
                devis=devis, produit=produit, designation=designation,
                quantite=Decimal(qte), prix_unitaire=Decimal(pu),
                remise=Decimal('0'), variante=variante)
        return devis

    def test_etude_pour_option_servie(self):
        devis = self._devis_divergent()
        rafraichir_etude_ci_devis(devis, force=True)
        devis.refresh_from_db()
        etude = devis.etude_params['etude_ci']
        self.assertEqual(etude['taille']['retenue_kwc'], 35.5)
        # CLAUSE PERSISTANCE — rafraîchir deux fois → étude identique.
        rafraichir_etude_ci_devis(devis, force=True)
        devis.refresh_from_db()
        self.assertEqual(devis.etude_params['etude_ci']['empreinte'],
                         etude['empreinte'])
        self.assertEqual(devis.etude_params['etude_ci']['bilan'],
                         etude['bilan'])

    def test_synthese_decrit_la_meme_option(self):
        devis = self._devis_divergent('DEV-AMOT62-02')
        rafraichir_etude_ci_devis(devis, force=True)
        devis.refresh_from_db()
        data = build_quote_data(devis, {})
        s = synth.synthese_ci(data)
        self.assertEqual(s['option_servie'], 'sans_batterie')
        self.assertAlmostEqual(s['systeme']['kwc'], 35.5, places=1)
        production = s['systeme']['production_kwh_an']
        self.assertIsNotNone(production)
        # kWh/kWc cohérent avec le productible (Casablanca ≈ 1 500-1 900),
        # jamais les 2 239 kWh/kWc de la sonde lci8.
        self.assertLess(production / s['systeme']['kwc'], 2000)
        self.assertIn('energie', s)

    def test_etude_d_une_autre_option_omise(self):
        """Une étude restée sur 49,7 kWc à côté de 35,5 kWc servis :
        production et taux omis, motif publié."""
        data = {
            'mode_installation': 'commercial', 'option_servie': 'sans',
            'puissance_kwc_sans': 35.5, 'puissance_kwc_avec': 49.7,
            'etude': {'etude_ci': {
                'taille': {'retenue_kwc': 49.7},
                'bilan': {'production_kwh': 79482, 'taux_autoconso': 0.8,
                          'taux_couverture': 0.4},
            }},
        }
        s = synth.synthese_ci(data)
        self.assertIsNone(s['systeme']['production_kwh_an'])
        self.assertNotIn('energie', s)
        motifs = {o['bloc']: o['motif'] for o in s['omissions']}
        self.assertEqual(motifs['systeme.production_kwh_an'],
                         synth.MOTIF_ETUDE_AUTRE_OPTION)
        self.assertEqual(motifs['energie'], synth.MOTIF_ETUDE_AUTRE_OPTION)
        # Règles d'origine (devis envoyé avant le 08/10) : inchangé.
        s1 = synth.synthese_ci(dict(data, regles_calcul_origine=True))
        self.assertEqual(s1['systeme']['production_kwh_an'], 79482)

    def test_regles_origine_gardent_l_etude(self):
        devis = self._devis_divergent('DEV-AMOT62-03')
        Devis.objects.filter(pk=devis.pk).update(regles_calcul=1)
        devis.refresh_from_db()
        rafraichir_etude_ci_devis(devis, force=True)
        devis.refresh_from_db()
        self.assertEqual(
            devis.etude_params['etude_ci']['taille']['retenue_kwc'], 49.7)
