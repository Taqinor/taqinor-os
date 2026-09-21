"""Tests PROJ20 -- Nivellement de charge (levelling).

Couvre :
- Ressource sur-chargee + ressource sous-chargee -> proposition de deplacement
- Tout le monde equilibre -> aucune proposition
- Le selecteur NE MUTE RIEN (aucune affectation deplacee en base)
- Un deplacement propose ne cree JAMAIS un conflit PROJ19 (chevauchement)
- Destinataire sans assez de marge -> pas de proposition (non resolue)
- Garde fenetre vide (fin < debut) -> aucune proposition, sans crash
- Affectation d'equipe / actif materiel jamais proposee (seules les directes)
- Scoping societe (donnees d'une autre societe ignorees)
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
    Projet,
    RessourceProfil,
    Tache,
)

User = get_user_model()

NIV_URL = (
    '/api/django/gestion-projet/ressources/nivellement-charge/')


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


def prop_for(resultat, affectation):
    for prop in resultat['propositions']:
        if prop['affectation'] == affectation.id:
            return prop
    return None


# ---------------------------------------------------------------------------
# Selecteur : sur-charge -> proposition vers sous-charge
# ---------------------------------------------------------------------------

class NivellementBaseTests(TestCase):

    def setUp(self):
        self.co = make_company('proj20-base', 'Societe A')
        self.projet = make_projet(self.co, 'P20-BASE')
        # Une semaine de travail : 2026-06-01 (lundi) -> 2026-06-05 (vendredi)
        # = 5 jours ouvres x 8h = 40h de capacite par ressource.
        self.debut = date(2026, 6, 1)
        self.fin = date(2026, 6, 5)

    def test_surcharge_proposee_vers_souscharge(self):
        # r1 a deux affectations de 5 j-h chacune (80h) sur 40h de capacite ->
        # sur-chargee. r2 est vide -> sous-chargee (40h libres). On propose de
        # deplacer une affectation de r1 vers r2.
        r1 = make_ressource(self.co, 'Niv R1')
        r2 = make_ressource(self.co, 'Niv R2')
        t1 = make_tache(self.co, self.projet, 'Tache 1')
        t2 = make_tache(self.co, self.projet, 'Tache 2')
        # Deux affectations DISJOINTES sur r1 (pas de conflit interne a r1).
        a1 = make_affectation(
            self.co, t1, date(2026, 6, 1), date(2026, 6, 2),
            ressource=r1, charge=Decimal('5'))
        a2 = make_affectation(
            self.co, t2, date(2026, 6, 4), date(2026, 6, 5),
            ressource=r1, charge=Decimal('5'))
        result = selectors.nivellement_charge(self.co, self.debut, self.fin)
        self.assertEqual(result['totaux']['nb_surcharges'], 1)
        self.assertGreaterEqual(result['totaux']['nb_sous_charges'], 1)
        self.assertGreaterEqual(result['totaux']['nb_propositions'], 1)
        # La proposition deplace bien une affectation de r1 vers r2.
        prop = result['propositions'][0]
        self.assertEqual(prop['de_ressource'], r1.id)
        self.assertEqual(prop['vers_ressource'], r2.id)
        self.assertIn(prop['affectation'], {a1.id, a2.id})

    def test_equilibre_aucune_proposition(self):
        # r1 et r2 ont chacune une affectation de 5 j-h (40h) = capacite exacte
        # -> personne n'est sur-charge -> aucune proposition.
        r1 = make_ressource(self.co, 'Eq R1')
        r2 = make_ressource(self.co, 'Eq R2')
        t1 = make_tache(self.co, self.projet, 'Tache 1')
        t2 = make_tache(self.co, self.projet, 'Tache 2')
        make_affectation(
            self.co, t1, date(2026, 6, 1), date(2026, 6, 5),
            ressource=r1, charge=Decimal('5'))
        make_affectation(
            self.co, t2, date(2026, 6, 1), date(2026, 6, 5),
            ressource=r2, charge=Decimal('5'))
        result = selectors.nivellement_charge(self.co, self.debut, self.fin)
        self.assertEqual(result['totaux']['nb_surcharges'], 0)
        self.assertEqual(result['totaux']['nb_propositions'], 0)

    def test_proposition_ne_mute_rien(self):
        # Apres calcul, l'affectation reste rattachee a r1 en base (pure lecture).
        r1 = make_ressource(self.co, 'Mut R1')
        make_ressource(self.co, 'Mut R2')
        t1 = make_tache(self.co, self.projet, 'Tache 1')
        t2 = make_tache(self.co, self.projet, 'Tache 2')
        a1 = make_affectation(
            self.co, t1, date(2026, 6, 1), date(2026, 6, 2),
            ressource=r1, charge=Decimal('5'))
        a2 = make_affectation(
            self.co, t2, date(2026, 6, 4), date(2026, 6, 5),
            ressource=r1, charge=Decimal('5'))
        result = selectors.nivellement_charge(self.co, self.debut, self.fin)
        self.assertGreaterEqual(result['totaux']['nb_propositions'], 1)
        # Rien n'a bouge en base : les deux affectations restent sur r1.
        a1.refresh_from_db()
        a2.refresh_from_db()
        self.assertEqual(a1.ressource_id, r1.id)
        self.assertEqual(a2.ressource_id, r1.id)


# ---------------------------------------------------------------------------
# Selecteur : anti-conflit PROJ19
# ---------------------------------------------------------------------------

class AntiConflitTests(TestCase):

    def setUp(self):
        self.co = make_company('proj20-conf', 'Societe A')
        self.projet = make_projet(self.co, 'P20-CONF')
        self.debut = date(2026, 6, 1)
        self.fin = date(2026, 6, 5)

    def test_deplacement_evite_conflit_chevauchement(self):
        # r1 sur-chargee (2 affectations). r2 a deja une affectation qui chevauche
        # l'affectation de r1 candidate au deplacement -> ce destinataire est
        # ecarte (pas de nouveau conflit PROJ19). Avec un seul destinataire
        # possible et en conflit, le deplacement est NON RESOLU.
        r1 = make_ressource(self.co, 'Conf R1')
        r2 = make_ressource(self.co, 'Conf R2')
        t1 = make_tache(self.co, self.projet, 'Tache 1')
        t2 = make_tache(self.co, self.projet, 'Tache 2')
        t3 = make_tache(self.co, self.projet, 'Tache 3')
        # r1 : deux affectations disjointes -> 80h sur 40h (sur-charge).
        make_affectation(
            self.co, t1, date(2026, 6, 1), date(2026, 6, 2),
            ressource=r1, charge=Decimal('5'))
        make_affectation(
            self.co, t2, date(2026, 6, 4), date(2026, 6, 5),
            ressource=r1, charge=Decimal('5'))
        # r2 occupe deja TOUTE la semaine avec une charge legere (faible heures)
        # -> r2 reste sous-chargee MAIS toute fenetre de r1 chevauche la sienne.
        make_affectation(
            self.co, t3, date(2026, 6, 1), date(2026, 6, 5),
            ressource=r2, charge=Decimal('1'))
        result = selectors.nivellement_charge(self.co, self.debut, self.fin)
        # r2 est le seul destinataire possible, mais il chevauche -> aucune
        # proposition realisable, tout en excedent compte comme non resolu.
        self.assertEqual(result['totaux']['nb_propositions'], 0)
        self.assertGreaterEqual(result['totaux']['nb_non_resolues'], 1)
        # Verification croisee : appliquer une proposition recreerait un conflit,
        # donc il ne doit en exister aucune.
        self.assertEqual(result['propositions'], [])

    def test_destinataire_sans_marge_non_resolu(self):
        # r1 sur-chargee, r2 a une toute petite marge (< charge a deplacer) ->
        # le deplacement n'est pas propose (recreerait une surcharge).
        r1 = make_ressource(self.co, 'Marge R1')
        r2 = make_ressource(self.co, 'Marge R2')
        t1 = make_tache(self.co, self.projet, 'Tache 1')
        t2 = make_tache(self.co, self.projet, 'Tache 2')
        t3 = make_tache(self.co, self.projet, 'Tache 3')
        make_affectation(
            self.co, t1, date(2026, 6, 1), date(2026, 6, 2),
            ressource=r1, charge=Decimal('5'))
        make_affectation(
            self.co, t2, date(2026, 6, 4), date(2026, 6, 5),
            ressource=r1, charge=Decimal('5'))
        # r2 deja chargee a 4.5 j-h (36h) sur une fenetre DISJOINTE des
        # affectations de r1 -> marge = 4h < 16h-20h a deplacer.
        make_affectation(
            self.co, t3, date(2026, 6, 3), date(2026, 6, 3),
            ressource=r2, charge=Decimal('4.5'))
        result = selectors.nivellement_charge(self.co, self.debut, self.fin)
        # r2 n'a pas assez de marge -> aucune affectation deplacable.
        self.assertEqual(result['totaux']['nb_propositions'], 0)
        self.assertGreaterEqual(result['totaux']['nb_non_resolues'], 1)


# ---------------------------------------------------------------------------
# Selecteur : seules les affectations directes sont deplacables
# ---------------------------------------------------------------------------

class VecteurTests(TestCase):

    def setUp(self):
        self.co = make_company('proj20-vect', 'Societe A')
        self.projet = make_projet(self.co, 'P20-VECT')
        self.debut = date(2026, 6, 1)
        self.fin = date(2026, 6, 5)

    def test_affectation_equipe_jamais_proposee(self):
        # Une affectation d'equipe surcharge ses membres mais n'est pas
        # deplacable (on ne casse pas une equipe). Aucune proposition.
        membre = make_ressource(self.co, 'Eq Membre')
        equipe = Equipe.objects.create(company=self.co, nom='Equipe Z')
        equipe.membres.add(membre)
        make_ressource(self.co, 'Vide Dest')
        t1 = make_tache(self.co, self.projet, 'Tache 1')
        # Charge d'equipe massive -> le membre est sur-charge via l'equipe.
        make_affectation(
            self.co, t1, date(2026, 6, 1), date(2026, 6, 5),
            equipe=equipe, charge=Decimal('10'))
        result = selectors.nivellement_charge(self.co, self.debut, self.fin)
        # Le membre est sur-charge mais aucune affectation DIRECTE a deplacer.
        self.assertEqual(result['totaux']['nb_propositions'], 0)

    def test_actif_materiel_jamais_propose(self):
        # Une affectation d'actif materiel n'est jamais consideree (pas une
        # personne) : elle n'entre ni dans la surcharge, ni dans les propositions.
        r1 = make_ressource(self.co, 'Actif R1')
        make_ressource(self.co, 'Actif Dest')
        t1 = make_tache(self.co, self.projet, 'Tache 1')
        t2 = make_tache(self.co, self.projet, 'Tache 2')
        # r1 sur-chargee via deux affectations directes.
        make_affectation(
            self.co, t1, date(2026, 6, 1), date(2026, 6, 2),
            ressource=r1, charge=Decimal('5'))
        make_affectation(
            self.co, t2, date(2026, 6, 4), date(2026, 6, 5),
            ressource=r1, charge=Decimal('5'))
        # Une affectation d'actif materiel disjointe -> ignoree.
        make_affectation(
            self.co, t2, date(2026, 6, 3), date(2026, 6, 3),
            actif_type=AffectationRessource.TypeActif.ACTIF_FLOTTE,
            actif_id=99)
        result = selectors.nivellement_charge(self.co, self.debut, self.fin)
        # Les propositions ne concernent que des affectations DIRECTES de r1.
        for prop in result['propositions']:
            self.assertEqual(prop['de_ressource'], r1.id)


# ---------------------------------------------------------------------------
# Selecteur : garde fenetre vide
# ---------------------------------------------------------------------------

class FenetreVideTests(TestCase):

    def setUp(self):
        self.co = make_company('proj20-vide', 'Societe A')
        self.projet = make_projet(self.co, 'P20-VIDE')

    def test_fenetre_inversee_aucune_proposition_sans_crash(self):
        r1 = make_ressource(self.co, 'Vide R1')
        make_ressource(self.co, 'Vide R2')
        t1 = make_tache(self.co, self.projet, 'Tache 1')
        t2 = make_tache(self.co, self.projet, 'Tache 2')
        make_affectation(
            self.co, t1, date(2026, 6, 1), date(2026, 6, 2),
            ressource=r1, charge=Decimal('5'))
        make_affectation(
            self.co, t2, date(2026, 6, 4), date(2026, 6, 5),
            ressource=r1, charge=Decimal('5'))
        result = selectors.nivellement_charge(
            self.co, date(2026, 6, 30), date(2026, 6, 1))
        self.assertEqual(result['totaux']['nb_surcharges'], 0)
        self.assertEqual(result['totaux']['nb_propositions'], 0)
        self.assertEqual(result['propositions'], [])


# ---------------------------------------------------------------------------
# Selecteur : scoping societe
# ---------------------------------------------------------------------------

class ScopingTests(TestCase):

    def setUp(self):
        self.co_a = make_company('proj20-scope-a', 'Societe A')
        self.co_b = make_company('proj20-scope-b', 'Societe B')

    def test_donnees_autre_societe_ignorees(self):
        # Sur-charge dans la societe B, requete sur la societe A -> rien.
        r1b = make_ressource(self.co_b, 'Res B1')
        make_ressource(self.co_b, 'Res B2')
        projet_b = make_projet(self.co_b, 'P20-SB')
        t1b = make_tache(self.co_b, projet_b, 'Tache B1')
        t2b = make_tache(self.co_b, projet_b, 'Tache B2')
        make_affectation(
            self.co_b, t1b, date(2026, 6, 1), date(2026, 6, 2),
            ressource=r1b, charge=Decimal('5'))
        make_affectation(
            self.co_b, t2b, date(2026, 6, 4), date(2026, 6, 5),
            ressource=r1b, charge=Decimal('5'))
        result = selectors.nivellement_charge(
            self.co_a, date(2026, 6, 1), date(2026, 6, 5))
        self.assertEqual(result['totaux']['nb_surcharges'], 0)
        self.assertEqual(result['totaux']['nb_propositions'], 0)


# ---------------------------------------------------------------------------
# Endpoint API
# ---------------------------------------------------------------------------

class NivellementApiTests(TestCase):

    def setUp(self):
        self.co = make_company('proj20-api', 'Societe A')
        self.user = make_user(self.co, 'proj20-api-u')
        self.projet = make_projet(self.co, 'P20-API')
        self.api = auth(self.user)

    def test_endpoint_propose_deplacement(self):
        r1 = make_ressource(self.co, 'Api R1')
        make_ressource(self.co, 'Api R2')
        t1 = make_tache(self.co, self.projet, 'Tache 1')
        t2 = make_tache(self.co, self.projet, 'Tache 2')
        make_affectation(
            self.co, t1, date(2026, 6, 1), date(2026, 6, 2),
            ressource=r1, charge=Decimal('5'))
        make_affectation(
            self.co, t2, date(2026, 6, 4), date(2026, 6, 5),
            ressource=r1, charge=Decimal('5'))
        resp = self.api.get(
            NIV_URL, {'debut': '2026-06-01', 'fin': '2026-06-05'})
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.data['totaux']['nb_surcharges'], 1)
        self.assertGreaterEqual(resp.data['totaux']['nb_propositions'], 1)

    def test_parametres_manquants_400(self):
        resp = self.api.get(NIV_URL, {'debut': '2026-06-01'})
        self.assertEqual(resp.status_code, 400)

    def test_date_invalide_400(self):
        resp = self.api.get(
            NIV_URL, {'debut': 'pas-une-date', 'fin': '2026-06-05'})
        self.assertEqual(resp.status_code, 400)

    def test_fin_avant_debut_400(self):
        resp = self.api.get(
            NIV_URL, {'debut': '2026-06-30', 'fin': '2026-06-01'})
        self.assertEqual(resp.status_code, 400)

    def test_heures_par_jour_invalide_400(self):
        resp = self.api.get(
            NIV_URL,
            {'debut': '2026-06-01', 'fin': '2026-06-05',
             'heures_par_jour': 'abc'})
        self.assertEqual(resp.status_code, 400)

    def test_isolation_societe_api(self):
        # Sur-charge dans une autre societe -> invisible via l'API de la societe A.
        co_b = make_company('proj20-api-b', 'Societe B')
        r1b = make_ressource(co_b, 'Res B autre')
        make_ressource(co_b, 'Res B2 autre')
        projet_b = make_projet(co_b, 'P20-API-B')
        t1b = make_tache(co_b, projet_b, 'Tache B1')
        t2b = make_tache(co_b, projet_b, 'Tache B2')
        make_affectation(
            co_b, t1b, date(2026, 6, 1), date(2026, 6, 2),
            ressource=r1b, charge=Decimal('5'))
        make_affectation(
            co_b, t2b, date(2026, 6, 4), date(2026, 6, 5),
            ressource=r1b, charge=Decimal('5'))
        resp = self.api.get(
            NIV_URL, {'debut': '2026-06-01', 'fin': '2026-06-05'})
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.data['totaux']['nb_surcharges'], 0)
        self.assertEqual(resp.data['totaux']['nb_propositions'], 0)
