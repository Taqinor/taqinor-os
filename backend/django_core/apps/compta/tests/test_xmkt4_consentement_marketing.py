"""XMKT4 — Application du consentement marketing par canal + double opt-in
+ listes d'opposition (loi 09-08/CNDP).

Couvre : envoi refusé (et journalisé) sans consentement canal via le
ConsentRecord existant, double opt-in fonctionnel derrière un toggle société
OFF par défaut, import d'opposition idempotent (réutilise XMKT3), n° CNDP
rendu dans le footer, tests.
"""
from django.contrib.auth import get_user_model
from django.test import TestCase

from authentication.models import Company
from core.models import ConsentRecord

from apps.compta import services
from apps.compta.models import Campagne, EnvoiCampagne
from apps.parametres.models_company import CompanyProfile

User = get_user_model()


def make_company(slug, nom):
    company, _ = Company.objects.get_or_create(slug=slug, defaults={'nom': nom})
    return company


class ConsentementMarketingTests(TestCase):
    def setUp(self):
        self.co = make_company('xmkt4', 'XMKT4')

    def test_sans_consentement_enregistre_comportement_historique(self):
        # Aucune entrée ConsentRecord pour ce destinataire → comportement
        # historique préservé (ciblable).
        self.assertTrue(
            services.consentement_accorde(self.co, 'a@x.ma', canal='email'))

    def test_consentement_refuse_bloque_envoi(self):
        ConsentRecord.objects.create(
            company=self.co, subject_identifier='refuse@x.ma',
            purpose='email', granted=False)
        camp = Campagne.objects.create(
            company=self.co, nom='C', canal=Campagne.Canal.EMAIL)
        services.envoyer_campagne(camp, destinataires=['ok@x.ma', 'refuse@x.ma'])
        camp.refresh_from_db()
        self.assertEqual(camp.nb_destinataires, 1)
        envoi_refuse = EnvoiCampagne.objects.get(
            campagne=camp, destinataire='refuse@x.ma')
        self.assertEqual(
            envoi_refuse.raison_smtp, 'consentement_refuse_ou_absent')
        self.assertTrue(
            EnvoiCampagne.objects.filter(
                campagne=camp, destinataire='ok@x.ma').exists())

    def test_consentement_accorde_autorise_envoi(self):
        ConsentRecord.objects.create(
            company=self.co, subject_identifier='ok2@x.ma',
            purpose='email', granted=True)
        camp = Campagne.objects.create(
            company=self.co, nom='C2', canal=Campagne.Canal.EMAIL)
        services.envoyer_campagne(camp, destinataires=['ok2@x.ma'])
        camp.refresh_from_db()
        self.assertEqual(camp.nb_destinataires, 1)

    def test_double_optin_off_par_defaut(self):
        self.assertFalse(services.double_optin_actif(self.co))

    def test_double_optin_toggle_active(self):
        CompanyProfile.objects.create(company=self.co, double_optin_actif=True)
        self.assertTrue(services.double_optin_actif(self.co))

    def test_confirmer_double_optin_pose_consentement(self):
        token = services.generer_token_double_optin(
            self.co.id, 'confirme@x.ma', version_texte='v1-2026-07')
        ok, resultat = services.confirmer_double_optin_via_token(token)
        self.assertTrue(ok)
        self.assertEqual(resultat, 'confirme@x.ma')
        record = ConsentRecord.objects.get(
            company=self.co, subject_identifier='confirme@x.ma',
            purpose='marketing')
        self.assertTrue(record.granted)
        self.assertEqual(record.version_texte, 'v1-2026-07')

    def test_confirmer_double_optin_token_invalide(self):
        ok, msg = services.confirmer_double_optin_via_token('bad-token')
        self.assertFalse(ok)
        self.assertEqual(
            ConsentRecord.objects.filter(company=self.co).count(), 0)

    def test_double_optin_endpoint_public(self):
        token = services.generer_token_double_optin(self.co.id, 'pub@x.ma')
        resp = self.client.post(f'/api/django/compta/double-optin/{token}/')
        self.assertEqual(resp.status_code, 200, resp.content)
        self.assertTrue(
            ConsentRecord.objects.filter(
                company=self.co, subject_identifier='pub@x.ma',
                granted=True).exists())

    def test_double_optin_endpoint_token_invalide(self):
        resp = self.client.post('/api/django/compta/double-optin/invalide/')
        self.assertEqual(resp.status_code, 400)

    def test_cndp_footer_vide_par_defaut(self):
        self.assertEqual(services.cndp_footer_texte(self.co), '')

    def test_cndp_footer_rendu_si_renseigne(self):
        CompanyProfile.objects.create(
            company=self.co, numero_declaration_cndp='D-GEN-2026-123')
        footer = services.cndp_footer_texte(self.co)
        self.assertIn('D-GEN-2026-123', footer)

    def test_import_opposition_idempotent_reutilise_xmkt3(self):
        ajoutes1 = services.importer_liste_opposition(self.co, ['z@x.ma'])
        ajoutes2 = services.importer_liste_opposition(self.co, ['z@x.ma'])
        self.assertEqual(ajoutes1, 1)
        self.assertEqual(ajoutes2, 0)

    def test_isolation_multi_tenant(self):
        other = make_company('xmkt4-b', 'XMKT4-B')
        ConsentRecord.objects.create(
            company=self.co, subject_identifier='shared@x.ma',
            purpose='email', granted=False)
        # L'autre société n'a aucune entrée → comportement historique (True).
        self.assertTrue(
            services.consentement_accorde(other, 'shared@x.ma', canal='email'))
