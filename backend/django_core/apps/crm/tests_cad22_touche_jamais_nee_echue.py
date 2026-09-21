"""CAD22 — une touche ne naît jamais déjà échue, un report ne laisse personne
derrière, et l'adhérence n'accuse plus à tort.

Trois défauts du moteur du temps, un seul mécanisme :

  * l'appel du dimanche est placé sur le premier dimanche atteignant J+5 —
    donc entre J+5 et J+11 selon le jour d'arrivée du lead. Les touches
    naissent dans l'ordre du PROTOCOLE : quand la touche J+7 naît APRÈS cet
    appel, son échéance calculée est déjà passée. Au grain JOUR de
    `selectors._a_lheure`, elle ne peut alors JAMAIS être à l'heure, et le
    cockpit compte un manquement que personne n'a commis ;
  * `reporter_prochaine_touche` ne décalait que les touches d'`ordre`
    supérieur — alors que l'ordre chronologique diverge de l'ordre du
    protocole. La touche dominicale, d'ordre INFÉRIEUR mais de date
    POSTÉRIEURE, restait sur place : le plan se réordonnait en silence ;
  * une touche traitée EN AVANCE, et une touche NÉE en retard, comptaient
    toutes deux comme un manquement d'adhérence.

Le protocole n'est pas touché : ni le nombre, ni l'ordre, ni le J+N des
touches. Seule change la DATE d'une touche qui naîtrait dans le passé.

Le temps est GELÉ partout — « déjà échue » est exactement la question qu'une
horloge vivante rend instable.
"""
import datetime
from types import SimpleNamespace

from django.contrib.auth import get_user_model
from django.test import SimpleTestCase, TestCase

from authentication.models import Company
from testkit.time import frozen

from apps.crm import cadence_temps, horaires
from apps.crm.models import Lead, RelanceEtape
from apps.crm.selectors import _a_lheure
from apps.crm.services import (
    calculer_echeances_cadence, materialiser_touche_suivante,
    reporter_prochaine_touche)
from apps.parametres.models import CompanyProfile

User = get_user_model()

#: Mercredi 9 septembre 2026, 10 h à Casablanca — jour ouvré, en fenêtre.
#: C'est le jour d'arrivée que la tâche nomme : pour lui, l'appel du dimanche
#: (J+5 → lundi 14) glisse au dimanche 20, APRÈS la touche J+7 (mercredi 16).
MERCREDI = datetime.datetime(2026, 9, 9, 10, 0, tzinfo=horaires.CASABLANCA)


def _company(slug):
    company, _ = Company.objects.get_or_create(
        slug=slug, defaults={'nom': slug})
    CompanyProfile.objects.get_or_create(company=company)
    return company


def _etape_fictive(**champs):
    """Une touche en MÉMOIRE : `_a_lheure` et `nee_en_retard` ne lisent que
    des attributs, jamais la base — on les interroge donc sans base."""
    defauts = {'statut': 'fait', 'traite_le': None, 'due_date': None,
               'due_at': None, 'created_at': None, 'cadence_depart': None}
    defauts.update(champs)
    return SimpleNamespace(**defauts)


class EcheanceJamaisEchueTests(SimpleTestCase):
    """La règle de date, isolée de toute base."""

    def test_une_echeance_future_est_rendue_telle_quelle(self):
        echeance = MERCREDI + datetime.timedelta(days=2)
        self.assertEqual(
            cadence_temps.echeance_jamais_echue(
                echeance, company=None, maintenant=MERCREDI),
            echeance)

    def test_une_echeance_nulle_reste_nulle(self):
        self.assertIsNone(cadence_temps.echeance_jamais_echue(
            None, company=None, maintenant=MERCREDI))

    def test_une_touche_dominicale_echue_repart_sur_un_DIMANCHE(self):
        """Le seul rendez-vous dominical du protocole reste un dimanche : on
        ne le rattrape pas un mardi sous prétexte qu'il est en retard."""
        maintenant = MERCREDI + datetime.timedelta(days=20)
        rattrapee = cadence_temps.echeance_jamais_echue(
            MERCREDI, company=None, dimanche=True, maintenant=maintenant)
        locale = rattrapee.astimezone(horaires.CASABLANCA)
        self.assertEqual(locale.weekday(), 6)
        self.assertGreaterEqual(rattrapee, maintenant)


