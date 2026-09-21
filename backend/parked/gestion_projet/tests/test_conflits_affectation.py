"""Tests PROJ19 -- Detection de conflits d'affectation.

Couvre :
- Meme ressource sur deux affectations qui se chevauchent -> conflit
- Affectations disjointes (memes dates) -> aucun conflit
- Plusieurs ressources, certaines en conflit, d'autres non
- Conflit via une equipe (membre affecte en direct + via son equipe)
- Affectation d'actif materiel ignoree (pas une personne)
- Affectation posee sur une indisponibilite (bonus)
- Garde fenetre vide (fin < debut) -> aucun conflit, sans crash
- Scoping societe (affectations d'une autre societe ignorees)
- Endpoint API : OK + parametres obligatoires / invalides -> 400 + isolation
"""
from datetime import date
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from authentication.models import Company
from apps.gestion_projet import selectors
from apps.gestion_projet.models import (
    AffectationRessource,
    Equipe,
    Indisponibilite,
    Projet,
    RessourceProfil,
    Tache,
)

User = get_user_model()

CONFLITS_URL = (
    '/api/django/gestion-projet/ressources/conflits-affectation/')


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

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


def make_projet(company, code='P1'):
    return Projet.objects.create(company=company, code=code, nom='Projet test')


def make_tache(company, projet, libelle='Tache test'):
    return Tache.objects.create(
        company=company, projet=projet, libelle=libelle)


def make_ressource(company, nom='Technicien', actif=True):
    return RessourceProfil.objects.create(
        company=company, nom=nom, cout_horaire=Decimal('0'), actif=actif)


def make_affectation(company, tache, debut, fin, ressource=None, equipe=None,
                     actif_type='', actif_id=None, charge=Decimal('1')):
    return AffectationRessource.objects.create(
        company=company, tache=tache,
        ressource=ressource, equipe=equipe,
        actif_type=actif_type, actif_id=actif_id,
        date_debut=debut, date_fin=fin,
        charge_jours=charge)


def ligne_for(resultat, ressource):
    for ligne in resultat['lignes']:
        if ligne['ressource'] == ressource.id:
            return ligne
    return None


# ---------------------------------------------------------------------------
# Selecteur : conflit / pas de conflit pour une ressource
# ---------------------------------------------------------------------------

