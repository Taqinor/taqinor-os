"""ACHT38 (C-ACHT-035) — service unique `replanifier` : date parsée et
validée (400 sous le champ, jamais de 500), compteur de reports, confirmation
du RDV remise à zéro, trace au chatter, pour `confirmer-rdv`, le PATCH de
`date_prevue` et la replanification de masse.

Rejoue CINT-12 (500 puis TransactionManagementError ; `rdv_confirme` True,
compteur 0).

Run :
    powershell -File scripts/test-backend.ps1 -RestoreDb \
        -Modules "apps.installations.tests_acht_replanifier"
"""
import datetime
import json
from pathlib import Path

from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from authentication.models import Company

from apps.installations import services
from apps.installations.models import Installation, Intervention
from apps.roles.models import Role
from apps.roles.permissions_registre import TECHNICIEN_PERMISSIONS

User = get_user_model()
BASE = '/api/django/installations/interventions'


class ReplanifierTests(TestCase):
    def setUp(self):
        self.company, _ = Company.objects.get_or_create(
            slug='co-acht38', defaults={'nom': 'Co ACHT38'})
        self.user = User.objects.create_user(
            username='resp-acht38', password='x', company=self.company,
            role_legacy='responsable')
        self.api = APIClient()
        self.api.credentials(
            HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(self.user)}')
        inst = Installation.objects.create(
            company=self.company, reference='CH-ACHT38')
        self.iv = Intervention.objects.create(
            company=self.company, installation=inst,
            type_intervention='pose', created_by=self.user,
            technicien=self.user, date_prevue=datetime.date(2026, 11, 2),
            rdv_confirme=True)

    def test_date_invalide_400(self):
        r = self.api.post(f'{BASE}/{self.iv.id}/confirmer-rdv/',
                          {'date_prevue': 'demain'}, format='json')
        self.assertEqual(r.status_code, 400, r.data)
        self.assertIn('date_prevue', r.data)
        self.iv.refresh_from_db()
        self.assertEqual(self.iv.date_prevue, datetime.date(2026, 11, 2))
        self.assertTrue(self.iv.rdv_confirme)
        self.assertEqual(self.iv.rdv_reschedule_count, 0)

    def test_date_prevue_publiee_en_date(self):
        """api-fuzz-full 27/10 (ENF11) : `date_prevue` est publiée au format
        DATE (une chaîne libre y était « conforme » puis refusée 400) ; une
        chaîne vide n'est pas une date → 400 aussi (elle passait en simple
        confirmation) ; `null` = simple confirmation."""
        from django.urls import include, path
        from drf_spectacular.generators import SchemaGenerator

        from apps.installations import urls as installations_urls
        schema = SchemaGenerator(patterns=[
            path('api/django/installations/', include(installations_urls)),
        ]).get_schema(request=None, public=True)
        champ = schema['components']['schemas']['ConfirmerRdvRequeteRequest'][
            'properties']['date_prevue']
        self.assertEqual(champ['format'], 'date')
        self.assertTrue(champ['nullable'])
        # api-fuzz-full 29/10 : `motif` publie le motif sans NUL (refusé 400).
        from core.champs_stricts import MOTIF_SANS_NUL
        motif = schema['components']['schemas']['ConfirmerRdvRequeteRequest'][
            'properties']['motif']
        self.assertEqual(motif['pattern'], MOTIF_SANS_NUL)
        r = self.api.post(f'{BASE}/{self.iv.id}/confirmer-rdv/',
                          {'date_prevue': ''}, format='json')
        self.assertEqual(r.status_code, 400, r.data)
        r = self.api.post(f'{BASE}/{self.iv.id}/confirmer-rdv/',
                          {'date_prevue': None, 'confirme': True},
                          format='json')
        self.assertEqual(r.status_code, 200, r.data)
        self.iv.refresh_from_db()
        self.assertEqual(self.iv.rdv_reschedule_count, 0)

    def test_annulation_deplacement_ne_compte_pas_de_report(self):
        """ACSV14 (C-ACSV-135) — déplacer puis « Annuler » au planning :
        compteur de reports revenu à sa valeur d'avant, note « Déplacement
        annulé » ; sans le drapeau le retour compte un report.
        ROUGE AVANT : compteur 2."""
        import datetime

        from apps.installations.models import Intervention
        j3 = datetime.date.today() + datetime.timedelta(days=3)
        j5 = j3 + datetime.timedelta(days=2)
        Intervention.objects.filter(pk=self.iv.pk).update(date_prevue=j3, rdv_reschedule_count=0)
        url = f'/api/django/installations/interventions/{self.iv.pk}/'
        r = self.api.patch(url, {'date_prevue': str(j5)}, format='json')
        self.assertEqual(r.status_code, 200, r.data)
        r = self.api.patch(url, {'date_prevue': str(j3), 'annulation_deplacement': True}, format='json')
        self.assertEqual(r.status_code, 200, r.data)
        self.iv.refresh_from_db()
        self.assertEqual((self.iv.date_prevue, self.iv.rdv_reschedule_count), (j3, 0))
        self.assertTrue(self.iv.activites.filter(body='Déplacement annulé.').exists())
        self.api.patch(url, {'date_prevue': str(j5)}, format='json')
        self.api.patch(url, {'date_prevue': str(j3)}, format='json')
        self.iv.refresh_from_db()
        self.assertEqual(self.iv.rdv_reschedule_count, 2)

    def test_patch_date_reinitialise_confirmation(self):
        r = self.api.patch(f'{BASE}/{self.iv.id}/',
                           {'date_prevue': '2026-11-09'}, format='json')
        self.assertEqual(r.status_code, 200, r.data)
        self.iv.refresh_from_db()
        self.assertFalse(self.iv.rdv_confirme)
        self.assertEqual(self.iv.rdv_reschedule_count, 1)
        self.assertTrue(self.iv.activites.filter(
            kind='note', body__contains='RDV reporté').exists())

    def test_masse_reinitialise_confirmation(self):
        # Le service est le point d'écriture commun de la masse.
        self.assertTrue(services.replanifier(
            self.iv, '2026-11-10', 'Pluie', self.user, technicien_id=None,
            trace=False))
        self.iv.refresh_from_db()
        self.assertFalse(self.iv.rdv_confirme)
        self.assertEqual(self.iv.rdv_reschedule_count, 1)
        self.assertEqual(self.iv.date_prevue, datetime.date(2026, 11, 10))
        with self.assertRaises(ValueError):
            services.replanifier(self.iv, 'n-importe-quoi', '', self.user)

    def test_confirmer_avec_nouvelle_date_confirme_la_nouvelle(self):
        r = self.api.post(f'{BASE}/{self.iv.id}/confirmer-rdv/',
                          {'date_prevue': '2026-11-20', 'confirme': True},
                          format='json')
        self.assertEqual(r.status_code, 200, r.data)
        self.iv.refresh_from_db()
        self.assertTrue(self.iv.rdv_confirme)
        self.assertEqual(self.iv.rdv_reschedule_count, 1)

    def test_types_du_corps_400(self):
        """api-fuzz-full 29/10 : `motif` publié texte et `confirme` booléen —
        un tableau ou une chaîne répond 400, rien n'est écrit."""
        for corps in ({'motif': [[True]], 'date_prevue': None},
                      {'confirme': 'oui'}, {'confirme': None}):
            r = self.api.post(f'{BASE}/{self.iv.id}/confirmer-rdv/', corps,
                              format='json')
            self.assertEqual(r.status_code, 400, r.data)
        self.iv.refresh_from_db()
        self.assertTrue(self.iv.rdv_confirme)


