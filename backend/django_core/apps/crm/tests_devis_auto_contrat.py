"""
QJR600 (Groupe QJR5) — la règle « devis automatique prêt » est SERVIE
structurée : bloc ``devis_auto`` du lead = {pret, manquants, message,
manquants_detail: [{champ, label}], requis: [[…]]}.

Contrat partagé : ``apps/crm/contract_samples/devis_auto_pret.json`` (QJR509).

Run:
    powershell -File scripts/test-backend.ps1 -RestoreDb \
        -Modules "apps.crm.tests_devis_auto_contrat"
"""
import json
from decimal import Decimal
from pathlib import Path

from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from apps.crm.devis_auto import (
    champs_manquants, champs_manquants_detail, champs_requis)
from apps.crm.models import Lead
from authentication.models import Company

User = get_user_model()

CONTRAT = json.loads(
    (Path(__file__).resolve().parent / 'contract_samples'
     / 'devis_auto_pret.json').read_text(encoding='utf-8'))


class TestDevisAutoContrat(TestCase):
    def setUp(self):
        self.company = Company.objects.create(
            nom='QJR600 Co', slug='qjr600-co')
        self.user = User.objects.create_user(
            username='qjr600_resp', password='x', role_legacy='responsable',
            company=self.company)
        self.api = APIClient()
        self.api.credentials(
            HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(self.user)}')

    def _bloc(self, lead):
        r = self.api.get(f'/api/django/crm/leads/{lead.id}/')
        self.assertEqual(r.status_code, 200, r.content)
        return r.json()['devis_auto']

    def test_industriel_bill_kwh_seul_est_pret_et_requis_porte_le_groupe(self):
        # ALEA47 — avec le contrat et le rythme que le moteur exige aussi.
        lead = Lead.objects.create(
            company=self.company, nom='Usine', type_installation='industriel',
            bill_kwh=500, contrat_electricite='bt_patente',
            regime_equipes='3x8', jours_ouverture=[1, 2, 3, 4, 5, 6, 7],
            raccordement='triphase')
        bloc = self._bloc(lead)
        self.assertEqual(bloc['manquants_detail'], [])
        self.assertTrue(bloc['pret'])
        # CIQ404 — groupe pro du contrat CIQ1 (kWh, relevé ou facture MAD).
        self.assertIn(['conso_mensuelle_kwh', 'bill_kwh', 'releve_conso',
                       'facture_hiver', 'puissance_max_appelee_kva'], bloc['requis'])

    def test_qjr603_pro_kwh_seulement_sans_facture_reste_pret(self):
        """QJR603 (D-QJR5-14) — le lead que le devis automatique dimensionne
        depuis ses kWh : aucune facture exigée. ALEA47 (D-ACI-5=a) — mais kWh
        SEUL ≠ prêt : le contrat et le rythme manquent (lead 1637)."""
        complet = {'contrat_electricite': 'bt_patente', 'regime_equipes': '3x8',
                   'jours_ouverture': [1, 2, 3, 4, 5, 6, 7],
                   'raccordement': 'triphase'}  # ADEV89 — la phase aussi
        for type_installation, kwh in (
                ('industriel', {'conso_mensuelle_kwh': 30000}),
                ('industriel', {'bill_kwh': 30000}),
                ('commercial', {'conso_mensuelle_kwh': 30000})):
            seul = Lead.objects.create(
                company=self.company, nom='Kwh seul',
                type_installation=type_installation, facture_hiver=None,
                raccordement='triphase', **kwh)
            bloc = self._bloc(seul)
            self.assertFalse(bloc['pret'], (type_installation, kwh))
            # ADEV125 (D-ACAL-92) — le contrat absent est supposé (BT).
            self.assertEqual([e['champ'] for e in bloc['manquants_detail']],
                             ['jours_ouverture'])
            lead = Lead.objects.create(
                company=self.company, nom='Kwh + moteur',
                type_installation=type_installation, facture_hiver=None,
                **kwh, **complet)
            self.assertEqual(champs_manquants(lead), [], (type_installation, kwh))
            self.assertTrue(self._bloc(lead)['pret'], (type_installation, kwh))

    def test_residentiel_facture_hiver_zero_est_manquant(self):
        lead = Lead.objects.create(
            company=self.company, nom='Maison', facture_hiver=Decimal('0'), ville='Casablanca')
        bloc = self._bloc(lead)
        self.assertFalse(bloc['pret'])
        self.assertEqual([e['champ'] for e in bloc['manquants_detail']],
                         ['facture_hiver'])

    def test_bloc_porte_les_cles_du_contrat(self):
        lead = Lead.objects.create(
            company=self.company, nom='Usine 2', type_installation='commercial')
        bloc = self._bloc(lead)
        self.assertTrue(set(CONTRAT['exemple']['devis_auto']) <= set(bloc))
        detail = bloc['manquants_detail'][0]
        self.assertEqual(
            set(detail), set(CONTRAT['exemple']['devis_auto']['manquants_detail'][0]))
        # CIQ404 — le groupe pro v2 (``exemple_commercial``) remplace le
        # groupe v1 de l'``exemple`` historique.
        self.assertEqual(bloc['requis'],
                         CONTRAT['exemple_commercial']['devis_auto']['requis'])

    def test_agricole_requis_conforme_au_contrat(self):
        lead = Lead.objects.create(
            company=self.company, nom='Ferme', type_installation='agricole', raccordement='triphase')
        attendu = CONTRAT['exemple_agricole']['devis_auto']
        self.assertEqual(champs_requis(lead), attendu['requis'])
        self.assertEqual([e['champ'] for e in champs_manquants_detail(lead)],
                         [e['champ'] for e in attendu['manquants_detail']])

    def test_manquants_libelles_inchanges(self):
        lead = Lead.objects.create(
            company=self.company, nom='Été', facture_hiver=Decimal('500'),
            ete_differente=True, ville='Casablanca')
        self.assertEqual(champs_manquants(lead), ['facture été'])
        self.assertEqual(champs_requis(lead),
                         [['facture_hiver', 'conso_mensuelle_kwh'], ['facture_ete'], ['ville', 'gps_lat']])