class ConflitRessourceTests(TestCase):

    def setUp(self):
        self.co = make_company('proj19-conf', 'Societe A')
        self.res = make_ressource(self.co, 'Conf Res')
        self.projet = make_projet(self.co, 'P19-CONF')
        self.t1 = make_tache(self.co, self.projet, 'Tache 1')
        self.t2 = make_tache(self.co, self.projet, 'Tache 2')

    def test_meme_ressource_chevauchement_detecte_conflit(self):
        # Deux affectations sur la meme ressource avec fenetres qui se
        # chevauchent (01-05 et 03-07) -> un conflit.
        make_affectation(
            self.co, self.t1, date(2026, 6, 1), date(2026, 6, 5),
            ressource=self.res)
        make_affectation(
            self.co, self.t2, date(2026, 6, 3), date(2026, 6, 7),
            ressource=self.res)
        result = selectors.conflits_affectation(
            self.co, date(2026, 6, 1), date(2026, 6, 30))
        self.assertEqual(result['nb_ressources_en_conflit'], 1)
        self.assertEqual(result['nb_conflits'], 1)
        ligne = ligne_for(result, self.res)
        self.assertIsNotNone(ligne)
        self.assertEqual(len(ligne['conflits']), 1)
        conflit = ligne['conflits'][0]
        self.assertEqual(conflit['chevauchement_debut'], '2026-06-03')
        self.assertEqual(conflit['chevauchement_fin'], '2026-06-05')
        self.assertFalse(conflit['via_equipe'])

    def test_chevauchement_bornes_inclusives(self):
        # Fenetres qui se touchent sur un seul jour (05) -> conflit (inclusif).
        make_affectation(
            self.co, self.t1, date(2026, 6, 1), date(2026, 6, 5),
            ressource=self.res)
        make_affectation(
            self.co, self.t2, date(2026, 6, 5), date(2026, 6, 9),
            ressource=self.res)
        result = selectors.conflits_affectation(
            self.co, date(2026, 6, 1), date(2026, 6, 30))
        self.assertEqual(result['nb_conflits'], 1)
        ligne = ligne_for(result, self.res)
        self.assertEqual(ligne['conflits'][0]['chevauchement_debut'],
                         '2026-06-05')
        self.assertEqual(ligne['conflits'][0]['chevauchement_fin'],
                         '2026-06-05')

    def test_affectations_disjointes_aucun_conflit(self):
        # 01-05 puis 06-09 : aucune journee commune -> pas de conflit.
        make_affectation(
            self.co, self.t1, date(2026, 6, 1), date(2026, 6, 5),
            ressource=self.res)
        make_affectation(
            self.co, self.t2, date(2026, 6, 6), date(2026, 6, 9),
            ressource=self.res)
        result = selectors.conflits_affectation(
            self.co, date(2026, 6, 1), date(2026, 6, 30))
        self.assertEqual(result['nb_conflits'], 0)
        self.assertEqual(result['lignes'], [])

    def test_une_seule_affectation_aucun_conflit(self):
        make_affectation(
            self.co, self.t1, date(2026, 6, 1), date(2026, 6, 5),
            ressource=self.res)
        result = selectors.conflits_affectation(
            self.co, date(2026, 6, 1), date(2026, 6, 30))
        self.assertEqual(result['nb_conflits'], 0)

    def test_trois_affectations_chevauchantes_donnent_trois_paires(self):
        # 01-10, 03-12, 05-08 : toutes se chevauchent deux a deux -> 3 paires.
        t3 = make_tache(self.co, self.projet, 'Tache 3')
        make_affectation(
            self.co, self.t1, date(2026, 6, 1), date(2026, 6, 10),
            ressource=self.res)
        make_affectation(
            self.co, self.t2, date(2026, 6, 3), date(2026, 6, 12),
            ressource=self.res)
        make_affectation(
            self.co, t3, date(2026, 6, 5), date(2026, 6, 8),
            ressource=self.res)
        result = selectors.conflits_affectation(
            self.co, date(2026, 6, 1), date(2026, 6, 30))
        ligne = ligne_for(result, self.res)
        self.assertEqual(len(ligne['conflits']), 3)
        self.assertEqual(result['nb_conflits'], 3)

    def test_affectation_hors_fenetre_ignoree(self):
        # Deux affectations qui se chevauchent MAIS hors de la fenetre
        # demandee -> aucun conflit remonte.
        make_affectation(
            self.co, self.t1, date(2026, 7, 1), date(2026, 7, 5),
            ressource=self.res)
        make_affectation(
            self.co, self.t2, date(2026, 7, 3), date(2026, 7, 7),
            ressource=self.res)
        result = selectors.conflits_affectation(
            self.co, date(2026, 6, 1), date(2026, 6, 30))
        self.assertEqual(result['nb_conflits'], 0)


# ---------------------------------------------------------------------------
# Selecteur : plusieurs ressources
# ---------------------------------------------------------------------------

class MultiRessourceTests(TestCase):

    def setUp(self):
        self.co = make_company('proj19-multi', 'Societe A')
        self.r1 = make_ressource(self.co, 'Multi R1')
        self.r2 = make_ressource(self.co, 'Multi R2')
        self.projet = make_projet(self.co, 'P19-MULTI')
        self.t1 = make_tache(self.co, self.projet, 'Tache 1')
        self.t2 = make_tache(self.co, self.projet, 'Tache 2')

    def test_seule_ressource_en_conflit_remontee(self):
        # r1 double-bookee ; r2 a une seule affectation -> seule r1 remonte.
        make_affectation(
            self.co, self.t1, date(2026, 6, 1), date(2026, 6, 5),
            ressource=self.r1)
        make_affectation(
            self.co, self.t2, date(2026, 6, 3), date(2026, 6, 7),
            ressource=self.r1)
        make_affectation(
            self.co, self.t1, date(2026, 6, 1), date(2026, 6, 5),
            ressource=self.r2)
        result = selectors.conflits_affectation(
            self.co, date(2026, 6, 1), date(2026, 6, 30))
        self.assertEqual(result['nb_ressources_en_conflit'], 1)
        self.assertIsNotNone(ligne_for(result, self.r1))
        self.assertIsNone(ligne_for(result, self.r2))


# ---------------------------------------------------------------------------
# Selecteur : conflit via equipe + actif materiel ignore
# ---------------------------------------------------------------------------

