"""CAD38 — la fenêtre de Ramadan par défaut vaut 09 h-15 h, pas 10 h-14 h.

Constat de l'audit L3 du 21/09/2026 : les défauts du modèle disaient
10 h-14 h, deux heures plus étroit que la référence nationale. Le Maroc
applique l'horaire continu 09 h-15 h pendant le Ramadan dans les
administrations, établissements publics et collectivités (Ministère de la
Transition numérique et de la Réforme de l'administration, annonce du
10/02/2026 ; relais maroc-hebdo, puis medias24 du 10/02/2026).

Décision fondateur du 21/09/2026 (CAD39) : cette fenêtre reste COMMUNE aux
appels et aux messages — aucun découpage par canal, aucune fenêtre du soir
après le ftour.

Garde-fou vérifié ici aussi : **aucun effet tant que les dates de Ramadan ne
sont pas saisies** (CAD37) — un profil sans dates garde ses horaires
normaux.
"""
import datetime

from django.test import SimpleTestCase, TestCase

from authentication.models import Company

from apps.crm import horaires
from apps.parametres.models import CompanyProfile

#: Mercredi 18 février 2026 → jeudi 19 mars 2026 : la période saisie par la
#: société dans ces tests. Ce sont des dates SAISIES, jamais calculées (le
#: calendrier hégirien glisse ; les dates officielles sont annoncées chaque
#: année).
RAMADAN_DEBUT = datetime.date(2026, 2, 18)
RAMADAN_FIN = datetime.date(2026, 3, 19)
#: Un jeudi en plein milieu de la période — jour ouvré, sans pause du
#: vendredi qui viendrait brouiller la lecture.
EN_RAMADAN = datetime.date(2026, 3, 5)
#: Un jeudi hors période, deux mois plus tard.
HORS_RAMADAN = datetime.date(2026, 5, 7)


class DefautsDuModeleTests(SimpleTestCase):
    """Les défauts DÉCLARÉS — lisibles sans base."""

    def _defaut(self, champ):
        return CompanyProfile._meta.get_field(champ).default

    def test_le_ramadan_ouvre_a_09h_et_ferme_a_15h(self):
        self.assertEqual(self._defaut('ramadan_appel_debut'),
                         datetime.time(9, 0))
        self.assertEqual(self._defaut('ramadan_appel_fin'),
                         datetime.time(15, 0))

    def test_les_dates_de_ramadan_restent_NON_devinees(self):
        """CAD37 : rien ne s'applique tant qu'un humain n'a pas saisi les
        deux dates — le calendrier hégirien n'est jamais calculé ici."""
        for champ in ('ramadan_debut', 'ramadan_fin'):
            declare = CompanyProfile._meta.get_field(champ)
            self.assertTrue(declare.null, champ)
            self.assertFalse(declare.has_default(), champ)


class FenetreRendueTests(TestCase):
    """Ce que le MOTEUR rend réellement, période saisie."""

    def setUp(self):
        self.company = Company.objects.create(slug='cad38', nom='cad38')
        self.profil = CompanyProfile.objects.create(
            company=self.company,
            ramadan_debut=RAMADAN_DEBUT, ramadan_fin=RAMADAN_FIN)

    def test_la_fenetre_rendue_en_ramadan_est_09h_15h(self):
        debut, fin, pause = horaires.fenetre_du_jour(EN_RAMADAN, self.company)
        self.assertEqual(debut, datetime.time(9, 0))
        self.assertEqual(fin, datetime.time(15, 0))
        self.assertIsNone(pause)

    def test_elle_est_la_MEME_pour_les_messages_et_pour_les_appels(self):
        """Décision du 21/09/2026 : fenêtre commune, pas de split par canal —
        le message ne part pas à 08:30 pendant le mois."""
        appel = horaires.fenetre_du_jour(
            EN_RAMADAN, self.company, canal='appel')
        message = horaires.fenetre_du_jour(
            EN_RAMADAN, self.company, canal='whatsapp')
        self.assertEqual(appel, message)
        self.assertEqual(appel[0], datetime.time(9, 0))

    def test_hors_periode_les_horaires_normaux_reviennent(self):
        debut, fin, _pause = horaires.fenetre_du_jour(
            HORS_RAMADAN, self.company)
        self.assertEqual(debut, datetime.time(9, 0))
        self.assertEqual(fin, datetime.time(20, 0))

    def test_sans_dates_saisies_le_ramadan_ne_s_applique_PAS(self):
        """Garde-fou de CAD37 : deux dates vides = hors Ramadan."""
        autre = Company.objects.create(slug='cad38-vide', nom='cad38-vide')
        CompanyProfile.objects.create(company=autre)
        _debut, fin, _pause = horaires.fenetre_du_jour(EN_RAMADAN, autre)
        self.assertEqual(fin, datetime.time(20, 0))

    def test_une_societe_qui_a_edite_sa_fenetre_la_garde(self):
        """Le champ reste éditable par société : le défaut n'écrase rien."""
        self.profil.ramadan_appel_debut = datetime.time(10, 30)
        self.profil.ramadan_appel_fin = datetime.time(14, 30)
        self.profil.save(update_fields=['ramadan_appel_debut',
                                        'ramadan_appel_fin'])
        debut, fin, _pause = horaires.fenetre_du_jour(
            EN_RAMADAN, self.company)
        self.assertEqual(debut, datetime.time(10, 30))
        self.assertEqual(fin, datetime.time(14, 30))
