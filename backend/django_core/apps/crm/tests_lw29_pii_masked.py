"""LW29 — ``pii_masked`` : le masquage PII devient VISIBLE au lieu de
silencieux.

``LeadSerializer`` masque déjà telephone/email/adresse/whatsapp/gps pour les
utilisateurs sans ``can_view_client_pii`` (force read_only + null, drop
silencieux au PATCH — recon 02 §6). Ce test couvre le champ calculé
``pii_masked`` pour les DEUX profils : un rôle sans ``client_pii_voir`` doit
voir ``pii_masked: true`` + les champs PII à ``null`` ; un admin (repli
historique légacy) doit voir ``pii_masked: false`` + les valeurs réelles."""
from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from authentication.models import Company
from apps.crm.models import Lead
from apps.roles.models import Role

User = get_user_model()


def _company(slug='lw29-co', nom='LW29 Co'):
    company, _ = Company.objects.get_or_create(slug=slug, defaults={'nom': nom})
    return company


def _api(user):
    api = APIClient()
    api.credentials(HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(user)}')
    return api


class PiiMaskedFieldTests(TestCase):
    def setUp(self):
        self.company = _company()
        self.role_no_pii = Role.objects.create(
            company=self.company, nom='LW29 sans PII',
            permissions=['crm_voir'])
        self.role_pii = Role.objects.create(
            company=self.company, nom='LW29 avec PII',
            permissions=['crm_voir', 'client_pii_voir'])
        self.lead = Lead.objects.create(
            company=self.company, nom='LW29 Lead',
            telephone='0612345678', email='lead@example.com',
            adresse='12 rue du Soleil')

    def _detail_url(self):
        return f'/api/django/crm/leads/{self.lead.id}/'

    def test_pii_masked_true_and_telephone_null_without_permission(self):
        u = User.objects.create_user(
            username='lw29_masked', password='x',
            role=self.role_no_pii, company=self.company)
        resp = _api(u).get(self._detail_url())
        self.assertEqual(resp.status_code, 200, resp.data)
        self.assertTrue(resp.data['pii_masked'])
        self.assertIsNone(resp.data['telephone'])
        self.assertIsNone(resp.data['email'])
        self.assertIsNone(resp.data['adresse'])
        # Le nom (non-PII) reste visible.
        self.assertEqual(resp.data['nom'], 'LW29 Lead')

    def test_pii_masked_false_and_values_visible_with_permission(self):
        u = User.objects.create_user(
            username='lw29_visible', password='x',
            role=self.role_pii, company=self.company)
        resp = _api(u).get(self._detail_url())
        self.assertEqual(resp.status_code, 200, resp.data)
        self.assertFalse(resp.data['pii_masked'])
        self.assertEqual(resp.data['telephone'], '0612345678')
        self.assertEqual(resp.data['email'], 'lead@example.com')

    def test_pii_masked_false_for_legacy_admin_account(self):
        # Compte légacy sans rôle fin → repli historique (accès complet).
        u = User.objects.create_user(
            username='lw29_legacy', password='x', role_legacy='admin',
            company=self.company)
        resp = _api(u).get(self._detail_url())
        self.assertEqual(resp.status_code, 200, resp.data)
        self.assertFalse(resp.data['pii_masked'])
        self.assertEqual(resp.data['telephone'], '0612345678')

    def test_pii_masked_present_on_list_endpoint_too(self):
        # pii_masked (contrairement à chatter_recent) n'est PAS gated par
        # retrieve() — il doit rester cohérent sur la liste également.
        u = User.objects.create_user(
            username='lw29_list', password='x',
            role=self.role_no_pii, company=self.company)
        resp = _api(u).get('/api/django/crm/leads/')
        self.assertEqual(resp.status_code, 200, resp.data)
        rows = resp.data['results'] if 'results' in resp.data else resp.data
        self.assertTrue(all(row['pii_masked'] for row in rows))


