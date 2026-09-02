"""SOL2(a) — la NCR ne porte plus de clé étrangère vers `sante`.

`qhse` est GARDÉ dans l'édition solaire, `sante` en est PARQUÉ : une
ForeignKey `NonConformite.cycle_sterilisation → sante.CycleSterilisation`
empêchait `migrate` d'aboutir sur une base vierge sans `apps.sante`.

Le lien devient une RÉFÉRENCE NON CONTRAINTE sur la MÊME colonne
(`cycle_sterilisation_id`) : aucune donnée n'est perdue, aucun appelant ne
change (`services.creer_ncr_depuis_cycle_sterilisation`, les filtres
`cycle_sterilisation_id=…`).
"""
from django.core.exceptions import FieldDoesNotExist
from django.db import models
from django.test import TestCase

from apps.qhse.models import NonConformite


class NcrSansFkSanteTests(TestCase):
    def test_colonne_conservee_en_entier_non_contraint(self):
        champ = NonConformite._meta.get_field('cycle_sterilisation_id')
        self.assertIsInstance(champ, models.IntegerField)
        self.assertNotIsInstance(champ, models.ForeignKey)
        # MÊME colonne physique qu'avant (aucun drop, données conservées).
        self.assertEqual(champ.column, 'cycle_sterilisation_id')
        self.assertTrue(champ.null)
        self.assertTrue(champ.db_index)

    def test_ancienne_fk_absente(self):
        with self.assertRaises(FieldDoesNotExist):
            NonConformite._meta.get_field('cycle_sterilisation')

    def test_aucune_relation_vers_sante(self):
        vers_sante = [
            champ.name for champ in NonConformite._meta.get_fields()
            if getattr(champ, 'related_model', None) is not None
            and getattr(
                champ.related_model._meta, 'app_label', '') == 'sante'
        ]
        self.assertEqual(
            vers_sante, [],
            f'relations qhse → sante encore présentes : {vers_sante}')

    def test_migration_0057_ne_depend_plus_de_sante(self):
        import importlib

        module = importlib.import_module(
            'apps.qhse.migrations.0057_ntsan23_ncr_cycle_sterilisation')
        deps = [app for app, _nom in module.Migration.dependencies]
        self.assertNotIn(
            'sante', deps,
            'qhse/0057 dépend encore de sante : `migrate` échouerait sur une '
            'base vierge en édition solaire.')

    def test_creation_ncr_depuis_cycle_conserve_l_identifiant(self):
        from authentication.models import Company
        from apps.qhse.services import creer_ncr_depuis_cycle_sterilisation

        company = Company.objects.create(nom='ACME')
        ncr, cree = creer_ncr_depuis_cycle_sterilisation(
            company=company, cycle_id=4242, numero_cycle='CY-42',
            autoclave_ref='AUTO-1')
        self.assertTrue(cree)
        self.assertEqual(ncr.cycle_sterilisation_id, 4242)
        # Idempotent : ré-appeler renvoie la même NCR (comportement NTSAN23).
        meme, cree2 = creer_ncr_depuis_cycle_sterilisation(
            company=company, cycle_id=4242, numero_cycle='CY-42')
        self.assertFalse(cree2)
        self.assertEqual(meme.pk, ncr.pk)
