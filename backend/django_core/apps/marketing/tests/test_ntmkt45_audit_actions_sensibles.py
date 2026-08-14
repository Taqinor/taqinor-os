"""NTMKT45 — Audit log des actions marketing sensibles (``apps.audit``,
jamais un second journal).

Couvre les 3 actions journalisées : envoi réel d'une campagne, export de
segment/campagne (NTMKT39/40), modification du modèle d'attribution société
(NTMKT20) — chacune avec l'utilisateur acteur + la société, filtrable via
l'écran d'audit existant (``AuditLog``).
"""
from apps.audit.models import AuditLog
from apps.crm.models import Lead
from apps.marketing import services as mkt_services
from apps.marketing.models import Campagne, SegmentMarketing

from testkit.base import TenantAPITestCase


class AuditEnvoiCampagneTests(TenantAPITestCase):
    def test_envoi_reel_est_journalise(self):
        campagne = Campagne.objects.create(
            company=self.company, nom='Campagne Audit', canal='email',
            objet='Objet', corps='Corps.')
        res = self.client_as().post(
            f'/api/django/marketing/campagnes/{campagne.id}/envoyer/',
            data={'destinataires': ['audit@ex.ma']},
            content_type='application/json')
        self.assertEqual(res.status_code, 200)
        entree = AuditLog.objects.filter(
            company=self.company, action=AuditLog.Action.EMAIL).latest('id')
        self.assertIn('Campagne Audit', entree.detail)
        self.assertEqual(entree.actor_username, self.user.username)


class AuditExportsTests(TenantAPITestCase):
    def test_export_campagnes_xlsx_est_journalise(self):
        res = self.client_as().get('/api/django/marketing/campagnes/export/')
        self.assertEqual(res.status_code, 200)
        entree = AuditLog.objects.filter(
            company=self.company, action=AuditLog.Action.EXPORT).latest('id')
        self.assertIn('campagnes', entree.detail.lower())

    def test_export_trace_envoi_est_journalise_avec_la_campagne(self):
        campagne = Campagne.objects.create(
            company=self.company, nom='Campagne Trace', canal='email')
        res = self.client_as().get(
            f'/api/django/marketing/campagnes/{campagne.id}/envois/export/')
        self.assertEqual(res.status_code, 200)
        entree = AuditLog.objects.filter(
            company=self.company, action=AuditLog.Action.EXPORT).latest('id')
        self.assertIn('Campagne Trace', entree.detail)

    def test_export_membres_segment_est_journalise(self):
        Lead.objects.create(company=self.company, nom='Lead A', ville='Fès')
        segment = SegmentMarketing.objects.create(
            company=self.company, nom='Segment Audit',
            regles={'ville': 'Fès'})
        res = self.client_as().get(
            f'/api/django/marketing/segments-marketing/{segment.id}/export/')
        self.assertEqual(res.status_code, 200)
        entree = AuditLog.objects.filter(
            company=self.company, action=AuditLog.Action.EXPORT).latest('id')
        self.assertIn('Segment Audit', entree.detail)


class AuditModeleAttributionTests(TenantAPITestCase):
    def test_changement_de_modele_est_journalise(self):
        res = self.client_as().patch(
            '/api/django/marketing/parametres/',
            data={'modele_attribution': 'lineaire'},
            content_type='application/json')
        self.assertEqual(res.status_code, 200)
        entree = AuditLog.objects.filter(
            company=self.company, action=AuditLog.Action.UPDATE).latest('id')
        self.assertIn('dernier_touche', entree.detail)
        self.assertIn('lineaire', entree.detail)

    def test_un_patch_qui_ne_change_pas_le_modele_ne_journalise_rien(self):
        avant = AuditLog.objects.filter(
            company=self.company, action=AuditLog.Action.UPDATE).count()
        res = self.client_as().patch(
            '/api/django/marketing/parametres/',
            data={'expediteur_nom': 'Nouveau nom'},
            content_type='application/json')
        self.assertEqual(res.status_code, 200)
        apres = AuditLog.objects.filter(
            company=self.company, action=AuditLog.Action.UPDATE).count()
        self.assertEqual(avant, apres)


class AuditServiceUnitTests(TenantAPITestCase):
    def test_journaliser_action_marketing_appelle_le_recorder(self):
        mkt_services.journaliser_action_marketing(
            AuditLog.Action.EXPORT, user=self.user, company=self.company,
            detail='Test direct.')
        self.assertTrue(AuditLog.objects.filter(
            company=self.company, detail='Test direct.').exists())
