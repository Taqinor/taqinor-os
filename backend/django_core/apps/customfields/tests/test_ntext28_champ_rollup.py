"""NTEXT28 — champ ROLLUP (agrégat d'objets liés).

Un champ ``ROLLUP`` (``rollup_config={'objet_lie', 'cle_liaison', 'agg',
'champ'}``) se calcule à la LECTURE — il agrège les ``CustomRecord`` liés via
``core.pivot._aggregate`` — sans jamais persister le résultat. Critère
explicite : « total interventions » sur une fiche devis somme les montants
des enregistrements custom liés (``cle_liaison='devis_id'``) sans les
persister.
"""
from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from authentication.models import Company

from apps.customfields.models import CustomFieldDef, CustomObjectDef, CustomRecord
from apps.customfields.services import (
    calculer_champs_rollup, evaluer_champ_rollup,
)

User = get_user_model()


class EvaluerChampRollupTests(TestCase):
    """Le critère explicite : total interventions = somme des montants liés
    à un devis, calculé sans écrire en base."""

    def setUp(self):
        self.company = Company.objects.create(nom='NTEXT28 Co')
        self.objet = CustomObjectDef.objects.create(
            company=self.company, code='interventions', libelle='Interventions')
        self.devis_id = 42
        CustomRecord.objects.create(
            company=self.company, objet=self.objet,
            data={'devis_id': self.devis_id, 'montant': 500})
        CustomRecord.objects.create(
            company=self.company, objet=self.objet,
            data={'devis_id': self.devis_id, 'montant': 300})
        # Un enregistrement d'un AUTRE devis ne doit jamais compter.
        CustomRecord.objects.create(
            company=self.company, objet=self.objet,
            data={'devis_id': 999, 'montant': 10000})

    def test_total_interventions_somme_les_montants_lies(self):
        champ = CustomFieldDef.objects.create(
            company=self.company, module='devis', code='total_interventions',
            libelle='Total interventions', type=CustomFieldDef.FieldType.ROLLUP,
            rollup_config={'objet_lie': 'interventions',
                           'cle_liaison': 'devis_id', 'agg': 'sum',
                           'champ': 'montant'})
        valeur = evaluer_champ_rollup(champ, self.company, self.devis_id)
        self.assertEqual(valeur, 800)
        # Rien n'a été écrit en base : la config reste EXACTEMENT celle
        # posée à la création (aucun champ de résultat n'a été ajouté).
        champ.refresh_from_db()
        self.assertEqual(champ.rollup_config, {
            'objet_lie': 'interventions', 'cle_liaison': 'devis_id',
            'agg': 'sum', 'champ': 'montant'})

    def test_agregat_count(self):
        champ = CustomFieldDef.objects.create(
            company=self.company, module='devis', code='nb_interventions',
            libelle='Nb interventions', type=CustomFieldDef.FieldType.ROLLUP,
            rollup_config={'objet_lie': 'interventions',
                           'cle_liaison': 'devis_id', 'agg': 'count'})
        self.assertEqual(
            evaluer_champ_rollup(champ, self.company, self.devis_id), 2)

    def test_objet_lie_introuvable_renvoie_none(self):
        champ = CustomFieldDef.objects.create(
            company=self.company, module='devis', code='x',
            libelle='X', type=CustomFieldDef.FieldType.ROLLUP,
            rollup_config={'objet_lie': 'inconnu',
                           'cle_liaison': 'devis_id', 'agg': 'sum',
                           'champ': 'montant'})
        self.assertIsNone(
            evaluer_champ_rollup(champ, self.company, self.devis_id))

    def test_config_incomplete_renvoie_none(self):
        champ = CustomFieldDef.objects.create(
            company=self.company, module='devis', code='y',
            libelle='Y', type=CustomFieldDef.FieldType.ROLLUP,
            rollup_config={})
        self.assertIsNone(
            evaluer_champ_rollup(champ, self.company, self.devis_id))

    def test_isolation_societe(self):
        autre_company = Company.objects.create(nom='NTEXT28 Autre Co')
        champ = CustomFieldDef.objects.create(
            company=self.company, module='devis', code='total_interventions',
            libelle='Total interventions', type=CustomFieldDef.FieldType.ROLLUP,
            rollup_config={'objet_lie': 'interventions',
                           'cle_liaison': 'devis_id', 'agg': 'sum',
                           'champ': 'montant'})
        self.assertEqual(
            evaluer_champ_rollup(champ, autre_company, self.devis_id), None)


class CalculerChampsRollupTests(TestCase):
    def test_calcule_tous_les_champs_rollup_du_module(self):
        company = Company.objects.create(nom='NTEXT28 Bulk Co')
        objet = CustomObjectDef.objects.create(
            company=company, code='interventions', libelle='Interventions')
        CustomRecord.objects.create(
            company=company, objet=objet, data={'devis_id': 7, 'montant': 50})
        CustomFieldDef.objects.create(
            company=company, module='devis', code='total_interventions',
            libelle='Total interventions', type=CustomFieldDef.FieldType.ROLLUP,
            rollup_config={'objet_lie': 'interventions',
                           'cle_liaison': 'devis_id', 'agg': 'sum',
                           'champ': 'montant'})
        out = calculer_champs_rollup('devis', company, 7)
        self.assertEqual(out, {'total_interventions': 50})


class RollupSurObjetCustomLieTests(TestCase):
    """Bout en bout via CustomRecordSerializer : un champ ROLLUP sur un
    objet personnalisé se calcule aussi en lecture, jamais persisté."""

    def setUp(self):
        self.company = Company.objects.create(nom='NTEXT28 Objet Co')
        self.admin = User.objects.create_user(
            username='ntext28_admin', password='x', role_legacy='admin',
            company=self.company)
        self.api = APIClient()
        self.api.credentials(
            HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(self.admin)}')
        self.chantier = CustomObjectDef.objects.create(
            company=self.company, code='chantier', libelle='Chantier')
        self.visite = CustomObjectDef.objects.create(
            company=self.company, code='visites', libelle='Visites')
        self.chantier_record = CustomRecord.objects.create(
            company=self.company, objet=self.chantier, data={})
        CustomRecord.objects.create(
            company=self.company, objet=self.visite,
            data={'chantier_id': self.chantier_record.pk, 'duree_h': 3})
        CustomRecord.objects.create(
            company=self.company, objet=self.visite,
            data={'chantier_id': self.chantier_record.pk, 'duree_h': 2})
        CustomFieldDef.objects.create(
            company=self.company, module=self.chantier.field_module,
            code='total_heures', libelle='Total heures',
            type=CustomFieldDef.FieldType.ROLLUP,
            rollup_config={'objet_lie': 'visites',
                           'cle_liaison': 'chantier_id', 'agg': 'sum',
                           'champ': 'duree_h'})

    def test_rollup_visible_en_lecture(self):
        res = self.api.get(
            f'/api/django/custom-fields/custom-objects/chantier/records/'
            f'{self.chantier_record.pk}/')
        self.assertEqual(res.status_code, 200, res.data)
        self.assertEqual(res.data['data']['total_heures'], 5)

    def test_rollup_jamais_persiste_meme_si_soumis(self):
        res = self.api.patch(
            f'/api/django/custom-fields/custom-objects/chantier/records/'
            f'{self.chantier_record.pk}/',
            {'data': {'total_heures': 999}}, format='json')
        self.assertEqual(res.status_code, 200, res.data)
        self.chantier_record.refresh_from_db()
        self.assertNotIn('total_heures', self.chantier_record.data)
        self.assertEqual(res.data['data']['total_heures'], 5)
