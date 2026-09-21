"""NTESG18 — prérequis de clôture d'une période ESG.

Ce que le test PROUVE — et c'est LE contrat de l'assistant :

  * une incohérence RÉELLE (période déjà figée, dates absentes, fin avant
    début) atterrit dans ``bloquants`` et met ``peut_figer`` à False ;
  * un simple MANQUE de donnée (couverture < 50 %, aucune période antérieure,
    catalogue non seedé) atterrit dans ``avertissements`` et NE BLOQUE PAS —
    une société qui démarre son reporting a le droit de figer une période peu
    couverte ;
  * ``comparaison`` vaut ``None`` sans période antérieure : jamais un diff
    inventé contre un zéro imaginaire ;
  * l'API ``figer/`` reste directement appelable (c'est l'écran qui impose les
    4 étapes, pas le serveur).
"""
from datetime import date

from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework import status
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from apps.esg import selectors
from apps.esg.models import (
    CatalogueIndicateurESG, PeriodeReportingESG, SnapshotESG,
)
from authentication.models import Company

User = get_user_model()


def _api(user):
    api = APIClient()
    api.credentials(HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(user)}')
    return api


def _url(periode_id):
    return f'/api/django/esg/periodes-esg/{periode_id}/prerequis-cloture/'


class PrerequisClotureEsgTests(TestCase):
    def setUp(self):
        self.co = Company.objects.create(nom='ESG Co', slug='esg-ntesg18')
        self.user = User.objects.create_user(
            username='ntesg18-user', password='x', company=self.co,
            role_legacy='responsable')

    def _periode(self, libelle='2026', debut=date(2026, 1, 1),
                 fin=date(2026, 12, 31), statut=None):
        periode = PeriodeReportingESG.objects.create(
            company=self.co, libelle=libelle, date_debut=debut, date_fin=fin)
        if statut:
            PeriodeReportingESG.objects.filter(pk=periode.pk).update(
                statut=statut)
            periode.refresh_from_db()
        return periode

    # ── bloquants RÉELS ────────────────────────────────────────────────────
    def test_periode_deja_figee_bloque(self):
        periode = self._periode(statut=PeriodeReportingESG.Statut.FIGEE)
        resultat = selectors.prerequis_cloture_esg(periode)
        self.assertFalse(resultat['peut_figer'])
        self.assertEqual(len(resultat['bloquants']), 1)
        self.assertIn('déjà', resultat['bloquants'][0])

    def test_dates_inversees_bloquent(self):
        periode = self._periode(debut=date(2026, 12, 31), fin=date(2026, 1, 1))
        resultat = selectors.prerequis_cloture_esg(periode)
        self.assertFalse(resultat['peut_figer'])
        self.assertTrue(
            any('invalides' in m for m in resultat['bloquants']),
            resultat['bloquants'])

    def test_periode_valide_peut_figer(self):
        periode = self._periode()
        resultat = selectors.prerequis_cloture_esg(periode)
        self.assertTrue(resultat['peut_figer'])
        self.assertEqual(resultat['bloquants'], [])

    # ── AVERTISSEMENTS : ils n'empêchent JAMAIS ────────────────────────────
    def test_couverture_faible_avertit_sans_bloquer(self):
        for index in range(4):
            CatalogueIndicateurESG.objects.create(
                company=self.co, code=f'ENV-{index}', libelle=f'Ind {index}',
                pilier=CatalogueIndicateurESG.Pilier.ENVIRONNEMENT)
        periode = self._periode()
        resultat = selectors.prerequis_cloture_esg(periode)
        # 0 indicateur qhse renseigné ⇒ couverture 0 % ⇒ avertissement.
        self.assertTrue(
            any('environnement' in m for m in resultat['avertissements']),
            resultat['avertissements'])
        # …mais le figeage reste POSSIBLE.
        self.assertTrue(resultat['peut_figer'])
        self.assertEqual(resultat['bloquants'], [])

    def test_catalogue_absent_avertit_sans_bloquer(self):
        periode = self._periode()
        resultat = selectors.prerequis_cloture_esg(periode)
        self.assertTrue(
            any('catalogue' in m.lower()
                for m in resultat['avertissements']),
            resultat['avertissements'])
        self.assertTrue(resultat['peut_figer'])

    def test_sans_periode_anterieure_comparaison_none(self):
        periode = self._periode()
        resultat = selectors.prerequis_cloture_esg(periode)
        self.assertIsNone(resultat['comparaison'])
        self.assertTrue(
            any('antérieure' in m for m in resultat['avertissements']),
            resultat['avertissements'])
        self.assertTrue(resultat['peut_figer'])

    def test_comparaison_avec_la_periode_precedente(self):
        precedente = self._periode(
            libelle='2025', debut=date(2025, 1, 1), fin=date(2025, 12, 31))
        courante = self._periode()
        resultat = selectors.prerequis_cloture_esg(courante)
        self.assertIsNotNone(resultat['comparaison'])
        self.assertEqual(
            resultat['comparaison']['periode_reference']['id'], precedente.pk)
        self.assertEqual(
            resultat['comparaison']['periode_n']['id'], courante.pk)
        self.assertFalse(
            any('antérieure' in m for m in resultat['avertissements']))

    def test_la_periode_suivante_n_est_pas_prise_pour_la_precedente(self):
        self._periode(
            libelle='2027', debut=date(2027, 1, 1), fin=date(2027, 12, 31))
        courante = self._periode()
        resultat = selectors.prerequis_cloture_esg(courante)
        self.assertIsNone(resultat['comparaison'])

    # ── forme + réglage société ────────────────────────────────────────────
    def test_forme_de_la_reponse(self):
        periode = self._periode()
        resp = _api(self.user).get(_url(periode.pk))
        self.assertEqual(resp.status_code, status.HTTP_200_OK, resp.content)
        for cle in ('periode', 'couverture', 'comparaison', 'avertissements',
                    'bloquants', 'peut_figer', 'frequence_reporting'):
            self.assertIn(cle, resp.data)
        self.assertEqual(resp.data['periode']['id'], periode.pk)

    def test_frequence_vient_du_reglage_societe(self):
        from apps.esg.models import ParametresESG
        ParametresESG.objects.create(
            company=self.co,
            frequence_reporting=ParametresESG.Frequence.TRIMESTRIELLE)
        periode = self._periode()
        self.assertEqual(
            selectors.prerequis_cloture_esg(periode)['frequence_reporting'],
            'trimestrielle')

    # ── l'API figer reste directement appelable (automatisation) ───────────
    def test_figer_reste_appelable_sans_passer_par_l_assistant(self):
        periode = self._periode()
        resp = _api(self.user).post(
            f'/api/django/esg/periodes-esg/{periode.pk}/figer/')
        self.assertEqual(resp.status_code, status.HTTP_200_OK, resp.content)
        periode.refresh_from_db()
        self.assertEqual(periode.statut, PeriodeReportingESG.Statut.FIGEE)
        self.assertTrue(SnapshotESG.objects.filter(periode=periode).exists())

    # ── multi-tenant ───────────────────────────────────────────────────────
    def test_cross_tenant_404(self):
        autre = Company.objects.create(nom='Autre', slug='esg-ntesg18-autre')
        voisine = PeriodeReportingESG.objects.create(
            company=autre, libelle='Voisine', date_debut=date(2026, 1, 1),
            date_fin=date(2026, 12, 31))
        resp = _api(self.user).get(_url(voisine.pk))
        self.assertIn(resp.status_code, (status.HTTP_403_FORBIDDEN,
                                         status.HTTP_404_NOT_FOUND))
