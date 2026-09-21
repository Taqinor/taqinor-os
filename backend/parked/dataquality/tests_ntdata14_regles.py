"""NTDATA14 — moteur de règles de validation d'entreprise.

Couvre :
  * multi-tenant (la règle porte une société) ;
  * la validation du paramétrage, en nommant le champ fautif ;
  * la traduction vers `core.rules` (non_vide / plage) — jamais une seconde
    implémentation ;
  * les cinq types de règle sur une population de lignes ;
  * une valeur VIDE n'est jamais une faute de format/plage/référentiel ;
  * le critère d'acceptation : « ICE client au bon format » évalue une
    population de clients RÉELS (dataset `crm_clients`).
"""
from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.test import TestCase

from apps.crm.bi_datasets import CLIENTS_DATASET
from apps.crm.models import Client
from apps.dataquality import services
from apps.dataquality.models import RegleQualite
from authentication.models import Company
from core import data_explorer

User = get_user_model()

#: ICE marocain : 15 chiffres.
MOTIF_ICE = r'^[0-9]{15}$'


class RegleQualiteModeleTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.company = Company.objects.create(nom='NTDATA14 SA',
                                             slug='ntdata14-sa')

    def _regle(self, **kw):
        defaults = dict(company=self.company, entite=CLIENTS_DATASET,
                        champ='ice', type_regle=RegleQualite.TypeRegle.FORMAT,
                        parametres={'motif': MOTIF_ICE})
        defaults.update(kw)
        return RegleQualite(**defaults)

    def test_format_sans_motif_refuse(self):
        with self.assertRaises(ValidationError) as ctx:
            self._regle(parametres={}).clean()
        self.assertIn('parametres', ctx.exception.message_dict)

    def test_motif_invalide_refuse(self):
        with self.assertRaises(ValidationError) as ctx:
            self._regle(parametres={'motif': '([a-'}).clean()
        self.assertIn('parametres', ctx.exception.message_dict)

    def test_plage_sans_borne_refusee(self):
        with self.assertRaises(ValidationError) as ctx:
            self._regle(type_regle=RegleQualite.TypeRegle.PLAGE,
                        parametres={}).clean()
        self.assertIn('parametres', ctx.exception.message_dict)

    def test_referentiel_sans_valeurs_refuse(self):
        with self.assertRaises(ValidationError) as ctx:
            self._regle(type_regle=RegleQualite.TypeRegle.REFERENCE_VALIDE,
                        parametres={}).clean()
        self.assertIn('parametres', ctx.exception.message_dict)

    def test_traduction_vers_core_rules(self):
        non_vide = self._regle(type_regle=RegleQualite.TypeRegle.NON_VIDE,
                               parametres={})
        self.assertEqual(non_vide.condition_core_rules['operator'], 'exists')
        plage = self._regle(champ='quantite_stock',
                            type_regle=RegleQualite.TypeRegle.PLAGE,
                            parametres={'min': 0, 'max': 100})
        arbre = plage.condition_core_rules
        self.assertEqual(arbre['op'], 'and')
        self.assertEqual([c['operator'] for c in arbre['conditions']],
                         ['gte', 'lte'])
        # Types inexprimables dans core.rules : pas d'arbre, et c'est assumé.
        self.assertIsNone(self._regle().condition_core_rules)


class EvaluationTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.company = Company.objects.create(nom='NTDATA14 Eval',
                                             slug='ntdata14-eval')

    def _regle(self, **kw):
        defaults = dict(company=self.company, entite=CLIENTS_DATASET,
                        champ='ice', type_regle=RegleQualite.TypeRegle.FORMAT,
                        parametres={'motif': MOTIF_ICE})
        defaults.update(kw)
        return RegleQualite(**defaults)

    def test_format(self):
        regle = self._regle()
        lignes = [
            {'id': 1, 'ice': '001234567000089'},   # 15 chiffres — conforme
            {'id': 2, 'ice': 'ABC'},               # non conforme
            {'id': 3, 'ice': ''},                  # VIDE — pas une faute ici
            {'id': 4, 'ice': None},
        ]
        nb, fautives = services.violations(regle, lignes)
        self.assertEqual(nb, 4)
        self.assertEqual(fautives, [2])

    def test_non_vide(self):
        regle = self._regle(type_regle=RegleQualite.TypeRegle.NON_VIDE,
                            parametres={})
        lignes = [{'id': 1, 'ice': '1'}, {'id': 2, 'ice': '  '},
                  {'id': 3, 'ice': None}]
        _nb, fautives = services.violations(regle, lignes)
        self.assertEqual(fautives, [2, 3])

    def test_non_vide_accepte_zero(self):
        regle = self._regle(champ='quantite_stock',
                            type_regle=RegleQualite.TypeRegle.NON_VIDE,
                            parametres={})
        _nb, fautives = services.violations(
            regle, [{'id': 1, 'quantite_stock': 0}])
        self.assertEqual(fautives, [])

    def test_plage(self):
        regle = self._regle(champ='quantite_stock',
                            type_regle=RegleQualite.TypeRegle.PLAGE,
                            parametres={'min': 0, 'max': 10})
        lignes = [{'id': 1, 'quantite_stock': 5},
                  {'id': 2, 'quantite_stock': -1},
                  {'id': 3, 'quantite_stock': 50}]
        _nb, fautives = services.violations(regle, lignes)
        self.assertEqual(fautives, [2, 3])

    def test_unicite_remonte_tout_le_groupe(self):
        regle = self._regle(champ='telephone',
                            type_regle=RegleQualite.TypeRegle.UNICITE,
                            parametres={})
        lignes = [{'id': 1, 'telephone': '0600000000'},
                  {'id': 2, 'telephone': '0600000000'},
                  {'id': 3, 'telephone': '0611111111'},
                  {'id': 4, 'telephone': ''}]
        _nb, fautives = services.violations(regle, lignes)
        self.assertEqual(sorted(fautives), [1, 2])

    def test_reference_valide(self):
        regle = self._regle(champ='type',
                            type_regle=RegleQualite.TypeRegle.REFERENCE_VALIDE,
                            parametres={'valeurs': ['particulier',
                                                    'entreprise']})
        lignes = [{'id': 1, 'type': 'particulier'},
                  {'id': 2, 'type': 'association'}]
        _nb, fautives = services.violations(regle, lignes)
        self.assertEqual(fautives, [2])

    def test_taux_conformite_population_vide_est_none(self):
        self.assertIsNone(services.taux_conformite(0, 0))
        self.assertEqual(services.taux_conformite(4, 1), 75.0)


class IceSurPopulationReelleTests(TestCase):
    """Critère d'acceptation NTDATA14 : la règle « ICE client au bon format »
    évalue une population de CLIENTS réels, lus par le dataset `crm_clients`."""

    @classmethod
    def setUpTestData(cls):
        cls.company = Company.objects.create(nom='NTDATA14 ICE',
                                             slug='ntdata14-ice')
        cls.user = User.objects.create_user(
            username='ntdata14_u', password='x', company=cls.company)
        Client.objects.create(company=cls.company, nom='Bon ICE',
                              ice='001234567000089')
        Client.objects.create(company=cls.company, nom='Mauvais ICE',
                              ice='12')
        Client.objects.create(company=cls.company, nom='Sans ICE')

    def test_regle_ice_sur_les_clients(self):
        regle = RegleQualite.objects.create(
            company=self.company, libelle='ICE client au bon format',
            entite=CLIENTS_DATASET, champ='ice',
            type_regle=RegleQualite.TypeRegle.FORMAT,
            parametres={'motif': MOTIF_ICE},
            severite=RegleQualite.Severite.BLOQUANT)
        lignes = data_explorer.run_query(
            CLIENTS_DATASET, self.company, self.user,
            {'select': ['id', 'ice']})
        nb, fautives = services.violations(regle, lignes)
        self.assertEqual(nb, 3)
        self.assertEqual(len(fautives), 1)
        self.assertEqual(services.taux_conformite(nb, len(fautives)), 66.7)
