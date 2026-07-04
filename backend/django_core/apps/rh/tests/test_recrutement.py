"""Tests FG189 — Recrutement (ATS-lite) : postes ouverts, candidatures, pipeline.

Couvre :
* ``OuverturePoste`` : création ``company`` posée CÔTÉ SERVEUR ; FK même société
  (``poste_ref`` / ``departement`` d'une autre société refusés) ; filtres
  (statut / département) ; CRUD ; isolation société.
* ``Candidature`` : création ``company`` posée CÔTÉ SERVEUR ; FK ``ouverture``
  même société ; pipeline d'étapes (recu → … → offre) ; filtres ; isolation.
* Service / action ``embaucher`` : crée un ``DossierEmploye`` (champs requis
  satisfaits), lie ``employe_cree``, passe l'étape à ``embauche``, bascule
  l'ouverture en ``pourvu`` quand pourvue ; idempotent (un 2e appel ne recrée
  pas) ; scopé société (404 autre tenant).
* Permission : un rôle normal est refusé (403).
"""
from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from authentication.models import Company
from apps.rh import services
from apps.rh.models import (
    Candidature,
    Departement,
    DossierEmploye,
    OuverturePoste,
    Poste,
)

User = get_user_model()

OUVERTURES_URL = '/api/django/rh/ouvertures-poste/'
CANDIDATURES_URL = '/api/django/rh/candidatures/'


def make_company(slug, nom):
    company, _ = Company.objects.get_or_create(slug=slug, defaults={'nom': nom})
    return company


def make_user(company, username, role='responsable'):
    return User.objects.create_user(
        username=username, password='x', company=company, role_legacy=role)


def make_ouverture(company, intitule='Technicien pose', **kwargs):
    # YHIRE14 — le statut par défaut du modèle est désormais 'brouillon'
    # (cycle d'approbation amont) ; ce fixture historique continue de
    # produire des ouvertures 'ouvert' par défaut pour ne pas casser les
    # tests existants qui postent des candidatures dessus.
    kwargs.setdefault('statut', OuverturePoste.Statut.OUVERT)
    return OuverturePoste.objects.create(
        company=company, intitule=intitule, **kwargs)


def make_candidature(company, ouverture, nom='Karim Bennani', **kwargs):
    return Candidature.objects.create(
        company=company, ouverture=ouverture, nom=nom, **kwargs)


def auth(user):
    api = APIClient()
    api.credentials(HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(user)}')
    return api


def rows(resp):
    data = resp.data
    return data['results'] if isinstance(data, dict) and 'results' in data \
        else data


class OuverturePosteCrudTests(TestCase):
    def setUp(self):
        self.co_a = make_company('op-a', 'A')
        self.co_b = make_company('op-b', 'B')
        self.user_a = make_user(self.co_a, 'op-user-a')
        self.user_b = make_user(self.co_b, 'op-user-b')
        self.poste_a = Poste.objects.create(
            company=self.co_a, intitule='Poseur')
        self.dep_a = Departement.objects.create(
            company=self.co_a, nom='Production')

    def test_create_company_cote_serveur(self):
        resp = auth(self.user_a).post(OUVERTURES_URL, {
            'intitule': 'Chef de chantier',
            'poste_ref': self.poste_a.id,
            'departement': self.dep_a.id,
            'description': 'Encadrement de pose résidentielle.',
            'nombre_postes': 2,
            'company': self.co_b.id,  # doit être ignorée
        }, format='json')
        self.assertEqual(resp.status_code, 201, resp.data)
        ouv = OuverturePoste.objects.get(id=resp.data['id'])
        self.assertEqual(ouv.company, self.co_a)
        self.assertEqual(ouv.nombre_postes, 2)
        self.assertEqual(ouv.statut, 'ouvert')
        self.assertEqual(ouv.poste_ref_id, self.poste_a.id)

    def test_poste_ref_autre_societe_refuse(self):
        poste_b = Poste.objects.create(company=self.co_b, intitule='B-poste')
        resp = auth(self.user_a).post(OUVERTURES_URL, {
            'intitule': 'X',
            'poste_ref': poste_b.id,
        }, format='json')
        self.assertEqual(resp.status_code, 400)
        self.assertIn('poste_ref', resp.data)

    def test_departement_autre_societe_refuse(self):
        dep_b = Departement.objects.create(company=self.co_b, nom='B-dep')
        resp = auth(self.user_a).post(OUVERTURES_URL, {
            'intitule': 'X',
            'departement': dep_b.id,
        }, format='json')
        self.assertEqual(resp.status_code, 400)
        self.assertIn('departement', resp.data)

    def test_filtre_statut_et_departement(self):
        make_ouverture(self.co_a, 'Ouverte', statut='ouvert',
                       departement=self.dep_a)
        make_ouverture(self.co_a, 'Close', statut='clos')
        resp = auth(self.user_a).get(f'{OUVERTURES_URL}?statut=ouvert')
        self.assertEqual(resp.status_code, 200)
        titres = {r['intitule'] for r in rows(resp)}
        self.assertEqual(titres, {'Ouverte'})
        resp2 = auth(self.user_a).get(
            f'{OUVERTURES_URL}?departement={self.dep_a.id}')
        titres2 = {r['intitule'] for r in rows(resp2)}
        self.assertEqual(titres2, {'Ouverte'})

    def test_isolation_list(self):
        make_ouverture(self.co_b, 'B-ouverture')
        resp = auth(self.user_a).get(OUVERTURES_URL)
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(len(rows(resp)), 0)

    def test_role_normal_refuse(self):
        normal = make_user(self.co_a, 'op-normal', role='normal')
        resp = auth(normal).get(OUVERTURES_URL)
        self.assertEqual(resp.status_code, 403)


