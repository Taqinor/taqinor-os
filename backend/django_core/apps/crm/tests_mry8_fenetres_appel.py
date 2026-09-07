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

DÉCISION FONDATEUR DU 07/09/2026 — deux ouvertures, pas une. Un message
WhatsApp/e-mail peut partir dès `message_heure_debut` (08:30) ; un APPEL
jamais avant `appel_heure_debut`, dont le défaut passe à 09:00. Les tests qui
attendaient une ouverture d'appel à 08:30 sont ADAPTÉS ici, et nommément :
ce n'est pas une dérive, c'est la décision. Ce qui reste COMMUN aux deux
canaux : la fermeture du soir, la fenêtre de Ramadan et le dimanche du
Protocole v3. Ce qui ne l'est pas : la pause de la prière du vendredi, qui ne
vaut que pour les appels — un message est silencieux.
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
        # Mercredi 2 septembre 2026. Décision du 07/09/2026 : l'ouverture des
        # APPELS est 09:00, plus 08:30 — un appel d'affaires ne se passe pas
        # à 8 h 30 au Maroc.
        debut, fin, pause = horaires.fenetre_du_jour(
            datetime.date(2026, 9, 2), self.company)
        self.assertEqual(debut, datetime.time(9, 0))
        self.assertEqual(fin, datetime.time(20, 0))
        self.assertIsNone(pause)

    def test_un_message_ouvre_une_demi_heure_plus_tot(self):
        """07/09/2026 — LE point de la décision : le message part à 08:30,
        l'appel à 09:00, et la FERMETURE reste commune."""
        message = horaires.fenetre_du_jour(
            datetime.date(2026, 9, 2), self.company, canal='whatsapp')
        appel = horaires.fenetre_du_jour(
            datetime.date(2026, 9, 2), self.company, canal='appel')
        self.assertEqual(message[0], datetime.time(8, 30))
        self.assertEqual(appel[0], datetime.time(9, 0))
        self.assertEqual(message[1], appel[1])

    def test_le_mail_suit_la_fenetre_des_messages(self):
        self.assertEqual(
            horaires.fenetre_du_jour(datetime.date(2026, 9, 2), self.company,
                                     canal='email')[0],
            datetime.time(8, 30))

    def test_un_canal_inconnu_retombe_sur_la_fenetre_dappel(self):
        """Dans le doute, la fenêtre la plus TARDIVE : mieux vaut poser une
        touche trop tard qu'appeler quelqu'un trop tôt."""
        for canal in ('visite', '', None, 'sms'):
            self.assertEqual(
                horaires.fenetre_du_jour(datetime.date(2026, 9, 2),
                                         self.company, canal=canal)[0],
                datetime.time(9, 0), canal)

    def test_les_heures_du_profil_priment_sur_les_defauts(self):
        profil = CompanyProfile.objects.get(company=self.company)
        profil.message_heure_debut = datetime.time(7, 45)
        profil.appel_heure_debut = datetime.time(10, 15)
        profil.save(update_fields=['message_heure_debut',
                                   'appel_heure_debut'])
        jour = datetime.date(2026, 9, 2)
        self.assertEqual(
            horaires.fenetre_du_jour(jour, self.company,
                                     canal='whatsapp')[0],
            datetime.time(7, 45))
        self.assertEqual(
            horaires.fenetre_du_jour(jour, self.company, canal='appel')[0],
            datetime.time(10, 15))

    def test_message_heure_debut_nulle_retombe_sur_0830(self):
        """Le champ est nullable : une société qui l'efface ne bloque pas ses
        messages jusqu'à l'ouverture des appels."""
        profil = CompanyProfile.objects.get(company=self.company)
        profil.message_heure_debut = None
        profil.appel_heure_debut = datetime.time(11, 0)
        profil.save(update_fields=['message_heure_debut',
                                   'appel_heure_debut'])
        jour = datetime.date(2026, 9, 2)
        self.assertEqual(
            horaires.fenetre_du_jour(jour, self.company,
                                     canal='whatsapp')[0],
            datetime.time(8, 30))
        self.assertEqual(
            horaires.fenetre_du_jour(jour, self.company, canal='appel')[0],
            datetime.time(11, 0))

    def test_sans_profil_les_deux_defauts_sappliquent(self):
        """Une société sans profil ne fait pas exception à la décision."""
        sans_profil, _ = Company.objects.get_or_create(
            slug='mry8-sans-profil', defaults={'nom': 'mry8-sans-profil'})
        CompanyProfile.objects.filter(company=sans_profil).delete()
        jour = datetime.date(2026, 9, 2)
        self.assertEqual(
            horaires.fenetre_du_jour(jour, sans_profil,
                                     canal='whatsapp')[0],
            datetime.time(8, 30))
        self.assertEqual(
            horaires.fenetre_du_jour(jour, sans_profil, canal='appel')[0],
            datetime.time(9, 0))

    def test_le_vendredi_porte_la_pause_de_priere(self):
        # Vendredi 4 septembre 2026.
        _, _, pause = horaires.fenetre_du_jour(
            datetime.date(2026, 9, 4), self.company)
        self.assertEqual(pause, (datetime.time(11, 30), datetime.time(15, 0)))

    def test_la_pause_du_vendredi_ne_vaut_que_pour_les_appels(self):
        """07/09/2026 — un message est SILENCIEUX : il ne dérange personne à
        la prière, donc il n'a pas à sauter par-dessus la pause."""
        for canal in ('whatsapp', 'email'):
            self.assertIsNone(
                horaires.fenetre_du_jour(datetime.date(2026, 9, 4),
                                         self.company, canal=canal)[2], canal)
        self.assertIsNotNone(
            horaires.fenetre_du_jour(datetime.date(2026, 9, 4), self.company,
                                     canal='appel')[2])

    def test_un_jour_non_ouvre_na_pas_de_fenetre(self):
        # Dimanche 6 septembre 2026 — hors jours ouvrés par défaut (L-V).
        self.assertIsNone(horaires.fenetre_du_jour(
            datetime.date(2026, 9, 6), self.company))

    def test_le_dimanche_du_protocole_v3_est_la_seule_exception(self):
        fenetre = horaires.fenetre_du_jour(
            datetime.date(2026, 9, 6), self.company, dimanche=True)
        self.assertEqual(fenetre, (datetime.time(16, 0),
                                   datetime.time(19, 0), None))

    def test_le_dimanche_est_le_meme_pour_les_deux_canaux(self):
        """La fenêtre dominicale 16 h-19 h est un RENDEZ-VOUS, pas une heure
        d'ouverture : elle ne se scinde pas par canal."""
        self.assertEqual(
            horaires.fenetre_du_jour(datetime.date(2026, 9, 6), self.company,
                                     dimanche=True, canal='whatsapp'),
            horaires.fenetre_du_jour(datetime.date(2026, 9, 6), self.company,
                                     dimanche=True, canal='appel'))

    def test_la_fenetre_de_ramadan_est_commune_aux_deux_canaux(self):
        """Pendant le Ramadan c'est la JOURNÉE entière qui se déplace
        (10 h-14 h), pas seulement l'heure des appels."""
        profil = CompanyProfile.objects.get(company=self.company)
        profil.ramadan_debut = datetime.date(2027, 2, 8)
        profil.ramadan_fin = datetime.date(2027, 3, 9)
        profil.save(update_fields=['ramadan_debut', 'ramadan_fin'])
        jour = datetime.date(2027, 2, 9)  # mardi
        self.assertEqual(
            horaires.fenetre_du_jour(jour, self.company, canal='whatsapp'),
            (datetime.time(10, 0), datetime.time(14, 0), None))
        self.assertEqual(
            horaires.fenetre_du_jour(jour, self.company, canal='whatsapp'),
            horaires.fenetre_du_jour(jour, self.company, canal='appel'))


