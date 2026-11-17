"""TCH153 — lecture ICS pure et minutes de rendez-vous (regles.md §3.6, §11) : unittest pur."""
import unittest
from datetime import date, datetime, time

from apps.taches.moteur.ics import (
    Fenetre, IcsIllisible, IcsTropGrand, RendezVousPur, lire_evenements, minutes_rendez_vous)

# Fuseau local fixe (UTC+1, sans règle de saison) : les attendus ne dépendent d'aucune règle de tzdata.
LOCAL = 'Etc/GMT-1'
DU, AU = date(2026, 11, 16), date(2026, 12, 20)

MICROSOFT_365 = """BEGIN:VCALENDAR\r
PRODID:-//Microsoft Corporation//Outlook 16.0 MIMEDIR//EN\r
VERSION:2.0\r
METHOD:PUBLISH\r
BEGIN:VTIMEZONE\r
TZID:Romance Standard Time\r
BEGIN:STANDARD\r
DTSTART:16011028T030000\r
TZOFFSETFROM:+0200\r
TZOFFSETTO:+0100\r
END:STANDARD\r
END:VTIMEZONE\r
BEGIN:VEVENT\r
UID:040000008200E00074C5B7101A82E008\r
DTSTART;TZID=Romance Standard Time:20261124T100000\r
DTEND;TZID=Romance Standard Time:20261124T113000\r
SUMMARY:Visite chantier Bouskoura\r
END:VEVENT\r
BEGIN:VEVENT\r
UID:040000008200E00074C5B7101A82E009\r
DTSTART;VALUE=DATE:20261126\r
DTEND;VALUE=DATE:20261127\r
SUMMARY:Salon Intersolar\r
END:VEVENT\r
END:VCALENDAR\r
"""

GOOGLE = """BEGIN:VCALENDAR
PRODID:-//Google Inc//Google Calendar 70.9054//EN
VERSION:2.0
X-WR-TIMEZONE:Africa/Casablanca
BEGIN:VEVENT
DTSTART:20261124T090000Z
DTEND:20261124T100000Z
UID:abc123@google.com
SUMMARY:Point equipe\\, avec Karim\\; salle 2
END:VEVENT
BEGIN:VEVENT
DTSTART;TZID=America/New_York:20261201T090000
DTEND;TZID=America/New_York:20261201T093000
UID:def456@google.com
SUMMARY:Appel New York avec un titre vraiment très long qui dépasse la ligne et se re
 plie sur la suivante
END:VEVENT
BEGIN:VEVENT
DTSTART:20261125T090000Z
DTEND:20261125T100000Z
UID:annule@google.com
STATUS:CANCELLED
SUMMARY:Annule
END:VEVENT
END:VCALENDAR
"""

ICLOUD = """BEGIN:VCALENDAR
VERSION:2.0
PRODID:-//Apple Inc.//iOS 18.0//EN
CALSCALE:GREGORIAN
BEGIN:VTIMEZONE
TZID:Europe/Paris
END:VTIMEZONE
BEGIN:VEVENT
CREATED:20261101T080000Z
UID:ICLOUD-1
DTSTART;TZID=Europe/Paris:20261203T140000
DURATION:PT1H30M
RRULE:FREQ=WEEKLY;COUNT=10
SUMMARY:Cours hebdo
END:VEVENT
BEGIN:VEVENT
UID:ICLOUD-2
DTSTART;VALUE=DATE:20261210
SUMMARY:Anniversaire
END:VEVENT
BEGIN:VEVENT
UID:ICLOUD-3
DTSTART:20261211T080000
SUMMARY:Sans fin
END:VEVENT
END:VCALENDAR
"""

FENETRE = Fenetre(time(8, 30), time(19, 0))
JOUR = date(2026, 11, 24)


def rdv(debut, fin, entiere=False):
    return RendezVousPur('k', 1, 't', debut, fin, entiere)


def jour(h1, m1, h2, m2, d=JOUR):
    return rdv(datetime(d.year, d.month, d.day, h1, m1), datetime(d.year, d.month, d.day, h2, m2))