class CandidatureCrudTests(TestCase):
    def setUp(self):
        self.co_a = make_company('cd-a', 'A')
        self.co_b = make_company('cd-b', 'B')
        self.user_a = make_user(self.co_a, 'cd-user-a')
        self.ouv_a = make_ouverture(self.co_a)

    def test_create_company_cote_serveur(self):
        resp = auth(self.user_a).post(CANDIDATURES_URL, {
            'ouverture': self.ouv_a.id,
            'nom': 'Yassine El Amrani',
            'email': 'y@example.com',
            'telephone': '0600000000',
            'source': 'ANAPEC',
            'company': self.co_b.id,  # doit être ignorée
        }, format='json')
        self.assertEqual(resp.status_code, 201, resp.data)
        cand = Candidature.objects.get(id=resp.data['id'])
        self.assertEqual(cand.company, self.co_a)
        self.assertEqual(cand.etape, 'recu')
        self.assertEqual(cand.source, 'ANAPEC')

    def test_ouverture_autre_societe_refuse(self):
        ouv_b = make_ouverture(self.co_b, 'B-ouverture')
        resp = auth(self.user_a).post(CANDIDATURES_URL, {
            'ouverture': ouv_b.id,
            'nom': 'X',
        }, format='json')
        self.assertEqual(resp.status_code, 400)
        self.assertIn('ouverture', resp.data)

    def test_pipeline_transition_etape(self):
        cand = make_candidature(self.co_a, self.ouv_a)
        for etape in ('preselection', 'entretien', 'offre'):
            resp = auth(self.user_a).patch(
                f'{CANDIDATURES_URL}{cand.id}/',
                {'etape': etape}, format='json')
            self.assertEqual(resp.status_code, 200, resp.data)
            cand.refresh_from_db()
            self.assertEqual(cand.etape, etape)

    def test_filtre_ouverture_et_etape(self):
        autre = make_ouverture(self.co_a, 'Autre')
        make_candidature(self.co_a, self.ouv_a, 'A1', etape='offre')
        make_candidature(self.co_a, autre, 'A2', etape='recu')
        resp = auth(self.user_a).get(
            f'{CANDIDATURES_URL}?ouverture={self.ouv_a.id}')
        noms = {r['nom'] for r in rows(resp)}
        self.assertEqual(noms, {'A1'})
        resp2 = auth(self.user_a).get(f'{CANDIDATURES_URL}?etape=recu')
        noms2 = {r['nom'] for r in rows(resp2)}
        self.assertEqual(noms2, {'A2'})

    def test_isolation_list(self):
        ouv_b = make_ouverture(self.co_b, 'B-ouverture')
        make_candidature(self.co_b, ouv_b, 'B-cand')
        resp = auth(self.user_a).get(CANDIDATURES_URL)
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(len(rows(resp)), 0)


