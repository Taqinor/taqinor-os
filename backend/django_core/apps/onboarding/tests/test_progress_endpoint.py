"""NTDMO13 — endpoint checklist « Premiers pas » + action ignorer."""
from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient

from authentication.models import Company
from apps.onboarding.models import OnboardingChecklistItem
from apps.onboarding.services import marquer_item_complete
from apps.roles.models import Role

User = get_user_model()


class OnboardingProgressEndpointTest(TestCase):
    def setUp(self):
        self.company = Company.objects.create(nom='Co', slug='co-pe')
        # La checklist est filtrée par RÔLE (``roles_cibles`` du catalogue,
        # comparé au ``roles.Role.nom`` de l'utilisateur — cf.
        # test_models.test_role_targeting_differs_between_users). Sans Role
        # assigné, ``role_legacy`` vaut 'normal' et NE matche aucun
        # ``roles_cibles`` : l'utilisateur ne verrait que « import_clients »
        # (seul item à cible vide). On assigne donc « Administrateur », le seul
        # nom présent dans les 5 items ciblés, pour que les tests portent bien
        # sur les 6 items du catalogue.
        self.role_admin = Role.objects.create(
            company=self.company, nom='Administrateur')
        self.u1 = User.objects.create_user(
            'u1', password='x', company=self.company, role=self.role_admin)
        self.u2 = User.objects.create_user(
            'u2', password='x', company=self.company, role=self.role_admin)

    def _client(self, user):
        c = APIClient()
        c.force_authenticate(user)
        return c

    def test_list_returns_checklist_with_summary(self):
        resp = self._client(self.u1).get('/api/django/onboarding/progress/')
        self.assertEqual(resp.status_code, 200)
        self.assertIn('items', resp.data)
        self.assertIn('pourcentage', resp.data)
        self.assertGreater(resp.data['total'], 0)

    def test_progress_differs_per_user(self):
        marquer_item_complete(self.company, self.u1, 'import_clients')
        r1 = self._client(self.u1).get('/api/django/onboarding/progress/')
        r2 = self._client(self.u2).get('/api/django/onboarding/progress/')
        self.assertGreater(r1.data['faits'], r2.data['faits'])

    def test_progress_persists_across_sessions(self):
        marquer_item_complete(self.company, self.u1, 'import_clients')
        # « reconnexion » = nouveau client authentifié.
        r = self._client(self.u1).get('/api/django/onboarding/progress/')
        done = [it for it in r.data['items']
                if it['key'] == 'import_clients']
        self.assertTrue(done and done[0]['fait'])

    def test_ignorer_hides_item_persistently(self):
        item = OnboardingChecklistItem.objects.get(key='import_clients')
        c = self._client(self.u1)
        c.post(f'/api/django/onboarding/progress/{item.id}/ignorer/')
        r = c.get('/api/django/onboarding/progress/')
        keys = {it['key'] for it in r.data['items']}
        self.assertNotIn('import_clients', keys)

    def test_ignorer_tout_marks_termine(self):
        c = self._client(self.u1)
        c.post('/api/django/onboarding/progress/ignorer-tout/')
        r = c.get('/api/django/onboarding/progress/')
        self.assertTrue(r.data['termine'])

    # ── WIR59 ────────────────────────────────────────────────────────────
    def test_list_exposes_event_key_per_item(self):
        r = self._client(self.u1).get('/api/django/onboarding/progress/')
        by_key = {it['key']: it['event_key'] for it in r.data['items']}
        self.assertEqual(by_key['premier_devis'], 'devis')
        self.assertEqual(by_key['premier_paiement'], 'paiement')
        self.assertEqual(by_key['premier_chantier'], 'chantier')
        self.assertEqual(by_key['configurer_societe'], '')
        self.assertEqual(by_key['import_clients'], '')
        self.assertEqual(by_key['inviter_coequipier'], '')

    def test_marquer_fait_completes_item_without_event(self):
        item = OnboardingChecklistItem.objects.get(key='configurer_societe')
        c = self._client(self.u1)
        r = c.post(f'/api/django/onboarding/progress/{item.id}/marquer-fait/')
        self.assertEqual(r.status_code, 200)
        done = [it for it in r.data['items'] if it['key'] == 'configurer_societe']
        self.assertTrue(done and done[0]['fait'])

    def test_marquer_fait_is_idempotent(self):
        item = OnboardingChecklistItem.objects.get(key='inviter_coequipier')
        c = self._client(self.u1)
        c.post(f'/api/django/onboarding/progress/{item.id}/marquer-fait/')
        r = c.post(f'/api/django/onboarding/progress/{item.id}/marquer-fait/')
        self.assertEqual(r.status_code, 200)
        done = [it for it in r.data['items'] if it['key'] == 'inviter_coequipier']
        self.assertTrue(done and done[0]['fait'])

    def test_schema_du_resume_est_un_objet_pas_un_tableau(self):
        """api-fuzz « Response violates schema » : ``list`` rend le résumé
        (UN objet) ; drf-spectacular l'enveloppait dans un tableau."""
        from django.urls import include, path
        from drf_spectacular.generators import SchemaGenerator
        schema = SchemaGenerator(patterns=[path(
            'api/django/onboarding/', include('apps.onboarding.urls'))]
        ).get_schema(request=None, public=True)
        reponse = schema['paths']['/api/django/onboarding/progress/']['get'][
            'responses']['200']['content']['application/json']['schema']
        self.assertEqual(reponse['$ref'].rsplit('/', 1)[-1],
                         'ViewsOnboardingProgressViewSetListReponse')


