"""Une visite SANS devis met le devis EN ATTENTE — décision fondateur du
24/09/2026.

Reda, 24/09/2026 : « après l'appel il n'y a plus rien à faire, sauf organiser
la visite, et même après ça rien ne se passe ». Deux trous, prouvés fermés :

* **planification** — l'étape « Préparer et envoyer le devis (ou fixer un
  rappel) » posée par le filet « client joint » restait ouverte, orpheline,
  datée de demain, pendant que la visite était calée plus tard ; et son
  « Fait » sans issue valait « devis parti ». Elle est désormais ANNULÉE
  (statut moteur) quand aucun devis n'est parti, et la note de planification
  le dit — une phrase de plus, jamais une seconde note. Avec un devis envoyé,
  rien ne change ;
* **retour terrain** — sans devis parti, la suite n'est plus un débrief
  « rappeler le client » (il n'y a encore rien à conclure) mais la tâche de
  PRODUCTION « Préparer et envoyer le devis » : demain, ou au moment convenu
  devant le client. Le débrief posé à la planification est annulé, la note du
  retour dit la suite et sa date. Avec un devis envoyé (ou un devis « à
  modifier »), le comportement d'avant est intact.

Horloge FIXE : mercredi 23/09/2026, 10 h à Casablanca.
"""
import datetime
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.utils import timezone

from authentication.models import Company
from testkit.time import frozen

from apps.crm import horaires, services, stages
from apps.crm.models import Client, Lead, RelanceEtape
from apps.parametres.models import CompanyProfile
from apps.parametres.models_relance import CADENCES_DEFAUT, CadenceRelanceEtape

User = get_user_model()

GEL = datetime.datetime(2026, 9, 23, 10, 0, tzinfo=horaires.CASABLANCA)
#: Lundi 28/09/2026 : la veille et le lendemain restent des jours de semaine.
VISITE_LE = datetime.date(2026, 9, 28)

A_FAIRE = RelanceEtape.Statut.A_FAIRE
ANNULEE = RelanceEtape.Statut.ANNULEE
DEVIS = services.FILET_JOINT_LIBELLE


class _Base(TestCase):
    slug = 'vsd'

    def setUp(self):
        gel = frozen(GEL)
        gel.start()
        self.addCleanup(gel.stop)
        self.company = Company.objects.create(
            nom=f'{self.slug} Solaire', slug=self.slug)
        CompanyProfile.objects.get_or_create(company=self.company)
        for cadence in CADENCES_DEFAUT:
            CadenceRelanceEtape.cadence_pour(self.company, cadence)
        self.acteur = User.objects.create_user(
            username=f'{self.slug}-resp', password='x',
            role_legacy='responsable', company=self.company)
        self.lead = Lead.objects.create(
            company=self.company, nom='Bennani', prenom='Karim',
            stage=stages.CONTACTED, owner=self.acteur,
            telephone='+212661000888')

    def _devis_envoye(self):
        from apps.ventes.models import Devis

        client = Client.objects.create(
            company=self.company, nom='Bennani',
            email=f'{self.slug}@example.com')
        return Devis.objects.create(
            company=self.company, reference=f'DEV-{self.slug.upper()}-1',
            client=client, lead=self.lead, statut=Devis.Statut.ENVOYE,
            taux_tva=Decimal('20.00'),
            date_envoi=GEL - datetime.timedelta(days=5))

    def _etape_devis_ouverte(self):
        """L'étape que le filet « client joint » pose après un appel."""
        demain = GEL + datetime.timedelta(days=1)
        return RelanceEtape.objects.create(
            company=self.company, lead=self.lead, cadence='generique',
            ordre=1, canal=RelanceEtape.Canal.APPEL, libelle=DEVIS,
            due_at=demain, due_date=demain.date(),
            note='Posée automatiquement : aucune autre relance ouverte.')

    def _ouvertes(self, libelle):
        return self.lead.relance_etapes.filter(libelle=libelle,
                                               statut=A_FAIRE)

    def _notes(self, debut):
        return self.lead.activites.filter(body__startswith=debut)

    def _echeance_devis(self, jours):
        """La date que ``poser_etape_preparer_devis`` vise : ``jours`` après
        maintenant, recalée sur le prochain créneau d'appel de la société."""
        vise = timezone.now() + datetime.timedelta(days=jours)
        return horaires.prochain_creneau_appel(
            vise, self.company, canal=RelanceEtape.Canal.APPEL,
        ).astimezone(horaires.CASABLANCA).date()


