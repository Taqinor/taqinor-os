"""XQHS21 — Relevés de consommation par site → génération bilan carbone.

Couvre :
  * les relevés mensuels se saisissent (scopés société) ;
  * la génération pré-remplit le bilan carbone sans doublon (idempotence) ;
  * les lignes restent éditables après génération ;
  * l'agrégation inclut le carburant flotte via le sélecteur cross-app ;
  * le scoping société.
"""
from datetime import date

from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from authentication.models import Company

from apps.flotte.models import PleinCarburant, Vehicule
from apps.qhse.models import BilanCarbone, LigneBilanCarbone, ReleveConsommation
from apps.qhse.services import generer_lignes_bilan

User = get_user_model()


def make_company(slug, nom):
    company, _ = Company.objects.get_or_create(slug=slug, defaults={'nom': nom})
    return company


def make_user(company, username, role='admin'):
    return User.objects.create_user(
        username=username, password='x', company=company, role_legacy=role)


def auth(user):
    api = APIClient()
    api.credentials(HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(user)}')
    return api


def make_bilan(company, annee=2026):
    return BilanCarbone.objects.create(
        company=company, libelle=f'Bilan {annee}', annee=annee)


class ReleveConsommationApiTests(TestCase):
    def setUp(self):
        self.company = make_company('xqhs21-api', 'Xqhs21 Api')
        self.user = make_user(self.company, 'xqhs21-user')

    def test_creation_pose_company_serveur(self):
        resp = auth(self.user).post(
            '/api/django/qhse/releves-consommation/',
            {'site_libelle': 'Siège Casa', 'type_energie': 'electricite',
             'periode': '2026-01-01', 'quantite': '1200.5'}, format='json')
        self.assertEqual(resp.status_code, 201)
        releve = ReleveConsommation.objects.get(id=resp.data['id'])
        self.assertEqual(releve.company_id, self.company.pk)

    def test_isolation_societe(self):
        other_co = make_company('xqhs21-api-other', 'Xqhs21 Api Other')
        other_user = make_user(other_co, 'xqhs21-other-user')
        ReleveConsommation.objects.create(
            company=self.company, site_libelle='Site A',
            type_energie='electricite', periode=date(2026, 1, 1),
            quantite=100)
        resp = auth(other_user).get('/api/django/qhse/releves-consommation/')
        ids = [item['id'] for item in resp.data.get('results', resp.data)]
        self.assertEqual(len(ids), 0)


class GenererLignesBilanTests(TestCase):
    def setUp(self):
        self.company = make_company('xqhs21-gen', 'Xqhs21 Gen')
        self.bilan = make_bilan(self.company)

    def test_agrege_releves_en_lignes(self):
        ReleveConsommation.objects.create(
            company=self.company, site_libelle='Siège',
            type_energie=ReleveConsommation.TypeEnergie.ELECTRICITE,
            periode=date(2026, 1, 1), quantite=1000)
        ReleveConsommation.objects.create(
            company=self.company, site_libelle='Siège',
            type_energie=ReleveConsommation.TypeEnergie.ELECTRICITE,
            periode=date(2026, 2, 1), quantite=1200)
        lignes = generer_lignes_bilan(self.bilan, 2026)
        elec = next(
            ligne for ligne in lignes
            if ligne.categorie == ReleveConsommation.TypeEnergie.ELECTRICITE)
        self.assertEqual(elec.quantite, 2200)
        self.assertEqual(elec.scope, LigneBilanCarbone.Scope.SCOPE_2)

    def test_idempotent_ne_duplique_pas(self):
        ReleveConsommation.objects.create(
            company=self.company, site_libelle='Siège',
            type_energie=ReleveConsommation.TypeEnergie.EAU,
            periode=date(2026, 3, 1), quantite=50)
        generer_lignes_bilan(self.bilan, 2026)
        generer_lignes_bilan(self.bilan, 2026)
        eau_lignes = LigneBilanCarbone.objects.filter(
            bilan=self.bilan, categorie=ReleveConsommation.TypeEnergie.EAU)
        self.assertEqual(eau_lignes.count(), 1)

    def test_regeneration_recalcule_quantite(self):
        ReleveConsommation.objects.create(
            company=self.company, site_libelle='Siège',
            type_energie=ReleveConsommation.TypeEnergie.EAU,
            periode=date(2026, 3, 1), quantite=50)
        generer_lignes_bilan(self.bilan, 2026)
        ReleveConsommation.objects.create(
            company=self.company, site_libelle='Siège',
            type_energie=ReleveConsommation.TypeEnergie.EAU,
            periode=date(2026, 4, 1), quantite=30)
        lignes = generer_lignes_bilan(self.bilan, 2026)
        eau = next(
            ligne for ligne in lignes
            if ligne.categorie == ReleveConsommation.TypeEnergie.EAU)
        self.assertEqual(eau.quantite, 80)

    def test_lignes_restent_editables_apres_generation(self):
        ReleveConsommation.objects.create(
            company=self.company, site_libelle='Siège',
            type_energie=ReleveConsommation.TypeEnergie.EAU,
            periode=date(2026, 3, 1), quantite=50)
        lignes = generer_lignes_bilan(self.bilan, 2026)
        ligne = lignes[0]
        ligne.quantite = 999
        ligne.save()
        ligne.refresh_from_db()
        self.assertEqual(ligne.quantite, 999)

    def test_scope_societe(self):
        other_co = make_company('xqhs21-gen-other', 'Xqhs21 Gen Other')
        ReleveConsommation.objects.create(
            company=other_co, site_libelle='Autre',
            type_energie=ReleveConsommation.TypeEnergie.EAU,
            periode=date(2026, 1, 1), quantite=999)
        lignes = generer_lignes_bilan(self.bilan, 2026)
        self.assertEqual(len(lignes), 0)

    def test_sans_releve_ni_flotte_aucune_ligne(self):
        lignes = generer_lignes_bilan(self.bilan, 2026)
        self.assertEqual(len(lignes), 0)


