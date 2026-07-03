"""XGED2 — Circuit multi-signataires (séquentiel/parallèle) + relances +
expiration + annulation.

Couvre :
  * création multi-destinataires : le 1er devient le signataire « principal »
    rétrocompatible, TOUS deviennent des `SignataireDemande` ordonnés ;
  * routage séquentiel : le rang N+1 n'est notifié qu'après traitement du
    rang N ; routage parallèle : tous notifiés dès l'envoi ;
  * relances automatiques à la cadence configurée (idempotentes par appel) ;
  * expiration bascule la demande `en_attente` échue en `annule` ;
  * annulation par l'émetteur est tracée (`annule_le`/`annule_par`) et
    refusée sur une demande déjà signée/refusée ;
  * scoping société sur `SignataireDemande` et l'API.
"""
from unittest import mock

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.utils import timezone
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from authentication.models import Company
from apps.ged import selectors, services
from apps.ged.models import (
    Cabinet, Document, Folder, ROLE_COPIE, ROLE_SIGNATAIRE,
    ROUTAGE_PARALLELE, ROUTAGE_SEQUENTIEL, SIGNATAIRE_EN_ATTENTE,
    SIGNATAIRE_NOTIFIE, SIGNATAIRE_REFUSE, SIGNATURE_ANNULE,
    SIGNATURE_REFUSE, SIGNATURE_SIGNE,
)

User = get_user_model()


def make_company(slug, nom):
    company, _ = Company.objects.get_or_create(slug=slug, defaults={'nom': nom})
    return company


def make_user(company, username, role='admin'):
    return User.objects.create_user(
        username=username, password='x', company=company, role_legacy=role)


def auth(user):
    api = APIClient()
    api.credentials(HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(user)}')
    return api


class XGed2Base(TestCase):
    def setUp(self):
        self.co_a = make_company('xged2-a', 'Xged2 A')
        self.co_b = make_company('xged2-b', 'Xged2 B')
        self.admin_a = make_user(self.co_a, 'xged2-admin-a', 'admin')
        self.admin_b = make_user(self.co_b, 'xged2-admin-b', 'admin')
        self.cab_a = Cabinet.objects.create(company=self.co_a, nom='Admin')
        self.folder_a = Folder.objects.create(
            company=self.co_a, cabinet=self.cab_a, nom='Dossier A')
        self.doc_a = Document.objects.create(
            company=self.co_a, folder=self.folder_a, nom='Contrat 3 parties')

    def _destinataires(self):
        return [
            {'nom': 'Alice', 'email': 'alice@x.com', 'role': ROLE_SIGNATAIRE},
            {'nom': 'Bob', 'email': 'bob@x.com', 'role': ROLE_SIGNATAIRE},
            {'nom': 'Carla', 'email': 'carla@x.com', 'role': ROLE_COPIE},
        ]


class CreationMultiTests(XGed2Base):
    def test_creates_signataires_ordered(self):
        demande = services.creer_demande_multi_signataires(
            self.doc_a, destinataires=self._destinataires(),
            company=self.co_a, created_by=self.admin_a)
        self.assertEqual(demande.signataires.count(), 3)
        self.assertEqual(demande.signataire_nom, 'Alice')
        ordres = list(demande.signataires.order_by('ordre').values_list(
            'ordre', flat=True))
        self.assertEqual(ordres, [1, 2, 3])

    def test_sequential_notifies_only_first_rank(self):
        """Séquentiel (défaut) : seul le rang 1 signataire est notifié — le
        rang 2 reste en_attente tant que le rang 1 n'a pas signé."""
        demande = services.creer_demande_multi_signataires(
            self.doc_a, destinataires=self._destinataires(),
            company=self.co_a, routage=ROUTAGE_SEQUENTIEL)
        alice = demande.signataires.get(nom='Alice')
        bob = demande.signataires.get(nom='Bob')
        self.assertEqual(alice.statut, SIGNATAIRE_NOTIFIE)
        self.assertEqual(bob.statut, SIGNATAIRE_EN_ATTENTE)

    def test_parallel_notifies_all_signataires(self):
        demande = services.creer_demande_multi_signataires(
            self.doc_a, destinataires=self._destinataires(),
            company=self.co_a, routage=ROUTAGE_PARALLELE)
        alice = demande.signataires.get(nom='Alice')
        bob = demande.signataires.get(nom='Bob')
        self.assertEqual(alice.statut, SIGNATAIRE_NOTIFIE)
        self.assertEqual(bob.statut, SIGNATAIRE_NOTIFIE)

    def test_copie_role_always_notified_in_parallel_of_flow(self):
        demande = services.creer_demande_multi_signataires(
            self.doc_a, destinataires=self._destinataires(),
            company=self.co_a, routage=ROUTAGE_SEQUENTIEL)
        carla = demande.signataires.get(nom='Carla')
        self.assertEqual(carla.statut, SIGNATAIRE_NOTIFIE)

    def test_cross_company_document_rejected(self):
        doc_b = Document.objects.create(
            company=self.co_b,
            folder=Folder.objects.create(
                company=self.co_b,
                cabinet=Cabinet.objects.create(company=self.co_b, nom='C'),
                nom='D'),
            nom='Doc B')
        with self.assertRaises(PermissionError):
            services.creer_demande_multi_signataires(
                doc_b, destinataires=self._destinataires(), company=self.co_a)

    def test_requires_at_least_one_destinataire(self):
        with self.assertRaises(ValueError):
            services.creer_demande_multi_signataires(
                self.doc_a, destinataires=[], company=self.co_a)


