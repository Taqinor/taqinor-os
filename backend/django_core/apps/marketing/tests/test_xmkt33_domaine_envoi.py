"""XMKT33 — Assistant d'authentification du domaine d'envoi (SPF/DKIM/DMARC).

Couvre : la page montre l'état de chaque enregistrement, la vérification
est relançable, l'avertissement apparaît dans le pré-check, no-op réseau en
tests (mock).
"""
from unittest.mock import patch

from django.test import TestCase

from authentication.models import Company

from apps.compta import services
from apps.marketing.models import Campagne, DomaineEnvoi
from apps.parametres.models_company import CompanyProfile


def make_company(slug, nom):
    company, _ = Company.objects.get_or_create(slug=slug, defaults={'nom': nom})
    return company


class DomaineEnvoiTests(TestCase):
    def setUp(self):
        self.co = make_company('xmkt33', 'XMKT33')

    def test_enregistrements_attendus(self):
        attendus = services.enregistrements_dns_attendus('taqinor.ma')
        self.assertEqual(attendus['spf']['type'], 'TXT')
        self.assertEqual(attendus['dkim']['type'], 'CNAME')
        self.assertEqual(attendus['dmarc']['hote'], '_dmarc.taqinor.ma')

    def test_verification_no_op_sans_reseau_par_defaut(self):
        # Sans mock, l'absence de réseau/dnspython ne doit jamais lever
        # d'exception — juste un statut non vérifié.
        domaine_envoi = DomaineEnvoi.objects.create(
            company=self.co, domaine='exemple-inexistant-xmkt33.invalid')
        services.verifier_domaine_envoi(domaine_envoi)
        domaine_envoi.refresh_from_db()
        self.assertFalse(domaine_envoi.spf_verifie)
        self.assertIsNotNone(domaine_envoi.derniere_verification_le)

    @patch('apps.compta.services._lookup_txt')
    @patch('apps.compta.services._lookup_cname')
    def test_verification_relance_avec_mock(self, mock_cname, mock_txt):
        mock_txt.side_effect = lambda hote: (
            ['v=spf1 include:spf.brevo.com ~all'] if 'dmarc' not in hote
            else ['v=DMARC1; p=none;'])
        mock_cname.return_value = ['mail._domainkey.taqinor.ma.brevo.com']
        domaine_envoi = DomaineEnvoi.objects.create(
            company=self.co, domaine='taqinor.ma')
        services.verifier_domaine_envoi(domaine_envoi)
        domaine_envoi.refresh_from_db()
        self.assertTrue(domaine_envoi.spf_verifie)
        self.assertTrue(domaine_envoi.dkim_verifie)
        self.assertTrue(domaine_envoi.dmarc_verifie)
        self.assertTrue(domaine_envoi.authentifie)

    def test_domaine_jamais_enregistre_non_authentifie(self):
        self.assertFalse(
            services.domaine_envoi_authentifie(self.co, 'jamais-vu.ma'))

    def test_precheck_avertit_domaine_non_authentifie(self):
        CompanyProfile.objects.create(
            company=self.co, email='contact@nonauth.ma')
        camp = Campagne.objects.create(
            company=self.co, nom='C', canal=Campagne.Canal.EMAIL,
            corps='/desinscription/token/')
        rapport = services.precheck_sante_campagne(camp)
        self.assertTrue(
            any('non authentifié' in a for a in rapport['avertissements']))

    def test_precheck_pas_avertissement_si_authentifie(self):
        CompanyProfile.objects.create(
            company=self.co, email='contact@auth.ma')
        domaine_envoi = DomaineEnvoi.objects.create(
            company=self.co, domaine='auth.ma',
            spf_verifie=True, dkim_verifie=True, dmarc_verifie=True)
        self.assertTrue(domaine_envoi.authentifie)
        camp = Campagne.objects.create(
            company=self.co, nom='C2', canal=Campagne.Canal.EMAIL,
            corps='/desinscription/token/')
        rapport = services.precheck_sante_campagne(camp)
        self.assertFalse(
            any('non authentifié' in a for a in rapport['avertissements']))

    def test_isolation_multi_tenant(self):
        other = make_company('xmkt33-b', 'XMKT33-B')
        DomaineEnvoi.objects.create(
            company=self.co, domaine='shared.ma',
            spf_verifie=True, dkim_verifie=True, dmarc_verifie=True)
        self.assertFalse(services.domaine_envoi_authentifie(other, 'shared.ma'))