class GenererLignesBilanFlotteTests(TestCase):
    """L'agrégation inclut le carburant véhicules via flotte.selectors."""

    def setUp(self):
        self.company = make_company('xqhs21-flotte', 'Xqhs21 Flotte')
        self.bilan = make_bilan(self.company)

    def test_carburant_vehicule_diesel_compte_en_gasoil(self):
        vehicule = Vehicule.objects.create(
            company=self.company, immatriculation='1234-A-1',
            energie=Vehicule.Energie.DIESEL)
        PleinCarburant.objects.create(
            company=self.company, vehicule=vehicule,
            date_plein=date(2026, 5, 1), kilometrage=1000, quantite=45,
            unite=PleinCarburant.Unite.LITRE)
        lignes = generer_lignes_bilan(self.bilan, 2026)
        gasoil = next(
            (ligne for ligne in lignes
             if ligne.categorie == ReleveConsommation.TypeEnergie.GASOIL),
            None)
        self.assertIsNotNone(gasoil)
        self.assertEqual(gasoil.quantite, 45)

    def test_carburant_vehicule_essence_compte_en_essence(self):
        vehicule = Vehicule.objects.create(
            company=self.company, immatriculation='5678-B-1',
            energie=Vehicule.Energie.ESSENCE)
        PleinCarburant.objects.create(
            company=self.company, vehicule=vehicule,
            date_plein=date(2026, 6, 1), kilometrage=2000, quantite=30,
            unite=PleinCarburant.Unite.LITRE)
        lignes = generer_lignes_bilan(self.bilan, 2026)
        essence = next(
            (ligne for ligne in lignes
             if ligne.categorie == ReleveConsommation.TypeEnergie.ESSENCE),
            None)
        self.assertIsNotNone(essence)
        self.assertEqual(essence.quantite, 30)

    def test_flotte_et_releve_site_se_cumulent(self):
        vehicule = Vehicule.objects.create(
            company=self.company, immatriculation='9999-C-1',
            energie=Vehicule.Energie.DIESEL)
        PleinCarburant.objects.create(
            company=self.company, vehicule=vehicule,
            date_plein=date(2026, 7, 1), kilometrage=3000, quantite=40,
            unite=PleinCarburant.Unite.LITRE)
        ReleveConsommation.objects.create(
            company=self.company, site_libelle='Groupe électrogène',
            type_energie=ReleveConsommation.TypeEnergie.GASOIL,
            periode=date(2026, 7, 1), quantite=60)
        lignes = generer_lignes_bilan(self.bilan, 2026)
        gasoil = next(
            ligne for ligne in lignes
            if ligne.categorie == ReleveConsommation.TypeEnergie.GASOIL)
        self.assertEqual(gasoil.quantite, 100)


class GenererLignesBilanApiTests(TestCase):
    def setUp(self):
        self.company = make_company('xqhs21-genapi', 'Xqhs21 Genapi')
        self.user = make_user(self.company, 'xqhs21-genapi-user')
        self.bilan = make_bilan(self.company)

    def test_action_generer_lignes_bilan(self):
        ReleveConsommation.objects.create(
            company=self.company, site_libelle='Siège',
            type_energie=ReleveConsommation.TypeEnergie.ELECTRICITE,
            periode=date(2026, 1, 1), quantite=500)
        resp = auth(self.user).post(
            f'/api/django/qhse/bilans-carbone/{self.bilan.pk}/generer-lignes-bilan/')
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(len(resp.data), 1)
