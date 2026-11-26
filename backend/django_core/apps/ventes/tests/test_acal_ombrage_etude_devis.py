"""ACAL144 (C-ACAL-075/078) — l'étude bancable du devis lit l'ombrage du
calepinage par ``ombrage_servi``, ZONE PAR ZONE, et retombe sur son chemin
quand il est PÉRIMÉ (fin de la tautologie).

Calepinage RÉEL simulé par la vraie chaîne (client météo rejoué, fiches
matériel injectées comme dans les tests du module), sélecteur JAMAIS mocké ;
seuls les deux fetchers réseau de l'étude (PVGIS productible / TMY) sont
rejoués, comme dans PV69/PV70.

Run :
    python manage.py test apps.ventes.tests.test_acal_ombrage_etude_devis -v2
"""
import contextlib
import copy
import json
from pathlib import Path
from types import SimpleNamespace
from unittest import mock

from django.test import SimpleTestCase

from apps.calepinage.models import Calepinage, CalepinageVariante
from apps.calepinage.selectors import ombrage_servi
from apps.calepinage.services.liens import lier_devis
from apps.calepinage.services.simulation import simuler_calepinage
from apps.calepinage.tests.acal_livrables_helpers import patch_materiel
from apps.calepinage.tests.test_acal_multi_pans import (
    _ClientParOrientation, _layout, _zone,
)
from apps.calepinage.tests.test_api_liste import BaseApiCalepinage
from apps.calepinage.tests.test_calx5_simulation import MATERIEL
from apps.ventes.etude import (
    AVERTISSEMENT_OMBRAGE_PERIME, ORIGINE_OMBRAGE_CALEPINAGE,
    ORIGINE_OMBRAGE_ETUDE, run_bankable_study,
)
from apps.ventes.models import Devis


def _fake_productible(settings, lat, lon, *, peakpower_kwc=1.0, tilt=None,
                      azimuth=None):
    return {'source': 'pvgis', 'productible_kwh_kwc': 1700.0,
            'production_mensuelle_kwh_kwc': None, 'reason': None}


def _fake_tmy(lat, lon, **_kwargs):
    return {'source': 'pvgis', 'irradiance_annuelle_kwh_m2': 2000.0,
            'irradiance_mensuelle_kwh_m2': [120.0] * 12,
            'temperature_moyenne_c': 19.0, 'reason': None}


_PATCH_TMY = mock.patch('apps.ventes.weather_feed.fetch_irradiance_tmy',
                        side_effect=_fake_tmy)
_PATCH_PROD = mock.patch('apps.parametres.pvgis.fetch_productible',
                         side_effect=_fake_productible)

ZONES = [
    {'label': 'PAN-1', 'lat': 33.5731, 'lon': -7.5898, 'tilt': 15,
     'azimuth': 90, 'kwc': 8.8},
    {'label': 'PAN-2', 'lat': 33.5731, 'lon': -7.5898, 'tilt': 15,
     'azimuth': 270, 'kwc': 4.4},
]


