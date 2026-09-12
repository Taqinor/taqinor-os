"""NTGRC18 — constats de déficience + liens risque / CAPA QHSE.

Garanties : une déficience majeure peut référencer un CAPA QHSE existant par
identifiant TEXTE (sans aucun import de `apps.qhse.models`), la référence est
VÉRIFIÉE comme appartenant à la société, et tout reste scopé société.
"""
from django.test import TestCase
from django.utils import timezone

from apps.grc.models import ControleInterne, DeficienceControle, TestControle
from apps.grc.services import creer_risque
from apps.qhse.models import ActionCorrectivePreventive, NonConformite
from authentication.models import Company
from testkit.base import TenantAPITestCase


def _capa(company):
    """Crée un CAPA QHSE réel (fixture de test — la PROD passe par selector)."""
    ncr = NonConformite.objects.create(company=company, titre='NCR test')
    return ActionCorrectivePreventive.objects.create(
        company=company, non_conformite=ncr, description='Corriger')


class ReferencesTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.company = Company.objects.create(nom='NTGRC18 SA', slug='ntgrc18')
        cls.controle = ControleInterne.objects.create(
            company=cls.company, code='ACC-01', intitule='Revue des accès')
        cls.test = TestControle.objects.create(
            company=cls.company, controle=cls.controle,
            resultat=TestControle.RESULTAT_DEFICIENT,
            date_realisee=timezone.now().date())

    def test_les_references_sont_du_texte_pas_des_fk(self):
        capa = _capa(self.company)
        risque = creer_risque(self.company, titre='R')
        deficience = DeficienceControle.objects.create(
            company=self.company, test_controle=self.test,
            gravite=DeficienceControle.GRAVITE_MAJEURE,
            responsable='DAF',
            qhse_capa_ref=str(capa.pk),
            risque_entreprise_ref=str(risque.pk))
        deficience.refresh_from_db()
        self.assertEqual(deficience.qhse_capa_ref, str(capa.pk))
        self.assertEqual(deficience.risque_entreprise_ref, str(risque.pk))
        # La référence est un CHAMP TEXTE : aucune FK n'est déclarée vers qhse.
        champs = {f.name: f for f in DeficienceControle._meta.get_fields()}
        self.assertEqual(
            champs['qhse_capa_ref'].get_internal_type(), 'CharField')

    def test_la_deficience_survit_a_la_disparition_du_capa(self):
        capa = _capa(self.company)
        deficience = DeficienceControle.objects.create(
            company=self.company, test_controle=self.test,
            qhse_capa_ref=str(capa.pk))
        ActionCorrectivePreventive.objects.filter(pk=capa.pk).delete()
        deficience.refresh_from_db()
        self.assertEqual(deficience.qhse_capa_ref, str(capa.pk))


class SelectorQhseTests(TestCase):
    def test_capa_ids_de_societe_est_borne(self):
        from apps.qhse.selectors import capa_ids_de_societe

        a = Company.objects.create(nom='NTGRC18 A', slug='ntgrc18-a')
        b = Company.objects.create(nom='NTGRC18 B', slug='ntgrc18-b')
        capa_a = _capa(a)
        _capa(b)
        self.assertEqual(capa_ids_de_societe(a), [capa_a.pk])
        self.assertEqual(capa_ids_de_societe(None), [])


class EndpointDeficiencesTests(TenantAPITestCase):
    BASE = '/api/django/grc/deficiences-controle/'

    def setUp(self):
        super().setUp()
        self.controle = ControleInterne.objects.create(
            company=self.company, code='ACC-01', intitule='Revue')
        self.test = TestControle.objects.create(
            company=self.company, controle=self.controle,
            resultat=TestControle.RESULTAT_DEFICIENT,
            date_realisee=timezone.now().date())

    def _admin(self):
        return self.client_as(role='admin')

    def test_une_deficience_majeure_reference_un_capa_existant(self):
        capa = _capa(self.company)
        r = self._admin().post(
            self.BASE,
            {'test_controle': self.test.pk, 'gravite': 'majeure',
             'responsable': 'DAF', 'qhse_capa_ref': str(capa.pk)},
            format='json')
        self.assertEqual(r.status_code, 201, r.content)
        deficience = DeficienceControle.objects.get(pk=r.data['id'])
        self.assertEqual(deficience.company, self.company)
        self.assertEqual(deficience.qhse_capa_ref, str(capa.pk))

    def test_un_capa_dune_autre_societe_est_refuse(self):
        etranger = _capa(self.other_company)
        r = self._admin().post(
            self.BASE,
            {'test_controle': self.test.pk, 'responsable': 'DAF',
             'qhse_capa_ref': str(etranger.pk)},
            format='json')
        self.assertEqual(r.status_code, 400)
        self.assertIn('qhse_capa_ref', r.data)

    def test_une_reference_non_numerique_est_refusee(self):
        r = self._admin().post(
            self.BASE,
            {'test_controle': self.test.pk, 'qhse_capa_ref': 'abc'},
            format='json')
        self.assertEqual(r.status_code, 400)
        self.assertIn('qhse_capa_ref', r.data)

    def test_une_deficience_majeure_exige_un_responsable(self):
        r = self._admin().post(
            self.BASE,
            {'test_controle': self.test.pk, 'gravite': 'majeure'},
            format='json')
        self.assertEqual(r.status_code, 400)
        self.assertIn('responsable', r.data)

    def test_un_test_dune_autre_societe_est_refuse(self):
        etranger_controle = ControleInterne.objects.create(
            company=self.other_company, code='X', intitule='X')
        etranger_test = TestControle.objects.create(
            company=self.other_company, controle=etranger_controle)
        r = self._admin().post(
            self.BASE, {'test_controle': etranger_test.pk}, format='json')
        self.assertEqual(r.status_code, 400)
        self.assertIn('test_controle', r.data)

    def test_filtre_par_gravite(self):
        DeficienceControle.objects.create(
            company=self.company, test_controle=self.test,
            gravite=DeficienceControle.GRAVITE_MINEURE)
        DeficienceControle.objects.create(
            company=self.company, test_controle=self.test,
            gravite=DeficienceControle.GRAVITE_MAJEURE, responsable='DAF')
        r = self._admin().get(self.BASE, {'gravite': 'majeure'})
        lignes = r.data.get('results', r.data)
        self.assertEqual(len(lignes), 1)
