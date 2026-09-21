"""NTEDU31/32/34 — portail parents (auth par token, échéancier, liste
d'attente). AUTH : la strict-scoping par famille est le critère central,
testée explicitement (une famille ne voit jamais les données d'une autre)."""
from datetime import date
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient

from authentication.models import Company

from .models import (
    AnneeScolaire, Classe, EcheancierScolarite, Eleve, Famille,
    GrilleTarifaire, Inscription, LigneEcheance, Niveau,
)
from .services import generer_ou_regenerer_compte_parent

User = get_user_model()


class PortailParentsTestCaseMixin:
    def setUp(self):
        super().setUp()
        self.company, _ = Company.objects.get_or_create(
            slug='ecole-portail-test', defaults={'nom': 'École Portail Test'})
        self.annee = AnneeScolaire.objects.create(
            company=self.company, libelle='2026-2027',
            date_debut=date(2026, 9, 1), date_fin=date(2027, 6, 30))
        self.niveau = Niveau.objects.create(
            company=self.company, nom='CP', cycle=Niveau.Cycle.PRIMAIRE, ordre=1)
        self.classe = Classe.objects.create(
            company=self.company, annee_scolaire=self.annee,
            niveau=self.niveau, nom='CP A', capacite_max=1)

        self.famille_a = Famille.objects.create(
            company=self.company, nom='Bennani')
        self.famille_b = Famille.objects.create(
            company=self.company, nom='Alaoui')

        self.eleve_a = Eleve.objects.create(
            company=self.company, famille=self.famille_a, nom='Bennani',
            prenom='Yasmine', classe=self.classe, statut=Eleve.Statut.INSCRIT)
        self.eleve_b = Eleve.objects.create(
            company=self.company, famille=self.famille_b, nom='Alaoui',
            prenom='Adam', statut=Eleve.Statut.INSCRIT)

        self.compte_a = generer_ou_regenerer_compte_parent(
            self.famille_a, 'parent-a@example.com')
        self.compte_b = generer_ou_regenerer_compte_parent(
            self.famille_b, 'parent-b@example.com')

        self.client = APIClient()


class NTEDU31ComptesParentTests(PortailParentsTestCaseMixin, TestCase):
    def test_generer_est_idempotent(self):
        compte2 = generer_ou_regenerer_compte_parent(
            self.famille_a, 'parent-a@example.com')
        self.assertEqual(self.compte_a.id, compte2.id)

    def test_token_unique_globalement(self):
        self.assertNotEqual(
            self.compte_a.token_acces, self.compte_b.token_acces)

    def test_liste_eleves_scopee_strictement_a_sa_famille(self):
        resp = self.client.get(
            f'/api/django/public/education/portail/'
            f'{self.compte_a.token_acces}/eleves/')
        self.assertEqual(resp.status_code, 200)
        ids = [row['id'] for row in resp.data['results']]
        self.assertEqual(ids, [self.eleve_a.id])
        self.assertNotIn(self.eleve_b.id, ids)

    def test_liste_eleves_autre_famille_ne_fuit_pas(self):
        resp_a = self.client.get(
            f'/api/django/public/education/portail/'
            f'{self.compte_a.token_acces}/eleves/')
        resp_b = self.client.get(
            f'/api/django/public/education/portail/'
            f'{self.compte_b.token_acces}/eleves/')
        ids_a = {row['id'] for row in resp_a.data['results']}
        ids_b = {row['id'] for row in resp_b.data['results']}
        self.assertEqual(ids_a, {self.eleve_a.id})
        self.assertEqual(ids_b, {self.eleve_b.id})
        self.assertTrue(ids_a.isdisjoint(ids_b))

    def test_token_invalide_renvoie_404_sans_fuite(self):
        resp = self.client.get(
            '/api/django/public/education/portail/token-inconnu/eleves/')
        self.assertEqual(resp.status_code, 404)

    def test_compte_inactif_renvoie_404(self):
        self.compte_a.actif = False
        self.compte_a.save(update_fields=['actif'])
        resp = self.client.get(
            f'/api/django/public/education/portail/'
            f'{self.compte_a.token_acces}/eleves/')
        self.assertEqual(resp.status_code, 404)

    def test_admin_endpoint_cree_compte_authenticated_only(self):
        resp = self.client.post(
            f'/api/django/education/familles/{self.famille_a.id}/'
            'compte-parent/', {'email': 'nouveau@example.com'})
        self.assertIn(resp.status_code, (401, 403))

    def test_admin_authentifie_peut_creer_compte_parent(self):
        user = User.objects.create_user(
            username='admin@ecole-portail-test.ma', password='x',
            company=self.company)
        self.client.force_authenticate(user)
        resp = self.client.post(
            f'/api/django/education/familles/{self.famille_a.id}/'
            'compte-parent/', {'email': 'nouveau-parent@example.com'})
        self.assertEqual(resp.status_code, 201)
        self.assertTrue(resp.data['token_acces'])
        self.assertEqual(resp.data['email'], 'nouveau-parent@example.com')


