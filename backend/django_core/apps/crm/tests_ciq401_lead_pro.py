"""CIQ401 — colonnes PRO du Lead, chacune avec sa question d'appel.

Contrat partagé : ``apps/crm/contract_samples/lead_pro.json`` (CIQ1, PACT10,
bloc ``colonnes_pro``). Chaque colonne existe sur ``crm.Lead`` ; celles qu'on
pose au téléphone portent leur question dans le ``help_text`` (format
« Question à l'appel : « … » »). Les colonnes ``*_source`` sont posées par le
SERVEUR selon le chemin d'écriture, jamais saisies.

Run :
    python manage.py test apps.crm.tests_ciq401_lead_pro -v 2
"""
import json
from decimal import Decimal
from pathlib import Path

from django.contrib.auth import get_user_model
from django.test import SimpleTestCase, TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from authentication.models import Company
from apps.crm import activity, selectors, services
from apps.crm.models import Lead

User = get_user_model()

CONTRAT = json.loads(
    (Path(__file__).resolve().parent / 'contract_samples'
     / 'lead_pro.json').read_text(encoding='utf-8'))

COLONNES = [c['nom'] for c in CONTRAT['colonnes_pro']]

#: Posées par le serveur : aucune question orale.
SOURCES = {
    'tension_source', 'puissance_souscrite_source', 'surface_source',
    'cos_phi_source',
}

#: Les colonnes NOUVELLES de CIQ401 (les ``reutilisee`` existaient déjà).
NOUVELLES = [c['nom'] for c in CONTRAT['colonnes_pro']
             if not c.get('reutilisee')]


def _champ(nom):
    return Lead._meta.get_field(nom)


class ColonnesDuContrat(SimpleTestCase):
    def test_chaque_colonne_du_contrat_existe_sur_le_lead(self):
        for nom in COLONNES:
            self.assertIsNotNone(_champ(nom), nom)

    def test_chaque_colonne_posee_au_telephone_porte_sa_question(self):
        for nom in COLONNES:
            if nom in SOURCES:
                continue
            texte = str(_champ(nom).help_text or '')
            self.assertTrue(texte.startswith("Question à l'appel : « "),
                            f'{nom} : {texte!r}')
            self.assertIn('»', texte, nom)

    def test_les_sources_n_ont_pas_de_question(self):
        for nom in SOURCES:
            self.assertNotIn("Question à l'appel", str(_champ(nom).help_text))

    def test_conso_et_surface_ont_leur_question(self):
        self.assertIn('kWh', str(_champ('conso_mensuelle_kwh').help_text))
        self.assertIn('m²', str(_champ('surface_toiture_m2').help_text))

    def test_le_kva_ne_parle_plus_de_dernier_recours(self):
        texte = str(_champ('compteur_puissance_kva').help_text)
        self.assertNotIn('DERNIER RECOURS', texte.upper())
        self.assertIn('facture ou votre contrat', texte)

    def test_toutes_les_nouvelles_sont_nullables_sans_defaut(self):
        for nom in NOUVELLES:
            self.assertTrue(_champ(nom).null, nom)
            self.assertFalse(_champ(nom).has_default(), nom)

    def test_les_choix_sont_ceux_du_contrat(self):
        for colonne in CONTRAT['colonnes_pro']:
            if colonne['type'] != 'choix' or colonne.get('reutilisee'):
                continue
            valeurs = [v for v, _ in _champ(colonne['nom']).choices]
            self.assertEqual(valeurs,
                             [c for c in colonne['choix'] if c != ''],
                             colonne['nom'])

    def test_financing_intent_gagne_credit_bail(self):
        valeurs = [v for v, _ in _champ('financing_intent').choices]
        self.assertEqual(valeurs, ['cash', 'credit', 'indecis', 'credit_bail'])

    def test_les_cles_de_categorie_sont_celles_du_contrat(self):
        attendu = CONTRAT['reponses_categorie_par_categorie']['cles']
        self.assertEqual(
            {k: list(v) for k, v in Lead.REPONSES_CATEGORIE_CLES.items()},
            attendu)

    def test_le_chatter_journalise_chaque_nouvelle_colonne(self):
        for nom in NOUVELLES:
            self.assertIn(nom, activity.TRACKED_FIELDS, nom)

    def test_la_garde_qjr234_reste_verte(self):
        self.assertEqual(selectors.lead_provenance_omissions(), [])

    def test_la_fusion_connait_les_nouvelles_colonnes(self):
        for nom in NOUVELLES:
            self.assertIn(nom, services._MERGE_FILL_FIELDS, nom)


