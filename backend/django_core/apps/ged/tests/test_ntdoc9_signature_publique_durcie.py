"""NTDOC9 — Durcissement anti-abus de la page de signature publique.

Couvre :
  * débit limité PAR JETON (indépendant de l'IP) : un attaquant qui fait
    tourner ses IP est quand même ralenti (429) ;
  * verrou temporaire après N tentatives ÉCHOUÉES consécutives sur un même
    jeton, avec un 429 explicite en français ;
  * chaque tentative échouée laisse une trace `JournalAcces` (`tentative_ko`) ;
  * un succès (signature/refus valides) remet le compteur à zéro — une série
    d'échecs NON consécutifs ne verrouille jamais ;
  * un usage normal (consultation + signature) n'est jamais impacté ;
  * détection « une même IP, plusieurs sociétés » → notification best-effort
    des administrateurs, une seule fois par fenêtre.
"""
from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.test import TestCase
from rest_framework.test import APIClient

from authentication.models import Company
from apps.ged import services
from apps.ged.models import (
    ACCES_TENTATIVE_KO, Cabinet, Document, DocumentVersion, Folder,
    JournalAcces, SIGNATURE_SIGNE,
)

User = get_user_model()


def make_company(slug, nom):
    company, _ = Company.objects.get_or_create(slug=slug, defaults={'nom': nom})
    return company


def make_user(company, username, role='admin'):
    return User.objects.create_user(
        username=username, password='x', company=company, role_legacy=role)


class NtDoc9Base(TestCase):
    def setUp(self):
        # Compteurs/verrous vivent dans le cache : on repart toujours propre
        # (sinon un test voisin laisserait un throttle armé).
        cache.clear()
        self.addCleanup(cache.clear)
        self.co_a = make_company('ntdoc9-a', 'Ntdoc9 A')
        self.admin_a = make_user(self.co_a, 'ntdoc9-admin-a', 'admin')
        self.cab_a = Cabinet.objects.create(company=self.co_a, nom='Admin')
        self.folder_a = Folder.objects.create(
            company=self.co_a, cabinet=self.cab_a, nom='Dossier A')
        self.doc_a = Document.objects.create(
            company=self.co_a, folder=self.folder_a, nom='Contrat à signer')
        DocumentVersion.objects.create(
            company=self.co_a, document=self.doc_a, version=1,
            file_key='ged/ntdoc9/doc-a.pdf', filename='doc-a.pdf',
            mime='application/pdf')
        self.demande = services.demander_signature(
            self.doc_a, signataire_nom='Jean Client',
            signataire_email='jean@example.com', company=self.co_a,
            created_by=self.admin_a)
        self.url = f'/api/django/ged/signature/{self.demande.token}/'
        self.api = APIClient()

    def _echec(self, ip='10.0.0.1'):
        """POST « signer » sans consentement : échec métier 400 attendu."""
        return self.api.post(self.url, {'action': 'signer'}, format='json',
                             REMOTE_ADDR=ip)


class VerrouApresEchecsTests(NtDoc9Base):
    def test_verrou_apres_seuil_echecs_consecutifs(self):
        """Le seuil atteint, le lien répond 429 explicite (plus 400)."""
        for _ in range(services.SIGNATURE_ABUS_MAX_ECHECS):
            self.assertEqual(self._echec().status_code, 400)
        self.assertTrue(
            services.signature_publique_verrouillee(self.demande.token))
        reponse = self.api.get(self.url, REMOTE_ADDR='10.0.0.1')
        self.assertEqual(reponse.status_code, 429)
        self.assertIn('verrouill', reponse.data['detail'].lower())

    def test_avant_le_seuil_aucun_verrou(self):
        """Une tentative ratée isolée ne verrouille jamais un signataire."""
        for _ in range(services.SIGNATURE_ABUS_MAX_ECHECS - 1):
            self.assertEqual(self._echec().status_code, 400)
        self.assertFalse(
            services.signature_publique_verrouillee(self.demande.token))
        self.assertEqual(
            self.api.get(self.url, REMOTE_ADDR='10.0.0.1').status_code, 200)

    def test_echecs_traces_dans_journal_acces(self):
        """Chaque échec laisse une trace auditable sur le bon document."""
        self._echec()
        self._echec()
        traces = JournalAcces.objects.filter(
            document=self.doc_a, type_acces=ACCES_TENTATIVE_KO)
        self.assertEqual(traces.count(), 2)
        trace = traces.first()
        self.assertEqual(trace.company_id, self.co_a.pk)
        self.assertIsNone(trace.utilisateur_id)
        self.assertEqual(trace.adresse_ip, '10.0.0.1')

    def test_succes_reinitialise_le_compteur(self):
        """Seule une série ININTERROMPUE d'échecs verrouille le lien."""
        for _ in range(services.SIGNATURE_ABUS_MAX_ECHECS - 1):
            self._echec()
        reponse = self.api.post(
            self.url,
            {'action': 'signer', 'consentement': True,
             'signature_texte': 'Jean Client'},
            format='json', REMOTE_ADDR='10.0.0.1')
        self.assertEqual(reponse.status_code, 200)
        self.demande.refresh_from_db()
        self.assertEqual(self.demande.statut, SIGNATURE_SIGNE)
        self.assertFalse(
            services.signature_publique_verrouillee(self.demande.token))
        self.assertIsNone(
            cache.get(services._cle_echecs_signature(self.demande.token)))

    def test_usage_normal_jamais_impacte(self):
        """Consultation puis signature : aucun 429, aucune trace d'échec."""
        self.assertEqual(
            self.api.get(self.url, REMOTE_ADDR='10.0.0.9').status_code, 200)
        reponse = self.api.post(
            self.url,
            {'action': 'signer', 'consentement': True,
             'signature_texte': 'Jean Client'},
            format='json', REMOTE_ADDR='10.0.0.9')
        self.assertEqual(reponse.status_code, 200)
        self.assertFalse(JournalAcces.objects.filter(
            type_acces=ACCES_TENTATIVE_KO).exists())