class NTEDU32EcheancierPortailTests(PortailParentsTestCaseMixin, TestCase):
    def setUp(self):
        super().setUp()
        self.grille = GrilleTarifaire.objects.create(
            company=self.company, annee_scolaire=self.annee,
            niveau=self.niveau, scolarite_annuelle=Decimal('10000'))
        self.echeancier = EcheancierScolarite.objects.create(
            company=self.company, eleve=self.eleve_a,
            annee_scolaire=self.annee, grille_tarifaire=self.grille,
            montant_total=Decimal('10000'), nombre_echeances=1)
        LigneEcheance.objects.create(
            company=self.company, echeancier=self.echeancier,
            libelle='Scolarité — Septembre', montant=Decimal('1000'),
            date_echeance=date(2026, 9, 5),
            statut=LigneEcheance.Statut.A_VENIR)

    def test_echeancier_visible_pour_sa_famille(self):
        resp = self.client.get(
            f'/api/django/public/education/portail/'
            f'{self.compte_a.token_acces}/echeancier/')
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.data['count'], 1)
        self.assertEqual(len(resp.data['results'][0]['lignes']), 1)

    def test_echeancier_vide_pour_famille_sans_echeancier(self):
        resp = self.client.get(
            f'/api/django/public/education/portail/'
            f'{self.compte_b.token_acces}/echeancier/')
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.data['count'], 0)

    def test_paiement_en_ligne_toujours_manuel_par_defaut(self):
        resp = self.client.get(
            f'/api/django/public/education/portail/'
            f'{self.compte_a.token_acces}/echeancier/')
        self.assertFalse(resp.data['paiement_en_ligne_disponible'])
        self.assertTrue(resp.data['moyens_paiement_manuel'])

    def test_jamais_de_champ_prix_achat_ou_marge_expose(self):
        resp = self.client.get(
            f'/api/django/public/education/portail/'
            f'{self.compte_a.token_acces}/echeancier/')
        payload_str = str(resp.data)
        self.assertNotIn('prix_achat', payload_str)
        self.assertNotIn('marge', payload_str)


class NTEDU34ListeAttentePortailTests(PortailParentsTestCaseMixin, TestCase):
    def test_position_liste_attente_correspond_au_back(self):
        # La classe (capacite_max=1) est déjà pleine avec eleve_a.
        eleve_c = Eleve.objects.create(
            company=self.company, famille=self.famille_a, nom='Bennani',
            prenom='Nadia')
        inscription = Inscription.objects.create(
            company=self.company, eleve=eleve_c, annee_scolaire=self.annee,
            classe_demandee=self.classe)
        from .services import affecter_classe
        affecter_classe(inscription, self.classe)
        inscription.refresh_from_db()
        self.assertEqual(
            inscription.statut, Inscription.Statut.LISTE_ATTENTE)

        resp = self.client.get(
            f'/api/django/public/education/portail/'
            f'{self.compte_a.token_acces}/liste-attente/')
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.data['count'], 1)
        self.assertEqual(
            resp.data['results'][0]['position'],
            inscription.position_liste_attente)

    def test_liste_attente_vide_pour_famille_sans_attente(self):
        resp = self.client.get(
            f'/api/django/public/education/portail/'
            f'{self.compte_b.token_acces}/liste-attente/')
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.data['count'], 0)