@_PATCH_TMY
@_PATCH_PROD
class OmbrageEtudeDevisTest(BaseApiCalepinage):
    def setUp(self):
        super().setUp()
        self.devis = Devis.objects.create(
            company=self.company, client=self.client_a, lead=self.lead,
            reference='DEV-202610-1441')
        layout = _layout(_zone(1, 16, 90.0), _zone(2, 8, 270.0))
        # ACAL137 — l'accès solaire vit DANS LA GÉOMÉTRIE DE CHAQUE PAN
        # (forme du contrat roof_layout_v2 : valeurs par module + méthode
        # objet), jamais à la racine : l'étape « accès module » s'applique
        # et la perte d'ombrage de chaque pan est MESURÉE.
        for zone in layout['zones']:
            zone['geometry']['solarAccess'] = {
                'values': [0.9] * zone['geometry']['count'],
                'method': {'horizon': False, 'rangees': False,
                           'resolution': 'annuelle',
                           'description': 'Accès solaire annuel'},
                'assumptions': {'periode': 'annee'},
                'computedAt': '2026-10-01T10:00:00Z',
            }
        self.calepinage = Calepinage.objects.create(
            company=self.company, lead_id=self.lead.pk, titre='Ombrage 144',
            roof_layout=layout)
        lier_devis(self.calepinage, self.devis.pk)
        with patch_materiel():
            simuler_calepinage(self.calepinage,
                               client=_ClientParOrientation(),
                               materiel=MATERIEL, enregistrer=True)
        self.calepinage.refresh_from_db()
        self.devis.refresh_from_db()

    def _etude(self):
        with patch_materiel():
            return run_bankable_study(self.devis, zones=copy.deepcopy(ZONES))

    def test_calepinage_retouche_sans_simulation_repli_etude(self, *_m):
        layout = copy.deepcopy(self.calepinage.roof_layout)
        layout['zones'][0]['geometry']['count'] = 3
        layout['zones'][0]['obstacles'] = [{'id': 'o1', 'heightM': 2.0}]
        Calepinage.objects.filter(pk=self.calepinage.pk).update(
            roof_layout=layout)
        etude = self._etude()
        self.assertEqual(etude['origine_ombrage'], ORIGINE_OMBRAGE_ETUDE)
        self.assertIn(AVERTISSEMENT_OMBRAGE_PERIME, etude['warnings'])

    def test_ombrage_par_zone(self, *_m):
        with patch_materiel():
            servi = ombrage_servi(self.devis.pk, self.company)
        self.assertFalse(servi['perime'])
        etude = self._etude()
        self.assertEqual(etude['origine_ombrage'], ORIGINE_OMBRAGE_CALEPINAGE)
        par_zone = {z['label']: z['shading_annual_loss_pct']
                    for z in etude['zones']}
        for label in ('PAN-1', 'PAN-2'):
            self.assertAlmostEqual(par_zone[label],
                                   float(servi['par_pan'][label]), places=2)
        if servi['par_pan']['PAN-1'] != servi['par_pan']['PAN-2']:
            self.assertNotEqual(par_zone['PAN-1'], par_zone['PAN-2'])

    def test_aucune_condition_de_variante_retenue(self, *_m):
        # Aucune variante n'existe : l'ombrage du calepinage est LU quand même.
        self.assertFalse(CalepinageVariante.objects.filter(
            calepinage=self.calepinage).exists())
        etude = self._etude()
        self.assertEqual(etude['origine_ombrage'], ORIGINE_OMBRAGE_CALEPINAGE)
        # Relancer deux fois sans changement ⇒ identique.
        self.assertEqual(
            [z['shading_annual_loss_pct'] for z in etude['zones']],
            [z['shading_annual_loss_pct'] for z in self._etude()['zones']])

    # ── D-RES-2710-1 (fondateur, 27/10/2026) — le moteur horaire résidentiel
    # retire la perte d'ombrage SERVIE par le calepinage, niveau de règles 3.

    def _kwargs_horaire(self):
        from apps.ventes.horaire.conso import profil_depuis_factures
        conso, _source, _detail = profil_depuis_factures(
            facture_hiver_mad=1200)
        return {'kwc': 5.0, 'conso_kwh_mensuelles': conso,
                'ville': 'Casablanca', 'tranches': None,
                'charges_fixes_mad': None}

    def test_d_res_2710_1_moteur_horaire_retire_l_ombrage_servi(self, *_m):
        from apps.ventes.etude_horaire import calculer_etude_horaire
        from apps.ventes.horaire.ombrage import perte_ombrage_du_devis
        with patch_materiel():
            servi = ombrage_servi(self.devis.pk, self.company)
            perte = perte_ombrage_du_devis(self.devis)
        self.assertGreater(perte, 0.0)
        self.assertAlmostEqual(perte, float(servi['global']), places=6)
        kwargs = self._kwargs_horaire()
        brut = calculer_etude_horaire(**kwargs)['annuel']['production_kwh']
        ombre = calculer_etude_horaire(
            perte_ombrage_pct=perte, **kwargs)['annuel']['production_kwh']
        self.assertAlmostEqual(ombre / brut, 1.0 - perte / 100.0, places=3)

    def test_d_res_2710_1_devis_envoye_niveau_2_garde_sa_production(self, *_m):
        from apps.ventes.horaire.ombrage import (
            facteur_production_saison, perte_ombrage_du_devis)
        Devis.objects.filter(pk=self.devis.pk).update(regles_calcul=2)
        self.devis.refresh_from_db()
        with patch_materiel():
            self.assertIsNone(perte_ombrage_du_devis(self.devis))
            self.assertEqual(facteur_production_saison(self.devis), 1.0)

    def test_devis_envoye_lit_la_perte_rangee(self, *_m):
        """ACON20 — un devis ENVOYÉ lit la perte RANGÉE à son bloc horaire,
        même quand la simulation vivante du calepinage a changé ; sans
        ``ombrage`` rangé : ``None`` ; brouillon : la perte vivante."""
        from apps.ventes.horaire.ombrage import perte_ombrage_du_devis

        layout = copy.deepcopy(self.calepinage.roof_layout)
        layout['zones'][0]['geometry']['count'] = 3
        Calepinage.objects.filter(pk=self.calepinage.pk).update(
            roof_layout=layout)
        Devis.objects.filter(pk=self.devis.pk).update(
            statut=Devis.Statut.ENVOYE, etude_params={
                'etude_horaire': {'ombrage': {'perte_pct': 8.0}}})
        self.devis.refresh_from_db()
        with patch_materiel():
            self.assertEqual(perte_ombrage_du_devis(self.devis), 8.0)
        Devis.objects.filter(pk=self.devis.pk).update(
            etude_params={'etude_horaire': {}})
        self.devis.refresh_from_db()
        with patch_materiel():
            self.assertIsNone(perte_ombrage_du_devis(self.devis))

    def test_lecture_d_etude_n_ecrit_rien_sans_profil(self, *_m):
        """ACON87 — société SANS ``CompanyProfile`` : l'étude horaire du
        devis et les lecteurs ventes n'écrivent AUCUN profil ; la perte
        d'ombrage servie ne bouge pas."""
        from django.db import connection
        from django.test.utils import CaptureQueriesContext

        from apps.parametres.models import CompanyProfile
        from apps.ventes.etude_horaire import etude_horaire_pour_devis
        from apps.ventes.horaire.ombrage import perte_ombrage_du_devis
        from apps.ventes.utils.company_settings import (
            doc_prefix, payment_terms_for, tva_standard,
        )

        CompanyProfile.objects.filter(company=self.company).delete()
        with patch_materiel():
            avant = perte_ombrage_du_devis(self.devis)
            with CaptureQueriesContext(connection) as requetes:
                etude_horaire_pour_devis(self.devis)
                tva_standard(self.company)
                doc_prefix(self.company, 'devis')
                payment_terms_for(self.company, 'residentiel')
            apres = perte_ombrage_du_devis(self.devis)
        ecritures = [q['sql'] for q in requetes.captured_queries
                     if 'parametres_companyprofile' in q['sql']
                     and q['sql'].lstrip().upper().startswith(
                         ('INSERT', 'UPDATE'))]
        self.assertEqual(ecritures, [])
        self.assertFalse(CompanyProfile.objects.filter(
            company=self.company).exists())
        self.assertEqual(avant, apres)

    def test_d_res_2710_1_simulation_perimee_aucun_ombrage(self, *_m):
        from apps.ventes.horaire.ombrage import perte_ombrage_du_devis
        layout = copy.deepcopy(self.calepinage.roof_layout)
        layout['zones'][0]['geometry']['count'] = 3
        Calepinage.objects.filter(pk=self.calepinage.pk).update(
            roof_layout=layout)
        with patch_materiel():
            self.assertIsNone(perte_ombrage_du_devis(self.devis))

    def test_c_rhor_004_courbe_saison_au_derate_du_devis(self, *_m):
        from apps.ventes.horaire.ombrage import (
            facteur_production_saison, perte_ombrage_du_devis)
        from apps.ventes.quote_engine.pricing import PRODUCTION_DERATE
        with patch_materiel():
            perte = perte_ombrage_du_devis(self.devis)
            facteur = facteur_production_saison(self.devis)
        self.assertAlmostEqual(
            facteur, PRODUCTION_DERATE * (1.0 - perte / 100.0), places=9)

    def test_err_rhor8_balayage_du_stockage_ombre_au_niveau_5(self, *_m):
        """ERR-RHOR8-TAILLES-PRODUCTION-SANS-OMBRAGE (devis 2007 : carte Max
        9 084 kWh non ombrée vs 8 473 officiels) — ``balayer_stockage_horaire``
        accepte ``perte_ombrage_pct`` ; au niveau de règles 5 les arguments du
        balayage (``kwargs_moteur_ombre``) portent la perte et le balayage
        produit ce que produit l'étude ombrée à kWc égal ; au niveau 4 (devis
        envoyé) : arguments d'hier, sans ombrage. Test-du-test : retirer le
        paramètre du balayage ⇒ ``kwargs_ombrage`` rend ``{}``, rouge."""
        from apps.ventes.domain.entrees import (
            EntreesMoteur, _ombrage_balayage, kwargs_moteur_ombre)
        from apps.ventes.etude_horaire import (
            balayer_stockage_horaire, calculer_etude_horaire)
        from apps.ventes.horaire.ombrage import perte_ombrage_du_devis
        kwargs = self._kwargs_horaire()
        for niveau, ombre_attendu in ((5, True), (4, False)):
            with self.subTest(niveau=niveau):
                Devis.objects.filter(pk=self.devis.pk).update(regles_calcul=niveau)
                self.devis.refresh_from_db()
                with patch_materiel():
                    perte = perte_ombrage_du_devis(self.devis)
                self.assertGreater(perte, 0.0)  # RHOR1 (niveau ≥ 3) inchangé
                self.assertIs(_ombrage_balayage(self.devis), ombre_attendu)
                entrees = EntreesMoteur(
                    conso_kwh_mensuelles=kwargs['conso_kwh_mensuelles'],
                    ville='Casablanca', perte_ombrage_pct=perte,
                    ombrage_balayage=_ombrage_balayage(self.devis))
                arguments = kwargs_moteur_ombre(entrees)
                if not ombre_attendu:
                    self.assertNotIn('perte_ombrage_pct', arguments)
                    continue
                self.assertEqual(arguments['perte_ombrage_pct'], perte)
                ombre = {'perte_ombrage_pct': perte}
                brut = balayer_stockage_horaire(capacites_kwh=[5.0], **kwargs)
                balaye = balayer_stockage_horaire(
                    capacites_kwh=[5.0], **ombre, **kwargs)
                etude = calculer_etude_horaire(**ombre, **kwargs)
                self.assertAlmostEqual(
                    balaye['production_annuelle_kwh'] / brut['production_annuelle_kwh'],
                    1.0 - perte / 100.0, places=3)
                self.assertAlmostEqual(balaye['production_annuelle_kwh'],
                                       etude['annuel']['production_kwh'], delta=1.0)

    # ── ACAL999 — la base de production de la pose réelle ─────────────────
    def _niveau(self, niveau, **champs):
        Devis.objects.filter(pk=self.devis.pk).update(
            regles_calcul=niveau, mode_installation='residentiel', **champs)
        self.devis.refresh_from_db()

    def test_acal999_niveau_15_meme_base_aux_entrees_et_a_la_page(self, *_m):
        from apps.calepinage.selectors_devis import productible_pose_servi
        from apps.ventes.domain.entrees import (
            entrees_depuis_devis, kwargs_moteur_ombre)
        from apps.ventes.horaire.productible_pose import (
            base_de_production, base_depuis_servi)
        from apps.ventes.horaire.public import production_annuelle_pour_kwc
        self._niveau(15)
        with patch_materiel():
            servi = productible_pose_servi(self.devis.pk, self.company,
                                           tolerance_kwc_ratio=0.02)
            base = base_de_production(self.devis)
            entrees = entrees_depuis_devis(self.devis)
        self.assertEqual(base, base_depuis_servi(servi)[0])
        self.assertEqual(entrees.base_production, base)
        if base is not None:  # simulation complète : servie partout
            kwargs = kwargs_moteur_ombre(entrees)
            self.assertEqual(kwargs['base_production'], base)
            self.assertNotIn('perte_ombrage_pct', kwargs)
            self.assertNotIn('productible_kwh_kwc', kwargs)
            self.assertEqual(
                production_annuelle_pour_kwc(servi['kwc_simule'],
                                             ville='Casablanca',
                                             base_production=base),
                round(servi['kwc_simule'] * sum(base['kwh_kwc_mensuel'])))
        else:  # incomplet : jamais servi, la ville sert
            self.assertTrue(servi is None or servi['perime'])

    def test_acal999_envoye_puis_resimule_relit_la_base_rangee(self, *_m):
        from apps.ventes.horaire.productible_pose import base_de_production
        rangee = {'kwh_kwc_annuel': 1388.4, 'kwh_kwc_mensuel': [115.7] * 12,
                  'pertes_incluses': True, 'source': 'calepinage_enregistre'}
        self._niveau(15, statut=Devis.Statut.ENVOYE, etude_params={
            'etude_horaire': {'base_production': rangee}})
        layout = copy.deepcopy(self.calepinage.roof_layout)
        layout['zones'][0]['geometry']['count'] = 3
        self.calepinage.roof_layout = layout
        self.calepinage.save(update_fields=['roof_layout'])
        with patch_materiel():
            simuler_calepinage(self.calepinage, client=_ClientParOrientation(),
                               materiel=MATERIEL, enregistrer=True)
            with mock.patch('apps.calepinage.selectors_devis.'
                            'productible_pose_servi') as vivant:
                self.assertEqual(base_de_production(self.devis), rangee)
        vivant.assert_not_called()

    def test_acal999_niveau_14_rien_ne_change(self, *_m):
        from apps.ventes.domain.entrees import (
            empreinte_entrees, entrees_depuis_devis, kwargs_moteur_ombre)
        from apps.ventes.horaire.productible_pose import (
            diagnostic_base_de_production)
        self._niveau(14)
        with patch_materiel():
            entrees = entrees_depuis_devis(self.devis)
            self.assertEqual(diagnostic_base_de_production(self.devis),
                             (None, 'règles d’avant le 21/11'))
        self.assertIsNone(entrees.base_production)
        self.assertNotIn('base_production', kwargs_moteur_ombre(entrees))
        self.assertEqual(empreinte_entrees(entrees), empreinte_entrees(
            SimpleNamespace(**{c: entrees[c] for c in entrees.keys()
                               if c != 'base_production'})))

    def test_acal1237_sans_conso_meme_kwh_an_brouillon_et_envoye(self, *_m):
        """ACAL1237 — niveau 15 sans consommation (aucun bloc horaire) : la base
        imprimée par le brouillon est rangée à l'envoi et relue après."""
        from apps.ventes.domain.envoi import geler_document_engage
        from apps.ventes.horaire.productible_pose import (
            CLE_BASE_ENVOI, base_de_production)
        self._niveau(15, etude_params={})
        with patch_materiel():
            avant = base_de_production(self.devis)
            geler_document_engage(self.devis, self.user, statut=Devis.Statut.ENVOYE)
        self.devis.refresh_from_db()
        self.assertEqual(self.devis.statut, Devis.Statut.ENVOYE)
        self.assertEqual(self.devis.etude_params.get(CLE_BASE_ENVOI), avant)
        with mock.patch('apps.calepinage.selectors_devis.'
                        'productible_pose_servi') as vivant:
            self.assertEqual(base_de_production(self.devis), avant)
            self.assertEqual(base_de_production(self.devis), avant)
        vivant.assert_not_called()