class ProgressionSequentielleTests(XGed2Base):
    def setUp(self):
        super().setUp()
        self.demande = services.creer_demande_multi_signataires(
            self.doc_a, destinataires=self._destinataires(),
            company=self.co_a, routage=ROUTAGE_SEQUENTIEL)

    def test_signing_rank1_notifies_rank2(self):
        alice = self.demande.signataires.get(nom='Alice')
        services.signer_signataire(
            alice, consentement=True, signature_texte='Alice A.')
        bob = self.demande.signataires.get(nom='Bob')
        self.assertEqual(bob.statut, SIGNATAIRE_NOTIFIE)

    def test_demande_globale_signe_only_when_all_signataires_signed(self):
        alice = self.demande.signataires.get(nom='Alice')
        services.signer_signataire(
            alice, consentement=True, signature_texte='Alice A.')
        self.demande.refresh_from_db()
        self.assertNotEqual(self.demande.statut, SIGNATURE_SIGNE)

        bob = self.demande.signataires.get(nom='Bob')
        services.signer_signataire(
            bob, consentement=True, signature_texte='Bob B.')
        self.demande.refresh_from_db()
        self.assertEqual(self.demande.statut, SIGNATURE_SIGNE)

    def test_signer_requires_consentement(self):
        alice = self.demande.signataires.get(nom='Alice')
        with self.assertRaises(ValueError):
            services.signer_signataire(
                alice, consentement=False, signature_texte='Alice A.')

    def test_refus_by_any_signataire_refuses_global_demande(self):
        alice = self.demande.signataires.get(nom='Alice')
        services.refuser_signataire(alice, motif='Pas d\'accord')
        self.demande.refresh_from_db()
        self.assertEqual(self.demande.statut, SIGNATURE_REFUSE)
        alice.refresh_from_db()
        self.assertEqual(alice.statut, SIGNATAIRE_REFUSE)

    def test_refuser_requires_motif(self):
        alice = self.demande.signataires.get(nom='Alice')
        with self.assertRaises(ValueError):
            services.refuser_signataire(alice, motif='')


class ExpirationAnnulationTests(XGed2Base):
    def test_expirer_demandes_echues(self):
        demande = services.demander_signature(
            self.doc_a, signataire_nom='X', signataire_email='x@x.com',
            company=self.co_a)
        demande.expires_at = timezone.now() - timezone.timedelta(days=1)
        demande.save(update_fields=['expires_at'])
        count = services.expirer_demandes_echues(self.co_a)
        self.assertEqual(count, 1)
        demande.refresh_from_db()
        self.assertEqual(demande.statut, SIGNATURE_ANNULE)

    def test_expirer_ignores_non_expired(self):
        demande = services.demander_signature(
            self.doc_a, signataire_nom='X', signataire_email='x@x.com',
            company=self.co_a)
        demande.expires_at = timezone.now() + timezone.timedelta(days=1)
        demande.save(update_fields=['expires_at'])
        count = services.expirer_demandes_echues(self.co_a)
        self.assertEqual(count, 0)

    def test_annuler_demande(self):
        demande = services.demander_signature(
            self.doc_a, signataire_nom='X', signataire_email='x@x.com',
            company=self.co_a)
        demande = services.annuler_demande(demande, user=self.admin_a)
        self.assertEqual(demande.statut, SIGNATURE_ANNULE)
        self.assertIsNotNone(demande.annule_le)
        self.assertEqual(demande.annule_par_id, self.admin_a.id)

    def test_annuler_signed_raises(self):
        demande = services.demander_signature(
            self.doc_a, signataire_nom='X', signataire_email='x@x.com',
            company=self.co_a)
        services.marquer_signe(demande)
        with self.assertRaises(ValueError):
            services.annuler_demande(demande, user=self.admin_a)

    def test_annuler_idempotent(self):
        demande = services.demander_signature(
            self.doc_a, signataire_nom='X', signataire_email='x@x.com',
            company=self.co_a)
        services.annuler_demande(demande, user=self.admin_a)
        demande2 = services.annuler_demande(demande, user=self.admin_a)
        self.assertEqual(demande2.statut, SIGNATURE_ANNULE)