class ChatterPiiMasqueTests(TestCase):
    """CRX19 — le CHATTER respecte LW29 sur ses TROIS surfaces.

    La fiche masquait déjà telephone/email/adresse/whatsapp/gps, mais
    l'historique recopiait la valeur en clair dans ``old_value``/``new_value``
    (« telephone : 0612345678 → 0698765432 ») : le masquage de la fiche ne
    valait rien. Le masquage vit désormais dans ``LeadActivitySerializer``,
    donc PAR CONSTRUCTION sur l'action ``historique``, sur ``chatter_recent``
    embarqué au retrieve, et sur l'enveloppe uniforme ARC9.
    """

    ANCIEN = '0612345678'
    NOUVEAU = '0698765432'
    MASQUE = '•••'

    def setUp(self):
        self.company = _company(slug='crx19-co', nom='CRX19 Co')
        self.role_sans_pii = Role.objects.create(
            company=self.company, nom='CRX19 sans PII',
            permissions=['crm_voir'])
        self.role_avec_pii = Role.objects.create(
            company=self.company, nom='CRX19 avec PII',
            permissions=['crm_voir', 'client_pii_voir'])
        self.role_sans_crm = Role.objects.create(
            company=self.company, nom='CRX19 hors CRM',
            permissions=['ventes_voir'])
        self.lead = Lead.objects.create(
            company=self.company, nom='CRX19 Lead',
            telephone=self.NOUVEAU)

        from apps.crm.models import LeadActivity
        self.activite_pii = LeadActivity.objects.create(
            lead=self.lead, company=self.company,
            kind=LeadActivity.Kind.MODIFICATION, field='telephone',
            field_label='Téléphone',
            old_value=self.ANCIEN, new_value=self.NOUVEAU)
        self.activite_neutre = LeadActivity.objects.create(
            lead=self.lead, company=self.company,
            kind=LeadActivity.Kind.MODIFICATION, field='stage',
            field_label='Étape', old_value='Nouveau', new_value='Contacté')

    def _user(self, username, role):
        return User.objects.create_user(
            username=username, password='x', role=role, company=self.company)

    def _entree(self, rows, activite_id):
        return next(r for r in rows if r['id'] == activite_id)

    # ── Surface 1 : action ``historique`` ──────────────────────────────────

    def test_historique_masque_les_valeurs_pii(self):
        u = self._user('crx19_hist_masque', self.role_sans_pii)
        resp = _api(u).get(f'/api/django/crm/leads/{self.lead.id}/historique/')
        self.assertEqual(resp.status_code, 200, resp.data)
        entree = self._entree(resp.data, self.activite_pii.id)
        self.assertEqual(entree['old_value'], self.MASQUE)
        self.assertEqual(entree['new_value'], self.MASQUE)
        self.assertNotIn(self.ANCIEN, str(resp.data))
        self.assertNotIn(self.NOUVEAU, str(resp.data))

    def test_historique_laisse_voir_avec_la_permission(self):
        u = self._user('crx19_hist_visible', self.role_avec_pii)
        resp = _api(u).get(f'/api/django/crm/leads/{self.lead.id}/historique/')
        self.assertEqual(resp.status_code, 200, resp.data)
        entree = self._entree(resp.data, self.activite_pii.id)
        self.assertEqual(entree['old_value'], self.ANCIEN)
        self.assertEqual(entree['new_value'], self.NOUVEAU)

    def test_historique_ne_masque_pas_un_champ_non_pii(self):
        u = self._user('crx19_hist_neutre', self.role_sans_pii)
        resp = _api(u).get(f'/api/django/crm/leads/{self.lead.id}/historique/')
        entree = self._entree(resp.data, self.activite_neutre.id)
        self.assertEqual(entree['old_value'], 'Nouveau')
        self.assertEqual(entree['new_value'], 'Contacté')

    def test_historique_exige_crm_voir(self):
        """Elle était ouverte à TOUT porteur de rôle (``IsAnyRole``) alors
        qu'elle sert l'historique complet d'un lead."""
        u = self._user('crx19_hist_hors_crm', self.role_sans_crm)
        resp = _api(u).get(f'/api/django/crm/leads/{self.lead.id}/historique/')
        self.assertEqual(resp.status_code, 403, getattr(resp, 'data', resp))

    # ── Surface 2 : ``chatter_recent`` embarqué au retrieve ────────────────

    def test_chatter_recent_masque_les_valeurs_pii(self):
        u = self._user('crx19_chatter_masque', self.role_sans_pii)
        resp = _api(u).get(f'/api/django/crm/leads/{self.lead.id}/')
        self.assertEqual(resp.status_code, 200, resp.data)
        self.assertIn('chatter_recent', resp.data)
        entree = self._entree(resp.data['chatter_recent'],
                              self.activite_pii.id)
        self.assertEqual(entree['old_value'], self.MASQUE)
        self.assertEqual(entree['new_value'], self.MASQUE)

    def test_chatter_recent_visible_avec_la_permission(self):
        u = self._user('crx19_chatter_visible', self.role_avec_pii)
        resp = _api(u).get(f'/api/django/crm/leads/{self.lead.id}/')
        entree = self._entree(resp.data['chatter_recent'],
                              self.activite_pii.id)
        self.assertEqual(entree['old_value'], self.ANCIEN)

    # ── Surface 3 : enveloppe uniforme ARC9 ────────────────────────────────

    def test_enveloppe_arc9_masque_pour_un_role_sans_pii(self):
        from apps.crm.selectors import lead_chatter_envelope
        u = self._user('crx19_env_masque', self.role_sans_pii)
        rows = lead_chatter_envelope(self.lead, user=u)
        entree = self._entree(rows, self.activite_pii.id)
        self.assertEqual(entree['old_value'], self.MASQUE)
        self.assertEqual(entree['new_value'], self.MASQUE)

    def test_enveloppe_arc9_intacte_avec_la_permission(self):
        from apps.crm.selectors import lead_chatter_envelope
        u = self._user('crx19_env_visible', self.role_avec_pii)
        entree = self._entree(
            lead_chatter_envelope(self.lead, user=u), self.activite_pii.id)
        self.assertEqual(entree['old_value'], self.ANCIEN)

    def test_enveloppe_arc9_sans_utilisateur_reste_historique(self):
        """Appel INTERNE (aucune requête) : rendu strictement inchangé."""
        from apps.crm.selectors import lead_chatter_envelope
        entree = self._entree(
            lead_chatter_envelope(self.lead), self.activite_pii.id)
        self.assertEqual(entree['old_value'], self.ANCIEN)
        self.assertEqual(entree['new_value'], self.NOUVEAU)

    # ── Source unique des champs PII ───────────────────────────────────────

    def test_une_seule_liste_de_champs_pii(self):
        from apps.crm.serializers import LEAD_PII_FIELDS, LeadSerializer
        self.assertIs(LeadSerializer.PII_FIELDS, LEAD_PII_FIELDS)
        self.assertEqual(len(LEAD_PII_FIELDS), 6)
