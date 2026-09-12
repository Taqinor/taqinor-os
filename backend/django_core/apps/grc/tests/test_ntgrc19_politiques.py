"""NTGRC19 — politiques internes versionnées.

Garanties : publier FIGE une version immuable et INCRÉMENTE le n° de version ;
une version publiée ne se réécrit ni ne se supprime ; tout reste scopé
société.
"""
from django.test import TestCase

from apps.grc.models import (
    PolitiqueInterne, PolitiqueVersion, PolitiqueVersionError,
)
from apps.grc.services import PublicationImpossible, publier_politique
from authentication.models import Company
from testkit.base import TenantAPITestCase


class PublicationTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.company = Company.objects.create(nom='NTGRC19 SA', slug='ntgrc19')

    def _politique(self, **kw):
        params = {'titre': 'Charte informatique', 'contenu': 'Texte v1'}
        params.update(kw)
        return PolitiqueInterne.objects.create(company=self.company, **params)

    def test_publier_fige_une_version_et_incremente(self):
        politique = self._politique()
        self.assertEqual(politique.version, 0)

        version = publier_politique(politique, auteur='dpo')
        politique.refresh_from_db()
        self.assertEqual(version.numero, 1)
        self.assertEqual(politique.version, 1)
        self.assertEqual(politique.statut, PolitiqueInterne.STATUT_PUBLIEE)
        self.assertIsNotNone(politique.date_publication)
        self.assertEqual(version.contenu, 'Texte v1')
        self.assertEqual(version.auteur, 'dpo')

    def test_la_version_figee_ne_suit_pas_les_edits_ulterieurs(self):
        politique = self._politique()
        version = publier_politique(politique)
        politique.contenu = 'Texte réécrit'
        politique.save()
        version.refresh_from_db()
        self.assertEqual(version.contenu, 'Texte v1')

    def test_republier_incremente_le_numero(self):
        politique = self._politique()
        publier_politique(politique)
        politique.contenu = 'Texte v2'
        politique.save()
        v2 = publier_politique(politique)
        politique.refresh_from_db()
        self.assertEqual(v2.numero, 2)
        self.assertEqual(politique.version, 2)
        self.assertEqual(politique.versions.count(), 2)

    def test_le_numero_ne_recule_pas_si_une_version_manque(self):
        """Plus-haut-numéro + 1, jamais count() + 1."""
        politique = self._politique()
        publier_politique(politique)
        politique.contenu = 'v2'
        politique.save()
        publier_politique(politique)
        PolitiqueVersion.objects.filter(
            politique=politique, numero=1).delete()
        politique.contenu = 'v3'
        politique.save()
        v3 = publier_politique(politique)
        self.assertEqual(v3.numero, 3)

    def test_publier_un_contenu_vide_est_refuse(self):
        politique = self._politique(contenu='   ')
        with self.assertRaises(PublicationImpossible):
            publier_politique(politique)
        self.assertEqual(politique.versions.count(), 0)

    def test_publier_une_politique_obsolete_est_refuse(self):
        politique = self._politique(
            statut=PolitiqueInterne.STATUT_OBSOLETE)
        with self.assertRaises(PublicationImpossible):
            publier_politique(politique)


class ImmuabiliteDesVersionsTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.company = Company.objects.create(nom='NTGRC19 I', slug='ntgrc19-i')

    def test_une_version_ne_se_modifie_pas(self):
        politique = PolitiqueInterne.objects.create(
            company=self.company, titre='P', contenu='texte')
        version = publier_politique(politique)
        version.contenu = 'réécrit'
        with self.assertRaises(PolitiqueVersionError):
            version.save()

    def test_une_version_ne_se_supprime_pas(self):
        politique = PolitiqueInterne.objects.create(
            company=self.company, titre='P', contenu='texte')
        version = publier_politique(politique)
        with self.assertRaises(PolitiqueVersionError):
            version.delete()


class EndpointPolitiquesTests(TenantAPITestCase):
    BASE = '/api/django/grc/politiques-internes/'

    def _admin(self):
        return self.client_as(role='admin')

    def test_creation_impose_la_societe_et_le_statut(self):
        r = self._admin().post(
            self.BASE, {'titre': 'Charte', 'contenu': 'Texte'},
            format='json')
        self.assertEqual(r.status_code, 201, r.content)
        politique = PolitiqueInterne.objects.get(pk=r.data['id'])
        self.assertEqual(politique.company, self.company)
        self.assertEqual(politique.statut, PolitiqueInterne.STATUT_BROUILLON)
        self.assertEqual(politique.version, 0)

    def test_le_statut_et_la_version_ne_sont_pas_ecrivables(self):
        r = self._admin().post(
            self.BASE,
            {'titre': 'Charte', 'contenu': 'Texte',
             'statut': 'publiee', 'version': 9},
            format='json')
        self.assertEqual(r.status_code, 201, r.content)
        politique = PolitiqueInterne.objects.get(pk=r.data['id'])
        self.assertEqual(politique.statut, PolitiqueInterne.STATUT_BROUILLON)
        self.assertEqual(politique.version, 0)

    def test_action_publier(self):
        politique = PolitiqueInterne.objects.create(
            company=self.company, titre='P', contenu='Texte')
        r = self._admin().post(
            f'{self.BASE}{politique.pk}/publier/', {}, format='json')
        self.assertEqual(r.status_code, 200, r.content)
        self.assertEqual(r.data['version']['numero'], 1)
        self.assertEqual(r.data['politique']['version'], 1)

    def test_publier_un_contenu_vide_nomme_le_champ(self):
        politique = PolitiqueInterne.objects.create(
            company=self.company, titre='P', contenu='')
        r = self._admin().post(
            f'{self.BASE}{politique.pk}/publier/', {}, format='json')
        self.assertEqual(r.status_code, 400)
        self.assertIn('contenu', r.data)

    def test_cible_role_sans_valeur_est_refusee(self):
        r = self._admin().post(
            self.BASE,
            {'titre': 'P', 'contenu': 'T', 'cible': 'role'},
            format='json')
        self.assertEqual(r.status_code, 400)
        self.assertIn('cible_valeur', r.data)

    def test_liste_scopee_societe(self):
        PolitiqueInterne.objects.create(
            company=self.other_company, titre='Etrangere')
        r = self._admin().get(self.BASE)
        lignes = r.data.get('results', r.data)
        self.assertEqual(lignes, [])
