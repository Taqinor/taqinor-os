"""XPLT19 — Accès multi-sociétés + sélecteur de société active.

Vérifie que :
* un utilisateur bi-société bascule (``/auth/switch-company/``) et voit alors
  les données de CHAQUE entité séparément (isolation stricte après switch) ;
* un mono-société ne peut PAS switcher (403) ;
* aucune fuite cross-société dans les listes après switch ;
* le comportement d'un compte mono-société existant est byte-identique
  (``company`` d'attache conservée, sélecteur à un seul élément).
"""
from rest_framework_simplejwt.tokens import RefreshToken

from testkit.base import TenantAPITestCase
from testkit.factories import (
    CompanyFactory, UserFactory, ClientFactory,
)
from authentication.active_company import ACTIVE_COMPANY_CLAIM


def _role(company, nom):
    """Rôle système canonique ``nom`` de ``company`` (comme la sonde C-APFS-064)."""
    from apps.roles.models import Role
    from apps.roles.permissions_registre import CANONICAL_SYSTEM_ROLES
    perms = list(dict(CANONICAL_SYSTEM_ROLES)[nom])
    return Role.objects.get_or_create(company=company, nom=nom,
                                      defaults={'permissions': perms, 'est_systeme': True})[0]


def _client_with_active(user, active_company_id=None):
    """APIClient portant un access token dont le claim ``active_company_id`` est
    posé (comme après un switch). Sans ``active_company_id``, comportement
    identique à ``AccessToken.for_user`` (société d'attache)."""
    from rest_framework.test import APIClient
    refresh = RefreshToken.for_user(user)
    access = refresh.access_token
    if active_company_id is not None:
        access[ACTIVE_COMPANY_CLAIM] = active_company_id
    api = APIClient()
    api.credentials(HTTP_AUTHORIZATION=f'Bearer {access}')
    return api


