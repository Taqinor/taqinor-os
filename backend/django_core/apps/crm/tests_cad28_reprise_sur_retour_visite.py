"""CAD28 — la reprise du protocole part du RETOUR de visite, pas de la date
prévue.

La suspension calait la reprise sur la date PRÉVUE de la visite (date prévue
+ `VISITE_REPRISE_JOURS`). Une visite reportée à la dernière minute sans mise
à jour de la fiche laissait donc la relance repartir quand même : le client
recevait un message « suite à notre visite » avant que quiconque soit passé
chez lui.

Le retour de visite, lui, est déjà saisi (`appliquer_retour_visite`). C'est
LUI qui recale désormais la touche pendante du protocole, par la mécanique
existante — jamais une seconde.

GARDE-FOUS tenus et testés :
  * on ne tire JAMAIS la relance en avant : un retour tardif ne doit pas
    accélérer une relance déjà posée plus loin ;
  * aucune touche n'est créée quand il n'y en a pas (ce serait un redémarrage
    de cadence) ;
  * le délai de deux jours n'est pas rendu réglable — c'est la place du
    débrief plus un jour.

Horloge FIXE partout : « aujourd'hui » ne doit pas dépendre du jour de la CI.
"""
import datetime

from django.contrib.auth import get_user_model
from django.test import TestCase

from testkit.time import frozen

from apps.crm import horaires, services
from apps.crm.models import Lead, LeadActivity, RelanceEtape
from apps.parametres.models import CompanyProfile
from apps.parametres.models_relance import CadenceRelanceEtape
from authentication.models import Company

User = get_user_model()

#: Jeudi 17 septembre 2026 — la date PRÉVUE de la visite.
VISITE_PREVUE_LE = datetime.date(2026, 9, 17)
#: La visite a réellement eu lieu TROIS JOURS plus tard : dimanche 20 ? non —
#: on prend le mardi 22, un jour ouvré, pour que le recalage d'horaires ne
#: déplace pas le JOUR et ne masque pas ce que le test mesure.
RETOUR_LE = datetime.date(2026, 9, 22)
RETOUR_A = datetime.datetime(2026, 9, 22, 11, 0,
                             tzinfo=horaires.CASABLANCA)


def _company(slug, nom):
    company = Company.objects.create(nom=nom, slug=slug)
    CompanyProfile.objects.get_or_create(company=company)
    return company


class _Base(TestCase):
    slug = 'cad28'

    def setUp(self):
        gel = frozen(RETOUR_A)
        gel.start()
        self.addCleanup(gel.stop)
        self.company = _company(f'{self.slug}-a', 'CAD28 Solaire')
        CadenceRelanceEtape.seed_defaults(self.company)
        self.owner = User.objects.create_user(
            username=f'{self.slug}-owner', password='x',
            company=self.company, first_name='Nadia')
        self.acteur = User.objects.create_user(
            username=f'{self.slug}-acteur', password='x',
            company=self.company, role_legacy='responsable')
        self.lead = Lead.objects.create(
            company=self.company, nom='Bennani', prenom='Karim',
            ville='Bouskoura', owner=self.owner)

    def _touche_du_plan(self, jour):
        """Une touche du GABARIT après-devis, ouverte, due le ``jour`` dit."""
        due_at = datetime.datetime.combine(
            jour, datetime.time(9, 0), tzinfo=horaires.CASABLANCA)
        return RelanceEtape.objects.create(
            company=self.company, lead=self.lead, cadence='apres_devis',
            ordre=1, canal=RelanceEtape.Canal.WHATSAPP,
            libelle="Le PDF s'ouvre bien ?", template_cle='j1_pdf',
            due_date=jour, due_at=due_at, cadence_depart=RETOUR_A)

    def _reprise_attendue(self):
        """La date que le moteur d'horaires produit pour « retour + délai »
        à 9 h — jamais une date codée en dur."""
        vise = datetime.datetime.combine(
            RETOUR_LE + datetime.timedelta(
                days=services.VISITE_REPRISE_JOURS),
            datetime.time(9, 0), tzinfo=horaires.CASABLANCA)
        return horaires.prochain_creneau_appel(
            vise, self.company, canal='whatsapp'
        ).astimezone(horaires.CASABLANCA).date()


