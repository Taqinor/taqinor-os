# -*- coding: utf-8 -*-
"""AGR123 — le rafraîchisseur d'étude pompage : l'étude suit la pompe
FACTURÉE, à chaque écriture de ligne et à chaque copie.

Sonde C1-03 : un CV 6 saisi donnait une ligne « Pompe 7,5 CV » mais l'étude
gardait ``pompe_cv=6``, ``pompe_kw=4,41`` et un champ 1,16× la pompe réelle.

Réseau : PVGIS et TMY simulés (``profils_horaires_site`` /
``temperatures_du_site`` patchés) — aucun test ne touche le réseau.

Run :
    powershell -File scripts/test-backend.ps1 -RestoreDb \\
        -Modules "apps.ventes.tests.test_agr123_rafraichir_pompage"
"""
import json
from decimal import Decimal
from pathlib import Path
from types import SimpleNamespace
from unittest import mock

from django.contrib.auth import get_user_model
from django.test import SimpleTestCase, TestCase
from rest_framework.test import APIClient

from apps.parametres.models import CompanyProfile
from apps.stock.models import FicheTechnique, Produit
from apps.ventes.domain import etude_schema, pompage
from apps.ventes.domain.etudes import rafraichir_etudes_du_devis
from apps.ventes.models import Devis, LigneDevis
from apps.ventes.tests._quote_engine_common import make_client
from authentication.models import Company

User = get_user_model()

_JOUR = ([0] * 6 + [100, 300, 500, 700, 850, 950, 1000, 950, 850, 700, 500,
                    300, 100] + [0] * 5)
PROFILS = [[g * (0.7 + 0.05 * i) for g in _JOUR] for i in range(12)]
COURBE = {'debits_m3h': [0, 12, 24, 30, 36, 39],
          'hmt_m': [91, 85, 70, 60, 43, 34]}

ENTREES = {
    'mode_pompe': 'neuve', 'type_pompe': 'immergee', 'alim': 'tri',
    'besoin': {'mode': 'volume_declare', 'volume_m3_jour': 135},
    'hmt_entrees': {'saisie_m': 60},
    'localisation': {'ville': 'Taroudant', 'lat': 30.47, 'lon': -8.88},
}
#: L'étude PÉRIMÉE de la sonde C1-03 (pompe 6 CV saisie à l'écran).
PERIMEE = {'pompe_cv': 6, 'pompe_kw': 4.41, 'champ_kwc': 6.39}