_SERVI_POSE = {
    'perime': False, 'motif': '', 'kwc_simule': 71.0,
    'kwh_kwc_annuel': 1388.4, 'pertes_et_ombrage_inclus': True,
    'kwh_kwc_mensuel': [75.2, 85.6, 115.3, 130.4, 148.9, 155.1, 160.2, 149.6,
                        122.8, 101.5, 77.4, 66.4]}


class BaseDeProductionSansBaseTest(SimpleTestCase):
    """ACAL999 — le résolveur et ses lecteurs, sans base (doublures)."""

    def _devis(self, **champs):
        return SimpleNamespace(**dict(dict(
            pk=1, company=None, regles_calcul=15, statut='brouillon',
            mode_installation='residentiel', etude_params={}), **champs))

    def _diag(self, devis, servi=_SERVI_POSE, kwc=71.0):
        from apps.ventes.horaire.productible_pose import (
            diagnostic_base_de_production)
        with mock.patch('apps.calepinage.selectors_devis.'
                        'productible_pose_servi', return_value=servi) as lu:
            return diagnostic_base_de_production(devis, kwc=kwc), lu

    def test_contrat_d_acal996_donne_la_base(self):
        from apps.ventes.horaire.productible_pose import base_depuis_servi
        exemple = json.loads((Path(__file__).resolve().parents[2]
                              / 'calepinage' / 'contract_samples'
                              / 'calepinage_productible_pose.json')
                             .read_text(encoding='utf-8'))
        base, motif = base_depuis_servi(exemple['exemple'], kwc=71.0)
        self.assertEqual(base, {
            'kwh_kwc_annuel': 1388.4,
            'kwh_kwc_mensuel': exemple['exemple']['kwh_kwc_mensuel'],
            'pertes_incluses': True, 'source': 'calepinage_enregistre'})
        self.assertEqual(motif, '')
        incomplet = base_depuis_servi(exemple['exemple_incomplet'])
        self.assertEqual(incomplet, (None, exemple['exemple_incomplet']['motif']))
        self.assertIsNone(base_depuis_servi(exemple['exemple_perime'])[0])

    def test_brouillon_niveau_15_lit_le_servi(self):
        (base, motif), lu = self._diag(self._devis())
        self.assertEqual(base['kwh_kwc_annuel'], 1388.4)
        self.assertEqual(lu.call_args.kwargs['tolerance_kwc_ratio'], 0.02)

    def test_kwc_hors_tolerance_ville_et_motif(self):
        (base, motif), _lu = self._diag(self._devis(), kwc=80.0)
        self.assertIsNone(base)
        self.assertEqual(motif, 'lignes du devis différentes du calepinage')

    def test_incomplet_ville(self):
        servi = dict(_SERVI_POSE, perime=True, pertes_et_ombrage_inclus=False,
                     motif='résultat incomplet : 3 pertes non renseignées')
        (base, motif), _lu = self._diag(self._devis(), servi=servi)
        self.assertIsNone(base)
        self.assertIn('incomplet', motif)

    def test_niveau_14_et_non_residentiel_ville(self):
        (base, motif), lu = self._diag(self._devis(regles_calcul=14))
        self.assertEqual((base, motif), (None, 'règles d’avant le 21/11'))
        lu.assert_not_called()
        (base, _m), _lu = self._diag(self._devis(mode_installation='industriel'))
        self.assertIsNone(base)

    def test_envoye_relit_la_base_rangee_jamais_le_vivant(self):
        rangee = {'kwh_kwc_annuel': 1300.0, 'kwh_kwc_mensuel': [108.3] * 12,
                  'pertes_incluses': True, 'source': 'calepinage_enregistre'}
        devis = self._devis(statut='envoye',
                            etude_params={'etude_horaire': {'base_production': rangee}})
        (base, _m), lu = self._diag(devis)
        self.assertEqual(base, rangee)
        lu.assert_not_called()
        (base, _m), _lu = self._diag(self._devis(statut='envoye'))
        self.assertIsNone(base)

    # ── ACAL1237 — la base rangée À L'ENVOI d'un devis sans consommation ──
    def _a_ranger(self, devis):
        from apps.ventes.horaire.productible_pose import base_a_ranger_a_l_envoi
        with mock.patch('apps.calepinage.selectors_devis.productible_pose_servi',
                        return_value=_SERVI_POSE), \
                mock.patch('apps.ventes.horaire.productible_pose._kwc_du_devis',
                           return_value=71.0):
            return base_a_ranger_a_l_envoi(devis)

    def test_acal1237_sans_conso_envoye_relit_la_base_rangee_a_l_envoi(self):
        from apps.ventes.horaire.productible_pose import CLE_BASE_ENVOI
        brouillon = self._devis()
        (imprimee, _m), _lu = self._diag(brouillon)
        rangee = self._a_ranger(brouillon)
        self.assertEqual(rangee, imprimee)
        envoye = self._devis(statut='envoye', etude_params={CLE_BASE_ENVOI: rangee})
        (base, _m), lu = self._diag(envoye)
        self.assertEqual(base, imprimee)  # même kWh/an avant et après l'envoi
        lu.assert_not_called()
        # Le bloc horaire, quand il porte la base, reste lu en premier (et rien à ranger).
        bloc = {'kwh_kwc_annuel': 1300.0, 'kwh_kwc_mensuel': [108.3] * 12,
                'pertes_incluses': True, 'source': 'calepinage_enregistre'}
        horaire = {'etude_horaire': {'base_production': bloc}}
        self.assertIsNone(self._a_ranger(self._devis(etude_params=horaire)))
        (base, _m), _lu = self._diag(self._devis(
            statut='envoye', etude_params=dict(horaire, **{CLE_BASE_ENVOI: rangee})))
        self.assertEqual(base, bloc)

    def test_acal1237_niveau_14_rien_a_ranger(self):
        self.assertIsNone(self._a_ranger(self._devis(regles_calcul=14)))
        self.assertIsNone(self._a_ranger(self._devis(mode_installation='industriel')))

    def _geler(self, devis, base):
        from apps.ventes.domain import envoi
        vu = []
        noms = ('refresh_marge_snapshot', 'figer_clauses_devis', 'figer_baremes_forfaits',
                'figer_reglages_rendu', 'poser_validite_devis', 'date_validite_credit')
        with contextlib.ExitStack() as pile:
            for nom in noms:
                pile.enter_context(mock.patch.object(envoi, nom))
            for cible in ('apps.ventes.domain.tarification.exiger_approbation_remise',
                          'apps.ventes.conceptions_options.figer_conceptions_des_options',
                          'apps.ventes.utils.echeancier.figer_echeancier',
                          'apps.ventes.domain.verrou_devis.toucher'):
                pile.enter_context(mock.patch(cible))
            pile.enter_context(mock.patch(
                'apps.ventes.horaire.productible_pose.base_a_ranger_a_l_envoi',
                side_effect=lambda d: vu.append(d.statut) or base))
            envoi.geler_document_engage(devis, None, statut='envoye')
        return vu

    def test_acal1237_geler_range_la_base_lue_avant_la_bascule(self):
        from apps.ventes.horaire.productible_pose import CLE_BASE_ENVOI
        base = {'kwh_kwc_annuel': 1388.4, 'kwh_kwc_mensuel': [115.7] * 12,
                'pertes_incluses': True, 'source': 'calepinage_enregistre'}
        devis = self._devis(save=mock.Mock())
        self.assertEqual(self._geler(devis, base), ['brouillon'])  # lue brouillon
        self.assertEqual(devis.statut, 'envoye')
        self.assertEqual(devis.etude_params[CLE_BASE_ENVOI], base)
        # Une clé héritée (copie, V2) sans base à ranger : retirée, jamais relue.
        devis = self._devis(save=mock.Mock(), etude_params={CLE_BASE_ENVOI: base})
        self._geler(devis, None)
        self.assertNotIn(CLE_BASE_ENVOI, devis.etude_params)
        # Niveau 14 / bloc horaire porteur : etude_params intouché.
        devis = self._devis(save=mock.Mock())
        self._geler(devis, None)
        self.assertEqual(devis.etude_params, {})

    def test_page_publique_lit_la_base_sans_derate(self):
        from apps.ventes.horaire.public import (
            production_annuelle_pour_kwc, production_journaliere_par_saison)
        base = {'kwh_kwc_annuel': 1388.4, 'pertes_incluses': True,
                'kwh_kwc_mensuel': _SERVI_POSE['kwh_kwc_mensuel'],
                'source': 'calepinage_enregistre'}
        with mock.patch('apps.ventes.horaire.public.productible_mensuel',
                        return_value=None):
            self.assertEqual(
                production_annuelle_pour_kwc(71.0, ville='X', perte_ombrage_pct=10.0,
                                             base_production=base),
                round(71.0 * sum(base['kwh_kwc_mensuel'])))
            self.assertIsNone(production_annuelle_pour_kwc(71.0, ville='X'))
        with mock.patch('apps.ventes.horaire.public.productible_mensuel',
                        return_value=None), \
                mock.patch('apps.ventes.horaire.public.production_par_saison',
                           return_value={'ete': {}}) as saison:
            production_journaliere_par_saison(71.0, ville='X', facteur=0.9,
                                              base_production=base)
        args, kwargs = saison.call_args
        self.assertEqual(args[1][0], base['kwh_kwc_mensuel'])
        self.assertEqual(kwargs['facteur'], 1.0)

    def test_kwargs_et_empreinte(self):
        from apps.ventes.domain.entrees import empreinte_entrees, kwargs_moteur_ombre
        base = {'kwh_kwc_annuel': 1388.4, 'pertes_incluses': True,
                'kwh_kwc_mensuel': [115.7] * 12, 'source': 'calepinage_enregistre'}
        entrees = {'conso_kwh_mensuelles': [300.0] * 12, 'ville': 'X',
                   'productible_kwh_kwc': 1600.0}
        self.assertNotIn('base_production', kwargs_moteur_ombre(entrees))
        avec = kwargs_moteur_ombre(dict(entrees, base_production=base))
        self.assertEqual(avec['base_production'], base)
        self.assertNotIn('productible_kwh_kwc', avec)
        sans = SimpleNamespace(conso_kwh_mensuelles=[300.0] * 12, ville='X')
        self.assertEqual(empreinte_entrees(sans), empreinte_entrees(
            SimpleNamespace(base_production=None, **vars(sans))))
        self.assertNotEqual(empreinte_entrees(sans), empreinte_entrees(
            SimpleNamespace(base_production=base, **vars(sans))))