class OnboardingResumePublicNTDMO35Test(TestCase):
    """NTDMO35 — pourcentage agrégé, clé API à scope restreint."""

    def setUp(self):
        from apps.publicapi.models import ApiKey
        from apps.publicapi.portees import SCOPE_READ_LEADS, SCOPE_READ_LICENCE
        self.company = Company.objects.create(nom="Co35", slug="co-35")
        role = Role.objects.create(company=self.company, nom="Administrateur")
        self.u1 = User.objects.create_user(
            "u35a", password="x", company=self.company, role=role)
        User.objects.create_user(
            "u35b", password="x", company=self.company, role=role)
        _, self.raw_ok = ApiKey.issue(
            company=self.company, label="ok", scopes=[SCOPE_READ_LICENCE])
        _, self.raw_ko = ApiKey.issue(
            company=self.company, label="ko", scopes=[SCOPE_READ_LEADS])
        self.url = "/api/django/onboarding/progress/resume/"

    def _get(self, raw=None):
        c = APIClient()
        if raw:
            c.credentials(HTTP_AUTHORIZATION=f"Api-Key {raw}")
        return c.get(self.url)

    def test_cle_valide_retourne_uniquement_le_pourcentage(self):
        r = self._get(self.raw_ok)
        self.assertEqual(r.status_code, 200)
        self.assertEqual(set(r.data), {"pourcentage"})
        self.assertEqual(r.data["pourcentage"], 0)
        item = OnboardingChecklistItem.objects.filter(actif=True).first()
        marquer_item_complete(self.company, self.u1, item.key)
        self.assertGreater(self._get(self.raw_ok).data["pourcentage"], 0)

    def test_sans_cle_401(self):
        self.assertEqual(self._get().status_code, 401)

    def test_scope_insuffisant_403(self):
        self.assertEqual(self._get(self.raw_ko).status_code, 403)


