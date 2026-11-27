"""ACAL126 — chaque refus de simulation est NOMMÉ et ATTEIGNABLE.

Constats C-ACAL-074 / C-ACAL-067. Avant : ``POST simuler/`` rendait 202 pour
une société sans mode météo (la tâche échouait ensuite, en texte libre) ; une
seule température saisie faisait un 500 ; un σ saisi illisible, un horizon
illisible ou PVGIS indisponible pour un pan levaient une exception brute ; et
le job en échec n'avait AUCUNE charge en cache — l'écran ne savait pas quel
champ pointer.

Désormais : pré-vérification 409 (refus d'état) dans la vue par LA fonction de la
simulation (``verifier_simulable``), exceptions d'entrée converties en
``SimulationRefusee``, échec de job structuré ``elements[0] = {statut,
champ, motif}`` servi par ``GET moteur/resultat/<job>/``.

Run :
    python manage.py test apps.calepinage.tests.test_acal_refus_simulation -v2
"""
from __future__ import annotations

import copy
from unittest import mock

from django.test import SimpleTestCase, TestCase

from apps.calepinage.services.pvgis_serie import EntreeInvalide
from apps.calepinage.services.simulation import (
    SimulationRefusee, construire_contexte, simuler_calepinage,
)

from .test_acal_multi_pans import _layout, _zone
from .test_calx5_simulation import (
    LAYOUT, MATERIEL, REGLAGES, _Calepinage, _ClientRejoue, _reponse_meteo,
)


class _ClientQuiRefuseLeSecondPan:
    """Un client double : le SECOND plan demandé est refusé (horizon
    illisible côté appel), comme ``ClientPvgis`` le ferait."""

    def __init__(self):
        self.demandes = []

    def serie_irradiance(self, **parametres):
        self.demandes.append(parametres)
        if len(self.demandes) > 1:
            raise EntreeInvalide(
                "Profil d'horizon illisible : 12 hauteurs attendues.",
                champ='horizonProfile')
        return _reponse_meteo()


class RefusDuServiceTest(SimpleTestCase):

    def test_sigma_illisible_refus_nomme(self):
        reglages = copy.deepcopy(REGLAGES)
        reglages['simulation']['sigma_modele_pct'] = {
            'valeur': '2,5', 'source': 'societe', 'reference': 'essai'}

        with self.assertRaises(SimulationRefusee) as refus:
            simuler_calepinage(_Calepinage(), client=_ClientRejoue(),
                               materiel=MATERIEL, reglages=reglages,
                               enregistrer=False)
        self.assertEqual(refus.exception.champ, 'sigma_modele_pct')
        self.assertTrue(refus.exception.motif)

    def test_entree_invalide_multi_pans_nommee(self):
        calepinage = _Calepinage(layout=_layout(_zone(1, 8, 90.0),
                                                _zone(2, 8, 270.0)))
        with self.assertRaises(SimulationRefusee) as refus:
            simuler_calepinage(calepinage,
                               client=_ClientQuiRefuseLeSecondPan(),
                               materiel=MATERIEL, reglages=REGLAGES,
                               enregistrer=False)
        self.assertEqual(refus.exception.champ, 'horizonProfile')
        self.assertIn('horizon', refus.exception.motif)

    def test_temperature_partielle_refus_nomme(self):
        calepinage = _Calepinage(resultat={
            'entree_electrique': {'temperature_min_c': -5.0}})
        with self.assertRaises(SimulationRefusee) as refus:
            construire_contexte(calepinage, materiel=MATERIEL,
                                reglages=REGLAGES)
        self.assertEqual(refus.exception.champ, 'temperature_max_c')


def _contrat_simulation():
    import json
    import pathlib

    chemin = (pathlib.Path(__file__).resolve().parents[1] / 'contract_samples'
              / 'calepinage_simulation.json')
    return json.loads(chemin.read_text(encoding='utf-8'))


