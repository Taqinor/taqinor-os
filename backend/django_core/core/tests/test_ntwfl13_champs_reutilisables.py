"""Tests NTWFL13 — bibliothèque de champs de formulaire réutilisables.

Couvre l'acceptance criteria : un champ réutilisable modifié met à jour
son libellé PARTOUT où il est référencé, sans dupliquer sa définition.
"""
from django.test import TestCase

from authentication.models import Company
from core.models import FormulaireChampReutilisable, FormulaireDefinition
from core.selectors import resoudre_champs_formulaire
from core.serializers import FormulaireDefinitionSerializer


def make_company(slug, nom):
    company, _ = Company.objects.get_or_create(slug=slug, defaults={'nom': nom})
    return company


class ResoudreChampsFormulaireTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.company = make_company('ntwfl13', 'NTWFL13')

    def test_champ_reutilisable_modifie_se_repercute_partout(self):
        champ = FormulaireChampReutilisable.objects.create(
            company=self.company, nom='Motif de rejet', type='texte')
        schema_a = [{'ref': champ.id, 'requis': True}]
        schema_b = [{'ref': champ.id, 'requis': False}]

        resolu_a = resoudre_champs_formulaire(schema_a, self.company)
        resolu_b = resoudre_champs_formulaire(schema_b, self.company)
        self.assertEqual(resolu_a[0]['nom'], 'Motif de rejet')
        self.assertEqual(resolu_b[0]['nom'], 'Motif de rejet')
        # L'attribut d'USAGE (requis) reste propre à chaque formulaire.
        self.assertTrue(resolu_a[0]['requis'])
        self.assertFalse(resolu_b[0]['requis'])

        champ.nom = 'Motif de refus (renommé)'
        champ.save(update_fields=['nom'])

        # AUCUNE écriture sur schema_a/schema_b : la résolution suit le
        # champ source EN DIRECT, sans dupliquer sa définition nulle part.
        resolu_a_apres = resoudre_champs_formulaire(schema_a, self.company)
        resolu_b_apres = resoudre_champs_formulaire(schema_b, self.company)
        self.assertEqual(resolu_a_apres[0]['nom'], 'Motif de refus (renommé)')
        self.assertEqual(resolu_b_apres[0]['nom'], 'Motif de refus (renommé)')

    def test_champ_inline_sans_ref_inchange(self):
        schema = [{'nom': 'Commentaire libre', 'type': 'texte'}]
        resolu = resoudre_champs_formulaire(schema, self.company)
        self.assertEqual(resolu, schema)

    def test_ref_introuvable_ne_leve_pas(self):
        schema = [{'ref': 99999, 'requis': True}]
        resolu = resoudre_champs_formulaire(schema, self.company)
        self.assertEqual(resolu, schema)  # renvoyé tel quel, jamais d'exception

    def test_isolation_tenant(self):
        autre = make_company('ntwfl13-b', 'NTWFL13 B')
        champ_autre = FormulaireChampReutilisable.objects.create(
            company=autre, nom='Champ autre société', type='texte')
        schema = [{'ref': champ_autre.id, 'requis': True}]
        # La société courante ne doit jamais résoudre un champ d'une AUTRE
        # société — renvoyé tel quel (pas de fuite cross-tenant).
        resolu = resoudre_champs_formulaire(schema, self.company)
        self.assertNotIn('nom', resolu[0])


class FormulaireDefinitionSerializerTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.company = make_company('ntwfl13-c', 'NTWFL13 C')

    def test_representation_developpe_le_champ_reutilisable(self):
        champ = FormulaireChampReutilisable.objects.create(
            company=self.company, nom='Motif', type='texte')
        formulaire = FormulaireDefinition.objects.create(
            company=self.company, code='f1', nom='F1',
            schema=[{'ref': champ.id, 'requis': True}])

        data = FormulaireDefinitionSerializer(formulaire).data
        self.assertEqual(data['schema'][0]['nom'], 'Motif')

        champ.nom = 'Motif (renommé)'
        champ.save(update_fields=['nom'])
        data_apres = FormulaireDefinitionSerializer(formulaire).data
        self.assertEqual(data_apres['schema'][0]['nom'], 'Motif (renommé)')