class PlanificationSansDevisTests(_Base):
    slug = 'vsd-plan'

    def test_la_visite_met_l_etape_devis_en_attente(self):
        etape = self._etape_devis_ouverte()

        services.appliquer_visite_planifiee(
            self.lead, self.acteur, VISITE_LE, commercial_nom='Youssef')

        etape.refresh_from_db()
        self.assertEqual(etape.statut, ANNULEE)
        self.assertEqual(etape.note, services.NOTE_DEVIS_APRES_VISITE)
        self.assertIsNone(etape.traite_par)
        # UNE note, qui le dit (après la mention CAD123).
        note = self._notes('Visite technique planifiée').get()
        self.assertIn(services.MENTION_VISITE_SANS_DEVIS, note.body)
        self.assertIn(services.MENTION_DEVIS_APRES_VISITE, note.body)
        self.assertIsNone(note.user)
        # Les deux gestes du rendez-vous sont là ; plus aucune étape devis.
        self.assertEqual(self._ouvertes(DEVIS).count(), 0)
        self.assertEqual(
            self._ouvertes(services.VISITE_DEBRIEF_LIBELLE).count(), 1)

    def test_replanifier_n_annule_rien_de_plus_et_ne_le_redit_pas(self):
        self._etape_devis_ouverte()
        services.appliquer_visite_planifiee(self.lead, self.acteur, VISITE_LE)
        services.appliquer_visite_planifiee(
            self.lead, self.acteur, VISITE_LE + datetime.timedelta(days=2))

        self.assertEqual(self.lead.relance_etapes.filter(
            libelle=DEVIS, statut=ANNULEE).count(), 1)
        notes = list(self._notes('Visite technique planifiée')
                     .order_by('created_at', 'pk'))
        self.assertEqual(len(notes), 2)
        self.assertIn(services.MENTION_DEVIS_APRES_VISITE, notes[0].body)
        self.assertNotIn(services.MENTION_DEVIS_APRES_VISITE, notes[1].body)

    def test_avec_un_devis_envoye_l_etape_devis_reste(self):
        self._devis_envoye()
        etape = self._etape_devis_ouverte()

        services.appliquer_visite_planifiee(self.lead, self.acteur, VISITE_LE)

        etape.refresh_from_db()
        self.assertEqual(etape.statut, A_FAIRE)
        note = self._notes('Visite technique planifiée').get()
        self.assertNotIn(services.MENTION_DEVIS_APRES_VISITE, note.body)

    def test_un_devis_parti_hors_erp_compte_aussi(self):
        # TREADMILL-1538 — le suivi de proposition a démarré sans objet devis
        # (devis envoyé par WhatsApp, hors ERP) : un devis EST parti.
        RelanceEtape.objects.create(
            company=self.company, lead=self.lead, cadence='apres_devis',
            ordre=1, canal=RelanceEtape.Canal.WHATSAPP,
            libelle="Le PDF s'ouvre bien ?", statut=RelanceEtape.Statut.FAIT,
            due_at=GEL - datetime.timedelta(days=3),
            due_date=(GEL - datetime.timedelta(days=3)).date(),
            traite_le=GEL - datetime.timedelta(days=3))
        etape = self._etape_devis_ouverte()

        services.appliquer_visite_planifiee(self.lead, self.acteur, VISITE_LE)

        etape.refresh_from_db()
        self.assertEqual(etape.statut, A_FAIRE)


