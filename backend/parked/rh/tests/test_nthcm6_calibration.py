"""Tests NTHCM6 — calibration des révisions salariales.

Couvre :
* le RH voit TOUTES les propositions du cycle, tous managers confondus, avec
  la consommation d'enveloppe par manager ;
* la distribution est agrégée sur le vocabulaire FERMÉ des tranches ;
* une proposition REJETÉE apparaît dans la liste mais ne consomme AUCUNE
  enveloppe ;
* valider la calibration FIGE le cycle ; un second appel répond 400 ;
* la permission ``salaires_voir`` gate l'endpoint (jamais élargi) ;
* isolation société ;
* l'exemple de contrat committé a EXACTEMENT les clés servies (PACT10).
"""
import json
from decimal import Decimal
from pathlib import Path

from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from authentication.models import Company
from apps.rh import selectors, services
from apps.rh.models import (
    CycleRevisionSalariale,
    DossierEmploye,
    EnveloppeManager,
    PropositionRevision,
)
from apps.roles.models import Role

User = get_user_model()

CONTRAT = (Path(__file__).resolve().parent.parent
           / 'contract_samples' / 'calibration_revisions.json')


def make_company(slug, nom):
    company, _ = Company.objects.get_or_create(slug=slug, defaults={'nom': nom})
    return company


def make_user_salaires(company, username, permissions=('salaires_voir',)):
    """Compte porteur de ``salaires_voir`` — même patron que le test NTHCM5."""
    role = Role.objects.create(
        company=company, nom=f'role-{username}', permissions=list(permissions))
    return User.objects.create_user(
        username=username, password='x', company=company, role=role)


def auth(user):
    api = APIClient()
    api.credentials(HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(user)}')
    return api


