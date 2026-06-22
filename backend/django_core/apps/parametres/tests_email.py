"""FG17 — tests des modèles d'e-mail éditables (EmailTemplate).

Couvre : CRUD, scoping société, company forcée côté serveur (jamais du corps),
persistance sujet + placeholders, liste effective (défauts fusionnés), upsert en
masse, validation des placeholders, fetch par clé (``get_template`` / ``render``)
et le verrou d'écriture (palier limité refusé)."""
from django.test import TestCase
from django.contrib.auth import get_user_model
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from authentication.models import Company
from apps.parametres.models_email import (
    EMAIL_TEMPLATE_DEFAULTS,
    EmailTemplate,
)

User = get_user_model()

BASE = '/api/django/parametres/email-templates/'


def _company(slug='mail-co', nom='Mail Co'):
    company, _ = Company.objects.get_or_create(slug=slug, defaults={'nom': nom})
    return company


def _auth(user):
    api = APIClient()
    token = str(AccessToken.for_user(user))
    api.credentials(HTTP_AUTHORIZATION=f'Bearer {token}')
    return api


class EmailTemplateApiTest(TestCase):
    def setUp(self):
        self.company = _company()
        self.admin = User.objects.create_user(
            username='mail_admin', password='x',
            role_legacy='admin', company=self.company)
        self.api = _auth(self.admin)

    # ── CRUD : créer puis relire ──────────────────────────────────────────
    def test_create_and_list(self):
        r = self.api.post(BASE, {
            'cle': 'devis',
            'sujet': 'Devis {reference}',
            'corps': 'Bonjour {civilite} {nom}, votre devis : {lien}',
        }, format='json')
        self.assertEqual(r.status_code, 201, r.data)
        obj = EmailTemplate.objects.get(id=r.data['id'])
        self.assertEqual(obj.cle, 'devis')
        self.assertEqual(obj.sujet, 'Devis {reference}')
        self.assertIn('{lien}', obj.corps)
        # Réapparaît dans la liste société.
        r2 = self.api.get(BASE)
        results = r2.data['results'] if 'results' in r2.data else r2.data
        self.assertEqual(len(results), 1)

    def test_update_persists_sujet_and_corps(self):
        r = self.api.post(BASE, {
            'cle': 'facture', 'sujet': 'A', 'corps': 'B'}, format='json')
        obj_id = r.data['id']
        r2 = self.api.patch(f'{BASE}{obj_id}/', {
            'sujet': 'Facture {reference}',
            'corps': 'Bonjour {nom}, facture : {lien}'}, format='json')
        self.assertEqual(r2.status_code, 200, r2.data)
        obj = EmailTemplate.objects.get(id=obj_id)
        self.assertEqual(obj.sujet, 'Facture {reference}')
        self.assertEqual(obj.corps, 'Bonjour {nom}, facture : {lien}')

    # ── company FORCÉE côté serveur (jamais lue du corps) ────────────────
    def test_company_forced_on_create(self):
        other = _company(slug='mail-evil', nom='Evil')
        r = self.api.post(BASE, {
            'cle': 'devis', 'sujet': 'X', 'corps': 'Y',
            'company': other.id}, format='json')
        self.assertEqual(r.status_code, 201, r.data)
        obj = EmailTemplate.objects.get(id=r.data['id'])
        # company = celle de l'utilisateur, JAMAIS celle du corps.
        self.assertEqual(obj.company_id, self.company.id)

    # ── Scoping société : une société ne voit pas l'autre ────────────────
    def test_company_scoped_list(self):
        self.api.post(BASE, {
            'cle': 'devis', 'sujet': 'Scopé', 'corps': 'x'}, format='json')
        other = _company(slug='mail-other', nom='Other')
        other_admin = User.objects.create_user(
            username='mail_other_admin', password='x',
            role_legacy='admin', company=other)
        api2 = _auth(other_admin)
        r = api2.get(BASE)
        results = r.data['results'] if 'results' in r.data else r.data
        self.assertEqual(len(results), 0)

    # ── Liste effective (défauts fusionnés avec la version société) ───────
    def test_effective_returns_defaults_then_overrides(self):
        r = self.api.get(BASE + 'effective/')
        self.assertEqual(r.status_code, 200)
        rows = {row['cle']: row for row in r.data['results']}
        # Liste complète == toutes les clés connues.
        self.assertEqual(set(rows), {c for c, _ in EmailTemplate.Cle.choices})
        # Sans surcharge : sujet/corps == défaut, non personnalisé.
        self.assertEqual(rows['devis']['sujet'],
                         EMAIL_TEMPLATE_DEFAULTS['devis']['sujet'])
        self.assertFalse(rows['devis']['personnalise'])
        # Avec surcharge : la version société remplace le défaut.
        self.api.post(BASE, {
            'cle': 'devis', 'sujet': 'Mon sujet {reference}',
            'corps': 'Mon corps {lien}'}, format='json')
        r2 = self.api.get(BASE + 'effective/')
        rows2 = {row['cle']: row for row in r2.data['results']}
        self.assertEqual(rows2['devis']['sujet'], 'Mon sujet {reference}')
        self.assertTrue(rows2['devis']['personnalise'])
        # Le défaut reste exposé (bouton « réinitialiser »).
        self.assertEqual(rows2['devis']['sujet_defaut'],
                         EMAIL_TEMPLATE_DEFAULTS['devis']['sujet'])

    # ── Upsert en masse (bulk) ───────────────────────────────────────────
    def test_bulk_upsert(self):
        r = self.api.put(BASE + 'bulk/', {
            'templates': [
                {'cle': 'devis', 'sujet': 'S1 {reference}', 'corps': 'C1'},
                {'cle': 'relance', 'sujet': 'S2', 'corps': 'C2 {lien}'},
                {'cle': 'inconnu', 'sujet': 'ignoré'},  # ignoré en silence
            ]}, format='json')
        self.assertEqual(r.status_code, 200, r.data)
        rows = {row['cle']: row for row in r.data['results']}
        self.assertEqual(rows['devis']['sujet'], 'S1 {reference}')
        self.assertEqual(rows['relance']['corps'], 'C2 {lien}')
        # La clé inconnue n'a PAS été créée.
        self.assertFalse(EmailTemplate.objects.filter(cle='inconnu').exists())

    # ── Validation des placeholders ──────────────────────────────────────
    def test_unknown_placeholder_rejected(self):
        r = self.api.post(BASE, {
            'cle': 'devis', 'sujet': 'Bonjour {inconnu}',
            'corps': 'x'}, format='json')
        self.assertEqual(r.status_code, 400)
        self.assertIn('sujet', r.data)

    def test_unknown_placeholder_rejected_in_bulk(self):
        r = self.api.put(BASE + 'bulk/', {
            'templates': [
                {'cle': 'devis', 'sujet': 'ok', 'corps': 'corps {bidon}'},
            ]}, format='json')
        self.assertEqual(r.status_code, 400)

    # ── Écriture réservée admin/responsable (pas le palier limité) ───────
    def test_write_forbidden_for_limited_role(self):
        viewer = User.objects.create_user(
            username='mail_viewer', password='x',
            role_legacy='normal', company=self.company)
        api2 = _auth(viewer)
        # Lecture OK.
        self.assertEqual(api2.get(BASE + 'effective/').status_code, 200)
        # Écriture refusée.
        r = api2.post(BASE, {
            'cle': 'devis', 'sujet': 'x', 'corps': 'y'}, format='json')
        self.assertEqual(r.status_code, 403)

    # ── La clé d'un modèle existant ne peut pas migrer ───────────────────
    def test_cannot_reassign_key(self):
        r = self.api.post(BASE, {
            'cle': 'devis', 'sujet': 'a', 'corps': 'b'}, format='json')
        obj_id = r.data['id']
        r2 = self.api.patch(f'{BASE}{obj_id}/', {
            'cle': 'facture'}, format='json')
        self.assertEqual(r2.status_code, 400)


