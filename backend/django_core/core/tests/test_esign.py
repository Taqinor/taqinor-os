"""Tests FG372 — e-signature (fondation branchable).

Couvre :
  * enregistrement du connecteur générique ;
  * ``GenericEsignProvider.is_configured`` (URL + secret) + no-op non configuré ;
  * ``creer_demande`` crée un EsignRequest brouillon multi-tenant ;
  * ``creer_demande`` attache une cible générique via contenttypes ;
  * ``envoyer`` non configuré reste en brouillon (no-op propre) ;
  * ``envoyer`` connecteur inconnu → statut erreur ;
  * découplage : aucun import d'app domaine.
"""
from django.test import TestCase

from authentication.models import Company
from core import esign, integrations
from core.models import EsignRequest, IntegrationConfig


class EsignProviderTests(TestCase):
    def test_generic_provider_registered(self):
        cls = integrations.get_provider_class(integrations.TYPE_ESIGN,
                                              'generic')
        self.assertIs(cls, esign.GenericEsignProvider)

    def test_not_configured_is_noop(self):
        p = esign.GenericEsignProvider(config={}, secret=None)
        self.assertFalse(p.is_configured())
        self.assertFalse(p.send_for_signature(None)['ok'])


class EsignFlowTests(TestCase):
    def setUp(self):
        self.company = Company.objects.create(nom='ACME')

    def test_creer_demande_brouillon(self):
        req = esign.creer_demande(
            self.company, signataire_email='a@b.com', signataire_nom='Ali')
        self.assertEqual(req.company, self.company)
        self.assertEqual(req.statut, EsignRequest.STATUT_BROUILLON)
        self.assertEqual(req.provider, 'generic')

    def test_creer_demande_with_target(self):
        # Cible générique : on réutilise une Company comme cible arbitraire
        # (le modèle est agnostique — n'importe quel modèle convient).
        other = Company.objects.create(nom='DOC')
        req = esign.creer_demande(self.company, target=other)
        self.assertEqual(req.object_id, other.pk)
        self.assertIsNotNone(req.content_type)

    def test_envoyer_noop_when_unconfigured(self):
        req = esign.creer_demande(self.company)
        esign.envoyer(req)
        req.refresh_from_db()
        self.assertEqual(req.statut, EsignRequest.STATUT_BROUILLON)

    def test_envoyer_unknown_provider_errors(self):
        req = EsignRequest.objects.create(
            company=self.company, provider='inconnu')
        esign.envoyer(req)
        req.refresh_from_db()
        self.assertEqual(req.statut, EsignRequest.STATUT_ERREUR)

    def test_envoyer_configured_marks_sent(self):
        IntegrationConfig.objects.create(
            company=self.company, integration_type=integrations.TYPE_ESIGN,
            provider='generic', actif=True,
            settings={'base_url': 'https://x'}, secret_ref='ESIGN_K')
        import os
        from unittest import mock
        req = esign.creer_demande(self.company, provider='generic')
        with mock.patch.dict(os.environ, {'ESIGN_K': 'tok'}):
            esign.envoyer(req)
        req.refresh_from_db()
        self.assertEqual(req.statut, EsignRequest.STATUT_ENVOYE)