class NeeEnRetardTests(SimpleTestCase):
    """Qui a le droit d'être excusé — et qui ne l'a pas."""

    def test_une_touche_creee_apres_son_echeance_est_nee_en_retard(self):
        self.assertTrue(cadence_temps.nee_en_retard(_etape_fictive(
            due_at=MERCREDI,
            created_at=MERCREDI + datetime.timedelta(days=1),
            cadence_depart=MERCREDI)))

    def test_une_touche_creee_avant_son_echeance_ne_lest_pas(self):
        self.assertFalse(cadence_temps.nee_en_retard(_etape_fictive(
            due_at=MERCREDI + datetime.timedelta(days=1),
            created_at=MERCREDI,
            cadence_depart=MERCREDI)))

    def test_une_ligne_SANS_ancre_nest_jamais_excusee(self):
        """Avant CKP2 tout le plan naissait d'un bloc à l'initialisation :
        `created_at` n'y dit rien de la naissance d'UNE touche. S'en servir
        inventerait une excuse au lieu de constater un fait."""
        self.assertFalse(cadence_temps.nee_en_retard(_etape_fictive(
            due_at=MERCREDI,
            created_at=MERCREDI + datetime.timedelta(days=1),
            cadence_depart=None)))

    def test_une_ligne_sans_heure_decheance_nest_jamais_excusee(self):
        self.assertFalse(cadence_temps.nee_en_retard(_etape_fictive(
            due_at=None,
            created_at=MERCREDI + datetime.timedelta(days=1),
            cadence_depart=MERCREDI)))


class AdherenceNaccusePlusATortTests(SimpleTestCase):
    """Garde-fou de CAD22 sur `selectors._a_lheure` (grain JOUR inchangé)."""

    def test_une_touche_faite_le_jour_dit_reste_a_lheure(self):
        self.assertTrue(_a_lheure(_etape_fictive(
            traite_le=MERCREDI, due_date=MERCREDI.date())))

    def test_une_touche_traitee_EN_AVANCE_est_a_lheure(self):
        """Prendre de l'avance n'est pas un manquement — l'égalité stricte
        punissait exactement le geste qu'on attend."""
        self.assertTrue(_a_lheure(_etape_fictive(
            traite_le=MERCREDI,
            due_date=(MERCREDI + datetime.timedelta(days=2)).date())))

    def test_une_touche_faite_en_retard_reste_un_manquement(self):
        self.assertFalse(_a_lheure(_etape_fictive(
            traite_le=MERCREDI,
            due_date=(MERCREDI - datetime.timedelta(days=2)).date())))

    def test_une_touche_NEE_en_retard_nest_pas_un_manquement(self):
        """Personne n'a jamais eu la chance de la faire à l'heure."""
        self.assertTrue(_a_lheure(_etape_fictive(
            traite_le=MERCREDI,
            due_date=(MERCREDI - datetime.timedelta(days=4)).date(),
            due_at=MERCREDI - datetime.timedelta(days=4),
            created_at=MERCREDI - datetime.timedelta(hours=2),
            cadence_depart=MERCREDI - datetime.timedelta(days=11))))

    def test_une_touche_non_faite_nest_jamais_a_lheure(self):
        self.assertFalse(_a_lheure(_etape_fictive(
            statut='sautee', traite_le=MERCREDI, due_date=MERCREDI.date())))


