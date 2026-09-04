"""Tests AUDV05 — la consolidation groupe expose ce qu'elle savait déjà faire.

Trois services complets et testés unitairement, sans aucun appelant :

* `convertir_entite` (NTFIN5) — un groupe avec une filiale en devise étrangère
  ne pouvait PAS consolider depuis l'écran : la balance de cette entité restait
  en devise locale, donc l'agrégat était faux ;
* `muter_immobilisation` (NTFIN42) — le ViewSet était un CRUD nu et
  `entite_source` un champ WRITABLE : un client pouvait déclarer une entité
  d'origine arbitraire pour un actif dont le serveur connaît le propriétaire ;
* `enregistrer_etape_audit_consolidation` (NTFIN55) — l'action `etapes-audit`
  listait une table qui restait vide POUR TOUJOURS : aucune étape du pipeline
  n'était scellée, donc la consolidation n'était pas auditable.
"""
import json
from datetime import date
from decimal import Decimal
from pathlib import Path

from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from authentication.models import Company

from apps.compta import services
from apps.compta.models import (
    CycleConsolidation, EtapeAuditConsolidation, ExerciceComptable,
    Immobilisation, LiasseRemontee, MutationImmobilisation,
)

User = get_user_model()

CONTRATS = Path(__file__).resolve().parent.parent / 'contract_samples'


def contrat(nom, variante='exemple'):
    return json.loads(
        (CONTRATS / f'{nom}.json').read_text(encoding='utf-8'))[variante]


def make_company(slug, nom):
    return Company.objects.get_or_create(slug=slug, defaults={'nom': nom})[0]


def make_user(company, username, role='admin'):
    return User.objects.create_user(
        username=username, password='x', company=company, role_legacy=role)


def auth(user):
    api = APIClient()
    api.credentials(HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(user)}')
    return api


def make_cycle(company):
    exercice, _ = ExerciceComptable.objects.get_or_create(
        company=company, date_debut=date(2026, 1, 1),
        date_fin=date(2026, 12, 31), defaults={'libelle': '2026'})
    return CycleConsolidation.objects.create(
        company=company, libelle='Consol 2026', exercice=exercice,
        date_debut=date(2026, 1, 1), date_fin=date(2026, 12, 31),
        devise_presentation='MAD')


class ConversionEntiteApiTests(TestCase):
    """DRAFT165-50 — convertir une liasse en devise de présentation."""

    def setUp(self):
        self.co = make_company('audv05-conv', 'AUDV05 Conversion')
        services.seed_plan_comptable(self.co)
        services.seed_journaux(self.co)
        self.user = make_user(self.co, 'audv05-conv-user')
        self.api = auth(self.user)
        self.cycle = make_cycle(self.co)
        self.liasse = LiasseRemontee.objects.create(
            company=self.co, cycle=self.cycle, entite=self.co,
            statut=LiasseRemontee.Statut.COLLECTE, devise_locale='EUR',
            snapshot_balance=[
                {'numero': '2340', 'classe': 2, 'debit': '1000', 'credit': '0'},
                {'numero': '1111', 'classe': 1, 'debit': '0', 'credit': '700'},
                {'numero': '7121', 'classe': 7, 'debit': '0', 'credit': '300'},
            ])

    def _url(self):
        return (f'/api/django/compta/cycles-consolidation/'
                f'{self.cycle.id}/convertir-entite/')

    def test_bilan_au_cours_de_cloture_resultat_au_cours_moyen(self):
        resp = self.api.post(self._url(), {
            'liasse': self.liasse.id, 'taux_cloture': '10', 'taux_moyen': '11',
        }, format='json')
        self.assertEqual(resp.status_code, 200, resp.content)
        # Bilan ×10 = 10 000 au débit ; 700×10 + 300×11 = 10 300 au crédit.
        self.assertEqual(resp.data['total_debit'], Decimal('10000.00'))
        self.assertEqual(resp.data['total_credit'], Decimal('10300.00'))
        # L'écart de conversion est DIT, jamais absorbé en silence.
        self.assertEqual(resp.data['ecart_conversion'], Decimal('300.00'))
        self.assertTrue(resp.data['equilibre'])

    def test_la_conversion_ne_reecrit_pas_le_snapshot_collecte(self):
        """L'original reste la preuve de ce que la filiale a DÉCLARÉ."""
        avant = list(self.liasse.snapshot_balance)
        self.api.post(self._url(), {
            'liasse': self.liasse.id, 'taux_cloture': '10', 'taux_moyen': '11',
        }, format='json')
        self.liasse.refresh_from_db()
        self.assertEqual(self.liasse.snapshot_balance, avant)

    def test_la_reponse_porte_les_cles_du_contrat(self):
        resp = self.api.post(self._url(), {
            'liasse': self.liasse.id, 'taux_cloture': '10', 'taux_moyen': '11',
        }, format='json')
        exemple = contrat('consolidation_conversion_entite')
        # `detail` est le canal d'ERREUR : au contrat (la garde unifie les
        # branches), absent de la réponse de succès.
        self.assertEqual(sorted(set(exemple) - {'detail'}), sorted(resp.data))
        self.assertEqual(sorted(exemple['lignes'][0]),
                         sorted(resp.data['lignes'][0]))

    def test_cours_non_positif_refuse(self):
        resp = self.api.post(self._url(), {
            'liasse': self.liasse.id, 'taux_cloture': '0', 'taux_moyen': '11',
        }, format='json')
        self.assertEqual(resp.status_code, 400, resp.content)

    def test_liasse_hors_cycle_refusee(self):
        autre_cycle = make_cycle(self.co)
        autre_liasse = LiasseRemontee.objects.create(
            company=self.co, cycle=autre_cycle, entite=self.co,
            statut=LiasseRemontee.Statut.COLLECTE, snapshot_balance=[])
        resp = self.api.post(self._url(), {
            'liasse': autre_liasse.id, 'taux_cloture': '10',
            'taux_moyen': '11'}, format='json')
        self.assertEqual(resp.status_code, 400, resp.content)


