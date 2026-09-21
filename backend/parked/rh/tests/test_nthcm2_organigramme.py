"""Tests NTHCM2 — organigramme hiérarchique (selector + endpoint).

Couvre :
* l'arbre imbrique toute la société depuis les employés SANS manager ;
* la recherche marque le nœud trouvé (``correspond``) ET ses ancêtres
  (``sur_chemin``) — c'est ce qui permet à l'écran de déplier jusqu'à lui ;
* aucune boucle infinie même si des données LEGACY portent un cycle
  (``tronque``) ;
* un employé SORTI est exclu, et un employé dont le manager est sorti
  devient une racine plutôt que de disparaître ;
* ``?racine=`` limite l'arbre à une branche ;
* isolation société ;
* l'exemple de contrat committé a EXACTEMENT les clés servies (PACT10).
"""
import json
from pathlib import Path

from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from authentication.models import Company
from apps.rh import selectors
from apps.rh.models import Departement, DossierEmploye, Poste

User = get_user_model()

CONTRAT = (Path(__file__).resolve().parent.parent
           / 'contract_samples' / 'organigramme.json')


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


class OrganigrammeTests(TestCase):
    def setUp(self):
        self.co = make_company('nthcm2-a', 'A')
        self.rh = make_user(self.co, 'nthcm2-rh')
        self.api = auth(self.rh)
        self.dept = Departement.objects.create(
            company=self.co, nom='Travaux', code='TRV')
        self.poste = Poste.objects.create(
            company=self.co, intitule='Chef de chantier')
        self.dg = DossierEmploye.objects.create(
            company=self.co, matricule='EMP-001', nom='Alami', prenom='Sara')
        self.chef = DossierEmploye.objects.create(
            company=self.co, matricule='EMP-002', nom='Bennani',
            prenom='Youssef', manager=self.dg, poste_ref=self.poste,
            departement=self.dept)
        self.poseuse = DossierEmploye.objects.create(
            company=self.co, matricule='EMP-003', nom='Cherkaoui',
            prenom='Imane', manager=self.chef, departement=self.dept)

    def test_arbre_imbrique_depuis_les_racines(self):
        arbre = selectors.arbre_hierarchique(self.co)
        self.assertEqual(len(arbre['racines']), 1)
        racine = arbre['racines'][0]
        self.assertEqual(racine['id'], self.dg.id)
        self.assertEqual(racine['employe'], 'Alami Sara')
        self.assertEqual(racine['nb_rapports_directs'], 1)
        enfant = racine['subordonnes'][0]
        self.assertEqual(enfant['id'], self.chef.id)
        self.assertEqual(enfant['poste'], 'Chef de chantier')
        self.assertEqual(enfant['departement'], 'Travaux')
        self.assertEqual(
            enfant['subordonnes'][0]['id'], self.poseuse.id)
        self.assertEqual(arbre['effectif'], 3)

    def test_photo_vide_quand_aucun_avatar(self):
        arbre = selectors.arbre_hierarchique(self.co)
        self.assertEqual(arbre['racines'][0]['photo'], '')

    def test_recherche_marque_le_noeud_et_ses_ancetres(self):
        arbre = selectors.arbre_hierarchique(self.co, q='cherkaoui')
        racine = arbre['racines'][0]
        self.assertFalse(racine['correspond'])
        self.assertTrue(racine['sur_chemin'])
        chef = racine['subordonnes'][0]
        self.assertFalse(chef['correspond'])
        self.assertTrue(chef['sur_chemin'])
        poseuse = chef['subordonnes'][0]
        self.assertTrue(poseuse['correspond'])
        self.assertTrue(poseuse['sur_chemin'])

    def test_recherche_sur_le_poste(self):
        arbre = selectors.arbre_hierarchique(self.co, q='chef de chantier')
        chef = arbre['racines'][0]['subordonnes'][0]
        self.assertTrue(chef['correspond'])

    def test_recherche_sans_correspondance(self):
        arbre = selectors.arbre_hierarchique(self.co, q='zzz-introuvable')
        racine = arbre['racines'][0]
        self.assertFalse(racine['sur_chemin'])

    def test_cycle_legacy_ne_boucle_pas(self):
        # Cycle imposé EN BASE (update brut) : `clean()` (NTHCM1) le refuse à
        # la saisie, mais un import legacy peut en porter un.
        DossierEmploye.objects.filter(pk=self.dg.pk).update(
            manager=self.poseuse)
        arbre = selectors.arbre_hierarchique(self.co, racine_id=self.dg.id)
        # Ne boucle pas : la descente s'arrête sur l'ancêtre déjà rencontré.
        noeud = arbre['racines'][0]
        profondeur = 0
        while noeud['subordonnes']:
            noeud = noeud['subordonnes'][0]
            profondeur += 1
            self.assertLessEqual(
                profondeur, selectors.PROFONDEUR_MAX_ORGANIGRAMME)
        self.assertTrue(noeud['tronque'])

    def test_employe_sorti_exclu_et_son_rattache_devient_racine(self):
        self.chef.statut = DossierEmploye.Statut.SORTI
        self.chef.save(update_fields=['statut'])
        arbre = selectors.arbre_hierarchique(self.co)
        ids = sorted(racine['id'] for racine in arbre['racines'])
        self.assertEqual(ids, sorted([self.dg.id, self.poseuse.id]))
        self.assertEqual(arbre['effectif'], 2)

    def test_racine_explicite(self):
        arbre = selectors.arbre_hierarchique(
            self.co, racine_id=self.chef.id)
        self.assertEqual(len(arbre['racines']), 1)
        self.assertEqual(arbre['racines'][0]['id'], self.chef.id)

    def test_racine_inconnue_renvoie_un_arbre_vide(self):
        arbre = selectors.arbre_hierarchique(self.co, racine_id=999999)
        self.assertEqual(arbre['racines'], [])

    def test_isolation_societe(self):
        autre = make_company('nthcm2-b', 'B')
        DossierEmploye.objects.create(
            company=autre, matricule='B-1', nom='Voisin', prenom='V')
        arbre = selectors.arbre_hierarchique(self.co)
        self.assertEqual(arbre['effectif'], 3)

    def test_endpoint_organigramme(self):
        reponse = self.api.get('/api/django/rh/employes/organigramme/')
        self.assertEqual(reponse.status_code, 200, reponse.content)
        self.assertEqual(reponse.data['effectif'], 3)
        self.assertEqual(len(reponse.data['racines']), 1)

    def test_endpoint_recherche(self):
        reponse = self.api.get(
            '/api/django/rh/employes/organigramme/?q=cherkaoui')
        self.assertEqual(reponse.status_code, 200, reponse.content)
        self.assertEqual(reponse.data['recherche'], 'cherkaoui')
        self.assertTrue(reponse.data['racines'][0]['sur_chemin'])

    def test_contrat_committe_a_les_memes_cles(self):
        """PACT10 — l'exemple JSON doit refléter la forme RÉELLE servie."""
        contrat = json.loads(CONTRAT.read_text(encoding='utf-8'))
        servi = selectors.arbre_hierarchique(self.co, q='bennani')
        self.assertEqual(
            sorted(contrat['exemple']), sorted(servi))
        self.assertEqual(
            sorted(contrat['exemple']['racines'][0]),
            sorted(servi['racines'][0]))
        self.assertEqual(
            sorted(contrat['exemple_vide']), sorted(servi))
