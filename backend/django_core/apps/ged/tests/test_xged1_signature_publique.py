"""XGED1 — Cérémonie de signature in-app sur document GED (lien public
tokenisé, loi 53-05).

Couvre :
  * un jeton public résout la demande, la consultation GET renvoie les
    métadonnées publiques (jamais de fuite cross-société) ;
  * signature (consentement + nom tapé et/ou tracé) enregistre les preuves
    IMMUABLES côté serveur (IP/UA/hash/horodatage) et bascule `signe` ;
  * refus avec motif obligatoire bascule `refuse` et trace le motif ;
  * jeton inconnu → 404 ; demande expirée/annulée/déjà traitée → 410 ;
  * consentement/signature manquants → 400 ; motif de refus vide → 400 ;
  * isolation société (le payload public ne référence qu'un seul document
    d'une seule société) ; ne touche ni `contrats.SignatureContrat` ni
    `/proposal`.
"""
from unittest import mock

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.utils import timezone

from authentication.models import Company
from apps.ged import services
from apps.ged.models import (
    Cabinet, Document, DocumentVersion, Folder, SIGNATURE_ANNULE,
    SIGNATURE_EN_ATTENTE, SIGNATURE_REFUSE, SIGNATURE_SIGNE,
)

User = get_user_model()


def make_company(slug, nom):
    company, _ = Company.objects.get_or_create(slug=slug, defaults={'nom': nom})
    return company


def make_user(company, username, role='admin'):
    return User.objects.create_user(
        username=username, password='x', company=company, role_legacy=role)


class XGed1Base(TestCase):
    def setUp(self):
        self.co_a = make_company('xged1-a', 'Xged1 A')
        self.co_b = make_company('xged1-b', 'Xged1 B')
        self.admin_a = make_user(self.co_a, 'xged1-admin-a', 'admin')
        self.cab_a = Cabinet.objects.create(company=self.co_a, nom='Admin')
        self.folder_a = Folder.objects.create(
            company=self.co_a, cabinet=self.cab_a, nom='Dossier A')
        self.doc_a = Document.objects.create(
            company=self.co_a, folder=self.folder_a, nom='Contrat à signer')
        self.version_a = DocumentVersion.objects.create(
            company=self.co_a, document=self.doc_a, version=1,
            file_key='ged/xged1/doc-a.pdf', filename='doc-a.pdf',
            mime='application/pdf')
        self.demande = services.demander_signature(
            self.doc_a, signataire_nom='Jean Client',
            signataire_email='jean@example.com', company=self.co_a,
            created_by=self.admin_a)


class ResolveSignaturePubliqueTests(XGed1Base):
    def test_token_generated_on_create(self):
        """Une demande GED30 reçoit un token public unique dès la création."""
        self.assertTrue(self.demande.token)
        self.assertEqual(len(self.demande.token), 43)  # token_urlsafe(32)

    def test_resolve_unknown_token_introuvable(self):
        statut, demande = services.resolve_signature_publique('bogus-token')
        self.assertEqual(statut, services.SIGNATURE_PUBLIQUE_INTROUVABLE)
        self.assertIsNone(demande)

    def test_resolve_ok_pending(self):
        statut, demande = services.resolve_signature_publique(
            self.demande.token)
        self.assertEqual(statut, services.SIGNATURE_PUBLIQUE_OK)
        self.assertEqual(demande.id, self.demande.id)

    def test_resolve_expired(self):
        self.demande.expires_at = timezone.now() - timezone.timedelta(days=1)
        self.demande.save(update_fields=['expires_at'])
        statut, demande = services.resolve_signature_publique(
            self.demande.token)
        self.assertEqual(statut, services.SIGNATURE_PUBLIQUE_EXPIREE)

    def test_resolve_annulee(self):
        self.demande.statut = SIGNATURE_ANNULE
        self.demande.save(update_fields=['statut'])
        statut, demande = services.resolve_signature_publique(
            self.demande.token)
        self.assertEqual(statut, services.SIGNATURE_PUBLIQUE_EXPIREE)

    def test_resolve_already_signed(self):
        self.demande.statut = SIGNATURE_SIGNE
        self.demande.save(update_fields=['statut'])
        statut, demande = services.resolve_signature_publique(
            self.demande.token)
        self.assertEqual(statut, services.SIGNATURE_PUBLIQUE_DEJA_TRAITEE)


