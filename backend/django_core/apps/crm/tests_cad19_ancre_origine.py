"""CAD19 — une seule ANCRE pour toute la cadence : l'origine ouvrable.

Les touches du jour même partaient de l'ORIGINE (le premier instant vraiment
joignable) ; toutes les autres partaient de `depart`, l'instant BRUT d'arrivée
du lead. Pour un lead arrivé samedi 11 h, J0, J+1 et J+2 retombaient donc tous
les trois sur le même lundi : trois jours de protocole écrasés en un. Le même
défaut frappait `apres_devis`, dont le départ est l'instant d'envoi du devis —
un devis fini un vendredi soir empilait J+1, J+2 et J+3 sur deux jours.

Comme la cadence est RÉACTIVE, la commerciale ne voyait pas six lignes le
lundi : elle les voyait NAÎTRE une à une, déjà en retard, et son adhérence
était fausse.

Ce que ce fichier verrouille :
  * les 11 touches de la prise de contact, DÉROULÉES pour les 7 jours
    d'arrivée de la semaine : aucune ne sort de la fenêtre de son canal,
    aucune ne précède l'origine, et les trois touches J0 restent sur le même
    jour ;
  * le cas de la tâche : un lead du SAMEDI étale J0 lundi, J+1 mardi,
    J+2 mercredi — et le même étalement sur `apres_devis` ;
  * le GARDE-FOU : un lead du dimanche 12:28 garde EXACTEMENT ses trois
    premières touches (lundi 08:30 / 09:00 / 11:00,
    `tests_mry5_relance_v2.py`) ;
  * l'EXCEPTION `reveil` : MRY30 rétrodate son départ pour tomber SUR un
    créneau d'étalement — cette ancre-là ne bouge pas.

Ni le nombre, ni l'ordre, ni le J+N des touches ne changent : seul change le
POINT ZÉRO depuis lequel les J+N se comptent. Le temps est GELÉ.
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

#: Lundi 7 septembre 2026, 07:00 — avant toute ouverture, pour que rien ne
#: dépende de l'heure du test. Les départs, eux, sont donnés explicitement.
GEL = datetime.datetime(2026, 9, 7, 7, 0, tzinfo=horaires.CASABLANCA)

#: Les 7 jours d'arrivée de la semaine du 7 septembre 2026 (lundi → dimanche),
#: tous à 11 h — une heure ouvrable, pour que seul le JOUR fasse la différence.
LUNDI = datetime.date(2026, 9, 7)
JOURS_DARRIVEE = [LUNDI + datetime.timedelta(days=n) for n in range(7)]
SAMEDI = datetime.date(2026, 9, 12)
DIMANCHE = datetime.date(2026, 9, 13)


def _a(jour, heure=11, minute=0):
    return datetime.datetime.combine(
        jour, datetime.time(heure, minute), tzinfo=horaires.CASABLANCA)


def _company(slug):
    company, _ = Company.objects.get_or_create(
        slug=slug, defaults={'nom': slug})
    CompanyProfile.objects.get_or_create(company=company)
    return company


class _Base(TestCase):
    slug = 'cad19'

    def setUp(self):
        gel = frozen(GEL)
        gel.start()
        self.addCleanup(gel.stop)
        self.company = _company(self.slug)
        self.acteur = User.objects.create_user(
            username=f'{self.slug}-resp', password='x',
            role_legacy='responsable', company=self.company)
        self.lead = Lead.objects.create(
            company=self.company, nom='Aziz', prenom='Benali',
            ville='Bouskoura', owner=self.acteur)

    def _plan(self, depart, cadence='contact'):
        """``{ordre: (gabarit, échéance locale)}`` — la partition datée."""
        return {
            gabarit.ordre: (gabarit,
                            echeance.astimezone(horaires.CASABLANCA))
            for gabarit, echeance in calculer_echeances_cadence(
                self.lead, cadence, depart)
        }

    def _origine(self, depart):
        return horaires.prochain_creneau_appel(
            depart, self.company, canal='whatsapp'
        ).astimezone(horaires.CASABLANCA)


class LesOnzeTouchesSurLesSeptJoursTests(_Base):
    """Le déroulé complet que le « Done = » demande."""

    slug = 'cad19-sept-jours'

    def test_les_onze_touches_existent_quel_que_soit_le_jour_darrivee(self):
        for jour in JOURS_DARRIVEE:
            plan = self._plan(_a(jour))
            self.assertEqual(len(plan), 11, jour)
            self.assertEqual(sorted(plan), list(range(1, 12)), jour)

    def test_aucune_touche_ne_precede_lorigine(self):
        for jour in JOURS_DARRIVEE:
            depart = _a(jour)
            origine = self._origine(depart)
            for ordre, (_gabarit, quand) in self._plan(depart).items():
                self.assertGreaterEqual(quand, origine, (jour, ordre))

    def test_chaque_touche_tombe_dans_la_fenetre_de_SON_canal(self):
        for jour in JOURS_DARRIVEE:
            for ordre, (gabarit, quand) in self._plan(_a(jour)).items():
                self.assertTrue(
                    horaires.est_dans_fenetre(
                        quand, self.company,
                        dimanche=bool(getattr(gabarit, 'dimanche_ok', False)),
                        canal=gabarit.canal),
                    (jour, ordre, quand))

    def test_les_trois_touches_J0_restent_sur_le_meme_jour(self):
        """Elles s'enchaînent (0 / +3 min / +2 h 30) depuis l'origine : c'est
        une SÉQUENCE dans une journée, jamais trois jours."""
        for jour in JOURS_DARRIVEE:
            depart = _a(jour)
            plan = self._plan(depart)
            jours_j0 = {plan[ordre][1].date() for ordre in (1, 2, 3)}
            self.assertEqual(jours_j0, {self._origine(depart).date()}, jour)

    def test_une_touche_dominicale_tombe_toujours_un_dimanche(self):
        for jour in JOURS_DARRIVEE:
            for ordre, (gabarit, quand) in self._plan(_a(jour)).items():
                if getattr(gabarit, 'dimanche_ok', False):
                    self.assertEqual(quand.weekday(), 6, (jour, ordre))
                else:
                    self.assertLess(quand.weekday(), 5, (jour, ordre))


class UnLeadDuSamediSetaleTests(_Base):
    """LE cas de la tâche."""

    slug = 'cad19-samedi'

    def test_un_lead_du_samedi_etale_J0_lundi_J1_mardi_J2_mercredi(self):
        plan = self._plan(_a(SAMEDI))
        self.assertEqual(plan[1][1].date(), datetime.date(2026, 9, 14))
        self.assertEqual(plan[2][1].date(), datetime.date(2026, 9, 14))
        self.assertEqual(plan[3][1].date(), datetime.date(2026, 9, 14))
        # J+1 : les deux touches du lendemain.
        self.assertEqual(plan[4][1].date(), datetime.date(2026, 9, 15))
        self.assertEqual(plan[5][1].date(), datetime.date(2026, 9, 15))
        # J+2.
        self.assertEqual(plan[6][1].date(), datetime.date(2026, 9, 16))

    def test_un_lead_du_dimanche_setale_pareil(self):
        plan = self._plan(_a(DIMANCHE))
        self.assertEqual(plan[1][1].date(), datetime.date(2026, 9, 14))
        self.assertEqual(plan[4][1].date(), datetime.date(2026, 9, 15))
        self.assertEqual(plan[6][1].date(), datetime.date(2026, 9, 16))

    def test_lheure_imposee_du_gabarit_est_respectee_le_bon_jour(self):
        """La touche J+1 porte une heure cible (10:30) et la J+2 une autre
        (18:00) : l'étalement ne les perd pas en route."""
        plan = self._plan(_a(SAMEDI))
        self.assertEqual((plan[4][1].hour, plan[4][1].minute), (10, 30))
        self.assertEqual((plan[6][1].hour, plan[6][1].minute), (18, 0))

    def test_un_lead_arrive_en_semaine_garde_ses_dates(self):
        """Garde négative : quand le départ est DÉJÀ joignable, l'origine lui
        est égale et rien ne bouge. Mercredi 09/09 11:00 → J+1 jeudi 10,
        J+2 vendredi 11."""
        plan = self._plan(_a(datetime.date(2026, 9, 9)))
        self.assertEqual(plan[1][1].date(), datetime.date(2026, 9, 9))
        self.assertEqual(plan[4][1].date(), datetime.date(2026, 9, 10))
        self.assertEqual(plan[6][1].date(), datetime.date(2026, 9, 11))


