"""NTGRC29 — score de maturité conformité.

Garanties : le score renvoie un TOTAL et le DÉTAIL pondéré par critère, borné
0-100 ; une société vierge ne décroche pas 100 % (ce qu'on doit DÉCLARER vaut
0 quand c'est vide) mais n'est pas punie pour ce qu'elle n'a jamais reçu ;
tout est scopé société. Horloge FIGÉE.
"""
from django.test import TestCase
from django.utils import timezone

from apps.grc.models import ControleInterne, PolitiqueInterne, ViolationDonnees
from apps.grc.selectors import PONDERATION_CONFORMITE, score_conformite
from apps.grc.services import creer_violation, notifier_cndp, publier_politique
from authentication.models import Company
from core.models import DataSubjectRequest, RegistreTraitement
from testkit.base import TenantAPITestCase
from testkit.time import frozen

INSTANT = '2026-09-12 12:00:00+00:00'


def _detail(resultat, critere):
    return next(d for d in resultat['details'] if d['critere'] == critere)


class ScoreConformiteTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.company = Company.objects.create(nom='NTGRC29 SA', slug='ntgrc29')

    def test_les_six_criteres_sont_toujours_presents(self):
        with frozen(INSTANT):
            resultat = score_conformite(self.company)
        self.assertEqual(
            {d['critere'] for d in resultat['details']},
            set(PONDERATION_CONFORMITE))

    def test_la_ponderation_totalise_cent(self):
        self.assertEqual(sum(PONDERATION_CONFORMITE.values()), 100)

    def test_le_score_est_borne_entre_0_et_100(self):
        with frozen(INSTANT):
            resultat = score_conformite(self.company)
        self.assertGreaterEqual(resultat['score'], 0.0)
        self.assertLessEqual(resultat['score'], 100.0)

    def test_une_societe_vierge_ne_decroche_pas_cent(self):
        """Rien de déclaré n'est PAS une conformité."""
        with frozen(INSTANT):
            resultat = score_conformite(self.company)
        self.assertEqual(_detail(resultat, 'ropa')['score'], 0.0)
        self.assertEqual(_detail(resultat, 'controles')['score'], 0.0)
        self.assertEqual(_detail(resultat, 'politiques')['score'], 0.0)
        # ... mais elle n'est pas punie pour ce qu'elle n'a jamais reçu.
        self.assertEqual(_detail(resultat, 'dsr')['score'], 100.0)
        self.assertEqual(_detail(resultat, 'violations')['score'], 100.0)
        self.assertEqual(_detail(resultat, 'dpia')['score'], 100.0)
        self.assertEqual(resultat['score'], 45.0)

    def test_un_ropa_a_moitie_renseigne_vaut_la_moitie(self):
        RegistreTraitement.objects.create(
            company=self.company, code='A', finalite='Prospection',
            base_legale='Consentement', categories_donnees='Contact',
            duree_conservation='3 ans')
        RegistreTraitement.objects.create(
            company=self.company, code='B', finalite='Paie')
        with frozen(INSTANT):
            resultat = score_conformite(self.company)
        ropa = _detail(resultat, 'ropa')
        self.assertEqual(ropa['score'], 50.0)
        self.assertEqual(ropa['points'], round(50.0 * ropa['poids'] / 100, 2))

    def test_un_controle_jamais_teste_fait_chuter_le_critere(self):
        ControleInterne.objects.create(
            company=self.company, code='ACC-01', intitule='Revue', actif=True)
        with frozen(INSTANT):
            resultat = score_conformite(self.company)
        self.assertEqual(_detail(resultat, 'controles')['score'], 0.0)

    def test_un_controle_inactif_ne_compte_pas(self):
        ControleInterne.objects.create(
            company=self.company, code='ACC-01', intitule='Revue', actif=False)
        with frozen(INSTANT):
            resultat = score_conformite(self.company)
        self.assertEqual(_detail(resultat, 'controles')['score'], 0.0)
        self.assertIn('sur 0', _detail(resultat, 'controles')['commentaire'])

    def test_une_dsr_encore_dans_les_temps_n_est_pas_jugee(self):
        with frozen(INSTANT):
            DataSubjectRequest.objects.create(
                company=self.company, subject_identifier='a@b.ma',
                kind=DataSubjectRequest.KIND_ACCESS)
            resultat = score_conformite(self.company)
        self.assertEqual(_detail(resultat, 'dsr')['score'], 100.0)

    def test_une_dsr_en_retard_fait_chuter_le_critere(self):
        with frozen(INSTANT):
            DataSubjectRequest.objects.create(
                company=self.company, subject_identifier='a@b.ma',
                kind=DataSubjectRequest.KIND_ACCESS)
        with frozen('2026-10-20 12:00:00+00:00'):
            resultat = score_conformite(self.company)
        self.assertEqual(_detail(resultat, 'dsr')['score'], 0.0)

    def test_une_violation_notifiee_a_temps_compte_pour_cent(self):
        with frozen(INSTANT):
            violation = creer_violation(
                self.company, date_detection=timezone.now(),
                statut=ViolationDonnees.STATUT_OUVERTE)
            notifier_cndp(violation)
            resultat = score_conformite(self.company)
        self.assertEqual(_detail(resultat, 'violations')['score'], 100.0)

    def test_une_violation_hors_delai_fait_chuter_le_critere(self):
        with frozen(INSTANT):
            creer_violation(
                self.company,
                date_detection=timezone.now() - timezone.timedelta(days=5),
                statut=ViolationDonnees.STATUT_OUVERTE)
            resultat = score_conformite(self.company)
        self.assertEqual(_detail(resultat, 'violations')['score'], 0.0)

    def test_une_politique_publiee_sans_attestation_pese(self):
        politique = PolitiqueInterne.objects.create(
            company=self.company, titre='Charte', contenu='Texte')
        publier_politique(politique)
        with frozen(INSTANT):
            resultat = score_conformite(self.company)
        self.assertEqual(_detail(resultat, 'politiques')['score'], 0.0)
        self.assertIn('1 politique(s) publiée(s)',
                      _detail(resultat, 'politiques')['commentaire'])

    def test_le_total_est_la_somme_des_points(self):
        with frozen(INSTANT):
            resultat = score_conformite(self.company)
        somme = round(sum(d['points'] for d in resultat['details']), 1)
        self.assertEqual(resultat['score'], somme)


class ScoreEndpointTests(TenantAPITestCase):
    URL = '/api/django/grc/score-conformite/'

    def test_endpoint_renvoie_total_et_detail(self):
        with frozen(INSTANT):
            r = self.client_as(role='admin').get(self.URL)
        self.assertEqual(r.status_code, 200, r.content)
        self.assertIn('score', r.data)
        self.assertEqual(len(r.data['details']), 6)
        for detail in r.data['details']:
            self.assertIn('poids', detail)
            self.assertIn('points', detail)
            self.assertIn('commentaire', detail)

    def test_le_score_est_scope_societe(self):
        RegistreTraitement.objects.create(
            company=self.other_company, code='A', finalite='X',
            base_legale='Y', categories_donnees='Z', duree_conservation='3 ans')
        with frozen(INSTANT):
            r = self.client_as(role='admin').get(self.URL)
        ropa = next(d for d in r.data['details'] if d['critere'] == 'ropa')
        self.assertEqual(ropa['score'], 0.0)
        self.assertIn('sur 0', ropa['commentaire'])
