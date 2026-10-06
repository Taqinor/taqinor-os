"""CIQ210 — brancher ``economie_ci`` : aperçu, lecture serveur, et le moteur
de devis sert CE bloc pour tout devis commercial ou industriel (fin du 60 %,
du 1,75 et du masque MT posé sur une clé de calepinage).

Lecteurs C&I de ``eco_s_ann`` / ``roi_s`` (grep joint au commit, D3 les
bascule) : ``quote_engine/commercial/renderer.py`` et
``quote_engine/industriel/renderer.py`` les OMETTENT déjà (CIQ301 :
``com_economies``/``ind_economies`` = None) ; ``quote_engine/builder.py`` les
calcule encore par ``calculate_savings_roi`` pour la charge utile commune —
aucun gabarit C&I ne les imprime.

Les cas « devis » (TestCase) créent le devis comme l'écran (``etude_params``
d'entrée, lignes) puis passent par le VRAI rafraîchisseur C&I (CIQ119, PVGIS
simulé) : aucune fixture n'injecte ``economies_annuelles``.

Run :
    powershell -File scripts/test-backend.ps1 -RestoreDb \\
        -Modules "apps.ventes.tests.test_ciq210_branchement"
"""
import copy
import json
import os
from decimal import Decimal
from unittest import mock

from django.contrib.auth import get_user_model
from django.test import SimpleTestCase, TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from apps.ventes import economie_ci as eco
from apps.ventes import tarif_ci

_ICI = os.path.dirname(__file__)


def _contrat(nom):
    with open(os.path.join(_ICI, os.pardir, 'contract_samples', nom),
              encoding='utf-8') as fh:
        return json.load(fh)


def _apercu(tension='bt'):
    apercu = copy.deepcopy(_contrat('etude_ci_preview.json')['exemple'])
    apercu['entrees_resolues']['tension'] = {'valeur': tension,
                                             'provenance': None}
    return apercu


TARIF_MT_FACTURE = {
    'contrat': 'mt_general', 'base_tarifs': 'ht', 'provenance': 'facture',
    'date_facture': '2026-08-31',
    'mt': {'tarif_pointe': 1.6, 'tarif_pleines': 1.1, 'tarif_creuses': 0.8}}

INVESTISSEMENT = {'ht': 900000.0, 'ttc': 1080000.0}


def _cles(o):
    if isinstance(o, dict):
        for k, v in o.items():
            yield k
            yield from _cles(v)
    elif isinstance(o, list):
        for v in o:
            yield from _cles(v)


def _nombres(o):
    if isinstance(o, dict):
        for v in o.values():
            yield from _nombres(v)
    elif isinstance(o, list):
        for v in o:
            yield from _nombres(v)
    elif isinstance(o, (int, float)) and not isinstance(o, bool):
        yield o