class LaRepriseSuitLeRetourTests(_Base):
    """Le « Done = » de la tâche."""

    slug = 'cad28-retour'

    def test_un_retour_saisi_trois_jours_apres_recale_la_reprise(self):
        """La suspension avait posé la reprise sur la date PRÉVUE ; le
        retour, saisi trois jours plus tard, la repousse d'autant."""
        suspendue = VISITE_PREVUE_LE + datetime.timedelta(
            days=services.VISITE_REPRISE_JOURS)
        touche = self._touche_du_plan(suspendue)
        self.assertEqual(touche.due_date, suspendue)

        services.appliquer_retour_visite(
            self.lead, self.acteur, {'notes': 'Toiture accessible.'})

        touche.refresh_from_db()
        self.assertEqual(touche.due_date, self._reprise_attendue())
        self.assertGreater(touche.due_date, suspendue)

    def test_la_touche_garde_sa_place_dans_le_protocole(self):
        """Garde-fou : on DÉPLACE, on ne redémarre pas — même ordre, même
        libellé, toujours à faire."""
        touche = self._touche_du_plan(
            VISITE_PREVUE_LE + datetime.timedelta(
                days=services.VISITE_REPRISE_JOURS))
        services.appliquer_retour_visite(
            self.lead, self.acteur, {'notes': 'RAS.'})
        touche.refresh_from_db()
        self.assertEqual(touche.statut, RelanceEtape.Statut.A_FAIRE)
        self.assertEqual(touche.ordre, 1)
        self.assertEqual(touche.libelle, "Le PDF s'ouvre bien ?")
        self.assertEqual(
            self.lead.relance_etapes.filter(
                statut=RelanceEtape.Statut.ANNULEE).count(), 0)

    def test_lancre_de_la_cadence_glisse_avec_la_touche(self):
        """CKP2 — sans l'ancre, la touche SUIVANTE renaîtrait à sa date
        d'origine, c'est-à-dire avant la visite."""
        touche = self._touche_du_plan(
            VISITE_PREVUE_LE + datetime.timedelta(
                days=services.VISITE_REPRISE_JOURS))
        avant = touche.cadence_depart
        services.appliquer_retour_visite(
            self.lead, self.acteur, {'notes': 'RAS.'})
        touche.refresh_from_db()
        self.assertGreater(touche.cadence_depart, avant)

    def test_le_chatter_dit_pourquoi_la_relance_a_bouge(self):
        self._touche_du_plan(
            VISITE_PREVUE_LE + datetime.timedelta(
                days=services.VISITE_REPRISE_JOURS))
        services.appliquer_retour_visite(
            self.lead, self.acteur, {'notes': 'RAS.'})
        notes = LeadActivity.objects.filter(
            lead=self.lead, kind=LeadActivity.Kind.NOTE)
        self.assertTrue(
            any('retour de visite' in (n.body or '') for n in notes),
            [n.body for n in notes])


class LesGardeFousTests(_Base):
    """Ce que la reprise ne fait JAMAIS."""

    slug = 'cad28-gardes'

    def test_une_touche_deja_posterieure_nest_pas_tiree_en_avant(self):
        loin = self._touche_du_plan(RETOUR_LE + datetime.timedelta(days=30))
        avant = loin.due_date
        services.appliquer_retour_visite(
            self.lead, self.acteur, {'notes': 'RAS.'})
        loin.refresh_from_db()
        self.assertEqual(loin.due_date, avant)

    def test_sans_touche_pendante_rien_nest_CREE(self):
        """Créer une touche ici serait un redémarrage de cadence."""
        avant = self.lead.relance_etapes.filter(
            cadence='apres_devis').exclude(
            libelle__in=services._LIBELLES_VISITE).count()
        self.assertEqual(avant, 0)
        services.appliquer_retour_visite(
            self.lead, self.acteur, {'notes': 'RAS.'})
        apres = self.lead.relance_etapes.filter(
            cadence='apres_devis').exclude(
            libelle__in=services._LIBELLES_VISITE).count()
        self.assertEqual(apres, 0)

    def test_le_delai_de_reprise_reste_celui_du_debrief(self):
        """Garde-fou explicite de la tâche : le délai n'est PAS rendu
        réglable — deux jours, la place du débrief plus un."""
        self.assertEqual(services.VISITE_REPRISE_JOURS, 2)

    def test_un_lead_quon_ne_relance_plus_ne_bouge_pas(self):
        touche = self._touche_du_plan(
            VISITE_PREVUE_LE + datetime.timedelta(
                days=services.VISITE_REPRISE_JOURS))
        avant = touche.due_date
        self.lead.ne_plus_contacter = True
        self.lead.save(update_fields=['ne_plus_contacter'])
        services.appliquer_retour_visite(
            self.lead, self.acteur, {'notes': 'RAS.'})
        touche.refresh_from_db()
        self.assertEqual(touche.due_date, avant)

    def test_le_debrief_lui_meme_nest_jamais_la_touche_recalee(self):
        """Les étapes de VISITE ne sont pas des barreaux du protocole : la
        reprise ne doit jamais les prendre pour cible."""
        self._touche_du_plan(
            VISITE_PREVUE_LE + datetime.timedelta(
                days=services.VISITE_REPRISE_JOURS))
        debrief = services.appliquer_retour_visite(
            self.lead, self.acteur, {'notes': 'RAS.'})
        self.assertIsNotNone(debrief)
        self.assertIn(debrief.libelle, services._LIBELLES_VISITE)
        self.assertLess(debrief.due_date, self._reprise_attendue())
