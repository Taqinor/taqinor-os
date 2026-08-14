"""NTMKT45 — Audit log des actions marketing sensibles (``apps.audit``,
jamais un second journal).

Couvre les 3 actions journalisées : envoi réel d'une campagne, export de
segment/campagne (NTMKT39/40), modification du modèle d'attribution société
(NTMKT20) — chacune avec l'utilisateur acteur + la société, filtrable via
l'écran d'audit existant (``AuditLog``).

Corps de requête : ``format='json'``, JAMAIS ``content_type='application/
json'``. ``TenantAPITestCase.client_as`` rend un ``APIClient`` DRF (pas le
``django.test.Client``) : quand un ``content_type`` est passé EXPLICITEMENT,
DRF traite ``data`` comme un corps brut et l'encode via ``force_bytes`` — un
dict part donc en ``repr()`` Python (guillemets simples,
``{'a': 'b'}``), JSON invalide. ``JSONParser`` lève alors ``ParseError`` et
la vue répond 400 avant même d'exécuter sa logique. ``format='json'``
sérialise réellement en JSON (idiome DRF déjà utilisé ailleurs dans le
repo).
"""
from apps.audit.models import AuditLog
from apps.crm.models import Lead
from apps.marketing import services as mkt_services
from apps.marketing.models import Campagne, SegmentMarketing

from testkit.base import TenantAPITestCase


class AuditEnvoiCampagneTests(TenantAPITestCase):
    def test_envoi_reel_est_journalise(self):
        # `CampagneViewSet.envoyer` exige `compta_valider`
        # (`HasPermissionOrLegacy`, apps/compta/views.py) — repli légataire
        # sur `is_responsable` pour un compte sans rôle fin. On élève
        # `self.user` en place (au lieu d'un utilisateur `role=` séparé) car
        # l'assertion ci-dessous vérifie `entree.actor_username ==
        # self.user.username` : l'acteur du journal doit rester CE user.
        self.user.role_legacy = 'responsable'
        self.user.save(update_fields=['role_legacy'])
        campagne = Campagne.objects.create(
            company=self.company, nom='Campagne Audit', canal='email',
            objet='Objet', corps='Corps.')
        res = self.client_as().post(
            f'/api/django/marketing/campagnes/{campagne.id}/envoyer/',
            data={'destinataires': ['audit@ex.ma']},
            format='json')
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
    # `parametres_marketing_view` exige explicitement IsResponsableOrAdmin
    # (apps/marketing/views.py) — un utilisateur 'normal' reçoit 403 avant
    # d'atteindre la vue. Aucune assertion ici ne dépend de l'identité de
    # l'acteur, donc un utilisateur 'responsable' dédié suffit.
    def test_changement_de_modele_est_journalise(self):
        res = self.client_as(role='responsable').patch(
            '/api/django/marketing/parametres/',
            data={'modele_attribution': 'lineaire'},
            format='json')
        self.assertEqual(res.status_code, 200)
        entree = AuditLog.objects.filter(
            company=self.company, action=AuditLog.Action.UPDATE).latest('id')
        self.assertIn('dernier_touche', entree.detail)
        self.assertIn('lineaire', entree.detail)

    def test_un_patch_qui_ne_change_pas_le_modele_ne_journalise_rien(self):
        avant = AuditLog.objects.filter(
            company=self.company, action=AuditLog.Action.UPDATE).count()
        res = self.client_as(role='responsable').patch(
            '/api/django/marketing/parametres/',
            data={'expediteur_nom': 'Nouveau nom'},
            format='json')
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
