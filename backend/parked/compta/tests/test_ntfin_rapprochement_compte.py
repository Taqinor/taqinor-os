"""Tests NTFIN35-39 — Rapprochements de comptes de bilan (workflow 4 yeux).

Couvre :

* NTFIN35 — un compte d'attente GL 12 000 / justifié 12 000 passe rapproché
  (écart 0).
* NTFIN36 — Σ lignes justificatives = solde justifié (contrôlé à la validation).
* NTFIN37 — le même utilisateur ne peut pas préparer ET valider (séparation).
* NTFIN38 — un compte non rapproché remonte dans la liste des en-retard.
* NTFIN39 — un rapprochement récurrent hérite des lignes permanentes N-1.
"""
from datetime import date
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.test import TestCase

from authentication.models import Company

from apps.compta import selectors, services
from apps.compta.models import (
    LigneJustificationCompte, PeriodeComptable, RapprochementCompte)

User = get_user_model()


def make_company(slug, nom):
    company, _ = Company.objects.get_or_create(slug=slug, defaults={'nom': nom})
    return company


class RapprochementCompteTests(TestCase):
    def setUp(self):
        self.co = make_company('ntfin35', 'NTFIN35')
        services.seed_plan_comptable(self.co)
        self.compte = services._assurer_compte(self.co, '3491')
        self.periode = PeriodeComptable.objects.create(
            company=self.co, date_debut=date(2026, 6, 1),
            date_fin=date(2026, 6, 30), libelle='Juin 2026')
        self.prep = User.objects.create_user(
            username='prep35', password='x', company=self.co)
        self.rev = User.objects.create_user(
            username='rev35', password='x', company=self.co)

    def _rappr(self, solde_gl=Decimal('12000')):
        return services.ouvrir_rapprochement_compte(
            self.co, self.compte, self.periode, solde_gl=solde_gl)

    def test_ecart_nul_passe_rapproche(self):
        rappr = self._rappr(Decimal('12000'))
        LigneJustificationCompte.objects.create(
            company=self.co, rapprochement=rappr, libelle='Justif',
            montant=Decimal('12000'))
        services.recalculer_rapprochement_compte(rappr)
        rappr.refresh_from_db()
        self.assertEqual(rappr.ecart, Decimal('0'))
        self.assertEqual(rappr.statut, RapprochementCompte.Statut.RAPPROCHE)

    def test_somme_lignes_controlee_a_la_validation(self):
        rappr = self._rappr(Decimal('12000'))
        LigneJustificationCompte.objects.create(
            company=self.co, rapprochement=rappr, libelle='Partiel',
            montant=Decimal('8000'))
        services.recalculer_rapprochement_compte(rappr)
        # solde_justifie = 8000 ; on force un solde_justifie incohérent puis
        # tente de valider → refus (Σ lignes 8000 != solde 9000).
        rappr.solde_justifie = Decimal('9000')
        rappr.save(update_fields=['solde_justifie'])
        services.soumettre_rapprochement_compte(rappr, user=self.prep)
        with self.assertRaises(ValidationError):
            services.valider_rapprochement_compte(rappr, user=self.rev)

    def test_separation_preparateur_reviseur(self):
        rappr = self._rappr(Decimal('12000'))
        LigneJustificationCompte.objects.create(
            company=self.co, rapprochement=rappr, libelle='Justif',
            montant=Decimal('12000'))
        services.recalculer_rapprochement_compte(rappr)
        services.soumettre_rapprochement_compte(rappr, user=self.prep)
        with self.assertRaises(ValidationError):
            services.valider_rapprochement_compte(rappr, user=self.prep)
        # Un réviseur distinct passe.
        services.valider_rapprochement_compte(rappr, user=self.rev)
        rappr.refresh_from_db()
        self.assertEqual(rappr.statut, RapprochementCompte.Statut.VALIDE)

    def test_en_retard_liste(self):
        self._rappr(Decimal('5000'))  # écart 5000, non validé
        data = selectors.rapprochements_en_retard(self.co, self.periode)
        self.assertEqual(data['nb_en_retard'], 1)
        self.assertEqual(data['total_ecart_non_justifie'], Decimal('5000'))

    def test_report_lignes_permanentes_n1(self):
        rappr_n1 = self._rappr(Decimal('12000'))
        LigneJustificationCompte.objects.create(
            company=self.co, rapprochement=rappr_n1, libelle='Abonnement',
            montant=Decimal('1000'), permanente=True)
        LigneJustificationCompte.objects.create(
            company=self.co, rapprochement=rappr_n1, libelle='Ponctuel',
            montant=Decimal('500'), permanente=False)
        periode_n = PeriodeComptable.objects.create(
            company=self.co, date_debut=date(2026, 7, 1),
            date_fin=date(2026, 7, 31), libelle='Juillet 2026')
        rappr_n = services.ouvrir_rapprochement_compte(
            self.co, self.compte, periode_n, solde_gl=Decimal('12000'))
        libelles = [li.libelle for li in rappr_n.lignes.all()]
        self.assertIn('Abonnement', libelles)
        self.assertNotIn('Ponctuel', libelles)