class ManquantsDeSimulationTest(SimpleTestCase):
    """ACAL940 — TOUS les manques en une fois, dans l'ordre des contrôles.
    Mutant : s'arrêter au premier manque ⇒ une ligne au lieu de trois."""

    def test_reglages_vides_sans_epingle_trois_lignes_dans_l_ordre(self):
        from apps.calepinage.services import manquants_simulation

        attendu = _contrat_simulation()['exemple_refus_manquants']
        lignes = manquants_simulation.manquants_de_simulation(
            {}, {'plans_equipes': 1})
        self.assertEqual(lignes, attendu['manquants'])

    def test_acal1649_le_refus_meteo_se_dit_sans_cle_brute(self):
        from apps.calepinage.services import manquants_simulation

        lignes = manquants_simulation.manquants_de_simulation(
            {'site': {'lat': 33.5, 'lon': -7.6}}, {'plans_equipes': 1})
        self.assertEqual([ligne['champ'] for ligne in lignes],
                         ['parametres.simulation.mode_meteo',
                          'parametres.simulation.fenetre_annees'])
        self.assertEqual(lignes[0]['motif'],
                         'Choisissez le mode météo : année type ou plusieurs années.')
        for ligne in lignes:
            for brut in ('parametres.', 'tmy', 'pluriannuel'):
                self.assertNotIn(brut, ligne['motif'])

    def test_avec_epingle_deux_lignes(self):
        from apps.calepinage.services import manquants_simulation

        lignes = manquants_simulation.manquants_de_simulation(
            {'site': {'lat': 33.5, 'lon': -7.6}}, {'plans_equipes': 1})
        self.assertEqual([ligne['champ'] for ligne in lignes],
                         ['parametres.simulation.mode_meteo',
                          'parametres.simulation.fenetre_annees'])

    def test_verifier_simulable_leve_une_fois_avec_toutes_les_lignes(self):
        from apps.calepinage.services.simulation import verifier_simulable

        attendu = _contrat_simulation()['exemple_refus_manquants']
        with self.assertRaises(SimulationRefusee) as refus:
            verifier_simulable({}, {'plans_equipes': 1})
        self.assertEqual(refus.exception.champ,
                         'parametres.simulation.mode_meteo')
        self.assertEqual(
            {refus.exception.champ: [refus.exception.motif]},
            {k: v for k, v in attendu.items() if k != 'manquants'})
        self.assertEqual(refus.exception.manquants, attendu['manquants'])


class RefusSansPanTest(SimpleTestCase):
    """ACAL771 — « aucun pan équipé » (champ ``plans``) est une ligne de
    ``manquants[]``, entre les réglages et l'épingle. Mutant : placer
    ``plans`` avant les réglages ⇒ l'ordre ci-dessous échoue."""

    REGLAGES = {
        'mode_meteo': {'valeur': 'pluriannuel', 'source': 'societe',
                       'reference': 'essai'},
        'fenetre_annees': {'valeur': '2015-2020', 'source': 'societe',
                           'reference': 'essai'},
    }

    def test_reglages_remplis_epingle_posee_sans_module_une_ligne_plans(self):
        from apps.calepinage.services import manquants_simulation

        attendu = _contrat_simulation()['exemple_refus_sans_pan_equipe']
        contexte = {'reglages_simulation': self.REGLAGES,
                    'site': {'lat': 33.5, 'lon': -7.6}}
        lignes = manquants_simulation.manquants_de_simulation(contexte, {})
        self.assertEqual(lignes, attendu['manquants'])

    def test_acal1639_le_refus_sans_module_mene_a_toit_ou_panneaux(self):
        from apps.calepinage.services import manquants_simulation

        def cible(contexte):
            lignes = manquants_simulation.manquants_de_simulation(
                dict(contexte, reglages_simulation=self.REGLAGES), {})
            return next(ligne for ligne in lignes if ligne['champ'] == 'plans')['cible']

        self.assertEqual(cible({'plans': []})['etape'], 'toit')
        self.assertEqual(cible({'plans': [{'modules': 0}]})['etape'], 'panneaux')
        # des modules posés : pas l'étape Toit ni Panneaux (matériel, côté écran)
        self.assertIsNone(cible({'plans': [{'modules': 4}]}))

    def test_le_409_garde_la_cle_de_tete_plans(self):
        from apps.calepinage.services.simulation import verifier_simulable

        attendu = _contrat_simulation()['exemple_refus_sans_pan_equipe']
        contexte = {'reglages_simulation': self.REGLAGES,
                    'site': {'lat': 33.5, 'lon': -7.6}}
        with self.assertRaises(SimulationRefusee) as refus:
            verifier_simulable(contexte, {})
        self.assertEqual(refus.exception.champ, 'plans')
        self.assertEqual({refus.exception.champ: [refus.exception.motif]},
                         {k: v for k, v in attendu.items()
                          if k != 'manquants'})
        self.assertEqual(refus.exception.manquants, attendu['manquants'])

    def test_reglages_vides_sans_module_ordre_mode_fenetre_plans_epingle(self):
        from apps.calepinage.services import manquants_simulation

        lignes = manquants_simulation.manquants_de_simulation({}, {})
        self.assertEqual([ligne['champ'] for ligne in lignes],
                         ['parametres.simulation.mode_meteo',
                          'parametres.simulation.fenetre_annees',
                          'plans', 'site.pin'])