class ToucheJamaisNeeEchueTests(TestCase):
    """Le cas de la tâche : lead du MERCREDI, touche J+7 qui naîtrait déjà
    échue derrière l'appel du dimanche.

    Depuis le fold de CAD23 (dimanche le PLUS PROCHE de J+N), ce n'est plus
    le PLACEMENT du rendez-vous dominical qui crée le retard mais son
    TRAITEMENT tardif — la règle de CAD22, elle, est la même."""

    def setUp(self):
        gel = frozen(MERCREDI)
        gel.start()
        self.addCleanup(gel.stop)
        self.company = _company('cad22-naissance')
        self.acteur = User.objects.create_user(
            username='cad22-naissance-u', password='x',
            role_legacy='responsable', company=self.company)
        self.lead = Lead.objects.create(
            company=self.company, nom='Aziz', prenom='Benali',
            ville='Bouskoura', owner=self.acteur)
        self.echeances = calculer_echeances_cadence(
            self.lead, 'contact', MERCREDI)

    def _partition(self, ordre):
        for gabarit, echeance in self.echeances:
            if gabarit.ordre == ordre:
                return gabarit, echeance
        self.fail(f'barreau {ordre} absent de la cadence « contact »')

    def _ordre_dominical(self):
        for gabarit, _echeance in self.echeances:
            if getattr(gabarit, 'dimanche_ok', False):
                return gabarit.ordre
        self.fail('aucune touche dominicale dans la cadence « contact »')

    def test_depuis_CAD23_la_touche_du_dimanche_tombe_AVANT_la_suivante(self):
        """Le DÉCOR du bug a disparu — et c'est CAD23 qui l'a supprimé.

        Quand CAD22 a été écrite, l'appel dominical se posait sur le PREMIER
        dimanche atteignant J+5 : pour un lead du mercredi il glissait au
        dimanche 20/09, donc APRÈS la touche J+7 (mercredi 16/09), et c'est
        cet ordre-là que ce test épinglait.

        CAD23 (TRANCHÉ 21/09/2026, fold du même jour) le place désormais sur
        le dimanche le PLUS PROCHE de J+N, avant ou après : pour ce même lead
        du mercredi, J+5 tombe le lundi 14/09 et le rendez-vous se cale sur le
        dimanche 13/09. Comme l'ancre de la cadence est toujours un jour
        OUVRABLE (CAD19, lundi-vendredi), le dimanche le plus proche de J+5 ne
        dépasse jamais J+6 : la touche dominicale est structurellement AVANT
        la touche J+7, pour tous les jours d'arrivée.

        La règle de CAD22 elle-même — « une touche ne naît jamais déjà
        échue » — n'est pas touchée : elle reste vérifiée par
        ``EcheanceJamaisEchueTests`` et par le test suivant, qui construit
        désormais le retard par la seule cause qui subsiste (une touche
        TRAITÉE en retard).
        """
        ordre_dimanche = self._ordre_dominical()
        gabarit_dimanche, dimanche = self._partition(ordre_dimanche)
        _g2, suivante = self._partition(ordre_dimanche + 1)
        self.assertLess(dimanche, suivante)
        # Le garde-fou de CAD23 : l'écart au J+N visé ne dépasse pas 3 jours.
        vise = (MERCREDI + datetime.timedelta(
            days=gabarit_dimanche.delai_jours)).astimezone(
                horaires.CASABLANCA).date()
        pose = dimanche.astimezone(horaires.CASABLANCA).date()
        self.assertLessEqual(abs((pose - vise).days), 3)

    def test_la_touche_suivante_nait_avec_une_echeance_FUTURE(self):
        """CAD22 — l'appel dominical TRAITÉ EN RETARD ne fait pas naître une
        touche déjà échue.

        Depuis CAD23 la touche dominicale ne dépasse plus la touche J+7 (voir
        le test précédent), mais la règle de CAD22 garde tout son objet : il
        suffit que l'appel du dimanche soit traité en retard — ici le JEUDI
        17/09, après l'échéance de partition de la J+7 (mercredi 16/09) —
        pour que la touche suivante naisse avec une date passée. Elle ne
        pourrait alors JAMAIS être « à l'heure » (grain jour,
        ``selectors._a_lheure``) et le cockpit compterait un manquement que
        personne n'a commis.
        """
        ordre_dimanche = self._ordre_dominical()
        gabarit, echeance_dimanche = self._partition(ordre_dimanche)
        _g2, echeance_partition = self._partition(gabarit.ordre + 1)
        # L'appel du dimanche n'est traité que le JEUDI suivant, APRÈS
        # l'échéance de partition de la touche J+7.
        traite_tard = echeance_partition + datetime.timedelta(
            days=1, hours=2)
        self.assertLess(echeance_partition, traite_tard)
        close = RelanceEtape.objects.create(
            company=self.company, lead=self.lead, cadence='contact',
            ordre=gabarit.ordre, due_at=echeance_dimanche,
            due_date=echeance_dimanche.astimezone(
                horaires.CASABLANCA).date(),
            canal=gabarit.canal, libelle=gabarit.libelle,
            template_cle=getattr(gabarit, 'template_cle', '') or '',
            cadence_depart=MERCREDI,
            statut=RelanceEtape.Statut.FAIT, traite_par=self.acteur,
            traite_le=traite_tard)
        gel = frozen(traite_tard)
        gel.start()
        self.addCleanup(gel.stop)
        maintenant = traite_tard  # horloge GELÉE sur ce jeudi

        nee = materialiser_touche_suivante(close, self.acteur)

        self.assertIsNotNone(nee)
        self.assertEqual(nee.ordre, gabarit.ordre + 1)
        self.assertGreaterEqual(nee.due_at, maintenant)
        self.assertEqual(
            nee.due_date, nee.due_at.astimezone(horaires.CASABLANCA).date())
        self.assertFalse(cadence_temps.nee_en_retard(nee))

    def test_une_touche_dont_lecheance_est_future_ne_bouge_PAS(self):
        """Garde-fou : le rattrapage ne touche QUE les échéances passées —
        le J+N du protocole reste le J+N du protocole."""
        premier, echeance_1 = self.echeances[0]
        close = RelanceEtape.objects.create(
            company=self.company, lead=self.lead, cadence='contact',
            ordre=premier.ordre, due_at=echeance_1,
            due_date=echeance_1.astimezone(horaires.CASABLANCA).date(),
            canal=premier.canal, libelle=premier.libelle,
            template_cle=getattr(premier, 'template_cle', '') or '',
            cadence_depart=MERCREDI,
            statut=RelanceEtape.Statut.FAIT, traite_par=self.acteur,
            traite_le=echeance_1)
        nee = materialiser_touche_suivante(close, self.acteur)
        self.assertIsNotNone(nee)
        self.assertGreaterEqual(nee.due_at, MERCREDI)  # horloge GELÉE


