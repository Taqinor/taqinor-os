"""QJR415 (QJR4-12) — le repli « première Company » devient BRUYANT partout.

CE QUE LE ROUGE PROUVAIT. Trois webhooks portaient le MÊME repli multi-tenant
et un seul portait le garde-fou QXG5 :

    apps/crm/webhooks.py ``_resolve_company``          → garde-fou QXG5 ✔
    apps/crm/webhooks.py ``_meta_lead_ads_company``    → repli MUET ✘
    apps/adsengine/whatsapp_webhook.py ``_resolve_company`` → repli MUET ✘

Retomber silencieusement sur ``Company.objects.order_by('pk').first()`` range
des leads entrants dans la société d'un AUTRE client sans qu'aucun signal ne
soit émis — dans un ERP multi-tenant c'est une fuite de données inter-tenant
doublée d'une perte commerciale, et RIEN ne la signalait.

CORRECTIF : un SEUL motif de repli dans le dépôt
(``crm.webhooks.resoudre_company_avec_repli_bruyant``), les deux variantes
muettes supprimées dans le même commit (règle permanente 2).
"""
from unittest import mock

from django.test import TestCase, override_settings

from authentication.models import Company

from apps.adsengine import whatsapp_webhook as wa
from apps.crm import webhooks


class ReplisBruyantsTests(TestCase):
    """Les DEUX chemins émettent le signal QXG5 sur une base multi-tenant."""

    def setUp(self):
        self.premiere = Company.objects.create(
            nom='QJR415 Première', slug='qjr415-a')
        self.seconde = Company.objects.create(
            nom='QJR415 Seconde', slug='qjr415-b')

    @override_settings(META_LEAD_ADS_COMPANY_ID=None)
    def test_meta_lead_ads_company_crie_avant_de_replier(self):
        """ROUGE avant QJR415 : ce chemin repliait EN SILENCE."""
        with self.assertLogs('apps.crm.webhooks', level='ERROR') as journal:
            company = webhooks._meta_lead_ads_company()
        self.assertEqual(company, self.premiere)
        message = '\n'.join(journal.output)
        self.assertIn('META_LEAD_ADS_COMPANY_ID', message)
        self.assertIn('QXG5', message)

    @override_settings(WHATSAPP_CLOUD_COMPANY_ID=None)
    def test_adsengine_resolve_company_crie_avant_de_replier(self):
        """ROUGE avant QJR415 : ce chemin repliait EN SILENCE."""
        with self.assertLogs('apps.crm.webhooks', level='ERROR') as journal:
            company = wa._resolve_company()
        self.assertEqual(company, self.premiere)
        message = '\n'.join(journal.output)
        self.assertIn('WHATSAPP_CLOUD_COMPANY_ID', message)
        self.assertIn('QXG5', message)

    @override_settings(WEBSITE_LEADS_COMPANY_ID=None)
    def test_le_jumeau_deja_bruyant_est_inchange(self):
        with self.assertLogs('apps.crm.webhooks', level='ERROR') as journal:
            company = webhooks._resolve_company()
        self.assertEqual(company, self.premiere)
        self.assertIn('WEBSITE_LEADS_COMPANY_ID', '\n'.join(journal.output))


class IdentifiantConfigureTests(TestCase):
    """Second test du `Done` : avec l'identifiant posé, rien ne bouge."""

    def setUp(self):
        self.premiere = Company.objects.create(
            nom='QJR415 Conf A', slug='qjr415-conf-a')
        self.seconde = Company.objects.create(
            nom='QJR415 Conf B', slug='qjr415-conf-b')

    def test_meta_lead_ads_company_rend_la_societe_designee_sans_bruit(self):
        with override_settings(META_LEAD_ADS_COMPANY_ID=self.seconde.pk):
            with mock.patch.object(webhooks.logger, 'error') as erreur:
                company = webhooks._meta_lead_ads_company()
        self.assertEqual(company, self.seconde)
        erreur.assert_not_called()

    def test_adsengine_rend_la_societe_designee_sans_bruit(self):
        with override_settings(WHATSAPP_CLOUD_COMPANY_ID=self.seconde.pk):
            with mock.patch.object(webhooks.logger, 'error') as erreur:
                company = wa._resolve_company()
        self.assertEqual(company, self.seconde)
        erreur.assert_not_called()

    def test_un_identifiant_qui_ne_correspond_a_rien_est_signale(self):
        with override_settings(META_LEAD_ADS_COMPANY_ID=999_999):
            with self.assertLogs('apps.crm.webhooks',
                                 level='ERROR') as journal:
                company = webhooks._meta_lead_ads_company()
        self.assertIsNone(company)
        self.assertIn('META_LEAD_ADS_COMPANY_ID', '\n'.join(journal.output))


class SocieteUniqueTests(TestCase):
    """Troisième test du `Done` : une base mono-société ne fait AUCUN bruit."""

    def setUp(self):
        self.seule = Company.objects.create(
            nom='QJR415 Seule', slug='qjr415-seule')

    @override_settings(META_LEAD_ADS_COMPANY_ID=None,
                       WHATSAPP_CLOUD_COMPANY_ID=None,
                       WEBSITE_LEADS_COMPANY_ID=None)
    def test_aucun_des_trois_chemins_ne_crie(self):
        with mock.patch.object(webhooks.logger, 'error') as erreur:
            self.assertEqual(webhooks._meta_lead_ads_company(), self.seule)
            self.assertEqual(wa._resolve_company(), self.seule)
            self.assertEqual(webhooks._resolve_company(), self.seule)
        erreur.assert_not_called()


class MotifUniqueTests(TestCase):
    """Règle permanente 2 : aucune variante muette ne subsiste."""

    def test_les_trois_chemins_appellent_la_meme_primitive(self):
        import ast
        from pathlib import Path

        # …/backend/django_core/apps/crm/webhooks.py → …/backend/django_core
        racine = Path(webhooks.__file__).resolve().parents[2]
        sources = {
            'apps/crm/webhooks.py': ('_resolve_company',
                                     '_meta_lead_ads_company'),
            'apps/adsengine/whatsapp_webhook.py': ('_resolve_company',),
        }
        for chemin, fonctions in sources.items():
            arbre = ast.parse(
                (racine / chemin).read_text(encoding='utf-8'))
            par_nom = {
                noeud.name: noeud for noeud in ast.walk(arbre)
                if isinstance(noeud, ast.FunctionDef)
            }
            for nom in fonctions:
                corps = ast.unparse(par_nom[nom])
                self.assertIn(
                    'resoudre_company_avec_repli_bruyant', corps,
                    '%s:%s n\'utilise pas la primitive partagée'
                    % (chemin, nom))
                self.assertNotIn(
                    "Company.objects.order_by('pk').first()", corps,
                    '%s:%s garde un repli muet' % (chemin, nom))
