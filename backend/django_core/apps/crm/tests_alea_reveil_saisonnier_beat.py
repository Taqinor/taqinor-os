"""ALEA1 (D-ALEA-1, option a) — le réveil saisonnier CAD74 branché sur le beat.

Constat C-ALEA-026 : ``poser_reveils_saisonniers`` existait, idempotente, mais
AUCUNE tâche Celery ni entrée beat ne l'appelait — la coche CAD74 était fausse
en prod. Ces tests passent par la TÂCHE réelle (point d'entrée de prod), sans
mock de la source : services, modèles et sélecteur de sociétés actives réels.
"""
import datetime

from django.contrib.auth import get_user_model
from django.test import TestCase

from authentication.models import Company

from apps.crm import horaires, stages
from apps.crm.cadence_reveil_saison import REVEIL_SAISON_CLE
from apps.crm.models import Lead, RelanceEtape
from apps.parametres.models import CompanyProfile
from apps.parametres.models_relance import CanalRelance

User = get_user_model()

#: Lundi 15 juin 2026, 10 h à Casablanca — début de la fenêtre.
JUIN_2026 = datetime.datetime(2026, 6, 15, 10, 0, tzinfo=horaires.CASABLANCA)
#: Mardi 15 juin 2027 — l'année suivante.
JUIN_2027 = datetime.datetime(2027, 6, 15, 10, 0, tzinfo=horaires.CASABLANCA)
#: Jeudi 15 janvier 2026 — hors saison.
JANVIER_2026 = datetime.datetime(2026, 1, 15, 10, 0,
                                 tzinfo=horaires.CASABLANCA)


def _geler(test, instant):
    from testkit.time import frozen

    gel = frozen(instant)
    gel.start()
    test.addCleanup(gel.stop)
    return gel


class ReveilSaisonnierBeatTests(TestCase):

    def _societe(self, slug, actif=True):
        etat = ({} if actif
                else {'actif': False, 'statut': Company.STATUT_SUSPENDU})
        company = Company.objects.create(slug=slug, nom=slug, **etat)
        company.refresh_from_db()
        self.assertEqual(company.actif, actif)
        CompanyProfile.objects.create(company=company)
        owner = User.objects.create_user(
            username=f'{slug}-resp', password='x',
            role_legacy='responsable', company=company)
        return company, owner

    def _dormant(self, company, owner, nom='Dormant'):
        lead = Lead.objects.create(
            company=company, nom=nom, prenom='Benali', ville='Bouskoura',
            owner=owner, stage=stages.COLD)
        # Son réveil J60 est tombé en mars : HORS de la fenêtre saisonnière.
        jour = datetime.date(2026, 3, 2)
        RelanceEtape.objects.create(
            company=company, lead=lead, cadence='reveil', ordre=2,
            due_at=datetime.datetime.combine(
                jour, datetime.time(10, 0), tzinfo=horaires.CASABLANCA),
            due_date=jour, canal=CanalRelance.WHATSAPP, libelle='Réveil J60',
            template_cle='reveil_a3', statut=RelanceEtape.Statut.FAIT)
        return lead

    def _touches(self, lead):
        return RelanceEtape.objects.filter(
            lead=lead, template_cle=REVEIL_SAISON_CLE)

    def test_beat_declare(self):
        from erp_agentique.celery import app

        entree = app.conf.beat_schedule.get('crm-poser-reveils-saisonniers')
        self.assertIsNotNone(entree)
        self.assertEqual(entree['task'], 'crm.poser_reveils_saisonniers')
        # Bornée juin → septembre.
        self.assertEqual(entree['schedule'].month_of_year, {6, 7, 8, 9})
        from apps.crm.tasks import poser_reveils_saisonniers_task
        self.assertEqual(poser_reveils_saisonniers_task.name,
                         'crm.poser_reveils_saisonniers')

    def test_une_touche_par_an(self):
        from apps.crm.tasks import poser_reveils_saisonniers_task

        company, owner = self._societe('alea1-an')
        lead = self._dormant(company, owner)

        gel = _geler(self, JUIN_2026)
        premier = poser_reveils_saisonniers_task()
        second = poser_reveils_saisonniers_task()

        self.assertGreaterEqual(premier['posees'], 1)
        self.assertEqual(second['posees'], 0)
        touches = self._touches(lead)
        self.assertEqual(touches.count(), 1)
        self.assertEqual(touches.get().due_date.year, 2026)

        # La touche 2026 est traitée ; l'année suivante, une nouvelle.
        touches.update(statut=RelanceEtape.Statut.FAIT)
        gel.stop()
        _geler(self, JUIN_2027)
        poser_reveils_saisonniers_task()
        poser_reveils_saisonniers_task()

        relu = self._touches(lead)
        self.assertEqual(relu.count(), 2)
        self.assertEqual(relu.filter(due_date__year=2027).count(), 1)

    def test_hors_saison_rien(self):
        from apps.crm.tasks import poser_reveils_saisonniers_task

        company, owner = self._societe('alea1-hiver')
        lead = self._dormant(company, owner)

        _geler(self, JANVIER_2026)
        resultat = poser_reveils_saisonniers_task()

        self.assertEqual(resultat['posees'], 0)
        self.assertFalse(self._touches(lead).exists())

    def test_societe_inactive_sautee(self):
        from apps.crm.tasks import poser_reveils_saisonniers_task

        active, owner_a = self._societe('alea1-active')
        inactive, owner_i = self._societe('alea1-inactive', actif=False)
        lead_actif = self._dormant(active, owner_a)
        lead_inactif = self._dormant(inactive, owner_i)

        _geler(self, JUIN_2026)
        poser_reveils_saisonniers_task()

        self.assertEqual(self._touches(lead_actif).count(), 1)
        self.assertFalse(self._touches(lead_inactif).exists())
