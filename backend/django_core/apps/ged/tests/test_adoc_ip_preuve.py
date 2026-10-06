"""ADOC66 — Toute IP de preuve, de détection et de journal GED est lue par
`core.throttling.ip_de_requete` (dernier saut de confiance) : l'IP enregistrée
à la signature est celle du signataire, jamais celle du conteneur nginx.

Sources réelles : vues publiques GED, primitive `ip_de_requete`, détecteur
NTDOC9 et `JournalAcces` réels ; aucun mock.
"""
from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.test import TestCase, override_settings
from rest_framework.test import APIClient

from authentication.models import Company
from apps.ged import services
from apps.ged.models import (
    ACCES_TENTATIVE_KO, Cabinet, Document, Folder, JournalAcces,
)

User = get_user_model()

NGINX = '172.18.0.5'
CLIENT = '41.77.1.5'


def _societe_avec_document(slug):
    company, _ = Company.objects.get_or_create(slug=slug, defaults={'nom': slug})
    admin = User.objects.create_user(
        username=f'{slug}-admin', password='x', company=company,
        role_legacy='admin')
    cab = Cabinet.objects.create(company=company, nom='Admin')
    folder = Folder.objects.create(company=company, cabinet=cab, nom='D')
    doc = Document.objects.create(company=company, folder=folder, nom='Doc')
    return company, admin, doc


@override_settings(NUM_PROXIES=1)
class IpPreuveTests(TestCase):
    def setUp(self):
        cache.clear()
        self.addCleanup(cache.clear)
        self.co_a, self.admin, self.doc = _societe_avec_document('adoc66-a')
        self.anon = APIClient()

    def _post(self, url, corps, xff=CLIENT):
        return self.anon.post(
            url, corps, format='json', REMOTE_ADDR=NGINX,
            HTTP_X_FORWARDED_FOR=xff)

    def test_ip_signature_mono_dernier_saut(self):
        demande = services.demander_signature(
            self.doc, signataire_nom='A', signataire_email='a@x.ma',
            company=self.co_a)
        resp = self._post(f'/api/django/ged/signature/{demande.token}/', {
            'action': 'signer', 'consentement': True,
            'signature_texte': 'A'})
        self.assertEqual(resp.status_code, 200, resp.data)
        demande.refresh_from_db()
        self.assertEqual(demande.adresse_ip, CLIENT)

    def test_ip_signature_multi(self):
        demande = services.creer_demande_multi_signataires(
            self.doc, destinataires=[{'nom': 'A', 'email': 'a@x.ma'}],
            company=self.co_a)
        signataire = demande.signataires.get()
        resp = self._post(
            f'/api/django/ged/signataire/{signataire.token}/', {
                'action': 'signer', 'consentement': True,
                'signature_texte': 'A'})
        self.assertEqual(resp.status_code, 200, resp.data)
        signataire.refresh_from_db()
        self.assertEqual(signataire.adresse_ip, CLIENT)

    def test_journal_acces_ip_client(self):
        demande = services.demander_signature(
            self.doc, signataire_nom='A', signataire_email='a@x.ma',
            company=self.co_a)
        # Signature sans consentement : échec tracé au JournalAcces.
        resp = self._post(f'/api/django/ged/signature/{demande.token}/', {
            'action': 'signer'})
        self.assertEqual(resp.status_code, 400)
        trace = JournalAcces.objects.filter(
            document=self.doc, type_acces=ACCES_TENTATIVE_KO).get()
        self.assertEqual(trace.adresse_ip, CLIENT)

    def test_detecteur_sans_fausse_alerte_derriere_proxy(self):
        from apps.notifications.models import Notification
        societes = [(self.co_a, self.doc)] + [
            _societe_avec_document(slug)[::2]
            for slug in ('adoc66-b', 'adoc66-c')]
        for i, (company, doc) in enumerate(societes):
            demande = services.demander_signature(
                doc, signataire_nom='S', signataire_email='s@x.ma',
                company=company)
            # Trois signataires légitimes, trois IP réelles, MÊME proxy nginx.
            resp = self.anon.get(
                f'/api/django/ged/signature/{demande.token}/',
                REMOTE_ADDR=NGINX, HTTP_X_FORWARDED_FOR=f'41.77.1.{10 + i}')
            self.assertEqual(resp.status_code, 200)
        self.assertFalse(Notification.objects.filter(
            event_type='security_alert').exists())
