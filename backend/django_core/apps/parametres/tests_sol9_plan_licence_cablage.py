"""SOL9 — le plan de licence agit sur le MÊME chemin que ModuleToggle.

NTADM7 avait livré `has_feature` en FONDATION SEULE : rien ne l'appelait. SOL9
le branche sur `core.feature_flags`, le point d'entrée unique déjà utilisé par
le middleware 404 ET par `modules_desactives` que sert `/auth/me`. Un module
hors plan disparaît donc de la nav ET répond 404, par la même règle — jamais
deux gatings divergents.

L'invariant NON NÉGOCIABLE reste : plan NULL ⇒ accès complet. C'est le cas de
TOUTES les sociétés existantes, donc zéro régression.
"""
from django.contrib.auth import get_user_model
from django.http import HttpResponse
from django.test import RequestFactory, TestCase

from apps.adminops.models import PlanLicence
from apps.adminops.plan_seeds import (
    CODE_SOLAIRE, modules_du_plan_solaire, seed_plan_solaire,
)
from apps.parametres import feature_flags as plan_flags
from apps.parametres.models import CompanyProfile
from authentication.models import Company
from core import feature_flags, permissions
from core.models import ModuleToggle

User = get_user_model()


class PlanNulAccesCompletTests(TestCase):
    """Compat totale : sans plan assigné, RIEN ne change."""

    def setUp(self):
        self.company = Company.objects.create(nom='Sans plan', slug='sol9-nul')

    def test_sans_profil_acces_complet(self):
        self.assertTrue(feature_flags.module_actif(self.company, 'pos'))
        self.assertEqual(
            feature_flags.modules_desactives(self.company), set())

    def test_profil_sans_plan_acces_complet(self):
        CompanyProfile.objects.create(company=self.company, nom='Sans plan')
        self.assertTrue(feature_flags.module_actif(self.company, 'mrp'))
        self.assertEqual(
            feature_flags.modules_desactives(self.company), set())

    def test_verificateur_bien_enregistre(self):
        self.assertIn('plan_licence', feature_flags.registered_access_checks())


class PlanRestreintTests(TestCase):
    def setUp(self):
        self.company = Company.objects.create(nom='Avec plan', slug='sol9-plan')
        # `adminops/0003` sème déjà starter/pro/enterprise : on met à jour,
        # jamais `create` (la contrainte unique sur `code` sauterait).
        self.plan, _ = PlanLicence.objects.update_or_create(
            code=PlanLicence.Code.STARTER,
            defaults={'nom': 'Starter',
                      'modules_inclus': ['crm', 'ventes', 'stock']})
        CompanyProfile.objects.create(
            company=self.company, nom='Avec plan', plan=self.plan)

    def test_module_du_plan_actif(self):
        self.assertTrue(feature_flags.module_actif(self.company, 'crm'))

    def test_module_hors_plan_inactif(self):
        self.assertFalse(feature_flags.module_actif(self.company, 'pos'))

    def test_modules_desactives_contient_les_modules_hors_plan(self):
        hors = feature_flags.modules_desactives(self.company)
        self.assertIn('pos', hors)
        self.assertIn('flotte', hors)
        self.assertNotIn('crm', hors)

    def test_fondation_jamais_bornee_par_un_plan(self):
        """Un palier commercial ne coupe jamais roles/parametres/core."""
        hors = feature_flags.modules_desactives(self.company)
        for cle in ('core', 'roles', 'parametres', 'records', 'customfields'):
            self.assertNotIn(cle, hors, cle)
        self.assertTrue(plan_flags.module_dans_le_plan(self.company, 'roles'))

    def test_cle_sans_manifeste_jamais_bornee(self):
        self.assertTrue(plan_flags.module_dans_le_plan(self.company, 'magasin'))

    def test_les_deux_axes_se_composent_en_et(self):
        """Toggle ON + hors plan ⇒ inactif ; toggle OFF + dans le plan ⇒ inactif."""
        ModuleToggle.objects.create(
            company=self.company, module='pos', actif=True)
        self.assertFalse(feature_flags.module_actif(self.company, 'pos'))
        ModuleToggle.objects.create(
            company=self.company, module='crm', actif=False)
        self.assertFalse(feature_flags.module_actif(self.company, 'crm'))

    def test_isolation_multi_tenant(self):
        voisine = Company.objects.create(nom='Voisine', slug='sol9-voisine')
        self.assertTrue(feature_flags.module_actif(voisine, 'pos'))
        self.assertEqual(feature_flags.modules_desactives(voisine), set())

    def test_version_groupee_et_unitaire_concordent(self):
        groupee = plan_flags.modules_hors_plan(self.company)
        for cle in groupee:
            self.assertFalse(
                plan_flags.module_dans_le_plan(self.company, cle), cle)
        self.assertIn('pos', groupee)
        self.assertNotIn('crm', groupee)