class EquipeEtActifTests(TestCase):

    def setUp(self):
        self.co = make_company('proj19-eq', 'Societe A')
        self.res = make_ressource(self.co, 'Eq Membre')
        self.equipe = Equipe.objects.create(company=self.co, nom='Equipe Y')
        self.equipe.membres.add(self.res)
        self.projet = make_projet(self.co, 'P19-EQ')
        self.t1 = make_tache(self.co, self.projet, 'Tache 1')
        self.t2 = make_tache(self.co, self.projet, 'Tache 2')

    def test_conflit_direct_et_via_equipe(self):
        # Membre affecte en direct (01-05) ET via son equipe (03-07) ->
        # conflit, marque via_equipe.
        make_affectation(
            self.co, self.t1, date(2026, 6, 1), date(2026, 6, 5),
            ressource=self.res)
        make_affectation(
            self.co, self.t2, date(2026, 6, 3), date(2026, 6, 7),
            equipe=self.equipe)
        result = selectors.conflits_affectation(
            self.co, date(2026, 6, 1), date(2026, 6, 30))
        ligne = ligne_for(result, self.res)
        self.assertIsNotNone(ligne)
        self.assertEqual(len(ligne['conflits']), 1)
        self.assertTrue(ligne['conflits'][0]['via_equipe'])

    def test_actif_materiel_ignore(self):
        # Une affectation d'actif materiel chevauchant une affectation
        # ressource ne cree PAS de conflit (un actif n'est pas une personne).
        make_affectation(
            self.co, self.t1, date(2026, 6, 1), date(2026, 6, 5),
            ressource=self.res)
        make_affectation(
            self.co, self.t2, date(2026, 6, 3), date(2026, 6, 7),
            actif_type=AffectationRessource.TypeActif.ACTIF_FLOTTE,
            actif_id=42)
        result = selectors.conflits_affectation(
            self.co, date(2026, 6, 1), date(2026, 6, 30))
        # La seule affectation-ressource ne suffit pas a creer un conflit.
        self.assertEqual(result['nb_conflits'], 0)


# ---------------------------------------------------------------------------
# Selecteur : affectation posee sur une indisponibilite (bonus)
# ---------------------------------------------------------------------------

class AffectationSurIndispoTests(TestCase):

    def setUp(self):
        self.co = make_company('proj19-indispo', 'Societe A')
        self.res = make_ressource(self.co, 'Indispo Res')
        self.projet = make_projet(self.co, 'P19-INDISPO')
        self.tache = make_tache(self.co, self.projet, 'Tache')

    def test_affectation_sur_conge_signalee(self):
        # Une seule affectation, mais posee pendant un conge -> remontee dans
        # affectations_sur_indispo (sans conflit de double-booking).
        Indisponibilite.objects.create(
            company=self.co, ressource=self.res,
            type_indispo=Indisponibilite.TypeIndispo.CONGE,
            date_debut=date(2026, 6, 2), date_fin=date(2026, 6, 4))
        make_affectation(
            self.co, self.tache, date(2026, 6, 1), date(2026, 6, 5),
            ressource=self.res)
        result = selectors.conflits_affectation(
            self.co, date(2026, 6, 1), date(2026, 6, 30))
        ligne = ligne_for(result, self.res)
        self.assertIsNotNone(ligne)
        self.assertEqual(len(ligne['conflits']), 0)
        self.assertEqual(len(ligne['affectations_sur_indispo']), 1)
        self.assertEqual(
            ligne['affectations_sur_indispo'][0]['type_indispo'], 'conge')


# ---------------------------------------------------------------------------
# Selecteur : garde fenetre vide
# ---------------------------------------------------------------------------

class FenetreVideTests(TestCase):

    def setUp(self):
        self.co = make_company('proj19-vide', 'Societe A')
        self.res = make_ressource(self.co, 'Vide Res')
        self.projet = make_projet(self.co, 'P19-VIDE')
        self.t1 = make_tache(self.co, self.projet, 'Tache 1')
        self.t2 = make_tache(self.co, self.projet, 'Tache 2')

    def test_fenetre_inversee_aucun_conflit_sans_crash(self):
        # Deux affectations qui se chevauchent, mais fin < debut -> garde.
        make_affectation(
            self.co, self.t1, date(2026, 6, 1), date(2026, 6, 5),
            ressource=self.res)
        make_affectation(
            self.co, self.t2, date(2026, 6, 3), date(2026, 6, 7),
            ressource=self.res)
        result = selectors.conflits_affectation(
            self.co, date(2026, 6, 30), date(2026, 6, 1))
        self.assertEqual(result['nb_conflits'], 0)
        self.assertEqual(result['nb_ressources_en_conflit'], 0)
        self.assertEqual(result['lignes'], [])


