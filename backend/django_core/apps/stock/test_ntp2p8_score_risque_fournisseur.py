"""
NTP2P8 — Score de risque fournisseur (calcul PUR, aucun service externe).

CRITÈRE D'ACCEPTATION : un fournisseur avec 3 retards CONSÉCUTIFS et un
document EXPIRÉ affiche un score < 50, avec le détail des facteurs.

Couvre aussi : le fournisseur sain à 100, chaque facteur isolément (OTD,
documents, retours, litiges, blocage), le plafonnement à 0-100, et le scope
société (un fournisseur d'une autre société n'est jamais noté).

Run :
    python manage.py test apps.stock.test_ntp2p8_score_risque_fournisseur -v2
"""
import itertools
from datetime import date, timedelta

from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from apps.stock import selectors as stock_selectors
from apps.stock.models import (
    BonCommandeFournisseur, DocumentFournisseur,
    DossierOnboardingFournisseur, Fournisseur, RetourFournisseur,
)

User = get_user_model()
_seq = itertools.count(1)
STOCK = '/api/django/stock'


def make_company():
    from authentication.models import Company
    n = next(_seq)
    company, _ = Company.objects.get_or_create(
        slug=f'ntp2p8-co-{n}', defaults={'nom': f'NTP2P8 Co {n}'})
    return company


def make_user(company, role='admin'):
    return User.objects.create_user(
        username=f'ntp2p8-{next(_seq)}', password='x',
        role_legacy=role, company=company)


def auth(user):
    api = APIClient()
    api.credentials(HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(user)}')
    return api


def make_bcf(company, fournisseur, *, prevue=None, confirmee=None):
    return BonCommandeFournisseur.objects.create(
        company=company, fournisseur=fournisseur,
        reference=f'BCF-T-{next(_seq):04d}',
        date_livraison_prevue=prevue, date_confirmee_fournisseur=confirmee)


def facteur(resultat, code):
    return next(f for f in resultat['facteurs'] if f['code'] == code)