class ProchainCreneauTests(TestCase):
    def setUp(self):
        self.company = _company('mry8-creneau')

    def test_dans_la_fenetre_linstant_ne_bouge_pas(self):
        moment = _dt(2026, 9, 2, 10, 0)
        self.assertEqual(
            horaires.prochain_creneau_appel(moment, self.company), moment)

    def test_avant_louverture_on_attend_louverture(self):
        # 07/09/2026 : l'ouverture des APPELS est 09:00 (défaut du canal).
        resultat = horaires.prochain_creneau_appel(
            _dt(2026, 9, 2, 6, 0), self.company)
        self.assertEqual(resultat, _dt(2026, 9, 2, 9, 0))

    def test_le_message_nattend_pas_louverture_des_appels(self):
        """07/09/2026 — LE gain : à 08:30 le message part, l'appel attend."""
        aube = _dt(2026, 9, 2, 6, 0)
        self.assertEqual(
            horaires.prochain_creneau_appel(aube, self.company,
                                            canal='whatsapp'),
            _dt(2026, 9, 2, 8, 30))
        self.assertEqual(
            horaires.prochain_creneau_appel(aube, self.company,
                                            canal='appel'),
            _dt(2026, 9, 2, 9, 0))

    def test_un_appel_calcule_a_0833_est_repousse_a_0900(self):
        """Le cas EXACT que la décision corrige : le lead de nuit recevait
        son message à 08:30 puis un coup de téléphone trois minutes après."""
        self.assertEqual(
            horaires.prochain_creneau_appel(_dt(2026, 9, 2, 8, 33),
                                            self.company, canal='appel'),
            _dt(2026, 9, 2, 9, 0))

    def test_un_message_a_0833_ne_bouge_pas(self):
        moment = _dt(2026, 9, 2, 8, 33)
        self.assertEqual(
            horaires.prochain_creneau_appel(moment, self.company,
                                            canal='whatsapp'),
            moment)

    def test_un_message_du_vendredi_midi_ne_saute_pas_la_priere(self):
        """La pause ne vaut que pour les appels : le message part à l'heure
        dite, l'appel attend 15:00."""
        midi = _dt(2026, 9, 4, 12, 0)
        self.assertEqual(
            horaires.prochain_creneau_appel(midi, self.company,
                                            canal='whatsapp'),
            midi)
        self.assertEqual(
            horaires.prochain_creneau_appel(midi, self.company,
                                            canal='appel'),
            _dt(2026, 9, 4, 15, 0))

    def test_vendredi_midi_tombe_a_la_fin_de_la_pause(self):
        resultat = horaires.prochain_creneau_appel(
            _dt(2026, 9, 4, 12, 0), self.company)
        self.assertEqual(resultat, _dt(2026, 9, 4, 15, 0))

    def test_vendredi_apres_fermeture_tombe_au_lundi(self):
        # Ouverture des appels du lundi : 09:00 (décision du 07/09/2026).
        resultat = horaires.prochain_creneau_appel(
            _dt(2026, 9, 4, 20, 1), self.company)
        self.assertEqual(resultat, _dt(2026, 9, 7, 9, 0))

    def test_samedi_tombe_au_lundi(self):
        resultat = horaires.prochain_creneau_appel(
            _dt(2026, 9, 5, 10, 0), self.company)
        self.assertEqual(resultat, _dt(2026, 9, 7, 9, 0))

    def test_le_week_end_dun_message_ouvre_au_lundi_0830(self):
        """Le report au prochain jour ouvré garde l'ouverture DU CANAL."""
        self.assertEqual(
            horaires.prochain_creneau_appel(_dt(2026, 9, 5, 10, 0),
                                            self.company, canal='whatsapp'),
            _dt(2026, 9, 7, 8, 30))

    def test_un_ferie_est_saute(self):
        from apps.notifications.models import Holiday
        Holiday.objects.create(
            company=self.company, nom='Fête', date=datetime.date(2026, 9, 7))
        resultat = horaires.prochain_creneau_appel(
            _dt(2026, 9, 5, 10, 0), self.company)
        self.assertEqual(resultat, _dt(2026, 9, 8, 9, 0))

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
        self.assertEqual(resultat, _dt(2026, 9, 7, 9, 0))


