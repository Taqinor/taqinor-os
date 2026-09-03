"""AUD516 — l'import de contrats ne pose plus le statut HORS machine d'états.

Constat d'audit (le ROUGE figé ici) : ``creer_contrat_import`` faisait
``Contrat.objects.create(statut=<valeur brute du fichier>)`` — zéro passage par
``changer_statut``/``machine_etats``, zéro garde « ≥ 2 parties », aucune
``SignatureContrat``, aucune ``Resiliation``, et aucun des trois événements
``core.events`` (``contrat_signe``/``contrat_actif``/``contrat_resilie``). Un
simple CSV fabriquait donc un contrat ACTIF sans partie ni signature.

Après correctif : le contrat naît TOUJOURS en brouillon, puis un statut cible
est atteint par les SERVICES GARDÉS ; une cible inatteignable met la LIGNE en
erreur (et la transaction de la ligne est annulée) au lieu de forcer le statut.

Run :
    python manage.py test apps.dataimport.test_aud516_contrat_statut_import -v2
"""
from django.test import TestCase

from authentication.models import Company
from apps.contrats.models import Contrat, Resiliation, SignatureContrat
from apps.contrats.services import creer_contrat_import


def make_company(slug, nom):
    company, _ = Company.objects.get_or_create(slug=slug, defaults={'nom': nom})
    return company


class AUD516StatutImportContratTests(TestCase):
    def setUp(self):
        self.co = make_company('imp-aud516', 'Imp AUD516')

    # ── ROUGE — un CSV fabriquait un contrat ACTIF ──────────────────────────

    def test_statut_actif_du_fichier_refuse(self):
        statut, message = creer_contrat_import(self.co, {
            'objet': 'Contrat repris', 'reference': 'AUD516-1',
            'statut': 'actif',
        })
        self.assertEqual(statut, 'erreur')
        self.assertIn('actif', (message or '').lower())
        # Rien n'est laissé derrière : ni contrat, ni statut posé en force.
        self.assertFalse(
            Contrat.objects.filter(company=self.co, reference='AUD516-1')
            .exists())

    def test_statut_signe_du_fichier_refuse_sans_signature(self):
        statut, message = creer_contrat_import(self.co, {
            'objet': 'Contrat signé ailleurs', 'reference': 'AUD516-2',
            'statut': 'signe',
        })
        self.assertEqual(statut, 'erreur')
        self.assertIn('sign', (message or '').lower())
        self.assertFalse(
            Contrat.objects.filter(company=self.co, reference='AUD516-2')
            .exists())
        self.assertEqual(SignatureContrat.objects.count(), 0)

    def test_statut_en_approbation_refuse_sans_deux_parties(self):
        """La garde métier « ≥ 2 parties » s'applique enfin à l'import."""
        statut, message = creer_contrat_import(self.co, {
            'objet': 'À approuver', 'reference': 'AUD516-3',
            'statut': 'en_approbation',
        })
        self.assertEqual(statut, 'erreur')
        self.assertIsNotNone(message)
        self.assertFalse(
            Contrat.objects.filter(company=self.co, reference='AUD516-3')
            .exists())

    def test_statut_suspendu_refuse_transition_interdite(self):
        statut, _ = creer_contrat_import(self.co, {
            'objet': 'Suspendu', 'reference': 'AUD516-4',
            'statut': 'suspendu',
        })
        self.assertEqual(statut, 'erreur')
        self.assertFalse(
            Contrat.objects.filter(company=self.co, reference='AUD516-4')
            .exists())

    # ── Le chemin gardé qui FONCTIONNE : résiliation par service ────────────

    def test_statut_resilie_passe_par_le_service_garde(self):
        statut, message = creer_contrat_import(self.co, {
            'objet': 'Contrat clos', 'reference': 'AUD516-5',
            'statut': 'resilie',
        })
        self.assertEqual(statut, 'cree', message)
        contrat = Contrat.objects.get(company=self.co, reference='AUD516-5')
        self.assertEqual(contrat.statut, Contrat.Statut.RESILIE)
        # Le service gardé a créé la Resiliation — l'écriture directe, non.
        self.assertTrue(
            Resiliation.objects.filter(contrat=contrat).exists())

    # ── Non-régression ARC13 ────────────────────────────────────────────────

    def test_sans_statut_le_contrat_nait_brouillon(self):
        statut, _ = creer_contrat_import(self.co, {
            'objet': 'Import simple', 'reference': 'AUD516-6',
        })
        self.assertEqual(statut, 'cree')
        contrat = Contrat.objects.get(company=self.co, reference='AUD516-6')
        self.assertEqual(contrat.statut, Contrat.Statut.BROUILLON)

    def test_statut_inconnu_retombe_sur_brouillon(self):
        statut, _ = creer_contrat_import(self.co, {
            'objet': 'Statut bidon', 'reference': 'AUD516-7',
            'statut': 'bidon-inexistant',
        })
        self.assertEqual(statut, 'cree')
        contrat = Contrat.objects.get(company=self.co, reference='AUD516-7')
        self.assertEqual(contrat.statut, Contrat.Statut.BROUILLON)

    def test_statut_brouillon_explicite_inchange(self):
        statut, _ = creer_contrat_import(self.co, {
            'objet': 'Brouillon explicite', 'reference': 'AUD516-8',
            'statut': 'brouillon', 'montant': '1 500,50',
        })
        self.assertEqual(statut, 'cree')
        contrat = Contrat.objects.get(company=self.co, reference='AUD516-8')
        self.assertEqual(contrat.statut, Contrat.Statut.BROUILLON)
        self.assertEqual(str(contrat.montant), '1500.50')
