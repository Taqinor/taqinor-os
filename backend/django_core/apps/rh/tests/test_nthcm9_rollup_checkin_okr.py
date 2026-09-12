"""Tests NTHCM9 — rollup OKR d'entreprise + check-ins continus.

Couvre :
* un check-in met à jour ``valeur_actuelle`` ET historise la trajectoire ;
* un key result d'un AUTRE OKR est refusé (400) ;
* le rollup agrège les contributeurs DISTINCTS et distingue « aucun
  contributeur » (``None``) de « 0 % » ;
* le tableau de bord sépare mes OKR / mon équipe / l'entreprise, et un
  non-manager reçoit une liste d'équipe vide (pas une erreur) ;
* un employé ne peut pas check-in sur l'OKR d'un autre ;
* isolation société ;
* l'exemple de contrat committé a EXACTEMENT les clés servies (PACT10).
"""
import json
from datetime import date
from decimal import Decimal
from pathlib import Path

from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from authentication.models import Company
from apps.rh import selectors, services
from apps.rh.models import (
    CheckInOkr,
    DossierEmploye,
    KeyResultIndividuel,
    ObjectifEntreprise,
    OkrIndividuel,
)

User = get_user_model()

JOUR_FIGE = date(2027, 2, 10)

CONTRAT = (Path(__file__).resolve().parent.parent
           / 'contract_samples' / 'okr_tableau_de_bord.json')


def make_company(slug, nom):
    company, _ = Company.objects.get_or_create(slug=slug, defaults={'nom': nom})
    return company


def make_user(company, username, role='normal'):
    return User.objects.create_user(
        username=username, password='x', company=company, role_legacy=role)


def auth(user):
    api = APIClient()
    api.credentials(HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(user)}')
    return api