class AssemblageTest(SimpleTestCase):
    def test_contrat_ni_declare_ni_deductible_omis_motif_nomme(self):
        bloc = eco.assembler_economie_ci(
            _apercu('bt'), investissement=INVESTISSEMENT,
            mode_installation='commercial')
        self.assertEqual(bloc['statut'], 'omis')
        self.assertEqual(bloc['motifs_omission'], [eco.MOTIF_TARIF_OMIS])
        self.assertEqual(bloc['tarif']['origine'], tarif_ci.ORIGINE_OMIS)
        self.assertIsNone(bloc['flux_ht'])
        self.assertEqual(set(bloc),
                         set(_contrat('economie_ci.json')['exemple_omis']))

    def test_mt_sans_prix_de_facture_repli_grille_etiquete(self):
        bloc = eco.assembler_economie_ci(
            _apercu('mt'), investissement=INVESTISSEMENT,
            mode_installation='industriel')
        self.assertEqual(bloc['statut'], 'calcule')
        self.assertEqual(bloc['tarif']['origine'], tarif_ci.ORIGINE_GRILLE)
        self.assertEqual(bloc['tarif']['contrat'], 'mt_general')
        hyp = {h['cle']: h for h in bloc['hypotheses']}
        self.assertIn('grille ONEE', hyp['tarif']['valeur'])
        self.assertIn('repli', hyp['tarif']['valeur'])
        self.assertEqual(hyp['tarif']['statut'], 'estimation')
        codes = [a['code'] for a in bloc['alertes_internes']]
        self.assertIn('tarif_repli', codes)
        self.assertGreater(bloc['economie_annee1']['total_mad'], 0)

    def test_mt_facture_declaree_prix_de_la_facture(self):
        bloc = eco.assembler_economie_ci(
            _apercu('mt'), tarif_declare=TARIF_MT_FACTURE,
            investissement=INVESTISSEMENT, mode_installation='industriel')
        self.assertEqual(bloc['statut'], 'calcule')
        self.assertEqual(bloc['tarif']['origine'], tarif_ci.ORIGINE_FACTURE)
        prix = {p['poste']: p['tarif_kwh_ht']
                for p in bloc['tarif']['tarifs_par_poste']}
        self.assertEqual(prix, {'pointe': 1.6, 'pleines': 1.1, 'creuses': 0.8})
        self.assertNotIn('tarif_repli',
                         [a['code'] for a in bloc['alertes_internes']])

    def test_aucune_trace_de_1_75_ni_de_savings_estimated(self):
        for tension, td in (('bt', {'contrat': 'bt_patente'}),
                            ('mt', None)):
            bloc = eco.assembler_economie_ci(
                _apercu(tension), tarif_declare=td,
                investissement=INVESTISSEMENT, mode_installation='commercial')
            self.assertEqual(bloc['statut'], 'calcule')
            cles = set(_cles(bloc))
            self.assertNotIn('savings_estimated', cles)
            self.assertNotIn('savings_model', cles)
            tarifs = [p['tarif_kwh_ht'] for p in
                      bloc['tarif']['tarifs_par_poste']] + [
                p['tarif_kwh'] for p in bloc['economie_annee1']['par_poste']]
            self.assertNotIn(1.75, tarifs)

    def test_forme_du_contrat_et_publique(self):
        bloc = eco.assembler_economie_ci(
            _apercu('bt'), tarif_declare={'contrat': 'bt_patente'},
            investissement=INVESTISSEMENT, mode_installation='commercial',
            saisies={'offre_cse_concurrente': {
                'tarif_kwh_ht': 0.85, 'duree_ans': 10,
                'source': 'offre écrite du prospect'}})
        exemple = _contrat('economie_ci.json')['exemple']
        # base « oui » (TVA récupérable de l'aperçu) : pas de flux TTC.
        self.assertLessEqual(set(bloc), set(exemple) | {'financement'})
        self.assertEqual(bloc['base'], 'ht')
        self.assertEqual(bloc['vue_interne']['comparaison_cse']['statut'],
                         'calculee')
        public = eco.economie_ci_publique(bloc)
        for interne in ('vue_interne', 'alertes_internes', 'comparaison_cse'):
            self.assertNotIn(interne, set(_cles(public)))

    def test_prix_achat_jamais_lu(self):
        lignes = [{'designation': 'Onduleur 50 kW', 'ht': 40000.0,
                   'ttc': 48000.0, 'optionnelle': False, 'onduleur': True,
                   'role_ci': None, 'prix_achat': 30000.0}]
        bloc = eco.assembler_economie_ci(
            _apercu('bt'), tarif_declare={'contrat': 'bt_patente'},
            investissement=INVESTISSEMENT, lignes=lignes,
            mode_installation='industriel')
        self.assertNotIn('prix_achat', set(_cles(bloc)))
        self.assertNotIn(30000.0, list(_nombres(bloc['remplacements'])))
        self.assertEqual(bloc['remplacements'][0]['montant_ht_mad'], 40000.0)

    def test_saisie_refusee_nomme_le_champ(self):
        with self.assertRaises(eco.SaisieEconomieCiInvalide) as ctx:
            eco.assembler_economie_ci(
                _apercu('bt'), tarif_declare={'contrat': 'bt_patente'},
                investissement=INVESTISSEMENT, mode_installation='commercial',
                saisies={'parcours_aide': 'subvention_magique'})
        self.assertEqual(ctx.exception.champ,
                         'saisies_economie_ci.parcours_aide')

    def test_alerte_cos_phi_relayee_jamais_recalculee(self):
        apercu = _apercu('mt')
        apercu['alertes'].append({'code': 'cos_phi_apres_pv',
                                  'champ': 'cos_phi', 'message': 'x',
                                  'interne': True})
        bloc = eco.assembler_economie_ci(
            apercu, investissement=INVESTISSEMENT,
            mode_installation='industriel')
        self.assertIn('cos_phi_apres_pv',
                      [a['code'] for a in bloc['alertes_internes']])
        self.assertNotIn('cos_phi', json.dumps(
            eco.economie_ci_publique(bloc)))


# ── Devis réels (base de données) ────────────────────────────────────────────

User = get_user_model()

ENTREES_ECRAN = {
    'mode': 'industriel', 'phases': 'tri',
    'site': {'ville': 'Casablanca', 'lat': None, 'lon': None},
    'consommation': {'kwh_mensuels': [20000] * 12},
    'rythme': {'jours_ouverts': [True] * 6 + [False],
               'plages': {'ouvre': [[7, 19]], 'samedi': [[7, 13]]},
               'talon': {'kw': 5}},
}


