"""AGR400 — colonnes pompage du Lead, chacune avec sa question d'appel.

Contrat partagé : ``apps/crm/contract_samples/lead_pompage.json`` (AGR1,
PACT10). Chaque colonne du contrat existe sur ``crm.Lead`` ; celles qu'on
pose au téléphone portent leur question orale dans le ``help_text`` (règle du
bloc L4 de ``models.py``). Les colonnes ``*_source`` et
``carburant_prix_declare_le`` sont posées par le SERVEUR, jamais saisies.

Run :
    python manage.py test apps.crm.tests_agr400_lead_pompage -v 2
"""
import json
from decimal import Decimal
from pathlib import Path

from django.contrib.auth import get_user_model
from django.test import SimpleTestCase, TestCase
from django.utils import timezone
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from authentication.models import Company
from apps.crm import activity, selectors, services
from apps.crm.models import Lead

User = get_user_model()

CONTRAT = json.loads(
    (Path(__file__).resolve().parent / 'contract_samples'
     / 'lead_pompage.json').read_text(encoding='utf-8'))

COLONNES = [c['nom'] for c in CONTRAT['colonnes']]

#: Posées par le serveur : aucune question orale.
SANS_QUESTION = {
    'niveau_statique_source', 'debit_forage_source', 'besoin_eau_source',
    'pompe_hmt_source', 'carburant_prix_declare_le',
}
#: AGR401 a livré ``pompe_actuelle_cv`` : plus aucune colonne hors contrôle.
HORS_AGR400 = set()

#: Les colonnes NOUVELLES d'AGR400 (le reste existait déjà).
NOUVELLES = [
    'source_eau', 'niveau_statique_m', 'niveau_statique_source',
    'profondeur_forage_m', 'debit_forage_m3h', 'debit_forage_source',
    'besoin_eau_m3j', 'besoin_eau_source', 'culture', 'surface_irriguee_ha',
    'irrigation_methode', 'region_agricole', 'pompe_actuelle_type',
    'pompe_actuelle_debit_m3h', 'butane_bouteilles_jour',
    'carburant_prix_unitaire_mad', 'carburant_prix_declare_le',
    'depense_carburant_mad_mois', 'mois_irrigation',
    'distance_forage_champ_m', 'electricite_sur_place',
    'autorisation_prelevement', 'autorisation_numero',
    'autorisation_debit_l_s', 'autorisation_volume_m3_an', 'compteur_eau',
    'projet_pompage', 'deja_beneficiaire_fda', 'pompe_hmt_source',
]


def _champ(nom):
    return Lead._meta.get_field(nom)


class ColonnesDuContrat(SimpleTestCase):
    def test_chaque_colonne_du_contrat_existe_sur_le_lead(self):
        for nom in COLONNES:
            if nom in HORS_AGR400:
                continue
            self.assertIsNotNone(_champ(nom), nom)

    def test_chaque_colonne_posee_au_telephone_porte_sa_question(self):
        for nom in COLONNES:
            if nom in SANS_QUESTION or nom in HORS_AGR400:
                continue
            texte = str(_champ(nom).help_text or '')
            self.assertTrue(texte.startswith("Question à l'appel : « "),
                            f'{nom} : {texte!r}')
            self.assertIn('»', texte, nom)

    def test_les_colonnes_serveur_n_ont_pas_de_question(self):
        for nom in SANS_QUESTION:
            self.assertNotIn("Question à l'appel", str(_champ(nom).help_text))

    def test_toutes_les_nouvelles_sont_nullables(self):
        for nom in NOUVELLES:
            self.assertTrue(_champ(nom).null, nom)
            self.assertIsNone(Lead(nom='x').__dict__.get(nom), nom)

    def test_les_choix_sont_ceux_du_contrat(self):
        for colonne in CONTRAT['colonnes']:
            if colonne['type'] != 'choix' or 'choix' not in colonne:
                continue
            if colonne['nom'] in HORS_AGR400:
                continue
            valeurs = [v for v, _ in _champ(colonne['nom']).choices]
            self.assertEqual(valeurs, colonne['choix'], colonne['nom'])

    def test_pompage_heures_jour_dit_pompe_actuelle(self):
        self.assertIn('pompe ACTUELLE',
                      str(_champ('pompage_heures_jour').help_text))

    def test_hmt_et_debit_ont_leur_question(self):
        self.assertIn('hauteur totale', str(_champ('pompe_hmt_m').help_text))
        self.assertIn('m³ par heure', str(_champ('pompe_debit_m3h').help_text))

    def test_le_chatter_journalise_chaque_nouvelle_colonne(self):
        for nom in NOUVELLES:
            self.assertIn(nom, activity.TRACKED_FIELDS, nom)

    def test_la_garde_qjr234_reste_verte(self):
        self.assertEqual(selectors.lead_provenance_omissions(), [])

    def test_chaque_nouvelle_colonne_est_declaree_ou_exclue(self):
        for nom in NOUVELLES:
            self.assertTrue(
                nom in selectors.LEAD_PROVENANCE_FIELDS
                or nom in selectors.LEAD_PROVENANCE_EXCLUSIONS, nom)

    def test_la_fusion_connait_les_nouvelles_colonnes(self):
        for nom in NOUVELLES:
            self.assertIn(nom, services._MERGE_FILL_FIELDS, nom)


