"""Tests AUD188 — contraintes DB d'argent + garde de ligne sur `creer_ecriture`.

Deux défauts prouvés par l'audit :

* `creer_ecriture` — la fabrique UNIQUE des écritures — créait ses
  `LigneEcriture` en boucle sans jamais `full_clean()` et ne revalidait QUE
  l'écriture globale (`ecriture.clean()` = l'équilibre) : les règles de
  `LigneEcriture.clean()` étaient du code MORT en production. Le contrôle amont
  comparant des SOMMES, deux erreurs symétriques se compensaient — une écriture
  dont chaque ligne est simultanément débitée ET créditée passait, gonflant les
  colonnes MOUVEMENTS de la balance, le journal et le FEC déposé à la DGI. Le
  second chemin non gardé, le plus atteignable car branché sur l'UI, est
  `EcritureComptableSerializer`, et la variante NÉGATIVE est atteignable depuis
  l'écran (inputs sans `min="0"`).
* `Avoir`/`LigneAvoir` n'avaient AUCUNE `CheckConstraint` — et `Avoir` n'a même
  ni `clean()` ni `save()` : un `QuerySet.update(montant_ttc=-500)` posait une
  note de crédit négative que rien ne détectait.
"""
from datetime import date
from decimal import Decimal

from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction
from django.test import TestCase

from authentication.models import Company

from apps.compta import services
from apps.compta.models import EcritureComptable, Journal, LigneEcriture
from apps.crm.models import Client
from apps.facturation.models import Avoir, Facture, LigneFacture, Paiement


def make_company(slug, nom):
    company, _ = Company.objects.get_or_create(slug=slug, defaults={'nom': nom})
    return company


class GardeLigneEcritureTests(TestCase):
    def setUp(self):
        self.co = make_company('aud188', 'AUD188 Co')
        services.seed_plan_comptable(self.co)
        services.seed_journaux(self.co)
        self.journal = services._journal(
            self.co, Journal.Type.OPERATIONS_DIVERSES)
        self.c6111 = services.get_compte(self.co, '6111')
        self.c5141 = services.get_compte(self.co, '5141')

    def test_ligne_debitee_et_creditee_refusee(self):
        """Le cas EXACT que la garde de somme laissait passer : chaque ligne
        porte son propre montant en débit ET en crédit, donc Σ débit = Σ
        crédit — l'écriture était acceptée et gonflait les MOUVEMENTS."""
        with self.assertRaises(ValidationError):
            services.creer_ecriture(
                self.co, self.journal, date(2026, 6, 1), 'OD truquée', [
                    {'compte': self.c6111, 'debit': Decimal('1000'),
                     'credit': Decimal('1000')},
                    {'compte': self.c5141, 'debit': Decimal('500'),
                     'credit': Decimal('500')},
                ])
        self.assertEqual(
            EcritureComptable.objects.filter(company=self.co).count(), 0)
        self.assertEqual(
            LigneEcriture.objects.filter(company=self.co).count(), 0)

    def test_montant_negatif_refuse(self):
        with self.assertRaises(ValidationError):
            services.creer_ecriture(
                self.co, self.journal, date(2026, 6, 1), 'OD négative', [
                    {'compte': self.c6111, 'debit': Decimal('-100'),
                     'credit': Decimal('0')},
                    {'compte': self.c5141, 'debit': Decimal('0'),
                     'credit': Decimal('-100')},
                ])
        self.assertEqual(
            EcritureComptable.objects.filter(company=self.co).count(), 0)

    def test_ecriture_valide_inchangee(self):
        """Non-régression : une écriture correcte passe exactement comme avant."""
        ecriture = services.creer_ecriture(
            self.co, self.journal, date(2026, 6, 1), 'OD saine', [
                {'compte': self.c6111, 'debit': Decimal('1000'),
                 'credit': Decimal('0')},
                {'compte': self.c5141, 'debit': Decimal('0'),
                 'credit': Decimal('1000')},
            ])
        self.assertTrue(ecriture.est_equilibree)
        self.assertEqual(ecriture.lignes.count(), 2)

    def test_part_nulle_toujours_acceptee(self):
        """Une part de 0 reste légitime (coefficient de répartition à 0 %) :
        la troisième règle de `clean()` n'est DÉLIBÉRÉMENT pas appliquée ici."""
        ecriture = services.creer_ecriture(
            self.co, self.journal, date(2026, 6, 1), 'OD avec part nulle', [
                {'compte': self.c6111, 'debit': Decimal('1000'),
                 'credit': Decimal('0')},
                {'compte': self.c6111, 'debit': Decimal('0'),
                 'credit': Decimal('0')},
                {'compte': self.c5141, 'debit': Decimal('0'),
                 'credit': Decimal('1000')},
            ])
        self.assertEqual(ecriture.lignes.count(), 3)

    def test_contrainte_db_bloque_le_chemin_sql(self):
        """`QuerySet.update` contourne tout garde Python : la CheckConstraint
        est le vrai backstop."""
        ecriture = services.creer_ecriture(
            self.co, self.journal, date(2026, 6, 2), 'OD saine', [
                {'compte': self.c6111, 'debit': Decimal('50'),
                 'credit': Decimal('0')},
                {'compte': self.c5141, 'debit': Decimal('0'),
                 'credit': Decimal('50')},
            ])
        ligne = ecriture.lignes.first()
        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                LigneEcriture.objects.filter(pk=ligne.pk).update(
                    debit=Decimal('-1'))


