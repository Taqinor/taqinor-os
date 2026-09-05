"""AUD820 — deux trous du partage niveau enregistrement (`core.sharing`).

1. `share_object` ne portait AUCUNE contrainte d'unicité en base : deux
   requêtes de partage CONCURRENTES sur le même (objet, principal) passaient
   toutes deux le SELECT de l'`update_or_create` et créaient DEUX lignes.
   Révoquer « le » partage en laissait alors une active — un accès fantôme
   qu'aucun écran ne montre.
2. `PrincipalType` déclarait USER/ROLE/**TEAM**, mais `_principals_for` ne
   construisait que `('user', …)` / `('role', …)` : une règle
   `principal_type='team'` était créée, affichée… et ne matchait jamais dans
   `_rules_qs`. Le partage d'équipe « ne marchait pas », en silence.

Test ROUGE d'abord — sur l'arbre d'avant AUD820 :
  * `SharingRule.objects.create(...)` deux fois avec le MÊME tuple réussissait
    (aucune IntegrityError) ;
  * `share_object(..., principal_type='team', principal_id=<superviseur>)` puis
    `visible_ids(<membre de l'équipe>)` renvoyait un ensemble VIDE.
"""
from django.db import IntegrityError, transaction
from django.test import TestCase

from core.sharing import (
    SharingRule, share_object, team_principal_ids, visible_ids,
)
from testkit.factories import ClientFactory, CompanyFactory, UserFactory


class UniciteDuPartageTests(TestCase):
    def setUp(self):
        self.company = CompanyFactory()
        self.beneficiaire = UserFactory(
            company=self.company, username='aud820-benef')
        self.obj = ClientFactory(company=self.company)

    def _cle(self):
        from django.contrib.contenttypes.models import ContentType
        return {
            'company': self.company,
            'content_type': ContentType.objects.get_for_model(type(self.obj)),
            'object_id': str(self.obj.pk),
            'principal_type': 'user',
            'principal_id': str(self.beneficiaire.pk),
        }

    def test_contrainte_db_interdit_le_doublon(self):
        SharingRule.objects.create(niveau='lecture', **self._cle())
        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                SharingRule.objects.create(niveau='ecriture', **self._cle())

    def test_la_contrainte_est_declaree_sur_le_modele(self):
        noms = {c.name for c in SharingRule._meta.constraints}
        self.assertIn('core_sharingrule_unique_principal', noms)

    def test_share_object_reste_idempotent(self):
        share_object(self.obj, principal_type='user',
                     principal_id=self.beneficiaire.pk, niveau='lecture')
        regle = share_object(self.obj, principal_type='user',
                             principal_id=self.beneficiaire.pk,
                             niveau='ecriture')
        self.assertEqual(SharingRule.objects.count(), 1)
        self.assertEqual(regle.niveau, 'ecriture')

    def test_share_object_rattrape_la_course_perdue(self):
        """La ligne créée « par l'autre requête » est mise à jour, pas dupliquée."""
        SharingRule.objects.create(niveau='lecture', **self._cle())
        regle = share_object(self.obj, principal_type='user',
                             principal_id=self.beneficiaire.pk,
                             niveau='ecriture')
        self.assertEqual(SharingRule.objects.count(), 1)
        self.assertEqual(regle.niveau, 'ecriture')

    def test_deux_principaux_differents_restent_possibles(self):
        autre = UserFactory(company=self.company, username='aud820-autre')
        share_object(self.obj, principal_type='user',
                     principal_id=self.beneficiaire.pk)
        share_object(self.obj, principal_type='user', principal_id=autre.pk)
        self.assertEqual(SharingRule.objects.count(), 2)


class PartageEquipeTests(TestCase):
    def setUp(self):
        self.company = CompanyFactory()
        self.chef = UserFactory(company=self.company, username='aud820-chef')
        self.membre = UserFactory(
            company=self.company, username='aud820-membre',
            supervisor=self.chef)
        self.coequipier = UserFactory(
            company=self.company, username='aud820-coequipier',
            supervisor=self.chef)
        self.etranger = UserFactory(
            company=self.company, username='aud820-etranger')
        self.obj = ClientFactory(company=self.company)

    def _partager_a_lequipe(self, niveau='lecture'):
        return share_object(self.obj, principal_type='team',
                            principal_id=self.chef.pk, niveau=niveau)

    def test_le_membre_de_lequipe_obtient_lacces(self):
        self._partager_a_lequipe()
        self.assertIn(
            str(self.obj.pk), visible_ids(self.membre, type(self.obj)))
        self.assertIn(
            str(self.obj.pk), visible_ids(self.coequipier, type(self.obj)))

    def test_le_chef_dequipe_obtient_lacces(self):
        self._partager_a_lequipe()
        self.assertIn(
            str(self.obj.pk), visible_ids(self.chef, type(self.obj)))

    def test_un_utilisateur_hors_equipe_ne_voit_rien(self):
        self._partager_a_lequipe()
        self.assertEqual(
            visible_ids(self.etranger, type(self.obj)), set())

    def test_le_niveau_ecriture_est_respecte(self):
        self._partager_a_lequipe(niveau='lecture')
        self.assertEqual(
            visible_ids(self.membre, type(self.obj), write=True), set())

    def test_team_principal_ids_resout_soi_et_son_superieur(self):
        self.assertEqual(
            team_principal_ids(self.membre),
            {str(self.membre.pk), str(self.chef.pk)})
        self.assertEqual(
            team_principal_ids(self.etranger), {str(self.etranger.pk)})

    def test_partage_equipe_jamais_cross_tenant(self):
        autre_company = CompanyFactory()
        intrus = UserFactory(
            company=autre_company, username='aud820-intrus',
            supervisor=None)
        self._partager_a_lequipe()
        self.assertEqual(visible_ids(intrus, type(self.obj)), set())
