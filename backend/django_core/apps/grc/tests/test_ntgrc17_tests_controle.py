"""NTGRC17 — tests de contrôle planifiés + preuves.

Garanties : un contrôle mensuel non testé ce mois-ci remonte comme « à
tester », un test « déficient » ouvre automatiquement un risque lié (une seule
fois), et tout reste scopé société.
"""
from django.test import TestCase
from django.utils import timezone

from apps.grc.models import ControleInterne, RisqueEntreprise, TestControle
from apps.grc.selectors import controles_a_tester
from apps.grc.services import enregistrer_test_controle
from authentication.models import Company
from testkit.base import TenantAPITestCase


class ControlesATesterTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.company = Company.objects.create(nom='NTGRC17 SA', slug='ntgrc17')

    def _controle(self, company=None, **kw):
        params = {
            'code': 'CPT-01', 'intitule': 'Rapprochement bancaire',
            'frequence': ControleInterne.FREQ_MENSUEL, 'actif': True,
        }
        params.update(kw)
        return ControleInterne.objects.create(
            company=company or self.company, **params)

    def _test_efficace(self, controle, il_y_a_jours):
        return enregistrer_test_controle(
            controle.company, controle,
            resultat=TestControle.RESULTAT_EFFICACE,
            date_realisee=timezone.now().date() -
            timezone.timedelta(days=il_y_a_jours))

    def test_un_controle_jamais_teste_est_toujours_du(self):
        controle = self._controle()
        dus = controles_a_tester(self.company)
        self.assertEqual([d['controle'].pk for d in dus], [controle.pk])
        self.assertTrue(dus[0]['dernier_test'] is None)

    def test_un_mensuel_non_teste_ce_mois_remonte(self):
        controle = self._controle()
        self._test_efficace(controle, 45)
        dus = controles_a_tester(self.company)
        self.assertEqual([d['controle'].pk for d in dus], [controle.pk])

    def test_un_mensuel_teste_recemment_ne_remonte_pas(self):
        controle = self._controle()
        self._test_efficace(controle, 5)
        self.assertEqual(controles_a_tester(self.company), [])

    def test_un_test_deficient_ne_remet_pas_le_compteur_a_zero(self):
        controle = self._controle()
        self._test_efficace(controle, 45)
        enregistrer_test_controle(
            self.company, controle,
            resultat=TestControle.RESULTAT_DEFICIENT,
            date_realisee=timezone.now().date())
        dus = controles_a_tester(self.company)
        self.assertEqual([d['controle'].pk for d in dus], [controle.pk])

    def test_un_controle_inactif_ne_remonte_pas(self):
        self._controle(actif=False)
        self.assertEqual(controles_a_tester(self.company), [])

    def test_la_fenetre_within_anticipe_lecheance(self):
        controle = self._controle()
        self._test_efficace(controle, 20)  # échéance dans 10 jours
        self.assertEqual(controles_a_tester(self.company), [])
        self.assertEqual(
            len(controles_a_tester(self.company, within=15)), 1)

    def test_la_frequence_pilote_la_fenetre(self):
        annuel = self._controle(code='SAV-02',
                                frequence=ControleInterne.FREQ_ANNUEL)
        self._test_efficace(annuel, 45)
        self.assertEqual(controles_a_tester(self.company), [])

    def test_selector_borne_a_la_societe(self):
        autre = Company.objects.create(nom='NTGRC17 B', slug='ntgrc17-b')
        self._controle(company=autre)
        self.assertEqual(controles_a_tester(self.company), [])


class DeficienceOuvreUnRisqueTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.company = Company.objects.create(nom='NTGRC17 D', slug='ntgrc17-d')

    def _controle(self):
        return ControleInterne.objects.create(
            company=self.company, code='SOD-01',
            intitule='Séparation saisie / validation',
            proprietaire='DAF')

    def test_un_test_deficient_ouvre_un_risque_lie(self):
        controle = self._controle()
        test = enregistrer_test_controle(
            self.company, controle,
            resultat=TestControle.RESULTAT_DEFICIENT,
            date_realisee=timezone.now().date(),
            conclusion='Deux paiements saisis et validés par la même personne.')
        test.refresh_from_db()
        self.assertIsNotNone(test.risque_ouvert)
        risque = test.risque_ouvert
        self.assertEqual(risque.company, self.company)
        self.assertIn('SOD-01', risque.titre)
        self.assertEqual(risque.categorie, 'conformite')
        self.assertEqual(risque.proprietaire, 'DAF')

    def test_un_test_efficace_nouvre_aucun_risque(self):
        controle = self._controle()
        test = enregistrer_test_controle(
            self.company, controle,
            resultat=TestControle.RESULTAT_EFFICACE,
            date_realisee=timezone.now().date())
        self.assertIsNone(test.risque_ouvert)
        self.assertEqual(
            RisqueEntreprise.objects.filter(company=self.company).count(), 0)

    def test_louverture_du_risque_est_idempotente(self):
        from apps.grc.services import ouvrir_risque_sur_deficience

        controle = self._controle()
        test = enregistrer_test_controle(
            self.company, controle,
            resultat=TestControle.RESULTAT_DEFICIENT,
            date_realisee=timezone.now().date())
        ouvrir_risque_sur_deficience(test)
        ouvrir_risque_sur_deficience(test)
        self.assertEqual(
            RisqueEntreprise.objects.filter(company=self.company).count(), 1)


class EndpointTestsControleTests(TenantAPITestCase):
    BASE = '/api/django/grc/tests-controle/'

    def setUp(self):
        super().setUp()
        self.controle = ControleInterne.objects.create(
            company=self.company, code='ACC-01', intitule='Revue des accès')

    def _admin(self):
        return self.client_as(role='admin')

    def test_creation_impose_la_societe_et_ouvre_le_risque(self):
        r = self._admin().post(
            self.BASE,
            {'controle': self.controle.pk, 'resultat': 'deficient',
             'date_realisee': timezone.now().date().isoformat(),
             'conclusion': 'Comptes de partis encore actifs.'},
            format='json')
        self.assertEqual(r.status_code, 201, r.content)
        test = TestControle.objects.get(pk=r.data['id'])
        self.assertEqual(test.company, self.company)
        self.assertIsNotNone(test.risque_ouvert)

    def test_un_resultat_sans_date_nomme_le_champ_fautif(self):
        r = self._admin().post(
            self.BASE,
            {'controle': self.controle.pk, 'resultat': 'efficace'},
            format='json')
        self.assertEqual(r.status_code, 400)
        self.assertIn('date_realisee', r.data)

    def test_un_test_ne_peut_pas_pointer_le_controle_dune_autre_societe(self):
        etranger = ControleInterne.objects.create(
            company=self.other_company, code='X', intitule='X')
        r = self._admin().post(
            self.BASE, {'controle': etranger.pk}, format='json')
        self.assertEqual(r.status_code, 400)
        self.assertIn('controle', r.data)

    def test_endpoint_controles_a_tester(self):
        r = self._admin().get(f'{self.BASE}controles-a-tester/')
        self.assertEqual(r.status_code, 200, r.content)
        self.assertEqual(len(r.data['results']), 1)
        self.assertTrue(r.data['results'][0]['jamais_teste'])