class SaisieParLApi(TestCase):
    def setUp(self):
        self.company, _ = Company.objects.get_or_create(
            slug='ciq401-co', defaults={'nom': 'CIQ401 Co'})
        self.user = User.objects.create_user(
            username='ciq401_user', password='x', role_legacy='responsable',
            company=self.company)
        self.lead = Lead.objects.create(
            company=self.company, nom='Hôtel CIQ401',
            type_installation='commercial')
        self.api = APIClient()
        self.api.credentials(
            HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(self.user)}')
        self.url = f'/api/django/crm/leads/{self.lead.id}/'

    def _patch(self, body):
        return self.api.patch(self.url, body, format='json')

    CORPS = {
        'societe': 'Hôtel Exemple SARL',
        'tension_raccordement': 'bt',
        'compteur_puissance_kva': '60.00',
        'categorie_commerciale': 'hotel',
        'reponses_categorie': {'chambres': 40, 'piscine': False},
        'regime_equipes': 'continu',
        'jours_ouverture': [1, 2, 3, 4, 5, 6, 7],
        'heure_debut': 0,
        'heure_fin': 24,
        'fermeture_mois': [8],
        'type_surface': 'toiture',
        'type_toiture': 'terrasse_beton',
        'surface_toiture_m2': '650.00',
        'groupe_electrogene': 'oui',
        'groupe_kva': '100.00',
        'pv_existant_kwc': '12.50',
        'cos_phi': '0.850',
        'releve_conso': {
            'mois': [{'mois': '2026-08', 'kwh': '17600.00',
                      'kwh_pointe': None, 'kwh_pleines': None,
                      'kwh_creuses': None, 'puissance_atteinte_kva': None,
                      'cos_phi': None}],
            'source': 'lu_sur_facture'},
        'tva_recuperable': 'oui',
        'ice': '000000000000000',
        'rc': '12345',
        'if_fiscal': '67890',
        'adresse_siege': '1 rue Exemple, Casablanca',
        'fonction_contact': 'Directeur',
        'contact_secondaire_fonction': 'DAF',
        'contact_secondaire_email': 'daf@example.com',
        'financing_intent': 'credit_bail',
        'facture_tranche_declaree': {
            'min_mad': 4000, 'max_mad': None,
            'libelle': 'plus de 4000 dh', 'source': 'meta'},
    }

    def test_patch_puis_get_rend_les_memes_valeurs(self):
        resp = self._patch(self.CORPS)
        self.assertEqual(resp.status_code, 200, resp.data)
        lu = self.api.get(self.url).data
        for cle, valeur in self.CORPS.items():
            self.assertEqual(lu[cle], valeur, cle)

    def test_patch_vide_rend_un_objet_identique_sources_comprises(self):
        self._patch(self.CORPS)
        avant = self.api.get(self.url).data
        resp = self._patch({})
        self.assertEqual(resp.status_code, 200, resp.data)
        apres = self.api.get(self.url).data
        for cle in COLONNES:
            self.assertEqual(apres[cle], avant[cle], cle)
        # Renvoyer tel quel ce que le GET a servi ne change rien non plus.
        renvoi = {cle: avant[cle] for cle in self.CORPS}
        self.assertEqual(self._patch(renvoi).status_code, 200)
        encore = self.api.get(self.url).data
        for cle in COLONNES:
            self.assertEqual(encore[cle], avant[cle], cle)

    def test_valeurs_refusees_en_400_qui_nomme_le_champ(self):
        douze_plus_un = {'mois': [
            {'mois': f'{2025 + (i // 12)}-{(i % 12) + 1:02d}', 'kwh': 10}
            for i in range(13)]}
        cas = (
            ('jours_ouverture', [8]),
            ('jours_ouverture', [1, 1]),
            ('fermeture_mois', [13]),
            ('cos_phi', '1.3'),
            ('cos_phi', '0'),
            ('releve_conso', douze_plus_un),
            ('releve_conso', {'mois': [{'mois': '2026-08', 'kwh': -1}]}),
            ('releve_conso', {'mois': [{'mois': '2026-08', 'kwh': 1},
                                       {'mois': '2026-08', 'kwh': 2}]}),
        )
        for champ, valeur in cas:
            resp = self._patch({champ: valeur})
            self.assertEqual(resp.status_code, 400, (champ, valeur))
            self.assertIn(champ, resp.data, (champ, valeur))

    def test_heure_de_fin_avant_le_debut_refusee(self):
        resp = self._patch({'heure_debut': 18, 'heure_fin': 8})
        self.assertEqual(resp.status_code, 400)
        self.assertIn('heure_fin', resp.data)
        self._patch({'heure_debut': 8})
        resp = self._patch({'heure_fin': 6})
        self.assertEqual(resp.status_code, 400)
        self.assertIn('heure_fin', resp.data)

    def test_reponses_hors_categorie_refusees(self):
        resp = self._patch({'categorie_commerciale': 'bureau',
                            'reponses_categorie': {'chambres': 3}})
        self.assertEqual(resp.status_code, 400)
        self.assertIn('reponses_categorie', resp.data)

    def test_douze_mois_acceptes_avec_registres_mt(self):
        releve = {'mois': [
            {'mois': f'2025-{m:02d}', 'kwh': 40000, 'kwh_pointe': 6000,
             'kwh_pleines': 26000, 'kwh_creuses': 8000,
             'puissance_atteinte_kva': 210}
            for m in range(1, 13)]}
        resp = self._patch({'releve_conso': releve})
        self.assertEqual(resp.status_code, 200, resp.data)
        self.lead.refresh_from_db()
        self.assertEqual(len(self.lead.releve_conso['mois']), 12)
        self.assertEqual(self.lead.releve_conso['source'], 'declare')
        self.assertEqual(self.lead.releve_conso['mois'][0]['kwh_pointe'],
                         '6000.00')

    def test_une_source_ne_se_saisit_pas(self):
        resp = self._patch({'tension_source': 'mesure_visite'})
        self.assertEqual(resp.status_code, 200, resp.data)
        self.lead.refresh_from_db()
        self.assertIsNone(self.lead.tension_source)
        self._patch({'tension_raccordement': 'mt'})
        self._patch({'tension_source': 'mesure_visite'})
        self.lead.refresh_from_db()
        self.assertEqual(self.lead.tension_source, 'declare')

    def test_la_fiche_pose_la_source_declare_et_facture_pour_le_cos_phi(self):
        self._patch({'tension_raccordement': 'mt', 'cos_phi': '0.9',
                     'compteur_puissance_kva': '250',
                     'surface_toiture_m2': '1200'})
        self.lead.refresh_from_db()
        self.assertEqual(self.lead.tension_source, 'declare')
        self.assertEqual(self.lead.cos_phi_source, 'facture')
        self.assertEqual(self.lead.puissance_souscrite_source, 'declare')
        self.assertEqual(self.lead.surface_source, 'declare')

    def test_la_source_ne_change_que_si_la_valeur_change(self):
        Lead.objects.filter(pk=self.lead.pk).update(
            tension_raccordement='mt', tension_source='mesure_visite')
        self._patch({'tension_raccordement': 'mt'})
        self.lead.refresh_from_db()
        self.assertEqual(self.lead.tension_source, 'mesure_visite')

    def test_vider_la_valeur_vide_sa_source(self):
        self._patch({'tension_raccordement': 'bt'})
        self._patch({'tension_raccordement': None})
        self.lead.refresh_from_db()
        self.assertIsNone(self.lead.tension_source)


