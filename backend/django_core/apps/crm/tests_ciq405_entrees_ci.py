"""CIQ405 — ``entrees_ci`` : UNE lecture lead → entrées du moteur C&I, avec
leur provenance, sans aucun défaut fabriqué (contrat CIQ1 ``lead_pro.json``,
bloc ``entrees_ci``).

Run :
    python manage.py test apps.crm.tests_ciq405_entrees_ci -v 2
"""
import json
from pathlib import Path

from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from authentication.models import Company
from apps.crm.models import Lead
from apps.crm.selectors import entrees_ci_du_lead, entrees_ci_pour_lead_id

User = get_user_model()

CONTRAT = json.loads(
    (Path(__file__).resolve().parent / 'contract_samples'
     / 'lead_pro.json').read_text(encoding='utf-8'))

#: Clés servies (non colonnes) de l'exemple : jamais posées sur le modèle.
_SERVIES = {'id', 'entrees_ci', 'devis_auto', 'incoherence_segment',
            'segment_suggere', 'identite_entreprise',
            # CIQ428 — indicateur interne servi au détail.
            'indicateurs_internes'}


def _sans_date(entree):
    copie = dict(entree)
    copie['provenance'] = {k: v for k, v in entree['provenance'].items()
                           if k != 'date'}
    return copie


class EntreesCi(TestCase):
    def setUp(self):
        self.company, _ = Company.objects.get_or_create(
            slug='ciq405-co', defaults={'nom': 'CIQ405 Co'})

    def _lead(self, **kw):
        kw.setdefault('type_installation', 'commercial')
        return Lead.objects.create(company=self.company, nom='Pro', **kw)

    def test_lead_vide_aucune_valeur_tout_manquant(self):
        bloc = entrees_ci_du_lead(self._lead())
        self.assertEqual(bloc['entrees'], [])
        for colonne in ('conso_mensuelle_kwh', 'tension_raccordement',
                        'compteur_puissance_kva', 'jours_ouverture',
                        'categorie_commerciale', 'surface_toiture_m2',
                        'tva_recuperable'):
            self.assertIn(colonne, bloc['manquants'])

    def test_null_hors_commercial_et_industriel(self):
        for mode in ('residentiel', 'agricole', None):
            self.assertIsNone(entrees_ci_du_lead(
                self._lead(type_installation=mode)), mode)

    def test_tension_site_defaut_visible_est_inconnue(self):
        lead = self._lead(tension_raccordement='bt',
                          tension_source='site_defaut_visible')
        bloc = entrees_ci_du_lead(lead)
        tension = [e for e in bloc['entrees']
                   if e['colonne'] == 'tension_raccordement'][0]
        self.assertEqual(tension['valeur'], 'inconnue')
        self.assertIn('tension_raccordement', bloc['manquants'])

    def test_douze_mois_releve_provenance_facture(self):
        releve = {'mois': [{'mois': f'2025-{m:02d}', 'kwh': f'{1000 + m}.00'}
                           for m in range(1, 13)],
                  'source': 'lu_sur_facture'}
        lead = self._lead(releve_conso=releve,
                          conso_mensuelle_kwh=900)
        conso = entrees_ci_du_lead(lead)['entrees'][0]
        self.assertEqual(conso['colonne'], 'releve_conso')
        self.assertEqual(len(conso['valeur']), 12)
        self.assertEqual(conso['provenance']['detail'], 'facture')
        self.assertEqual(conso['provenance']['origine'], 'lead')

    def test_activity_profile_seulement_en_information(self):
        lead = self._lead(web_questionnaire={'activity_profile': 'continuous'})
        bloc = entrees_ci_du_lead(lead)
        self.assertNotIn('activity_profile',
                         [e['colonne'] for e in bloc['entrees']])
        self.assertIn('activity_profile',
                      [i['colonne'] for i in bloc['informations']])

    def test_la_sortie_egale_l_exemple_du_contrat(self):
        exemple = CONTRAT['exemple']
        champs = {k: v for k, v in exemple.items() if k not in _SERVIES}
        lead = self._lead(**champs)
        bloc = entrees_ci_du_lead(lead)
        attendu = exemple['entrees_ci']
        self.assertEqual(bloc['manquants'], attendu['manquants'])
        servies = {e['colonne']: _sans_date(e) for e in bloc['entrees']}
        for entree in attendu['entrees']:
            self.assertEqual(servies.get(entree['colonne']),
                             _sans_date(entree), entree['colonne'])

    def test_lecture_par_id_filtree_par_societe(self):
        autre, _ = Company.objects.get_or_create(
            slug='ciq405-autre', defaults={'nom': 'CIQ405 Autre'})
        lead = self._lead(tension_raccordement='mt')
        self.assertIsNotNone(entrees_ci_pour_lead_id(lead.pk, self.company))
        self.assertIsNone(entrees_ci_pour_lead_id(lead.pk, autre))


class ServiAuDetailSeulement(TestCase):
    def setUp(self):
        self.company, _ = Company.objects.get_or_create(
            slug='ciq405-api', defaults={'nom': 'CIQ405 Api'})
        self.user = User.objects.create_user(
            username='ciq405_user', password='x', role_legacy='responsable',
            company=self.company)
        self.api = APIClient()
        self.api.credentials(
            HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(self.user)}')
        self.lead = Lead.objects.create(
            company=self.company, nom='Hôtel', type_installation='commercial',
            tension_raccordement='bt', tension_source='declare')

    def test_detail_sert_entrees_ci(self):
        lu = self.api.get(f'/api/django/crm/leads/{self.lead.id}/').data
        self.assertEqual(set(lu['entrees_ci']),
                         {'entrees', 'manquants', 'informations'})

    def test_la_liste_ne_sert_pas_entrees_ci_et_garde_ses_requetes(self):
        def _compte():
            from django.db import connection
            from django.test.utils import CaptureQueriesContext
            with CaptureQueriesContext(connection) as ctx:
                resp = self.api.get('/api/django/crm/leads/')
            self.assertEqual(resp.status_code, 200)
            return resp, len(ctx.captured_queries)

        resp, avant = _compte()
        lignes = resp.data.get('results', resp.data)
        for ligne in lignes:
            self.assertNotIn('entrees_ci', ligne)
        Lead.objects.filter(pk=self.lead.pk).update(
            jours_ouverture=[1, 2, 3], regime_equipes='1x8',
            surface_toiture_m2=300)
        _resp, apres = _compte()
        self.assertEqual(apres, avant)