class ScoreRisqueTests(TestCase):

    def setUp(self):
        self.company = make_company()
        self.user = make_user(self.company)
        self.api = auth(self.user)
        self.fournisseur = Fournisseur.objects.create(
            company=self.company, nom='SolarImport')

    def test_fournisseur_sain_score_100(self):
        resultat = stock_selectors.score_risque_fournisseur(
            self.company, self.fournisseur.pk)
        self.assertEqual(resultat['score'], 100)
        self.assertEqual(resultat['niveau'], 'faible')
        self.assertEqual(resultat['penalite_totale'], 0)
        self.assertEqual(len(resultat['facteurs']), 5)

    def test_trois_retards_et_un_document_expire_score_sous_50(self):
        """CRITÈRE D'ACCEPTATION NTP2P8."""
        prevue = date(2026, 3, 1)
        for _ in range(3):
            make_bcf(self.company, self.fournisseur,
                     prevue=prevue, confirmee=prevue + timedelta(days=7))

        dossier = DossierOnboardingFournisseur.objects.create(
            company=self.company, fournisseur=self.fournisseur)
        for type_document in DocumentFournisseur.TYPES_REQUIS:
            DocumentFournisseur.objects.create(
                company=self.company, dossier=dossier,
                type_document=type_document,
                file_key=f'attachments/{self.company.id}/{next(_seq)}.pdf',
                filename='piece.pdf')
        expiree = dossier.documents.first()
        expiree.date_expiration = date.today() - timedelta(days=1)
        expiree.save(update_fields=['date_expiration'])

        resultat = stock_selectors.score_risque_fournisseur(
            self.company, self.fournisseur.pk)
        self.assertLess(resultat['score'], 50)
        self.assertEqual(resultat['niveau'], 'eleve')
        # Le DÉTAIL des facteurs est présent et chiffré.
        otd = facteur(resultat, 'ponctualite')
        self.assertEqual(otd['detail']['retards'], 3)
        self.assertEqual(otd['detail']['taux_retard_pct'], 100)
        self.assertEqual(otd['penalite'], 45)
        docs = facteur(resultat, 'documents')
        self.assertEqual(docs['penalite'], 10)
        self.assertIn(expiree.type_document, docs['detail']['expires'])

    def test_livraisons_a_lheure_ne_penalisent_pas(self):
        prevue = date(2026, 3, 1)
        for _ in range(3):
            make_bcf(self.company, self.fournisseur,
                     prevue=prevue, confirmee=prevue)
        resultat = stock_selectors.score_risque_fournisseur(
            self.company, self.fournisseur.pk)
        self.assertEqual(facteur(resultat, 'ponctualite')['penalite'], 0)
        self.assertEqual(resultat['score'], 100)

    def test_bcf_sans_dates_ignores(self):
        make_bcf(self.company, self.fournisseur)
        resultat = stock_selectors.score_risque_fournisseur(
            self.company, self.fournisseur.pk)
        otd = facteur(resultat, 'ponctualite')
        self.assertEqual(otd['detail']['bcf_dates'], 0)
        self.assertEqual(otd['penalite'], 0)

    def test_un_retard_sur_quatre_penalise_proportionnellement(self):
        prevue = date(2026, 3, 1)
        make_bcf(self.company, self.fournisseur,
                 prevue=prevue, confirmee=prevue + timedelta(days=3))
        for _ in range(3):
            make_bcf(self.company, self.fournisseur,
                     prevue=prevue, confirmee=prevue)
        resultat = stock_selectors.score_risque_fournisseur(
            self.company, self.fournisseur.pk)
        self.assertEqual(facteur(resultat, 'ponctualite')['penalite'],
                         round(0.25 * 45))

    def test_retours_penalises(self):
        make_bcf(self.company, self.fournisseur)
        make_bcf(self.company, self.fournisseur)
        RetourFournisseur.objects.create(
            company=self.company, fournisseur=self.fournisseur,
            reference=f'RF-{next(_seq)}')
        resultat = stock_selectors.score_risque_fournisseur(
            self.company, self.fournisseur.pk)
        retours = facteur(resultat, 'retours')
        self.assertEqual(retours['detail']['taux_retour_pct'], 50)
        self.assertEqual(retours['penalite'], round(0.5 * 15))

    def test_litiges_ouverts_penalises(self):
        from apps.litiges.models import Reclamation
        Reclamation.objects.create(
            company=self.company, reference=f'REC-{next(_seq)}',
            objet='Marchandise non conforme', source_type='fournisseur',
            source_id=self.fournisseur.pk,
            statut=Reclamation.Statut.OUVERTE)
        resultat = stock_selectors.score_risque_fournisseur(
            self.company, self.fournisseur.pk)
        litiges = facteur(resultat, 'litiges')
        self.assertEqual(litiges['detail']['ouvertes'], 1)
        self.assertEqual(litiges['penalite'], 5)

    def test_litige_resolu_ne_penalise_pas(self):
        from apps.litiges.models import Reclamation
        Reclamation.objects.create(
            company=self.company, reference=f'REC-{next(_seq)}',
            objet='Résolu', source_type='fournisseur',
            source_id=self.fournisseur.pk,
            statut=Reclamation.Statut.RESOLUE)
        resultat = stock_selectors.score_risque_fournisseur(
            self.company, self.fournisseur.pk)
        self.assertEqual(facteur(resultat, 'litiges')['penalite'], 0)

    def test_blocage_total_penalise_au_maximum(self):
        self.fournisseur.statut = Fournisseur.Statut.BLOQUE_TOTAL
        self.fournisseur.save(update_fields=['statut'])
        resultat = stock_selectors.score_risque_fournisseur(
            self.company, self.fournisseur.pk)
        self.assertEqual(facteur(resultat, 'blocage')['penalite'], 25)
        self.assertEqual(resultat['score'], 75)

    def test_score_borne_a_zero(self):
        prevue = date(2026, 3, 1)
        make_bcf(self.company, self.fournisseur,
                 prevue=prevue, confirmee=prevue + timedelta(days=30))
        RetourFournisseur.objects.create(
            company=self.company, fournisseur=self.fournisseur,
            reference=f'RF-{next(_seq)}')
        self.fournisseur.statut = Fournisseur.Statut.BLOQUE_TOTAL
        self.fournisseur.save(update_fields=['statut'])
        dossier = DossierOnboardingFournisseur.objects.create(
            company=self.company, fournisseur=self.fournisseur)
        for type_document in DocumentFournisseur.TYPES_REQUIS:
            DocumentFournisseur.objects.create(
                company=self.company, dossier=dossier,
                type_document=type_document,
                file_key=f'attachments/{self.company.id}/{next(_seq)}.pdf',
                date_expiration=date.today() - timedelta(days=1))
        resultat = stock_selectors.score_risque_fournisseur(
            self.company, self.fournisseur.pk)
        self.assertGreaterEqual(resultat['score'], 0)
        self.assertLessEqual(resultat['score'], 100)

    def test_sans_dossier_et_sans_obligation_aucune_penalite_documentaire(self):
        resultat = stock_selectors.score_risque_fournisseur(
            self.company, self.fournisseur.pk)
        self.assertEqual(facteur(resultat, 'documents')['penalite'], 0)

    def test_endpoint_score_risque(self):
        resp = self.api.get(
            f'{STOCK}/fournisseurs/{self.fournisseur.pk}/score-risque/')
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.data['score'], 100)
        self.assertEqual(resp.data['fournisseur_id'], self.fournisseur.pk)
        self.assertEqual(len(resp.data['facteurs']), 5)

    def test_fournisseur_dune_autre_societe_jamais_note(self):
        autre = make_company()
        voisin = Fournisseur.objects.create(company=autre, nom='Voisin')
        self.assertIsNone(stock_selectors.score_risque_fournisseur(
            self.company, voisin.pk))
        resp = self.api.get(f'{STOCK}/fournisseurs/{voisin.pk}/score-risque/')
        self.assertEqual(resp.status_code, 404)
