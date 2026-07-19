"""ASG1 — Tests du modèle/API ``AssumptionNode`` (dd-assumption-engine §3.1).

Couvre : isolation multi-tenant (CRUD company-scopé, company forcée côté
serveur, FK ``parent``/``invalidation_links`` bloquées cross-société) et les
contraintes de classe (statut/classe invalides rejetés, S/R hors [0, 1]
rejetés, demi-vie par défaut posée depuis la classe quand absente).
"""
from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from authentication.models import Company
from apps.roles.models import Role

from apps.adsengine.models import AssumptionNode

User = get_user_model()
BASE = '/api/django/adsengine/noeuds-hypothese/'


def make_user(company, username, permissions):
    role = Role.objects.create(
        company=company, nom=username + '-role', permissions=permissions)
    return User.objects.create_user(
        username=username, password='x', company=company,
        role_legacy='normal', role=role)


def auth(user):
    api = APIClient()
    api.credentials(HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(user)}')
    return api


class AssumptionNodeModelTests(TestCase):
    """Contraintes de classe au niveau modèle (clean())."""

    def setUp(self):
        self.company = Company.objects.create(nom='ASG Co', slug='asg-co')

    def _node(self, **kwargs):
        defaults = dict(
            company=self.company, classe=AssumptionNode.Classe.CREATIF,
            enonce_fr='Le hook facture convertit mieux.',
            enjeux_s=0.5, pertinence_r=0.5,
        )
        defaults.update(kwargs)
        return AssumptionNode(**defaults)

    def test_half_life_weeks_map(self):
        self.assertEqual(
            AssumptionNode.HALF_LIFE_WEEKS[AssumptionNode.Classe.CREATIF], 8)
        self.assertEqual(
            AssumptionNode.HALF_LIFE_WEEKS[AssumptionNode.Classe.ANGLE], 13)
        self.assertEqual(
            AssumptionNode.HALF_LIFE_WEEKS[
                AssumptionNode.Classe.AUDIENCE_STRUCTURE], 26)

    def test_clean_fills_half_life_from_classe_when_absent(self):
        node = self._node(
            classe=AssumptionNode.Classe.ANGLE, demi_vie_semaines=None)
        node.clean()
        self.assertEqual(node.demi_vie_semaines, 13)

    def test_clean_never_overwrites_explicit_half_life(self):
        # Une demi-vie déjà posée (override, §8.1) n'est JAMAIS écrasée.
        node = self._node(
            classe=AssumptionNode.Classe.CREATIF, demi_vie_semaines=99)
        node.clean()
        self.assertEqual(node.demi_vie_semaines, 99)

    def test_clean_rejects_enjeux_out_of_range(self):
        node = self._node(enjeux_s=1.5)
        with self.assertRaises(ValidationError):
            node.clean()

    def test_clean_rejects_pertinence_out_of_range(self):
        node = self._node(pertinence_r=-0.1)
        with self.assertRaises(ValidationError):
            node.clean()

    def test_full_clean_rejects_bad_classe_choice(self):
        node = self._node(classe='pas-une-classe')
        with self.assertRaises(ValidationError):
            node.full_clean()

    def test_full_clean_rejects_bad_statut_choice(self):
        node = self._node(statut='pas-un-statut')
        with self.assertRaises(ValidationError):
            node.full_clean()

    def test_default_alpha_beta_priors(self):
        node = self._node()
        node.save()
        self.assertEqual(node.alpha, 1.0)
        self.assertEqual(node.beta, 1.0)
        self.assertEqual(node.alpha0, 1.0)
        self.assertEqual(node.beta0, 1.0)
        self.assertEqual(node.statut, AssumptionNode.Statut.ASSUMED)

    def test_tags_saison_default_empty_list(self):
        node = self._node()
        node.save()
        self.assertEqual(node.tags_saison, [])

    def test_invalidation_dag_not_symmetrical(self):
        parent = self._node(enonce_fr='Parent')
        parent.save()
        child = self._node(enonce_fr='Enfant', parent=parent)
        child.save()
        other = self._node(enonce_fr='Lien invalidation')
        other.save()
        child.invalidation_links.add(other)
        self.assertIn(other, child.invalidation_links.all())
        self.assertIn(child, other.invalidated_by.all())
        # Pas symétrique : `other` ne pointe PAS automatiquement vers `child`.
        self.assertNotIn(child, other.invalidation_links.all())
        self.assertIn(child, parent.children.all())


