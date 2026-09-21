"""AUD315 — admin gestion_projet scopé société + jeton du portail protégé.

Deux défauts :

1. AUCUNE des classes `ModelAdmin` de `apps/gestion_projet/admin.py` ne
   surchargeait `get_queryset` : un compte `is_staff` d'une société voyait —
   et pouvait modifier — les lignes de TOUTES les sociétés. Or `is_staff`
   n'est pas réservé aux comptes internes (le seeder de démo et l'inscription
   posent des comptes admin scopés société qui peuvent le porter).
2. `PortailProjetTokenAdmin.search_fields = ('token',)` laissait n'importe
   quel staff retrouver et lire EN CLAIR le jeton du portail public de
   n'importe quelle société — donc ouvrir le portail client d'un autre tenant
   sans jamais s'y authentifier.

Run :
    docker compose exec django_core python manage.py test \
        apps.gestion_projet.tests.test_aud315_admin_scoping -v 2
"""
from django.contrib.admin.sites import site
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Permission
from django.test import RequestFactory, TestCase

from apps.gestion_projet.admin import PortailProjetTokenAdmin
from apps.gestion_projet.models import PortailProjetToken, Projet, Tache
from authentication.models import Company

User = get_user_model()

# Les modèles du module effectivement enregistrés dans l'admin Django.
_MODELES_GESTION_PROJET = [
    (modele, adm) for modele, adm in site._registry.items()
    if modele.__module__.startswith('apps.gestion_projet')
]


class AdminScopingTests(TestCase):
    def setUp(self):
        self.rf = RequestFactory()
        self.co_a = Company.objects.get_or_create(
            slug='aud315-a', defaults={'nom': 'A'})[0]
        self.co_b = Company.objects.get_or_create(
            slug='aud315-b', defaults={'nom': 'B'})[0]
        self.staff_a = User.objects.create_user(
            username='aud315-staff-a', password='x', company=self.co_a,
            role_legacy='admin', is_staff=True)
        self.root = User.objects.create_superuser(
            username='aud315-root', password='x', email='r@example.com')
        self.projet_a = Projet.objects.create(
            company=self.co_a, code='P-A315', nom='Projet A')
        self.projet_b = Projet.objects.create(
            company=self.co_b, code='P-B315', nom='Projet B')

    def _request(self, user):
        req = self.rf.get('/admin/')
        req.user = user
        return req

    def test_tous_les_modeladmin_du_module_sont_scopes(self):
        self.assertTrue(_MODELES_GESTION_PROJET, 'aucun admin enregistré ?')
        for modele, adm in _MODELES_GESTION_PROJET:
            with self.subTest(modele=modele.__name__):
                self.assertTrue(
                    hasattr(adm, '_societe_utilisateur'),
                    f'{type(adm).__name__} n’hérite pas de _AdminScopeSociete')

    def test_staff_ne_voit_que_sa_societe(self):
        adm = site._registry[Projet]
        vus = adm.get_queryset(self._request(self.staff_a))

        self.assertIn(self.projet_a, vus)
        self.assertNotIn(self.projet_b, vus)

    def test_superutilisateur_voit_tout(self):
        adm = site._registry[Projet]
        vus = adm.get_queryset(self._request(self.root))

        self.assertIn(self.projet_a, vus)
        self.assertIn(self.projet_b, vus)

    def test_compte_sans_societe_ne_voit_rien(self):
        sans_co = User.objects.create_user(
            username='aud315-sans-co', password='x', is_staff=True)
        adm = site._registry[Projet]

        self.assertEqual(
            adm.get_queryset(self._request(sans_co)).count(), 0)

    def test_permissions_objet_refusent_une_autre_societe(self):
        # On DONNE au compte staff les permissions Django du modèle : sans ça
        # le refus viendrait de `super()` et ne prouverait rien du scoping.
        perms = Permission.objects.filter(
            content_type__app_label='gestion_projet',
            codename__in=('view_projet', 'change_projet', 'delete_projet'))
        self.assertEqual(perms.count(), 3)
        self.staff_a.user_permissions.add(*perms)
        staff = User.objects.get(pk=self.staff_a.pk)  # vide le cache de perms
        adm = site._registry[Projet]
        req = self._request(staff)

        # Sa propre société : autorisée (les permissions Django passent).
        self.assertTrue(adm.has_view_permission(req, self.projet_a))
        self.assertTrue(adm.has_change_permission(req, self.projet_a))
        self.assertTrue(adm.has_delete_permission(req, self.projet_a))
        # Une autre société : refusée par le scoping, permissions ou pas.
        self.assertFalse(adm.has_view_permission(req, self.projet_b))
        self.assertFalse(adm.has_change_permission(req, self.projet_b))
        self.assertFalse(adm.has_delete_permission(req, self.projet_b))

    def test_scoping_actif_sur_un_modele_enfant(self):
        tache_b = Tache.objects.create(
            company=self.co_b, projet=self.projet_b, libelle='T B')
        adm = site._registry[Tache]

        self.assertNotIn(
            tache_b, adm.get_queryset(self._request(self.staff_a)))


class JetonPortailTests(TestCase):
    def setUp(self):
        self.co = Company.objects.get_or_create(
            slug='aud315-tok', defaults={'nom': 'Tok'})[0]
        self.projet = Projet.objects.create(
            company=self.co, code='P-TOK315', nom='Projet jeton')

    def test_le_jeton_nest_plus_cherchable(self):
        self.assertNotIn('token', PortailProjetTokenAdmin.search_fields)
        self.assertEqual(
            PortailProjetTokenAdmin.search_fields,
            ('projet__code', 'projet__nom'))

    def test_le_jeton_nest_plus_affiche_ni_editable(self):
        self.assertIn('token', PortailProjetTokenAdmin.exclude)
        self.assertNotIn('token', PortailProjetTokenAdmin.list_display)

    def test_le_jeton_reste_pose_cote_serveur(self):
        acces = PortailProjetToken.objects.create(
            company=self.co, projet=self.projet)

        self.assertTrue(acces.token)
        self.assertGreaterEqual(len(acces.token), 32)