class RollupEtCheckInTests(TestCase):
    def setUp(self):
        self.co = make_company('nthcm9-a', 'A')
        self.u_chef = make_user(self.co, 'nthcm9-chef')
        self.u_membre = make_user(self.co, 'nthcm9-membre')
        self.chef = DossierEmploye.objects.create(
            company=self.co, matricule='O-001', nom='Alami', prenom='Sara',
            user=self.u_chef)
        self.membre = DossierEmploye.objects.create(
            company=self.co, matricule='O-002', nom='Cherkaoui',
            prenom='Imane', user=self.u_membre, manager=self.chef)

        self.objectif = ObjectifEntreprise.objects.create(
            company=self.co, titre='Doubler la capacité de pose',
            periode='T1-2027')
        self.objectif_orphelin = ObjectifEntreprise.objects.create(
            company=self.co, titre='Ouvrir une agence à Agadir',
            periode='T1-2027')

        self.okr_chef = OkrIndividuel.objects.create(
            company=self.co, employe=self.chef, periode='T1-2027',
            titre='Réduire le délai de pose',
            objectif_parent=self.objectif)
        self.kr = KeyResultIndividuel.objects.create(
            company=self.co, okr=self.okr_chef, libelle='Jours moyens',
            valeur_cible=Decimal('100'), valeur_actuelle=Decimal('0'))

        self.okr_membre = OkrIndividuel.objects.create(
            company=self.co, employe=self.membre, periode='T1-2027',
            titre='Zéro incident chantier',
            objectif_parent=self.objectif)
        self.kr_membre = KeyResultIndividuel.objects.create(
            company=self.co, okr=self.okr_membre, libelle='Incidents',
            valeur_cible=Decimal('100'), valeur_actuelle=Decimal('40'))

    # ── check-in ──────────────────────────────────────────────────────────
    def test_checkin_met_a_jour_et_historise(self):
        checkin = services.enregistrer_checkin_okr(
            self.okr_chef, auteur=self.u_chef,
            valeurs={self.kr.id: '60'}, commentaire='Bien avancé',
            aujourdhui=JOUR_FIGE)
        self.kr.refresh_from_db()
        self.assertEqual(self.kr.valeur_actuelle, Decimal('60'))
        self.assertEqual(self.kr.progression_pct, Decimal('60.00'))
        self.assertEqual(checkin.date, JOUR_FIGE)
        self.assertEqual(checkin.auteur_id, self.u_chef.id)
        self.assertEqual(
            checkin.valeurs_snapshot, {str(self.kr.id): '60'})

        # Un second check-in écrase la valeur ACTUELLE mais conserve la
        # trajectoire : c'est tout l'intérêt de l'historique.
        services.enregistrer_checkin_okr(
            self.okr_chef, auteur=self.u_chef,
            valeurs={self.kr.id: '80'}, aujourdhui=JOUR_FIGE)
        self.kr.refresh_from_db()
        self.assertEqual(self.kr.valeur_actuelle, Decimal('80'))
        historique = list(
            CheckInOkr.objects.filter(okr=self.okr_chef)
            .order_by('created_at')
            .values_list('valeurs_snapshot', flat=True))
        self.assertEqual(
            historique,
            [{str(self.kr.id): '60'}, {str(self.kr.id): '80'}])

    def test_key_result_dun_autre_okr_refuse(self):
        with self.assertRaises(services.CheckInOkrError):
            services.enregistrer_checkin_okr(
                self.okr_chef, auteur=self.u_chef,
                valeurs={self.kr_membre.id: '90'}, aujourdhui=JOUR_FIGE)

    def test_valeur_illisible_refusee(self):
        with self.assertRaises(services.CheckInOkrError):
            services.enregistrer_checkin_okr(
                self.okr_chef, auteur=self.u_chef,
                valeurs={self.kr.id: 'beaucoup'}, aujourdhui=JOUR_FIGE)

    def test_checkin_sans_valeur_reste_un_point_de_suivi(self):
        checkin = services.enregistrer_checkin_okr(
            self.okr_chef, auteur=self.u_chef,
            commentaire='Rien de neuf', aujourdhui=JOUR_FIGE)
        self.assertEqual(checkin.valeurs_snapshot, {})
        self.assertEqual(checkin.commentaire, 'Rien de neuf')

    # ── rollup ────────────────────────────────────────────────────────────
    def test_rollup_agrege_les_contributeurs_distincts(self):
        services.enregistrer_checkin_okr(
            self.okr_chef, auteur=self.u_chef,
            valeurs={self.kr.id: '80'}, aujourdhui=JOUR_FIGE)
        lignes = {ligne['objectif_id']: ligne
                  for ligne in selectors.rollup_okr_entreprise(
                      self.co, periode='T1-2027')}
        ligne = lignes[self.objectif.id]
        self.assertEqual(ligne['nombre_contributeurs'], 2)
        self.assertEqual(ligne['nombre_okr_rattaches'], 2)
        # (80 % + 40 %) / 2
        self.assertEqual(ligne['progression_okr_pct'], Decimal('60.00'))

    def test_objectif_sans_okr_nest_pas_a_zero(self):
        lignes = {ligne['objectif_id']: ligne
                  for ligne in selectors.rollup_okr_entreprise(self.co)}
        orphelin = lignes[self.objectif_orphelin.id]
        self.assertIsNone(orphelin['progression_okr_pct'])
        self.assertEqual(orphelin['nombre_contributeurs'], 0)

    def test_deux_okr_du_meme_employe_font_un_contributeur(self):
        OkrIndividuel.objects.create(
            company=self.co, employe=self.chef, periode='T1-2027',
            titre='Second objectif', objectif_parent=self.objectif_orphelin)
        OkrIndividuel.objects.create(
            company=self.co, employe=self.chef, periode='T1-2027',
            titre='Troisième objectif',
            objectif_parent=self.objectif_orphelin)
        lignes = {ligne['objectif_id']: ligne
                  for ligne in selectors.rollup_okr_entreprise(self.co)}
        ligne = lignes[self.objectif_orphelin.id]
        self.assertEqual(ligne['nombre_contributeurs'], 1)
        self.assertEqual(ligne['nombre_okr_rattaches'], 2)

    def test_isolation_societe(self):
        autre = make_company('nthcm9-b', 'B')
        self.assertEqual(selectors.rollup_okr_entreprise(autre), [])

    # ── tableau de bord ───────────────────────────────────────────────────
    def test_tableau_separe_les_trois_portees(self):
        tableau = selectors.tableau_okr_employe(
            self.co, self.chef, periode='T1-2027')
        self.assertEqual(
            [okr['id'] for okr in tableau['mes_okr']], [self.okr_chef.id])
        self.assertEqual(
            [okr['id'] for okr in tableau['equipe']], [self.okr_membre.id])
        self.assertTrue(tableau['est_manager'])
        self.assertEqual(len(tableau['entreprise']), 2)

    def test_non_manager_recoit_une_equipe_vide(self):
        tableau = selectors.tableau_okr_employe(self.co, self.membre)
        self.assertEqual(tableau['equipe'], [])
        self.assertFalse(tableau['est_manager'])

    def test_compte_sans_dossier_garde_le_rollup(self):
        tableau = selectors.tableau_okr_employe(self.co, None)
        self.assertEqual(tableau['mes_okr'], [])
        self.assertEqual(tableau['equipe'], [])
        self.assertEqual(len(tableau['entreprise']), 2)

    # ── API ───────────────────────────────────────────────────────────────
    def test_endpoint_tableau_de_bord(self):
        reponse = auth(self.u_chef).get(
            '/api/django/rh/okr-individuels/tableau-de-bord/')
        self.assertEqual(reponse.status_code, 200, reponse.content)
        self.assertTrue(reponse.data['est_manager'])
        self.assertEqual(len(reponse.data['mes_okr']), 1)

    def test_endpoint_rollup_objectif(self):
        reponse = auth(
            make_user(self.co, 'nthcm9-rh', role='responsable')).get(
                f'/api/django/rh/objectifs-entreprise/{self.objectif.id}'
                '/rollup/')
        self.assertEqual(reponse.status_code, 200, reponse.content)
        self.assertEqual(reponse.data['nombre_contributeurs'], 2)

    def test_endpoint_checkin_sur_mon_okr(self):
        reponse = auth(self.u_chef).post(
            f'/api/django/rh/okr-individuels/{self.okr_chef.id}/check-in/',
            {'valeurs': {str(self.kr.id): '55'}, 'commentaire': 'RAS'},
            format='json')
        self.assertEqual(reponse.status_code, 201, reponse.content)
        self.kr.refresh_from_db()
        self.assertEqual(self.kr.valeur_actuelle, Decimal('55'))

    def test_endpoint_checkin_sur_lokr_dun_autre_refuse(self):
        reponse = auth(self.u_membre).post(
            f'/api/django/rh/okr-individuels/{self.okr_chef.id}/check-in/',
            {'valeurs': {}}, format='json')
        self.assertEqual(reponse.status_code, 403, reponse.content)

    def test_contrat_committe_a_les_memes_cles(self):
        """PACT10 — l'exemple JSON doit refléter la forme RÉELLE servie."""
        contrat = json.loads(CONTRAT.read_text(encoding='utf-8'))
        servi = selectors.tableau_okr_employe(
            self.co, self.chef, periode='T1-2027')
        self.assertEqual(sorted(contrat['exemple']), sorted(servi))
        self.assertEqual(
            sorted(contrat['exemple']['mes_okr'][0]),
            sorted(servi['mes_okr'][0]))
        self.assertEqual(
            sorted(contrat['exemple']['equipe'][0]),
            sorted(servi['equipe'][0]))
        self.assertEqual(
            sorted(contrat['exemple']['entreprise'][0]),
            sorted(servi['entreprise'][0]))
        self.assertEqual(sorted(contrat['exemple_vide']), sorted(servi))
