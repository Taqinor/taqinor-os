"""AGR404 — ``entrees_pompage`` : UNE lecture lead → entrées du dimensionnement,
avec leur provenance et sans aucun défaut fabriqué.

Contrat partagé : ``apps/crm/contract_samples/lead_pompage.json`` (AGR1,
bloc ``entrees_pompage`` + ``regles.entrees_pompage.cibles``). Le contrat
fait foi sur deux points : ``source_eau`` et ``electricite_sur_place`` sont
des INFORMATIONS sans cible (« ne choisit jamais `alim` à la place du
vendeur ») — aucun type de pompe ni alimentation n'est donc déduit ici.

Run :
    python manage.py test apps.crm.tests_agr404_entrees_pompage -v 2
"""
import json
from decimal import Decimal
from pathlib import Path

from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from authentication.models import Company
from apps.crm import selectors
from apps.crm.models import Lead, LeadActivity

User = get_user_model()

CONTRAT = json.loads(
    (Path(__file__).resolve().parent / 'contract_samples'
     / 'lead_pompage.json').read_text(encoding='utf-8'))

#: Clés v1 qu'une entrée ne doit JAMAIS viser (contrat AGR1).
CLES_V1 = ('current_fuel', 'fuel_spend_current', 'distance_m', 'hmt_static',
           'region', 'crop', 'surface_ha')


def _par_colonne(bloc):
    return {e['colonne']: e for e in bloc['entrees']}


