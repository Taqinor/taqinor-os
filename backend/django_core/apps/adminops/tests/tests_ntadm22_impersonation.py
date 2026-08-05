"""NTADM22 — impersonation auditée SOUS CONSENTEMENT.

Les deux critères d'acceptation sont testés frontalement :
  1. sans consentement, AUCUNE session n'est possible (à aucun endroit) ;
  2. les actions faites pendant une session sont distinctement marquées dans
     le journal d'audit.
"""
from django.test import TestCase
from django.utils import timezone
from rest_framework.test import APIClient

from authentication.models import Company, CustomUser

from .. import impersonation_service
from ..models import SessionImpersonation


def _company(nom, slug):
    return Company.objects.create(nom=nom, slug=slug)


class ImpersonationConsentementTests(TestCase):
    """Cœur sécurité : pas de consentement ⇒ pas de session."""

    def setUp(self):
        self.tenant = _company('Client Alpha', 'client-alpha-imp')
        self.admin = CustomUser.objects.create_user(
            username='admin_alpha_imp', password='pw41827',
            company=self.tenant, role_legacy='admin')
        self.cible = CustomUser.objects.create_user(
            username='vendeur_alpha_imp', password='pw41827',
            company=self.tenant, role_legacy='normal')
        self.support = CustomUser.objects.create_user(
            username='support_editeur_imp', password='pw41827',
            is_taqinor_support=True)

    def _demande(self):
        return impersonation_service.demander_impersonation(
            utilisateur_cible=self.cible, initiee_par=self.support,
            motif='Diagnostic incident #4182')

    # ── 1. Sans consentement, aucune session ────────────────────────────────
    def test_demande_naît_inerte(self):
        demande = self._demande()
        self.assertFalse(demande.consentement_donne)
        self.assertFalse(demande.est_active())
        self.assertEqual(demande.statut, 'en_attente')

    def test_sans_consentement_aucun_jeton(self):
        demande = self._demande()
        with self.assertRaises(impersonation_service.ImpersonationRefusee):
            impersonation_service.emettre_jeton_impersonation(demande)

    def test_refus_bloque_definitivement(self):
        demande = self._demande()
        impersonation_service.refuser(demande, par=self.admin)
        with self.assertRaises(impersonation_service.ImpersonationRefusee):
            impersonation_service.donner_consentement(demande, par=self.admin)
        with self.assertRaises(impersonation_service.ImpersonationRefusee):
            impersonation_service.emettre_jeton_impersonation(demande)

    def test_demande_expiree_jamais_autorisable_retroactivement(self):
        demande = self._demande()
        SessionImpersonation.objects.filter(pk=demande.pk).update(
            expire_le=timezone.now() - timezone.timedelta(minutes=1))
        demande.refresh_from_db()
        with self.assertRaises(impersonation_service.ImpersonationRefusee):
            impersonation_service.donner_consentement(demande, par=self.admin)
        demande.refresh_from_db()
        self.assertFalse(demande.consentement_donne)
        self.assertTrue(demande.expiree)

    def test_motif_obligatoire(self):
        with self.assertRaises(impersonation_service.ImpersonationRefusee):
            impersonation_service.demander_impersonation(
                utilisateur_cible=self.cible, initiee_par=self.support,
                motif='   ')
        self.assertEqual(SessionImpersonation.objects.count(), 0)

    def test_non_support_ne_peut_pas_demander(self):
        with self.assertRaises(impersonation_service.ImpersonationRefusee):
            impersonation_service.demander_impersonation(
                utilisateur_cible=self.cible, initiee_par=self.admin,
                motif='tentative')

    # ── Consentement donné : la session devient exploitable ─────────────────
    def test_consentement_ouvre_la_session(self):
        demande = self._demande()
        impersonation_service.donner_consentement(demande, par=self.admin)
        self.assertTrue(demande.est_active())
        self.assertEqual(demande.statut, 'active')
        jeton = impersonation_service.emettre_jeton_impersonation(demande)
        self.assertTrue(jeton)

    def test_session_terminee_nest_plus_active(self):
        demande = self._demande()
        impersonation_service.donner_consentement(demande, par=self.admin)
        impersonation_service.terminer(demande)
        self.assertFalse(demande.est_active())
        with self.assertRaises(impersonation_service.ImpersonationRefusee):
            impersonation_service.emettre_jeton_impersonation(demande)

    def test_notification_envoyee_a_l_administrateur(self):
        from apps.notifications.models import EventType, Notification
        self._demande()
        self.assertTrue(Notification.objects.filter(
            recipient=self.admin,
            event_type=EventType.IMPERSONATION_REQUESTED).exists())


