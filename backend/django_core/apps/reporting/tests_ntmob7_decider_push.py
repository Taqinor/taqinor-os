"""NTMOB7 — approbation en un geste depuis une notification push.

Couvre l'endpoint ``POST reporting/approbations-en-attente/decider-push/``
(AllowAny délibéré — la preuve d'identité + de décision est le jeton signé,
pas la session HTTP) : décision d'un item de l'agrégateur existant (source
``automation``, ré-utilise ``_decider_approbation_core`` inchangé) ET la
nouvelle catégorie ``notes_frais`` (hors agrégateur de LECTURE, mais bien
décidable ici). Le round-trip du jeton lui-même (``apps.notifications.
approval_tokens``) est couvert dans ``apps/notifications/tests_ntmob7_*``."""
from datetime import date
from decimal import Decimal

from django.test import TestCase
from rest_framework.test import APIClient

from apps.automation.models import AutomationApproval
from apps.compta import services as compta_services
from apps.frais.models import NoteFrais
from apps.notifications.approval_tokens import make_approval_token
from authentication.models import Company, CustomUser


def _make_company(slug, nom):
    return Company.objects.get_or_create(slug=slug, defaults={'nom': nom})[0]


def _make_user(company, username, **kw):
    return CustomUser.objects.create_user(
        username=username, password='x', company=company, **kw)


class DeciderApprobationViaPushTests(TestCase):
    def setUp(self):
        self.company = _make_company('ntmob7-co', 'NTMOB7 Co')
        self.other_company = _make_company('ntmob7-other', 'NTMOB7 Other')
        # normal role_legacy → PAS compta_valider (repli HasPermissionOrLegacy
        # sans rôle fin : is_responsable seulement pour responsable/admin).
        self.user = _make_user(self.company, 'ntmob7-u', role_legacy='normal')
        self.resp_user = _make_user(
            self.company, 'ntmob7-resp', role_legacy='responsable')
        # AllowAny délibéré : le client n'a besoin d'AUCUNE authentification —
        # le jeton signé porte tout.
        self.api = APIClient()

    def _url(self):
        return '/api/django/reporting/approbations-en-attente/decider-push/'

    def test_approve_automation_via_token_without_any_session(self):
        approval = AutomationApproval.objects.create(
            company=self.company, status=AutomationApproval.Status.PENDING)
        token = make_approval_token(
            self.user.id, 'automation', approval.id, 'approuver')
        resp = self.api.post(self._url(), {'token': token}, format='json')
        self.assertEqual(resp.status_code, 200)
        approval.refresh_from_db()
        self.assertEqual(approval.status, AutomationApproval.Status.APPROVED)
        self.assertEqual(approval.decided_by_id, self.user.id)

    def test_reject_automation_needs_no_motif_in_body(self):
        # NTMOB7 — contrairement à `decider/` (motif obligatoire pour un
        # refus), le refus via push fonctionne SANS aucun motif dans le
        # corps : le jeton fournit un motif automatique (pas de nouvelle UI).
        approval = AutomationApproval.objects.create(
            company=self.company, status=AutomationApproval.Status.PENDING)
        token = make_approval_token(
            self.user.id, 'automation', approval.id, 'refuser')
        resp = self.api.post(self._url(), {'token': token}, format='json')
        self.assertEqual(resp.status_code, 200)
        approval.refresh_from_db()
        self.assertEqual(approval.status, AutomationApproval.Status.REJECTED)

    def test_decision_field_in_body_is_ignored(self):
        # La décision vit UNIQUEMENT dans le jeton scellé — un corps qui tente
        # d'en injecter une autre n'a strictement aucun effet.
        approval = AutomationApproval.objects.create(
            company=self.company, status=AutomationApproval.Status.PENDING)
        token = make_approval_token(
            self.user.id, 'automation', approval.id, 'refuser')
        resp = self.api.post(
            self._url(), {'token': token, 'decision': 'approuver'},
            format='json')
        self.assertEqual(resp.status_code, 200)
        approval.refresh_from_db()
        self.assertEqual(approval.status, AutomationApproval.Status.REJECTED)

    def test_invalid_token_401(self):
        resp = self.api.post(
            self._url(), {'token': 'not-a-real-token'}, format='json')
        self.assertEqual(resp.status_code, 401)

    def test_missing_token_401(self):
        resp = self.api.post(self._url(), {}, format='json')
        self.assertEqual(resp.status_code, 401)

    def test_token_for_unknown_user_401(self):
        token = make_approval_token(999999, 'automation', 1, 'approuver')
        resp = self.api.post(self._url(), {'token': token}, format='json')
        self.assertEqual(resp.status_code, 401)

    def test_token_for_inactive_user_401(self):
        self.user.is_active = False
        self.user.save(update_fields=['is_active'])
        approval = AutomationApproval.objects.create(
            company=self.company, status=AutomationApproval.Status.PENDING)
        token = make_approval_token(
            self.user.id, 'automation', approval.id, 'approuver')
        resp = self.api.post(self._url(), {'token': token}, format='json')
        self.assertEqual(resp.status_code, 401)

    def test_token_for_item_in_another_company_404(self):
        approval = AutomationApproval.objects.create(
            company=self.other_company,
            status=AutomationApproval.Status.PENDING)
        token = make_approval_token(
            self.user.id, 'automation', approval.id, 'approuver')
        resp = self.api.post(self._url(), {'token': token}, format='json')
        self.assertEqual(resp.status_code, 404)
        approval.refresh_from_db()
        self.assertEqual(approval.status, AutomationApproval.Status.PENDING)

    def test_unknown_source_400(self):
        token = make_approval_token(self.user.id, 'bogus_source', 1, 'approuver')
        resp = self.api.post(self._url(), {'token': token}, format='json')
        self.assertEqual(resp.status_code, 400)


