"""WIR277 — contexte SMQ ISO 4.1/4.2 + DIFFUSION des procédures qualité.

``PartieInteressee`` / ``ContexteOrganisation`` / ``DiffusionProcedure``
étaient modélisés et testés côté service, mais AUCUN endpoint ne les
exposait : ``diffuser_procedure`` n'avait aucun appelant, donc « mes lectures
en attente » restait vide pour toujours.

Couvre : isolation par société du contexte (singleton), diffusion avec
population VALIDÉE serveur (un id d'une autre société est ignoré), un accusé
par destinataire (idempotent), ``ajouter-lecteurs`` idempotent, et
``marquer-lu`` qui n'accuse QUE pour l'utilisateur courant (jamais un tiers).
"""
from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from authentication.models import Company
from apps.qhse.models import (
    AccuseLecture, ContexteOrganisation, DiffusionProcedure, PartieInteressee,
    ProcedureQualite,
)

User = get_user_model()

CONTEXTE = '/api/django/qhse/contexte-organisation/'
PARTIES = '/api/django/qhse/parties-interessees/'
DIFFUSIONS = '/api/django/qhse/diffusions-procedure/'
PROCEDURES = '/api/django/qhse/procedures/'


def _company(slug, nom):
    company, _ = Company.objects.get_or_create(
        slug=slug, defaults={'nom': nom})
    return company


def _user(company, username, role='responsable'):
    return User.objects.create_user(
        username=username, password='x', company=company, role_legacy=role)


def _auth(user):
    api = APIClient()
    api.credentials(HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(user)}')
    return api


class ContexteSmqApiTests(TestCase):
    def setUp(self):
        self.company = _company('wir277-co', 'WIR277 Co')
        self.autre = _company('wir277-autre', 'WIR277 Autre')
        self.user = _user(self.company, 'wir277_user')
        self.user_autre = _user(self.autre, 'wir277_autre')
        self.api = _auth(self.user)
        self.api_autre = _auth(self.user_autre)

    def test_contexte_est_un_singleton_cree_au_premier_get(self):
        self.assertEqual(ContexteOrganisation.objects.count(), 0)
        premier = self.api.get(CONTEXTE)
        self.assertEqual(premier.status_code, 200, premier.data)
        second = self.api.get(CONTEXTE)
        self.assertEqual(second.data['id'], premier.data['id'])
        self.assertEqual(
            ContexteOrganisation.objects.filter(
                company=self.company).count(), 1)

    def test_contexte_isole_par_societe(self):
        self.api.put(CONTEXTE, {'swot': 'Forces internes'}, format='json')
        vue_autre = self.api_autre.get(CONTEXTE)
        self.assertEqual(vue_autre.status_code, 200)
        # La société voisine obtient SON contexte (vierge), jamais celui-ci.
        self.assertEqual(vue_autre.data['swot'], '')
        self.assertNotEqual(vue_autre.data['id'], self.api.get(CONTEXTE).data['id'])

    def test_put_enregistre_swot_et_perimetre(self):
        resp = self.api.put(CONTEXTE, {
            'swot': 'Forces / faiblesses',
            'perimetre_smq': 'Installation PV raccordée',
        }, format='json')
        self.assertEqual(resp.status_code, 200, resp.data)
        contexte = ContexteOrganisation.objects.get(company=self.company)
        self.assertEqual(contexte.perimetre_smq, 'Installation PV raccordée')

    def test_parties_interessees_filtrables_par_pertinence(self):
        PartieInteressee.objects.create(
            company=self.company, partie='Client', pertinence='forte')
        PartieInteressee.objects.create(
            company=self.company, partie='Voisinage', pertinence='faible')
        resp = self.api.get(PARTIES, {'pertinence': 'forte'})
        rows = (resp.data['results']
                if isinstance(resp.data, dict) else resp.data)
        self.assertEqual([r['partie'] for r in rows], ['Client'])

    def test_partie_interessee_invisible_hors_societe(self):
        partie = PartieInteressee.objects.create(
            company=self.company, partie='Client')
        self.assertEqual(
            self.api_autre.get(f'{PARTIES}{partie.id}/').status_code, 404)