class FusionConserveLesColonnesPro(TestCase):
    def test_la_fusion_recopie_les_colonnes_vides_du_survivant(self):
        company, _ = Company.objects.get_or_create(
            slug='ciq401-fusion', defaults={'nom': 'CIQ401 Fusion'})
        user = User.objects.create_user(
            username='ciq401_fusion', password='x',
            role_legacy='responsable', company=company)
        survivant = Lead.objects.create(company=company, nom='Survivant')
        absorbe = Lead.objects.create(
            company=company, nom='Absorbé', tension_raccordement='mt',
            tension_source='facture', categorie_commerciale='hotel',
            jours_ouverture=[1, 2, 3], ice='000000000000000',
            cos_phi=Decimal('0.900'), tva_recuperable='oui')
        services.merge_leads(survivant, [absorbe], user)
        survivant.refresh_from_db()
        self.assertEqual(survivant.tension_raccordement, 'mt')
        self.assertEqual(survivant.tension_source, 'facture')
        self.assertEqual(survivant.categorie_commerciale, 'hotel')
        self.assertEqual(survivant.jours_ouverture, [1, 2, 3])
        self.assertEqual(survivant.ice, '000000000000000')
        self.assertEqual(survivant.cos_phi, Decimal('0.900'))
        self.assertEqual(survivant.tva_recuperable, 'oui')
