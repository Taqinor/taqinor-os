"""Tests ODY25 — journal d'installation des applications (qui / quoi / quand).

Couvre :
  * un franchissement (installer / désinstaller) émet ``module_toggled`` sur le
    bus M6 avec la société, la clé de module, le nouvel état et l'auteur ;
  * un NON-franchissement (ré-activer une app déjà active, désactiver une app
    déjà désactivée) n'émet RIEN et n'écrit aucune ligne de journal ;
  * une cascade journalise CHAQUE module réellement basculé, pas seulement
    celui qui a été cliqué ;
  * la bascule est historisée dans le chatter générique ``records.Activity``
    (ARC8) — aucun modèle de journal dédié, donc aucune migration ;
  * MULTI-TENANT STRICT : le journal de la société A est invisible de B, aussi
    bien par le service que par l'endpoint ``GET /core/modules/journal/``.
"""
from django.contrib.auth import get_user_model
from django.contrib.contenttypes.models import ContentType
from django.test import TestCase
from rest_framework.test import APIRequestFactory, force_authenticate

from apps.records.models import Activity
from authentication.models import Company
from core import events, feature_flags
from core.models import ModuleToggle
from core.views import ModuleCatalogViewSet

User = get_user_model()


def _journal_rows(company):
    """Entrées de chatter attachées aux ModuleToggle de ``company``."""
    ct = ContentType.objects.get_for_model(ModuleToggle)
    ids = list(ModuleToggle.objects.filter(company=company)
               .values_list('id', flat=True))
    return list(
        Activity.objects
        .filter(content_type=ct, object_id__in=ids, field='actif')
        .order_by('id')
    )


class ModuleToggledEventTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.company = Company.objects.create(nom='ODY25 Emission SARL')
        cls.user = User.objects.create_user(
            username='ody25_emetteur', password='x', company=cls.company)

    def setUp(self):
        self.recus = []

        def _spy(sender, **kwargs):
            self.recus.append(kwargs)

        self._spy = _spy
        events.module_toggled.connect(_spy, dispatch_uid='ody25_test_spy')
        self.addCleanup(
            events.module_toggled.disconnect,
            dispatch_uid='ody25_test_spy')

    def test_desinstaller_emet_l_evenement_avec_l_auteur(self):
        feature_flags.desactiver_module(
            self.company, 'flotte', user=self.user)

        self.assertEqual(len(self.recus), 1)
        recu = self.recus[0]
        self.assertEqual(recu['module'], 'flotte')
        self.assertFalse(recu['actif'])
        self.assertEqual(recu['company'], self.company)
        self.assertEqual(recu['user'], self.user)
        self.assertEqual(recu['toggle'].company, self.company)

    def test_reinstaller_emet_l_evenement(self):
        feature_flags.desactiver_module(self.company, 'flotte')
        self.recus.clear()

        feature_flags.activer_module(self.company, 'flotte', user=self.user)

        self.assertEqual(len(self.recus), 1)
        self.assertTrue(self.recus[0]['actif'])
        self.assertEqual(self.recus[0]['user'], self.user)

    def test_aucune_emission_sans_franchissement(self):
        # Le module est déjà actif (politique FG391 : pas de ligne = actif).
        feature_flags.activer_module(self.company, 'flotte', user=self.user)
        self.assertEqual(self.recus, [])

        # Deux désactivations de suite : seule la PREMIÈRE est un
        # franchissement.
        feature_flags.desactiver_module(self.company, 'flotte',
                                        user=self.user)
        feature_flags.desactiver_module(self.company, 'flotte',
                                        user=self.user)
        self.assertEqual(len(self.recus), 1)

    def test_cascade_emet_par_module_reellement_bascule(self):
        # crm est requis par plusieurs modules actifs (ventes, sav…) : la
        # cascade doit journaliser chacun d'eux, pas seulement crm.
        desactives = feature_flags.desactiver_module(
            self.company, 'crm', cascade=True, user=self.user)

        self.assertGreater(len(desactives), 1)
        emis = {r['module'] for r in self.recus}
        self.assertEqual(emis, set(desactives))