class _Base(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.co = Company.objects.get_or_create(
            slug='agr123-co', defaults={'nom': 'AGR123 Co'})[0]
        profil, _ = CompanyProfile.objects.get_or_create(company=cls.co)
        CompanyProfile.objects.filter(pk=profil.pk).update(
            agricole_pump_hours=Decimal('7'))
        cls.pompe = cls._produit(
            'Pompe immergée OSP 30/8 7,5 CV 380V', role_pompage='pompe',
            type_pompe='immergee', alimentation='tri',
            pompe_kw=Decimal('5.5'), pompe_cv=Decimal('7.5'), tension_v=380,
            courbe_pompe=COURBE)
        cls.variateur = cls._produit(
            'VARIATEUR VEICHI SI23 5.5KW 380V',
            role_pompage='variateur_pompage', alimentation='tri',
            pompe_kw=Decimal('5.5'), tension_v=380)
        FicheTechnique.objects.create(
            company=cls.co, produit=cls.variateur,
            type_fiche='variateur_pompage', ond_mppt_v_min=Decimal('250'),
            ond_mppt_v_max=Decimal('750'), ond_v_max_abs=Decimal('800'),
            ond_i_max_mppt_a=Decimal('20'), ond_phases=3,
            var_v_sortie_v=Decimal('380'))
        cls.panneau = cls._produit('Panneau 710W')
        FicheTechnique.objects.create(
            company=cls.co, produit=cls.panneau, type_fiche='module',
            pmax_wc=Decimal('710'), vmp_v=Decimal('40'), voc_v=Decimal('48'),
            isc_a=Decimal('18'), imp_a=Decimal('17'))
        cls.client_obj = make_client(cls.co)

    @classmethod
    def _produit(cls, nom, **kw):
        kw.setdefault('prix_vente', Decimal('1000'))
        kw.setdefault('prix_achat', Decimal('600'))
        return Produit.objects.create(company=cls.co, nom=nom, **kw)

    def setUp(self):
        self.user = User.objects.create_user(
            username='agr123_user', password='x', role_legacy='responsable',
            company=self.co)
        for cible, valeur in (('profils_horaires_site', PROFILS),
                              ('temperatures_du_site', None)):
            patcher = mock.patch.object(pompage, cible, return_value=valeur)
            patcher.start()
            self.addCleanup(patcher.stop)

    def devis(self, *, mode='agricole', etude=None, panneaux=10,
              reference='DEV-AGR123-0010'):
        devis = Devis.objects.create(
            company=self.co, reference=reference, client=self.client_obj,
            statut='brouillon', taux_tva=Decimal('20.00'),
            remise_globale=Decimal('0'), created_by=self.user,
            mode_installation=mode,
            etude_params=dict(ENTREES, **PERIMEE) if etude is None else etude)
        for ordre, (produit, qte) in enumerate((
                (self.pompe, 1), (self.variateur, 1),
                (self.panneau, panneaux))):
            LigneDevis.objects.create(
                devis=devis, produit=produit, designation=produit.nom,
                quantite=Decimal(qte), prix_unitaire=Decimal('1000'),
                remise=Decimal('0'), ordre=ordre)
        return devis


class EtudeSuitLaPompeFactureeTests(_Base):

    def test_etude_deja_calculee_relue_jamais_recalculee(self):
        """AGQ24 (C-AGQ-023) — une étude passée au rafraîchisseur (devis
        automatique) est RELUE : aucun second appel au moteur."""
        devis = self.devis()
        sortie = pompage.etudier_pompage(self.co, dict(ENTREES), devis=devis)
        with mock.patch.object(pompage, 'etudier_pompage') as espion:
            derivees = pompage.rafraichir_etude_pompage_devis(
                devis, sortie=sortie)
        espion.assert_not_called()
        self.assertEqual(derivees['pompe_kw'], 5.5)

    def test_cv_de_plaque_servi_jamais_le_cv_derive(self):
        """AGQ29 (C-AGQ-027) — OSP 30/8 : plaque 10 CV / 7,5 kW ⇒ l'étude
        sert 10 CV, jamais 7,5 ÷ 0,7355 = 10,2."""
        Produit.objects.filter(pk=self.pompe.pk).update(
            pompe_kw=Decimal('7.5'), pompe_cv=Decimal('10'))
        devis = self.devis()
        pompage.rafraichir_etude_pompage_devis(devis)
        devis.refresh_from_db()
        self.assertEqual(devis.etude_params['pompe_kw'], 7.5)
        self.assertEqual(devis.etude_params['pompe_cv'], 10)

    def test_la_pompe_facturee_remplace_l_etude_perimee(self):
        """ROUGE AVANT : l'étude gardait 6 CV / 4,41 kW / 6,39 kWc."""
        devis = self.devis()
        pompage.rafraichir_etude_pompage_devis(devis)
        devis.refresh_from_db()
        etude = devis.etude_params
        self.assertEqual(etude['pompe_kw'], 5.5)
        self.assertEqual(etude['pompe_cv'], 7.5)
        self.assertEqual(etude['champ_kwc'], 7.1)
        self.assertEqual(etude['champ']['nb_panneaux'], 10)
        self.assertEqual(etude['champ']['ratio'], round(7.1 / 5.5, 2))
        self.assertEqual(etude['hmt_m'], 60)
        self.assertEqual(etude['debit_hmt_m3h'], 30.0)
        # Les ENTRÉES ne sont jamais réécrites.
        for cle, valeur in ENTREES.items():
            self.assertEqual(etude[cle], valeur)

    def test_c_est_la_cinquieme_etude_de_l_orchestrateur(self):
        devis = self.devis()
        resultat = rafraichir_etudes_du_devis(devis)
        self.assertIn('etude_pompage', resultat)
        devis.refresh_from_db()
        self.assertEqual(devis.etude_params['pompe_kw'], 5.5)

    def test_second_appel_sans_changement_zero_ecriture(self):
        devis = self.devis()
        pompage.rafraichir_etude_pompage_devis(devis)
        devis.refresh_from_db()
        avant = (dict(devis.etude_params), devis.updated_at)
        with mock.patch.object(etude_schema, 'ecrire') as ecrire, \
                mock.patch.object(pompage, 'etudier_pompage') as moteur:
            pompage.rafraichir_etude_pompage_devis(devis)
        ecrire.assert_not_called()
        moteur.assert_not_called()
        devis.refresh_from_db()
        self.assertEqual((devis.etude_params, devis.updated_at), avant)

    def test_ligne_pompe_supprimee_derivees_omises(self):
        devis = self.devis()
        pompage.rafraichir_etude_pompage_devis(devis)
        devis.lignes.filter(produit=self.pompe).delete()
        devis.refresh_from_db()
        pompage.rafraichir_etude_pompage_devis(devis)
        devis.refresh_from_db()
        etude = devis.etude_params
        for cle in ('pompe_kw', 'pompe_cv', 'debit_hmt_m3h', 'm3_jour',
                    'heures_pompage', 'champ_kwc', 'production'):
            with self.subTest(cle=cle):
                self.assertNotIn(cle, etude)

    def test_statut_et_lignes_intouches(self):
        devis = self.devis()
        lignes = list(devis.lignes.values_list('id', 'quantite',
                                               'prix_unitaire'))
        pompage.rafraichir_etude_pompage_devis(devis)
        devis.refresh_from_db()
        self.assertEqual(devis.statut, 'brouillon')
        self.assertEqual(list(devis.lignes.values_list(
            'id', 'quantite', 'prix_unitaire')), lignes)


class LigneDevisViewSetTests(_Base):

    def test_modifier_une_ligne_fait_suivre_l_etude(self):
        devis = self.devis()
        pompage.rafraichir_etude_pompage_devis(devis)
        api = APIClient()
        api.force_authenticate(user=self.user)
        ligne = devis.lignes.get(produit=self.panneau)
        rep = api.patch('/api/django/ventes/devis-lignes/%s/' % ligne.id,
                        {'quantite': '12'}, format='json')
        self.assertEqual(rep.status_code, 200, rep.content[:400])
        devis.refresh_from_db()
        self.assertEqual(devis.etude_params['champ_kwc'], 8.52)
        self.assertEqual(devis.etude_params['champ']['nb_panneaux'], 12)


class AutreMarcheInchangeTests(_Base):

    def test_devis_residentiel_strictement_inchange(self):
        etude = {'scenario': 'Sans batterie', 'pompe_kw': 4.41}
        devis = self.devis(mode='residentiel', etude=dict(etude),
                           reference='DEV-AGR123-0020')
        avant = devis.updated_at
        with mock.patch.object(pompage, 'etudier_pompage') as moteur:
            self.assertIsNone(pompage.rafraichir_etude_pompage_devis(devis))
        moteur.assert_not_called()
        devis.refresh_from_db()
        self.assertEqual(devis.etude_params, etude)
        self.assertEqual(devis.updated_at, avant)


class ArticlesMultiplesTests(_Base):
    """AGM7 — plusieurs pompes, variateurs ou modèles de panneaux : l'étude ne
    mélange plus (premier modèle × quantité totale), elle omet et le dit."""

    DERIVEES_CHAMP = ('champ_kwc', 'champ', 'm3_jour', 'production',
                      'heures_pompage')

    def _ligne(self, devis, produit, quantite, ordre):
        return LigneDevis.objects.create(
            devis=devis, produit=produit, designation=produit.nom,
            quantite=Decimal(quantite), prix_unitaire=Decimal('1000'),
            remise=Decimal('0'), ordre=ordre)

    def _rafraichi(self, devis):
        pompage.rafraichir_etude_pompage_devis(devis, force=True)
        devis.refresh_from_db()
        return devis.etude_params

    def _codes(self, etude):
        return [a['code'] for a in etude.get('alertes_pompage') or ()]

    def test_deux_modeles_de_panneaux_champ_omis_et_dit(self):
        devis = self.devis()
        self.assertEqual(self._rafraichi(devis)['champ_kwc'], 7.1)
        autre = self._produit('Panneau 600W')
        FicheTechnique.objects.create(
            company=self.co, produit=autre, type_fiche='module',
            pmax_wc=Decimal('600'), vmp_v=Decimal('40'), voc_v=Decimal('48'),
            isc_a=Decimal('18'), imp_a=Decimal('17'))
        self._ligne(devis, autre, 4, 10)
        etude = self._rafraichi(devis)
        self.assertIn('panneaux_modeles_multiples', self._codes(etude))
        for cle in self.DERIVEES_CHAMP:
            with self.subTest(cle=cle):
                self.assertNotIn(cle, etude)
        # La pompe, elle, reste décrite.
        self.assertEqual(etude['pompe_kw'], 5.5)

    def test_deux_lignes_du_meme_panneau_restent_additionnees(self):
        devis = self.devis(panneaux=6)
        self._ligne(devis, self.panneau, 4, 10)
        etude = self._rafraichi(devis)
        self.assertNotIn('panneaux_modeles_multiples', self._codes(etude))
        self.assertEqual(etude['champ']['nb_panneaux'], 10)
        self.assertEqual(etude['champ_kwc'], 7.1)

    def test_deux_lignes_pompe_pompe_et_production_omises(self):
        devis = self.devis()
        self.assertEqual(self._rafraichi(devis)['pompe_kw'], 5.5)
        self._ligne(devis, self.pompe, 1, 10)
        etude = self._rafraichi(devis)
        self.assertIn('pompes_multiples', self._codes(etude))
        for cle in ('pompe_kw', 'pompe_cv', 'debit_hmt_m3h') \
                + self.DERIVEES_CHAMP:
            with self.subTest(cle=cle):
                self.assertNotIn(cle, etude)

    def test_pompe_quantite_deux_pompe_et_production_omises(self):
        devis = self.devis()
        self._rafraichi(devis)
        devis.lignes.filter(produit=self.pompe).update(quantite=Decimal(2))
        etude = self._rafraichi(devis)
        self.assertIn('pompes_multiples', self._codes(etude))
        self.assertNotIn('pompe_kw', etude)
        self.assertNotIn('m3_jour', etude)

    def test_deux_variateurs_alerte_et_chaines_non_evaluees(self):
        devis = self.devis()
        self._ligne(devis, self.variateur, 1, 10)
        etude = self._rafraichi(devis)
        self.assertIn('variateurs_multiples', self._codes(etude))
        self.assertFalse(etude['champ']['chaines']['verifiable'])
        self.assertEqual(etude['champ']['chaines']['motif'],
                         'plusieurs variateurs facturés')


_CONTRAT_POSE = json.loads(
    (Path(__file__).resolve().parents[2] / 'calepinage' / 'contract_samples'
     / 'calepinage_productible_pose.json').read_text(encoding='utf-8'))


class PlanPosePompageTests(SimpleTestCase):
    """ACAL1199 — le plan des panneaux d'un devis agricole (doublures, contrat
    ACAL996). Mutant : relire le vivant d'un envoyé ⇒ ``assert_not_called``
    rouge."""

    def _devis(self, **champs):
        return SimpleNamespace(**dict(dict(
            pk=7, company=None, regles_calcul=15, statut='brouillon',
            mode_installation='agricole', etude_params={}), **champs))

    def _diag(self, devis, servi=None, kwc=71.0):
        from apps.ventes.domain.pompage_pose import diagnostic_plan_pose_pompage
        servi = _CONTRAT_POSE['exemple'] if servi is None else servi
        with mock.patch('apps.calepinage.selectors_devis.productible_pose_servi',
                        return_value=servi) as lu:
            return diagnostic_plan_pose_pompage(devis, kwc=kwc), lu

    def test_brouillon_niveau_15_frais_rend_ses_pans(self):
        (plan, motif), lu = self._diag(self._devis())
        self.assertEqual(motif, '')
        self.assertEqual(plan['source'], 'pose_calepinage')
        self.assertEqual([(p['pan'], p['azimut_deg']) for p in plan['pans']],
                         [('PAN-E', 90.0), ('PAN-O', 270.0)])
        self.assertEqual(set(plan['pans'][0]),
                         {'pan', 'kwc', 'inclinaison_deg', 'azimut_deg'})
        self.assertEqual(lu.call_args.kwargs['tolerance_kwc_ratio'], 0.02)

    def test_perime_none_et_motif_servi(self):
        (plan, motif), _lu = self._diag(self._devis(),
                                        servi=_CONTRAT_POSE['exemple_perime'])
        self.assertIsNone(plan)
        self.assertEqual(motif, _CONTRAT_POSE['exemple_perime']['motif'])

    def test_envoye_relit_le_plan_range(self):
        range_ = {'source': 'pose_calepinage', 'pans': [
            {'pan': 'A', 'kwc': 3.0, 'inclinaison_deg': 10.0, 'azimut_deg': 180.0}]}
        devis = self._devis(statut='envoye',
                            etude_params={'pvgis_fige': {'plan': range_}})
        (plan, _m), lu = self._diag(devis)
        self.assertEqual(plan, range_)
        lu.assert_not_called()
        (plan, _m), _lu = self._diag(self._devis(statut='envoye'))
        self.assertIsNone(plan)

    def test_autres_cas_none_et_motif(self):
        for devis, attendu in (
                (self._devis(regles_calcul=14), 'règles d’avant le 21/11'),
                (self._devis(mode_installation='residentiel'), 'marché non agricole')):
            (plan, motif), lu = self._diag(devis)
            self.assertEqual((plan, motif), (None, attendu))
            lu.assert_not_called()
        (plan, motif), _lu = self._diag(self._devis(), kwc=80.0)
        self.assertEqual((plan, motif),
                         (None, 'lignes du devis différentes du calepinage'))
        sans_azimut = dict(_CONTRAT_POSE['exemple'], pans=[
            {'pan': 'X', 'kwc': 71.0, 'inclinaison_deg': 15.0, 'azimut_deg': None}])
        self.assertIsNone(self._diag(self._devis(), servi=sans_azimut)[0][0])
        with mock.patch('apps.calepinage.selectors_devis.productible_pose_servi',
                        return_value=None):
            from apps.ventes.domain.pompage_pose import plan_pose_pompage
            self.assertIsNone(plan_pose_pompage(self._devis(), kwc=71.0))


class PlanDuCalculTests(SimpleTestCase):
    """ACAL1201 — le plan publié par le calcul d'eau (forme ACAL1198)."""

    PLAN = {'source': 'pose_calepinage', 'pans': [
        {'pan': 'E', 'kwc': 3.55, 'inclinaison_deg': 15.0, 'azimut_deg': 90.0}]}

    def _plan(self, *, mode='neuve', diag=None, pose=PROFILS, site=PROFILS):
        from apps.ventes.domain import pompage_pose as pp
        with mock.patch.object(pp, 'diagnostic_plan_pose_pompage',
                               return_value=diag or (self.PLAN, '')), \
                mock.patch.object(pp, 'profils_horaires_pose', return_value=pose):
            return pp.plan_du_calcul(SimpleNamespace(pk=1), facture=None,
                                     mode_pompe=mode, profils_site=site,
                                     coordonnees={'lat': 30.47, 'lon': -8.88})

    def test_pose_servie(self):
        plan, profils = self._plan()
        self.assertEqual(plan, {'source': 'pose_calepinage',
                                'pans': self.PLAN['pans'],
                                'plan_reference': None, 'motif': None})
        self.assertIs(profils, PROFILS)

    def test_site_et_repli_avec_motif(self):
        from apps.parametres.pvgis_profils import PVGIS_ANGLE_DEG, PVGIS_ASPECT_DEG
        plan, profils = self._plan(mode='existante')
        self.assertEqual((plan['source'], plan['motif'], profils),
                         ('site_reference', 'pompe existante : débit déclaré', None))
        self.assertEqual(plan['plan_reference'],
                         {'inclinaison_deg': PVGIS_ANGLE_DEG,
                          'aspect_deg': PVGIS_ASPECT_DEG})
        plan, _p = self._plan(diag=(None, 'règles d’avant le 21/11'))
        self.assertEqual(plan['motif'], 'règles d’avant le 21/11')
        plan, _p = self._plan(pose=None)
        self.assertEqual(plan['motif'],
                         'ensoleillement indisponible au plan des panneaux')
        plan, profils = self._plan(site=None)
        self.assertEqual((plan['source'], profils), ('repli', None))


class PoseReellePompageTests(_Base):
    """ACAL1201 — le m³/jour d'un brouillon agricole de NIVEAU 15 suit le
    plan servi par le calepinage ; l'envoyé garde le sien ; ≤ 14 à l'octet.
    Mutants : profils de la pose passés à ``_besoin`` ⇒ besoin différent ⇒
    rouge ; plan vivant relu sur un envoyé ⇒ ``assert_not_called`` rouge."""

    #: Profils de la pose : 30 % d'irradiance de plus que ceux du site.
    POSE = [[g * 1.3 for g in jour] for jour in PROFILS]

    def _servi(self, azimut=90.0):
        return dict(_CONTRAT_POSE['exemple'], kwc_simule=7.1, pans=[
            {'pan': 'E', 'kwc': 7.1, 'inclinaison_deg': 15.0,
             'azimut_deg': azimut, 'specific_yield_kwh_kwc': 1400.0}])

    def _rafraichir(self, devis, servi):
        with mock.patch('apps.calepinage.selectors_devis.productible_pose_servi',
                        return_value=servi) as lu, \
                mock.patch('apps.ventes.domain.pompage_pose.profils_horaires_pose',
                           return_value=self.POSE):
            pompage.rafraichir_etude_pompage_devis(devis)
        devis.refresh_from_db()
        return devis.etude_params, lu

    def _devis(self, niveau, reference):
        devis = self.devis(reference=reference)
        Devis.objects.filter(pk=devis.pk).update(regles_calcul=niveau)
        devis.refresh_from_db()
        return devis

    def test_niveau_15_m3_jour_de_la_pose_besoin_inchange(self):
        site, _lu = self._rafraichir(self._devis(14, 'DEV-AGR123-1514'),
                                     self._servi())
        pose, _lu = self._rafraichir(self._devis(15, 'DEV-AGR123-1515'),
                                     self._servi())
        self.assertGreater(pose['m3_jour'], site['m3_jour'])
        self.assertEqual(pose['besoin_mensuel'], site['besoin_mensuel'])
        plan = pose['production']['plan_irradiation']
        self.assertEqual((plan['source'], plan['plan_reference'], plan['motif']),
                         ('pose_calepinage', None, None))
        self.assertEqual(pose['production']['source_irradiation'], 'pvgis')
        self.assertEqual(pose['pvgis_fige']['plan']['pans'][0]['azimut_deg'], 90.0)
        # Niveau 14 : ni plan publié aux dérivées, ni plan figé.
        self.assertNotIn('plan_irradiation', site['production'])
        self.assertNotIn('plan', site['pvgis_fige'] or {})

    def test_envoye_garde_son_m3_jour_apres_re_simulation(self):
        devis = self._devis(15, 'DEV-AGR123-1516')
        avant, _lu = self._rafraichir(devis, self._servi())
        Devis.objects.filter(pk=devis.pk).update(statut='envoye')
        devis.refresh_from_db()
        with mock.patch('apps.calepinage.selectors_devis.productible_pose_servi',
                        return_value=self._servi(azimut=270.0)) as vivant, \
                mock.patch('apps.ventes.domain.pompage_pose.profils_horaires_pose',
                           return_value=self.POSE):
            pompage.rafraichir_etude_pompage_devis(devis, force=True)
        vivant.assert_not_called()
        devis.refresh_from_db()
        self.assertEqual(devis.etude_params['m3_jour'], avant['m3_jour'])
        self.assertEqual(devis.etude_params['pvgis_fige']['plan'],
                         avant['pvgis_fige']['plan'])

    def test_niveau_14_derivees_et_empreinte_identiques(self):
        devis = self._devis(14, 'DEV-AGR123-1517')
        etude, lu = self._rafraichir(devis, self._servi())
        lu.assert_not_called()
        facture = pompage.facture_du_devis(devis, pompage.lire_catalogue(self.co))
        self.assertEqual(pompage._empreinte(etude, facture, None),
                         pompage._empreinte(etude, facture, None, None))
        self.assertNotIn('plan_irradiation', etude['production'])