class LeSuiviApresDevisSetaleAussiTests(_Base):
    """« Même test sur `apres_devis` » : un devis fini hors fenêtre."""

    slug = 'cad19-apres-devis'

    def test_un_devis_envoye_le_samedi_etale_J1_J2_J4(self):
        plan = self._plan(_a(SAMEDI), cadence='apres_devis')
        # J+1, J+2, J+4 depuis l'origine (lundi 14) : mardi, mercredi,
        # vendredi — trois jours distincts, plus deux touches sur le lundi.
        self.assertEqual(plan[1][1].date(), datetime.date(2026, 9, 15))
        self.assertEqual(plan[2][1].date(), datetime.date(2026, 9, 16))
        self.assertEqual(plan[4][1].date(), datetime.date(2026, 9, 18))

    def test_un_devis_envoye_le_vendredi_soir_ne_les_empile_plus(self):
        """Vendredi 21:30 : après la fermeture. Sans l'ancre unique, J+1
        (samedi) et J+2 (dimanche) retombaient tous deux sur le lundi."""
        vendredi_soir = _a(datetime.date(2026, 9, 11), heure=21, minute=30)
        plan = self._plan(vendredi_soir, cadence='apres_devis')
        jours = [plan[ordre][1].date() for ordre in (1, 2, 4)]
        self.assertEqual(len(set(jours)), 3, jours)
        self.assertEqual(jours[0], datetime.date(2026, 9, 15))
        self.assertEqual(jours[1], datetime.date(2026, 9, 16))

    def test_la_touche_famille_reste_reservee_aux_dossiers_etiquetes(self):
        """Garde négative MRY4 : l'ancre unique ne réintroduit pas le barreau
        dominical sur un lead qui ne porte pas l'étiquette."""
        plan = self._plan(_a(SAMEDI), cadence='apres_devis')
        self.assertNotIn(3, plan)


