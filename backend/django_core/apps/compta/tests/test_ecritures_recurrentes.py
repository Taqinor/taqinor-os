"""XACC8 — Modèles d'écriture, écritures récurrentes & extourne automatique.

Couvre :

* un loyer mensuel (modèle 6131/5141) est généré chaque mois SANS doublon
  (idempotent par période) ;
* l'extourne automatique (``modele.extourne_auto``) est liée à l'écriture
  d'origine et datée du 1er jour du mois suivant ;
* le verrou de période est respecté (échéance dans un mois clos → ignorée,
  pas de crash du batch) ;
* la commande ``generer_ecritures_recurrentes`` (CLI).
"""
from datetime import date
from decimal import Decimal

from django.core.exceptions import ValidationError
from django.core.management import call_command
from django.test import TestCase

from authentication.models import Company

from apps.compta import services
from apps.compta.models import (
    AbonnementEcriture, EcritureComptable, LigneModeleEcriture, ModeleEcriture,
)


def make_company(slug, nom):
    company, _ = Company.objects.get_or_create(slug=slug, defaults={'nom': nom})
    return company


class EcheanceSuivanteTests(TestCase):
    def setUp(self):
        self.co = make_company('xacc8-ech', 'XACC8 Échéance Co')
        services.seed_plan_comptable(self.co)
        services.seed_journaux(self.co)
        modele = ModeleEcriture.objects.create(
            company=self.co, libelle='Loyer',
            journal=services._journal(
                self.co, services.Journal.Type.OPERATIONS_DIVERSES))
        self.ab = AbonnementEcriture.objects.create(
            company=self.co, modele=modele,
            prochaine_echeance=date(2026, 1, 31))

    def test_mensuelle_clampe_fin_de_mois(self):
        # 31 janvier + 1 mois → 28 février (2026 n'est pas bissextile).
        suivante = self.ab.echeance_suivante(date(2026, 1, 31))
        self.assertEqual(suivante, date(2026, 2, 28))

    def test_trimestrielle(self):
        self.ab.frequence = AbonnementEcriture.Frequence.TRIMESTRIELLE
        suivante = self.ab.echeance_suivante(date(2026, 1, 15))
        self.assertEqual(suivante, date(2026, 4, 15))

    def test_decembre_passe_a_annee_suivante(self):
        suivante = self.ab.echeance_suivante(date(2026, 12, 10))
        self.assertEqual(suivante, date(2027, 1, 10))