class ScellementEtapesAuditTests(TestCase):
    """DRAFT165-52 — chaque étape du pipeline scelle son maillon d'audit."""

    def setUp(self):
        self.co = make_company('audv05-audit', 'AUDV05 Audit')
        services.seed_plan_comptable(self.co)
        services.seed_journaux(self.co)
        self.user = make_user(self.co, 'audv05-audit-user')
        self.api = auth(self.user)
        self.cycle = make_cycle(self.co)

    def _etapes(self):
        return list(EtapeAuditConsolidation.objects.filter(
            cycle=self.cycle).order_by('sequence'))

    def _post(self, action, corps=None):
        return self.api.post(
            f'/api/django/compta/cycles-consolidation/{self.cycle.id}/'
            f'{action}/', corps or {}, format='json')

    def test_avant_toute_action_aucune_etape(self):
        resp = self.api.get(
            f'/api/django/compta/cycles-consolidation/{self.cycle.id}/'
            'etapes-audit/')
        self.assertEqual(resp.status_code, 200, resp.content)
        self.assertEqual(self._etapes(), [])

    def test_chaque_etape_du_pipeline_scelle_un_maillon(self):
        self.assertEqual(self._post('collecter').status_code, 200)
        self.assertEqual(self._post('apparier').status_code, 200)
        self.assertEqual(self._post('generer-reciproques').status_code, 200)
        self.assertEqual(self._post('interets-minoritaires').status_code, 200)
        self.assertEqual(self._post('verrouiller').status_code, 200)
        etapes = [e.etape for e in self._etapes()]
        self.assertEqual(etapes, [
            'collecte', 'appariement', 'reciproques',
            'interets_minoritaires', 'verrouillage'])

    def test_la_chaine_de_hachage_est_continue_et_horodatee(self):
        self._post('collecter')
        self._post('apparier')
        etapes = self._etapes()
        self.assertEqual(len(etapes), 2)
        self.assertEqual(etapes[0].sequence, 1)
        self.assertEqual(etapes[1].sequence, 2)
        # Le second maillon CHAÎNE le premier : un maillon retiré se voit.
        self.assertEqual(etapes[0].hash_precedent, '')
        self.assertEqual(etapes[1].hash_precedent, etapes[0].hash)
        self.assertNotEqual(etapes[0].hash, etapes[1].hash)

    def test_l_acteur_est_pose_cote_serveur(self):
        self._post('collecter')
        self.assertEqual(self._etapes()[0].acteur_id, self.user.id)


class MutationImmobilisationEntiteSourceTests(TestCase):
    """DRAFT165-51 — `entite_source` est DÉRIVÉE, jamais lue du corps."""

    URL = '/api/django/compta/mutations-immobilisation/'

    def setUp(self):
        self.co = make_company('audv05-mut', 'AUDV05 Mutation')
        self.autre = make_company('audv05-mut-autre', 'AUDV05 Autre')
        self.user = make_user(self.co, 'audv05-mut-user')
        self.api = auth(self.user)
        self.immo = Immobilisation.objects.create(
            company=self.co, libelle='Onduleur central',
            cout=Decimal('120000'), date_acquisition=date(2026, 1, 5),
            date_mise_en_service=date(2026, 1, 5))

    def test_entite_source_derivee_de_la_societe_de_l_actif(self):
        resp = self.api.post(self.URL, {
            'immobilisation': self.immo.id, 'date': '2026-06-01',
            'motif': 'Transfert au dépôt Nord',
        }, format='json')
        self.assertEqual(resp.status_code, 201, resp.content)
        mutation = MutationImmobilisation.objects.get(id=resp.data['id'])
        self.assertEqual(mutation.entite_source_id, self.co.id)
        self.assertEqual(mutation.company_id, self.co.id)

    def test_une_entite_source_envoyee_par_le_client_est_IGNOREE(self):
        resp = self.api.post(self.URL, {
            'immobilisation': self.immo.id, 'date': '2026-06-01',
            'entite_source': self.autre.id,  # doit être ignoré
        }, format='json')
        self.assertEqual(resp.status_code, 201, resp.content)
        mutation = MutationImmobilisation.objects.get(id=resp.data['id'])
        self.assertEqual(mutation.entite_source_id, self.co.id)

    def test_immobilisation_d_une_autre_societe_refusee(self):
        immo_autre = Immobilisation.objects.create(
            company=self.autre, libelle='Hors société',
            cout=Decimal('1000'), date_acquisition=date(2026, 1, 5),
            date_mise_en_service=date(2026, 1, 5))
        resp = self.api.post(self.URL, {
            'immobilisation': immo_autre.id, 'date': '2026-06-01',
        }, format='json')
        self.assertEqual(resp.status_code, 400, resp.content)
