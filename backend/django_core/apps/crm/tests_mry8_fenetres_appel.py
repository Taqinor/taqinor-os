"""MRY8 — Fenêtres d'appel : quand une touche tombe, et combien de minutes
OUVRÉES séparent réellement deux instants.

Les deux défauts que ce module corrige, vérifiés ici sur des datetimes fixés :
  * une touche « J+1 » tombait à l'heure de création du lead — un prospect
    arrivé à 23 h se voyait rappelé à 23 h le lendemain ;
  * un délai mesuré en minutes CALENDAIRES comptait la nuit et le week-end :
    un lead arrivé vendredi 21 h et rappelé lundi 08:32 affichait 60 heures
    de retard alors que la réponse avait pris 2 minutes ouvrées.

Plus une régression réelle : `_ramadan_pacing_enabled` lisait un champ
`ramadan_pacing` QUI N'A JAMAIS EXISTÉ — il renvoyait donc toujours False.
"""
import datetime

from django.test import TestCase
from django.utils import timezone

from authentication.models import Company

from apps.crm import horaires, services
from apps.parametres.models import CompanyProfile

CASA = horaires.CASABLANCA


def _company(slug):
    company, _ = Company.objects.get_or_create(
        slug=slug, defaults={'nom': slug})
    CompanyProfile.objects.get_or_create(company=company)
    return company


def _dt(annee, mois, jour, heure=0, minute=0):
    """Datetime AWARE en heure locale Casablanca."""
    return datetime.datetime(annee, mois, jour, heure, minute, tzinfo=CASA)


class FenetreDuJourTests(TestCase):
    def setUp(self):
        self.company = _company('mry8-fenetre')

    def test_un_jour_ouvre_porte_la_fenetre_par_defaut(self):
        # Mercredi 2 septembre 2026.
        debut, fin, pause = horaires.fenetre_du_jour(
            datetime.date(2026, 9, 2), self.company)
        self.assertEqual(debut, datetime.time(8, 30))
        self.assertEqual(fin, datetime.time(20, 0))
        self.assertIsNone(pause)

    def test_le_vendredi_porte_la_pause_de_priere(self):
        # Vendredi 4 septembre 2026.
        _, _, pause = horaires.fenetre_du_jour(
            datetime.date(2026, 9, 4), self.company)
        self.assertEqual(pause, (datetime.time(11, 30), datetime.time(15, 0)))

    def test_un_jour_non_ouvre_na_pas_de_fenetre(self):
        # Dimanche 6 septembre 2026 — hors jours ouvrés par défaut (L-V).
        self.assertIsNone(horaires.fenetre_du_jour(
            datetime.date(2026, 9, 6), self.company))

    def test_le_dimanche_du_protocole_v3_est_la_seule_exception(self):
        fenetre = horaires.fenetre_du_jour(
            datetime.date(2026, 9, 6), self.company, dimanche=True)
        self.assertEqual(fenetre, (datetime.time(16, 0),
                                   datetime.time(19, 0), None))


class ProchainCreneauTests(TestCase):
    def setUp(self):
        self.company = _company('mry8-creneau')

    def test_dans_la_fenetre_linstant_ne_bouge_pas(self):
        moment = _dt(2026, 9, 2, 10, 0)
        self.assertEqual(
            horaires.prochain_creneau_appel(moment, self.company), moment)

    def test_avant_louverture_on_attend_louverture(self):
        resultat = horaires.prochain_creneau_appel(
            _dt(2026, 9, 2, 6, 0), self.company)
        self.assertEqual(resultat, _dt(2026, 9, 2, 8, 30))

    def test_vendredi_midi_tombe_a_la_fin_de_la_pause(self):
        resultat = horaires.prochain_creneau_appel(
            _dt(2026, 9, 4, 12, 0), self.company)
        self.assertEqual(resultat, _dt(2026, 9, 4, 15, 0))

    def test_vendredi_apres_fermeture_tombe_au_lundi(self):
        resultat = horaires.prochain_creneau_appel(
            _dt(2026, 9, 4, 20, 1), self.company)
        self.assertEqual(resultat, _dt(2026, 9, 7, 8, 30))

    def test_samedi_tombe_au_lundi(self):
        resultat = horaires.prochain_creneau_appel(
            _dt(2026, 9, 5, 10, 0), self.company)
        self.assertEqual(resultat, _dt(2026, 9, 7, 8, 30))

    def test_un_ferie_est_saute(self):
        from apps.notifications.models import Holiday
        Holiday.objects.create(
            company=self.company, nom='Fête', date=datetime.date(2026, 9, 7))
        resultat = horaires.prochain_creneau_appel(
            _dt(2026, 9, 5, 10, 0), self.company)
        self.assertEqual(resultat, _dt(2026, 9, 8, 8, 30))

    def test_pendant_le_ramadan_la_fenetre_se_resserre(self):
        profil = CompanyProfile.objects.get(company=self.company)
        profil.ramadan_debut = datetime.date(2027, 2, 8)
        profil.ramadan_fin = datetime.date(2027, 3, 9)
        profil.save(update_fields=['ramadan_debut', 'ramadan_fin'])
        # Mardi 9 février 2027, 09:00 → attend l'ouverture de 10:00.
        resultat = horaires.prochain_creneau_appel(
            _dt(2027, 2, 9, 9, 0), self.company)
        self.assertEqual(resultat, _dt(2027, 2, 9, 10, 0))

    def test_la_sortie_reste_dans_le_fuseau_dentree(self):
        entree = _dt(2026, 9, 5, 10, 0).astimezone(datetime.timezone.utc)
        resultat = horaires.prochain_creneau_appel(entree, self.company)
        self.assertEqual(resultat.tzinfo, datetime.timezone.utc)
        self.assertEqual(resultat, _dt(2026, 9, 7, 8, 30))