class RetourSansDevisTests(_Base):
    slug = 'vsd-retour'

    RETOUR = {'notes': 'Toiture saine, compteur à déplacer.',
              'commentaires_photos': [], 'nb_photos': 0}

    def test_la_suite_du_retour_est_de_preparer_le_devis(self):
        services.appliquer_visite_planifiee(self.lead, self.acteur, VISITE_LE)
        debrief = self._ouvertes(services.VISITE_DEBRIEF_LIBELLE).get()

        etape = services.appliquer_retour_visite(
            self.lead, self.acteur, self.RETOUR, auteur='Youssef')

        debrief.refresh_from_db()
        self.assertEqual(debrief.statut, ANNULEE)
        self.assertEqual(debrief.note, services.NOTE_RETOUR_SANS_DEVIS)
        self.assertIsNone(debrief.traite_par)
        self.assertEqual(etape.libelle, DEVIS)
        self.assertEqual(etape.statut, A_FAIRE)
        self.assertEqual(etape.canal, RelanceEtape.Canal.APPEL)
        self.assertEqual(etape.due_date, self._echeance_devis(1))
        self.assertEqual(self._ouvertes(DEVIS).count(), 1)
        self.assertFalse(self.lead.relance_etapes.filter(
            libelle__in=(services.VISITE_DEBRIEF_LIBELLE,
                         services.VISITE_DEVIS_LIBELLE),
            statut=A_FAIRE).exists())
        # Le funnel ne bouge pas : c'est une tâche, pas un devis parti.
        self.lead.refresh_from_db()
        self.assertEqual(self.lead.stage, stages.CONTACTED)

    def test_une_seule_note_qui_dit_la_suite_et_sa_date(self):
        etape = services.appliquer_retour_visite(
            self.lead, self.acteur, self.RETOUR)

        note = self._notes('Visite technique terminée').get()
        self.assertIn('Toiture saine, compteur à déplacer.', note.body)
        self.assertTrue(note.body.endswith(
            'Suite : préparer et envoyer le devis (pour le '
            f'{etape.due_date:%d/%m/%Y}).'), note.body)
        self.assertIsNone(note.user)
        # Pas de seconde note « Retour de visite technique : étape posée ».
        self.assertFalse(self._notes('Retour de visite technique').exists())
        self.lead.refresh_from_db()
        self.assertTrue(self.lead.visite_effectuee)
        self.assertEqual(self.lead.relance_date, etape.due_date)

    def test_cette_semaine_cale_l_etape_devis_sur_le_moment_convenu(self):
        etape = services.appliquer_retour_visite(
            self.lead, self.acteur, self.RETOUR,
            qualification={'devis': 'convient', 'rappel': 'cette_semaine'})
        self.assertEqual(etape.libelle, DEVIS)
        self.assertEqual(etape.due_date, self._echeance_devis(3))

    def test_une_etape_devis_deja_ouverte_n_est_ni_doublee_ni_deplacee(self):
        ouverte = self._etape_devis_ouverte()
        avant = ouverte.due_date

        etape = services.appliquer_retour_visite(
            self.lead, self.acteur, self.RETOUR)

        self.assertEqual(etape.pk, ouverte.pk)
        self.assertEqual(self._ouvertes(DEVIS).count(), 1)
        etape.refresh_from_db()
        self.assertEqual(etape.due_date, avant)

    def test_un_devis_a_modifier_garde_son_etape(self):
        services.appliquer_retour_visite(
            self.lead, self.acteur, self.RETOUR,
            qualification={'devis': 'a_modifier',
                           'devis_details': 'Ajouter une batterie'})
        self.assertEqual(
            self._ouvertes(services.VISITE_DEVIS_LIBELLE).count(), 1)
        self.assertEqual(self._ouvertes(DEVIS).count(), 0)

    def test_avec_un_devis_envoye_le_debrief_reste_la_suite(self):
        self._devis_envoye()
        services.appliquer_visite_planifiee(self.lead, self.acteur, VISITE_LE)

        etape = services.appliquer_retour_visite(
            self.lead, self.acteur, self.RETOUR)

        self.assertEqual(etape.libelle, services.VISITE_DEBRIEF_LIBELLE)
        self.assertEqual(etape.statut, A_FAIRE)
        self.assertEqual(self._ouvertes(DEVIS).count(), 0)
        note = self._notes('Visite technique terminée').get()
        self.assertNotIn('Suite : préparer et envoyer le devis', note.body)

    def test_lead_perdu_chatter_seul(self):
        self.lead.perdu = True
        self.lead.save(update_fields=['perdu'])

        self.assertIsNone(services.appliquer_retour_visite(
            self.lead, self.acteur, self.RETOUR))
        self.assertFalse(self.lead.relance_etapes.filter(
            statut=A_FAIRE).exists())
        self.assertTrue(self._notes('Visite technique terminée').exists())