class EmbaucherServiceTests(TestCase):
    def setUp(self):
        self.co_a = make_company('emb-a', 'A')
        self.poste_a = Poste.objects.create(
            company=self.co_a, intitule='Poseur')
        self.dep_a = Departement.objects.create(
            company=self.co_a, nom='Production')
        self.ouv = make_ouverture(
            self.co_a, 'Poseur', poste_ref=self.poste_a,
            departement=self.dep_a, nombre_postes=1)

    def test_embaucher_cree_dossier_et_lie(self):
        cand = make_candidature(self.co_a, self.ouv, 'Karim Bennani')
        dossier = services.embaucher(cand, matricule='M-001')
        self.assertIsInstance(dossier, DossierEmploye)
        # Champs requis satisfaits.
        self.assertEqual(dossier.company, self.co_a)
        self.assertEqual(dossier.matricule, 'M-001')
        self.assertEqual(dossier.prenom, 'Karim')
        self.assertEqual(dossier.nom, 'Bennani')
        # Dérivés de l'ouverture.
        self.assertEqual(dossier.poste_ref_id, self.poste_a.id)
        self.assertEqual(dossier.departement_id, self.dep_a.id)
        self.assertEqual(dossier.statut, DossierEmploye.Statut.EMBAUCHE)
        # Lien + étape.
        cand.refresh_from_db()
        self.assertEqual(cand.employe_cree_id, dossier.id)
        self.assertEqual(cand.etape, 'embauche')

    def test_embaucher_bascule_ouverture_pourvu(self):
        cand = make_candidature(self.co_a, self.ouv)
        services.embaucher(cand)
        self.ouv.refresh_from_db()
        self.assertEqual(self.ouv.statut, 'pourvu')

    def test_embaucher_idempotent(self):
        cand = make_candidature(self.co_a, self.ouv)
        d1 = services.embaucher(cand)
        avant = DossierEmploye.objects.count()
        d2 = services.embaucher(cand)
        apres = DossierEmploye.objects.count()
        self.assertEqual(d1.id, d2.id)
        self.assertEqual(avant, apres)

    def test_embaucher_matricule_par_defaut(self):
        cand = make_candidature(self.co_a, self.ouv, 'Solo')
        dossier = services.embaucher(cand)
        self.assertEqual(dossier.matricule, f'CAND-{cand.id}')
        # Nom mono-mot : prénom et nom non vides.
        self.assertEqual(dossier.prenom, 'Solo')
        self.assertEqual(dossier.nom, 'Solo')


class EmbaucherActionTests(TestCase):
    def setUp(self):
        self.co_a = make_company('ema-a', 'A')
        self.co_b = make_company('ema-b', 'B')
        self.user_a = make_user(self.co_a, 'ema-user-a')
        self.user_b = make_user(self.co_b, 'ema-user-b')
        self.ouv = make_ouverture(self.co_a, nombre_postes=2)

    def test_action_embauche_et_renvoie_employe(self):
        cand = make_candidature(self.co_a, self.ouv, 'Karim Bennani')
        resp = auth(self.user_a).post(
            f'{CANDIDATURES_URL}{cand.id}/embaucher/',
            {'matricule': 'M-009', 'type_contrat': 'cdd'}, format='json')
        self.assertEqual(resp.status_code, 200, resp.data)
        self.assertEqual(resp.data['etape'], 'embauche')
        self.assertIsNotNone(resp.data['employe_cree'])
        dossier = DossierEmploye.objects.get(id=resp.data['employe_cree'])
        self.assertEqual(dossier.matricule, 'M-009')
        self.assertEqual(dossier.type_contrat, 'cdd')

    def test_action_autre_societe_404(self):
        cand = make_candidature(self.co_a, self.ouv)
        resp = auth(self.user_b).post(
            f'{CANDIDATURES_URL}{cand.id}/embaucher/', {}, format='json')
        self.assertEqual(resp.status_code, 404)
        cand.refresh_from_db()
        self.assertIsNone(cand.employe_cree_id)

    def test_action_role_normal_refuse(self):
        normal = make_user(self.co_a, 'ema-normal', role='normal')
        cand = make_candidature(self.co_a, self.ouv)
        resp = auth(normal).post(
            f'{CANDIDATURES_URL}{cand.id}/embaucher/', {}, format='json')
        self.assertEqual(resp.status_code, 403)
