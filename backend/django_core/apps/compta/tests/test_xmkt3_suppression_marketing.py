"""XMKT3 — Désinscription un clic + liste de suppression globale.

Couvre : un clic désinscrit (endpoint public tokenisé), le contact n'est plus
jamais ciblé même après ré-import, l'import de liste d'opposition est
idempotent, un jeton invalide échoue proprement, isolation multi-tenant.
"""
from django.contrib.auth import get_user_model
from django.test import TestCase

from authentication.models import Company

from apps.compta import services
from apps.compta.models import Campagne, EnvoiCampagne, SuppressionMarketing

User = get_user_model()


def make_company(slug, nom):
    company, _ = Company.objects.get_or_create(slug=slug, defaults={'nom': nom})
    return company


class SuppressionMarketingTests(TestCase):
    def setUp(self):
        self.co = make_company('xmkt3', 'XMKT3')

    def test_supprimer_destinataire_idempotent(self):
        services.supprimer_destinataire(self.co, 'a@x.ma')
        services.supprimer_destinataire(self.co, 'a@x.ma')
        self.assertEqual(
            SuppressionMarketing.objects.filter(
                company=self.co, destinataire='a@x.ma').count(), 1)

    def test_est_supprime(self):
        self.assertFalse(services.est_supprime(self.co, 'a@x.ma'))
        services.supprimer_destinataire(self.co, 'a@x.ma')
        self.assertTrue(services.est_supprime(self.co, 'a@x.ma'))

    def test_envoi_filtre_les_supprimes(self):
        services.supprimer_destinataire(self.co, 'blocked@x.ma')
        camp = Campagne.objects.create(
            company=self.co, nom='C', canal=Campagne.Canal.EMAIL)
        services.envoyer_campagne(
            camp, destinataires=['ok@x.ma', 'blocked@x.ma'])
        camp.refresh_from_db()
        self.assertEqual(camp.nb_destinataires, 1)
        self.assertFalse(
            EnvoiCampagne.objects.filter(
                campagne=camp, destinataire='blocked@x.ma').exists())
        self.assertTrue(
            EnvoiCampagne.objects.filter(
                campagne=camp, destinataire='ok@x.ma').exists())

    def test_immune_au_reimport(self):
        services.supprimer_destinataire(self.co, 'a@x.ma')
        # Ré-import : ne doit jamais écraser la suppression existante.
        services.importer_liste_opposition(self.co, ['a@x.ma', 'b@x.ma'])
        supp = SuppressionMarketing.objects.get(
            company=self.co, destinataire='a@x.ma')
        self.assertEqual(supp.motif, SuppressionMarketing.Motif.DESINSCRIT)

    def test_import_liste_opposition_idempotent(self):
        ajoutes1 = services.importer_liste_opposition(
            self.co, ['a@x.ma', 'b@x.ma'])
        ajoutes2 = services.importer_liste_opposition(
            self.co, ['a@x.ma', 'b@x.ma', 'c@x.ma'])
        self.assertEqual(ajoutes1, 2)
        self.assertEqual(ajoutes2, 1)
        self.assertEqual(
            SuppressionMarketing.objects.filter(company=self.co).count(), 3)

    def test_token_desinscription_endpoint_supprime(self):
        token = services.generer_token_desinscription(self.co.id, 'a@x.ma')
        client_public = self.client
        resp = client_public.post(
            f'/api/django/compta/desinscription/{token}/')
        self.assertEqual(resp.status_code, 200, resp.content)
        self.assertTrue(services.est_supprime(self.co, 'a@x.ma'))

    def test_token_invalide_ne_supprime_rien(self):
        resp = self.client.post(
            '/api/django/compta/desinscription/token-invalide/')
        self.assertEqual(resp.status_code, 400)
        self.assertEqual(SuppressionMarketing.objects.count(), 0)

    def test_isolation_multi_tenant(self):
        other = make_company('xmkt3-b', 'XMKT3-B')
        services.supprimer_destinataire(self.co, 'shared@x.ma')
        self.assertFalse(services.est_supprime(other, 'shared@x.ma'))