class RelancesTests(XGed2Base):
    def test_relance_due_after_cadence(self):
        demande = services.creer_demande_multi_signataires(
            self.doc_a, destinataires=self._destinataires(),
            company=self.co_a, relance_cadence_jours=3)
        alice = demande.signataires.get(nom='Alice')
        alice.notifie_le = timezone.now() - timezone.timedelta(days=4)
        alice.save(update_fields=['notifie_le'])
        with mock.patch('apps.ged.services._send_signataire_email',
                        return_value=True) as mocked:
            relances = services.relancer_signataires_dus(self.co_a)
        self.assertEqual(len(relances), 1)
        self.assertEqual(relances[0].id, alice.id)
        mocked.assert_called_once()
        alice.refresh_from_db()
        self.assertEqual(alice.nb_relances, 1)

    def test_relance_not_due_yet(self):
        demande = services.creer_demande_multi_signataires(
            self.doc_a, destinataires=self._destinataires(),
            company=self.co_a, relance_cadence_jours=7)
        alice = demande.signataires.get(nom='Alice')
        alice.notifie_le = timezone.now() - timezone.timedelta(days=1)
        alice.save(update_fields=['notifie_le'])
        relances = services.relancer_signataires_dus(self.co_a)
        self.assertEqual(len(relances), 0)

    def test_relance_no_cadence_configured_noop(self):
        services.creer_demande_multi_signataires(
            self.doc_a, destinataires=self._destinataires(),
            company=self.co_a)  # pas de cadence
        relances = services.relancer_signataires_dus(self.co_a)
        self.assertEqual(len(relances), 0)

    def test_relance_idempotent_within_same_pass(self):
        demande = services.creer_demande_multi_signataires(
            self.doc_a, destinataires=self._destinataires(),
            company=self.co_a, relance_cadence_jours=1)
        alice = demande.signataires.get(nom='Alice')
        alice.notifie_le = timezone.now() - timezone.timedelta(days=2)
        alice.save(update_fields=['notifie_le'])
        services.relancer_signataires_dus(self.co_a)
        # Un second passage IMMÉDIAT ne relance pas de nouveau (la dernière
        # relance vient d'être posée).
        relances2 = services.relancer_signataires_dus(self.co_a)
        self.assertEqual(len(relances2), 0)


class ScopingApiTests(XGed2Base):
    def test_signataire_scoped_by_company(self):
        demande = services.creer_demande_multi_signataires(
            self.doc_a, destinataires=self._destinataires(),
            company=self.co_a)
        self.assertEqual(
            selectors.signataires_for_demande(demande).count(), 3)
        resp = auth(self.admin_b).get('/api/django/ged/signataires-demande/')
        self.assertEqual(resp.status_code, 200)
        data = resp.data['results'] if isinstance(resp.data, dict) else resp.data
        self.assertEqual(len(data), 0)

    def test_creer_multi_api(self):
        resp = auth(self.admin_a).post(
            '/api/django/ged/demandes-signature/creer-multi/',
            {'document': self.doc_a.id, 'destinataires': self._destinataires()},
            format='json')
        self.assertEqual(resp.status_code, 201, resp.data)
        self.assertEqual(len(resp.data['signataires']), 3)

    def test_annuler_api(self):
        demande = services.demander_signature(
            self.doc_a, signataire_nom='X', signataire_email='x@x.com',
            company=self.co_a)
        resp = auth(self.admin_a).post(
            f'/api/django/ged/demandes-signature/{demande.id}/annuler/',
            {}, format='json')
        self.assertEqual(resp.status_code, 200, resp.data)
        self.assertEqual(resp.data['statut'], SIGNATURE_ANNULE)

    def test_public_signataire_endpoint_get(self):
        demande = services.creer_demande_multi_signataires(
            self.doc_a, destinataires=self._destinataires(),
            company=self.co_a)
        alice = demande.signataires.get(nom='Alice')
        resp = self.client.get(
            f'/api/django/ged/signataire/{alice.token}/')
        self.assertEqual(resp.status_code, 200, resp.data)
        self.assertEqual(resp.data['nom'], 'Alice')

    def test_public_signataire_not_yet_turn_403(self):
        demande = services.creer_demande_multi_signataires(
            self.doc_a, destinataires=self._destinataires(),
            company=self.co_a, routage=ROUTAGE_SEQUENTIEL)
        bob = demande.signataires.get(nom='Bob')  # rang 2, pas encore notifié
        resp = self.client.post(
            f'/api/django/ged/signataire/{bob.token}/',
            {'action': 'signer', 'consentement': True,
             'signature_texte': 'Bob'}, format='json')
        self.assertEqual(resp.status_code, 403)

    def test_public_signataire_unknown_token_404(self):
        resp = self.client.get('/api/django/ged/signataire/bogus/')
        self.assertEqual(resp.status_code, 404)
