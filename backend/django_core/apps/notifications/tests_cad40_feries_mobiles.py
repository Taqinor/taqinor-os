"""CAD40 — les fêtes MOBILES entrent au calendrier de chaque société.

Constat de l'audit L3 du 21/09/2026 : ``seed_ma_holidays`` excluait
DÉLIBÉRÉMENT les fêtes lunaires et ne posait que 9 fériés fixes ;
``is_jour_ouvre`` ne bloque un jour que s'il existe une ligne ``Holiday`` ; et
aucun crochet de création de société ne posait de férié. Résultat : une
touche de cadence pouvait tomber le jour de l'Aïd. Le dépôt portait pourtant
déjà les 4 fêtes mobiles 2026 dans ``core/calendar.py``.

Les trois garanties verrouillées ici :
  * une société neuve a ses 9 fériés FIXES **et** les fêtes mobiles de
    l'année en cours ;
  * aucune touche de cadence ne se pose un jour d'Aïd SAISI ;
  * **rien n'est calculé** — une année dont les dates lunaires sont inconnues
    n'en reçoit aucune, et un rappel français le dit.

Le temps est GELÉ : « l'année en cours » est exactement ce qu'une horloge
vivante rend instable.
"""
import datetime

from django.test import TestCase

from authentication.models import Company

from apps.crm import horaires
from apps.notifications.calendar_utils import (
    is_jour_ouvre, rappel_fetes_mobiles,
)
from apps.notifications.models import Holiday
from apps.notifications.signup_hooks import seed_jours_feries
from apps.parametres.models import CompanyProfile
from core.calendar import movable_holidays

#: Lundi 21 septembre 2026, 10 h à Casablanca. L'année en cours des tests est
#: donc 2026 — la seule pour laquelle `core.calendar` connaît des dates.
MAINTENANT = datetime.datetime(2026, 9, 21, 10, 0, tzinfo=horaires.CASABLANCA)

#: Les 9 fériés fixes, tels que le seeder les pose (récurrents annuels).
FIXES_ATTENDUS = 9


def _company(slug):
    company = Company.objects.create(slug=slug, nom=slug)
    CompanyProfile.objects.create(company=company)
    return company


class _Base(TestCase):
    slug = 'cad40'

    def setUp(self):
        from testkit.time import frozen

        gel = frozen(MAINTENANT)
        gel.start()
        self.addCleanup(gel.stop)
        self.company = _company(self.slug)


class SocieteNeuveTests(_Base):
    slug = 'cad40-neuve'

    def test_une_societe_neuve_a_ses_9_fixes_et_les_mobiles_de_l_annee(self):
        seed_jours_feries(self.company)

        fixes = Holiday.objects.filter(
            company=self.company, recurrent_annuel=True)
        mobiles = Holiday.objects.filter(
            company=self.company, recurrent_annuel=False)
        attendues = movable_holidays(2026)

        self.assertEqual(fixes.count(), FIXES_ATTENDUS)
        self.assertTrue(attendues, 'core.calendar doit connaître 2026')
        self.assertEqual(
            {h.date for h in mobiles}, set(attendues))

    def test_les_fetes_mobiles_ne_sont_PAS_recurrentes(self):
        """Une date lunaire ne retombe jamais au même jour grégorien : la
        cocher « récurrente » la figerait pour toujours (CAD42)."""
        seed_jours_feries(self.company)
        for jour in movable_holidays(2026):
            with self.subTest(jour=jour):
                ligne = Holiday.objects.get(
                    company=self.company, date=jour)
                self.assertFalse(ligne.recurrent_annuel)

    def test_le_seed_est_idempotent(self):
        seed_jours_feries(self.company)
        avant = Holiday.objects.filter(company=self.company).count()
        seed_jours_feries(self.company)
        self.assertEqual(
            Holiday.objects.filter(company=self.company).count(), avant)

    def test_une_societe_ne_recoit_pas_les_feries_d_une_autre(self):
        voisine = _company(f'{self.slug}-voisine')
        seed_jours_feries(self.company)
        self.assertEqual(
            Holiday.objects.filter(company=voisine).count(), 0)


class AucuneToucheLeJourDeLAidTests(_Base):
    slug = 'cad40-aid'

    def test_une_touche_ne_se_pose_pas_un_jour_d_aid_saisi(self):
        """Le second Done : le moteur du temps VOIT la fête saisie."""
        seed_jours_feries(self.company)
        # Aïd al-Adha 2026 : mercredi 27 mai, jour ouvré au sens de la
        # semaine — c'est la ligne Holiday qui doit le fermer.
        aid = datetime.date(2026, 5, 27)
        self.assertIn(aid, movable_holidays(2026))
        self.assertEqual(aid.weekday(), 2)

        self.assertFalse(is_jour_ouvre(aid, self.company))
        self.assertIsNone(
            horaires.fenetre_du_jour(aid, self.company))
        # La touche calculée ce jour-là glisse au premier jour rouvert.
        quand = datetime.datetime.combine(
            aid, datetime.time(10, 0), tzinfo=horaires.CASABLANCA)
        creneau = horaires.prochain_creneau_appel(quand, self.company)
        self.assertGreater(creneau.date(), aid)
        self.assertTrue(is_jour_ouvre(creneau.date(), self.company))

    def test_sans_fete_saisie_le_jour_reste_ouvert(self):
        """Anti-faux-vert : c'est bien la LIGNE qui ferme le jour, pas une
        règle devinée quelque part."""
        aid = datetime.date(2026, 5, 27)
        self.assertTrue(is_jour_ouvre(aid, self.company))


class RienNEstCalculeTests(_Base):
    slug = 'cad40-rappel'

    def test_une_annee_inconnue_ne_recoit_AUCUNE_date_devinee(self):
        inconnues = movable_holidays(2031)
        self.assertEqual(inconnues, {})

    def test_le_rappel_parle_quand_l_annee_n_est_pas_saisie(self):
        message = rappel_fetes_mobiles(self.company, 2031)
        self.assertIsInstance(message, str)
        self.assertIn('2031', message)
        self.assertIn('Fêtes mobiles', message)

    def test_le_rappel_se_tait_une_fois_l_annee_saisie(self):
        Holiday.objects.create(
            company=self.company, date=datetime.date(2031, 1, 20),
            nom='Aïd al-Fitr', recurrent_annuel=False)
        self.assertIsNone(rappel_fetes_mobiles(self.company, 2031))

    def test_un_ferie_FIXE_recurrent_ne_fait_pas_taire_le_rappel(self):
        """Neuf lignes récurrentes ne prouvent pas que les fêtes lunaires de
        l'année sont saisies."""
        seed_jours_feries(self.company)
        self.assertIsInstance(rappel_fetes_mobiles(self.company, 2031), str)

    def test_sans_annee_le_rappel_regarde_l_annee_en_cours(self):
        seed_jours_feries(self.company)
        self.assertIsNone(rappel_fetes_mobiles(self.company))