class CalibrationTests(TestCase):
    def setUp(self):
        self.co = make_company('nthcm6-a', 'A')
        self.rh = make_user_salaires(self.co, 'nthcm6-rh')
        self.api = auth(self.rh)
        self.manager = DossierEmploye.objects.create(
            company=self.co, matricule='K-001', nom='Bennani', prenom='Y')
        self.a = DossierEmploye.objects.create(
            company=self.co, matricule='K-002', nom='Alami', prenom='S',
            manager=self.manager)
        self.b = DossierEmploye.objects.create(
            company=self.co, matricule='K-003', nom='Cherkaoui', prenom='I',
            manager=self.manager)
        self.cycle = CycleRevisionSalariale.objects.create(
            company=self.co, libelle='Révisions 2026', periode='2026',
            statut=CycleRevisionSalariale.Statut.CALIBRATION)
        EnveloppeManager.objects.create(
            company=self.co, cycle=self.cycle, manager=self.manager,
            enveloppe_pct=Decimal('5.00'))
        PropositionRevision.objects.create(
            company=self.co, cycle=self.cycle, employe=self.a,
            augmentation_pct_proposee=Decimal('3.00'))
        PropositionRevision.objects.create(
            company=self.co, cycle=self.cycle, employe=self.b,
            augmentation_pct_proposee=Decimal('7.00'),
            statut=PropositionRevision.Statut.REJETEE)

    def test_toutes_les_propositions_du_cycle(self):
        calibration = selectors.calibration_cycle_revision(
            self.co, self.cycle.id)
        self.assertEqual(calibration['nb_propositions'], 2)
        employes = sorted(
            ligne['employe'] for ligne in calibration['propositions'])
        self.assertEqual(employes, ['Alami S', 'Cherkaoui I'])
        self.assertEqual(
            calibration['propositions'][0]['manager'], 'Bennani Y')

    def test_distribution_sur_le_vocabulaire_ferme(self):
        calibration = selectors.calibration_cycle_revision(
            self.co, self.cycle.id)
        tranches = {ligne['tranche']: ligne['nombre']
                    for ligne in calibration['distribution']}
        self.assertEqual(
            sorted(tranches),
            sorted(etiquette
                   for etiquette, _, _ in selectors.TRANCHES_CALIBRATION))
        self.assertEqual(tranches['2-4'], 1)   # 3 %
        self.assertEqual(tranches['6+'], 1)    # 7 % (rejetée, mais listée)
        self.assertEqual(tranches['0'], 0)

    def test_proposition_rejetee_ne_consomme_rien(self):
        calibration = selectors.calibration_cycle_revision(
            self.co, self.cycle.id)
        ligne = calibration['par_manager'][0]
        self.assertEqual(ligne['enveloppe_allouee_pct'], Decimal('5.00'))
        # 3 % (proposée) seulement — les 7 % rejetés rendent leur enveloppe.
        self.assertEqual(ligne['enveloppe_consommee_pct'], Decimal('3.00'))
        self.assertFalse(ligne['depassement'])

    def test_depassement_signale(self):
        PropositionRevision.objects.filter(
            cycle=self.cycle, employe=self.b).update(
                statut=PropositionRevision.Statut.PROPOSEE)
        calibration = selectors.calibration_cycle_revision(
            self.co, self.cycle.id)
        self.assertTrue(calibration['par_manager'][0]['depassement'])

    def test_cycle_inconnu(self):
        self.assertIsNone(
            selectors.calibration_cycle_revision(self.co, 999999))

    def test_isolation_societe(self):
        autre = make_company('nthcm6-b', 'B')
        self.assertIsNone(
            selectors.calibration_cycle_revision(autre, self.cycle.id))

    # ── validation ────────────────────────────────────────────────────────
    def test_valider_fige_le_cycle_une_seule_fois(self):
        resultat = services.valider_calibration_cycle(self.cycle)
        self.cycle.refresh_from_db()
        self.assertEqual(self.cycle.statut, 'clos')
        self.assertEqual(resultat['propositions_figees'], 2)
        with self.assertRaises(services.CalibrationDejaValideeError):
            services.valider_calibration_cycle(self.cycle)

    # ── API ───────────────────────────────────────────────────────────────
    def test_endpoint_calibration(self):
        reponse = self.api.get(
            f'/api/django/rh/cycles-revision/{self.cycle.id}/calibration/')
        self.assertEqual(reponse.status_code, 200, reponse.content)
        self.assertEqual(reponse.data['nb_propositions'], 2)
        self.assertFalse(reponse.data['cycle']['clos'])

    def test_endpoint_valider_puis_400(self):
        url = (f'/api/django/rh/cycles-revision/{self.cycle.id}'
               '/valider-calibration/')
        premier = self.api.post(url, {}, format='json')
        self.assertEqual(premier.status_code, 200, premier.content)
        second = self.api.post(url, {}, format='json')
        self.assertEqual(second.status_code, 400, second.content)
        self.assertIn('déjà clos', second.data['detail'])

    def test_endpoint_refuse_sans_salaires_voir(self):
        simple = make_user_salaires(
            self.co, 'nthcm6-simple', permissions=('rh_voir',))
        reponse = auth(simple).get(
            f'/api/django/rh/cycles-revision/{self.cycle.id}/calibration/')
        self.assertEqual(reponse.status_code, 403, reponse.content)

    def test_contrat_committe_a_les_memes_cles(self):
        """PACT10 — l'exemple JSON doit refléter la forme RÉELLE servie."""
        contrat = json.loads(CONTRAT.read_text(encoding='utf-8'))
        servi = selectors.calibration_cycle_revision(self.co, self.cycle.id)
        self.assertEqual(sorted(contrat['exemple']), sorted(servi))
        self.assertEqual(
            sorted(contrat['exemple']['cycle']), sorted(servi['cycle']))
        self.assertEqual(
            sorted(contrat['exemple']['propositions'][0]),
            sorted(servi['propositions'][0]))
        self.assertEqual(
            sorted(contrat['exemple']['par_manager'][0]),
            sorted(servi['par_manager'][0]))
        self.assertEqual(
            sorted(contrat['exemple']['distribution'][0]),
            sorted(servi['distribution'][0]))
        self.assertEqual(sorted(contrat['exemple_vide']), sorted(servi))