class _BaseDevis(TestCase):
    @classmethod
    def setUpTestData(cls):
        from apps.crm.models import Client
        from apps.stock.models import FicheTechnique, Produit
        from authentication.models import Company
        cls.co = Company.objects.get_or_create(
            slug='ciq210-co', defaults={'nom': 'CIQ210 Co'})[0]
        cls.autre = Company.objects.get_or_create(
            slug='ciq210-autre', defaults={'nom': 'CIQ210 Autre'})[0]
        cls.client_obj = Client.objects.create(company=cls.co,
                                               nom='Usine CIQ210')
        cls.panneau = Produit.objects.create(
            company=cls.co, nom='Panneau 710W', prix_vente=Decimal('1272.73'),
            prix_achat=Decimal('800'))
        FicheTechnique.objects.create(
            company=cls.co, produit=cls.panneau, type_fiche='module',
            pmax_wc=Decimal('710'), vmp_v=Decimal('40'), voc_v=Decimal('48'),
            isc_a=Decimal('18'), imp_a=Decimal('17'))
        cls.ond = Produit.objects.create(
            company=cls.co, nom='Onduleur réseau Huawei 50kW Triphasé',
            prix_vente=Decimal('40000'), prix_achat=Decimal('30000'),
            role_devis='onduleur_reseau', garantie='10 ans constructeur')
        FicheTechnique.objects.create(
            company=cls.co, produit=cls.ond, type_fiche='onduleur',
            ond_ac_kw=Decimal('50'), ond_phases=3, ond_n_mppt=4,
            ond_mppt_v_min=Decimal('200'), ond_mppt_v_max=Decimal('1000'),
            ond_v_max_abs=Decimal('1100'), ond_i_max_mppt_a=Decimal('30'),
            ond_rendement_euro_pct=Decimal('98.4'))

    def setUp(self):
        from apps.ventes.domain import etude_ci
        from apps.ventes.tests.test_ciq118_etude_ci_preview import (
            _production_casablanca)
        patcher = mock.patch.object(etude_ci, 'lire_production',
                                    side_effect=_production_casablanca)
        patcher.start()
        self.addCleanup(patcher.stop)
        self.user = User.objects.create_user(
            username='ciq210_user', password='x', role_legacy='responsable',
            company=self.co)
        self.api = APIClient()
        self.api.credentials(
            HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(self.user)}')

    def _devis(self, ref, *, mode='industriel', tension='mt', extra=None):
        from apps.ventes.domain.etudes import rafraichir_etudes_du_devis
        from apps.ventes.models import Devis, LigneDevis
        params = dict(ENTREES_ECRAN, mode=mode, tension=tension)
        params.update(extra or {})
        devis = Devis.objects.create(
            company=self.co, reference=ref, client=self.client_obj,
            statut='brouillon', taux_tva=Decimal('20'),
            mode_installation=mode, etude_params=params)
        LigneDevis.objects.create(
            devis=devis, produit=self.panneau, designation='Panneau 710W',
            quantite=Decimal('70'), prix_unitaire=Decimal('1272.73'),
            remise=Decimal('0'))
        LigneDevis.objects.create(
            devis=devis, produit=self.ond, designation='Onduleur 50 kW',
            quantite=Decimal('1'), prix_unitaire=Decimal('40000'),
            remise=Decimal('0'))
        rafraichir_etudes_du_devis(devis)
        devis.refresh_from_db()
        return devis

    def _data(self, devis):
        from apps.ventes.quote_engine.builder import build_quote_data
        return build_quote_data(devis, {'pdf_mode': 'full'})


