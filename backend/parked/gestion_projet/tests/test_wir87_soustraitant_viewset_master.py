"""Tests WIR87 — carnet de sous-traitants (gestion_projet) : ferme la
« régression PROJ38/ARC22 » au niveau du ViewSet.

ARC22 avait ajouté un chemin de création RECOMMANDÉ
(``services.creer_sous_traitant_via_master``) qui pose le lien vers le
master DC34 (``stock.Fournisseur`` type=service + ``SousTraitantProfile``),
mais laissait l'ANCIEN chemin (``SousTraitantViewSet.perform_create``, bare
``serializer.save``) grand ouvert — une création via l'API REST créait donc
une ligne SANS lien. WIR87 ferme ce chemin : le ViewSet route désormais
systématiquement par le master, et une modification (PATCH) GÈLE la
cohérence des colonnes dupliquées entre le carnet local et le Fournisseur
lié (écriture des deux côtés dans le même appel).

Couvre : POST pose fournisseur (plus de ligne orpheline via l'API) + crée
le Fournisseur/profil correspondant ; PATCH synchronise les champs
d'identité + le statut actif sur le Fournisseur lié ; une ligne locale NON
liée (legacy, pré-ARC22) reste modifiable localement sans lever d'erreur ;
isolation société inchangée.

Run:
    docker compose exec django_core python manage.py test \
        apps.gestion_projet.tests.test_wir87_soustraitant_viewset_master -v 2
"""
from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from authentication.models import Company

from apps.gestion_projet.models import SousTraitant
from apps.stock.models import Fournisseur, SousTraitantProfile

User = get_user_model()

ST = '/api/django/gestion-projet/sous-traitants/'


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


class SousTraitantViewSetCreationViaMasterTests(TestCase):
    def setUp(self):
        self.co = make_company('wir87-create', 'WIR87 Co')
        self.user = make_user(self.co, 'wir87-create-user')

    def test_creation_api_pose_le_lien_fournisseur(self):
        api = auth(self.user)
        resp = api.post(ST, {
            'nom': 'Terrassement Atlas', 'specialite': 'terrassement',
            'telephone': '0600000001',
        }, format='json')
        self.assertEqual(resp.status_code, 201, resp.data)

        st = SousTraitant.objects.get(id=resp.data['id'])
        self.assertIsNotNone(st.fournisseur_id)
        fournisseur = Fournisseur.objects.get(pk=st.fournisseur_id)
        self.assertEqual(fournisseur.type, Fournisseur.Type.SERVICE)
        self.assertEqual(fournisseur.nom, 'Terrassement Atlas')
        profil = SousTraitantProfile.objects.get(fournisseur=fournisseur)
        self.assertEqual(profil.metier, SousTraitantProfile.Metier.TERRASSEMENT)

    def test_creation_api_company_posee_serveur(self):
        api = auth(self.user)
        resp = api.post(ST, {'nom': 'Levage Pro'}, format='json')
        self.assertEqual(resp.status_code, 201, resp.data)
        st = SousTraitant.objects.get(id=resp.data['id'])
        self.assertEqual(st.company_id, self.co.id)


class SousTraitantViewSetUpdateGeleColonnesTests(TestCase):
    def setUp(self):
        self.co = make_company('wir87-update', 'WIR87 Update Co')
        self.user = make_user(self.co, 'wir87-update-user')

    def _cree_lie(self, nom='Electricite Nord', telephone='0611111111'):
        api = auth(self.user)
        resp = api.post(ST, {'nom': nom, 'telephone': telephone}, format='json')
        self.assertEqual(resp.status_code, 201, resp.data)
        return SousTraitant.objects.get(id=resp.data['id'])

    def test_patch_synchronise_le_telephone_sur_le_fournisseur_lie(self):
        st = self._cree_lie()
        api = auth(self.user)
        resp = api.patch(f'{ST}{st.id}/', {'telephone': '0699999999'}, format='json')
        self.assertEqual(resp.status_code, 200, resp.data)

        st.refresh_from_db()
        self.assertEqual(st.telephone, '0699999999')
        fournisseur = Fournisseur.objects.get(pk=st.fournisseur_id)
        self.assertEqual(fournisseur.telephone, '0699999999')

    def test_patch_synchronise_actif_sur_le_profil_lie(self):
        st = self._cree_lie()
        api = auth(self.user)
        resp = api.patch(f'{ST}{st.id}/', {'actif': False}, format='json')
        self.assertEqual(resp.status_code, 200, resp.data)

        st.refresh_from_db()
        self.assertFalse(st.actif)
        profil = SousTraitantProfile.objects.get(fournisseur_id=st.fournisseur_id)
        self.assertFalse(profil.actif)

    def test_patch_synchronise_specialite_vers_metier_sur_le_profil_lie(self):
        st = self._cree_lie()
        api = auth(self.user)
        resp = api.patch(f'{ST}{st.id}/', {'specialite': 'levage'}, format='json')
        self.assertEqual(resp.status_code, 200, resp.data)

        profil = SousTraitantProfile.objects.get(fournisseur_id=st.fournisseur_id)
        self.assertEqual(profil.metier, SousTraitantProfile.Metier.LEVAGE)

    def test_patch_ligne_legacy_non_liee_reste_modifiable_localement(self):
        """Une ligne créée AVANT ARC22/WIR87 (jamais liée, pas de backfill
        exécuté) reste modifiable localement — jamais bloquant."""
        st = SousTraitant.objects.create(
            company=self.co, nom='Legacy SARL', telephone='0600000000')
        self.assertIsNone(st.fournisseur_id)

        api = auth(self.user)
        resp = api.patch(f'{ST}{st.id}/', {'telephone': '0611112222'}, format='json')
        self.assertEqual(resp.status_code, 200, resp.data)

        st.refresh_from_db()
        self.assertEqual(st.telephone, '0611112222')
        self.assertIsNone(st.fournisseur_id)


class SousTraitantViewSetIsolationTests(TestCase):
    def setUp(self):
        self.co_a = make_company('wir87-iso-a', 'A')
        self.co_b = make_company('wir87-iso-b', 'B')
        self.user_a = make_user(self.co_a, 'wir87-iso-a-user')
        self.user_b = make_user(self.co_b, 'wir87-iso-b-user')

    def test_isolation_societe_sur_la_creation(self):
        api_a = auth(self.user_a)
        resp = api_a.post(ST, {'nom': 'ST A'}, format='json')
        self.assertEqual(resp.status_code, 201, resp.data)
        st_a = SousTraitant.objects.get(id=resp.data['id'])

        api_b = auth(self.user_b)
        resp_get = api_b.get(f'{ST}{st_a.id}/')
        self.assertEqual(resp_get.status_code, 404)