class AssumptionNodeApiTests(TestCase):
    """CRUD company-scopé (SCA4) + contraintes de classe côté API."""

    def setUp(self):
        self.company_a = Company.objects.create(nom='ASG A', slug='asg-a')
        self.company_b = Company.objects.create(nom='ASG B', slug='asg-b')
        self.user_a = make_user(
            self.company_a, 'asg-user-a',
            ['adsengine_view', 'adsengine_manage'])
        self.user_b = make_user(
            self.company_b, 'asg-user-b',
            ['adsengine_view', 'adsengine_manage'])

    def _payload(self, **kwargs):
        payload = dict(
            classe=AssumptionNode.Classe.CREATIF,
            enonce_fr='Le hook facture convertit mieux.',
            enjeux_s=0.4, pertinence_r=0.6,
        )
        payload.update(kwargs)
        return payload

    def test_create_forces_company_server_side(self):
        api = auth(self.user_a)
        resp = api.post(BASE, self._payload(), format='json')
        self.assertEqual(resp.status_code, 201, resp.content)
        node = AssumptionNode.objects.get(pk=resp.data['id'])
        self.assertEqual(node.company_id, self.company_a.id)

    def test_company_body_field_ignored(self):
        # `company` n'est PAS un champ du serializer : même envoyé, il est
        # ignoré et la société vient du token, jamais du corps de requête.
        api = auth(self.user_a)
        payload = self._payload()
        payload['company'] = self.company_b.id
        resp = api.post(BASE, payload, format='json')
        self.assertEqual(resp.status_code, 201, resp.content)
        node = AssumptionNode.objects.get(pk=resp.data['id'])
        self.assertEqual(node.company_id, self.company_a.id)

    def test_list_never_leaks_other_company_nodes(self):
        AssumptionNode.objects.create(
            company=self.company_a, classe=AssumptionNode.Classe.CREATIF,
            enonce_fr='Nœud A', enjeux_s=0.3, pertinence_r=0.3)
        AssumptionNode.objects.create(
            company=self.company_b, classe=AssumptionNode.Classe.CREATIF,
            enonce_fr='Nœud B', enjeux_s=0.3, pertinence_r=0.3)
        api = auth(self.user_a)
        resp = api.get(BASE)
        self.assertEqual(resp.status_code, 200)
        enonces = [n['enonce_fr'] for n in resp.data['results']] \
            if 'results' in resp.data else [n['enonce_fr'] for n in resp.data]
        self.assertIn('Nœud A', enonces)
        self.assertNotIn('Nœud B', enonces)

    def test_detail_of_other_company_node_is_hidden(self):
        other = AssumptionNode.objects.create(
            company=self.company_b, classe=AssumptionNode.Classe.CREATIF,
            enonce_fr='Nœud B', enjeux_s=0.3, pertinence_r=0.3)
        api = auth(self.user_a)
        resp = api.get(f'{BASE}{other.id}/')
        self.assertEqual(resp.status_code, 404)

    def test_parent_rejects_cross_company_reference(self):
        foreign_parent = AssumptionNode.objects.create(
            company=self.company_b, classe=AssumptionNode.Classe.CREATIF,
            enonce_fr='Parent étranger', enjeux_s=0.3, pertinence_r=0.3)
        api = auth(self.user_a)
        resp = api.post(
            BASE, self._payload(parent=foreign_parent.id), format='json')
        self.assertEqual(resp.status_code, 400)

    def test_invalidation_links_rejects_cross_company_reference(self):
        foreign = AssumptionNode.objects.create(
            company=self.company_b, classe=AssumptionNode.Classe.CREATIF,
            enonce_fr='Lien étranger', enjeux_s=0.3, pertinence_r=0.3)
        api = auth(self.user_a)
        resp = api.post(
            BASE, self._payload(invalidation_links=[foreign.id]),
            format='json')
        self.assertEqual(resp.status_code, 400)

    def test_create_rejects_bad_classe(self):
        api = auth(self.user_a)
        resp = api.post(
            BASE, self._payload(classe='pas-une-classe'), format='json')
        self.assertEqual(resp.status_code, 400)

    def test_create_rejects_bad_statut(self):
        api = auth(self.user_a)
        resp = api.post(
            BASE, self._payload(statut='pas-un-statut'), format='json')
        self.assertEqual(resp.status_code, 400)

    def test_create_rejects_enjeux_out_of_range(self):
        api = auth(self.user_a)
        resp = api.post(BASE, self._payload(enjeux_s=1.2), format='json')
        self.assertEqual(resp.status_code, 400)

    def test_create_rejects_pertinence_out_of_range(self):
        api = auth(self.user_a)
        resp = api.post(BASE, self._payload(pertinence_r=-0.2), format='json')
        self.assertEqual(resp.status_code, 400)

    def test_create_defaults_half_life_from_classe(self):
        api = auth(self.user_a)
        resp = api.post(
            BASE, self._payload(classe=AssumptionNode.Classe.ANGLE),
            format='json')
        self.assertEqual(resp.status_code, 201, resp.content)
        self.assertEqual(resp.data['demi_vie_semaines'], 13)

    def test_create_keeps_explicit_half_life_override(self):
        api = auth(self.user_a)
        resp = api.post(
            BASE, self._payload(demi_vie_semaines=52), format='json')
        self.assertEqual(resp.status_code, 201, resp.content)
        self.assertEqual(resp.data['demi_vie_semaines'], 52)

    def test_view_only_permission_blocks_write(self):
        viewer = make_user(
            self.company_a, 'asg-viewer', ['adsengine_view'])
        api = auth(viewer)
        resp = api.post(BASE, self._payload(), format='json')
        self.assertEqual(resp.status_code, 403)