class DiffusionProcedureApiTests(TestCase):
    def setUp(self):
        self.company = _company('wir277-diff', 'WIR277 Diff')
        self.autre = _company('wir277-diff-autre', 'WIR277 Diff Autre')
        self.user = _user(self.company, 'wir277_diff_user')
        self.lecteur = _user(self.company, 'wir277_lecteur')
        self.etranger = _user(self.autre, 'wir277_etranger')
        self.api = _auth(self.user)
        self.api_lecteur = _auth(self.lecteur)
        self.procedure = ProcedureQualite.objects.create(
            company=self.company, reference='PRO-QUAL-004',
            titre='Réception des modules')

    def _diffuser(self, ids):
        return self.api.post(
            f'{PROCEDURES}{self.procedure.id}/diffuser/',
            {'user_ids': ids}, format='json')

    def test_diffusion_valide_la_population_cote_serveur(self):
        resp = self._diffuser([self.lecteur.id, self.etranger.id])
        self.assertEqual(resp.status_code, 201, resp.data)
        # L'utilisateur d'une AUTRE société n'est jamais diffusé.
        self.assertEqual(resp.data['nb_destinataires'], 1)
        self.assertEqual(
            resp.data['population_cible']['user_ids'], [self.lecteur.id])
        self.assertFalse(
            AccuseLecture.objects.filter(user=self.etranger).exists())

    def test_diffusion_sans_destinataire_valide_est_refusee(self):
        resp = self._diffuser([self.etranger.id])
        self.assertEqual(resp.status_code, 400)
        self.assertFalse(DiffusionProcedure.objects.exists())

    def test_un_accuse_par_destinataire(self):
        resp = self._diffuser([self.lecteur.id, self.lecteur.id])
        self.assertEqual(resp.status_code, 201, resp.data)
        self.assertEqual(
            AccuseLecture.objects.filter(
                diffusion_id=resp.data['id']).count(), 1)

    def test_ajouter_lecteurs_est_idempotent(self):
        diffusion_id = self._diffuser([self.lecteur.id]).data['id']
        autre_membre = _user(self.company, 'wir277_membre2')

        premier = self.api.post(
            f'{DIFFUSIONS}{diffusion_id}/ajouter-lecteurs/',
            {'user_ids': [autre_membre.id]}, format='json')
        self.assertEqual(premier.status_code, 200, premier.data)
        self.assertEqual(premier.data['ajoutes'], 1)

        second = self.api.post(
            f'{DIFFUSIONS}{diffusion_id}/ajouter-lecteurs/',
            {'user_ids': [autre_membre.id]}, format='json')
        self.assertEqual(second.data['ajoutes'], 0)
        self.assertEqual(
            AccuseLecture.objects.filter(diffusion_id=diffusion_id).count(), 2)

    def test_marquer_lu_nacquitte_que_lutilisateur_courant(self):
        diffusion_id = self._diffuser([self.lecteur.id]).data['id']
        # Le responsable tente d'acquitter POUR le lecteur : le corps est
        # ignoré, c'est SA propre lecture qui est signée.
        resp = self.api.post(
            f'{DIFFUSIONS}{diffusion_id}/marquer-lu/',
            {'user': self.lecteur.id}, format='json')
        self.assertEqual(resp.status_code, 200, resp.data)
        accuse_lecteur = AccuseLecture.objects.get(
            diffusion_id=diffusion_id, user=self.lecteur)
        self.assertIsNone(accuse_lecteur.lu_le)
        self.assertIsNotNone(
            AccuseLecture.objects.get(
                diffusion_id=diffusion_id, user=self.user).lu_le)

    def test_marquer_lu_est_idempotent_la_premiere_lecture_fait_foi(self):
        diffusion_id = self._diffuser([self.lecteur.id]).data['id']
        premier = self.api_lecteur.post(
            f'{DIFFUSIONS}{diffusion_id}/marquer-lu/')
        self.assertEqual(premier.status_code, 200, premier.data)
        lu_le = premier.data['lu_le']
        second = self.api_lecteur.post(
            f'{DIFFUSIONS}{diffusion_id}/marquer-lu/')
        self.assertEqual(second.data['lu_le'], lu_le)

    def test_diffusion_en_lecture_seule(self):
        resp = self.api.post(DIFFUSIONS, {
            'procedure': self.procedure.id,
        }, format='json')
        self.assertIn(resp.status_code, (403, 405))

    def test_mes_lectures_en_attente_se_remplit_apres_diffusion(self):
        self._diffuser([self.lecteur.id])
        resp = self.api_lecteur.get(
            f'{PROCEDURES}mes-lectures-en-attente/')
        self.assertEqual(resp.status_code, 200, resp.data)
        self.assertEqual(len(resp.data), 1)
        self.assertEqual(resp.data[0]['procedure_reference'], 'PRO-QUAL-004')
