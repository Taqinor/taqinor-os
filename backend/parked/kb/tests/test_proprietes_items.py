"""Tests ZGED11 — Propriétés d'article + vues d'items (kanban/cartes/liste/
calendrier).

Couvre :
* définir une propriété « Statut » (sélection) sur un article parent
  s'applique aux enfants (héritage, sauf surcharge locale) ;
* la vue kanban groupe les sous-articles par cette propriété ;
* la vue calendrier place ceux qui ont une propriété date ;
* liste/cartes rendent les propriétés (aucun regroupement) ;
* validation par les définitions actives (``customfields``, module
  ``kb_article``) ;
* scoping société.
"""
from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from authentication.models import Company

from apps.customfields.models import CustomFieldDef
from apps.kb import selectors
from apps.kb.models import KbArticle

User = get_user_model()


def make_company(slug, nom):
    company, _ = Company.objects.get_or_create(slug=slug, defaults={'nom': nom})
    return company


def make_user(company, username, role='responsable'):
    return User.objects.create_user(
        username=username, password='x', company=company, role_legacy=role)


def auth(user):
    api = APIClient()
    api.credentials(HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(user)}')
    return api


class KbProprietesInheritanceTests(TestCase):
    def setUp(self):
        self.co = make_company('kb-prop', 'P')
        self.parent = KbArticle.objects.create(
            company=self.co, titre='Parent',
            proprietes={'statut': 'a_faire'})
        self.enfant = KbArticle.objects.create(
            company=self.co, titre='Enfant', parent=self.parent)

    def test_child_inherits_parent_property(self):
        effectives = selectors.proprietes_effectives(self.enfant)
        self.assertEqual(effectives['statut'], 'a_faire')

    def test_child_own_property_overrides_inherited(self):
        self.enfant.proprietes = {'statut': 'termine'}
        self.enfant.save(update_fields=['proprietes'])
        effectives = selectors.proprietes_effectives(self.enfant)
        self.assertEqual(effectives['statut'], 'termine')

    def test_grandchild_inherits_from_grandparent(self):
        petit_enfant = KbArticle.objects.create(
            company=self.co, titre='Petit-enfant', parent=self.enfant)
        effectives = selectors.proprietes_effectives(petit_enfant)
        self.assertEqual(effectives['statut'], 'a_faire')

    def test_root_article_has_no_inherited_properties(self):
        effectives = selectors.proprietes_effectives(self.parent)
        self.assertEqual(effectives, {'statut': 'a_faire'})


class KbItemsVuesTests(TestCase):
    def setUp(self):
        self.co = make_company('kb-items', 'I')
        self.user = make_user(self.co, 'kb-items-u1')
        self.parent = KbArticle.objects.create(
            company=self.co, titre='Projet', proprietes={'statut': 'defaut'})
        self.enfant_a = KbArticle.objects.create(
            company=self.co, titre='Tâche A', parent=self.parent,
            proprietes={'statut': 'en_cours', 'echeance': '2026-08-01'})
        self.enfant_b = KbArticle.objects.create(
            company=self.co, titre='Tâche B', parent=self.parent,
            proprietes={'statut': 'termine'})
        self.enfant_c = KbArticle.objects.create(
            company=self.co, titre='Tâche C', parent=self.parent)

    def test_liste_vue_renders_all_with_properties(self):
        qs = KbArticle.objects.filter(company=self.co, parent=self.parent)
        items = selectors.items_parcours_vue(qs, vue='liste')
        self.assertEqual(len(items), 3)
        titres_props = {i['titre']: i['proprietes'] for i in items}
        self.assertEqual(titres_props['Tâche A']['statut'], 'en_cours')
        # Tâche C hérite du statut du parent.
        self.assertEqual(titres_props['Tâche C']['statut'], 'defaut')

    def test_kanban_groups_by_property(self):
        qs = KbArticle.objects.filter(company=self.co, parent=self.parent)
        groupes = selectors.items_parcours_vue(
            qs, vue='kanban', propriete='statut')
        self.assertIn('en_cours', groupes)
        self.assertIn('termine', groupes)
        self.assertEqual(len(groupes['en_cours']), 1)
        self.assertEqual(groupes['en_cours'][0]['titre'], 'Tâche A')

    def test_calendrier_only_keeps_dated_items(self):
        qs = KbArticle.objects.filter(company=self.co, parent=self.parent)
        groupes = selectors.items_parcours_vue(
            qs, vue='calendrier', propriete='echeance')
        self.assertIn('2026-08-01', groupes)
        self.assertEqual(len(groupes['2026-08-01']), 1)
        # Aucune autre date -> aucun autre groupe.
        self.assertEqual(len(groupes), 1)

    def test_cartes_vue_same_shape_as_liste(self):
        qs = KbArticle.objects.filter(company=self.co, parent=self.parent)
        items = selectors.items_parcours_vue(qs, vue='cartes')
        self.assertEqual(len(items), 3)


class KbProprietesApiTests(TestCase):
    ARTICLES = '/api/django/kb/articles/'

    def setUp(self):
        self.co = make_company('kb-prop-api', 'A')
        self.user = make_user(self.co, 'kb-prop-api-u1')
        CustomFieldDef.objects.create(
            company=self.co, module='kb_article', code='statut',
            libelle='Statut', type='choice',
            options=['a_faire', 'en_cours', 'termine'])
        self.parent = KbArticle.objects.create(
            company=self.co, titre='Parent API')
        self.enfant = KbArticle.objects.create(
            company=self.co, titre='Enfant API', parent=self.parent,
            proprietes={'statut': 'en_cours'})

    def test_valid_choice_property_accepted(self):
        resp = auth(self.user).patch(
            f'{self.ARTICLES}{self.parent.id}/',
            {'proprietes': {'statut': 'a_faire'}}, format='json')
        self.assertEqual(resp.status_code, 200, resp.data)

    def test_invalid_choice_property_rejected(self):
        resp = auth(self.user).patch(
            f'{self.ARTICLES}{self.parent.id}/',
            {'proprietes': {'statut': 'inexistant'}}, format='json')
        self.assertEqual(resp.status_code, 400)

    def test_items_endpoint_kanban(self):
        resp = auth(self.user).get(
            f'{self.ARTICLES}{self.parent.id}/items/'
            f'?vue=kanban&propriete=statut')
        self.assertEqual(resp.status_code, 200, resp.data)
        self.assertIn('en_cours', resp.data)

    def test_proprietes_effectives_exposed_on_detail(self):
        resp = auth(self.user).get(f'{self.ARTICLES}{self.enfant.id}/')
        self.assertEqual(
            resp.data['proprietes_effectives']['statut'], 'en_cours')