class ImpersonationApiTests(TestCase):
    """Gardes d'accès des endpoints (support vs Administrateur vs tiers)."""

    def setUp(self):
        self.tenant = _company('Client Beta', 'client-beta-imp')
        self.autre = _company('Client Gamma', 'client-gamma-imp')
        self.admin = CustomUser.objects.create_user(
            username='admin_beta_imp', password='pw41827',
            company=self.tenant, role_legacy='admin')
        self.admin_autre = CustomUser.objects.create_user(
            username='admin_gamma_imp', password='pw41827',
            company=self.autre, role_legacy='admin')
        self.cible = CustomUser.objects.create_user(
            username='vendeur_beta_imp', password='pw41827',
            company=self.tenant, role_legacy='normal')
        self.support = CustomUser.objects.create_user(
            username='support_beta_imp', password='pw41827',
            is_taqinor_support=True)

    def _api(self, user):
        client = APIClient()
        client.force_authenticate(user)
        return client

    def test_demande_sans_motif_refusee_par_le_serveur(self):
        resp = self._api(self.support).post(
            '/api/django/adminops/impersonation/',
            {'utilisateur_cible': self.cible.pk, 'motif': ''}, format='json')
        self.assertEqual(resp.status_code, 400)
        self.assertEqual(SessionImpersonation.objects.count(), 0)

    def test_demande_creee_par_le_support(self):
        resp = self._api(self.support).post(
            '/api/django/adminops/impersonation/',
            {'utilisateur_cible': self.cible.pk,
             'motif': 'Analyse du devis bloqué'}, format='json')
        self.assertEqual(resp.status_code, 201)
        self.assertFalse(resp.data['consentement_donne'])
        self.assertEqual(resp.data['statut'], 'en_attente')

    def test_utilisateur_normal_ne_peut_pas_demander(self):
        resp = self._api(self.cible).post(
            '/api/django/adminops/impersonation/',
            {'utilisateur_cible': self.cible.pk, 'motif': 'x'}, format='json')
        self.assertIn(resp.status_code, (401, 403))

    def test_admin_dun_autre_tenant_ne_peut_pas_consentir(self):
        demande = impersonation_service.demander_impersonation(
            utilisateur_cible=self.cible, initiee_par=self.support,
            motif='Diagnostic')
        resp = self._api(self.admin_autre).post(
            f'/api/django/adminops/impersonation/{demande.pk}/consentir/')
        self.assertEqual(resp.status_code, 404)
        demande.refresh_from_db()
        self.assertFalse(demande.consentement_donne)

    def test_parcours_consentir_puis_demarrer(self):
        demande = impersonation_service.demander_impersonation(
            utilisateur_cible=self.cible, initiee_par=self.support,
            motif='Diagnostic')
        # Le support ne peut pas démarrer avant le consentement.
        refus = self._api(self.support).post(
            f'/api/django/adminops/impersonation/{demande.pk}/demarrer/')
        self.assertEqual(refus.status_code, 403)

        ok = self._api(self.admin).post(
            f'/api/django/adminops/impersonation/{demande.pk}/consentir/')
        self.assertEqual(ok.status_code, 200)
        self.assertTrue(ok.data['consentement_donne'])

        demarre = self._api(self.support).post(
            f'/api/django/adminops/impersonation/{demande.pk}/demarrer/')
        self.assertEqual(demarre.status_code, 200)
        self.assertIn('access', demarre.data)

    def test_session_active_faux_pour_une_requete_ordinaire(self):
        resp = self._api(self.cible).get(
            '/api/django/adminops/impersonation/session-active/')
        self.assertEqual(resp.status_code, 200)
        self.assertFalse(resp.data['active'])


class ImpersonationAuditTests(TestCase):
    """Critère d'acceptation 2 : les actions de la session sont marquées."""

    def setUp(self):
        self.tenant = _company('Client Delta', 'client-delta-imp')
        self.admin = CustomUser.objects.create_user(
            username='admin_delta_imp', password='pw41827',
            company=self.tenant, role_legacy='admin')
        self.cible = CustomUser.objects.create_user(
            username='vendeur_delta_imp', password='pw41827',
            company=self.tenant, role_legacy='normal')
        self.support = CustomUser.objects.create_user(
            username='support_delta_imp', password='pw41827',
            is_taqinor_support=True)

    def test_ligne_daudit_marquee_pendant_une_session(self):
        from apps.audit.models import AuditLog
        from apps.audit.recorder import begin_request, end_request, record

        from ..receivers import MARQUEUR_IMPERSONATION

        demande = impersonation_service.demander_impersonation(
            utilisateur_cible=self.cible, initiee_par=self.support,
            motif='Diagnostic incident')
        impersonation_service.donner_consentement(demande, par=self.admin)

        class _FausseRequete:
            """Requête minimale portant les revendications du jeton."""
            def __init__(self, user, claims):
                self.user = user
                self.auth = claims

        requete = _FausseRequete(self.cible, {
            impersonation_service.CLAIM_SESSION: demande.pk,
            impersonation_service.CLAIM_SUPPORT: self.support.pk,
        })
        begin_request(requete)
        try:
            record('update', company=self.tenant, user=self.cible,
                   detail='Modification du devis')
        finally:
            end_request()

        ligne = AuditLog.objects.filter(company=self.tenant).latest('id')
        self.assertIn(MARQUEUR_IMPERSONATION, ligne.detail)
        self.assertIn(f'session={demande.pk}', ligne.detail)
        self.assertIn(self.support.username, ligne.detail)

    def test_ligne_daudit_non_marquee_hors_session(self):
        from apps.audit.models import AuditLog
        from apps.audit.recorder import begin_request, end_request, record

        from ..receivers import MARQUEUR_IMPERSONATION

        class _FausseRequete:
            def __init__(self, user):
                self.user = user
                self.auth = None

        begin_request(_FausseRequete(self.cible))
        try:
            record('update', company=self.tenant, user=self.cible,
                   detail='Modification ordinaire')
        finally:
            end_request()

        ligne = AuditLog.objects.filter(company=self.tenant).latest('id')
        self.assertNotIn(MARQUEUR_IMPERSONATION, ligne.detail)
