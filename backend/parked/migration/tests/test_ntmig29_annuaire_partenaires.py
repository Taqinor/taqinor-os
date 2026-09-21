"""Tests NTMIG29 — annuaire interne des partenaires certifiés.

Critère d'acceptation : filtrer par spécialité « compta » et niveau ≥
``certifie`` renvoie les partenaires qualifiés.

Couvre aussi : le score PROPOSÉ (NTMIG27) et l'historique des déploiements
(NTMIG28) sont bien portés par chaque ligne, l'isolation multi-société,
et la garde de rôle (palier limité refusé).

Run :
    python manage.py test apps.migration.tests.test_ntmig29_annuaire_partenaires -v2
"""
from django.test import TestCase

from apps.crm.models import Partenaire
from apps.migration.models import DeploiementPartenaire

from ._base import auth, make_admin, make_company, make_user

ANNUAIRE = '/api/django/migration/annuaire-partenaires-certifies/'


class Ntmig29AnnuairePartenairesTests(TestCase):

    def setUp(self):
        self.company = make_company('ntmig29', 'NTMIG29')
        self.admin = make_admin(self.company, 'ntmig29-admin')
        self.api = auth(self.admin)

        self.qualifie = Partenaire.objects.create(
            company=self.company, nom='Intégrateur Atlas',
            token_acces='ntmig29-token-1',
            niveau_certification=Partenaire.NiveauCertification.CERTIFIE,
            specialites=['compta', 'crm'], zone='Casablanca')
        self.non_qualifie_niveau = Partenaire.objects.create(
            company=self.company, nom='Intégrateur Sud',
            token_acces='ntmig29-token-2',
            niveau_certification=Partenaire.NiveauCertification.ENREGISTRE,
            specialites=['compta'], zone='Agadir')
        self.non_qualifie_specialite = Partenaire.objects.create(
            company=self.company, nom='Intégrateur Nord',
            token_acces='ntmig29-token-3',
            niveau_certification=Partenaire.NiveauCertification.PLATINE,
            specialites=['rh'], zone='Tanger')

        DeploiementPartenaire.objects.create(
            company=self.company, partenaire=self.qualifie,
            client_final='Coopérative Souss',
            statut=DeploiementPartenaire.Statut.REUSSI,
            date_go_live='2026-04-10', note_satisfaction=9)

    def test_filtre_specialite_et_niveau_min_renvoie_les_qualifies(self):
        resp = self.api.get(
            ANNUAIRE, {'specialite': 'compta', 'niveau_min': 'certifie'})
        self.assertEqual(resp.status_code, 200, resp.data)
        noms = [r['nom'] for r in resp.data]
        self.assertEqual(noms, ['Intégrateur Atlas'])

    def test_ligne_porte_score_et_historique(self):
        resp = self.api.get(ANNUAIRE, {'specialite': 'compta'})
        self.assertEqual(resp.status_code, 200, resp.data)
        ligne = next(r for r in resp.data if r['id'] == self.qualifie.pk)
        self.assertIn('score', ligne)
        self.assertEqual(len(ligne['historique_deploiements']), 1)
        self.assertEqual(
            ligne['historique_deploiements'][0]['client_final'],
            'Coopérative Souss')
        self.assertEqual(ligne['niveau_certification_display'], 'Certifié')

    def test_sans_filtre_liste_tous_les_partenaires_de_la_societe(self):
        resp = self.api.get(ANNUAIRE)
        self.assertEqual(resp.status_code, 200, resp.data)
        self.assertEqual(len(resp.data), 3)

    def test_isolation_multi_societe(self):
        autre = make_company('ntmig29-bis', 'NTMIG29 bis')
        Partenaire.objects.create(
            company=autre, nom='Intégrateur voisin',
            token_acces='ntmig29-token-4',
            niveau_certification=Partenaire.NiveauCertification.PLATINE,
            specialites=['compta'])
        resp = self.api.get(ANNUAIRE, {'specialite': 'compta'})
        noms = [r['nom'] for r in resp.data]
        self.assertNotIn('Intégrateur voisin', noms)

    def test_role_limite_refuse(self):
        limite = make_user(self.company, 'ntmig29-limite')
        resp = auth(limite).get(ANNUAIRE)
        self.assertEqual(resp.status_code, 403)

    def test_ecriture_jamais_exposee(self):
        """Annuaire lecture seule : aucune méthode d'écriture disponible."""
        resp = self.api.post(ANNUAIRE, {'nom': 'x'}, format='json')
        self.assertEqual(resp.status_code, 405)
