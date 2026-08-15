"""Tests NTMIG28 — traçabilité « qui a déployé quoi ».

Critère d'acceptation : enregistrer un déploiement RÉUSSI pour un partenaire
incrémente son historique (le compteur miroir de sa fiche crm).

Couvre aussi : le compteur est RECOMPTÉ (un déploiement repassé en
``abandonne``, réattribué ou supprimé le fait baisser), l'écriture passe par
``crm.services`` et jamais par les modèles crm, et un partenaire d'une autre
société est introuvable — donc non créditable.
"""
from django.test import TestCase

from apps.crm.models import Partenaire
from apps.migration.models import DeploiementPartenaire, ProjetMigration

from ._base import auth, make_admin, make_company, make_user

DEPLOIEMENTS = '/api/django/migration/deploiements-partenaire/'


class Ntmig28DeploiementTests(TestCase):

    def setUp(self):
        self.company = make_company('ntmig28', 'NTMIG28')
        self.admin = make_admin(self.company, 'ntmig28-admin')
        self.api = auth(self.admin)
        self.partenaire = Partenaire.objects.create(
            company=self.company, nom='Intégrateur Atlas',
            token_acces='ntmig28-token')

    def _creer(self, **extra):
        payload = {
            'partenaire': self.partenaire.pk,
            'client_final': 'Coopérative Souss',
            'modules': ['crm', 'ventes'],
            'statut': 'reussi',
            'date_go_live': '2026-05-20',
        }
        payload.update(extra)
        return self.api.post(DEPLOIEMENTS, payload, format='json')

    def _compteur(self):
        return Partenaire.objects.get(
            pk=self.partenaire.pk).nb_deploiements_reussis

    def test_deploiement_reussi_incremente_l_historique(self):
        resp = self._creer()
        self.assertEqual(resp.status_code, 201, resp.data)
        self.assertEqual(resp.data['partenaire_nom'], 'Intégrateur Atlas')
        self.assertEqual(resp.data['modules'], ['crm', 'ventes'])
        self.assertEqual(self._compteur(), 1)

        self._creer(client_final='Ferme Doukkala')
        self.assertEqual(self._compteur(), 2)

    def test_deploiement_en_cours_ne_compte_pas(self):
        self._creer(statut='en_cours')
        self.assertEqual(self._compteur(), 0)

    def test_repasser_en_abandonne_fait_baisser_le_compteur(self):
        """Le compteur est RECOMPTÉ, jamais incrémenté aveuglément."""
        deploiement_id = self._creer().data['id']
        self.assertEqual(self._compteur(), 1)
        resp = self.api.patch(f'{DEPLOIEMENTS}{deploiement_id}/',
                              {'statut': 'abandonne'}, format='json')
        self.assertEqual(resp.status_code, 200, resp.data)
        self.assertEqual(self._compteur(), 0)

    def test_suppression_fait_baisser_le_compteur(self):
        deploiement_id = self._creer().data['id']
        self.assertEqual(self._compteur(), 1)
        resp = self.api.delete(f'{DEPLOIEMENTS}{deploiement_id}/')
        self.assertEqual(resp.status_code, 204)
        self.assertEqual(self._compteur(), 0)

    def test_reattribution_decompte_l_ancien_partenaire(self):
        autre = Partenaire.objects.create(
            company=self.company, nom='Intégrateur Rif',
            token_acces='ntmig28-token-2')
        deploiement_id = self._creer().data['id']
        self.assertEqual(self._compteur(), 1)
        resp = self.api.patch(f'{DEPLOIEMENTS}{deploiement_id}/',
                              {'partenaire': autre.pk}, format='json')
        self.assertEqual(resp.status_code, 200, resp.data)
        self.assertEqual(self._compteur(), 0)
        self.assertEqual(
            Partenaire.objects.get(pk=autre.pk).nb_deploiements_reussis, 1)

    def test_partenaire_d_une_autre_societe_refuse(self):
        autre_company = make_company('ntmig28-bis', 'NTMIG28 bis')
        etranger = Partenaire.objects.create(
            company=autre_company, nom='Voisin',
            token_acces='ntmig28-token-3')
        resp = self._creer(partenaire=etranger.pk)
        self.assertEqual(resp.status_code, 400)
        self.assertFalse(DeploiementPartenaire.objects.exists())

    def test_projet_d_une_autre_societe_refuse(self):
        autre_company = make_company('ntmig28-ter', 'NTMIG28 ter')
        projet = ProjetMigration.objects.create(
            company=autre_company, nom='Projet voisin')
        resp = self._creer(projet_migration=projet.pk)
        self.assertEqual(resp.status_code, 400)

    def test_note_satisfaction_bornee(self):
        resp = self._creer(note_satisfaction=42)
        self.assertEqual(resp.status_code, 400)
        resp = self._creer(note_satisfaction=9)
        self.assertEqual(resp.status_code, 201, resp.data)

    def test_modules_non_liste_refuses(self):
        resp = self._creer(modules='crm')
        self.assertEqual(resp.status_code, 400)

    def test_liste_scopee_societe_et_filtrable(self):
        self._creer()
        autre_company = make_company('ntmig28-quat', 'NTMIG28 quat')
        autre_admin = make_admin(autre_company, 'ntmig28-autre-admin')
        resp = auth(autre_admin).get(DEPLOIEMENTS)
        data = resp.data
        self.assertEqual(data['results'] if isinstance(data, dict) else data,
                         [])
        resp = self.api.get(DEPLOIEMENTS, {'statut': 'abandonne'})
        data = resp.data
        self.assertEqual(data['results'] if isinstance(data, dict) else data,
                         [])

    def test_role_limite_refuse(self):
        limite = make_user(self.company, 'ntmig28-limite')
        resp = auth(limite).get(DEPLOIEMENTS)
        self.assertEqual(resp.status_code, 403)
