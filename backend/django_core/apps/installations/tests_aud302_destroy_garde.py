"""AUD302 — DELETE gardé sur intervention signée, fiche de recette et POD.

Défaut d'origine : `InterventionViewSet` (destroy → `IsResponsableOrAdmin`
seul, `perform_destroy` journalisant une note générique puis `super()`),
`CommissioningRecordViewSet` et `PreuveLivraisonViewSet` n'avaient AUCUNE
garde d'usage — une intervention VALIDÉE signée, une fiche `passe=True` ou une
preuve de livraison signée se détruisaient définitivement en 204 par un simple
Responsable/Admin.

REQUALIFICATION vérifiée dans cette lane : contrairement au constat d'audit,
`('installations', 'Intervention')` EST déjà dans
`apps.audit.signals.TRACKED_MODELS` — le signal générique `post_delete`
journalise donc déjà ses suppressions. Seuls `CommissioningRecord` et
`PreuveLivraison` en étaient absents, et c'est le `UsageGuardedDestroyMixin`
qui pose leur ligne `AuditLog`. Appliquer le mixin à l'intervention aurait
DOUBLÉ sa ligne — elle reçoit donc la garde seule.

Run :
    python manage.py test apps.installations.tests_aud302_destroy_garde -v2
"""
import itertools

from django.contrib.auth import get_user_model
from django.contrib.contenttypes.models import ContentType
from django.test import TestCase
from django.utils import timezone
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from apps.audit.models import AuditLog
from apps.audit.signals import TRACKED_MODELS
from apps.installations.models import (
    CommissioningRecord, Installation, Intervention, Livraison,
    PreuveLivraison,
)

User = get_user_model()
_seq = itertools.count(1)
BASE = '/api/django/installations'


def make_company():
    from authentication.models import Company
    n = next(_seq)
    company, _ = Company.objects.get_or_create(
        slug=f'aud302-co-{n}', defaults={'nom': f'AUD302 Co {n}'})
    return company


def auth(user):
    api = APIClient()
    api.credentials(HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(user)}')
    return api


class DestroyGardeTests(TestCase):
    def setUp(self):
        self.company = make_company()
        self.user = User.objects.create_user(
            username=f'aud302-resp-{next(_seq)}', password='x',
            company=self.company, role_legacy='responsable')
        self.api = auth(self.user)
        self.inst = Installation.objects.create(
            company=self.company, reference='AUD302-1',
            statut=Installation.Statut.INSTALLE)

    # ── Intervention ────────────────────────────────────────────────────────
    def _intervention(self, **kw):
        kw.setdefault('type_intervention', Intervention.Type.POSE)
        return Intervention.objects.create(
            company=self.company, installation=self.inst, **kw)

    def test_delete_intervention_signee_refuse(self):
        """ROUGE avant AUD302 : 204, compte-rendu signé détruit."""
        iv = self._intervention(
            statut=Intervention.Statut.TERMINEE,
            signature_client='data:image/png;base64,AAAA',
            signataire_nom='Client')
        r = self.api.delete(f'{BASE}/interventions/{iv.id}/')
        self.assertEqual(r.status_code, 409, r.data)
        self.assertTrue(Intervention.objects.filter(pk=iv.pk).exists())

    def test_delete_intervention_validee_refuse(self):
        iv = self._intervention(statut=Intervention.Statut.VALIDEE)
        r = self.api.delete(f'{BASE}/interventions/{iv.id}/')
        self.assertEqual(r.status_code, 409, r.data)
        self.assertTrue(Intervention.objects.filter(pk=iv.pk).exists())

    def test_delete_intervention_ordinaire_reste_permis_et_journalise(self):
        iv = self._intervention(statut=Intervention.Statut.A_PREPARER)
        r = self.api.delete(f'{BASE}/interventions/{iv.id}/')
        self.assertEqual(r.status_code, 204)
        self.assertFalse(Intervention.objects.filter(pk=iv.pk).exists())
        # Une seule ligne DELETE — jamais deux (TRACKED_MODELS + mixin).
        ct = ContentType.objects.get_for_model(Intervention)
        lignes = AuditLog.objects.filter(
            action=AuditLog.Action.DELETE, content_type=ct,
            object_id=str(iv.pk))
        self.assertEqual(lignes.count(), 1, list(lignes))

    def test_intervention_deja_couverte_par_tracked_models(self):
        """Preuve de la requalification (constat d'audit inexact sur ce point)."""
        self.assertIn(('installations', 'Intervention'), TRACKED_MODELS)

    # ── Fiche de recette IEC 62446-1 ────────────────────────────────────────
    def test_delete_recette_passee_refuse(self):
        """ROUGE avant AUD302 : 204, preuve de conformité détruite."""
        rec = CommissioningRecord.objects.create(
            company=self.company, installation=self.inst,
            resultat=CommissioningRecord.Resultat.CONFORME)
        self.assertTrue(rec.passe)
        r = self.api.delete(f'{BASE}/recettes-commissioning/{rec.id}/')
        self.assertEqual(r.status_code, 409, r.data)
        self.assertTrue(CommissioningRecord.objects.filter(pk=rec.pk).exists())

    def test_delete_recette_non_passee_permis_et_journalise(self):
        rec = CommissioningRecord.objects.create(
            company=self.company, installation=self.inst,
            resultat=CommissioningRecord.Resultat.NON_CONFORME)
        self.assertFalse(rec.passe)
        r = self.api.delete(f'{BASE}/recettes-commissioning/{rec.id}/')
        self.assertEqual(r.status_code, 204)
        ct = ContentType.objects.get_for_model(CommissioningRecord)
        self.assertEqual(
            AuditLog.objects.filter(
                action=AuditLog.Action.DELETE, content_type=ct,
                object_id=str(rec.pk)).count(), 1)

    # ── Preuve de livraison (POD) ───────────────────────────────────────────
    def _livraison(self):
        return Livraison.objects.create(
            company=self.company, reference=f'LIV-{next(_seq)}',
            installation=self.inst)

    def test_delete_pod_signee_refuse(self):
        """ROUGE avant AUD302 : 204, preuve de remise client détruite."""
        pod = PreuveLivraison.objects.create(
            company=self.company, livraison=self._livraison(),
            signataire_nom='Client', signature_data='base64:AAAA',
            horodatage=timezone.now())
        r = self.api.delete(f'{BASE}/preuves-livraison/{pod.id}/')
        self.assertEqual(r.status_code, 409, r.data)
        self.assertTrue(PreuveLivraison.objects.filter(pk=pod.pk).exists())

    def test_delete_pod_non_signee_permis_et_journalise(self):
        pod = PreuveLivraison.objects.create(
            company=self.company, livraison=self._livraison(),
            horodatage=timezone.now())
        r = self.api.delete(f'{BASE}/preuves-livraison/{pod.id}/')
        self.assertEqual(r.status_code, 204)
        ct = ContentType.objects.get_for_model(PreuveLivraison)
        self.assertEqual(
            AuditLog.objects.filter(
                action=AuditLog.Action.DELETE, content_type=ct,
                object_id=str(pod.pk)).count(), 1)