class ReportNeLaissePersonneDerriereTests(TestCase):
    """`reporter_prochaine_touche` — l'ordre du plan ne se défait pas."""

    def setUp(self):
        gel = frozen(MERCREDI)
        gel.start()
        self.addCleanup(gel.stop)
        self.company = _company('cad22-report')
        self.acteur = User.objects.create_user(
            username='cad22-report-u', password='x',
            role_legacy='responsable', company=self.company)
        self.lead = Lead.objects.create(
            company=self.company, nom='Karim', prenom='Alaoui',
            ville='Bouskoura', owner=self.acteur)
        # Le plan tel qu'un lead du mercredi le porte : la touche J+7
        # (ordre 9) tombe AVANT l'appel dominical (ordre 8, J+11).
        self.j7 = self._touche(ordre=9, jours=7)
        self.dimanche = self._touche(ordre=8, jours=11,
                                     canal=RelanceEtape.Canal.APPEL)
        self.j14 = self._touche(ordre=11, jours=14)

    def _touche(self, *, ordre, jours, canal=RelanceEtape.Canal.WHATSAPP):
        due = MERCREDI + datetime.timedelta(days=jours)
        return RelanceEtape.objects.create(
            company=self.company, lead=self.lead, cadence='contact',
            ordre=ordre, due_at=due,
            due_date=due.astimezone(horaires.CASABLANCA).date(),
            canal=canal, libelle=f'Touche {ordre}',
            cadence_depart=MERCREDI)

    def test_un_report_ne_laisse_aucune_touche_dordre_inferieur_derriere(self):
        """Done de CAD22 : après le report, AUCUNE touche d'ordre inférieur
        ne reste plantée derrière la touche reportée. L'appel dominical
        (ordre 8) est d'ordre INFÉRIEUR à la touche reportée (ordre 9) mais
        de date POSTÉRIEURE : le filtre `ordre__gt` le laissait sur place, et
        le plan se réordonnait tout seul.

        TOUT SE COMPARE EN INSTANTS (UTC), et ce n'est pas un détail de
        forme. Ce plan-ci enjambe la bascule du décret 2.26.530 : le Maroc
        passe de UTC+1 à UTC+0 dans la nuit du 19 au 20/09/2026 (CAD30,
        tzdata épinglée). Or Python soustrait DEUX datetimes qui partagent le
        MÊME objet `tzinfo` en heure MURALE, pas en instants : les objets en
        mémoire, tous porteurs de `horaires.CASABLANCA`, donnaient ici un
        delta de 8 jours pile là où le moteur — qui relit des instants UTC
        depuis la base — décale de 8 jours et 1 heure. Une heure d'écart, sur
        une comparaison censée vérifier « le MÊME delta pour tout le monde ».
        On convertit donc chaque côté en UTC avant de soustraire et
        d'ajouter : le delta est alors celui du temps réellement écoulé, des
        deux côtés."""
        avant_dimanche = self.dimanche.due_at.astimezone(datetime.timezone.utc)
        avant_j14 = self.j14.due_at.astimezone(datetime.timezone.utc)

        cible = reporter_prochaine_touche(
            self.lead, self.acteur,
            MERCREDI + datetime.timedelta(days=15))

        self.assertIsNotNone(cible)
        self.assertEqual(cible.ordre, 9)
        delta = (cible.due_at.astimezone(datetime.timezone.utc)
                 - self.j7.due_at.astimezone(datetime.timezone.utc))
        self.dimanche.refresh_from_db()
        self.j14.refresh_from_db()
        self.assertEqual(self.dimanche.due_at, avant_dimanche + delta)
        self.assertEqual(self.j14.due_at, avant_j14 + delta)
        self.assertGreater(self.dimanche.due_at, cible.due_at)
        self.assertGreater(self.j14.due_at, cible.due_at)

    def test_les_dates_LOCALES_suivent_les_heures(self):
        reporter_prochaine_touche(
            self.lead, self.acteur,
            MERCREDI + datetime.timedelta(days=15))
        for touche in (self.dimanche, self.j14):
            touche.refresh_from_db()
            self.assertEqual(
                touche.due_date,
                touche.due_at.astimezone(horaires.CASABLANCA).date())

    def test_une_touche_ANTERIEURE_a_la_reportee_ne_bouge_pas(self):
        """Garde-fou symétrique : on décale ce qui vient APRÈS, jamais ce qui
        est déjà derrière — sinon un report repousserait le passé."""
        anterieure = self._touche(ordre=7, jours=3)
        avant = anterieure.due_at
        reporter_prochaine_touche(
            self.lead, self.acteur,
            MERCREDI + datetime.timedelta(days=15),
            etape=self.j7)
        anterieure.refresh_from_db()
        self.assertEqual(anterieure.due_at, avant)
