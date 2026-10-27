"""CIQ412 — lien « questionnaire client » d'un lead PRO : sections réseau,
activité, site, société — et plus jamais une question résidentielle.

Contrats partagés : ``questionnaire_lead.json`` (``exemple_pro``,
``segment_pro``) et ``questionnaire_lien_mint.json`` (``exemple_pro``), CIQ400.

Le GPS est une section du lead pro, cochée par défaut tant qu'il manque
(fondateur 26/10/2026 : calcul heure par heure de la production) ;
``exemple_pro`` du contrat le montre.

Run :
    python manage.py test apps.crm.tests_ciq412_questionnaire_pro -v 2
"""
import json
from decimal import Decimal
from pathlib import Path

from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from authentication.models import Company
from apps.crm import questionnaire as quest
from apps.crm.models import Lead, QuestionnaireLien

User = get_user_model()

ICI = Path(__file__).resolve().parent / 'contract_samples'
CONTRAT = json.loads((ICI / 'questionnaire_lead.json').read_text(
    encoding='utf-8'))
CONTRAT_MINT = json.loads((ICI / 'questionnaire_lien_mint.json').read_text(
    encoding='utf-8'))
PUBLIC = '/api/django/crm/public/questionnaire/{}/'


class QuestionnairePro(TestCase):
    def setUp(self):
        self.company = Company.objects.create(
            nom='CIQ412 Co', slug='ciq412-co')
        self.user = User.objects.create_user(
            username='ciq412_resp', password='x', role_legacy='responsable',
            company=self.company)
        self.api = APIClient()
        self.api.credentials(
            HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(self.user)}')

    def _pro(self, **extra):
        extra.setdefault('type_installation', 'commercial')
        return Lead.objects.create(
            company=self.company, nom='Hôtel', prenom='Karim', **extra)

    def _mint(self, lead, corps=None):
        return self.api.post(
            f'/api/django/crm/leads/{lead.pk}/questionnaire-lien/',
            corps or {}, format='json')

    def test_contrat_sections_et_colonnes(self):
        self.assertEqual(CONTRAT['sections'], list(quest.SECTIONS))
        for section, colonnes in CONTRAT['exemple_pro']['champs'].items():
            if section == 'contact':
                continue  # écart documenté : contact garde ses colonnes
            self.assertEqual(list(quest.CHAMPS_PAR_SECTION[section]),
                             colonnes, section)
        self.assertEqual(
            set(CONTRAT['segment_pro']['sections_pro']) - {'contact', 'gps'},
            set(quest.SECTIONS_PRO_SEULES))

    def test_envoi_pro_coche_les_sections_pro_manquantes(self):
        lead = self._pro(tension_raccordement='bt', tension_source='declare',
                         categorie_commerciale='hotel',
                         surface_toiture_m2=Decimal('650'),
                         type_surface='toiture',
                         type_toiture='terrasse_beton',
                         societe='Hôtel Exemple SARL',
                         email='h@example.ma', ville='Marrakech',
                         adresse='Route X')
        res = self._mint(lead)
        self.assertEqual(res.status_code, 200, res.data)
        questions = res.data['questions']
        self.assertTrue(set(CONTRAT_MINT['exemple_pro']['questions'])
                        <= set(questions))
        for residentielle in ('occupation', 'equipements', 'energie',
                              'toiture', 'photo_facture'):
            self.assertNotIn(residentielle, questions)
        attendu = CONTRAT_MINT['exemple_pro']['manquantes']
        for section, valeur in attendu.items():
            self.assertEqual(res.data['manquantes'][section], valeur, section)
        self.assertTrue(questions['reseau'])
        self.assertFalse(questions['site'])

    def test_section_residentielle_refusee_en_400_qui_la_nomme(self):
        lead = self._pro()
        for section in CONTRAT['segment_pro']['refusees_400']:
            res = self._mint(lead, {'questions': {section: True}})
            self.assertEqual(res.status_code, 409, section)  # ENF11 : hors segment
            self.assertIn(section, res.data['detail'])

    def test_activite_et_societe_manquantes_equipes_fermeture_tva(self):
        # Fondateur 26/10/2026 — régime d'équipes, mois de fermeture (liste
        # vide = « jamais fermé », une réponse) et TVA récupérable comptent.
        activite = dict(categorie_commerciale='hotel', jours_ouverture=[1, 2],
                        heure_debut=8, heure_fin=18, regime_equipes='1x8',
                        fermeture_mois=[])
        self.assertFalse(quest.manquantes(self._pro(**activite))['activite'])
        for vide in ('regime_equipes', 'fermeture_mois'):
            lead = self._pro(**dict(activite, **{vide: None}))
            self.assertTrue(quest.manquantes(lead)['activite'], vide)
        societe = dict(societe='Hôtel SARL', ice='001234567000089',
                       tva_recuperable='oui')
        self.assertFalse(quest.manquantes(self._pro(**societe))['societe'])
        lead = self._pro(**dict(societe, tva_recuperable=None))
        self.assertTrue(quest.manquantes(lead)['societe'])

    def test_post_activite_jamais_ferme_enregistre_une_liste_vide(self):
        lead = self._pro()
        lien = QuestionnaireLien.objects.create(
            company=self.company, lead=lead, questions={'activite': True})
        res = self.client.post(
            PUBLIC.format(lien.token),
            data=json.dumps({'section': 'activite',
                             'reponses': {'fermeture_mois': []}}),
            content_type='application/json')
        self.assertEqual(res.status_code, 200, res.content)
        lead.refresh_from_db()
        self.assertEqual(lead.fermeture_mois, [])

    def test_post_reseau_n_ecrit_que_ses_colonnes_jamais_de_vide(self):
        lead = self._pro(email='h@example.ma', compteur_puissance_kva=60,
                         facture_hiver=Decimal('5000'))
        lien = QuestionnaireLien.objects.create(
            company=self.company, lead=lead,
            questions={s: s == 'reseau' for s in quest.sections_du_lead(lead)})
        get = self.client.get(PUBLIC.format(lien.token))
        self.assertEqual(get.status_code, 200, get.content)
        self.assertEqual(get.json()['sections'], ['reseau'])
        res = self.client.post(
            PUBLIC.format(lien.token),
            data=json.dumps({'section': 'reseau', 'reponses': {
                'tension_raccordement': 'mt',
                'compteur_puissance_kva': None,
                'releve_conso': {'mois': [
                    {'mois': '2026-08', 'kwh': 40000, 'kwh_pointe': 6000}],
                    'source': 'ocr_confirme'},
                'facture_hiver': 4200, 'email': 'pirate@example.ma',
                'decideur': 'seul'}}),
            content_type='application/json')
        self.assertEqual(res.status_code, 200, res.content)
        lead.refresh_from_db()
        self.assertEqual(lead.tension_raccordement, 'mt')
        self.assertEqual(lead.tension_source, 'declare')
        self.assertEqual(lead.releve_conso['source'], 'declare')
        self.assertEqual(lead.releve_conso['mois'][0]['kwh_pointe'],
                         '6000.00')
        # Une valeur existante non répondue n'est jamais vidée.
        self.assertEqual(lead.compteur_puissance_kva, Decimal('60'))
        # Fondateur 26/10/2026 — la dernière facture (MAD) est une colonne
        # de la section réseau.
        self.assertEqual(lead.facture_hiver, Decimal('4200'))
        # Hors section : jamais écrit.
        self.assertEqual(lead.email, 'h@example.ma')
        self.assertIsNone(lead.decideur)

    def test_gps_coche_par_defaut_tant_qu_il_manque(self):
        # Fondateur 26/10/2026 — le GPS fait partie des sections pro par défaut.
        sans = self._pro()
        self.assertTrue(quest.questions_par_defaut(sans)['gps'])
        self.assertIn('gps', quest.sections_du_lead(sans))
        avec = self._pro(gps_lat=Decimal('33.57'), gps_lng=Decimal('-7.59'))
        self.assertFalse(quest.questions_par_defaut(avec)['gps'])

    def test_site_manquant_tant_que_type_de_surface_ou_toiture_vide(self):
        # Fondateur 26/10/2026 — pas seulement la surface.
        complet = dict(surface_toiture_m2=Decimal('650'),
                       type_surface='toiture', type_toiture='bac_acier')
        self.assertFalse(quest.manquantes(self._pro(**complet))['site'])
        for vide in ('type_surface', 'type_toiture', 'surface_toiture_m2'):
            lead = self._pro(**dict(complet, **{vide: None}))
            self.assertTrue(quest.manquantes(lead)['site'], vide)
        # Une ombrière ou un terrain n'a pas de couverture à déclarer.
        ombriere = self._pro(**dict(complet, type_surface='ombriere',
                                    type_toiture=None))
        self.assertFalse(quest.manquantes(ombriere)['site'])

    def test_reseau_manquant_tant_que_contrat_ou_phase_vide(self):
        # Fondateur 26/10/2026 — contrat et phase bloquent le devis auto.
        complet = dict(tension_raccordement='bt', tension_source='declare',
                       compteur_puissance_kva=60,
                       contrat_electricite='bt_patente',
                       raccordement='triphase', conso_mensuelle_kwh=6000)
        self.assertFalse(quest.manquantes(self._pro(**complet))['reseau'])
        for vide in ('contrat_electricite', 'raccordement',
                     'conso_mensuelle_kwh'):
            lead = self._pro(**dict(complet, **{vide: None}))
            self.assertTrue(quest.manquantes(lead)['reseau'], vide)

    def test_reseau_suit_la_regle_du_devis_automatique(self):
        # CQST1 — « ne sait pas » / « inconnu » ne sont pas des réponses ; une
        # facture en MAD ne compte qu'avec un contrat BT ; un site MT n'a pas
        # de contrat à donner.
        base = dict(tension_raccordement='bt', tension_source='declare',
                    compteur_puissance_kva=60, contrat_electricite='bt_patente',
                    raccordement='triphase', conso_mensuelle_kwh=6000)
        for champ, valeur in (('contrat_electricite', 'ne_sait_pas'),
                              ('raccordement', 'inconnu')):
            lead = self._pro(**dict(base, **{champ: valeur}))
            self.assertTrue(quest.manquantes(lead)['reseau'], champ)
            self.assertFalse(quest.devis_possible(lead), champ)
        mad_sans_contrat = self._pro(**dict(
            base, conso_mensuelle_kwh=None, facture_hiver=5000,
            contrat_electricite='ne_sait_pas'))
        self.assertTrue(quest.manquantes(mad_sans_contrat)['reseau'])
        mad_bt = self._pro(**dict(base, conso_mensuelle_kwh=None,
                                  facture_hiver=5000))
        self.assertFalse(quest.manquantes(mad_bt)['reseau'])
        mt = self._pro(**dict(base, type_installation='industriel',
                              tension_raccordement='mt',
                              contrat_electricite=None))
        self.assertFalse(quest.manquantes(mt)['reseau'])

    def test_post_activite_heures_de_cuisson_gardees_cle_inconnue_ecartee(self):
        # CQST2 — les heures lues par le moteur C&I sont acceptées ; une clé
        # inconnue ne fait plus perdre tout l'objet.
        lead = self._pro(categorie_commerciale='boulangerie')
        lien = QuestionnaireLien.objects.create(
            company=self.company, lead=lead,
            questions={s: s == 'activite' for s in quest.sections_du_lead(lead)})
        res = self.client.post(
            PUBLIC.format(lien.token),
            data=json.dumps({'section': 'activite', 'reponses': {
                'reponses_categorie': {
                    'four': 'electrique', 'cuisson_nocturne': True,
                    'heures_cuisson': [[2, 6]], 'pirate': 1}}}),
            content_type='application/json')
        self.assertEqual(res.status_code, 200, res.content)
        lead.refresh_from_db()
        self.assertEqual(lead.reponses_categorie, {
            'four': 'electrique', 'cuisson_nocturne': True,
            'heures_cuisson': [[2, 6]]})
        self.assertIn('devis_possible', res.json())

    def test_post_reseau_contrat_phase_option_force_motrice_seulement(self):
        lead = self._pro()
        lien = QuestionnaireLien.objects.create(
            company=self.company, lead=lead, questions={'reseau': True})
        res = self.client.post(
            PUBLIC.format(lien.token),
            data=json.dumps({'section': 'reseau', 'reponses': {
                'contrat_electricite': 'bt_patente',
                'option_tarifaire_bt': 'bi_horaire',
                'raccordement': 'triphase'}}),
            content_type='application/json')
        self.assertEqual(res.status_code, 200, res.content)
        lead.refresh_from_db()
        self.assertEqual(lead.contrat_electricite, 'bt_patente')
        self.assertEqual(lead.raccordement, 'triphase')
        self.assertIsNone(lead.option_tarifaire_bt)
        res = self.client.post(
            PUBLIC.format(lien.token),
            data=json.dumps({'section': 'reseau', 'reponses': {
                'contrat_electricite': 'bt_force_motrice',
                'option_tarifaire_bt': 'bi_horaire',
                'raccordement': 'mono'}}),
            content_type='application/json')
        self.assertEqual(res.status_code, 200, res.content)
        lead.refresh_from_db()
        self.assertEqual(lead.option_tarifaire_bt, 'bi_horaire')
        self.assertEqual(lead.raccordement, 'triphase')  # « mono » : refusé

    def test_post_site_pente_et_orientation(self):
        # Fondateur 26/10/2026 — pente en degrés [0 ; 90[, orientation fermée.
        lead = self._pro()
        lien = QuestionnaireLien.objects.create(
            company=self.company, lead=lead, questions={'site': True})
        for reponses in ({'inclinaison_deg': 120, 'orientation': 'nord'},
                         {'inclinaison_deg': 15, 'orientation': 'est'}):
            res = self.client.post(
                PUBLIC.format(lien.token),
                data=json.dumps({'section': 'site', 'reponses': reponses}),
                content_type='application/json')
            self.assertEqual(res.status_code, 200, res.content)
        lead.refresh_from_db()
        self.assertEqual(lead.inclinaison_deg, Decimal('15'))
        self.assertEqual(lead.orientation, 'est')

    def test_post_occupation_pour_un_pro_refuse(self):
        lead = self._pro()
        lien = QuestionnaireLien.objects.create(
            company=self.company, lead=lead, questions={})
        res = self.client.post(
            PUBLIC.format(lien.token),
            data=json.dumps({'section': 'occupation',
                             'reponses': {'occupation_jour': 'present'}}),
            content_type='application/json')
        self.assertEqual(res.status_code, 400, res.content)
        lead.refresh_from_db()
        self.assertIsNone(lead.occupation_jour)

    def test_activite_ne_montre_que_le_segment(self):
        commercial = self._pro()
        industriel = self._pro(type_installation='industriel')
        carte_c = quest.champs_a_poser(commercial, ['activite'])['activite']
        carte_i = quest.champs_a_poser(industriel, ['activite'])['activite']
        self.assertIn('categorie_commerciale', carte_c)
        self.assertNotIn('secteur_industriel', carte_c)
        self.assertIn('secteur_industriel', carte_i)
        self.assertNotIn('categorie_commerciale', carte_i)

    def test_lien_residentiel_identique(self):
        lead = Lead.objects.create(company=self.company, nom='Maison')
        res = self._mint(lead)
        self.assertEqual(res.status_code, 200, res.data)
        self.assertEqual(list(res.data['questions']),
                         list(quest.SECTIONS_HORS_POMPAGE))
        self.assertEqual(sorted(res.data['questions']),
                         sorted(CONTRAT_MINT['exemple']['questions']))

    def test_agricole_inchange(self):
        lead = Lead.objects.create(company=self.company, nom='Ferme',
                                   type_installation='agricole')
        res = self._mint(lead)
        self.assertEqual(sorted(res.data['questions']),
                         sorted(CONTRAT_MINT['exemple_agricole']['questions']))
