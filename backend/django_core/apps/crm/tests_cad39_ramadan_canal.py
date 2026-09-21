"""CAD39 — la fenêtre de Ramadan est COMMUNE aux deux canaux : un CHOIX daté.

Constat de l'audit L3 du 21/09/2026 : le bloc Ramadan de ``fenetre_du_jour``
retourne AVANT ``_ouverture(profil, canal)``, donc le découpage
messages 08:30 / appels 09:00 est inatteignable pendant le mois — et un test
verrouillait ce comportement sans dire que c'en était un.

**Décision fondateur du 21/09/2026** : la fenêtre de Ramadan reste COMMUNE
aux appels et aux messages, et vaut **09 h-15 h** (référence nationale,
CAD38) ; **aucune fenêtre du soir n'est ouverte** — les WhatsApp se tapent à
la main, on ne demande à personne de travailler après le ftour. La touche
dominicale rentre elle aussi dans cette fenêtre (CAD41).

Ce module assert les deux moitiés du Done : 09:00-15:00, et l'absence de tout
créneau après 15 h.
"""
import datetime

from django.test import TestCase

from authentication.models import Company

from apps.crm import horaires
from apps.parametres.models import CompanyProfile

#: Période SAISIE par la société (jamais calculée : le calendrier hégirien
#: glisse, les dates officielles sont annoncées chaque année).
RAMADAN_DEBUT = datetime.date(2027, 2, 8)
RAMADAN_FIN = datetime.date(2027, 3, 9)
#: Mardi 9 février 2027 — jour ouvré, en plein mois, hors vendredi.
MARDI = datetime.date(2027, 2, 9)
#: Vendredi 12 février 2027 — pour vérifier que la pause de prière ne vient
#: pas trouer une fenêtre déjà courte.
VENDREDI = datetime.date(2027, 2, 12)


def _quand(jour, heure, minute=0):
    return datetime.datetime.combine(
        jour, datetime.time(heure, minute), tzinfo=horaires.CASABLANCA)


class FenetreCommuneTests(TestCase):
    def setUp(self):
        self.company = Company.objects.create(slug='cad39', nom='cad39')
        CompanyProfile.objects.create(
            company=self.company,
            ramadan_debut=RAMADAN_DEBUT, ramadan_fin=RAMADAN_FIN)

    def test_la_fenetre_vaut_09h_15h(self):
        self.assertEqual(
            horaires.fenetre_du_jour(MARDI, self.company),
            (datetime.time(9, 0), datetime.time(15, 0), None))

    def test_appels_et_messages_partagent_EXACTEMENT_la_meme_fenetre(self):
        appel = horaires.fenetre_du_jour(MARDI, self.company, canal='appel')
        for canal in ('whatsapp', 'email', 'WhatsApp', None):
            with self.subTest(canal=canal):
                self.assertEqual(
                    horaires.fenetre_du_jour(
                        MARDI, self.company, canal=canal),
                    appel)

    def test_aucun_creneau_apres_15h(self):
        """La moitié « pas de soirée » du Done : à 15 h le mois est fermé, et
        rien ne rouvre après le ftour."""
        for heure in (15, 16, 18, 19, 21, 23):
            with self.subTest(heure=heure):
                self.assertFalse(
                    horaires.est_dans_fenetre(
                        _quand(MARDI, heure), self.company))
                self.assertFalse(
                    horaires.est_dans_fenetre(
                        _quand(MARDI, heure), self.company, canal='whatsapp'))

    def test_un_instant_apres_15h_bascule_au_lendemain_9h(self):
        self.assertEqual(
            horaires.prochain_creneau_appel(
                _quand(MARDI, 19), self.company),
            _quand(datetime.date(2027, 2, 10), 9))

    def test_un_message_ne_part_plus_a_08h30_pendant_le_mois(self):
        """Hors Ramadan un WhatsApp peut partir dès 08:30 ; pendant le mois
        la journée ENTIÈRE se déplace, donc pas avant 09:00."""
        self.assertFalse(
            horaires.est_dans_fenetre(
                _quand(MARDI, 8, 30), self.company, canal='whatsapp'))
        self.assertEqual(
            horaires.prochain_creneau_appel(
                _quand(MARDI, 8, 30), self.company, canal='whatsapp'),
            _quand(MARDI, 9))

    def test_la_pause_du_vendredi_ne_troue_pas_la_fenetre_du_mois(self):
        self.assertEqual(
            horaires.fenetre_du_jour(VENDREDI, self.company),
            (datetime.time(9, 0), datetime.time(15, 0), None))
        self.assertTrue(
            horaires.est_dans_fenetre(_quand(VENDREDI, 12), self.company))

    def test_hors_periode_le_decoupage_par_canal_revient(self):
        """Garde anti-régression : la décision vaut PENDANT le mois, elle ne
        supprime pas le découpage message/appel du reste de l'année."""
        hors = datetime.date(2027, 5, 11)  # mardi, hors période
        message = horaires.fenetre_du_jour(
            hors, self.company, canal='whatsapp')
        appel = horaires.fenetre_du_jour(hors, self.company, canal='appel')
        self.assertEqual(message[0], datetime.time(8, 30))
        self.assertEqual(appel[0], datetime.time(9, 0))