class LireMicrosoft365Tests(unittest.TestCase):
    def test_fuseau_windows_et_journee_entiere(self):
        evts = lire_evenements(MICROSOFT_365, DU, AU, agenda_id=7, fuseau=LOCAL)
        self.assertEqual(len(evts), 2)
        visite, salon = evts
        self.assertEqual(visite.titre, 'Visite chantier Bouskoura')
        # 10:00 « Romance Standard Time » (Paris, hiver = +01:00) = 10:00 en UTC+1.
        self.assertEqual((visite.debut, visite.fin),
                         (datetime(2026, 11, 24, 10, 0), datetime(2026, 11, 24, 11, 30)))
        self.assertFalse(visite.journee_entiere)
        self.assertTrue(salon.journee_entiere)
        self.assertEqual((salon.debut, salon.fin), (datetime(2026, 11, 26), datetime(2026, 11, 27)))
        self.assertEqual(visite.agenda_id, 7)

    def test_fuseau_ete_decale(self):
        texte = (MICROSOFT_365.replace('20261124T100000', '20260715T100000')
                 .replace('20261124T113000', '20260715T113000'))
        evts = lire_evenements(texte, date(2026, 7, 1), date(2026, 7, 31), fuseau=LOCAL)
        # Paris en été = +02:00 ; le fuseau local fixe est +01:00 : 10:00 devient 09:00.
        self.assertEqual(evts[0].debut, datetime(2026, 7, 15, 9, 0))


class LireGoogleTests(unittest.TestCase):
    def test_utc_et_fuseau_nomme(self):
        evts = lire_evenements(GOOGLE, DU, AU, fuseau=LOCAL)
        self.assertEqual([e.titre[:10] for e in evts], ['Point equi', 'Appel New '])
        equipe, new_york = evts
        self.assertEqual((equipe.debut, equipe.fin),
                         (datetime(2026, 11, 24, 10, 0), datetime(2026, 11, 24, 11, 0)))
        # 09:00 à New York (hiver, -05:00) = 14:00 UTC = 15:00 en UTC+1.
        self.assertEqual(new_york.debut, datetime(2026, 12, 1, 15, 0))
        self.assertEqual(new_york.fin, datetime(2026, 12, 1, 15, 30))

    def test_echappements_retires(self):
        equipe = lire_evenements(GOOGLE, DU, AU, fuseau=LOCAL)[0]
        self.assertEqual(equipe.titre, 'Point equipe, avec Karim; salle 2')

    def test_lignes_repliees_depliees(self):
        new_york = lire_evenements(GOOGLE, DU, AU, fuseau=LOCAL)[1]
        self.assertEqual(new_york.titre, 'Appel New York avec un titre vraiment très long '
                                         'qui dépasse la ligne et se replie sur la suivante')

    def test_annule_ignore(self):
        titres = [e.titre for e in lire_evenements(GOOGLE, DU, AU, fuseau=LOCAL)]
        self.assertNotIn('Annule', titres)


class LireICloudTests(unittest.TestCase):
    def test_duration_rrule_ignore_date_seule_sans_fin(self):
        evts = lire_evenements(ICLOUD, DU, AU, fuseau=LOCAL)
        self.assertEqual([e.titre for e in evts], ['Cours hebdo', 'Anniversaire', 'Sans fin'])
        cours, anniv, sans_fin = evts
        # RRULE non lu en v1 : une seule occurrence, celle de DTSTART.
        self.assertEqual((cours.debut, cours.fin),
                         (datetime(2026, 12, 3, 14, 0), datetime(2026, 12, 3, 15, 30)))
        self.assertTrue(anniv.journee_entiere)
        self.assertEqual(anniv.fin, datetime(2026, 12, 11))  # date seule : un jour
        self.assertEqual(sans_fin.debut, sans_fin.fin)  # ni DTEND ni DURATION : 0 minute
        self.assertEqual(sans_fin.debut, datetime(2026, 12, 11, 8, 0))  # flottant : heure locale