class ThrottleParJetonTests(NtDoc9Base):
    def test_debit_par_jeton_independant_de_l_ip(self):
        """20 appels/min sur le MÊME jeton, même en changeant d'IP → 429."""
        codes = []
        for i in range(22):
            reponse = self.api.get(self.url, REMOTE_ADDR=f'10.1.{i}.1')
            codes.append(reponse.status_code)
        self.assertEqual(codes[0], 200)
        self.assertIn(429, codes)
        # Le blocage vient bien du débit par jeton, pas d'un verrou d'abus
        # (aucune tentative n'a échoué côté métier).
        self.assertFalse(
            services.signature_publique_verrouillee(self.demande.token))

    def test_un_autre_jeton_reste_servi(self):
        """Le débit d'un jeton n'affecte jamais un autre lien de signature."""
        autre = services.demander_signature(
            self.doc_a, signataire_nom='Autre Client',
            signataire_email='autre@example.com', company=self.co_a,
            created_by=self.admin_a)
        for i in range(22):
            self.api.get(self.url, REMOTE_ADDR=f'10.2.{i}.1')
        reponse = self.api.get(
            f'/api/django/ged/signature/{autre.token}/', REMOTE_ADDR='10.3.0.1')
        self.assertEqual(reponse.status_code, 200)


class ReutilisationSuspecteTests(NtDoc9Base):
    def _autre_societe(self, slug):
        company = make_company(slug, slug)
        make_user(company, f'{slug}-admin', 'admin')
        return company

    def test_notification_admin_au_dela_du_seuil(self):
        from apps.notifications.models import Notification

        co_b = self._autre_societe('ntdoc9-b')
        co_c = self._autre_societe('ntdoc9-c')
        ip = '203.0.113.7'
        self.assertFalse(services.surveiller_reutilisation_suspecte(ip, self.co_a))
        self.assertFalse(services.surveiller_reutilisation_suspecte(ip, co_b))
        self.assertTrue(services.surveiller_reutilisation_suspecte(ip, co_c))
        alertes = Notification.objects.filter(
            company=co_c, event_type='security_alert')
        self.assertEqual(alertes.count(), 1)

    def test_une_seule_alerte_par_fenetre(self):
        from apps.notifications.models import Notification

        co_b = self._autre_societe('ntdoc9-d')
        co_c = self._autre_societe('ntdoc9-e')
        ip = '203.0.113.8'
        services.surveiller_reutilisation_suspecte(ip, self.co_a)
        services.surveiller_reutilisation_suspecte(ip, co_b)
        services.surveiller_reutilisation_suspecte(ip, co_c)
        services.surveiller_reutilisation_suspecte(ip, co_c)
        services.surveiller_reutilisation_suspecte(ip, co_c)
        self.assertEqual(
            Notification.objects.filter(event_type='security_alert').count(), 1)

    def test_usage_mono_societe_jamais_suspect(self):
        from apps.notifications.models import Notification

        ip = '203.0.113.9'
        for _ in range(10):
            self.assertFalse(
                services.surveiller_reutilisation_suspecte(ip, self.co_a))
        self.assertFalse(
            Notification.objects.filter(event_type='security_alert').exists())