CONTRAT_PLANIFIER = (Path(__file__).resolve().parent / 'contract_samples'
                     / 'chantier_planifier_pose.json')


class PlanifierPoseAssistantTests(TestCase):
    """Copilote vague 2 (CHTA5) — ``POST chantiers/<pk>/planifier-pose/`` :
    la pose OUVERTE est déplacée par le service unique ``replanifier``
    (compteur, confirmation remise à zéro), sinon créée ; date et technicien du
    chantier posés ; statut INCHANGÉ ; refus nommés sans rien écrire.
    Même jeu de données que :class:`ReplanifierTests`."""

    setUp = ReplanifierTests.setUp

    def _url(self, chantier=None):
        chantier = chantier or self.iv.installation
        return f'/api/django/installations/chantiers/{chantier.id}/planifier-pose/'

    def _jour(self, jours):
        return datetime.date.today() + datetime.timedelta(days=jours)

    def test_deplace_la_pose_ouverte_statut_inchange(self):
        inst = self.iv.installation
        statut_avant = inst.statut
        jour = self._jour(4)
        r = self.api.post(self._url(), {
            'date_pose_prevue': jour.isoformat(),
            'date_pose_fin_prevue': self._jour(5).isoformat()}, format='json')
        self.assertEqual(r.status_code, 200, r.data)
        exemple = json.loads(CONTRAT_PLANIFIER.read_text(encoding='utf-8'))['exemple']
        self.assertEqual(set(r.data), set(exemple))
        self.assertEqual(set(r.data['planning']), set(exemple['planning']))
        self.iv.refresh_from_db()
        self.assertEqual(self.iv.date_prevue, jour)
        self.assertEqual(self.iv.rdv_reschedule_count, 1)
        self.assertFalse(self.iv.rdv_confirme)
        self.assertEqual(Intervention.objects.filter(
            installation=inst, type_intervention='pose').count(), 1)
        inst.refresh_from_db()
        self.assertEqual((inst.date_pose_prevue, inst.date_pose_fin_prevue),
                         (jour, self._jour(5)))
        self.assertEqual(inst.statut, statut_avant)
        self.assertEqual(r.data['planning']['intervention_pose']['id'], self.iv.id)
        self.assertEqual(r.data['liens']['intervention_pose'], f'/interventions?id={self.iv.id}')

    def test_cree_la_pose_au_technicien_donne(self):
        inst = self.iv.installation
        self.iv.delete()
        tech = User.objects.create_user(username='tech-chta5', password='x',
                                        company=self.company, role_legacy='responsable')
        jour = self._jour(6)
        r = self.api.post(self._url(inst), {'date_pose_prevue': jour.isoformat(),
                                            'technicien': tech.id}, format='json')
        self.assertEqual(r.status_code, 200, r.data)
        pose = Intervention.objects.get(installation=inst, type_intervention='pose')
        self.assertEqual((pose.technicien_id, pose.date_prevue), (tech.id, jour))
        inst.refresh_from_db()
        self.assertEqual(inst.technicien_responsable_id, tech.id)
        self.assertEqual(r.data['planning']['technicien']['id'], tech.id)
        self.assertEqual(r.data['planning']['intervention_pose']['id'], pose.id)

    def test_refus_nommes_sans_ecriture(self):
        demain = self._jour(1).isoformat()
        cas = [
            ({'date_pose_prevue': self._jour(-1).isoformat()}, 409, 'date_pose_prevue', 'date_passee'),
            ({'date_pose_prevue': demain, 'motif_override_acompte': 'VIP'}, 400,
             'motif_override_acompte', 'champ_refuse'),
            ({'date_pose_prevue': demain, 'technicien': 2147483000}, 400, 'technicien',
             'technicien_inconnu'),
            ({'date_pose_prevue': demain, 'date_pose_fin_prevue': self._jour(0).isoformat()},
             400, 'date_pose_fin_prevue', 'fin_avant_debut'),
        ]
        for corps, statut, champ, code in cas:
            r = self.api.post(self._url(), corps, format='json')
            self.assertEqual(r.status_code, statut, (corps, r.data))
            self.assertEqual((r.data['field'], r.data['code']), (champ, code))
        Intervention.objects.filter(pk=self.iv.pk).update(statut='en_route')
        r = self.api.post(self._url(), {'date_pose_prevue': demain}, format='json')
        self.assertEqual(r.status_code, 409, r.data)
        self.assertEqual(r.data['code'], 'pose_commencee')
        self.iv.refresh_from_db()
        self.assertEqual(self.iv.date_prevue, datetime.date(2026, 11, 2))
        self.assertIsNone(Installation.objects.get(pk=self.iv.installation_id).date_pose_prevue)

    def test_annule_409_et_autre_societe_404(self):
        Installation.objects.filter(pk=self.iv.installation_id).update(annule=True)
        r = self.api.post(self._url(), {'date_pose_prevue': self._jour(2).isoformat()},
                          format='json')
        self.assertEqual(r.status_code, 409, r.data)
        self.assertEqual(r.data['code'], 'chantier_annule')
        autre, _ = Company.objects.get_or_create(slug='co-chta5-autre',
                                                 defaults={'nom': 'Autre CHTA5'})
        chantier_autre = Installation.objects.create(company=autre, reference='CH-CHTA5-AUTRE')
        r = self.api.post(self._url(chantier_autre),
                          {'date_pose_prevue': self._jour(2).isoformat()}, format='json')
        self.assertEqual(r.status_code, 404, r.data)

    def test_affecter_un_technicien_exige_technicien_assign(self):
        role = Role.objects.create(company=self.company, nom='Technicien CHTA5',
                                   permissions=list(TECHNICIEN_PERMISSIONS))
        technicien = User.objects.create_user(username='tech-sans-assign-chta5', password='x',
                                              company=self.company, role=role)
        api = APIClient()
        api.credentials(HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(technicien)}')
        r = api.post(self._url(), {'date_pose_prevue': self._jour(2).isoformat(),
                                   'technicien': self.user.id}, format='json')
        self.assertEqual(r.status_code, 403, r.data)
        self.iv.refresh_from_db()
        self.assertEqual(self.iv.date_prevue, datetime.date(2026, 11, 2))