class _BaseApi(TestCase):

    def setUp(self):
        from django.contrib.auth import get_user_model
        from rest_framework.test import APIClient
        from rest_framework_simplejwt.tokens import AccessToken

        from apps.calepinage.models import Calepinage
        from apps.crm.models import Lead
        from apps.roles.models import Role
        from apps.roles.permissions_registre import DIRECTEUR_PERMISSIONS
        from authentication.models import Company

        self.societe = Company.objects.create(nom='ACAL126', slug='acal126')
        role = Role.objects.create(company=self.societe, nom='Directeur',
                                   permissions=list(DIRECTEUR_PERMISSIONS))
        self.user = get_user_model().objects.create_user(
            username='acal126', password='x', company=self.societe,
            role=role)
        self.api = APIClient()
        self.api.credentials(
            HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(self.user)}')
        lead = Lead.objects.create(company=self.societe, nom='Toiture 126')
        self.calepinage = Calepinage.objects.create(
            company=self.societe, lead_id=lead.pk, titre='Refus 126',
            roof_layout=copy.deepcopy(LAYOUT))
        self.url = (f'/api/django/calepinage/calepinages/'
                    f'{self.calepinage.pk}/simuler/')

    def _poster(self):
        with mock.patch(
                'apps.calepinage.services.electrique.resoudre_materiel',
                return_value=MATERIEL), \
                mock.patch('core.jobs.submit') as soumettre:
            reponse = self.api.post(self.url, {}, format='json')
        return reponse, soumettre


class PreVerificationApiTest(_BaseApi):

    def test_sans_mode_meteo_409_nomme(self):
        # La société n'a RIEN réglé : aucun mode météo.
        reponse, soumettre = self._poster()

        self.assertEqual(reponse.status_code, 409, reponse.content[:300])
        self.assertIn('parametres.simulation.mode_meteo', reponse.data)
        self.assertTrue(reponse.data['parametres.simulation.mode_meteo'][0])
        soumettre.assert_not_called()

    def test_reglages_vides_un_seul_409_avec_tous_les_manquants(self):
        # ACAL940 — aucun réglage : mode météo ET fenêtre listés d'un coup.
        reponse, _soumettre = self._poster()

        self.assertEqual(reponse.status_code, 409, reponse.content[:300])
        champs = [ligne['champ'] for ligne in reponse.data['manquants']]
        self.assertEqual(champs[:2], ['parametres.simulation.mode_meteo',
                                      'parametres.simulation.fenetre_annees'])
        self.assertEqual(reponse.data['manquants'][0]['cible'],
                         {'onglet': 'reglages', 'champ': 'calx69-mode_meteo'})

    def test_temperature_partielle_409_pas_500(self):
        self.calepinage.resultat = {
            'entree_electrique': {'temperature_min_c': -5.0}}
        self.calepinage.save(update_fields=['resultat'])

        reponse, soumettre = self._poster()

        self.assertEqual(reponse.status_code, 409, reponse.content[:300])
        self.assertIn('temperature_max_c', reponse.data)
        soumettre.assert_not_called()