class MinutesOuvreesTests(TestCase):
    def setUp(self):
        self.company = _company('mry8-minutes')

    def test_une_nuit_complete_vaut_zero_minute(self):
        self.assertEqual(
            horaires.minutes_ouvrees_entre(
                _dt(2026, 9, 2, 21, 0), _dt(2026, 9, 3, 6, 0), self.company),
            0)

    def test_deux_minutes_ouvrees_par_dessus_un_week_end(self):
        """Le cas qui rendait le KPI faux à charge : vendredi 21:00 → lundi
        08:32 = 2 minutes ouvrées, pas 60 heures."""
        self.assertEqual(
            horaires.minutes_ouvrees_entre(
                _dt(2026, 9, 4, 21, 0), _dt(2026, 9, 7, 8, 32), self.company),
            2)

    def test_meme_journee_compte_les_minutes_reelles(self):
        self.assertEqual(
            horaires.minutes_ouvrees_entre(
                _dt(2026, 9, 2, 9, 0), _dt(2026, 9, 2, 9, 45), self.company),
            45)

    def test_la_pause_du_vendredi_est_retranchee(self):
        # Vendredi 11:00 → 15:30 : 30 min avant la pause + 30 min après.
        self.assertEqual(
            horaires.minutes_ouvrees_entre(
                _dt(2026, 9, 4, 11, 0), _dt(2026, 9, 4, 15, 30),
                self.company),
            60)

    def test_ordre_inverse_vaut_zero(self):
        self.assertEqual(
            horaires.minutes_ouvrees_entre(
                _dt(2026, 9, 2, 12, 0), _dt(2026, 9, 2, 9, 0), self.company),
            0)

    def test_none_vaut_zero(self):
        self.assertEqual(
            horaires.minutes_ouvrees_entre(None, timezone.now(), self.company),
            0)


class RamadanPacingTests(TestCase):
    """`_ramadan_pacing_enabled` lisait `CompanyProfile.ramadan_pacing`, un
    champ inexistant : il renvoyait TOUJOURS False et le pacing iftar était
    mort depuis sa création."""

    def setUp(self):
        self.company = _company('mry8-ramadan')

    def test_faux_tant_quaucune_periode_nest_saisie(self):
        self.assertFalse(services._ramadan_pacing_enabled(self.company))

    def test_vrai_pendant_la_periode_saisie(self):
        aujourd_hui = horaires._local(timezone.now()).date()
        profil = CompanyProfile.objects.get(company=self.company)
        profil.ramadan_debut = aujourd_hui - datetime.timedelta(days=2)
        profil.ramadan_fin = aujourd_hui + datetime.timedelta(days=25)
        profil.save(update_fields=['ramadan_debut', 'ramadan_fin'])
        self.assertTrue(services._ramadan_pacing_enabled(self.company))

    def test_faux_hors_de_la_periode_saisie(self):
        aujourd_hui = horaires._local(timezone.now()).date()
        profil = CompanyProfile.objects.get(company=self.company)
        profil.ramadan_debut = aujourd_hui - datetime.timedelta(days=400)
        profil.ramadan_fin = aujourd_hui - datetime.timedelta(days=370)
        profil.save(update_fields=['ramadan_debut', 'ramadan_fin'])
        self.assertFalse(services._ramadan_pacing_enabled(self.company))

    def test_societe_absente_reste_fausse(self):
        self.assertFalse(services._ramadan_pacing_enabled(None))