class BuilderEconomieCiTest(_BaseDevis):
    def test_contrat_inconnu_omis_economies_masquees(self):
        devis = self._devis('DEV-CIQ210-0010', tension='bt')
        data = self._data(devis)
        self.assertEqual(data['economie_ci']['statut'], 'omis')
        self.assertTrue(data['economie_ci']['motifs_omission'])
        self.assertTrue(data['masquer_economies'])
        self.assertEqual(data['tarif_mt_mention'], '')

    def test_mt_sans_prix_repli_grille_et_mention_mt(self):
        from apps.ventes.quote_engine.constants_82_21 import MENTION_MT
        devis = self._devis('DEV-CIQ210-0020')
        self.assertIsNotNone(devis.etude_params['etude_ci']['bilan'])
        data = self._data(devis)
        bloc = data['economie_ci']
        self.assertEqual(bloc['statut'], 'calcule')
        self.assertEqual(bloc['tarif']['origine'], tarif_ci.ORIGINE_GRILLE)
        self.assertFalse(data['masquer_economies'])
        self.assertEqual(data['tarif_mt_mention'], MENTION_MT)
        self.assertNotIn('vue_interne', bloc)
        self.assertNotIn('alertes_internes', bloc)

    def test_mt_facture_declaree_origine_facture(self):
        from apps.ventes.quote_engine.constants_82_21 import MENTION_MT
        devis = self._devis('DEV-CIQ210-0030',
                            extra={'tarif_declare': TARIF_MT_FACTURE})
        data = self._data(devis)
        self.assertEqual(data['economie_ci']['tarif']['origine'],
                         tarif_ci.ORIGINE_FACTURE)
        self.assertEqual(data['tarif_mt_mention'], MENTION_MT)

    def test_economie_du_calepinage_n_apparait_nulle_part(self):
        from apps.ventes.models import Devis
        devis = self._devis('DEV-CIQ210-0040')
        # Le calepinage synchronisé écrit sa figure ``savings`` dans
        # ``economies_annuelles`` (domain/pipeline.py, resynchronisation.py).
        params = dict(devis.etude_params, economies_annuelles=987653)
        Devis.objects.filter(pk=devis.pk).update(etude_params=params)
        devis.refresh_from_db()
        data = self._data(devis)
        self.assertNotIn('987653', json.dumps(data, default=str))
        self.assertNotIn('economies_annuelles', data.get('etude') or {})

    def test_devis_commercial_sans_distributeur_aucun_1_75(self):
        devis = self._devis('DEV-CIQ210-0050', mode='commercial',
                            tension='bt',
                            extra={'tarif_declare': {'contrat': 'bt_patente'}})
        bloc = self._data(devis)['economie_ci']
        self.assertEqual(bloc['statut'], 'calcule')
        self.assertNotIn('savings_estimated', set(_cles(bloc)))
        tarifs = [p['tarif_kwh_ht'] for p in bloc['tarif']['tarifs_par_poste']]
        self.assertNotIn(1.75, tarifs)

    def test_residentiel_sans_cle_economie_ci(self):
        from apps.ventes.models import Devis, LigneDevis
        devis = Devis.objects.create(
            company=self.co, reference='DEV-CIQ210-0060',
            client=self.client_obj, statut='brouillon',
            taux_tva=Decimal('20'), mode_installation='residentiel',
            etude_params={})
        LigneDevis.objects.create(
            devis=devis, produit=self.panneau, designation='Panneau 710W',
            quantite=Decimal('10'), prix_unitaire=Decimal('1272.73'),
            remise=Decimal('0'))
        self.assertNotIn('economie_ci', self._data(devis))


class VuesEconomieCiTest(_BaseDevis):
    def test_lecture_interne_avec_vue_interne(self):
        devis = self._devis('DEV-CIQ210-0070')
        rep = self.api.get(f'/api/django/ventes/devis/{devis.pk}/economie-ci/')
        self.assertEqual(rep.status_code, 200, rep.content)
        self.assertIn('vue_interne', rep.json())
        self.assertEqual(rep.json()['statut'], 'calcule')

    def test_devis_d_une_autre_societe_404(self):
        from apps.ventes.models import Devis
        etranger = Devis.objects.create(
            company=self.autre, reference='DEV-CIQ210-0080',
            statut='brouillon', taux_tva=Decimal('20'),
            mode_installation='industriel', etude_params={})
        rep = self.api.get(
            f'/api/django/ventes/devis/{etranger.pk}/economie-ci/')
        self.assertEqual(rep.status_code, 404)

    def test_preview_n_ecrit_rien(self):
        from apps.ventes.models import Devis
        devis = self._devis('DEV-CIQ210-0090')
        avant = (Devis.objects.count(), json.dumps(
            Devis.objects.get(pk=devis.pk).etude_params, sort_keys=True,
            default=str))
        corps = {
            'sortie_etude_ci': devis.etude_params['etude_ci'],
            'saisies': {},
            'lignes': [{'produit': self.ond.pk, 'quantite': 1,
                        'taux_tva': 20,
                        'totaux': {'ht': 40000, 'ttc': 48000}},
                       {'produit': self.panneau.pk, 'quantite': 70,
                        'taux_tva': 20,
                        'totaux': {'ht': 89091.1, 'ttc': 106909.32}}]}
        rep = self.api.post('/api/django/ventes/economie-ci/preview/', corps,
                            format='json')
        self.assertEqual(rep.status_code, 200, rep.content)
        self.assertEqual(rep.json()['statut'], 'calcule')
        apres = (Devis.objects.count(), json.dumps(
            Devis.objects.get(pk=devis.pk).etude_params, sort_keys=True,
            default=str))
        self.assertEqual(avant, apres)
        self.assertNotIn('30000', json.dumps(rep.json()['remplacements']))
