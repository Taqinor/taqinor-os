"""NTPRO15 — État des lieux entrée/sortie — modèle + pièces.

Couvre : un état des lieux se crée avec une grille de pièces/éléments
pré-remplie depuis le type de local (habitation vs commerce vs un type
inconnu — repli sur une grille générique, jamais vide), isolation tenant,
et la mise à jour de l'état relevé sur une pièce/élément.
"""
from datetime import date
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from authentication.models import Company

from apps.immobilier.models import (
    Bail, Batiment, ElementEtatLieux, EtatLieuxImmo, Local, Locataire,
    Niveau, PieceEtatLieux, Site,
)
from apps.immobilier.services import creer_bail, creer_etat_lieux

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


class Ntpro15EtatLieuxTests(TestCase):
    def setUp(self):
        self.co_a = make_company('immo-el-a', 'Immo EL A')
        self.co_b = make_company('immo-el-b', 'Immo EL B')
        self.admin_a = make_user(self.co_a, 'immo-el-admin-a')
        site = Site.objects.create(company=self.co_a, nom='Résidence')
        batiment = Batiment.objects.create(
            company=self.co_a, site=site, nom='Bât A')
        niveau = Niveau.objects.create(
            company=self.co_a, batiment=batiment, numero='RDC')
        self.local_habitation = Local.objects.create(
            company=self.co_a, niveau=niveau, reference='RDC-01',
            type_local=Local.TypeLocal.HABITATION)
        self.local_parking = Local.objects.create(
            company=self.co_a, niveau=niveau, reference='RDC-02',
            type_local=Local.TypeLocal.PARKING)
        locataire = Locataire.objects.create(company=self.co_a, nom='Bennani')
        self.bail = creer_bail(
            company=self.co_a, local=self.local_habitation,
            locataire=locataire, type_bail=Bail.TypeBail.HABITATION,
            date_debut=date(2026, 1, 1), duree_mois=12,
            loyer_mensuel_ht=Decimal('3000.00'))
        self.bail_parking = creer_bail(
            company=self.co_a, local=self.local_parking, locataire=locataire,
            type_bail=Bail.TypeBail.HABITATION, date_debut=date(2026, 1, 1),
            duree_mois=12, loyer_mensuel_ht=Decimal('500.00'))

    def test_grille_prefill_habitation(self):
        etat_lieux = creer_etat_lieux(
            self.bail, EtatLieuxImmo.Moment.ENTREE, date=date(2026, 1, 1))
        pieces = list(etat_lieux.pieces.all())
        self.assertGreater(len(pieces), 0)
        noms_pieces = {p.nom_piece for p in pieces}
        self.assertIn('Cuisine', noms_pieces)
        cuisine = etat_lieux.pieces.get(nom_piece='Cuisine')
        elements = {e.element for e in cuisine.elements.all()}
        self.assertIn('plomberie', elements)
        self.assertIn('électricité', elements)

    def test_grille_prefill_type_different_parking(self):
        etat_lieux = creer_etat_lieux(
            self.bail_parking, EtatLieuxImmo.Moment.ENTREE,
            date=date(2026, 1, 1))
        pieces = list(etat_lieux.pieces.all())
        self.assertEqual(len(pieces), 1)
        self.assertEqual(pieces[0].nom_piece, 'Emplacement')

    def test_grille_repli_type_inconnu_jamais_vide(self):
        local_sans_type_connu = Local.objects.create(
            company=self.co_a, niveau=self.local_habitation.niveau,
            reference='RDC-99', type_local='inexistant')
        bail = creer_bail(
            company=self.co_a, local=local_sans_type_connu,
            locataire=self.bail.locataire, statut=Bail.Statut.BROUILLON,
            type_bail=Bail.TypeBail.HABITATION, date_debut=date(2026, 1, 1),
            duree_mois=12, loyer_mensuel_ht=Decimal('1000.00'))
        etat_lieux = creer_etat_lieux(
            bail, EtatLieuxImmo.Moment.ENTREE, date=date(2026, 1, 1))
        pieces = list(etat_lieux.pieces.all())
        self.assertGreater(len(pieces), 0)

    def test_statut_par_defaut_brouillon(self):
        etat_lieux = creer_etat_lieux(
            self.bail, EtatLieuxImmo.Moment.ENTREE, date=date(2026, 1, 1))
        self.assertEqual(etat_lieux.statut, EtatLieuxImmo.Statut.BROUILLON)

    def test_api_create_prefill_grille(self):
        api = auth(self.admin_a)
        resp = api.post('/api/django/immobilier/etats-lieux/', {
            'bail': self.bail.id, 'moment': 'entree', 'date': '2026-01-01',
        }, format='json')
        self.assertEqual(resp.status_code, 201, resp.data)
        self.assertGreater(len(resp.data['pieces']), 0)
        self.assertGreater(len(resp.data['pieces'][0]['elements']), 0)

    def test_isolation_tenant(self):
        etat_lieux = creer_etat_lieux(
            self.bail, EtatLieuxImmo.Moment.ENTREE, date=date(2026, 1, 1))
        self.admin_b = make_user(self.co_b, 'immo-el-admin-b')
        resp = auth(self.admin_b).get(
            f'/api/django/immobilier/etats-lieux/{etat_lieux.id}/')
        self.assertEqual(resp.status_code, 404)

    def test_maj_etat_piece_et_element(self):
        etat_lieux = creer_etat_lieux(
            self.bail, EtatLieuxImmo.Moment.ENTREE, date=date(2026, 1, 1))
        piece = etat_lieux.pieces.first()
        element = piece.elements.first()
        api = auth(self.admin_a)

        resp_piece = api.patch(
            f'/api/django/immobilier/pieces-etat-lieux/{piece.id}/',
            {'etat_general': 'degrade', 'commentaire': 'Fissure murale'},
            format='json')
        self.assertEqual(resp_piece.status_code, 200, resp_piece.data)
        piece.refresh_from_db()
        self.assertEqual(piece.etat_general, PieceEtatLieux.EtatGeneral.DEGRADE)

        resp_element = api.patch(
            f'/api/django/immobilier/elements-etat-lieux/{element.id}/',
            {'etat': 'degrade', 'commentaire': 'Prise cassée'}, format='json')
        self.assertEqual(resp_element.status_code, 200, resp_element.data)
        element.refresh_from_db()
        self.assertEqual(element.etat, ElementEtatLieux.Etat.DEGRADE)

    def test_bail_dune_autre_societe_refuse(self):
        site_b = Site.objects.create(company=self.co_b, nom='Résidence B')
        batiment_b = Batiment.objects.create(
            company=self.co_b, site=site_b, nom='Bât B')
        niveau_b = Niveau.objects.create(
            company=self.co_b, batiment=batiment_b, numero='RDC')
        local_b = Local.objects.create(
            company=self.co_b, niveau=niveau_b, reference='RDC-01')
        locataire_b = Locataire.objects.create(company=self.co_b, nom='X')
        bail_b = creer_bail(
            company=self.co_b, local=local_b, locataire=locataire_b,
            type_bail=Bail.TypeBail.HABITATION, date_debut=date(2026, 1, 1),
            duree_mois=12, loyer_mensuel_ht=Decimal('1000.00'))
        api = auth(self.admin_a)
        resp = api.post('/api/django/immobilier/etats-lieux/', {
            'bail': bail_b.id, 'moment': 'entree', 'date': '2026-01-01',
        }, format='json')
        self.assertEqual(resp.status_code, 400, resp.data)