class GardeEgaleAuMoteurTests(TestCase):
    """ALEA70 — la garde « devis automatique prêt » dit exactement ce qui
    manque au MOTEUR : un lead prêt n'est jamais refusé par
    ``calculer_conception`` ; un lead refusé n'est pas prêt et nomme le même
    champ. ``manques_du_moteur`` (ventes) lit cette garde : une seule liste.
    Constat T4-U1-022 : un résidentiel au kWh déclaré sans facture était
    « Facture manquante » alors que le moteur le calcule."""

    def setUp(self):
        from unittest import mock

        from apps.ventes.tests import test_devis_auto as res

        coupure = mock.patch('urllib.request.urlopen', side_effect=OSError('ALEA70 hors réseau'))
        coupure.start()
        self.addCleanup(coupure.stop)
        self.company = res.make_company('alea70-co')
        res.seed_catalogue(self.company)
        self.ville = res.VILLE_ANCRE

    def _lead(self, **champs):
        return Lead.objects.create(company=self.company, nom='Alea', prenom='Soixante-dix', **champs)

    def _verdicts(self, lead):
        from apps.ventes.conception.moteur import calculer_conception
        from apps.ventes.selectors import manques_du_moteur

        resultat = calculer_conception(lead, self.company)
        manquants = [e['champ'] for e in champs_manquants_detail(lead)]
        return not champs_manquants(lead), resultat, manquants, manques_du_moteur(lead)

    def test_pret_si_et_seulement_si_le_moteur_calcule(self):
        cas = {
            'facture': dict(facture_hiver=Decimal('1800'), ville=self.ville),
            'kwh_seul': dict(conso_mensuelle_kwh=Decimal('450'), ville=self.ville),
            'kwh_ete_different': dict(conso_mensuelle_kwh=Decimal('450'), ete_differente=True, ville=self.ville),
            'rien': dict(ville=self.ville),
            'sans_lieu': dict(facture_hiver=Decimal('1800'), ville=''),
        }
        for nom, champs in cas.items():
            with self.subTest(cas=nom):
                pret, resultat, manquants, manques = self._verdicts(self._lead(**champs))
                self.assertEqual(pret, resultat.etat == 'complet', (nom, resultat.refus, manquants))
                if not pret:
                    self.assertIn(resultat.refus['champ'], manquants)
                self.assertEqual([m['champ'] for m in manques], manquants)
        # Le constat : kWh déclaré, aucune facture ⇒ prêt (le moteur calcule).
        pret, resultat, manquants, _ = self._verdicts(self._lead(conso_mensuelle_kwh=Decimal('450'),
                                                                 ville=self.ville))
        self.assertEqual((pret, resultat.etat, manquants), (True, 'complet', []))