class SerializerGardeLigneTests(TestCase):
    """Le chemin serializer (branché sur l'écran) suit la MÊME garde."""

    def setUp(self):
        from django.contrib.auth import get_user_model
        from rest_framework.test import APIClient
        from rest_framework_simplejwt.tokens import AccessToken

        User = get_user_model()
        self.co = make_company('aud188-api', 'AUD188 API')
        services.seed_plan_comptable(self.co)
        services.seed_journaux(self.co)
        self.journal = services._journal(
            self.co, Journal.Type.OPERATIONS_DIVERSES)
        self.c6111 = services.get_compte(self.co, '6111')
        self.c5141 = services.get_compte(self.co, '5141')
        self.user = User.objects.create_user(
            username='aud188-admin', password='x', company=self.co,
            role_legacy='admin')
        self.api = APIClient()
        self.api.credentials(
            HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(self.user)}')

    def _post(self, lignes):
        return self.api.post(
            '/api/django/compta/ecritures/',
            {'journal': self.journal.id, 'date_ecriture': '2026-06-01',
             'libelle': 'OD API', 'lignes': lignes},
            format='json')

    def test_serializer_refuse_montant_negatif(self):
        resp = self._post([
            {'compte': self.c6111.id, 'debit': '-100', 'credit': '0'},
            {'compte': self.c5141.id, 'debit': '0', 'credit': '-100'},
        ])
        self.assertEqual(resp.status_code, 400, resp.data)
        self.assertEqual(
            EcritureComptable.objects.filter(company=self.co).count(), 0)

    def test_serializer_refuse_debit_et_credit(self):
        resp = self._post([
            {'compte': self.c6111.id, 'debit': '100', 'credit': '100'},
            {'compte': self.c5141.id, 'debit': '50', 'credit': '50'},
        ])
        self.assertEqual(resp.status_code, 400, resp.data)
        self.assertEqual(
            EcritureComptable.objects.filter(company=self.co).count(), 0)

    def test_serializer_accepte_une_ecriture_saine(self):
        resp = self._post([
            {'compte': self.c6111.id, 'debit': '100', 'credit': '0'},
            {'compte': self.c5141.id, 'debit': '0', 'credit': '100'},
        ])
        self.assertEqual(resp.status_code, 201, resp.data)


class ContraintesArgentFacturationTests(TestCase):
    """Les documents d'argent portent enfin un backstop DB."""

    def setUp(self):
        self.co = make_company('aud188-fac', 'AUD188 Facturation')
        self.client_obj = Client.objects.create(
            company=self.co, nom='Client', prenom='AUD188',
            email='aud188@example.com', telephone='+212600000188')
        self.facture = Facture.objects.create(
            company=self.co, reference='FAC-AUD188-0001',
            client=self.client_obj, statut=Facture.Statut.EMISE,
            taux_tva=Decimal('20.00'))

    def test_avoir_montant_ttc_negatif_refuse_en_base(self):
        avoir = Avoir.objects.create(
            company=self.co, reference='AV-AUD188-0001',
            facture=self.facture, client=self.client_obj,
            montant_ht=Decimal('1000'), montant_tva=Decimal('200'),
            montant_ttc=Decimal('1200'))
        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                Avoir.objects.filter(pk=avoir.pk).update(
                    montant_ttc=Decimal('-500'))
        avoir.refresh_from_db()
        self.assertEqual(avoir.montant_ttc, Decimal('1200'))

    def test_avoir_remise_hors_bornes_refusee(self):
        avoir = Avoir.objects.create(
            company=self.co, reference='AV-AUD188-0002',
            facture=self.facture, client=self.client_obj)
        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                Avoir.objects.filter(pk=avoir.pk).update(
                    remise_globale=Decimal('150'))

    def test_paiement_montant_negatif_refuse(self):
        paiement = Paiement.objects.create(
            company=self.co, facture=self.facture,
            montant=Decimal('100'), date_paiement=date(2026, 6, 1),
            mode=Paiement.Mode.VIREMENT)
        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                Paiement.objects.filter(pk=paiement.pk).update(
                    montant=Decimal('-1'))

    def test_ligne_facture_prix_negatif_refuse(self):
        ligne = LigneFacture.objects.create(
            facture=self.facture, designation='Onduleur',
            quantite=Decimal('1'), prix_unitaire=Decimal('1000'),
            taux_tva=Decimal('20.00'))
        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                LigneFacture.objects.filter(pk=ligne.pk).update(
                    prix_unitaire=Decimal('-10'))

    def test_documents_valides_inchanges(self):
        """Non-régression : un avoir et une facture corrects restent créables."""
        avoir = Avoir.objects.create(
            company=self.co, reference='AV-AUD188-0003',
            facture=self.facture, client=self.client_obj,
            remise_globale=Decimal('15'),
            montant_ht=Decimal('17000'), montant_tva=Decimal('3400'),
            montant_ttc=Decimal('20400'))
        self.assertEqual(avoir.montant_ttc, Decimal('20400'))
        # Les montants figés NULL (avoir à lignes) restent valides.
        sans_montants = Avoir.objects.create(
            company=self.co, reference='AV-AUD188-0004',
            facture=self.facture, client=self.client_obj)
        self.assertIsNone(sans_montants.montant_ttc)


class RegistreInvariantsTests(TestCase):
    """Le registre `docs/db-invariants-gap.md` couvre enfin son périmètre."""

    def test_registre_liste_avoir_ligneavoir_et_boncommande(self):
        from pathlib import Path

        # .../backend/django_core/apps/compta/tests/<fichier> → racine du dépôt.
        racine = Path(__file__).resolve().parents[5]
        doc = (racine / 'docs' / 'db-invariants-gap.md').read_text(
            encoding='utf-8')
        for modele in ('`Avoir`', '`LigneAvoir`', '`BonCommande`'):
            self.assertIn(modele, doc)