class DeciderNotesFraisViaPushTests(TestCase):
    """NTMOB7 — 'notes_frais' : catégorie hors agrégateur de LECTURE
    (``reporting.approbations``) mais décidable ici, même garde de
    permission (``compta_valider``) que ``NoteFraisViewSet.valider/rejeter``,
    reconstruite sans objet ``request``."""

    def setUp(self):
        self.company = _make_company('ntmob7-frais-co', 'NTMOB7 Frais Co')
        compta_services.seed_plan_comptable(self.company)
        compta_services.seed_journaux(self.company)
        self.employe = _make_user(
            self.company, 'ntmob7-frais-emp', role_legacy='normal')
        self.resp_user = _make_user(
            self.company, 'ntmob7-frais-resp', role_legacy='responsable')
        self.api = APIClient()

    def _url(self):
        return '/api/django/reporting/approbations-en-attente/decider-push/'

    def _note(self, statut=NoteFrais.Statut.SOUMISE):
        return NoteFrais.objects.create(
            company=self.company, employe=self.employe,
            date_frais=date(2026, 1, 10), montant=Decimal('150.00'),
            motif='Déplacement chantier', statut=statut)

    def test_approve_requires_compta_valider_permission(self):
        # role_legacy='normal' sans rôle fin → PAS is_responsable → 403.
        note = self._note()
        token = make_approval_token(
            self.employe.id, 'notes_frais', note.id, 'approuver')
        resp = self.api.post(self._url(), {'token': token}, format='json')
        self.assertEqual(resp.status_code, 403)
        note.refresh_from_db()
        self.assertEqual(note.statut, NoteFrais.Statut.SOUMISE)

    def test_responsable_can_approve(self):
        note = self._note()
        token = make_approval_token(
            self.resp_user.id, 'notes_frais', note.id, 'approuver')
        resp = self.api.post(self._url(), {'token': token}, format='json')
        self.assertEqual(resp.status_code, 200)
        note.refresh_from_db()
        self.assertEqual(note.statut, NoteFrais.Statut.VALIDEE)
        self.assertEqual(note.valide_par_id, self.resp_user.id)

    def test_responsable_can_reject_with_automatic_motif(self):
        note = self._note()
        token = make_approval_token(
            self.resp_user.id, 'notes_frais', note.id, 'refuser')
        resp = self.api.post(self._url(), {'token': token}, format='json')
        self.assertEqual(resp.status_code, 200)
        note.refresh_from_db()
        self.assertEqual(note.statut, NoteFrais.Statut.REJETEE)
        self.assertEqual(note.motif_rejet, 'Refusé depuis une notification push.')

    def test_note_from_another_company_404(self):
        other_co = _make_company('ntmob7-frais-other', 'NTMOB7 Frais Other')
        compta_services.seed_plan_comptable(other_co)
        compta_services.seed_journaux(other_co)
        other_employe = _make_user(other_co, 'ntmob7-frais-other-emp')
        note = NoteFrais.objects.create(
            company=other_co, employe=other_employe,
            date_frais=date(2026, 1, 10), montant=Decimal('50.00'),
            motif='Autre société', statut=NoteFrais.Statut.SOUMISE)
        token = make_approval_token(
            self.resp_user.id, 'notes_frais', note.id, 'approuver')
        resp = self.api.post(self._url(), {'token': token}, format='json')
        self.assertEqual(resp.status_code, 404)

    def test_already_validated_note_stays_validee_idempotent(self):
        note = self._note(statut=NoteFrais.Statut.VALIDEE)
        token = make_approval_token(
            self.resp_user.id, 'notes_frais', note.id, 'approuver')
        resp = self.api.post(self._url(), {'token': token}, format='json')
        self.assertEqual(resp.status_code, 200)
        note.refresh_from_db()
        self.assertEqual(note.statut, NoteFrais.Statut.VALIDEE)