class LeGardeFouDesTroisPremieresTouchesTests(_Base):
    """La minute près : le résultat de `tests_mry5_relance_v2` ne bouge pas."""

    slug = 'cad19-garde-fou'

    def test_dimanche_12h28_donne_toujours_lundi_08h30_09h00_11h00(self):
        plan = self._plan(_a(datetime.date(2026, 9, 6), heure=12, minute=28))
        self.assertEqual(
            [(plan[ordre][1].date(), plan[ordre][1].hour,
              plan[ordre][1].minute) for ordre in (1, 2, 3)],
            [(datetime.date(2026, 9, 7), 8, 30),
             (datetime.date(2026, 9, 7), 9, 0),
             (datetime.date(2026, 9, 7), 11, 0)])

    def test_la_touche_dominicale_reste_un_dimanche_a_16h30(self):
        """L'autre garde-fou de MRY4 : la touche dominicale d'un lead du
        mercredi tombe bien un DIMANCHE, à 16:30. Sa DATE exacte relève de
        CAD23 (le dimanche le plus proche de J+5) — pinnée là-bas, pas ici."""
        plan = self._plan(_a(datetime.date(2026, 9, 2), heure=10))
        dominicales = [quand for _g, quand in plan.values()
                       if quand.weekday() == 6]
        self.assertEqual(len(dominicales), 1)
        self.assertEqual((dominicales[0].hour, dominicales[0].minute),
                         (16, 30))


class LexceptionDuReveilTests(_Base):
    """MRY30 rétrodate le départ d'un réveil pour tomber SUR son créneau."""

    slug = 'cad19-reveil'

    def test_le_reveil_garde_son_depart_pour_ancre(self):
        """Départ rétrodaté un SAMEDI (le créneau visé est 30 jours plus
        tard) : ancrer sur l'origine ouvrable décalerait le créneau de deux
        jours et ferait dérailler le quota de réveils par jour ouvré."""
        depart = _a(datetime.date(2026, 8, 15), heure=10)   # samedi
        self.assertEqual(depart.weekday(), 5)
        plan = self._plan(depart, cadence='reveil')
        premier = plan[1][1]
        self.assertEqual(premier.date(), datetime.date(2026, 9, 14))
        self.assertEqual((premier.hour, premier.minute), (10, 0))

    def test_le_second_reveil_suit_la_meme_ancre(self):
        depart = _a(datetime.date(2026, 8, 15), heure=10)
        plan = self._plan(depart, cadence='reveil')
        self.assertEqual(
            (plan[2][1] - plan[1][1]).days, 30,
            (plan[1][1], plan[2][1]))
