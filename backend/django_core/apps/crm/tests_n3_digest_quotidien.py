"""N3 — le digest de 08:30 est QUOTIDIEN, même à zéro, et parle des étapes.

Décision fondateur du 25/09/2026 : « La notification de 8 h 30 de Meryem a
disparu ». Le digest se taisait quand aucune touche n'était due
(`if not n: continue`) — et ce silence se lisait comme une panne. Ce module
verrouille :

  * à zéro touche due, un commercial qui tient des dossiers vivants reçoit
    « Aucune relance due aujourd'hui — N touche(s) à venir cette semaine » ;
  * les étapes de VISITE (planifier, confirmer la veille, débrief) et de
    DEVIS (préparer et envoyer) entrent dans le total ET sont comptées à part ;
  * aucun digest un jour NON ouvré (dimanche, férié).

Temps gelé : « dû aujourd'hui » et l'idempotence par jour en dépendent.
"""
import datetime
from zoneinfo import ZoneInfo

from django.contrib.auth import get_user_model
from django.test import TestCase

from authentication.models import Company
from testkit.time import frozen

from apps.crm import services as crm_services
from apps.crm import stages
from apps.crm.management.commands.notifier_relances_dues import (
    DIGEST_ZERO_TITRE, notifier_relances_dues)
from apps.crm.models import Lead, RelanceEtape
from apps.notifications.models import EventType, Holiday, Notification
from apps.parametres.models import CompanyProfile

User = get_user_model()

CASA = ZoneInfo('Africa/Casablanca')

#: Mardi 29 septembre 2026, 08:30 à Casablanca — l'heure du digest.
MARDI = datetime.datetime(2026, 9, 29, 8, 30, tzinfo=CASA)
#: Dimanche 4 octobre 2026, 08:30.
DIMANCHE = datetime.datetime(2026, 10, 4, 8, 30, tzinfo=CASA)


class _Base(TestCase):
    slug = 'n3-digest'
    maintenant = MARDI

    def setUp(self):
        gel = frozen(self.maintenant)
        gel.start()
        self.addCleanup(gel.stop)
        self.company = Company.objects.create(
            nom='N3 Solaire', slug=self.slug)
        self.profil, _ = CompanyProfile.objects.get_or_create(
            company=self.company)
        self.meryem = User.objects.create_user(
            username=f'{self.slug}-meryem', password='x',
            role_legacy='commercial', company=self.company)
        self._compteur = 0

    def _lead(self, nom='Prospect', **kw):
        self._compteur += 1
        champs = {'company': self.company, 'nom': nom,
                  'stage': stages.CONTACTED, 'owner': self.meryem,
                  'telephone': f'+21266222{self._compteur:04d}'}
        champs.update(kw)
        return Lead.objects.create(**champs)

    def _touche(self, lead, *, jours=0, libelle='Appel de suivi',
                cadence='contact', ordre=1, canal=RelanceEtape.Canal.APPEL):
        quand = self.maintenant.replace(hour=10, minute=0) + datetime.timedelta(
            days=jours)
        return RelanceEtape.objects.create(
            company=self.company, lead=lead, cadence=cadence, ordre=ordre,
            due_at=quand, due_date=quand.astimezone(CASA).date(),
            canal=canal, libelle=libelle, cadence_depart=quand)

    def _lancer(self):
        return notifier_relances_dues(
            today=self.maintenant.astimezone(CASA).date())

    def _digests(self):
        return Notification.objects.filter(
            recipient=self.meryem, event_type=EventType.RELANCE_DUE)


class DigestAZeroTests(_Base):
    slug = 'n3-zero'

    def test_zero_touche_due_le_digest_part_quand_meme(self):
        lead = self._lead()
        self._touche(lead, jours=3)  # à venir cette semaine, pas due
        self.assertEqual(self._lancer(), (1, 1))
        digest = self._digests().get()
        self.assertEqual(digest.title, DIGEST_ZERO_TITRE)
        self.assertIn("Aucune relance due aujourd'hui", digest.body)
        self.assertIn('1 touche(s) à venir cette semaine', digest.body)
        self.assertEqual(digest.link, '/crm/cockpit')

    def test_sans_dossier_vivant_rien_ne_part(self):
        """Un commercial dont tous les dossiers sont clos, perdus ou archivés
        n'a rien à suivre : pas de digest à zéro pour lui."""
        self._lead('Signé', stage=stages.SIGNED)
        self._lead('Perdu', perdu=True, motif_perte='Prix')
        self._lead('Archivé', is_archived=True)
        self.assertEqual(self._lancer(), (0, 0))
        self.assertFalse(self._digests().exists())

    def test_idempotent_meme_a_zero(self):
        self._lead()
        self._lancer()
        self.assertEqual(self._lancer(), (0, 1))
        self.assertEqual(self._digests().count(), 1)


class EtapesVisiteEtDevisTests(_Base):
    slug = 'n3-etapes'

    def test_les_etapes_de_visite_et_de_devis_sont_comptees(self):
        self._touche(self._lead('Visite A'),
                     libelle=crm_services.VISITE_CONFIRMATION_LIBELLE,
                     cadence=crm_services.VISITE_CADENCE,
                     ordre=crm_services.VISITE_ORDRE_CONFIRMATION)
        self._touche(self._lead('Visite B'),
                     libelle=crm_services.VISITE_DEBRIEF_LIBELLE,
                     cadence=crm_services.VISITE_CADENCE,
                     ordre=crm_services.VISITE_ORDRE_DEBRIEF)
        self._touche(self._lead('Devis C'),
                     libelle=crm_services.FILET_JOINT_LIBELLE,
                     cadence='generique', ordre=1)
        self._touche(self._lead('Suivi D'))
        self._lancer()
        digest = self._digests().get()
        # Les quatre entrent dans le TOTAL…
        self.assertEqual(digest.title, "4 relance(s) à faire aujourd'hui")
        # …et visite / devis sont ventilés à part.
        self.assertIn('2 étape(s) de visite', digest.body)
        self.assertIn('1 étape(s) de devis', digest.body)

    def test_sans_etape_de_visite_ni_de_devis_pas_de_ventilation(self):
        self._touche(self._lead('Suivi'))
        self._lancer()
        digest = self._digests().get()
        self.assertNotIn('étape(s) de visite', digest.body)
        self.assertNotIn('étape(s) de devis', digest.body)


class JourNonOuvreTests(_Base):
    slug = 'n3-ferie'

    def test_un_jour_ferie_rien_ne_part(self):
        Holiday.objects.create(
            company=self.company, date=MARDI.date(), nom='Férié de test')
        self._touche(self._lead())
        self.assertEqual(self._lancer(), (0, 0))
        self.assertFalse(self._digests().exists())


class DimancheTests(_Base):
    slug = 'n3-dimanche'
    maintenant = DIMANCHE

    def test_le_dimanche_rien_ne_part(self):
        self._touche(self._lead())
        self.assertEqual(self._lancer(), (0, 0))
        self.assertFalse(self._digests().exists())