class SaisieParLApi(TestCase):
    def setUp(self):
        self.company, _ = Company.objects.get_or_create(
            slug='agr400-co', defaults={'nom': 'AGR400 Co'})
        self.user = User.objects.create_user(
            username='agr400_user', password='x', role_legacy='responsable',
            company=self.company)
        self.lead = Lead.objects.create(
            company=self.company, nom='Ferme AGR400',
            type_installation='agricole')
        self.api = APIClient()
        self.api.credentials(
            HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(self.user)}')
        self.url = f'/api/django/crm/leads/{self.lead.id}/'

    def _patch(self, body):
        return self.api.patch(self.url, body, format='json')

    CORPS = {
        'source_eau': 'forage',
        'niveau_statique_m': '32.00',
        'profondeur_forage_m': '90.00',
        'debit_forage_m3h': '36.00',
        'besoin_eau_m3j': '135.00',
        'culture': 'agrumes',
        'surface_irriguee_ha': '4.00',
        'irrigation_methode': 'goutte',
        'region_agricole': 'souss-massa',
        'pompe_actuelle_type': 'immergee',
        'butane_bouteilles_jour': '4.0',
        'carburant_prix_unitaire_mad': '50.00',
        'mois_irrigation': [4, 5, 6, 7, 8, 9],
        'distance_forage_champ_m': '25.00',
        'electricite_sur_place': 'aucune',
        'autorisation_prelevement': 'en_cours',
        'compteur_eau': False,
        'projet_pompage': 'existant',
        'deja_beneficiaire_fda': False,
        'pompe_hmt_m': '60.00',
    }

    def test_patch_puis_get_rend_les_memes_valeurs(self):
        resp = self._patch(self.CORPS)
        self.assertEqual(resp.status_code, 200, resp.data)
        lu = self.api.get(self.url).data
        for cle, valeur in self.CORPS.items():
            self.assertEqual(lu[cle], valeur, cle)

    def test_patch_vide_rend_un_objet_identique(self):
        self._patch(self.CORPS)
        avant = self.api.get(self.url).data
        resp = self._patch({})
        self.assertEqual(resp.status_code, 200, resp.data)
        apres = self.api.get(self.url).data
        for cle in COLONNES:
            if cle in HORS_AGR400:
                continue
            self.assertEqual(apres[cle], avant[cle], cle)

    def test_mois_hors_1_12_refuse_en_400_qui_nomme_le_champ(self):
        resp = self._patch({'mois_irrigation': [13]})
        self.assertEqual(resp.status_code, 400)
        self.assertIn('mois_irrigation', resp.data)
        resp = self._patch({'mois_irrigation': [4, 4]})
        self.assertEqual(resp.status_code, 400)
        self.assertIn('mois_irrigation', resp.data)

    def test_le_serveur_pose_provenances_et_date_du_prix(self):
        self._patch(self.CORPS)
        self.lead.refresh_from_db()
        self.assertEqual(self.lead.niveau_statique_source, 'declare')
        self.assertEqual(self.lead.debit_forage_source, 'client')
        self.assertEqual(self.lead.besoin_eau_source, 'client')
        self.assertEqual(self.lead.pompe_hmt_source, 'declaree')
        self.assertEqual(self.lead.carburant_prix_declare_le,
                         timezone.localdate())

    def test_les_colonnes_serveur_ne_se_saisissent_pas(self):
        resp = self._patch({'niveau_statique_source': 'mesure_visite',
                            'carburant_prix_declare_le': '2020-01-01'})
        self.assertEqual(resp.status_code, 200, resp.data)
        self.lead.refresh_from_db()
        self.assertIsNone(self.lead.niveau_statique_source)
        self.assertIsNone(self.lead.carburant_prix_declare_le)

    def test_une_valeur_effacee_efface_sa_provenance(self):
        self._patch({'niveau_statique_m': '12'})
        self._patch({'niveau_statique_m': None})
        self.lead.refresh_from_db()
        self.assertIsNone(self.lead.niveau_statique_source)


class FusionConserveLePompage(TestCase):
    def test_la_fusion_recopie_les_colonnes_vides_du_survivant(self):
        company, _ = Company.objects.get_or_create(
            slug='agr400-fusion', defaults={'nom': 'AGR400 Fusion'})
        user = User.objects.create_user(
            username='agr400_fusion', password='x',
            role_legacy='responsable', company=company)
        survivant = Lead.objects.create(company=company, nom='Survivant')
        absorbe = Lead.objects.create(
            company=company, nom='Absorbé', source_eau='puits',
            niveau_statique_m=Decimal('18.50'), mois_irrigation=[5, 6],
            electricite_sur_place='triphase', culture='olivier')
        services.merge_leads(survivant, [absorbe], user)
        survivant.refresh_from_db()
        self.assertEqual(survivant.source_eau, 'puits')
        self.assertEqual(survivant.niveau_statique_m, Decimal('18.50'))
        self.assertEqual(survivant.mois_irrigation, [5, 6])
        self.assertEqual(survivant.electricite_sur_place, 'triphase')
        self.assertEqual(survivant.culture, 'olivier')