class EntreesPompage(TestCase):
    def setUp(self):
        self.company, _ = Company.objects.get_or_create(
            slug='agr404-co', defaults={'nom': 'AGR404 Co'})

    def _lead(self, **kwargs):
        kwargs.setdefault('type_installation', 'agricole')
        return Lead.objects.create(company=self.company, nom='Ferme',
                                   **kwargs)

    def test_lead_vide_aucune_valeur_tout_manquant(self):
        bloc = selectors.entrees_pompage_du_lead(self._lead())
        self.assertEqual(bloc['entrees'], [])
        attendus = [c for c, _k, _p in selectors.ENTREES_POMPAGE_CIBLES]
        self.assertEqual(bloc['manquants'], attendus)

    def test_sans_distance_pas_de_distance_et_listee_manquante(self):
        bloc = selectors.entrees_pompage_du_lead(
            self._lead(niveau_statique_m=Decimal('20')))
        self.assertNotIn('distance_forage_champ_m', _par_colonne(bloc))
        self.assertIn('distance_forage_champ_m', bloc['manquants'])
        self.assertNotIn('distance_champ_m',
                         {e['cle_etude'] for e in bloc['entrees']})

    def test_aucun_defaut_fabrique_type_ou_alimentation(self):
        bloc = selectors.entrees_pompage_du_lead(self._lead(
            source_eau='bassin', raccordement='monophase',
            electricite_sur_place='monophase'))
        cles = {e['cle_etude'] for e in bloc['entrees']}
        colonnes = set(_par_colonne(bloc))
        self.assertNotIn('type_pompe', cles)
        self.assertNotIn('alim', cles)
        self.assertNotIn('source_eau', colonnes)
        self.assertNotIn('electricite_sur_place', colonnes)

    def test_volume_declare_derive_du_debit_et_des_heures_actuels(self):
        bloc = selectors.entrees_pompage_du_lead(self._lead(
            pompe_actuelle_debit_m3h=Decimal('10'),
            pompage_heures_jour=Decimal('7')))
        derive = [e for e in bloc['entrees']
                  if e['colonne'] == 'besoin_eau_m3j']
        self.assertEqual(len(derive), 1)
        self.assertEqual(derive[0]['valeur'], 70)
        self.assertEqual(derive[0]['provenance'], 'derive')
        self.assertEqual(derive[0]['formule'],
                         selectors.FORMULE_VOLUME_DECLARE)
        heures = _par_colonne(bloc)['pompage_heures_jour']
        self.assertEqual(heures['libelle'], 'heures de la pompe actuelle')
        self.assertEqual(heures['chemin'], 'besoin.heures_actuelles_jour')

    def test_le_besoin_declare_prime_sur_le_volume_derive(self):
        bloc = selectors.entrees_pompage_du_lead(self._lead(
            besoin_eau_m3j=Decimal('135'), besoin_eau_source='client',
            pompe_actuelle_debit_m3h=Decimal('10'),
            pompage_heures_jour=Decimal('7')))
        besoins = [e for e in bloc['entrees']
                   if e['colonne'] == 'besoin_eau_m3j']
        self.assertEqual([(e['valeur'], e['provenance']) for e in besoins],
                         [(135, 'client')])

    def test_pompe_actuelle_marquee_information_et_ne_sait_pas_omis(self):
        bloc = selectors.entrees_pompage_du_lead(self._lead(
            pompe_actuelle_cv=Decimal('7.5'), pompe_actuelle_type='ne_sait_pas'))
        par = _par_colonne(bloc)
        self.assertTrue(par['pompe_actuelle_cv']['information'])
        self.assertEqual(par['pompe_actuelle_cv']['chemin'], 'plaque.cv')
        self.assertNotIn('pompe_actuelle_type', par)

    def test_aucune_cible_v1(self):
        lead = self._lead(
            niveau_statique_m=Decimal('32'), distance_forage_champ_m=25,
            region_agricole='souss-massa', culture='agrumes',
            surface_irriguee_ha=4, pompe_alim_actuelle='butane',
            butane_bouteilles_jour=Decimal('4'), mois_irrigation=[4, 5])
        for entree in selectors.entrees_pompage_du_lead(lead)['entrees']:
            self.assertNotIn(entree['cle_etude'], CLES_V1, entree)

    def test_la_sortie_egale_l_exemple_du_contrat(self):
        exemple = CONTRAT['exemple']
        champs = {c['nom'] for c in CONTRAT['colonnes']}
        valeurs = {k: v for k, v in exemple.items()
                   if k in champs and v is not None}
        lead = Lead.objects.create(
            company=self.company, nom='Ferme', source=Lead.Source.SITE_WEB,
            type_installation='agricole', **valeurs)
        # Les colonnes que l'exemple dit « client » ont été saisies par un
        # humain dans l'ERP (une ligne de chatter avec un utilisateur).
        user = User.objects.create_user(
            username='agr404_user', password='x', role_legacy='responsable',
            company=self.company)
        attendues = exemple['entrees_pompage']['entrees']
        for entree in attendues:
            if entree['provenance'] == 'client':
                LeadActivity.objects.create(
                    company=self.company, lead=lead, user=user,
                    kind=LeadActivity.Kind.MODIFICATION,
                    field=entree['colonne'], field_label=entree['colonne'])
        servies = _par_colonne(selectors.entrees_pompage_du_lead(lead))
        for entree in attendues:
            servie = servies.get(entree['colonne'])
            self.assertIsNotNone(servie, entree['colonne'])
            self.assertTrue(set(entree) <= set(servie), entree['colonne'])
            for cle in ('valeur', 'provenance', 'cle_etude', 'chemin'):
                self.assertEqual(servie[cle], entree[cle],
                                 f"{entree['colonne']}.{cle}")

    def test_lecture_filtree_par_societe(self):
        lead = self._lead(niveau_statique_m=Decimal('20'))
        autre, _ = Company.objects.get_or_create(
            slug='agr404-autre', defaults={'nom': 'AGR404 Autre'})
        self.assertIsNone(
            selectors.entrees_pompage_pour_lead_id(lead.pk, autre))
        bloc = selectors.entrees_pompage_pour_lead_id(lead.pk, self.company)
        self.assertIn('niveau_statique_m', _par_colonne(bloc))


class EntreesPompageServiesAuDetail(TestCase):
    def setUp(self):
        self.company, _ = Company.objects.get_or_create(
            slug='agr404-api', defaults={'nom': 'AGR404 API'})
        self.user = User.objects.create_user(
            username='agr404_api', password='x', role_legacy='responsable',
            company=self.company)
        self.api = APIClient()
        self.api.credentials(
            HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(self.user)}')
        self.lead = Lead.objects.create(
            company=self.company, nom='Ferme', type_installation='agricole',
            niveau_statique_m=Decimal('32'))

    def test_detail_sert_le_bloc_et_la_liste_non(self):
        detail = self.api.get(f'/api/django/crm/leads/{self.lead.id}/').data
        self.assertEqual(set(detail['entrees_pompage']),
                         {'entrees', 'manquants'})
        self.assertIn('niveau_statique_m',
                      _par_colonne(detail['entrees_pompage']))
        liste = self.api.get('/api/django/crm/leads/').data
        lignes = liste['results'] if 'results' in liste else liste
        self.assertNotIn('entrees_pompage', lignes[0])
