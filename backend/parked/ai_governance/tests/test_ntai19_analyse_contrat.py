"""NTAI19 — Tests de l'analyse de contrat (échéances + alerte de préavis).

Couvre : les dates/montant/préavis rendus, la PROPOSITION d'alerte sans
écriture, la création UNIQUEMENT sur confirmation explicite, le refus de
proposer quand l'échéance ne peut pas être établie (jamais de date inventée),
la lecture des durées (« 3 mois ») et le scoping société.
"""
from datetime import date
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from authentication.models import Company

from ..contrat_ai import analyser_contrat, lire_date, lire_preavis_jours

User = get_user_model()

URL = '/api/django/ai/analyser-contrat/'


def make_company(slug, nom):
    company, _ = Company.objects.get_or_create(slug=slug, defaults={'nom': nom})
    return company


def auth(user):
    api = APIClient()
    api.credentials(HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(user)}')
    return api


class Ntai19AnalyseContratTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        from apps.contrats.models import Contrat

        cls.company = make_company('ntai19-co', 'NTAI19 Co')
        cls.autre = make_company('ntai19-autre', 'NTAI19 Autre')
        cls.user = User.objects.create_user(
            username='ntai19-user', password='x', company=cls.company,
            role_legacy='normal')
        cls.contrat = Contrat.objects.create(
            company=cls.company, objet='Maintenance annuelle',
            montant=Decimal('48000'), type_contrat='vente',
            date_debut=date(2026, 1, 1), date_fin=date(2026, 12, 31),
            preavis_jours=60)
        cls.sans_echeance = Contrat.objects.create(
            company=cls.company, objet='Contrat sans date',
            type_contrat='vente')
        cls.contrat_autre = Contrat.objects.create(
            company=cls.autre, objet='Contrat voisin', type_contrat='vente')

    # --- Lecture des valeurs ------------------------------------------------

    def test_lire_date_formats_acceptes_et_refuses(self):
        self.assertEqual(lire_date('2026-12-31'), date(2026, 12, 31))
        self.assertEqual(lire_date('31/12/2026'), date(2026, 12, 31))
        # Format non reconnu : None, jamais une date devinée.
        self.assertIsNone(lire_date('fin décembre'))
        self.assertIsNone(lire_date(''))

    def test_lire_preavis_en_jours_et_en_mois(self):
        self.assertEqual(lire_preavis_jours('90'), 90)
        self.assertEqual(lire_preavis_jours('90 jours'), 90)
        self.assertEqual(lire_preavis_jours('3 mois'), 90)
        self.assertEqual(lire_preavis_jours('1 an'), 365)
        self.assertIsNone(lire_preavis_jours('à discuter'))

    # --- Analyse ------------------------------------------------------------

    def test_analyse_rend_les_echeances_et_propose_une_alerte(self):
        resultat = analyser_contrat(
            company=self.company, contrat_id=self.contrat.id)
        self.assertEqual(resultat['date_fin'], '2026-12-31')
        self.assertEqual(resultat['preavis_jours'], 60)
        self.assertEqual(Decimal(resultat['montant']), Decimal('48000'))
        # 31/12/2026 - 60 jours = 01/11/2026 (soustraction, pas estimation).
        self.assertEqual(resultat['proposition']['date_declenchement'],
                         '2026-11-01')
        self.assertFalse(resultat['applique'])

    def test_analyse_n_ecrit_rien_sans_confirmation(self):
        from apps.contrats.models import AlerteContrat

        analyser_contrat(company=self.company, contrat_id=self.contrat.id)
        self.assertEqual(AlerteContrat.objects.count(), 0)

    def test_confirmation_cree_l_alerte(self):
        from apps.contrats.models import AlerteContrat

        resultat = analyser_contrat(
            company=self.company, contrat_id=self.contrat.id,
            confirmer=True, user=self.user)
        self.assertTrue(resultat['applique'])
        alerte = AlerteContrat.objects.get(pk=resultat['alerte_id'])
        self.assertEqual(alerte.company_id, self.company.id)
        self.assertEqual(alerte.contrat_id, self.contrat.id)
        self.assertEqual(alerte.date_declenchement, date(2026, 11, 1))
        self.assertEqual(alerte.type_alerte, 'preavis')

    def test_sans_echeance_aucune_proposition(self):
        resultat = analyser_contrat(
            company=self.company, contrat_id=self.sans_echeance.id)
        self.assertIsNone(resultat['proposition'])

    def test_confirmation_refusee_sans_echeance(self):
        from apps.ai_governance.services import AiCopiloteUnavailable
        from apps.contrats.models import AlerteContrat

        with self.assertRaises(AiCopiloteUnavailable):
            analyser_contrat(
                company=self.company, contrat_id=self.sans_echeance.id,
                confirmer=True, user=self.user)
        self.assertEqual(AlerteContrat.objects.count(), 0)

    def test_contrat_d_une_autre_societe_refuse(self):
        from apps.ai_governance.services import AiCopiloteUnavailable

        with self.assertRaises(AiCopiloteUnavailable):
            analyser_contrat(company=self.company,
                             contrat_id=self.contrat_autre.id)

    # --- Endpoint -----------------------------------------------------------

    def test_endpoint_propose_puis_applique(self):
        api = auth(self.user)
        reponse = api.post(URL, {'contrat_id': self.contrat.id},
                           format='json')
        self.assertEqual(reponse.status_code, 200, reponse.content)
        self.assertFalse(reponse.json()['applique'])

        confirmee = api.post(
            URL, {'contrat_id': self.contrat.id, 'confirmer': True},
            format='json')
        self.assertEqual(confirmee.status_code, 200, confirmee.content)
        self.assertTrue(confirmee.json()['applique'])

    def test_endpoint_exige_un_contrat(self):
        reponse = auth(self.user).post(URL, {}, format='json')
        self.assertEqual(reponse.status_code, 400)
