"""Tests XQHS12 — Revue de direction (ISO 9.3) + comité de sécurité et
d'hygiène (Code du travail).

Couvre :

* la création d'une CAPA liée depuis une décision (idempotente) ;
* la clôture d'une revue de direction exige la checklist ISO 9.3 complète ;
* les autres types de réunion clôturent sans condition ;
* la relance trimestrielle CSH (due / non due) ;
* le scoping société.
"""
from datetime import date, timedelta

from django.contrib.auth import get_user_model
from django.test import TestCase

from authentication.models import Company

from apps.qhse.models import (
    ActionCorrectivePreventive, DecisionReunion, ReunionQhse,
)
from apps.qhse.services import (
    cloturer_reunion_qhse, creer_capa_depuis_decision, csh_relance_due,
)

User = get_user_model()


def make_company(slug, nom):
    company, _ = Company.objects.get_or_create(slug=slug, defaults={'nom': nom})
    return company


def make_user(company, username, role='responsable'):
    return User.objects.create_user(
        username=username, password='x', company=company, role_legacy=role)


class CreerCapaDepuisDecisionTests(TestCase):
    def setUp(self):
        self.company = make_company('co-xqhs12-capa', 'CoXqhs12Capa')
        self.reunion = ReunionQhse.objects.create(
            company=self.company,
            type_reunion=ReunionQhse.TypeReunion.REUNION_HSE)

    def test_cree_capa_liee(self):
        decision = DecisionReunion.objects.create(
            company=self.company, reunion=self.reunion,
            texte='Renforcer la formation LOTO')
        capa = creer_capa_depuis_decision(decision)
        self.assertIsInstance(capa, ActionCorrectivePreventive)
        decision.refresh_from_db()
        self.assertEqual(decision.capa_id, capa.id)

    def test_idempotent(self):
        decision = DecisionReunion.objects.create(
            company=self.company, reunion=self.reunion, texte='Décision X')
        capa1 = creer_capa_depuis_decision(decision)
        decision.refresh_from_db()
        capa2 = creer_capa_depuis_decision(decision)
        self.assertEqual(capa1.id, capa2.id)
        self.assertEqual(
            ActionCorrectivePreventive.objects.filter(
                company=self.company).count(), 1)


class CloturerReunionQhseTests(TestCase):
    def setUp(self):
        self.company = make_company('co-xqhs12-clot', 'CoXqhs12Clot')

    def test_revue_direction_checklist_incomplete_refuse_cloture(self):
        reunion = ReunionQhse.objects.create(
            company=self.company,
            type_reunion=ReunionQhse.TypeReunion.REVUE_DIRECTION,
            checklist_revue_direction={'resultats_audits': True})
        with self.assertRaises(ValueError):
            cloturer_reunion_qhse(reunion)

    def test_revue_direction_checklist_complete_cloture(self):
        checklist = {cle: True for cle in
                     ReunionQhse.CHECKLIST_REVUE_DIRECTION_CLES}
        reunion = ReunionQhse.objects.create(
            company=self.company,
            type_reunion=ReunionQhse.TypeReunion.REVUE_DIRECTION,
            checklist_revue_direction=checklist)
        cloturer_reunion_qhse(reunion)
        reunion.refresh_from_db()
        self.assertEqual(reunion.statut, ReunionQhse.Statut.CLOTUREE)

    def test_csh_cloture_sans_checklist(self):
        reunion = ReunionQhse.objects.create(
            company=self.company,
            type_reunion=ReunionQhse.TypeReunion.COMITE_HYGIENE_SECURITE)
        cloturer_reunion_qhse(reunion)
        reunion.refresh_from_db()
        self.assertEqual(reunion.statut, ReunionQhse.Statut.CLOTUREE)


class CshRelanceDueTests(TestCase):
    def setUp(self):
        self.company = make_company('co-xqhs12-csh', 'CoXqhs12Csh')

    def test_due_sans_reunion_anterieure(self):
        self.assertTrue(csh_relance_due(self.company))

    def test_pas_due_apres_reunion_recente(self):
        ReunionQhse.objects.create(
            company=self.company,
            type_reunion=ReunionQhse.TypeReunion.COMITE_HYGIENE_SECURITE,
            statut=ReunionQhse.Statut.TENUE,
            date_reunion=date.today() - timedelta(days=10))
        self.assertFalse(csh_relance_due(self.company))

    def test_due_apres_cadence_depassee(self):
        ReunionQhse.objects.create(
            company=self.company,
            type_reunion=ReunionQhse.TypeReunion.COMITE_HYGIENE_SECURITE,
            statut=ReunionQhse.Statut.TENUE,
            date_reunion=date.today() - timedelta(days=100))
        self.assertTrue(csh_relance_due(self.company, cadence_jours=90))

    def test_isolation_societe(self):
        autre = make_company('co-xqhs12-csh-autre', 'CoXqhs12CshAutre')
        ReunionQhse.objects.create(
            company=self.company,
            type_reunion=ReunionQhse.TypeReunion.COMITE_HYGIENE_SECURITE,
            statut=ReunionQhse.Statut.TENUE,
            date_reunion=date.today())
        self.assertTrue(csh_relance_due(autre))
