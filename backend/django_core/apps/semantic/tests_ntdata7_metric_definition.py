"""NTDATA7 — modèle `MetricDefinition` (couche sémantique).

Couvre :
  * multi-tenant : la clé est unique PAR SOCIÉTÉ (deux sociétés peuvent avoir
    chacune leur `marge_brute`) ;
  * la validation structurelle de `mesure` (simple et formule), en FRANÇAIS et
    en nommant le champ fautif ;
  * `est_formule`.
"""
from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction
from django.test import TestCase

from apps.semantic.models import MetricDefinition
from authentication.models import Company


class MetricDefinitionTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.company = Company.objects.create(nom='NTDATA7 SA',
                                             slug='ntdata7-sa')
        cls.autre = Company.objects.create(nom='NTDATA7 Autre',
                                           slug='ntdata7-autre')

    def _metrique(self, company=None, **kw):
        defaults = dict(
            company=company or self.company, cle='ca_ttc',
            libelle='Chiffre d\'affaires TTC', dataset='ventes_factures',
            mesure={'field': 'montant_ttc', 'agg': 'sum'},
            unite=MetricDefinition.Unite.MAD)
        defaults.update(kw)
        return MetricDefinition.objects.create(**defaults)

    def test_cle_unique_par_societe(self):
        self._metrique()
        # Même clé dans une AUTRE société : autorisé.
        self._metrique(company=self.autre)
        # Même clé dans la MÊME société : refusé.
        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                self._metrique()

    def test_mesure_simple_valide(self):
        metrique = self._metrique()
        metrique.full_clean()
        self.assertFalse(metrique.est_formule)

    def test_mesure_formule_valide(self):
        metrique = self._metrique(
            cle='panier_moyen',
            mesure={
                'formula': 'ca / nb',
                'aggregates': [
                    {'alias': 'ca', 'fn': 'sum', 'field': 'montant_ttc'},
                    {'alias': 'nb', 'fn': 'count', 'field': 'id'},
                ],
            })
        metrique.full_clean()
        self.assertTrue(metrique.est_formule)

    def test_agregation_inconnue_refusee_en_nommant_le_champ(self):
        metrique = MetricDefinition(
            company=self.company, cle='x', libelle='X',
            dataset='ventes_factures',
            mesure={'field': 'montant_ttc', 'agg': 'mediane'})
        with self.assertRaises(ValidationError) as ctx:
            metrique.clean()
        self.assertIn('mesure', ctx.exception.message_dict)
        self.assertIn('mediane', str(ctx.exception.message_dict['mesure']))

    def test_formule_sans_aggregates_refusee(self):
        metrique = MetricDefinition(
            company=self.company, cle='y', libelle='Y',
            dataset='ventes_factures', mesure={'formula': 'a / b'})
        with self.assertRaises(ValidationError) as ctx:
            metrique.clean()
        self.assertIn('aggregates', str(ctx.exception.message_dict['mesure']))

    def test_dataset_obligatoire(self):
        metrique = MetricDefinition(
            company=self.company, cle='z', libelle='Z', dataset='',
            mesure={'field': 'id', 'agg': 'count'})
        with self.assertRaises(ValidationError) as ctx:
            metrique.clean()
        self.assertIn('dataset', ctx.exception.message_dict)

    def test_count_sans_field_accepte(self):
        metrique = self._metrique(cle='nb_factures',
                                  mesure={'agg': 'count'},
                                  unite=MetricDefinition.Unite.NOMBRE)
        metrique.clean()  # ne lève pas
