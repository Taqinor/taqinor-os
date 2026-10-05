"""AGR401 — ``pompe_cv`` scindé : la pompe ACTUELLE n'est plus jamais la pompe
du devis.

Le CV envoyé par le site (``pompeCvActuelle``) décrit la pompe EXISTANTE : il
atterrit dans ``Lead.pompe_actuelle_cv`` (information) et ne remplit JAMAIS une
entrée de dimensionnement (HMT, débit, besoin). Le détail du lead sert encore
``pompe_cv`` en ALIAS lecture seule déprécié (même valeur) jusqu'à AGR424.

Run :
    python manage.py test apps.crm.tests_agr401_pompe_actuelle_cv -v 2
"""
import json
from decimal import Decimal
from pathlib import Path

from django.contrib.auth import get_user_model
from django.test import SimpleTestCase, TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from authentication.models import Company
from apps.crm import activity, devis_auto, panneau_appel, selectors, webhooks
from apps.crm.models import Lead, LeadActivity, SiteProfile

User = get_user_model()

CONTRAT_POMPAGE = json.loads(
    (Path(__file__).resolve().parent / 'contract_samples'
     / 'lead_pompage.json').read_text(encoding='utf-8'))

#: Entrées de dimensionnement que le CV actuel ne doit JAMAIS remplir.
ENTREES_DIMENSIONNEMENT = (
    'pompe_hmt_m', 'pompe_debit_m3h', 'besoin_eau_m3j', 'niveau_statique_m',
    'debit_forage_m3h', 'pompe_actuelle_debit_m3h',
)


class LeCvDuSiteEstLaPompeActuelle(SimpleTestCase):
    def test_pompe_cv_actuelle_remplit_pompe_actuelle_cv_seulement(self):
        fields = webhooks._map_payload_to_fields(
            {'mode': 'agricole', 'pompeCvActuelle': 3})
        self.assertEqual(fields.get('pompe_actuelle_cv'), 3)
        for entree in ENTREES_DIMENSIONNEMENT:
            self.assertNotIn(entree, fields, entree)
        self.assertNotIn('pompe_cv', fields)

    def test_la_colonne_porte_sa_question_et_son_libelle(self):
        champ = Lead._meta.get_field('pompe_actuelle_cv')
        self.assertEqual(champ.verbose_name, 'Pompe actuelle (CV)')
        self.assertTrue(str(champ.help_text).startswith(
            "Question à l'appel : « Votre pompe actuelle fait combien"))
        self.assertIsNotNone(SiteProfile._meta.get_field('pompe_actuelle_cv'))

    def test_l_ancienne_colonne_n_existe_plus(self):
        noms = {f.name for f in Lead._meta.get_fields()}
        self.assertNotIn('pompe_cv', noms)
        self.assertNotIn(
            'pompe_cv', {f.name for f in SiteProfile._meta.get_fields()})

    def test_le_cv_actuel_n_est_dans_aucun_groupe_du_devis_auto(self):
        for groupe in devis_auto.champs_requis(
                Lead(nom='F', type_installation='agricole')):
            self.assertNotIn('pompe_actuelle_cv', groupe)

    def test_appelants_renommes(self):
        # AGR407 — la CV de la pompe actuelle sort de l'appel : elle se
        # relève sur la PLAQUE, en visite (re-pin de l'assertion AGR401).
        self.assertNotIn('pompe_actuelle_cv',
                         panneau_appel.CHAMPS_ORAUX_AGRICOLE)
        self.assertIn('pompe_actuelle_cv', activity.TRACKED_FIELDS)
        self.assertNotIn('pompe_cv', activity.TRACKED_FIELDS)
        # L'ancienne clé ne sert plus qu'à RELIRE l'historique.
        self.assertEqual(activity.LIBELLES_HISTORIQUES['pompe_cv'],
                         'Pompe (CV)')
        self.assertIn('pompe_actuelle_cv', selectors.SITE_PROFILE_FIELDS)
        self.assertIn('pompe_actuelle_cv', selectors.LEAD_PROVENANCE_FIELDS)
        self.assertEqual(selectors.lead_provenance_omissions(), [])

    def test_contrat_lead_pompage_respecte(self):
        colonne = next(c for c in CONTRAT_POMPAGE['colonnes']
                       if c['nom'] == 'pompe_actuelle_cv')
        self.assertEqual(colonne['type'], 'décimal')
        self.assertEqual(Lead._meta.get_field('pompe_actuelle_cv')
                         .get_internal_type(), 'DecimalField')


class AliasDepreciePompeCv(TestCase):
    def setUp(self):
        self.company, _ = Company.objects.get_or_create(
            slug='agr401-co', defaults={'nom': 'AGR401 Co'})
        self.user = User.objects.create_user(
            username='agr401_user', password='x', role_legacy='responsable',
            company=self.company)
        self.api = APIClient()
        self.api.credentials(
            HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(self.user)}')
        self.lead = Lead.objects.create(
            company=self.company, nom='Ferme', type_installation='agricole',
            pompe_actuelle_cv=Decimal('7.50'))
        self.url = f'/api/django/crm/leads/{self.lead.id}/'

    def test_le_detail_sert_l_alias_egal_a_la_colonne(self):
        data = self.api.get(self.url).data
        self.assertEqual(data['pompe_actuelle_cv'], '7.50')
        self.assertEqual(data['pompe_cv'], data['pompe_actuelle_cv'])

    def test_l_alias_est_en_lecture_seule(self):
        resp = self.api.patch(self.url, {'pompe_cv': '12'}, format='json')
        self.assertEqual(resp.status_code, 200, resp.data)
        self.lead.refresh_from_db()
        self.assertEqual(self.lead.pompe_actuelle_cv, Decimal('7.50'))

    def test_la_colonne_se_saisit_et_se_journalise(self):
        resp = self.api.patch(
            self.url, {'pompe_actuelle_cv': '10'}, format='json')
        self.assertEqual(resp.status_code, 200, resp.data)
        self.lead.refresh_from_db()
        self.assertEqual(self.lead.pompe_actuelle_cv, Decimal('10'))
        self.assertTrue(LeadActivity.objects.filter(
            lead=self.lead,
            field='pompe_actuelle_cv',
            field_label='Pompe actuelle (CV)').exists())