class ProchainDimancheTests(TestCase):
    """MRY4/MRY8 — une touche dominicale se PLACE sur un dimanche.

    `prochain_creneau_appel` ne sait que borner un instant dans la fenêtre de
    SON jour : il ne déplace jamais une touche vers un autre jour de la
    semaine. L'« appel du dimanche » du Protocole v3, calculé en J+5 depuis un
    mercredi, tombait donc un lundi — le seul rendez-vous dominical du
    protocole n'avait jamais lieu un dimanche.
    """

    def test_un_mercredi_renvoie_le_dimanche_suivant_a_1630(self):
        # Mercredi 2 septembre 2026 → dimanche 6 septembre.
        self.assertEqual(
            horaires.prochain_dimanche(_dt(2026, 9, 2, 10, 0)),
            _dt(2026, 9, 6, 16, 30))

    def test_un_samedi_soir_renvoie_le_lendemain(self):
        self.assertEqual(
            horaires.prochain_dimanche(_dt(2026, 9, 5, 20, 0)),
            _dt(2026, 9, 6, 16, 30))

    def test_un_dimanche_avant_1630_reste_ce_dimanche(self):
        self.assertEqual(
            horaires.prochain_dimanche(_dt(2026, 9, 6, 12, 0)),
            _dt(2026, 9, 6, 16, 30))

    def test_un_dimanche_dans_la_fenetre_ne_recule_jamais(self):
        """On ne replanifie pas une touche dans le passé de son départ."""
        self.assertEqual(
            horaires.prochain_dimanche(_dt(2026, 9, 6, 17, 15)),
            _dt(2026, 9, 6, 17, 15))

    def test_un_dimanche_apres_la_fermeture_passe_au_suivant(self):
        self.assertEqual(
            horaires.prochain_dimanche(_dt(2026, 9, 6, 19, 0)),
            _dt(2026, 9, 13, 16, 30))

    def test_lheure_est_parametrable(self):
        self.assertEqual(
            horaires.prochain_dimanche(
                _dt(2026, 9, 2, 10, 0), heure=datetime.time(17, 0)),
            _dt(2026, 9, 6, 17, 0))

    def test_la_sortie_reste_dans_le_fuseau_dentree(self):
        entree = _dt(2026, 9, 2, 10, 0).astimezone(datetime.timezone.utc)
        resultat = horaires.prochain_dimanche(entree)
        self.assertEqual(resultat.tzinfo, datetime.timezone.utc)
        self.assertEqual(resultat, _dt(2026, 9, 6, 16, 30))

    def test_le_resultat_est_toujours_dans_la_fenetre_dominicale(self):
        company = _company('mry8-dimanche')
        for depart in (_dt(2026, 9, 2, 10, 0), _dt(2026, 9, 5, 20, 0),
                       _dt(2026, 9, 6, 12, 0)):
            resultat = horaires.prochain_dimanche(depart)
            self.assertEqual(resultat.astimezone(CASA).weekday(), 6)
            self.assertTrue(
                horaires.est_dans_fenetre(resultat, company, dimanche=True))


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

    def test_la_pause_du_vendredi_est_retranchee_pour_un_appel(self):
        # Vendredi 11:00 → 15:30 : 30 min avant la pause + 30 min après.
        self.assertEqual(
            horaires.minutes_ouvrees_entre(
                _dt(2026, 9, 4, 11, 0), _dt(2026, 9, 4, 15, 30),
                self.company, canal='appel'),
            60)

    def test_la_pause_du_vendredi_nest_pas_retranchee_pour_un_message(self):
        """07/09/2026 — un message reste posable pendant la prière : les
        4 h 30 s'écoulent en entier."""
        self.assertEqual(
            horaires.minutes_ouvrees_entre(
                _dt(2026, 9, 4, 11, 0), _dt(2026, 9, 4, 15, 30),
                self.company, canal='whatsapp'),
            270)

    def test_le_defaut_est_le_canal_message(self):
        """Le premier contact du protocole est un MESSAGE : le compteur doit
        démarrer à 08:30, pas à 09:00 — sinon la demi-heure pendant laquelle
        Meryem écrit ne compterait pour rien."""
        depart = _dt(2026, 9, 2, 8, 20)  # mercredi, avant les deux ouvertures
        arrivee = _dt(2026, 9, 2, 8, 45)
        self.assertEqual(
            horaires.minutes_ouvrees_entre(depart, arrivee, self.company), 15)
        self.assertEqual(
            horaires.minutes_ouvrees_entre(depart, arrivee, self.company,
                                           canal='appel'),
            0)

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


