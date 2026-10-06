"""ADOC63 — Le lien public de signature est construit par UNE fonction
(`services.url_publique_signature`), ABSOLU sur l'origine de l'ERP, et envoyé
à chaque création (mono, multi, lot) et à chaque relance : le destinataire
atteint toujours sa cérémonie (200).

Sources réelles : services GED, `send_mail` sur le backend locmem de Django,
routes publiques réelles ; aucun mock interne.
"""
import re

from django.contrib.auth import get_user_model
from django.core import mail
from django.test import TestCase, override_settings
from django.utils import timezone
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from authentication.models import Company
from apps.ged import services
from apps.ged.models import (
    Cabinet, DemandeSignatureDocument, Document, Folder, ModeleDocument,
    ROLE_SIGNATAIRE,
)

User = get_user_model()

BASE = 'https://erp.exemple.ma'
RE_LIEN = re.compile(r'Lien : (\S+)')


def _liens(message):
    return RE_LIEN.findall(message.body)


@override_settings(
    PUBLIC_BASE_URL=BASE,
    EMAIL_BACKEND='django.core.mail.backends.locmem.EmailBackend')
class LienSignatureBase(TestCase):
    def setUp(self):
        self.co_a, _ = Company.objects.get_or_create(
            slug='adoc63-a', defaults={'nom': 'Adoc63 A'})
        self.admin = User.objects.create_user(
            username='adoc63-admin', password='x', company=self.co_a,
            role_legacy='admin')
        cab = Cabinet.objects.create(company=self.co_a, nom='Admin')
        folder = Folder.objects.create(
            company=self.co_a, cabinet=cab, nom='Contrats')
        self.doc = Document.objects.create(
            company=self.co_a, folder=folder, nom='Contrat ADOC63')
        self.api = APIClient()
        self.api.credentials(
            HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(self.admin)}')
        self.anon = APIClient()


class LienSignatureTests(LienSignatureBase):
    def test_mono_signataire_notifie_avec_lien_absolu(self):
        mail.outbox = []
        resp = self.api.post('/api/django/ged/demandes-signature/', {
            'document': self.doc.pk, 'signataire_nom': 'Client A',
            'signataire_email': 'client@a.ma'}, format='json')
        self.assertEqual(resp.status_code, 201, resp.data)
        demande = DemandeSignatureDocument.objects.get(pk=resp.data['id'])
        attendu = f'{BASE}/ged/signature/{demande.token}/'
        self.assertEqual(len(mail.outbox), 1)
        self.assertEqual(mail.outbox[0].to, ['client@a.ma'])
        self.assertIn(attendu, mail.outbox[0].body)
        # Le serializer expose le même lien absolu (« Copier le lien »)…
        self.assertEqual(resp.data['lien_signature'], attendu)
        # …et la demande rouverte aussi.
        relue = self.api.get(f'/api/django/ged/demandes-signature/{demande.pk}/')
        self.assertEqual(relue.data['lien_signature'], attendu)
        # Le lien mène à la cérémonie (API publique correspondante).
        self.assertEqual(
            self.anon.get(f'/api/django/ged/signature/{demande.token}/')
            .status_code, 200)

    def test_multi_lien_route_signataire_200(self):
        mail.outbox = []
        resp = self.api.post(
            '/api/django/ged/demandes-signature/creer-multi/', {
                'document': self.doc.pk,
                'destinataires': [{'nom': 'Alice', 'email': 'alice@x.ma',
                                   'role': ROLE_SIGNATAIRE}]},
            format='json')
        self.assertEqual(resp.status_code, 201, resp.data)
        demande = DemandeSignatureDocument.objects.get(pk=resp.data['id'])
        alice = demande.signataires.get()
        attendu = f'{BASE}/ged/signataire/{alice.token}/'
        # Un seul mail : celui du destinataire, jamais celui de la demande.
        self.assertEqual(len(mail.outbox), 1)
        liens = _liens(mail.outbox[0])
        self.assertEqual(liens, [attendu])
        self.assertNotIn(demande.token, mail.outbox[0].body)
        self.assertIsNone(resp.data['lien_signature'])
        self.assertEqual(resp.data['signataires'][0]['lien_signature'], attendu)
        self.assertEqual(
            self.anon.get(f'/api/django/ged/signataire/{alice.token}/')
            .status_code, 200)

    def test_relance_meme_lien(self):
        demande = services.creer_demande_multi_signataires(
            self.doc, destinataires=[
                {'nom': 'Alice', 'email': 'alice@x.ma'}],
            company=self.co_a, relance_cadence_jours=2)
        alice = demande.signataires.get()
        alice.notifie_le = timezone.now() - timezone.timedelta(days=3)
        alice.save(update_fields=['notifie_le'])
        mail.outbox = []
        relances = services.relancer_signataires_dus(self.co_a)
        self.assertEqual(len(relances), 1)
        self.assertEqual(len(mail.outbox), 1)
        self.assertEqual(
            _liens(mail.outbox[0]), [f'{BASE}/ged/signataire/{alice.token}/'])

    def test_lot_envoi_signature_notifie(self):
        modele = ModeleDocument.objects.create(
            company=self.co_a, nom='Renouvellement',
            corps_html='<p>Bonjour {{ nom }}.</p>')
        mail.outbox = []
        lot = services.creer_lot_envoi_signature(
            company=self.co_a, modele=modele, destinataires=[
                {'nom': 'Client A', 'email': 'a@x.ma'},
                {'nom': 'Client B', 'email': 'b@x.ma'}],
            created_by=self.admin)
        self.assertEqual(lot.nb_envoyes, 2, lot.resultats)
        destinataires = sorted(m.to[0] for m in mail.outbox)
        self.assertEqual(destinataires, ['a@x.ma', 'b@x.ma'])
        for resultat in lot.resultats:
            demande = DemandeSignatureDocument.objects.get(
                pk=resultat['demande_id'])
            message = next(m for m in mail.outbox
                           if m.to == [resultat['email']])
            self.assertEqual(
                _liens(message), [f'{BASE}/ged/signature/{demande.token}/'])


@override_settings(
    PUBLIC_BASE_URL='',
    EMAIL_BACKEND='django.core.mail.backends.locmem.EmailBackend')
class SansBaseTests(LienSignatureBase):
    def test_sans_base_ni_requete_aucun_lien_relatif(self):
        mail.outbox = []
        with self.assertLogs('apps.ged.services', level='WARNING'):
            services.demander_signature(
                self.doc, signataire_nom='X', signataire_email='x@x.ma',
                company=self.co_a)
        self.assertEqual(len(mail.outbox), 0)

    def test_sans_base_repli_origine_de_la_requete(self):
        mail.outbox = []
        resp = self.api.post('/api/django/ged/demandes-signature/', {
            'document': self.doc.pk, 'signataire_nom': 'Client A',
            'signataire_email': 'client@a.ma'}, format='json')
        self.assertEqual(resp.status_code, 201, resp.data)
        self.assertEqual(len(mail.outbox), 1)
        lien = _liens(mail.outbox[0])[0]
        self.assertTrue(lien.startswith('http://'), lien)
        self.assertTrue(lien.endswith(f"/ged/signature/{resp.data['token']}/"))
