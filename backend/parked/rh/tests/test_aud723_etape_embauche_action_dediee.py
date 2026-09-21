"""AUD723 — « embauche » ne se pose plus par un PATCH direct de `etape`.

DÉFAUT (rouge avant ce correctif) : `CandidatureSerializer.Meta.read_only_fields`
protégeait `employe_cree` / `vivier_origine` / les dates, mais PAS `etape`.
Un `PATCH /candidatures/{id}/ {"etape": "embauche"}` passait la validation,
journalisait la transition (`CandidatureViewSet.perform_update`) et envoyait
l'email automatique « vous êtes embauché » — alors qu'AUCUN `DossierEmploye`
n'était créé, que `employe_cree` restait NULL et que l'`OuverturePoste` ne
basculait jamais en pourvu. Seule l'action dédiée `POST {id}/embaucher/`
(→ `services.embaucher`) produit réellement ces effets.

Après correctif : le PATCH vers « embauche » est refusé et renvoie vers
l'action ; les autres transitions du pipeline restent éditables (c'est ce que
fait l'écran Recrutement).
"""
from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from authentication.models import Company
from apps.rh.models import Candidature, DossierEmploye, OuverturePoste

User = get_user_model()

CANDIDATURES = '/api/django/rh/candidatures/'


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


class EtapeEmbaucheTests(TestCase):
    def setUp(self):
        self.co = make_company('aud723', 'A')
        self.rh = make_user(self.co, 'aud723-rh')
        self.ouverture = OuverturePoste.objects.create(
            company=self.co, intitule='Technicien PV', nombre_postes=1,
            statut=OuverturePoste.Statut.OUVERT)
        self.cand = Candidature.objects.create(
            company=self.co, ouverture=self.ouverture,
            nom='Karim Bennani', email='karim@example.ma')

    def test_patch_vers_embauche_refuse(self):
        resp = auth(self.rh).patch(
            f'{CANDIDATURES}{self.cand.pk}/', {'etape': 'embauche'})
        self.assertEqual(resp.status_code, 400, resp.data)
        self.assertIn('etape', resp.data)
        self.cand.refresh_from_db()
        self.assertNotEqual(self.cand.etape, Candidature.Etape.EMBAUCHE)
        self.assertIsNone(self.cand.employe_cree_id)
        self.ouverture.refresh_from_db()
        self.assertEqual(self.ouverture.statut, OuverturePoste.Statut.OUVERT)
        self.assertFalse(DossierEmploye.objects.exists())

    def test_creation_directe_a_l_etape_embauche_refusee(self):
        resp = auth(self.rh).post(CANDIDATURES, {
            'ouverture': self.ouverture.id, 'nom': 'Sara Alami',
            'etape': 'embauche',
        })
        self.assertEqual(resp.status_code, 400, resp.data)
        self.assertIn('etape', resp.data)

    def test_les_autres_transitions_restent_editables(self):
        for etape in ('preselection', 'entretien', 'offre', 'rejete'):
            resp = auth(self.rh).patch(
                f'{CANDIDATURES}{self.cand.pk}/', {'etape': etape})
            self.assertEqual(resp.status_code, 200, resp.data)
            self.assertEqual(resp.data['etape'], etape)

    def test_action_dediee_reste_le_seul_chemin_et_produit_les_effets(self):
        resp = auth(self.rh).post(
            f'{CANDIDATURES}{self.cand.pk}/embaucher/',
            {'matricule': 'M-723'})
        self.assertEqual(resp.status_code, 200, resp.data)
        self.assertEqual(resp.data['etape'], 'embauche')
        self.assertIsNotNone(resp.data['employe_cree'])
        self.ouverture.refresh_from_db()
        self.assertEqual(self.ouverture.statut, 'pourvu')

    def test_patch_sur_une_candidature_deja_embauchee_ne_regresse_pas(self):
        """Renvoyer l'étape courante d'un embauché ne doit pas planter."""
        auth(self.rh).post(f'{CANDIDATURES}{self.cand.pk}/embaucher/', {})
        resp = auth(self.rh).patch(
            f'{CANDIDATURES}{self.cand.pk}/',
            {'etape': 'embauche', 'note': 'Dossier complet'})
        self.assertEqual(resp.status_code, 200, resp.data)
        self.assertEqual(resp.data['etape'], 'embauche')