class GenererEcrituresRecurrentesTests(TestCase):
    def setUp(self):
        self.co = make_company('xacc8', 'XACC8 Co')
        services.seed_plan_comptable(self.co)
        services.seed_journaux(self.co)
        self.journal_od = services._journal(
            self.co, services.Journal.Type.OPERATIONS_DIVERSES)
        self.modele = ModeleEcriture.objects.create(
            company=self.co, libelle='Loyer mensuel', journal=self.journal_od,
            extourne_auto=False)
        compte_charge = services.get_compte(self.co, '6111')
        compte_banque = services.get_compte(self.co, '5141')
        LigneModeleEcriture.objects.create(
            company=self.co, modele=self.modele, compte=compte_charge,
            sens='debit', montant_defaut=Decimal('5000'), ordre=1)
        LigneModeleEcriture.objects.create(
            company=self.co, modele=self.modele, compte=compte_banque,
            sens='credit', montant_defaut=Decimal('5000'), ordre=2)
        self.ab = AbonnementEcriture.objects.create(
            company=self.co, modele=self.modele, libelle='Loyer bureau',
            prochaine_echeance=date(2026, 1, 31))

    def test_loyer_genere_chaque_mois_sans_doublon(self):
        res1 = services.generer_ecritures_recurrentes(
            self.co, jusqua=date(2026, 1, 31))
        self.assertEqual(len(res1['generees']), 1)
        self.ab.refresh_from_db()
        self.assertEqual(self.ab.prochaine_echeance, date(2026, 2, 28))

        # Rejouer le MÊME jusqua ne régénère rien (échéance déjà avancée).
        res2 = services.generer_ecritures_recurrentes(
            self.co, jusqua=date(2026, 1, 31))
        self.assertEqual(len(res2['generees']), 0)

        # Le mois suivant : une NOUVELLE écriture, jamais un doublon du mois 1.
        res3 = services.generer_ecritures_recurrentes(
            self.co, jusqua=date(2026, 2, 28))
        self.assertEqual(len(res3['generees']), 1)
        self.assertEqual(
            EcritureComptable.objects.filter(
                company=self.co, source_type='abonnement').count(), 2)

    def test_ecriture_equilibree_montants_par_defaut(self):
        services.generer_ecritures_recurrentes(self.co, jusqua=date(2026, 1, 31))
        ecr = EcritureComptable.objects.get(
            company=self.co, source_type='abonnement')
        self.assertTrue(ecr.est_equilibree)
        self.assertEqual(ecr.total_debit, Decimal('5000'))
        self.assertEqual(ecr.statut, EcritureComptable.Statut.BROUILLON)

    def test_extourne_auto_liee_a_ecriture_origine(self):
        self.modele.extourne_auto = True
        self.modele.save(update_fields=['extourne_auto'])
        res = services.generer_ecritures_recurrentes(
            self.co, jusqua=date(2026, 1, 31))
        self.assertIsNotNone(res['generees'][0]['extourne_id'])
        extourne = EcritureComptable.objects.get(
            id=res['generees'][0]['extourne_id'])
        self.assertEqual(extourne.source_type, 'extourne')
        self.assertEqual(
            extourne.source_id, res['generees'][0]['ecriture_id'])
        self.assertEqual(extourne.date_ecriture, date(2026, 2, 1))

    def test_verrou_de_periode_ignore_sans_crash(self):
        periode = services.creer_periode(
            self.co, date(2026, 1, 1), date(2026, 1, 31), libelle='Janvier 2026')
        services.cloturer_periode(periode)
        res = services.generer_ecritures_recurrentes(
            self.co, jusqua=date(2026, 1, 31))
        self.assertEqual(res['generees'], [])
        self.assertEqual(len(res['ignorees']), 1)
        # L'échéance n'avance PAS : la génération est retentée plus tard.
        self.ab.refresh_from_db()
        self.assertEqual(self.ab.prochaine_echeance, date(2026, 1, 31))

    def test_ligne_sans_montant_par_defaut_leve_erreur_explicite(self):
        LigneModeleEcriture.objects.filter(
            modele=self.modele, sens='credit').update(montant_defaut=None)
        with self.assertRaises(ValidationError):
            services.generer_ecriture_depuis_modele(
                self.modele, date_ecriture=date(2026, 1, 31))

    def test_abonnement_inactif_ignore(self):
        self.ab.actif = False
        self.ab.save(update_fields=['actif'])
        res = services.generer_ecritures_recurrentes(
            self.co, jusqua=date(2026, 1, 31))
        self.assertEqual(res['generees'], [])
        self.assertEqual(res['ignorees'], [])

    def test_date_fin_arrete_la_recurrence(self):
        self.ab.date_fin = date(2025, 12, 31)
        self.ab.save(update_fields=['date_fin'])
        res = services.generer_ecritures_recurrentes(
            self.co, jusqua=date(2026, 1, 31))
        self.assertEqual(res['generees'], [])


class GenererEcrituresRecurrentesCommandTests(TestCase):
    def setUp(self):
        self.co = make_company('xacc8-cmd', 'XACC8 Commande Co')
        services.seed_plan_comptable(self.co)
        services.seed_journaux(self.co)
        journal_od = services._journal(
            self.co, services.Journal.Type.OPERATIONS_DIVERSES)
        modele = ModeleEcriture.objects.create(
            company=self.co, libelle='Abonnement logiciel', journal=journal_od)
        LigneModeleEcriture.objects.create(
            company=self.co, modele=modele,
            compte=services.get_compte(self.co, '6111'),
            sens='debit', montant_defaut=Decimal('300'))
        LigneModeleEcriture.objects.create(
            company=self.co, modele=modele,
            compte=services.get_compte(self.co, '5141'),
            sens='credit', montant_defaut=Decimal('300'))
        AbonnementEcriture.objects.create(
            company=self.co, modele=modele,
            prochaine_echeance=date(2026, 1, 31))

    def test_commande_genere_via_slug(self):
        call_command(
            'generer_ecritures_recurrentes', company=self.co.slug,
            jusqua='2026-01-31')
        self.assertEqual(
            EcritureComptable.objects.filter(
                company=self.co, source_type='abonnement').count(), 1)

    def test_commande_all(self):
        call_command('generer_ecritures_recurrentes', all=True,
                     jusqua='2026-01-31')
        self.assertEqual(
            EcritureComptable.objects.filter(
                company=self.co, source_type='abonnement').count(), 1)
