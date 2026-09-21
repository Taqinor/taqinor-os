"""Tests NTMIG27 — barème & scoring de certification partenaire.

Critère d'acceptation : un partenaire avec 5 déploiements et un NPS élevé
obtient un score PROPOSANT ``or`` — l'attribution restant une action admin
explicite (le calcul n'écrit jamais le niveau).
"""
from django.test import TestCase

from apps.crm.models import Partenaire
from apps.migration.certification import (
    calculer_score_certification, niveau_propose_pour)
from apps.migration.models import DeploiementPartenaire, ProjetMigration

from ._base import auth, make_admin, make_company, make_user

SCORE = '/api/django/migration/certification/{}/score/'


class Ntmig27CertificationTests(TestCase):

    def setUp(self):
        self.company = make_company('ntmig27', 'NTMIG27')
        self.admin = make_admin(self.company, 'ntmig27-admin')
        self.api = auth(self.admin)
        self.partenaire = Partenaire.objects.create(
            company=self.company, nom='Intégrateur Atlas',
            token_acces='ntmig27-token')

    def _deploiements(self, nb, note=None, statut='reussi'):
        for i in range(nb):
            DeploiementPartenaire.objects.create(
                company=self.company, partenaire=self.partenaire,
                client_final=f'Client {i}', statut=statut,
                note_satisfaction=note)

    def test_cinq_deploiements_et_nps_eleve_proposent_or(self):
        self._deploiements(5, note=9)
        resultat = calculer_score_certification(self.partenaire)
        self.assertEqual(resultat['detail']['deploiements']['nb_reussis'], 5)
        self.assertEqual(resultat['detail']['deploiements']['points'], 45)
        self.assertEqual(resultat['source_satisfaction'], 'deploiements')
        self.assertGreaterEqual(resultat['score'], 65)
        self.assertEqual(resultat['niveau_propose'], 'or')
        # PROPOSITION, jamais attribution : la fiche n'a pas bougé.
        self.assertEqual(resultat['attribution'], 'manuelle')
        self.assertTrue(resultat['proposition_differente'])
        self.assertEqual(
            Partenaire.objects.get(pk=self.partenaire.pk)
            .niveau_certification, 'aucun')

    def test_partenaire_neuf_reste_a_aucun(self):
        resultat = calculer_score_certification(self.partenaire)
        self.assertEqual(resultat['score'], 0)
        self.assertEqual(resultat['niveau_propose'], 'aucun')
        self.assertIsNone(resultat['source_satisfaction'])
        self.assertFalse(resultat['proposition_differente'])

    def test_deploiements_non_reussis_ne_comptent_pas(self):
        self._deploiements(5, note=9, statut='abandonne')
        resultat = calculer_score_certification(self.partenaire)
        self.assertEqual(resultat['detail']['deploiements']['nb_reussis'], 0)
        self.assertEqual(resultat['detail']['deploiements']['points'], 0)

    def test_specialites_comptent_dans_le_score(self):
        self.partenaire.specialites = ['crm', 'compta']
        self.partenaire.save(update_fields=['specialites'])
        resultat = calculer_score_certification(self.partenaire)
        self.assertEqual(resultat['detail']['specialites']['nb'], 2)
        self.assertEqual(resultat['detail']['specialites']['points'], 10)

    def test_composantes_plafonnees(self):
        """Vingt déploiements ne valent pas plus que le plafond de 45."""
        self._deploiements(20, note=10)
        self.partenaire.specialites = ['crm', 'ventes', 'compta', 'stock',
                                       'sav', 'rh', 'migration']
        self.partenaire.save(update_fields=['specialites'])
        resultat = calculer_score_certification(self.partenaire)
        self.assertEqual(resultat['detail']['deploiements']['points'], 45)
        self.assertEqual(resultat['detail']['specialites']['points'], 15)
        self.assertLessEqual(resultat['score'], 100)

    def test_projets_termines_comptes_sans_double_comptage(self):
        projet = ProjetMigration.objects.create(
            company=self.company, nom='Migration Alpha',
            statut=ProjetMigration.Statut.TERMINE)
        DeploiementPartenaire.objects.create(
            company=self.company, partenaire=self.partenaire,
            projet_migration=projet, statut='reussi')
        resultat = calculer_score_certification(self.partenaire)
        detail = resultat['detail']['deploiements']
        self.assertEqual(detail['nb_reussis'], 1)
        self.assertEqual(detail['nb_projets_termines'], 1)
        # Un seul travail : 1 × 9 points, jamais 2 × 9.
        self.assertEqual(detail['points'], 9)

    def test_seuils_de_proposition(self):
        self.assertEqual(niveau_propose_pour(0), 'aucun')
        self.assertEqual(niveau_propose_pour(20), 'enregistre')
        self.assertEqual(niveau_propose_pour(45), 'certifie')
        self.assertEqual(niveau_propose_pour(65), 'or')
        self.assertEqual(niveau_propose_pour(85), 'platine')

    def test_endpoint_score(self):
        self._deploiements(5, note=9)
        resp = self.api.get(SCORE.format(self.partenaire.pk))
        self.assertEqual(resp.status_code, 200, resp.data)
        self.assertEqual(resp.data['niveau_propose'], 'or')
        self.assertEqual(resp.data['partenaire_nom'], 'Intégrateur Atlas')

    def test_endpoint_partenaire_d_une_autre_societe_404(self):
        autre = make_company('ntmig27-bis', 'NTMIG27 bis')
        etranger = Partenaire.objects.create(
            company=autre, nom='Voisin', token_acces='ntmig27-token-2')
        resp = self.api.get(SCORE.format(etranger.pk))
        self.assertEqual(resp.status_code, 404)

    def test_endpoint_role_limite_refuse(self):
        limite = make_user(self.company, 'ntmig27-limite')
        resp = auth(limite).get(SCORE.format(self.partenaire.pk))
        self.assertEqual(resp.status_code, 403)

    def test_satisfaction_isolee_par_partenaire(self):
        """La note d'un AUTRE partenaire ne crédite jamais celui-ci."""
        autre = Partenaire.objects.create(
            company=self.company, nom='Intégrateur Rif',
            token_acces='ntmig27-token-3')
        DeploiementPartenaire.objects.create(
            company=self.company, partenaire=autre, statut='reussi',
            note_satisfaction=10)
        self._deploiements(1, note=None)
        resultat = calculer_score_certification(self.partenaire)
        self.assertNotEqual(resultat['source_satisfaction'], 'deploiements')
