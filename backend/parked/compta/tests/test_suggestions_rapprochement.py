"""XACC3 — Auto-suggestion de rapprochement bancaire.

Couvre :

* une ligne de relevé au montant+réf d'une facture GL reçoit la suggestion en
  tête (meilleur score) ;
* l'acceptation (``accepter_suggestions_rapprochement``) crée le pointage pour
  les lignes NON ambiguës ;
* les lignes ambiguës (2 candidats au même montant/score) ne sont JAMAIS
  auto-acceptées ;
* l'endpoint API ``suggestions``/``accepter-suggestions``.
"""
from datetime import date
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from authentication.models import Company

from apps.compta import selectors, services
from apps.compta.models import (
    CompteTresorerie, LigneReleve, PointageReleve,
)

User = get_user_model()


def make_company(slug, nom):
    company, _ = Company.objects.get_or_create(slug=slug, defaults={'nom': nom})
    return company


def make_user(company, username, role='responsable'):
    return User.objects.create_user(
        username=username, password='x', company=company, role_legacy=role)


def auth(user):
    api = APIClient()
    api.credentials(HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(user)}')
    return api


def _journal_type(code):
    from apps.compta.models import Journal
    return {
        'VTE': Journal.Type.VENTE, 'BNK': Journal.Type.BANQUE,
        'OD': Journal.Type.OPERATIONS_DIVERSES,
    }[code]


def _ecriture(company, code_journal, lignes_par_numero, *, jour, reference=''):
    journal = services._journal(company, _journal_type(code_journal))
    lignes = []
    for numero, debit, credit in lignes_par_numero:
        lignes.append({
            'compte': services.get_compte(company, numero),
            'debit': Decimal(debit), 'credit': Decimal(credit),
        })
    return services.creer_ecriture(
        company, journal, jour, 'Test XACC3', lignes, reference=reference)