class EchecDeJobStructureTest(_BaseApi):

    def _job(self):
        from core.models import BackgroundJob

        from apps.calepinage.tasks import KIND_CALEPINAGE

        return BackgroundJob.objects.create(
            company=self.societe, user=self.user, kind=KIND_CALEPINAGE,
            statut=BackgroundJob.STATUT_QUEUED)

    def test_sigma_illisible_echec_structure_avec_champ(self):
        from apps.calepinage.tasks import simuler_calepinage as tache

        job = self._job()
        reglages = copy.deepcopy(REGLAGES)
        reglages['simulation']['sigma_modele_pct'] = {
            'valeur': '2,5', 'source': 'societe', 'reference': 'essai'}
        with mock.patch(
                'apps.calepinage.services.electrique.resoudre_materiel',
                return_value=MATERIEL), \
                mock.patch(
                    'apps.calepinage.services.electrique.parametres_societe',
                    return_value=reglages), \
                mock.patch('apps.calepinage.services.simulation.ClientPvgis',
                           return_value=_ClientRejoue()):
            issue = tache(job_id=job.pk, company_id=self.societe.pk,
                          calepinage_id=self.calepinage.pk, forcer=True)

        job.refresh_from_db()
        self.assertEqual(issue['statut'], 'failed')
        self.assertEqual(issue['champ'], 'sigma_modele_pct')
        self.assertEqual(job.statut, job.STATUT_FAILED)
        from apps.calepinage.tasks import resultat_du_job

        element = resultat_du_job(job)['elements'][0]
        self.assertEqual(element['statut'], 'failed')
        self.assertEqual(element['champ'], 'sigma_modele_pct')
        self.assertTrue(element['motif'])

    def test_suivi_job_expose_champ_et_motif(self):
        from apps.calepinage.tasks import simuler_calepinage as tache

        job = self._job()
        with mock.patch(
                'apps.calepinage.services.electrique.resoudre_materiel',
                return_value=MATERIEL):
            tache(job_id=job.pk, company_id=self.societe.pk,
                  calepinage_id=self.calepinage.pk, forcer=True)

        reponse = self.api.get(
            f'/api/django/calepinage/moteur/resultat/{job.pk}/')
        self.assertEqual(reponse.status_code, 200, reponse.content[:300])
        self.assertEqual(reponse.data['statut'], 'failed')
        element = reponse.data['elements'][0]
        self.assertEqual(element['statut'], 'failed')
        self.assertEqual(element['champ'],
                         'parametres.simulation.mode_meteo')
        self.assertTrue(element['motif'])

    def _echouer_sur(self, exception):
        from apps.calepinage.tasks import resultat_du_job
        from apps.calepinage.tasks import simuler_calepinage as tache

        job = self._job()
        with mock.patch(
                'apps.calepinage.services.simulation.simuler_calepinage',
                side_effect=exception):
            issue = tache(job_id=job.pk, company_id=self.societe.pk,
                          calepinage_id=self.calepinage.pk, forcer=True)
        job.refresh_from_db()
        return issue, job, resultat_du_job(job)['elements'][0]

    def test_t4_v1_012_temps_depasse_dit_en_francais_quoi_faire(self):
        """Au-delà de la limite douce de Celery, le serveur publiait
        ``str(SoftTimeLimitExceeded())`` — « SoftTimeLimitExceeded() » à
        l'écran, sans phrase ni nouvel essai."""
        from celery.exceptions import SoftTimeLimitExceeded

        issue, job, element = self._echouer_sur(SoftTimeLimitExceeded())
        self.assertEqual(issue['statut'], 'failed')
        self.assertEqual(element['champ'],
                         'parametres.simulation.fenetre_annees')
        self.assertTrue(element['motif'].startswith(
            'La simulation a dépassé le temps alloué'))
        self.assertIn('relancez-la', element['motif'])
        self.assertIn('Fenêtre d’années météo', element['motif'])
        for texte in (element['motif'], job.message_erreur, issue['motif']):
            self.assertNotIn('SoftTimeLimitExceeded', texte)

    def test_t4_v1_012_erreur_inattendue_jamais_le_nom_de_l_exception(self):
        issue, job, element = self._echouer_sur(KeyError('zones'))
        self.assertEqual(element['champ'], '')
        self.assertTrue(element['motif'].startswith('La simulation a échoué'))
        for texte in (element['motif'], job.message_erreur, issue['motif']):
            self.assertNotIn('KeyError', texte)
            self.assertNotIn("'zones'", texte)

    def _echouer_balayage(self, exception):
        from apps.calepinage.tasks import balayer_calepinage as tache
        from apps.calepinage.tasks import resultat_du_job

        job = self._job()
        with mock.patch('apps.calepinage.services.balayage.balayer',
                        side_effect=exception):
            issue = tache(job_id=job.pk, company_id=self.societe.pk,
                          calepinage_id=self.calepinage.pk,
                          corps={'pan': 'p1', 'axes': {}})
        job.refresh_from_db()
        return issue, job, resultat_du_job(job)['elements'][0]

    def test_acal1629_balayage_temps_depasse_dit_de_reduire_la_grille(self):
        from celery.exceptions import SoftTimeLimitExceeded

        issue, job, element = self._echouer_balayage(SoftTimeLimitExceeded())
        self.assertEqual(issue['statut'], 'failed')
        self.assertIn('Le balayage a dépassé le temps permis : réduisez la '
                      'grille', element['motif'])
        for texte in (element['motif'], job.message_erreur, issue['motif']):
            self.assertNotIn('SoftTimeLimitExceeded', texte)

    def test_acal1629_balayage_meteo_refusee_sans_cle_technique(self):
        refus = SimulationRefusee(
            "La série météo ne porte que l'irradiance HORIZONTALE "
            "(« gh_w_m2 ») : elle se transpose sur le PLAN (« gi_w_m2 »).",
            champ='meteo.gi_w_m2')
        issue, job, element = self._echouer_balayage(refus)
        self.assertEqual(issue['statut'], 'failed')
        self.assertIn("L'optimisation demande une année type ou une série "
                      'horaire : passez la fenêtre météo à un an',
                      element['motif'])
        for cle in ('gh_w_m2', 'gi_w_m2', 'mode_meteo'):
            self.assertNotIn(cle, element['motif'])