class OnboardingTextesCsvNTDMO36Test(TestCase):
    """NTDMO36 — export/réimport CSV des textes FR par clé stable."""

    def setUp(self):
        self.company = Company.objects.create(nom="Co36", slug="co-36")
        self.role_admin = Role.objects.create(
            company=self.company, nom="Administrateur",
            permissions=["roles_gerer"])
        self.role_tech = Role.objects.create(
            company=self.company, nom="Technicien")
        self.admin = User.objects.create_user(
            "a36", password="x", company=self.company, role=self.role_admin)
        self.tech = User.objects.create_user(
            "t36", password="x", company=self.company, role=self.role_tech)
        self.url_export = "/api/django/onboarding/export-textes.csv"
        self.url_import = "/api/django/onboarding/import-textes.csv"

    def _client(self, user):
        c = APIClient()
        c.force_authenticate(user)
        return c

    def test_non_admin_403(self):
        self.assertEqual(self._client(self.tech).get(self.url_export).status_code, 403)
        self.assertEqual(self._client(self.tech).post(self.url_import).status_code, 403)

    def test_export_trois_colonnes_et_cles_stables(self):
        r = self._client(self.admin).get(self.url_export)
        self.assertEqual(r.status_code, 200)
        texte = r.content.decode("utf-8-sig")
        self.assertEqual(texte.splitlines()[0], "cle_stable,ecran_cible,texte_fr")
        self.assertIn("item:", texte)

    def test_reimport_met_a_jour_sans_doublon(self):
        from django.core.files.uploadedfile import SimpleUploadedFile
        from apps.onboarding.models import OnboardingChecklistItem
        item = OnboardingChecklistItem.objects.create(
            company=self.company, key="item-36", libelle="Ancien", lien="/x")
        avant = OnboardingChecklistItem.objects.count()
        contenu = self._client(self.admin).get(self.url_export).content
        contenu = contenu.decode("utf-8-sig").replace("Ancien", "Nouveau")
        r = self._client(self.admin).post(
            self.url_import,
            {"fichier": SimpleUploadedFile("t.csv", contenu.encode("utf-8"))},
            format="multipart")
        self.assertEqual(r.status_code, 200, r.content)
        item.refresh_from_db()
        self.assertEqual(item.libelle, "Nouveau")
        self.assertEqual(OnboardingChecklistItem.objects.count(), avant)
        # Le catalogue global n"est pas modifiable par un admin de société.
        self.assertEqual(r.data["mis_a_jour"], 1)

    def test_surcharge_societe_exportee_seule_et_jamais_ecrasee(self):
        """Item global + surcharge société de la même clé : UNE ligne
        ``item:<key>`` (la surcharge) ; le réimport du fichier tel quel ne
        remet jamais le texte global sur la surcharge."""
        from django.core.files.uploadedfile import SimpleUploadedFile
        globale = OnboardingChecklistItem.objects.create(
            company=None, key="item-36-g", libelle="Texte global", ordre=500)
        surcharge = OnboardingChecklistItem.objects.create(
            company=self.company, key="item-36-g", libelle="Texte societe",
            ordre=1)
        texte = self._client(self.admin).get(
            self.url_export).content.decode("utf-8-sig")
        lignes = [x for x in texte.splitlines()
                  if x.startswith("item:item-36-g,")]
        self.assertEqual(lignes, ["item:item-36-g,,Texte societe"])
        r = self._client(self.admin).post(
            self.url_import,
            {"fichier": SimpleUploadedFile("t.csv", texte.encode("utf-8"))},
            format="multipart")
        self.assertEqual(r.status_code, 200, r.content)
        surcharge.refresh_from_db()
        globale.refresh_from_db()
        self.assertEqual(surcharge.libelle, "Texte societe")
        self.assertEqual(globale.libelle, "Texte global")
        self.assertEqual(r.data["mis_a_jour"], 0)

    def test_fichier_inexploitable_409(self):
        """ENF11 — octets non UTF-8 ou en-tête absent : fichier conforme au
        schéma (binaire) mais inexploitable → 409, rien n'est écrit."""
        from django.core.files.uploadedfile import SimpleUploadedFile
        for nom, octets in (("bin.csv", bytes([0x50, 0x4B, 0x03, 0xB1, 0xFF])),
                            ("entete.csv", "a,b\r\n1,2\r\n".encode())):
            r = self._client(self.admin).post(
                self.url_import,
                {"fichier": SimpleUploadedFile(nom, octets)},
                format="multipart")
            self.assertEqual(r.status_code, 409, (nom, r.content))
            self.assertIn("detail", r.data)

    def test_import_sans_fichier_400(self):
        self.assertEqual(self._client(self.admin).post(
            self.url_import, {}, format="multipart").status_code, 400)