class EmailTemplateHelperTest(TestCase):
    """FG17 — l'aide ``get_template`` / ``render`` (pour l'action e-mail future)."""

    def setUp(self):
        self.company = _company(slug='mail-helper', nom='Helper Co')

    def test_get_template_falls_back_to_default(self):
        tpl = EmailTemplate.get_template(self.company, 'devis')
        self.assertEqual(tpl['sujet'],
                         EMAIL_TEMPLATE_DEFAULTS['devis']['sujet'])
        self.assertEqual(tpl['corps'],
                         EMAIL_TEMPLATE_DEFAULTS['devis']['corps'])

    def test_get_template_uses_company_override(self):
        EmailTemplate.objects.create(
            company=self.company, cle='facture',
            sujet='Sujet société', corps='Corps société')
        tpl = EmailTemplate.get_template(self.company, 'facture')
        self.assertEqual(tpl['sujet'], 'Sujet société')
        self.assertEqual(tpl['corps'], 'Corps société')

    def test_get_template_blank_override_falls_back(self):
        # Une ligne avec sujet vide retombe sur le défaut (jamais un sujet vide).
        EmailTemplate.objects.create(
            company=self.company, cle='devis', sujet='', corps='')
        tpl = EmailTemplate.get_template(self.company, 'devis')
        self.assertEqual(tpl['sujet'],
                         EMAIL_TEMPLATE_DEFAULTS['devis']['sujet'])

    def test_render_substitutes_placeholders(self):
        out = EmailTemplate.render(
            self.company, 'devis',
            civilite='M.', nom='Kasri', reference='DV-1', lien='http://x')
        self.assertIn('DV-1', out['sujet'])
        self.assertIn('M.', out['corps'])
        self.assertIn('Kasri', out['corps'])
        self.assertIn('http://x', out['corps'])
        # Plus aucun token non substitué pour les placeholders fournis.
        self.assertNotIn('{reference}', out['sujet'])

    def test_render_leaves_unknown_tokens_intact(self):
        # Substitution tolérante : un token absent du contexte reste tel quel
        # (jamais de KeyError).
        EmailTemplate.objects.create(
            company=self.company, cle='notification',
            sujet='Sujet', corps='Bonjour {nom}, voir {reference}')
        out = EmailTemplate.render(self.company, 'notification', nom='Kasri')
        self.assertIn('Kasri', out['corps'])
        self.assertIn('{reference}', out['corps'])

    def test_get_template_no_company_returns_default(self):
        tpl = EmailTemplate.get_template(None, 'relance')
        self.assertEqual(tpl['sujet'],
                         EMAIL_TEMPLATE_DEFAULTS['relance']['sujet'])
