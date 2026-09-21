"""CAD33 — [TRANCHÉ 21/09/2026] la préférence du client prime JUSQUE sur le
rendez-vous du dimanche.

L'appel du dimanche 16 h-19 h est le SEUL rendez-vous dominical du Protocole
v3, réservé aux prospects qu'on ne trouve jamais en semaine. C'était un
APPEL, y compris pour un prospect qui avait explicitement coché « WhatsApp
uniquement » : CAD32 avait adapté tous les autres barreaux et laissé
celui-là, faute de décision.

Décision fondateur : **la préférence du client prime**. Sur un lead
`whatsapp_only`, la touche du dimanche naît elle aussi en canal WhatsApp,
dans la même fenêtre 16 h-19 h.

GARDE-FOU : la fenêtre dominicale et l'UNICITÉ de la touche ne changent pas.
C'est le canal, et lui seul, qui suit le client — le nombre de touches est
inchangé.

Le temps est GELÉ.
"""
import datetime

from django.contrib.auth import get_user_model
from django.test import TestCase

from authentication.models import Company
from testkit.time import frozen

from apps.crm import horaires
from apps.crm.models import Lead
from apps.crm.services import calculer_echeances_cadence
from apps.parametres.models import CompanyProfile

User = get_user_model()

#: Mardi 8 septembre 2026, 11 h — jour ouvré, en pleine fenêtre.
DEPART = datetime.datetime(2026, 9, 8, 11, 0, tzinfo=horaires.CASABLANCA)
GEL = datetime.datetime(2026, 9, 7, 7, 0, tzinfo=horaires.CASABLANCA)

#: L'étiquette qui débloque le barreau dominical du suivi après devis (MRY4).
TAG_FAMILLE = 'Décision à plusieurs'


class _Base(TestCase):
    slug = 'cad33'

    def setUp(self):
        gel = frozen(GEL)
        gel.start()
        self.addCleanup(gel.stop)
        self.company = Company.objects.create(
            nom='CAD33 Solaire', slug=f'{self.slug}-a')
        CompanyProfile.objects.get_or_create(company=self.company)
        self.acteur = User.objects.create_user(
            username=f'{self.slug}-resp', password='x',
            role_legacy='responsable', company=self.company)
        self.whatsapp_only = self._lead(
            'Aziz', Lead.ContactPreference.WHATSAPP_ONLY)
        self.temoin = self._lead('Karim', Lead.ContactPreference.PHONE_OK)

    def _lead(self, prenom, preference):
        return Lead.objects.create(
            company=self.company, nom='Benali', prenom=prenom,
            ville='Bouskoura', owner=self.acteur, tags=TAG_FAMILLE,
            contact_preference=preference)

    def _plan(self, lead, cadence='contact'):
        return calculer_echeances_cadence(lead, cadence, DEPART)

    def _dominicales(self, lead, cadence='contact'):
        return [(g, e.astimezone(horaires.CASABLANCA))
                for g, e in self._plan(lead, cadence)
                if getattr(g, 'dimanche_ok', False)]


class LeDimancheSuitLaPreferenceTests(_Base):
    """Le « Done = » : plus AUCUNE touche d'appel, dimanche compris."""

    slug = 'cad33-dimanche'

    def test_la_touche_dominicale_nait_en_WhatsApp(self):
        dominicales = self._dominicales(self.whatsapp_only)
        self.assertEqual(len(dominicales), 1)
        gabarit, _quand = dominicales[0]
        self.assertTrue(horaires.est_un_message(gabarit.canal),
                        gabarit.canal)

    def test_aucune_touche_de_canal_appel_ne_subsiste(self):
        for gabarit, _echeance in self._plan(self.whatsapp_only):
            self.assertTrue(
                horaires.est_un_message(gabarit.canal),
                (gabarit.ordre, gabarit.libelle, gabarit.canal))

    def test_le_nombre_de_touches_est_inchange(self):
        self.assertEqual(len(self._plan(self.whatsapp_only)),
                         len(self._plan(self.temoin)))

    def test_le_temoin_garde_son_appel_du_dimanche(self):
        """Garde négative : sans la préférence, le rendez-vous dominical
        reste un APPEL."""
        gabarit, _quand = self._dominicales(self.temoin)[0]
        self.assertFalse(horaires.est_un_message(gabarit.canal))


class LaFenetreEtLUniciteNeBougentPasTests(_Base):
    """Le garde-fou de la décision."""

    slug = 'cad33-fenetre'

    def test_elle_tombe_toujours_un_dimanche(self):
        _gabarit, quand = self._dominicales(self.whatsapp_only)[0]
        self.assertEqual(quand.weekday(), 6)

    def test_elle_reste_dans_la_fenetre_16h_19h(self):
        gabarit, quand = self._dominicales(self.whatsapp_only)[0]
        self.assertTrue(horaires.est_dans_fenetre(
            quand, self.company, dimanche=True, canal=gabarit.canal))
        self.assertGreaterEqual(quand.time(), horaires.DIMANCHE_DEBUT)
        self.assertLess(quand.time(), horaires.DIMANCHE_FIN)

    def test_elle_tombe_le_MEME_jour_que_pour_le_temoin(self):
        _g1, adapte = self._dominicales(self.whatsapp_only)[0]
        _g2, temoin = self._dominicales(self.temoin)[0]
        self.assertEqual(adapte.date(), temoin.date())

    def test_il_ny_en_a_toujours_QUUNE(self):
        for cadence in ('contact', 'apres_devis'):
            self.assertEqual(
                len(self._dominicales(self.whatsapp_only, cadence)), 1,
                cadence)

    def test_le_dimanche_famille_du_suivi_apres_devis_aussi(self):
        gabarit, quand = self._dominicales(
            self.whatsapp_only, 'apres_devis')[0]
        self.assertTrue(horaires.est_un_message(gabarit.canal))
        self.assertEqual(quand.weekday(), 6)
