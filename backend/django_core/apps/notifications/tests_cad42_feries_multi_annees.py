"""CAD42 — un férié NON récurrent ne bloque que SON année.

Constat de l'audit L3 du 21/09/2026 : « prochain jour ouvré » et « ajouter N
jours ouvrés » chargent PLUSIEURS années de fériés puis ne comparaient que
(mois, jour) — trois Aïd saisis, c'étaient trois dates bloquées CHAQUE
année. ``feries_entre`` faisait déjà la distinction correctement ; les deux
lectures parlent enfin du même calendrier.

La cadence n'utilise pas ces deux fonctions (elle passe par le contrôle
correct à une seule année), mais les délais RH et projet si.
"""
import datetime

from django.test import TestCase

from authentication.models import Company

from apps.notifications.calendar_utils import (
    ajouter_jours_ouvres, feries_entre, is_jour_ouvre, prochain_jour_ouvre,
)
from apps.notifications.models import Holiday

#: Un Aïd SAISI pour 2027 — mercredi 5 mai 2027, jour ouvré de la semaine.
AID_2027 = datetime.date(2027, 5, 5)
#: La même date grégorienne en 2026 et 2028 : elle ne doit rien bloquer.
MEME_JOUR_2026 = datetime.date(2026, 5, 5)
MEME_JOUR_2028 = datetime.date(2028, 5, 5)


class _Base(TestCase):
    slug = 'cad42'

    def setUp(self):
        self.company = Company.objects.create(slug=self.slug, nom=self.slug)

    def _ferie(self, jour, nom='Aïd al-Fitr', recurrent=False):
        return Holiday.objects.create(
            company=self.company, date=jour, nom=nom,
            recurrent_annuel=recurrent)


class UnAidNeBloqueQueSonAnneeTests(_Base):
    slug = 'cad42-aid'

    def setUp(self):
        super().setUp()
        self._ferie(AID_2027)

    def test_il_bloque_bien_SON_jour(self):
        self.assertFalse(is_jour_ouvre(AID_2027, self.company))

    def test_il_ne_bloque_pas_la_meme_date_les_autres_annees(self):
        for jour in (MEME_JOUR_2026, MEME_JOUR_2028):
            with self.subTest(jour=jour):
                self.assertTrue(is_jour_ouvre(jour, self.company))

    def test_prochain_jour_ouvre_ne_saute_pas_la_date_d_une_autre_annee(self):
        """Le vrai défaut : cette fonction charge DEUX années d'un coup."""
        self.assertEqual(
            prochain_jour_ouvre(MEME_JOUR_2026, self.company),
            MEME_JOUR_2026)
        self.assertEqual(
            prochain_jour_ouvre(MEME_JOUR_2028, self.company),
            MEME_JOUR_2028)

    def test_prochain_jour_ouvre_saute_bien_la_date_de_SON_annee(self):
        self.assertEqual(
            prochain_jour_ouvre(AID_2027, self.company),
            AID_2027 + datetime.timedelta(days=1))

    def test_ajouter_jours_ouvres_charge_trois_annees_sans_se_tromper(self):
        """Elle pré-charge année + 2 : c'est là que trois Aïd devenaient
        trois dates mortes par an."""
        veille = MEME_JOUR_2026 - datetime.timedelta(days=1)  # lundi 4 mai
        self.assertEqual(veille.weekday(), 0)
        self.assertEqual(
            ajouter_jours_ouvres(veille, 1, self.company), MEME_JOUR_2026)

    def test_les_deux_lectures_du_calendrier_sont_d_accord(self):
        """``feries_entre`` (correcte depuis toujours) et ``is_jour_ouvre``
        doivent dire la même chose sur les mêmes dates."""
        for jour in (AID_2027, MEME_JOUR_2026, MEME_JOUR_2028):
            with self.subTest(jour=jour):
                self.assertEqual(
                    bool(feries_entre(self.company, jour, jour)),
                    not is_jour_ouvre(jour, self.company))


class UnFerieRECURRENTGardeSonComportementTests(_Base):
    slug = 'cad42-recurrent'

    def test_un_ferie_fixe_recurrent_bloque_bien_toutes_les_annees(self):
        """Anti-régression : la Fête du Travail reste fériée chaque année."""
        self._ferie(datetime.date(2024, 5, 1), nom='Fête du Travail',
                    recurrent=True)
        for annee in (2026, 2027, 2028):
            with self.subTest(annee=annee):
                self.assertFalse(
                    is_jour_ouvre(datetime.date(annee, 5, 1), self.company))

    def test_une_societe_ne_voit_pas_les_feries_d_une_autre(self):
        voisine = Company.objects.create(
            slug=f'{self.slug}-voisine', nom='voisine')
        self._ferie(AID_2027)
        self.assertTrue(is_jour_ouvre(AID_2027, voisine))