class SwitchCompanyApiTest(TenantAPITestCase):
    def setUp(self):
        super().setUp()
        # Société A = self.company (d'attache) ; société B = seconde entité.
        self.company_b = CompanyFactory(nom='Entité B', slug='entite-b')
        # Utilisateur bi-société : attaché à A, membre de A + B.
        self.bi_user = UserFactory(
            username='reda-bi', company=self.company,
            # Rôle écrivain requis : la création de clients CRM exige le rôle
            # responsable quel que soit le multi-société (le 403 sans lui n'a
            # rien à voir avec le switch).
            role_legacy='responsable',
        )
        self.bi_user.societes_autorisees.add(self.company)
        # APFS66 (D-APFS-3) — un rôle DANS B est exigé pour y basculer. Rôle
        # « Responsable » (aucun marqueur de portée) : le « Commercial » ne voit
        # que SES enregistrements, ce qui masquerait ClientB (fabrique nue).
        self.bi_user.societes_autorisees.add(
            self.company_b, through_defaults={'role': _role(self.company_b, 'Responsable')})
        # Données distinctes par société.
        self.client_a = ClientFactory(company=self.company, nom='ClientA')
        self.client_b = ClientFactory(company=self.company_b, nom='ClientB')

    # ── Bascule autorisée + isolation par entité ──────────────────────────────
    def test_bi_societe_switch_puis_voit_chaque_entite_separement(self):
        api = _client_with_active(self.bi_user)
        # Par défaut (pas de switch) → société d'attache A : voit ClientA seul.
        r = api.get('/api/django/crm/clients/')
        self.assertEqual(r.status_code, 200)
        noms = {c['nom'] for c in r.data.get('results', r.data)}
        self.assertIn('ClientA', noms)
        self.assertNotIn('ClientB', noms)

        # Switch vers B.
        r = api.post('/api/django/auth/switch-company/',
                     {'company_id': self.company_b.id}, format='json')
        self.assertEqual(r.status_code, 200, r.data)
        self.assertEqual(r.data['company_id'], self.company_b.id)

        # Rejoue avec un jeton portant la société active B.
        api_b = _client_with_active(self.bi_user, self.company_b.id)
        r = api_b.get('/api/django/crm/clients/')
        self.assertEqual(r.status_code, 200)
        noms = {c['nom'] for c in r.data.get('results', r.data)}
        self.assertIn('ClientB', noms)
        self.assertNotIn('ClientA', noms)

    def test_switch_pose_company_active_sur_la_requete(self):
        api_b = _client_with_active(self.bi_user, self.company_b.id)
        r = api_b.get('/api/django/auth/me/')
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.data['active_company_id'], self.company_b.id)
        ids = {s['id'] for s in r.data['societes_operables']}
        self.assertEqual(ids, {self.company.id, self.company_b.id})

    # ── Garde d'appartenance stricte ──────────────────────────────────────────
    def test_mono_societe_ne_peut_pas_switcher(self):
        # self.user est mono-société (backfill = {self.company}).
        self.user.societes_autorisees.add(self.company)
        api = _client_with_active(self.user)
        r = api.post('/api/django/auth/switch-company/',
                     {'company_id': self.company_b.id}, format='json')
        self.assertEqual(r.status_code, 403)

    def test_bascule_refusee_sans_role_dans_la_societe(self):
        """APFS66 (C-APFS-064) — Administrateur de A membre de B sans rôle dans B."""
        from apps.crm.models import Lead
        from authentication.models import AppartenanceSociete
        role_a = _role(self.company, 'Administrateur')
        x = UserFactory(username='apfs66-adm-a', company=self.company, role=role_a, role_legacy='admin')
        x.societes_autorisees.add(self.company, self.company_b)
        adm_b = UserFactory(username='apfs66-adm-b', company=self.company_b,
                            role=_role(self.company_b, 'Administrateur'), role_legacy='admin')
        r = _client_with_active(x).post('/api/django/auth/switch-company/',
                                        {'company_id': self.company_b.id}, format='json')
        self.assertEqual(r.status_code, 403, r.data)
        self.assertIn('detail', r.data)
        # Jeton forgé revendiquant B : repli sur A, aucun lead créé dans B.
        api_b = _client_with_active(x, self.company_b.id)
        api_b.post('/api/django/crm/leads/', {'nom': 'Lead APFS66'}, format='json')
        self.assertFalse(Lead.objects.filter(company=self.company_b, nom='Lead APFS66').exists())
        # Avec le rôle « Commercial » de B : bascule 200, users/ 403 (droits Commercial).
        AppartenanceSociete.objects.filter(user=x, company=self.company_b).update(
            role=_role(self.company_b, 'Commercial'))
        r = _client_with_active(x).post('/api/django/auth/switch-company/',
                                        {'company_id': self.company_b.id}, format='json')
        self.assertEqual(r.status_code, 200, r.data)
        self.assertEqual(api_b.get('/api/django/users/').status_code, 403)
        # L'Administrateur de B voit X parmi ses membres.
        r = _client_with_active(adm_b).get('/api/django/users/?page_size=200')
        self.assertEqual(r.status_code, 200)
        self.assertIn(x.id, {u['id'] for u in r.data.get('results', r.data)})
        # Persistance : l'appartenance porte le rôle de B ; le rôle d'attache est inchangé.
        lien = AppartenanceSociete.objects.get(user=x, company=self.company_b)
        self.assertEqual(lien.role.company_id, self.company_b.id)
        x.refresh_from_db()
        self.assertEqual(x.role_id, role_a.id)

    def test_enf11_switch_corps_invalide_400_pas_500(self):
        api = _client_with_active(self.bi_user)
        for corps in ([None, None], {}, {'company_id': 'abc'},
                      {'company_id': 10 ** 30}):
            r = api.post('/api/django/auth/switch-company/', corps, format='json')
            self.assertEqual(r.status_code, 400, (corps, r.content))

    def test_switch_vers_societe_non_membre_refuse(self):
        # bi_user n'est PAS membre de other_company.
        api = _client_with_active(self.bi_user)
        r = api.post('/api/django/auth/switch-company/',
                     {'company_id': self.other_company.id}, format='json')
        self.assertEqual(r.status_code, 403)

    def test_claim_non_autorise_ne_change_pas_la_societe(self):
        # Un jeton forgé revendiquant other_company (non membre) DOIT retomber
        # sur la société d'attache — aucune fuite.
        api = _client_with_active(self.bi_user, self.other_company.id)
        r = api.get('/api/django/crm/clients/')
        self.assertEqual(r.status_code, 200)
        noms = {c['nom'] for c in r.data.get('results', r.data)}
        # Retombe sur A (attache) : voit ClientA, jamais les données d'un tiers.
        self.assertIn('ClientA', noms)
        self.assertNotIn('ClientB', noms)

    # ── Rétrocompatibilité mono-société (byte-identique) ──────────────────────
    def test_mono_societe_comportement_inchange(self):
        api = _client_with_active(self.user)
        r = api.get('/api/django/auth/me/')
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.data['active_company_id'], self.company.id)
        # Sans backfill M2M explicite, societes_operables ⊇ {company d'attache}.
        ids = {s['id'] for s in r.data['societes_operables']}
        self.assertIn(self.company.id, ids)

    def test_switch_journalise_dans_audit(self):
        from apps.audit.models import AuditLog
        api = _client_with_active(self.bi_user)
        api.post('/api/django/auth/switch-company/',
                 {'company_id': self.company_b.id}, format='json')
        log = AuditLog.objects.filter(
            action=AuditLog.Action.SWITCH_COMPANY,
            user=self.bi_user, company=self.company_b).first()
        self.assertIsNotNone(log)

    # ── perform_create borne à la société active ──────────────────────────────
    def test_creation_scopee_a_la_societe_active(self):
        api_b = _client_with_active(self.bi_user, self.company_b.id)
        r = api_b.post('/api/django/crm/clients/',
                       {'nom': 'NouveauB', 'prenom': 'X',
                        'email': 'nouveaub@example.com',
                        'telephone': '+212600000001'}, format='json')
        self.assertIn(r.status_code, (200, 201), getattr(r, 'data', None))
        from apps.crm.models import Client
        cree = Client.objects.get(nom='NouveauB')
        # Créé DANS la société active B, jamais la société d'attache A.
        self.assertEqual(cree.company_id, self.company_b.id)


class ActiveCompanyResolutionUnitTest(TenantAPITestCase):
    """Tests unitaires du résolveur (défenses sans HTTP)."""

    def test_user_can_operate_home_et_m2m(self):
        from authentication.active_company import user_can_operate
        b = CompanyFactory(nom='B2', slug='b2')
        u = UserFactory(username='u-multi', company=self.company)
        u.societes_autorisees.add(self.company, b)
        self.assertTrue(user_can_operate(u, self.company.id))
        self.assertTrue(user_can_operate(u, b.id))
        self.assertFalse(user_can_operate(u, self.other_company.id))

    def test_resolve_repli_sur_home_si_non_membre(self):
        from authentication.active_company import resolve_active_company
        u = UserFactory(username='u-mono', company=self.company)
        active = resolve_active_company(u, self.other_company.id)
        self.assertEqual(active.id, self.company.id)