class ModuleJournalStorageTests(TestCase):
    """Le journal vit dans le chatter générique ARC8 (aucun modèle dédié)."""

    @classmethod
    def setUpTestData(cls):
        cls.company = Company.objects.create(nom='ODY25 Journal SARL')
        cls.user = User.objects.create_user(
            username='ody25_meryem', password='x', company=cls.company,
            first_name='Meryem', last_name='B.')

    def test_bascule_ecrit_une_entree_de_chatter(self):
        feature_flags.desactiver_module(
            self.company, 'flotte', user=self.user)

        lignes = _journal_rows(self.company)
        self.assertEqual(len(lignes), 1)
        ligne = lignes[0]
        self.assertEqual(ligne.kind, Activity.Kind.MODIFICATION)
        self.assertEqual(ligne.new_value, feature_flags.ACTIF_DESINSTALLEE)
        self.assertEqual(ligne.old_value, feature_flags.ACTIF_INSTALLEE)
        self.assertEqual(ligne.created_by, self.user)
        # La société du journal est celle du TOGGLE (structurel, pas déclaré).
        self.assertEqual(ligne.company, self.company)

    def test_journal_modules_rend_la_derniere_bascule_par_module(self):
        feature_flags.desactiver_module(self.company, 'flotte',
                                        user=self.user)
        feature_flags.activer_module(self.company, 'flotte', user=self.user)

        journal = feature_flags.journal_modules(self.company)
        lignes = [row for row in journal if row['module'] == 'flotte']
        self.assertEqual(len(lignes), 1)
        self.assertTrue(lignes[0]['actif'])
        self.assertEqual(lignes[0]['par'], 'Meryem B.')
        self.assertTrue(lignes[0]['le'])

    def test_bascule_systeme_sans_utilisateur(self):
        feature_flags.desactiver_module(self.company, 'flotte')

        journal = feature_flags.journal_modules(self.company)
        self.assertEqual([r['par'] for r in journal], [''])

    def test_motif_du_toggle_est_journalise(self):
        feature_flags.desactiver_module(self.company, 'flotte')
        ModuleToggle.objects.filter(
            company=self.company, module='flotte').update(
                raison='Hors offre pilote')
        feature_flags.activer_module(self.company, 'flotte', user=self.user)

        journal = feature_flags.journal_modules(self.company)
        self.assertEqual(journal[0]['raison'], 'Hors offre pilote')


class ModuleJournalTenantIsolationTests(TestCase):
    """Le journal d'une société est INVISIBLE d'une autre (société A ≠ B)."""

    @classmethod
    def setUpTestData(cls):
        cls.company_a = Company.objects.create(nom='ODY25 Alpha SARL')
        cls.company_b = Company.objects.create(nom='ODY25 Beta SAS')
        cls.admin_a = User.objects.create_user(
            username='ody25_admin_alpha', password='x',
            company=cls.company_a, role_legacy='admin')
        cls.admin_b = User.objects.create_user(
            username='ody25_admin_beta', password='x',
            company=cls.company_b, role_legacy='admin')

    def _get_journal(self, user):
        vue = ModuleCatalogViewSet.as_view({'get': 'journal'})
        requete = APIRequestFactory().get('/api/django/core/modules/journal/')
        force_authenticate(requete, user=user)
        return vue(requete)

    def test_le_journal_de_a_n_apparait_jamais_chez_b(self):
        # A désinstalle « flotte » ; B ne touche à rien.
        feature_flags.desactiver_module(
            self.company_a, 'flotte', user=self.admin_a)

        # Service : B ne voit rien.
        self.assertEqual(feature_flags.journal_modules(self.company_b), [])
        self.assertEqual(
            [r['module'] for r in feature_flags.journal_modules(
                self.company_a)],
            ['flotte'])

        # Endpoint : idem, et la société vient de l'utilisateur authentifié.
        reponse_b = self._get_journal(self.admin_b)
        self.assertEqual(reponse_b.status_code, 200)
        self.assertEqual(reponse_b.data, [])

        reponse_a = self._get_journal(self.admin_a)
        self.assertEqual(reponse_a.status_code, 200)
        self.assertEqual([r['module'] for r in reponse_a.data], ['flotte'])
        self.assertEqual(reponse_a.data[0]['par'], 'ody25_admin_alpha')

    def test_deux_societes_journalisent_independamment(self):
        # `achats` (dépend de `stock`, aucun dépendant) — `pos` a gagné un
        # dépendant actif (`promotions`, NTRET13) depuis cette lane et ne se
        # désactive plus seul.
        feature_flags.desactiver_module(
            self.company_a, 'flotte', user=self.admin_a)
        feature_flags.desactiver_module(
            self.company_b, 'achats', user=self.admin_b)

        self.assertEqual(
            [r['module'] for r in feature_flags.journal_modules(
                self.company_a)],
            ['flotte'])
        self.assertEqual(
            [r['module'] for r in feature_flags.journal_modules(
                self.company_b)],
            ['achats'])
