"""ARC24 — Référentiel des conditions de paiement (parametres.ConditionPaiement).

Vérifie :
  - le master + le libellé FR canonique d'un triplet ;
  - le DÉFAUT branché à la création d'une facture (le libellé du référentiel
    alimente le texte libre vide ; un texte fourni reste MAÎTRE) ;
  - l'immutabilité (règle #4) : le texte libre d'une facture existante n'est
    JAMAIS réécrit ;
  - le backfill des triplets DISTINCTS des fournisseurs en entrées du
    référentiel + la FK miroir posée, le tout idempotent ;
  - les champs numériques du fournisseur restent MAÎTRES (miroir seulement) ;
  - le référentiel est borné à la société.

Run:
    docker compose exec django_core python manage.py test \
        apps.stock.test_arc24_conditions_paiement -v 2
"""
from decimal import Decimal

from django.core.management import call_command
from django.test import TestCase

from apps.parametres.models import ConditionPaiement
from apps.stock.models import Fournisseur


def _make_company(slug='arc24-co', nom='ARC24 Co'):
    from authentication.models import Company
    return Company.objects.get_or_create(slug=slug, defaults={'nom': nom})[0]


class TestArc24LibelleCanonique(TestCase):
    def test_libelle_pour_comptant(self):
        self.assertEqual(
            ConditionPaiement.libelle_pour(0, False, 0), 'Comptant')

    def test_libelle_pour_delai_fin_de_mois(self):
        self.assertEqual(
            ConditionPaiement.libelle_pour(60, True, 0),
            '60 jours fin de mois')

    def test_libelle_pour_escompte(self):
        lib = ConditionPaiement.libelle_pour(30, False, Decimal('2'))
        self.assertEqual(lib, '30 jours — escompte 2 %')


class TestArc24FactureDefault(TestCase):
    def setUp(self):
        self.company = _make_company()
        from apps.crm.models import Client
        self.client_obj = Client.objects.create(
            company=self.company, nom='C', prenom='D', email='c@d.ma')
        self.cond = ConditionPaiement.objects.create(
            company=self.company, libelle='30 jours net', delai_jours=30)

    def _facture(self, **kw):
        from apps.ventes.models import Facture
        return Facture.objects.create(
            company=self.company, reference=kw.pop('reference', 'FAC-ARC24'),
            client=self.client_obj, statut=Facture.Statut.EMISE, **kw)

    def test_ref_label_fills_empty_free_text_on_create(self):
        f = self._facture(condition_paiement_ref=self.cond)
        self.assertEqual(f.conditions_paiement, '30 jours net')

    def test_explicit_free_text_wins_over_ref(self):
        f = self._facture(
            condition_paiement_ref=self.cond,
            conditions_paiement='Paiement à 45 jours (accord spécial)')
        self.assertEqual(
            f.conditions_paiement, 'Paiement à 45 jours (accord spécial)')

    def test_no_ref_preserves_historical_empty(self):
        f = self._facture()
        self.assertEqual(f.conditions_paiement, '')

    def test_existing_facture_free_text_never_rewritten(self):
        # Facture émise sans texte ni ref, puis on relie une ref et on
        # ré-enregistre : le texte NE se remplit PAS (défaut à la création
        # uniquement — immutabilité règle #4).
        f = self._facture()
        f.condition_paiement_ref = self.cond
        f.save(update_fields=['condition_paiement_ref'])
        f.refresh_from_db()
        self.assertEqual(f.conditions_paiement, '')


class TestArc24BackfillFournisseur(TestCase):
    def setUp(self):
        self.company = _make_company(slug='arc24-bf', nom='ARC24 BF')
        # Trois fournisseurs, deux triplets DISTINCTS (A/B identiques, C autre).
        self.fa = Fournisseur.objects.create(
            company=self.company, nom='A',
            delai_paiement_jours=30, fin_de_mois=False,
            escompte_pct=Decimal('0'))
        self.fb = Fournisseur.objects.create(
            company=self.company, nom='B',
            delai_paiement_jours=30, fin_de_mois=False,
            escompte_pct=Decimal('0'))
        self.fc = Fournisseur.objects.create(
            company=self.company, nom='C',
            delai_paiement_jours=60, fin_de_mois=True,
            escompte_pct=Decimal('2'))

    def test_backfill_creates_distinct_conditions_and_links(self):
        call_command('backfill_conditions_paiement',
                     company_slug=self.company.slug)
        # Deux triplets distincts → deux conditions.
        self.assertEqual(
            ConditionPaiement.objects.filter(company=self.company).count(), 2)
        self.fa.refresh_from_db()
        self.fb.refresh_from_db()
        self.fc.refresh_from_db()
        # A et B partagent la MÊME condition ; C en a une autre.
        self.assertIsNotNone(self.fa.condition_paiement_ref_id)
        self.assertEqual(self.fa.condition_paiement_ref_id,
                         self.fb.condition_paiement_ref_id)
        self.assertNotEqual(self.fa.condition_paiement_ref_id,
                            self.fc.condition_paiement_ref_id)

    def test_numeric_fields_stay_master(self):
        call_command('backfill_conditions_paiement',
                     company_slug=self.company.slug)
        self.fc.refresh_from_db()
        # Les champs numériques du fournisseur sont INCHANGÉS (miroir seulement).
        self.assertEqual(self.fc.delai_paiement_jours, 60)
        self.assertTrue(self.fc.fin_de_mois)
        self.assertEqual(self.fc.escompte_pct, Decimal('2'))
        # La condition référentielle reflète bien le triplet.
        cond = self.fc.condition_paiement_ref
        self.assertEqual(cond.delai_jours, 60)
        self.assertTrue(cond.fin_de_mois)
        self.assertEqual(cond.escompte_pct, Decimal('2'))

    def test_backfill_is_idempotent(self):
        call_command('backfill_conditions_paiement',
                     company_slug=self.company.slug)
        avant = ConditionPaiement.objects.filter(company=self.company).count()
        call_command('backfill_conditions_paiement',
                     company_slug=self.company.slug)
        apres = ConditionPaiement.objects.filter(company=self.company).count()
        self.assertEqual(avant, apres)  # aucun doublon au second passage

    def test_referential_is_company_scoped(self):
        other = _make_company(slug='arc24-other', nom='Autre')
        call_command('backfill_conditions_paiement',
                     company_slug=self.company.slug)
        # L'autre société n'a AUCUNE condition (backfill borné par slug).
        self.assertEqual(
            ConditionPaiement.objects.filter(company=other).count(), 0)
