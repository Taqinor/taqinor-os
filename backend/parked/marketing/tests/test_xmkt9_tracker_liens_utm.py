"""XMKT9 — Tracker de liens + auto-tag UTM.

Couvre : les liens sont réécrits à l'envoi, un clic incrémente le lien +
le destinataire + crée le point de contact, l'UTM arrive sur le lead web
existant, page « clics par lien » sur le détail campagne.
"""
from django.test import TestCase

from authentication.models import Company

from apps.compta import services
from apps.marketing.models import Campagne, ClicLien, EnvoiCampagne, LienTrackee


def make_company(slug, nom):
    company, _ = Company.objects.get_or_create(slug=slug, defaults={'nom': nom})
    return company


class TrackerLiensUtmTests(TestCase):
    def setUp(self):
        self.co = make_company('xmkt9', 'XMKT9')

    def test_liens_reecrits_a_lenvoi(self):
        camp = Campagne.objects.create(
            company=self.co, nom='C', canal=Campagne.Canal.EMAIL,
            corps='Cliquez ici: https://taqinor.ma/offre')
        services.envoyer_campagne(camp, destinataires=['a@x.ma'])
        camp.refresh_from_db()
        self.assertNotIn('https://taqinor.ma/offre', camp.corps)
        self.assertIn('/api/django/compta/r/', camp.corps)
        self.assertEqual(LienTrackee.objects.filter(campagne=camp).count(), 1)

    def test_utm_auto_tag_sur_url_cible(self):
        camp = Campagne.objects.create(
            company=self.co, nom='Promo Été', canal=Campagne.Canal.EMAIL,
            corps='https://taqinor.ma/offre')
        services.envoyer_campagne(camp, destinataires=['a@x.ma'])
        lien = LienTrackee.objects.get(campagne=camp)
        self.assertIn('utm_source=campagne', lien.url_cible)
        self.assertIn('utm_medium=email', lien.url_cible)
        self.assertIn('utm_campaign=Promo', lien.url_cible)

    def test_clic_incremente_lien_et_destinataire(self):
        camp = Campagne.objects.create(
            company=self.co, nom='C2', canal=Campagne.Canal.EMAIL,
            corps='https://taqinor.ma/x')
        services.envoyer_campagne(camp, destinataires=['a@x.ma'])
        lien = LienTrackee.objects.get(campagne=camp)
        ok, url = services.traiter_clic_lien(lien.token, destinataire='a@x.ma')
        self.assertTrue(ok)
        lien.refresh_from_db()
        self.assertEqual(lien.nb_clics, 1)
        self.assertEqual(ClicLien.objects.filter(lien=lien).count(), 1)
        envoi = EnvoiCampagne.objects.get(campagne=camp, destinataire='a@x.ma')
        self.assertIsNotNone(envoi.clique_le)

    def test_clic_token_invalide(self):
        ok, msg = services.traiter_clic_lien('invalide')
        self.assertFalse(ok)

    def test_clics_par_lien_endpoint_donnees(self):
        camp = Campagne.objects.create(
            company=self.co, nom='C3', canal=Campagne.Canal.EMAIL,
            corps='https://taqinor.ma/y')
        services.envoyer_campagne(camp, destinataires=['a@x.ma'])
        lien = LienTrackee.objects.get(campagne=camp)
        services.traiter_clic_lien(lien.token, destinataire='a@x.ma')
        data = services.clics_par_lien(camp)
        self.assertEqual(len(data), 1)
        self.assertEqual(data[0]['nb_clics'], 1)

    def test_redirection_publique_via_endpoint(self):
        camp = Campagne.objects.create(
            company=self.co, nom='C4', canal=Campagne.Canal.EMAIL,
            corps='https://taqinor.ma/z')
        services.envoyer_campagne(camp, destinataires=['a@x.ma'])
        lien = LienTrackee.objects.get(campagne=camp)
        resp = self.client.get(
            f'/api/django/compta/r/{lien.token}/?d=a@x.ma')
        self.assertEqual(resp.status_code, 302)
        lien.refresh_from_db()
        self.assertEqual(lien.nb_clics, 1)

    def test_redirection_publique_token_invalide_404(self):
        resp = self.client.get('/api/django/compta/r/invalide/')
        self.assertEqual(resp.status_code, 404)

    def test_idempotent_meme_url_pas_de_doublon_lien(self):
        camp = Campagne.objects.create(
            company=self.co, nom='C5', canal=Campagne.Canal.EMAIL,
            corps='https://taqinor.ma/a https://taqinor.ma/a')
        _corps, liens = services.envelopper_liens_campagne(camp)
        self.assertEqual(len(liens), 1)