# ---------------------------------------------------------------------------
# Selecteur : scoping societe
# ---------------------------------------------------------------------------

class ScopingTests(TestCase):

    def setUp(self):
        self.co_a = make_company('proj19-scope-a', 'Societe A')
        self.co_b = make_company('proj19-scope-b', 'Societe B')
        self.res_b = make_ressource(self.co_b, 'Res B')
        self.projet_b = make_projet(self.co_b, 'P19-SB')
        self.t1b = make_tache(self.co_b, self.projet_b, 'Tache B1')
        self.t2b = make_tache(self.co_b, self.projet_b, 'Tache B2')

    def test_affectations_autre_societe_ignorees(self):
        # Double-booking dans la societe B, requete sur la societe A -> rien.
        make_affectation(
            self.co_b, self.t1b, date(2026, 6, 1), date(2026, 6, 5),
            ressource=self.res_b)
        make_affectation(
            self.co_b, self.t2b, date(2026, 6, 3), date(2026, 6, 7),
            ressource=self.res_b)
        result = selectors.conflits_affectation(
            self.co_a, date(2026, 6, 1), date(2026, 6, 30))
        self.assertEqual(result['nb_conflits'], 0)
        self.assertEqual(result['lignes'], [])


# ---------------------------------------------------------------------------
# Endpoint API
# ---------------------------------------------------------------------------

class ConflitsApiTests(TestCase):

    def setUp(self):
        self.co = make_company('proj19-api', 'Societe A')
        self.user = make_user(self.co, 'proj19-api-u')
        self.res = make_ressource(self.co, 'Api Res')
        self.projet = make_projet(self.co, 'P19-API')
        self.t1 = make_tache(self.co, self.projet, 'Tache 1')
        self.t2 = make_tache(self.co, self.projet, 'Tache 2')
        self.api = auth(self.user)

    def test_endpoint_detecte_conflit(self):
        make_affectation(
            self.co, self.t1, date(2026, 6, 1), date(2026, 6, 5),
            ressource=self.res)
        make_affectation(
            self.co, self.t2, date(2026, 6, 3), date(2026, 6, 7),
            ressource=self.res)
        resp = self.api.get(
            CONFLITS_URL, {'debut': '2026-06-01', 'fin': '2026-06-30'})
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.data['nb_conflits'], 1)
        self.assertEqual(resp.data['nb_ressources_en_conflit'], 1)

    def test_parametres_manquants_400(self):
        resp = self.api.get(CONFLITS_URL, {'debut': '2026-06-01'})
        self.assertEqual(resp.status_code, 400)

    def test_date_invalide_400(self):
        resp = self.api.get(
            CONFLITS_URL, {'debut': 'pas-une-date', 'fin': '2026-06-05'})
        self.assertEqual(resp.status_code, 400)

    def test_fin_avant_debut_400(self):
        resp = self.api.get(
            CONFLITS_URL, {'debut': '2026-06-30', 'fin': '2026-06-01'})
        self.assertEqual(resp.status_code, 400)

    def test_isolation_societe_api(self):
        # Conflit dans une autre societe -> invisible via l'API de la societe A.
        co_b = make_company('proj19-api-b', 'Societe B')
        res_b = make_ressource(co_b, 'Res B autre')
        projet_b = make_projet(co_b, 'P19-API-B')
        t1b = make_tache(co_b, projet_b, 'Tache B1')
        t2b = make_tache(co_b, projet_b, 'Tache B2')
        make_affectation(
            co_b, t1b, date(2026, 6, 1), date(2026, 6, 5), ressource=res_b)
        make_affectation(
            co_b, t2b, date(2026, 6, 3), date(2026, 6, 7), ressource=res_b)
        resp = self.api.get(
            CONFLITS_URL, {'debut': '2026-06-01', 'fin': '2026-06-30'})
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.data['nb_conflits'], 0)
