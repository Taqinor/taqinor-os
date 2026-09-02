"""SOL14 — `societes_avec_module` : la brique des tâches planifiées.

Une tâche périodique qui boucle sur toutes les sociétés travaille pour des
tenants qui ont ÉTEINT le module : elle leur écrit des données et leur envoie
des notifications, pendant que l'API leur répond 404 au même instant. Deux
vérités contradictoires le même jour.
"""
from django.test import TestCase

from authentication.models import Company
from core import feature_flags
from core.models import ModuleToggle


class SocietesAvecModuleTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.a = Company.objects.create(nom='A SOL14', slug='sol14-a')
        cls.b = Company.objects.create(nom='B SOL14', slug='sol14-b')
        cls.c = Company.objects.create(nom='C SOL14', slug='sol14-c')

    def _cles(self, resultat):
        return sorted(c.slug for c in resultat)

    def test_defaut_toutes_les_societes(self):
        """Politique FG391 : absence de ligne = module actif."""
        self.assertEqual(
            self._cles(feature_flags.societes_avec_module('scm')),
            ['sol14-a', 'sol14-b', 'sol14-c'])

    def test_saute_les_societes_module_off(self):
        ModuleToggle.objects.create(company=self.b, module='scm', actif=False)
        self.assertEqual(
            self._cles(feature_flags.societes_avec_module('scm')),
            ['sol14-a', 'sol14-c'])

    def test_un_module_off_n_affecte_pas_les_autres(self):
        ModuleToggle.objects.create(company=self.b, module='scm', actif=False)
        self.assertEqual(
            self._cles(feature_flags.societes_avec_module('transport')),
            ['sol14-a', 'sol14-b', 'sol14-c'])

    def test_une_ligne_actif_true_ne_masque_rien(self):
        ModuleToggle.objects.create(company=self.b, module='scm', actif=True)
        self.assertEqual(
            self._cles(feature_flags.societes_avec_module('scm')),
            ['sol14-a', 'sol14-b', 'sol14-c'])

    def test_enveloppe_le_queryset_de_l_appelant(self):
        """Les filtres de l'appelant sont CONSERVÉS, jamais remplacés."""
        base = Company.objects.filter(slug__in=['sol14-a', 'sol14-b'])
        self.assertEqual(
            self._cles(feature_flags.societes_avec_module('scm', base)),
            ['sol14-a', 'sol14-b'])
        ModuleToggle.objects.create(company=self.a, module='scm', actif=False)
        self.assertEqual(
            self._cles(feature_flags.societes_avec_module('scm', base)),
            ['sol14-b'])

    def test_respecte_aussi_le_plan_de_licence(self):
        """SOL9 : un module hors plan est aussi sauté par le beat."""
        from apps.adminops.models import PlanLicence
        from apps.parametres.models import CompanyProfile

        plan, _ = PlanLicence.objects.update_or_create(
            code=PlanLicence.Code.STARTER,
            defaults={'nom': 'Starter', 'modules_inclus': ['crm']})
        CompanyProfile.objects.create(
            company=self.c, nom='C SOL14', plan=plan)
        self.assertEqual(
            self._cles(feature_flags.societes_avec_module('scm')),
            ['sol14-a', 'sol14-b'])