class MiddlewareEtMeTests(TestCase):
    """Le MÊME chemin : 404 de l'API et liste servie à /auth/me."""

    def setUp(self):
        self.company = Company.objects.create(nom='MW plan', slug='sol9-mw')
        plan, _ = PlanLicence.objects.update_or_create(
            code=PlanLicence.Code.PRO,
            defaults={'nom': 'Pro', 'modules_inclus': ['crm', 'ventes']})
        CompanyProfile.objects.create(
            company=self.company, nom='MW plan', plan=plan)
        self.user = User.objects.create_user(
            username='sol9_user', password='x', role_legacy='normal',
            company=self.company)

    def _mw(self):
        sentinel = HttpResponse('ok')
        return permissions.DisabledModuleMiddleware(lambda r: sentinel), sentinel

    def _req(self, path):
        req = RequestFactory().get(path)
        req.user = self.user
        return req

    def test_module_hors_plan_renvoie_404(self):
        mw, _sentinel = self._mw()
        self.assertEqual(mw(self._req('/api/django/pos/x/')).status_code, 404)
        # SOL7 : le miroir v1 est gardé par la même règle.
        self.assertEqual(mw(self._req('/api/v1/pos/x/')).status_code, 404)

    def test_module_du_plan_passe(self):
        mw, sentinel = self._mw()
        self.assertIs(mw(self._req('/api/django/crm/leads/')), sentinel)

    def test_serializer_me_sert_la_meme_liste(self):
        """`/auth/me` expose EXACTEMENT la liste enrichie (même source)."""
        from authentication.serializers import UserSerializer

        # Appel direct du SerializerMethodField : on teste la SOURCE de la
        # liste, sans dépendre du contexte `request` du reste du sérialiseur.
        liste = UserSerializer().get_modules_desactives(self.user)
        self.assertIn('pos', liste)
        self.assertNotIn('crm', liste)
        self.assertEqual(
            set(liste), feature_flags.modules_desactives(self.company))


class PlanSolaireTests(TestCase):
    def test_seed_idempotent_et_perimetre_solaire(self):
        plan, cree = seed_plan_solaire()
        self.assertTrue(cree)
        self.assertEqual(plan.code, CODE_SOLAIRE)
        attendu = modules_du_plan_solaire()
        self.assertEqual(list(plan.modules_inclus), attendu)
        plan2, cree2 = seed_plan_solaire()
        self.assertFalse(cree2)
        self.assertEqual(plan2.pk, plan.pk)

    def test_aucun_vertical_parque_dans_le_plan(self):
        from erp_agentique.settings import editions

        inclus = set(modules_du_plan_solaire())
        for cle in editions.modules_parques(editions.EDITION_SOLAR):
            self.assertNotIn(cle, inclus, cle)

    def test_le_coeur_metier_est_inclus(self):
        inclus = set(modules_du_plan_solaire())
        for cle in ('crm', 'ventes', 'stock', 'installations', 'sav', 'compta'):
            self.assertIn(cle, inclus, cle)

    def test_plan_solaire_n_assigne_aucune_societe(self):
        company = Company.objects.create(nom='Non assignée', slug='sol9-na')
        CompanyProfile.objects.create(company=company, nom='Non assignée')
        seed_plan_solaire()
        profil = CompanyProfile.objects.get(company=company)
        self.assertIsNone(profil.plan)
        self.assertEqual(feature_flags.modules_desactives(company), set())

    def test_une_societe_sur_le_plan_solaire_garde_tout_le_metier(self):
        company = Company.objects.create(nom='Solaire', slug='sol9-solaire')
        plan, _ = seed_plan_solaire()
        CompanyProfile.objects.create(
            company=company, nom='Solaire', plan=plan)
        hors = feature_flags.modules_desactives(company)
        for cle in ('crm', 'ventes', 'stock', 'installations', 'sav', 'pos'):
            self.assertNotIn(cle, hors, cle)
        self.assertTrue(feature_flags.module_actif(company, 'crm'))