class FenetreEtCleTests(unittest.TestCase):
    def test_fenetre_de_lecture(self):
        texte = GOOGLE
        self.assertEqual(len(lire_evenements(texte, date(2026, 11, 24), date(2026, 11, 24), fuseau=LOCAL)), 1)
        self.assertEqual(len(lire_evenements(texte, date(2026, 11, 25), date(2026, 11, 30), fuseau=LOCAL)), 0)
        self.assertEqual(len(lire_evenements(texte, date(2026, 12, 1), date(2026, 12, 1), fuseau=LOCAL)), 1)

    def test_evenement_qui_chevauche_la_borne_est_garde(self):
        texte = ICLOUD.replace('DURATION:PT1H30M', 'DTEND;TZID=Europe/Paris:20261204T100000')
        evts = lire_evenements(texte, date(2026, 12, 4), date(2026, 12, 4), fuseau=LOCAL)
        self.assertEqual([e.titre for e in evts], ['Cours hebdo'])

    def test_cle_stable_et_distincte(self):
        a = lire_evenements(GOOGLE, DU, AU, agenda_id=3, fuseau=LOCAL)
        b = lire_evenements(GOOGLE, DU, AU, agenda_id=3, fuseau=LOCAL)
        self.assertEqual([e.cle for e in a], [e.cle for e in b])
        self.assertEqual(len({e.cle for e in a}), len(a))
        self.assertRegex(a[0].cle, r'^3-[0-9a-f]{8}$')

    def test_ordre_par_debut(self):
        evts = lire_evenements(GOOGLE, DU, AU, fuseau=LOCAL)
        self.assertEqual(list(evts), sorted(evts, key=lambda e: e.debut))


class ErreursTests(unittest.TestCase):
    def test_sans_vcalendar_illisible(self):
        with self.assertRaises(IcsIllisible):
            lire_evenements('<html>pas un agenda</html>', DU, AU)

    def test_calendrier_vide_est_valide(self):
        self.assertEqual(lire_evenements('BEGIN:VCALENDAR\nEND:VCALENDAR\n', DU, AU, fuseau=LOCAL), ())

    def test_plus_de_2000_evenements(self):
        un = 'BEGIN:VEVENT\nUID:x{i}\nDTSTART:20261124T090000Z\nEND:VEVENT\n'
        corps = ''.join(un.format(i=i) for i in range(2001))
        with self.assertRaises(IcsTropGrand):
            lire_evenements('BEGIN:VCALENDAR\n' + corps + 'END:VCALENDAR\n', DU, AU, fuseau=LOCAL)

    def test_evenement_illisible_ignore_sans_exception(self):
        texte = ('BEGIN:VCALENDAR\nBEGIN:VEVENT\nDTSTART:pasunedate\nSUMMARY:x\nEND:VEVENT\n'
                 'BEGIN:VEVENT\nSUMMARY:sans debut\nEND:VEVENT\nEND:VCALENDAR\n')
        self.assertEqual(lire_evenements(texte, DU, AU, fuseau=LOCAL), ())

    def test_fuseau_inconnu_lu_en_heure_locale(self):
        texte = ('BEGIN:VCALENDAR\nBEGIN:VEVENT\nUID:z\nDTSTART;TZID=Fuseau Inventé:20261124T090000\n'
                 'DTEND;TZID=Fuseau Inventé:20261124T100000\nEND:VEVENT\nEND:VCALENDAR\n')
        evts = lire_evenements(texte, DU, AU, fuseau=LOCAL)
        self.assertEqual(evts[0].debut, datetime(2026, 11, 24, 9, 0))

    def _avec_un_hostile(self, lignes_hostiles):
        """Un fichier : un événement sain, l'événement hostile, un autre événement sain."""
        sain = ('BEGIN:VEVENT\nUID:{uid}\nDTSTART:2026112{j}T090000Z\nDTEND:2026112{j}T100000Z\n'
                'SUMMARY:{uid}\nEND:VEVENT\n')
        texte = ('BEGIN:VCALENDAR\n' + sain.format(uid='avant', j=4)
                 + 'BEGIN:VEVENT\nUID:hostile\n' + lignes_hostiles + 'SUMMARY:hostile\nEND:VEVENT\n'
                 + sain.format(uid='apres', j=5) + 'END:VCALENDAR\n')
        return lire_evenements(texte, DU, AU, fuseau=LOCAL)

    def test_duree_demesuree_ignoree_les_autres_rendus(self):
        evts = self._avec_un_hostile('DTSTART:20261124T110000Z\nDURATION:P999999999W\n')
        self.assertEqual([e.titre for e in evts], ['avant', 'apres'])

    def test_date_de_fin_hors_calendrier_ignoree_les_autres_rendus(self):
        evts = self._avec_un_hostile('DTSTART;VALUE=DATE:99991231\n')
        self.assertEqual([e.titre for e in evts], ['avant', 'apres'])

    def test_fuseau_qui_est_un_dossier_lu_comme_un_fuseau_inconnu(self):
        """`TZID=America` (un dossier de tzdata : `PermissionError`/`IsADirectoryError`) ne fait pas
        tomber l'agenda : il est lu comme tout fuseau inconnu, en heure locale."""
        evts = self._avec_un_hostile('DTSTART;TZID=America:20261124T110000\n')
        self.assertEqual([e.titre for e in evts], ['avant', 'hostile', 'apres'])
        self.assertEqual(evts[1].debut, datetime(2026, 11, 24, 11, 0))


