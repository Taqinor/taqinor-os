"""NTMKT22 — Centre de préférences self-service public.

Couvre : un contact garde WhatsApp et coupe l'email sans se désinscrire
totalement, le choix est respecté au prochain envoi (``consentement_accorde``
XMKT4 — un seul registre, ``core.ConsentRecord``), un jeton invalide est
rejeté proprement, et un jeton d'une société ne touche jamais une autre.
"""
from django.test import TestCase
from django.urls import reverse

from authentication.models import Company
from core.models import ConsentRecord

from apps.compta import services as compta_services
from apps.marketing import services as mkt_services
from apps.marketing.models import AbonnementListe, ListeDiffusion


class CentrePreferencesTests(TestCase):
    def setUp(self):
        self.co = Company.objects.create(slug='ntmkt22', nom='NTMKT22')
        self.dest = 'client@exemple.ma'
        self.liste = ListeDiffusion.objects.create(
            company=self.co, nom='Newsletter')
        self.token = mkt_services.generer_token_preferences(
            self.co.id, self.dest)

    def _url(self, token=None):
        return reverse('mkt-preferences-publiques',
                       kwargs={'token': token or self.token})

    def test_etat_initial_tout_accorde(self):
        res = self.client.get(self._url())
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertEqual(data['destinataire'], self.dest)
        self.assertEqual(data['canaux'],
                         {'email': True, 'sms': True, 'whatsapp': True})
        self.assertEqual(
            data['listes'], [{'id': self.liste.id, 'nom': 'Newsletter',
                              'abonne': False}])

    def test_couper_email_sans_toucher_whatsapp(self):
        res = self.client.post(
            self._url(), {'canaux': {'email': False}},
            content_type='application/json')
        self.assertEqual(res.status_code, 200)
        canaux = res.json()['canaux']
        self.assertFalse(canaux['email'])
        self.assertTrue(canaux['whatsapp'])
        # Le prochain envoi respecte le choix (XMKT4, même registre).
        self.assertFalse(compta_services.consentement_accorde(
            self.co, self.dest, canal='email'))
        self.assertTrue(compta_services.consentement_accorde(
            self.co, self.dest, canal='whatsapp'))

    def test_le_registre_est_un_journal_jamais_reecrit(self):
        self.client.post(self._url(), {'canaux': {'email': False}},
                         content_type='application/json')
        self.client.post(self._url(), {'canaux': {'email': True}},
                         content_type='application/json')
        entrees = ConsentRecord.objects.filter(
            company=self.co, subject_identifier=self.dest, purpose='email')
        self.assertEqual(entrees.count(), 2)
        self.assertTrue(compta_services.consentement_accorde(
            self.co, self.dest, canal='email'))

    def test_abonnement_liste_bascule(self):
        self.client.post(
            self._url(), {'listes': {str(self.liste.id): True}},
            content_type='application/json')
        abo = AbonnementListe.objects.get(
            liste=self.liste, destinataire=self.dest)
        self.assertEqual(abo.statut, AbonnementListe.Statut.INSCRIT)
        self.assertEqual(abo.company_id, self.co.id)
        self.client.post(
            self._url(), {'listes': {str(self.liste.id): False}},
            content_type='application/json')
        abo.refresh_from_db()
        self.assertEqual(abo.statut, AbonnementListe.Statut.DESINSCRIT)

    def test_token_invalide_rejete_proprement(self):
        for mauvais in ('nimportequoi', self.token + 'x'):
            res = self.client.get(self._url(mauvais))
            self.assertEqual(res.status_code, 400)
            self.assertEqual(res.json()['detail'], 'Lien invalide.')

    def test_jeton_scope_a_sa_societe(self):
        autre = Company.objects.create(slug='ntmkt22b', nom='Autre')
        liste_autre = ListeDiffusion.objects.create(
            company=autre, nom='Liste B')
        self.client.post(
            self._url(), {'listes': {str(liste_autre.id): True}},
            content_type='application/json')
        # La liste d'une AUTRE société n'est jamais adressable par ce jeton.
        self.assertFalse(AbonnementListe.objects.filter(
            liste=liste_autre).exists())
        data = self.client.get(self._url()).json()
        self.assertEqual([le['id'] for le in data['listes']], [self.liste.id])

    def test_lien_preferences_est_resolvable(self):
        chemin = mkt_services.lien_preferences(self.co, self.dest)
        self.assertIn('/marketing/preferences/', chemin)
        token = chemin.rstrip('/').rsplit('/', 1)[-1]
        company, dest = mkt_services.lire_token_preferences(token)
        self.assertEqual((company.id, dest), (self.co.id, self.dest))
