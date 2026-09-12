"""NTEXT1 — champ personnalisé CALCULÉ (type FORMULA).

La valeur n'est jamais saisie : elle se calcule à la LECTURE depuis les
autres champs custom de l'enregistrement (``core.formula.evaluer_formule``,
AST sûr — jamais ``eval``), jamais persistée dans ``custom_data``/``data``.
Une formule référençant ``prix_achat``/``marge`` (même garde que les prompts
IA, ``FORBIDDEN_PROMPT_PLACEHOLDERS``) est rejetée à la DÉFINITION.
"""
from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from authentication.models import Company

from apps.customfields.models import CustomFieldDef, CustomObjectDef, CustomRecord
from apps.customfields.services import (
    calculer_champs_formule, evaluer_champ_formule, valider_formule_definition,
)

User = get_user_model()

CHAMPS = '/api/django/custom-fields/definitions/'


def _auth(user):
    api = APIClient()
    api.credentials(HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(user)}')
    return api


class ValiderFormuleDefinitionTests(TestCase):
    """Validation à la DÉFINITION : formule sûre + jamais de placeholder
    interdit, même si un champ frère porte ce nom."""

    def test_formule_valide_contre_les_codes_freres(self):
        ok, erreur = valider_formule_definition(
            'quantite * prix_unitaire', ['quantite', 'prix_unitaire'])
        self.assertTrue(ok, erreur)
        self.assertEqual(erreur, '')

    def test_formule_referencant_prix_achat_rejetee(self):
        ok, erreur = valider_formule_definition(
            'prix_achat * 2', ['prix_achat'])
        self.assertFalse(ok)
        self.assertIn('prix_achat', erreur)

    def test_formule_referencant_marge_rejetee(self):
        ok, erreur = valider_formule_definition('marge + 1', ['marge'])
        self.assertFalse(ok)
        self.assertIn('marge', erreur)

    def test_formule_vide_rejetee(self):
        ok, erreur = valider_formule_definition('', [])
        self.assertFalse(ok)
        self.assertTrue(erreur)

    def test_formule_avec_import_rejetee(self):
        ok, erreur = valider_formule_definition(
            "__import__('os').system('ls')", [])
        self.assertFalse(ok)
        self.assertTrue(erreur)


class EvaluerChampFormuleTests(TestCase):
    """Calcul à la LECTURE : jamais persisté, jamais d'accès à prix_achat."""

    def setUp(self):
        self.company = Company.objects.create(nom='NTEXT1 Co')

    def test_total_ht_calcule_sans_ecrire_en_base(self):
        champ = CustomFieldDef.objects.create(
            company=self.company, module='devis', code='total_ht',
            libelle='Total HT', type=CustomFieldDef.FieldType.FORMULA,
            formule='quantite * prix_unitaire')
        valeur = evaluer_champ_formule(
            champ, {'quantite': 3, 'prix_unitaire': 100})
        self.assertEqual(valeur, 300)
        # Rien n'a été écrit — l'objet en base n'a pas de valeur stockée.
        champ.refresh_from_db()
        self.assertEqual(champ.formule, 'quantite * prix_unitaire')

    def test_contexte_ne_transmet_jamais_prix_achat(self):
        champ = CustomFieldDef.objects.create(
            company=self.company, module='devis', code='verifie_marge',
            libelle='Vérifie marge', type=CustomFieldDef.FieldType.FORMULA,
            # Une formule légitime qui ne référence pas prix_achat, mais le
            # contexte fourni en contient un — il doit être filtré, jamais lu.
            formule='quantite * 2')
        # Le contexte contient prix_achat : la garde le retire avant calcul.
        valeur = evaluer_champ_formule(
            champ, {'quantite': 5, 'prix_achat': 999999})
        self.assertEqual(valeur, 10)

    def test_formule_invalide_renvoie_none_sans_lever(self):
        champ = CustomFieldDef.objects.create(
            company=self.company, module='devis', code='casse',
            libelle='Casse', type=CustomFieldDef.FieldType.FORMULA,
            formule='inconnu + 1')
        self.assertIsNone(evaluer_champ_formule(champ, {'autre': 1}))


class CustomRecordFormulaReadOnlyTests(TestCase):
    """Bout en bout via l'objet personnalisé : la valeur calculée apparaît en
    LECTURE et n'est jamais persistée dans ``CustomRecord.data``."""

    def setUp(self):
        self.company = Company.objects.create(nom='NTEXT1 Objet Co')
        self.admin = User.objects.create_user(
            username='ntext1_admin', password='x', role_legacy='admin',
            company=self.company)
        self.api = _auth(self.admin)
        self.objet = CustomObjectDef.objects.create(
            company=self.company, code='intervention', libelle='Intervention')
        CustomFieldDef.objects.create(
            company=self.company, module=self.objet.field_module,
            code='quantite', libelle='Quantité', type='number')
        CustomFieldDef.objects.create(
            company=self.company, module=self.objet.field_module,
            code='prix_unitaire', libelle='Prix unitaire', type='number')
        CustomFieldDef.objects.create(
            company=self.company, module=self.objet.field_module,
            code='total_ht', libelle='Total HT',
            type=CustomFieldDef.FieldType.FORMULA,
            formule='quantite * prix_unitaire')

    def test_lecture_renvoie_la_valeur_calculee(self):
        record = CustomRecord.objects.create(
            company=self.company, objet=self.objet,
            data={'quantite': 4, 'prix_unitaire': 250})
        res = self.api.get(
            f'/api/django/custom-fields/custom-objects/intervention/records/'
            f'{record.pk}/')
        self.assertEqual(res.status_code, 200, res.data)
        self.assertEqual(res.data['data']['total_ht'], 1000)

    def test_valeur_soumise_pour_un_champ_calcule_est_ignoree(self):
        """Un total_ht envoyé par erreur à la création n'est jamais persisté :
        seule la valeur calculée compte."""
        res = self.api.post(
            '/api/django/custom-fields/custom-objects/intervention/records/',
            {'data': {'quantite': 2, 'prix_unitaire': 50,
                      'total_ht': 999999}},
            format='json')
        self.assertEqual(res.status_code, 201, res.data)
        record = CustomRecord.objects.get(pk=res.data['id'])
        self.assertNotIn('total_ht', record.data)
        self.assertEqual(record.data['quantite'], 2)
        self.assertEqual(res.data['data']['total_ht'], 100)

    def test_calculer_champs_formule_direct(self):
        out = calculer_champs_formule(
            self.objet.field_module, self.company,
            {'quantite': 10, 'prix_unitaire': 5})
        self.assertEqual(out, {'total_ht': 50})