class MinutesRendezVousTests(unittest.TestCase):
    """Tableau de regles.md §3.6 : fenêtre 08:30-19:00."""

    def test_un_rendez_vous(self):
        self.assertEqual(minutes_rendez_vous([jour(11, 0, 12, 0)], JOUR, FENETRE), 60)

    def test_deux_rendez_vous_chevauchants_fusionnes(self):
        evts = [jour(10, 0, 11, 30), jour(11, 0, 12, 0)]
        self.assertEqual(minutes_rendez_vous(evts, JOUR, FENETRE), 120)

    def test_ordre_indifferent(self):
        evts = [jour(11, 0, 12, 0), jour(10, 0, 11, 30)]
        self.assertEqual(minutes_rendez_vous(evts, JOUR, FENETRE), 120)

    def test_borne_au_debut_de_la_fenetre(self):
        self.assertEqual(minutes_rendez_vous([jour(7, 0, 9, 0)], JOUR, FENETRE), 30)

    def test_borne_a_la_fin_de_la_fenetre(self):
        self.assertEqual(minutes_rendez_vous([jour(18, 30, 20, 0)], JOUR, FENETRE), 30)

    def test_journee_entiere_vaut_zero(self):
        entiere = rdv(datetime(2026, 11, 24), datetime(2026, 11, 25), entiere=True)
        self.assertEqual(minutes_rendez_vous([entiere], JOUR, FENETRE), 0)

    def test_deux_plages_separees(self):
        evts = [jour(9, 0, 12, 0), jour(14, 0, 16, 0)]
        self.assertEqual(minutes_rendez_vous(evts, JOUR, FENETRE), 300)

    def test_hors_fenetre_vaut_zero(self):
        self.assertEqual(minutes_rendez_vous([jour(6, 0, 8, 0), jour(19, 0, 21, 0)], JOUR, FENETRE), 0)

    def test_autre_jour_ignore(self):
        autre = jour(10, 0, 11, 0, d=date(2026, 11, 25))
        self.assertEqual(minutes_rendez_vous([autre], JOUR, FENETRE), 0)

    def test_evenement_sur_deux_jours_coupe_au_jour(self):
        veille = rdv(datetime(2026, 11, 23, 22, 0), datetime(2026, 11, 24, 10, 0))
        self.assertEqual(minutes_rendez_vous([veille], JOUR, FENETRE), 90)

    def test_instant_nul_et_liste_vide_jamais_negatif(self):
        instant = rdv(datetime(2026, 11, 24, 10, 0), datetime(2026, 11, 24, 10, 0))
        self.assertEqual(minutes_rendez_vous([instant], JOUR, FENETRE), 0)
        self.assertEqual(minutes_rendez_vous([], JOUR, FENETRE), 0)

    def test_bout_a_bout_et_inclus(self):
        evts = [jour(9, 0, 10, 0), jour(10, 0, 11, 0), jour(9, 30, 9, 45)]
        self.assertEqual(minutes_rendez_vous(evts, JOUR, FENETRE), 120)

    def test_de_bout_en_bout_depuis_un_fichier(self):
        evts = lire_evenements(MICROSOFT_365, DU, AU, fuseau=LOCAL)
        self.assertEqual(minutes_rendez_vous(evts, JOUR, FENETRE), 90)
        self.assertEqual(minutes_rendez_vous(evts, date(2026, 11, 26), FENETRE), 0)


if __name__ == '__main__':
    unittest.main()