class SuggestionsRapprochementTests(TestCase):
    def setUp(self):
        self.co = make_company('xacc3', 'XACC3 Co')
        services.seed_plan_comptable(self.co)
        services.seed_journaux(self.co)
        self.banque = CompteTresorerie.objects.create(
            company=self.co, type_compte=CompteTresorerie.Type.BANQUE,
            libelle='BMCE', solde_initial=Decimal('0'),
            compte_comptable=services.get_compte(self.co, '5141'))
        self.rap = services.creer_rapprochement(
            self.co, self.banque, date_debut=date(2026, 1, 1),
            date_fin=date(2026, 1, 31), solde_releve=Decimal('1200'))

    def test_montant_et_reference_donnent_la_meilleure_suggestion(self):
        # Écriture GL : encaissement facture FAC-100 (débit banque 1200).
        ecr = _ecriture(
            self.co, 'BNK', [('5141', '1200', '0'), ('3421', '0', '1200')],
            jour=date(2026, 1, 10), reference='FAC-100')
        ligne_releve = services.ajouter_ligne_releve(
            self.rap, date_operation=date(2026, 1, 10),
            libelle='VIR CLIENT FAC-100', montant=Decimal('1200'))
        suggestions = selectors.suggestions_rapprochement(self.rap)
        self.assertEqual(len(suggestions), 1)
        sugg = suggestions[0]
        self.assertEqual(sugg['ligne_releve_id'], ligne_releve.id)
        self.assertFalse(sugg['ambigue'])
        self.assertTrue(sugg['candidats'])
        meilleur = sugg['candidats'][0]
        gl_banque = ecr.lignes.get(compte__numero='5141')
        self.assertEqual(meilleur['ligne_gl_id'], gl_banque.id)
        # Montant exact + date exacte + référence dans le libellé : score élevé.
        self.assertGreaterEqual(meilleur['score'], 60 + 20 + 15)

    def test_acceptation_pointe_la_suggestion_non_ambigue(self):
        ecr = _ecriture(
            self.co, 'BNK', [('5141', '500', '0'), ('3421', '0', '500')],
            jour=date(2026, 1, 12), reference='FAC-200')
        services.ajouter_ligne_releve(
            self.rap, date_operation=date(2026, 1, 12),
            libelle='VIR FAC-200', montant=Decimal('500'))
        resultat = services.accepter_suggestions_rapprochement(self.rap)
        self.assertEqual(len(resultat['pointees']), 1)
        self.assertEqual(resultat['ignorees'], [])
        gl_banque = ecr.lignes.get(compte__numero='5141')
        self.assertTrue(
            PointageReleve.objects.filter(
                company=self.co, ligne_gl=gl_banque).exists())
        ligne_releve = LigneReleve.objects.get(company=self.co, montant=500)
        self.assertEqual(ligne_releve.statut, LigneReleve.Statut.RAPPROCHEE)

    def test_lignes_ambigues_ne_sont_jamais_auto_acceptees(self):
        # Deux écritures GL au MÊME montant/date : ambiguïté, aucune auto-accept.
        _ecriture(
            self.co, 'BNK', [('5141', '300', '0'), ('3421', '0', '300')],
            jour=date(2026, 1, 15), reference='FAC-A')
        _ecriture(
            self.co, 'BNK', [('5141', '300', '0'), ('3421', '0', '300')],
            jour=date(2026, 1, 15), reference='FAC-B')
        services.ajouter_ligne_releve(
            self.rap, date_operation=date(2026, 1, 15),
            libelle='VIR AMBIGU', montant=Decimal('300'))
        suggestions = selectors.suggestions_rapprochement(self.rap)
        self.assertTrue(suggestions[0]['ambigue'])
        resultat = services.accepter_suggestions_rapprochement(self.rap)
        self.assertEqual(resultat['pointees'], [])
        self.assertEqual(len(resultat['ignorees']), 1)
        self.assertIn('ambigu', resultat['ignorees'][0]['raison'])
        self.assertEqual(
            PointageReleve.objects.filter(company=self.co).count(), 0)

    def test_aucun_candidat_liste_dans_ignorees(self):
        services.ajouter_ligne_releve(
            self.rap, date_operation=date(2026, 1, 20),
            libelle='VIR SANS MATCH', montant=Decimal('9999'))
        resultat = services.accepter_suggestions_rapprochement(self.rap)
        self.assertEqual(resultat['pointees'], [])
        self.assertEqual(len(resultat['ignorees']), 1)
        self.assertEqual(resultat['ignorees'][0]['raison'], 'aucun candidat')


class SuggestionsRapprochementAPITests(TestCase):
    def setUp(self):
        self.co = make_company('xacc3-api', 'XACC3 API Co')
        services.seed_plan_comptable(self.co)
        services.seed_journaux(self.co)
        self.banque = CompteTresorerie.objects.create(
            company=self.co, type_compte=CompteTresorerie.Type.BANQUE,
            libelle='BMCE', solde_initial=Decimal('0'),
            compte_comptable=services.get_compte(self.co, '5141'))
        self.rap = services.creer_rapprochement(
            self.co, self.banque, date_debut=date(2026, 1, 1),
            date_fin=date(2026, 1, 31), solde_releve=Decimal('700'))
        self.user = make_user(self.co, 'admin-xacc3')
        self.api = auth(self.user)

    def test_endpoint_suggestions_et_acceptation(self):
        _ecriture(
            self.co, 'BNK', [('5141', '700', '0'), ('3421', '0', '700')],
            jour=date(2026, 1, 5), reference='FAC-700')
        services.ajouter_ligne_releve(
            self.rap, date_operation=date(2026, 1, 5),
            libelle='VIR FAC-700', montant=Decimal('700'))
        resp = self.api.get(
            f'/api/django/compta/rapprochements/{self.rap.id}/suggestions/')
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(len(resp.data), 1)
        resp2 = self.api.post(
            '/api/django/compta/rapprochements/'
            f'{self.rap.id}/accepter-suggestions/')
        self.assertEqual(resp2.status_code, 200)
        self.assertEqual(len(resp2.data['pointees']), 1)
