"""NTGRC27 — analyses d'impact (AIPD) des traitements à haut risque.

Garantie centrale : un traitement porteur de DONNÉES SENSIBLES sans AIPD
VALIDÉE remonte dans le sélecteur — un brouillon ou une analyse « à réviser »
ne couvre rien. Horloge FIGÉE dans l'assertion de date de validation.
"""
from django.test import TestCase

from apps.grc.models import AnalyseImpactDPIA
from apps.grc.selectors import traitements_dpia_manquante
from apps.grc.services import (
    ValidationDPIAImpossible, demander_revision_dpia, valider_dpia,
)
from authentication.models import Company
from core.models import RegistreTraitement
from core.selectors import traitements_haut_risque
from testkit.base import TenantAPITestCase
from testkit.time import frozen

INSTANT = '2026-09-12 11:00:00+00:00'


def _traitement(company, code, sensibles=False, actif=True):
    return RegistreTraitement.objects.create(
        company=company, code=code, finalite=f'Finalité {code}',
        donnees_sensibles=sensibles, actif=actif)


class SelectorDpiaManquanteTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.company = Company.objects.create(nom='NTGRC27 SA', slug='ntgrc27')

    def _analyse(self, traitement, **kw):
        params = {'traitement_ref': str(traitement.pk),
                  'mesures_attenuation': 'Chiffrement + accès restreint'}
        params.update(kw)
        return AnalyseImpactDPIA.objects.create(
            company=self.company, **params)

    def test_un_traitement_sensible_sans_analyse_remonte(self):
        traitement = _traitement(self.company, 'RH-SANTE', sensibles=True)
        manquants = traitements_dpia_manquante(self.company)
        self.assertEqual(len(manquants), 1)
        self.assertEqual(manquants[0]['traitement'].pk, traitement.pk)
        self.assertIsNone(manquants[0]['analyse'])

    def test_un_traitement_non_sensible_ne_remonte_pas(self):
        _traitement(self.company, 'PROSPECTS', sensibles=False)
        self.assertEqual(traitements_dpia_manquante(self.company), [])

    def test_une_analyse_en_brouillon_ne_couvre_pas(self):
        traitement = _traitement(self.company, 'RH-SANTE', sensibles=True)
        self._analyse(traitement)  # statut brouillon par défaut
        manquants = traitements_dpia_manquante(self.company)
        self.assertEqual(len(manquants), 1)
        self.assertIsNotNone(manquants[0]['analyse'])

    def test_une_analyse_validee_couvre(self):
        traitement = _traitement(self.company, 'RH-SANTE', sensibles=True)
        analyse = self._analyse(traitement)
        valider_dpia(analyse)
        self.assertEqual(traitements_dpia_manquante(self.company), [])

    def test_une_analyse_a_reviser_redevient_manquante(self):
        traitement = _traitement(self.company, 'RH-SANTE', sensibles=True)
        analyse = self._analyse(traitement)
        valider_dpia(analyse)
        demander_revision_dpia(analyse)
        self.assertEqual(len(traitements_dpia_manquante(self.company)), 1)

    def test_un_traitement_inactif_est_hors_perimetre(self):
        _traitement(self.company, 'ANCIEN', sensibles=True, actif=False)
        self.assertEqual(traitements_dpia_manquante(self.company), [])

    def test_le_selector_core_est_borne_a_la_societe(self):
        autre = Company.objects.create(nom='Autre', slug='ntgrc27-autre')
        _traitement(autre, 'RH-SANTE', sensibles=True)
        self.assertEqual(list(traitements_haut_risque(self.company)), [])
        self.assertEqual(traitements_dpia_manquante(self.company), [])


class ValidationDpiaTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.company = Company.objects.create(nom='NTGRC27 V', slug='ntgrc27-v')

    def _analyse(self, **kw):
        traitement = _traitement(
            self.company, kw.pop('code', 'T1'), sensibles=True)
        params = {'traitement_ref': str(traitement.pk),
                  'mesures_attenuation': 'Chiffrement'}
        params.update(kw)
        return AnalyseImpactDPIA.objects.create(
            company=self.company, **params)

    def test_valider_pose_le_statut_et_la_date_ensemble(self):
        analyse = self._analyse()
        with frozen(INSTANT):
            valider_dpia(analyse)
        analyse.refresh_from_db()
        self.assertEqual(analyse.statut, AnalyseImpactDPIA.STATUT_VALIDEE)
        self.assertEqual(analyse.date_validation.isoformat(),
                         '2026-09-12T11:00:00+00:00')

    def test_valider_sans_mesures_est_refuse(self):
        analyse = self._analyse(mesures_attenuation='   ')
        with self.assertRaises(ValidationDPIAImpossible) as ctx:
            valider_dpia(analyse)
        self.assertEqual(ctx.exception.champ, 'mesures_attenuation')
        analyse.refresh_from_db()
        self.assertEqual(analyse.statut, AnalyseImpactDPIA.STATUT_BROUILLON)

    def test_un_risque_residuel_eleve_exige_l_avis_du_dpo(self):
        analyse = self._analyse(
            risque_residuel=AnalyseImpactDPIA.RISQUE_ELEVE)
        with self.assertRaises(ValidationDPIAImpossible) as ctx:
            valider_dpia(analyse)
        self.assertEqual(ctx.exception.champ, 'avis_dpo')

    def test_un_risque_eleve_avec_avis_passe(self):
        analyse = self._analyse(
            risque_residuel=AnalyseImpactDPIA.RISQUE_ELEVE,
            avis_dpo='Consultation CNDP engagée.')
        valider_dpia(analyse)
        analyse.refresh_from_db()
        self.assertEqual(analyse.statut, AnalyseImpactDPIA.STATUT_VALIDEE)


class EndpointDpiaTests(TenantAPITestCase):
    BASE = '/api/django/grc/analyses-dpia/'

    def _admin(self):
        return self.client_as(role='admin')

    def test_creation_impose_la_societe_et_le_statut(self):
        traitement = _traitement(self.company, 'T1', sensibles=True)
        r = self._admin().post(
            self.BASE,
            {'traitement_ref': str(traitement.pk),
             'mesures_attenuation': 'Chiffrement',
             'statut': 'validee'},
            format='json')
        self.assertEqual(r.status_code, 201, r.content)
        analyse = AnalyseImpactDPIA.objects.get(pk=r.data['id'])
        self.assertEqual(analyse.company, self.company)
        self.assertEqual(analyse.statut, AnalyseImpactDPIA.STATUT_BROUILLON)
        self.assertIsNone(analyse.date_validation)

    def test_un_traitement_d_une_autre_societe_est_refuse(self):
        etranger = _traitement(self.other_company, 'T9', sensibles=True)
        r = self._admin().post(
            self.BASE, {'traitement_ref': str(etranger.pk)}, format='json')
        self.assertEqual(r.status_code, 400)
        self.assertIn('traitement_ref', r.data)

    def test_declarer_aucune_dpia_necessaire_exige_une_justification(self):
        traitement = _traitement(self.company, 'T2')
        r = self._admin().post(
            self.BASE,
            {'traitement_ref': str(traitement.pk), 'necessite_dpia': False},
            format='json')
        self.assertEqual(r.status_code, 400)
        self.assertIn('avis_dpo', r.data)

    def test_action_valider_nomme_le_champ_en_cas_de_refus(self):
        traitement = _traitement(self.company, 'T3', sensibles=True)
        analyse = AnalyseImpactDPIA.objects.create(
            company=self.company, traitement_ref=str(traitement.pk))
        r = self._admin().post(
            f'{self.BASE}{analyse.pk}/valider/', {}, format='json')
        self.assertEqual(r.status_code, 400)
        self.assertIn('mesures_attenuation', r.data)

    def test_endpoint_traitements_sans_dpia(self):
        traitement = _traitement(self.company, 'T4', sensibles=True)
        r = self._admin().get(f'{self.BASE}traitements-sans-dpia/')
        self.assertEqual(r.status_code, 200, r.content)
        self.assertEqual(len(r.data['results']), 1)
        self.assertEqual(r.data['results'][0]['traitement_ref'],
                         str(traitement.pk))
        self.assertIsNone(r.data['results'][0]['analyse'])

    def test_liste_scopee_societe(self):
        etranger = _traitement(self.other_company, 'T5', sensibles=True)
        AnalyseImpactDPIA.objects.create(
            company=self.other_company, traitement_ref=str(etranger.pk))
        r = self._admin().get(self.BASE)
        lignes = r.data.get('results', r.data)
        self.assertEqual(lignes, [])
