"""NTGRC28 — cockpit de conformité du DPO (7 compteurs en un appel).

Garanties : l'endpoint renvoie les SEPT compteurs scopés société, en UN appel,
sans aucune donnée personnelle ; un retard de DSR s'affiche en jours NÉGATIFS.
Horloge FIGÉE : tous les compteurs à échéance sont datés.
"""
import json
from pathlib import Path

from django.test import TestCase
from django.utils import timezone

from apps.grc.models import (
    AnalyseImpactDPIA, ControleInterne, PolitiqueInterne, RisqueEntreprise,
    ViolationDonnees,
)
from apps.grc.selectors import tableau_bord_dpo
from apps.grc.services import creer_violation, publier_politique
from apps.rh.models import DossierEmploye
from authentication.models import Company
from core.models import ConsentRecord, DataSubjectRequest, RegistreTraitement
from testkit.base import TenantAPITestCase
from testkit.time import frozen

INSTANT = '2026-09-12 12:00:00+00:00'


def _peupler(company):
    """Une société avec EXACTEMENT un manquement de chaque famille."""
    # 1/2. DSR en retard (échéance dépassée) — posée à la création.
    DataSubjectRequest.objects.create(
        company=company, subject_identifier='a@b.ma',
        kind=DataSubjectRequest.KIND_ERASURE)
    # 3. Violation non notifiée, échéance 72 h dépassée.
    creer_violation(
        company,
        date_detection=timezone.now() - timezone.timedelta(days=5),
        statut=ViolationDonnees.STATUT_OUVERTE)
    # 4. Consentement RETIRÉ ce mois-ci — SANS ``occurred_at`` (le champ est
    #    facultatif) : le cockpit doit quand même le compter, via created_at.
    ConsentRecord.objects.create(
        company=company, subject_identifier='a@b.ma', purpose='marketing',
        granted=False)
    # 5. Politique publiée non attestée (un salarié cible, zéro attestation).
    DossierEmploye.objects.create(
        company=company, matricule='E1', nom='A', prenom='A')
    politique = PolitiqueInterne.objects.create(
        company=company, titre='Charte', contenu='Texte')
    publier_politique(politique)
    # 6. Contrôle actif jamais testé.
    ControleInterne.objects.create(
        company=company, code='ACC-01', intitule='Revue des comptes',
        actif=True)
    # 7. Risque résiduel en zone rouge + traitement sensible sans AIPD.
    RisqueEntreprise.objects.create(
        company=company, titre='Fuite de données', probabilite_residuelle=5,
        impact_residuel=5)
    RegistreTraitement.objects.create(
        company=company, code='RH-SANTE', finalite='Dossiers médicaux',
        donnees_sensibles=True)


class CockpitSelectorTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.company = Company.objects.create(nom='NTGRC28 SA', slug='ntgrc28')

    def test_les_sept_compteurs_repondent(self):
        with frozen(INSTANT):
            _peupler(self.company)
        with frozen('2026-10-20 12:00:00+00:00'):
            cockpit = tableau_bord_dpo(self.company)
        self.assertEqual(cockpit['dsr_ouverts'], 1)
        self.assertEqual(cockpit['dsr_en_retard'], 1)
        self.assertEqual(cockpit['violations_72h'], 1)
        self.assertEqual(cockpit['violations_72h_depassees'], 1)
        self.assertEqual(cockpit['politiques_non_attestees'], 1)
        self.assertEqual(cockpit['controles_a_tester'], 1)
        self.assertEqual(cockpit['risques_critiques'], 1)
        self.assertEqual(cockpit['traitements_sans_dpia'], 1)

    def test_le_retard_d_une_dsr_est_un_nombre_negatif(self):
        with frozen(INSTANT):
            _peupler(self.company)
        with frozen('2026-10-20 12:00:00+00:00'):
            cockpit = tableau_bord_dpo(self.company)
        self.assertEqual(cockpit['dsr_details'][0]['jours_restants'], -8)

    def test_les_consentements_retires_sont_ceux_du_mois_en_cours(self):
        with frozen(INSTANT):
            _peupler(self.company)
            # Un second retrait, celui-là avec sa date d'action renseignée.
            ConsentRecord.objects.create(
                company=self.company, subject_identifier='c@d.ma',
                purpose='whatsapp', granted=False,
                occurred_at=timezone.now())
            cockpit = tableau_bord_dpo(self.company)
        self.assertEqual(cockpit['consentements_retires_mois'], 2)
        with frozen('2026-10-20 12:00:00+00:00'):
            plus_tard = tableau_bord_dpo(self.company)
        self.assertEqual(plus_tard['consentements_retires_mois'], 0)

    def test_un_consentement_toujours_accorde_n_est_pas_un_retrait(self):
        with frozen(INSTANT):
            ConsentRecord.objects.create(
                company=self.company, subject_identifier='e@f.ma',
                purpose='marketing', granted=True)
            cockpit = tableau_bord_dpo(self.company)
        self.assertEqual(cockpit['consentements_retires_mois'], 0)

    def test_le_cockpit_n_expose_aucune_donnee_personnelle(self):
        with frozen(INSTANT):
            _peupler(self.company)
            cockpit = tableau_bord_dpo(self.company)
        brut = json.dumps(cockpit, default=str)
        self.assertNotIn('a@b.ma', brut)

    def test_une_analyse_validee_retire_le_traitement_du_compte(self):
        with frozen(INSTANT):
            _peupler(self.company)
            traitement = RegistreTraitement.objects.get(
                company=self.company, code='RH-SANTE')
            AnalyseImpactDPIA.objects.create(
                company=self.company, traitement_ref=str(traitement.pk),
                mesures_attenuation='Chiffrement',
                statut=AnalyseImpactDPIA.STATUT_VALIDEE)
            cockpit = tableau_bord_dpo(self.company)
        self.assertEqual(cockpit['traitements_sans_dpia'], 0)

    def test_une_societe_vierge_renvoie_des_zeros(self):
        vierge = Company.objects.create(nom='Vierge', slug='ntgrc28-vierge')
        with frozen(INSTANT):
            cockpit = tableau_bord_dpo(vierge)
        for cle in ('dsr_ouverts', 'violations_72h',
                    'consentements_retires_mois', 'politiques_non_attestees',
                    'controles_a_tester', 'risques_critiques',
                    'traitements_sans_dpia'):
            self.assertEqual(cockpit[cle], 0, cle)


class CockpitEndpointTests(TenantAPITestCase):
    URL = '/api/django/grc/tableau-bord-dpo/'

    def test_un_seul_appel_renvoie_les_sept_compteurs(self):
        with frozen(INSTANT):
            _peupler(self.company)
            r = self.client_as(role='admin').get(self.URL)
        self.assertEqual(r.status_code, 200, r.content)
        for cle in ('dsr_ouverts', 'violations_72h',
                    'consentements_retires_mois', 'politiques_non_attestees',
                    'controles_a_tester', 'risques_critiques',
                    'traitements_sans_dpia'):
            self.assertIn(cle, r.data)

    def test_le_cockpit_est_scope_societe(self):
        with frozen(INSTANT):
            _peupler(self.other_company)
            r = self.client_as(role='admin').get(self.URL)
        self.assertEqual(r.data['dsr_ouverts'], 0)
        self.assertEqual(r.data['risques_critiques'], 0)
        self.assertEqual(r.data['traitements_sans_dpia'], 0)


class ContratCockpitTests(TestCase):
    """PACT10 — l'exemple partagé colle aux clés réellement servies."""

    CHEMIN = (Path(__file__).resolve().parents[1] / 'contract_samples'
              / 'tableau_bord_dpo.json')

    @classmethod
    def setUpTestData(cls):
        cls.company = Company.objects.create(nom='NTGRC28 C', slug='ntgrc28-c')

    def test_l_exemple_porte_les_memes_cles_que_le_selector(self):
        exemple = json.loads(self.CHEMIN.read_text(encoding='utf-8'))
        with frozen(INSTANT):
            _peupler(self.company)
            reel = tableau_bord_dpo(self.company)
        self.assertEqual(set(exemple['exemple']), set(reel))

    def test_les_compteurs_de_l_exemple_sont_des_entiers(self):
        exemple = json.loads(self.CHEMIN.read_text(encoding='utf-8'))['exemple']
        for cle, valeur in exemple.items():
            if cle in ('dsr_details', 'calcule_le'):
                continue
            self.assertIsInstance(valeur, int, cle)
