"""CAD88 — le délai CALENDAIRE réel, à côté du délai ouvré.

Audit L3 du 21/09/2026, section CAD-I. ``minutes_ouvrees_entre`` neutralise
la nuit et le week-end — c'est la bonne mesure de l'OBJECTIF, et une très
mauvaise mesure de ce que le CLIENT a vécu : un lead arrivé vendredi 20:00 et
traité lundi 08:30 s'affichait « conforme » après soixante heures d'attente.
Tant que la mesure neutralise ce retard, le samedi (CAD43) ne peut pas
s'arbitrer sur des faits.

Ce fichier verrouille les deux moitiés de la règle :

  * la colonne ouvrée ne bouge PAS d'une minute (le calcul existant et la
    doctrine du temps gelé de CKP3 sont intouchés) ;
  * la colonne calendaire, elle, montre les ~60 heures.

Le temps est GELÉ, et ``date_creation`` / ``first_contacted_at`` sont
rétrodatés par ``.update()`` (``date_creation`` est en ``auto_now_add`` :
passé en argument, il serait ignoré en silence).
"""
import datetime

from django.contrib.auth import get_user_model
from django.test import SimpleTestCase, TestCase

from authentication.models import Company
from testkit.time import frozen

from apps.crm import horaires, stages
from apps.crm.models import Lead
from apps.crm.selectors import kpi_premier_contact
from apps.parametres.models import CompanyProfile

User = get_user_model()

#: Mardi 15 septembre 2026, 12 h à Casablanca — jour ouvré, hors week-end.
MAINTENANT = datetime.datetime(2026, 9, 15, 12, 0, tzinfo=horaires.CASABLANCA)

#: Vendredi 11 septembre 2026, 20:00 — après la fermeture, veille de week-end.
VENDREDI_SOIR = datetime.datetime(
    2026, 9, 11, 20, 0, tzinfo=horaires.CASABLANCA)
#: Lundi 14 septembre 2026, 08:30 — l'ouverture de la fenêtre message.
LUNDI_MATIN = datetime.datetime(
    2026, 9, 14, 8, 30, tzinfo=horaires.CASABLANCA)


class MinutesCalendairesTests(SimpleTestCase):
    """La fonction pure : aucune société, aucun horaire, aucun canal."""

    def test_le_week_end_compte(self):
        self.assertEqual(
            horaires.minutes_calendaires_entre(VENDREDI_SOIR, LUNDI_MATIN),
            60 * 60 + 30)

    def test_zero_quand_la_fin_precede_le_debut(self):
        self.assertEqual(
            horaires.minutes_calendaires_entre(LUNDI_MATIN, VENDREDI_SOIR), 0)

    def test_zero_sur_une_borne_absente(self):
        self.assertEqual(
            horaires.minutes_calendaires_entre(None, LUNDI_MATIN), 0)
        self.assertEqual(
            horaires.minutes_calendaires_entre(VENDREDI_SOIR, None), 0)


class KpiPremierContactCalendaireTests(TestCase):
    def setUp(self):
        gel = frozen(MAINTENANT)
        gel.start()
        self.addCleanup(gel.stop)
        self.company, _ = Company.objects.get_or_create(
            slug='cad88', defaults={'nom': 'cad88'})
        CompanyProfile.objects.get_or_create(company=self.company)
        self.acteur = User.objects.create_user(
            username='cad88-resp', password='x', role_legacy='responsable',
            company=self.company)

    def _lead(self, nom, *, cree_le, contacte_le):
        lead = Lead.objects.create(
            company=self.company, nom=nom, owner=self.acteur,
            stage=stages.NEW, source=Lead.Source.OS_NATIVE)
        Lead.objects.filter(pk=lead.pk).update(
            date_creation=cree_le, first_contacted_at=contacte_le)
        lead.refresh_from_db()
        return lead

    def test_vendredi_soir_traite_lundi_conforme_mais_60h_affichees(self):
        """LE cas de l'audit : conforme à l'objectif, 60 heures vécues."""
        self._lead('Vendredi soir', cree_le=VENDREDI_SOIR,
                   contacte_le=LUNDI_MATIN)
        kpi = kpi_premier_contact(self.company, jours=30)

        # L'OBJECTIF : la colonne ouvrée ne bouge pas — le week-end ne se
        # reproche à personne, et le lead reste sous l'objectif.
        self.assertEqual(kpi['nb_sous_objectif'], 1)
        self.assertEqual(kpi['pct_sous_objectif'], 100.0)
        self.assertLessEqual(kpi['mediane_minutes_ouvrees'],
                             kpi['objectif_minutes'])
        # CE QUE LE CLIENT A VÉCU : ~60 h 30 (3 630 minutes).
        self.assertEqual(kpi['mediane_minutes_calendaires'], 60 * 60 + 30)

    def test_la_colonne_ouvree_est_inchangee_sur_un_lead_de_semaine(self):
        cree = datetime.datetime(
            2026, 9, 15, 9, 0, tzinfo=horaires.CASABLANCA)
        self._lead('Mardi matin', cree_le=cree,
                   contacte_le=cree + datetime.timedelta(minutes=4))
        kpi = kpi_premier_contact(self.company, jours=30)
        self.assertEqual(kpi['mediane_minutes_ouvrees'], 4)
        self.assertEqual(kpi['mediane_minutes_calendaires'], 4)

    def test_null_sur_zero_lead(self):
        kpi = kpi_premier_contact(self.company, jours=30)
        self.assertEqual(kpi['nb_leads'], 0)
        self.assertIsNone(kpi['mediane_minutes_calendaires'])
        self.assertIsNone(kpi['mediane_minutes_ouvrees'])

    def test_lead_jamais_contacte_ne_fabrique_aucune_mediane(self):
        lead = Lead.objects.create(
            company=self.company, nom='Jamais rappelé', owner=self.acteur,
            stage=stages.NEW, source=Lead.Source.OS_NATIVE)
        Lead.objects.filter(pk=lead.pk).update(date_creation=VENDREDI_SOIR)
        kpi = kpi_premier_contact(self.company, jours=30)
        self.assertEqual(kpi['nb_leads'], 1)
        self.assertIsNone(kpi['mediane_minutes_calendaires'])

    def test_forme_de_lechantillon_de_contrat(self):
        import json
        from pathlib import Path
        echantillon = json.loads(
            (Path(__file__).resolve().parent / 'contract_samples'
             / 'kpi_premier_contact.json').read_text(encoding='utf-8'))
        kpi = kpi_premier_contact(self.company, jours=30)
        self.assertEqual(set(kpi), set(echantillon['exemple']))
        self.assertEqual(set(kpi), set(echantillon['exemple_vide']))