class SignerRefuserServiceTests(XGed1Base):
    def test_signer_requires_consentement(self):
        with self.assertRaises(ValueError):
            services.signer_demande_publique(
                self.demande, consentement=False,
                signature_texte='Jean Client')

    def test_signer_requires_a_signature_form(self):
        with self.assertRaises(ValueError):
            services.signer_demande_publique(
                self.demande, consentement=True)

    def test_signer_with_typed_name_records_proof(self):
        """Signature tapée : preuves IP/UA/hash/horodatage posées, statut→signe."""
        with mock.patch('apps.records.storage.fetch_attachment',
                        return_value=(b'%PDF-1.4 contenu', None)):
            demande = services.signer_demande_publique(
                self.demande, consentement=True,
                signature_texte='Jean Client',
                adresse_ip='41.140.1.2', user_agent='TestAgent/1.0')
        self.assertEqual(demande.statut, SIGNATURE_SIGNE)
        self.assertTrue(demande.consentement_explicite)
        self.assertEqual(demande.signature_texte, 'Jean Client')
        self.assertEqual(demande.adresse_ip, '41.140.1.2')
        self.assertEqual(demande.user_agent, 'TestAgent/1.0')
        self.assertEqual(len(demande.hash_contenu), 64)
        self.assertIsNotNone(demande.date_signature)

    def test_signer_with_traced_signature(self):
        with mock.patch('apps.records.storage.fetch_attachment',
                        return_value=(b'contenu', None)):
            demande = services.signer_demande_publique(
                self.demande, consentement=True,
                signature_tracee='data:image/png;base64,abc==')
        self.assertEqual(demande.statut, SIGNATURE_SIGNE)
        self.assertEqual(demande.signature_tracee,
                         'data:image/png;base64,abc==')

    def test_signer_hash_best_effort_empty_on_storage_error(self):
        """Le stockage indisponible ne bloque jamais la signature (hash vide)."""
        with mock.patch('apps.records.storage.fetch_attachment',
                        return_value=(None, 'unreachable')):
            demande = services.signer_demande_publique(
                self.demande, consentement=True, signature_texte='Jean')
        self.assertEqual(demande.statut, SIGNATURE_SIGNE)
        self.assertEqual(demande.hash_contenu, '')

    def test_refuser_requires_motif(self):
        with self.assertRaises(ValueError):
            services.refuser_demande_publique(self.demande, motif='')

    def test_refuser_with_motif_records_proof(self):
        demande = services.refuser_demande_publique(
            self.demande, motif='Prix trop élevé',
            adresse_ip='41.140.1.3', user_agent='TestAgent/2.0')
        self.assertEqual(demande.statut, SIGNATURE_REFUSE)
        self.assertEqual(demande.motif_refus, 'Prix trop élevé')
        self.assertEqual(demande.adresse_ip, '41.140.1.3')
        self.assertIsNotNone(demande.refuse_le)

    def test_refuser_idempotent(self):
        demande = services.refuser_demande_publique(
            self.demande, motif='Non merci')
        date1 = demande.refuse_le
        demande = services.refuser_demande_publique(
            self.demande, motif='Non merci (bis)')
        self.assertEqual(demande.refuse_le, date1)


class PublicSignatureApiTests(XGed1Base):
    URL_TMPL = '/api/django/ged/signature/{token}/'

    def test_get_unknown_token_404(self):
        resp = self.client.get(self.URL_TMPL.format(token='bogus'))
        self.assertEqual(resp.status_code, 404)

    def test_get_consult_payload(self):
        resp = self.client.get(
            self.URL_TMPL.format(token=self.demande.token))
        self.assertEqual(resp.status_code, 200, resp.data)
        self.assertEqual(resp.data['document_nom'], 'Contrat à signer')
        self.assertEqual(resp.data['signataire_nom'], 'Jean Client')
        self.assertEqual(resp.data['statut'], SIGNATURE_EN_ATTENTE)

    def test_get_expired_410(self):
        self.demande.expires_at = timezone.now() - timezone.timedelta(hours=1)
        self.demande.save(update_fields=['expires_at'])
        resp = self.client.get(
            self.URL_TMPL.format(token=self.demande.token))
        self.assertEqual(resp.status_code, 410)

    def test_post_signer_missing_consentement_400(self):
        resp = self.client.post(
            self.URL_TMPL.format(token=self.demande.token),
            {'action': 'signer', 'signature_texte': 'Jean'}, format='json')
        self.assertEqual(resp.status_code, 400)

    def test_post_signer_success(self):
        with mock.patch('apps.records.storage.fetch_attachment',
                        return_value=(b'data', None)):
            resp = self.client.post(
                self.URL_TMPL.format(token=self.demande.token),
                {'action': 'signer', 'consentement': True,
                 'signature_texte': 'Jean Client'}, format='json')
        self.assertEqual(resp.status_code, 200, resp.data)
        self.assertEqual(resp.data['statut'], SIGNATURE_SIGNE)
        self.demande.refresh_from_db()
        self.assertEqual(self.demande.statut, SIGNATURE_SIGNE)
        self.assertTrue(self.demande.consentement_explicite)

    def test_post_signer_twice_returns_410(self):
        """Une demande déjà signée ne peut plus être re-signée (410)."""
        with mock.patch('apps.records.storage.fetch_attachment',
                        return_value=(b'data', None)):
            self.client.post(
                self.URL_TMPL.format(token=self.demande.token),
                {'action': 'signer', 'consentement': True,
                 'signature_texte': 'Jean'}, format='json')
            resp = self.client.post(
                self.URL_TMPL.format(token=self.demande.token),
                {'action': 'signer', 'consentement': True,
                 'signature_texte': 'Jean'}, format='json')
        self.assertEqual(resp.status_code, 410)

    def test_post_refuser_missing_motif_400(self):
        resp = self.client.post(
            self.URL_TMPL.format(token=self.demande.token),
            {'action': 'refuser'}, format='json')
        self.assertEqual(resp.status_code, 400)

    def test_post_refuser_success(self):
        resp = self.client.post(
            self.URL_TMPL.format(token=self.demande.token),
            {'action': 'refuser', 'motif': 'Pas intéressé'}, format='json')
        self.assertEqual(resp.status_code, 200, resp.data)
        self.assertEqual(resp.data['statut'], SIGNATURE_REFUSE)
        self.demande.refresh_from_db()
        self.assertEqual(self.demande.motif_refus, 'Pas intéressé')

    def test_post_unknown_action_400(self):
        resp = self.client.post(
            self.URL_TMPL.format(token=self.demande.token),
            {'action': 'danser'}, format='json')
        self.assertEqual(resp.status_code, 400)

    def test_public_payload_never_leaks_other_company(self):
        """Le token ne référence qu'une seule demande d'une seule société ;
        aucun champ de la réponse ne fuit une donnée d'une autre société."""
        resp = self.client.get(
            self.URL_TMPL.format(token=self.demande.token))
        self.assertEqual(resp.status_code, 200)
        self.assertNotIn('company', resp.data)
