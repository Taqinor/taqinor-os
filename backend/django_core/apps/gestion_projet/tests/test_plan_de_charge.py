"""Tests PROJ18 -- Plan de charge (capacite vs affecte).

Couvre :
- Capacite = jours ouvres (L-V) x heures/jour, sur fenetre inclusive
- Affecte = somme proratee des affectations chevauchant la fenetre
- Drapeau surcharge (affecte > capacite)
- Chevauchement de periode (affectation partiellement hors fenetre -> prorata)
- Indisponibilite retranchee de la capacite
- Repartition de la charge d'equipe entre membres
- Garde division par zero (capacite nulle -> utilisation_pct None,
  mais surcharge=True si charge presente)
- Scoping societe (donnees d'une autre societe ignorees)
- Endpoint API : parametres obligatoires / invalides -> 400
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

PLAN_URL = '/api/django/gestion-projet/ressources/plan-de-charge/'


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


def make_affectation(company, tache, debut, fin, charge, ressource=None,
                     equipe=None):
    return AffectationRessource.objects.create(
        company=company, tache=tache,
        ressource=ressource, equipe=equipe,
        date_debut=debut, date_fin=fin,
        charge_jours=charge)


def ligne_for(resultat, ressource):
    for ligne in resultat['lignes']:
        if ligne['ressource'] == ressource.id:
            return ligne
    return None


# ---------------------------------------------------------------------------
# Selecteur : capacite
# ---------------------------------------------------------------------------

class CapaciteTests(TestCase):

    def setUp(self):
        self.co = make_company('proj18-cap', 'Societe A')
        self.res = make_ressource(self.co, 'Cap Res')

    def test_capacite_jours_ouvres_semaine_complete(self):
        # Lundi 2026-06-01 -> vendredi 2026-06-05 = 5 jours ouvres.
        result = selectors.plan_de_charge(
            self.co, date(2026, 6, 1), date(2026, 6, 5))
        ligne = ligne_for(result, self.res)
        self.assertEqual(ligne['jours_ouvres'], 5)
        self.assertEqual(ligne['capacite_heures'], 5 * 8)

    def test_capacite_exclut_weekend(self):
        # Inclut un week-end (sam 06 + dim 07) -> seuls 5 jours ouvres.
        result = selectors.plan_de_charge(
            self.co, date(2026, 6, 1), date(2026, 6, 7))
        ligne = ligne_for(result, self.res)
        self.assertEqual(ligne['jours_ouvres'], 5)

    def test_heures_par_jour_personnalise(self):
        result = selectors.plan_de_charge(
            self.co, date(2026, 6, 1), date(2026, 6, 5),
            heures_par_jour=7)
        ligne = ligne_for(result, self.res)
        self.assertEqual(ligne['capacite_heures'], 5 * 7)

    def test_fenetre_inversee_donne_capacite_nulle(self):
        result = selectors.plan_de_charge(
            self.co, date(2026, 6, 5), date(2026, 6, 1))
        ligne = ligne_for(result, self.res)
        self.assertEqual(ligne['jours_ouvres'], 0)
        self.assertEqual(ligne['capacite_heures'], 0)

    def test_ressource_inactive_exclue(self):
        make_ressource(self.co, 'Inactif', actif=False)
        result = selectors.plan_de_charge(
            self.co, date(2026, 6, 1), date(2026, 6, 5))
        noms = {ligne['nom'] for ligne in result['lignes']}
        self.assertNotIn('Inactif', noms)


# ---------------------------------------------------------------------------
# Selecteur : affecte + surcharge + prorata
# ---------------------------------------------------------------------------

class AffecteEtSurchargeTests(TestCase):

    def setUp(self):
        self.co = make_company('proj18-aff', 'Societe A')
        self.res = make_ressource(self.co, 'Aff Res')
        self.projet = make_projet(self.co, 'P18-AFF')
        self.tache = make_tache(self.co, self.projet, 'Pose')

    def test_affecte_dans_fenetre(self):
        # 3 j-h sur lun-mer dans la fenetre lun-ven.
        make_affectation(
            self.co, self.tache, date(2026, 6, 1), date(2026, 6, 3),
            Decimal('3'), ressource=self.res)
        result = selectors.plan_de_charge(
            self.co, date(2026, 6, 1), date(2026, 6, 5))
        ligne = ligne_for(result, self.res)
        self.assertEqual(ligne['affecte_heures'], 3 * 8)
        self.assertFalse(ligne['surcharge'])
        self.assertEqual(ligne['utilisation_pct'], round(24 / 40 * 100, 1))

    def test_surcharge_quand_affecte_depasse_capacite(self):
        # 6 j-h sur 5 jours ouvres de capacite -> surcharge.
        make_affectation(
            self.co, self.tache, date(2026, 6, 1), date(2026, 6, 5),
            Decimal('6'), ressource=self.res)
        result = selectors.plan_de_charge(
            self.co, date(2026, 6, 1), date(2026, 6, 5))
        ligne = ligne_for(result, self.res)
        self.assertEqual(ligne['affecte_heures'], 6 * 8)
        self.assertTrue(ligne['surcharge'])
        self.assertEqual(result['nb_surcharges'], 1)

    def test_prorata_affectation_partiellement_hors_fenetre(self):
        # Affectation lun-ven (5 j ouvres), charge 5 j-h. Fenetre = lun-mer
        # (3 j ouvres dans la fenetre) -> prorata 3/5 de 5 j-h = 3 j-h.
        make_affectation(
            self.co, self.tache, date(2026, 6, 1), date(2026, 6, 5),
            Decimal('5'), ressource=self.res)
        result = selectors.plan_de_charge(
            self.co, date(2026, 6, 1), date(2026, 6, 3))
        ligne = ligne_for(result, self.res)
        self.assertAlmostEqual(ligne['affecte_heures'], 3 * 8, places=2)

    def test_affectation_disjointe_ignoree(self):
        make_affectation(
            self.co, self.tache, date(2026, 7, 1), date(2026, 7, 3),
            Decimal('3'), ressource=self.res)
        result = selectors.plan_de_charge(
            self.co, date(2026, 6, 1), date(2026, 6, 5))
        ligne = ligne_for(result, self.res)
        self.assertEqual(ligne['affecte_heures'], 0)

    def test_affectation_sans_charge_ignoree(self):
        make_affectation(
            self.co, self.tache, date(2026, 6, 1), date(2026, 6, 3),
            None, ressource=self.res)
        result = selectors.plan_de_charge(
            self.co, date(2026, 6, 1), date(2026, 6, 5))
        ligne = ligne_for(result, self.res)
        self.assertEqual(ligne['affecte_heures'], 0)


# ---------------------------------------------------------------------------
# Selecteur : indisponibilites retranchees de la capacite
# ---------------------------------------------------------------------------

class IndisponibiliteTests(TestCase):

    def setUp(self):
        self.co = make_company('proj18-indispo', 'Societe A')
        self.res = make_ressource(self.co, 'Indispo Res')

    def test_indispo_retranche_jours_ouvres(self):
        # Conge lun-mar (2 j ouvres) sur une fenetre lun-ven (5 j) -> 3 j dispo.
        Indisponibilite.objects.create(
            company=self.co, ressource=self.res,
            type_indispo=Indisponibilite.TypeIndispo.CONGE,
            date_debut=date(2026, 6, 1), date_fin=date(2026, 6, 2))
        result = selectors.plan_de_charge(
            self.co, date(2026, 6, 1), date(2026, 6, 5))
        ligne = ligne_for(result, self.res)
        self.assertEqual(ligne['jours_indispo'], 2)
        self.assertEqual(ligne['capacite_heures'], 3 * 8)

    def test_indispo_weekend_seulement_ne_change_rien(self):
        Indisponibilite.objects.create(
            company=self.co, ressource=self.res,
            type_indispo=Indisponibilite.TypeIndispo.CONGE,
            date_debut=date(2026, 6, 6), date_fin=date(2026, 6, 7))
        result = selectors.plan_de_charge(
            self.co, date(2026, 6, 1), date(2026, 6, 7))
        ligne = ligne_for(result, self.res)
        self.assertEqual(ligne['jours_indispo'], 0)
        self.assertEqual(ligne['capacite_heures'], 5 * 8)


# ---------------------------------------------------------------------------
# Selecteur : equipe (charge repartie entre membres)
# ---------------------------------------------------------------------------

class EquipeChargeTests(TestCase):

    def setUp(self):
        self.co = make_company('proj18-eq', 'Societe A')
        self.r1 = make_ressource(self.co, 'Membre 1')
        self.r2 = make_ressource(self.co, 'Membre 2')
        self.equipe = Equipe.objects.create(company=self.co, nom='Equipe X')
        self.equipe.membres.add(self.r1, self.r2)
        self.projet = make_projet(self.co, 'P18-EQ')
        self.tache = make_tache(self.co, self.projet, 'Chantier')

    def test_charge_equipe_repartie_entre_membres(self):
        # Affectation equipe 4 j-h sur lun-jeu -> 2 j-h chacun.
        make_affectation(
            self.co, self.tache, date(2026, 6, 1), date(2026, 6, 4),
            Decimal('4'), equipe=self.equipe)
        result = selectors.plan_de_charge(
            self.co, date(2026, 6, 1), date(2026, 6, 5))
        l1 = ligne_for(result, self.r1)
        l2 = ligne_for(result, self.r2)
        self.assertAlmostEqual(l1['affecte_heures'], 2 * 8, places=2)
        self.assertAlmostEqual(l2['affecte_heures'], 2 * 8, places=2)


# ---------------------------------------------------------------------------
# Selecteur : garde division par zero (capacite nulle)
# ---------------------------------------------------------------------------

class ZeroCapaciteTests(TestCase):

    def setUp(self):
        self.co = make_company('proj18-zero', 'Societe A')
        self.res = make_ressource(self.co, 'Zero Res')
        self.projet = make_projet(self.co, 'P18-ZERO')
        self.tache = make_tache(self.co, self.projet, 'WE')

    def test_capacite_nulle_utilisation_none_sans_crash(self):
        # Fenetre = week-end seul (sam-dim) -> 0 jour ouvre, capacite 0.
        result = selectors.plan_de_charge(
            self.co, date(2026, 6, 6), date(2026, 6, 7))
        ligne = ligne_for(result, self.res)
        self.assertEqual(ligne['capacite_heures'], 0)
        self.assertIsNone(ligne['utilisation_pct'])
        self.assertFalse(ligne['surcharge'])

    def test_capacite_nulle_avec_charge_signale_surcharge(self):
        # Ressource en conge TOUTE la fenetre ouvree (capacite 0) mais avec une
        # affectation chargee dans la fenetre -> affecte > 0 > capacite : la
        # surcharge est signalee SANS division par zero (utilisation_pct None).
        Indisponibilite.objects.create(
            company=self.co, ressource=self.res,
            type_indispo=Indisponibilite.TypeIndispo.CONGE,
            date_debut=date(2026, 6, 1), date_fin=date(2026, 6, 5))
        make_affectation(
            self.co, self.tache, date(2026, 6, 1), date(2026, 6, 3),
            Decimal('2'), ressource=self.res)
        result = selectors.plan_de_charge(
            self.co, date(2026, 6, 1), date(2026, 6, 5))
        ligne = ligne_for(result, self.res)
        self.assertEqual(ligne['capacite_heures'], 0)
        self.assertIsNone(ligne['utilisation_pct'])
        self.assertGreater(ligne['affecte_heures'], 0)
        self.assertTrue(ligne['surcharge'])


# ---------------------------------------------------------------------------
# Selecteur : scoping societe
# ---------------------------------------------------------------------------

class ScopingTests(TestCase):

    def setUp(self):
        self.co_a = make_company('proj18-scope-a', 'Societe A')
        self.co_b = make_company('proj18-scope-b', 'Societe B')
        self.res_a = make_ressource(self.co_a, 'Res A')
        self.res_b = make_ressource(self.co_b, 'Res B')

    def test_seules_ressources_societe_demandee(self):
        result = selectors.plan_de_charge(
            self.co_a, date(2026, 6, 1), date(2026, 6, 5))
        noms = {ligne['nom'] for ligne in result['lignes']}
        self.assertIn('Res A', noms)
        self.assertNotIn('Res B', noms)

    def test_affectation_autre_societe_ignoree(self):
        projet_b = make_projet(self.co_b, 'P18-SB')
        tache_b = make_tache(self.co_b, projet_b, 'Tache B')
        make_affectation(
            self.co_b, tache_b, date(2026, 6, 1), date(2026, 6, 5),
            Decimal('5'), ressource=self.res_b)
        result = selectors.plan_de_charge(
            self.co_a, date(2026, 6, 1), date(2026, 6, 5))
        # Aucune ligne de la societe A ne porte de charge issue de B.
        for ligne in result['lignes']:
            self.assertEqual(ligne['affecte_heures'], 0)

    def test_filtre_ressource_unique(self):
        autre = make_ressource(self.co_a, 'Res A2')
        result = selectors.plan_de_charge(
            self.co_a, date(2026, 6, 1), date(2026, 6, 5),
            ressource_id=self.res_a.id)
        ids = {ligne['ressource'] for ligne in result['lignes']}
        self.assertEqual(ids, {self.res_a.id})
        self.assertNotIn(autre.id, ids)


# ---------------------------------------------------------------------------
# Endpoint API
# ---------------------------------------------------------------------------

class PlanDeChargeApiTests(TestCase):

    def setUp(self):
        self.co = make_company('proj18-api', 'Societe A')
        self.user = make_user(self.co, 'proj18-api-u')
        self.res = make_ressource(self.co, 'Api Res')
        self.api = auth(self.user)

    def test_endpoint_ok(self):
        resp = self.api.get(
            PLAN_URL, {'debut': '2026-06-01', 'fin': '2026-06-05'})
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.data['debut'], '2026-06-01')
        self.assertEqual(resp.data['fin'], '2026-06-05')
        self.assertTrue(any(
            ligne['ressource'] == self.res.id for ligne in resp.data['lignes']))

    def test_parametres_manquants_400(self):
        resp = self.api.get(PLAN_URL, {'debut': '2026-06-01'})
        self.assertEqual(resp.status_code, 400)

    def test_fin_avant_debut_400(self):
        resp = self.api.get(
            PLAN_URL, {'debut': '2026-06-05', 'fin': '2026-06-01'})
        self.assertEqual(resp.status_code, 400)

    def test_heures_par_jour_invalide_400(self):
        resp = self.api.get(PLAN_URL, {
            'debut': '2026-06-01', 'fin': '2026-06-05',
            'heures_par_jour': 'abc'})
        self.assertEqual(resp.status_code, 400)

    def test_date_invalide_400(self):
        resp = self.api.get(
            PLAN_URL, {'debut': 'pas-une-date', 'fin': '2026-06-05'})
        self.assertEqual(resp.status_code, 400)

    def test_isolation_societe_api(self):
        co_b = make_company('proj18-api-b', 'Societe B')
        make_ressource(co_b, 'Res B autre')
        resp = self.api.get(
            PLAN_URL, {'debut': '2026-06-01', 'fin': '2026-06-05'})
        noms = {ligne['nom'] for ligne in resp.data['lignes']}
        self.assertNotIn('Res B autre', noms)