class CacheLocalTests(TestCase):
    """Cache LOCAL à une opération (`horaires.cache_local`) : le profil et les
    jours ouvrés ne sont lus qu'une fois par bloc — 24 s mesurées en prod le
    07/09 pour dater 272 leads sans lui. Hors bloc, rien n'est mis en cache :
    un réglage modifié se voit tout de suite."""

    def setUp(self):
        from authentication.models import Company
        from apps.parametres.models import CompanyProfile
        self.company, _ = Company.objects.get_or_create(
            slug='mry8-cache', defaults={'nom': 'mry8-cache'})
        CompanyProfile.objects.get_or_create(company=self.company)

    def _requetes(self, appels):
        from django.db import connection
        from django.test.utils import CaptureQueriesContext
        jour = datetime.date(2026, 9, 9)  # mercredi ouvré
        with CaptureQueriesContext(connection) as ctx:
            for _ in range(appels):
                horaires.fenetre_du_jour(jour, self.company)
        return len(ctx.captured_queries)

    def test_dans_le_bloc_le_calendrier_n_est_lu_qu_une_fois(self):
        une = self._requetes(1)
        with horaires.cache_local():
            cinq = self._requetes(5)
        self.assertGreater(une, 0)
        self.assertEqual(cinq, une)

    def test_hors_du_bloc_rien_n_est_memorise(self):
        une = self._requetes(1)
        cinq = self._requetes(5)
        self.assertEqual(cinq, 5 * une)

    def test_un_reglage_modifie_se_voit_apres_le_bloc(self):
        from apps.parametres.models import CompanyProfile
        jour = datetime.date(2026, 9, 9)
        with horaires.cache_local():
            avant = horaires.fenetre_du_jour(jour, self.company)[0]
        CompanyProfile.objects.filter(company=self.company).update(
            appel_heure_debut=datetime.time(10, 15))
        apres = horaires.fenetre_du_jour(jour, self.company)[0]
        self.assertNotEqual(avant, apres)
        self.assertEqual(apres, datetime.time(10, 15))
