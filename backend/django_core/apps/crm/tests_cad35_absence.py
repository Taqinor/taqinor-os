"""CAD35 — une absence déclarée n'accuse personne.

Rien ne suspendait les cadences quand la personne qui les tient est absente.
En régime RÉACTIF les touches naissent quand même, elles échoient pendant le
congé, et `selectors._a_lheure` comptait un manquement pour chacune : le
cockpit d'adhérence (CKP3) reprochait à quelqu'un ses propres vacances.

Ce que ce fichier verrouille :
  * une touche échue PENDANT une absence déclarée n'est comptée en retard
    NULLE PART dans CKP3 (adhérence globale, touches en retard ouvertes,
    tuiles personnelles, série de jours sans retard) ;
  * le GARDE-FOU : aucune touche n'est supprimée, aucune n'est avancée,
    aucune n'est décalée — l'absence neutralise une MESURE, pas le suivi ;
  * l'absence de QUELQU'UN D'AUTRE n'excuse personne, et une fermeture de
    société (sans utilisateur) couvre tout le monde ;
  * la période est VISIBLE : le cockpit la sert dans `absences_declarees`,
    avec la personne qui reprend les dossiers, sans aucun prénom en dur.

Le temps est GELÉ : « échue pendant », « en retard » et « les 7 derniers
jours » sont exactement les questions qu'une horloge vivante rend instables.
"""
import datetime

from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.test import SimpleTestCase, TestCase

from authentication.models import Company
from testkit.time import frozen

from apps.crm import horaires, stages
from apps.crm.cadence_absence import CouvertureAbsences
from apps.crm.models import Lead, PeriodeAbsence, RelanceEtape
from apps.crm.selectors import kpi_adherence, mes_stats_relance
from apps.parametres.models import CompanyProfile

User = get_user_model()

#: Jeudi 10 septembre 2026, 12 h à Casablanca — jour ouvré, en pleine fenêtre.
MAINTENANT = datetime.datetime(2026, 9, 10, 12, 0, tzinfo=horaires.CASABLANCA)
AUJOURDHUI = MAINTENANT.date()


def _jour(jours_avant):
    return AUJOURDHUI - datetime.timedelta(days=jours_avant)


def _quand(jours_avant, heure=10):
    return datetime.datetime.combine(
        _jour(jours_avant), datetime.time(heure, 0),
        tzinfo=horaires.CASABLANCA)


def _company(slug):
    company, _ = Company.objects.get_or_create(
        slug=slug, defaults={'nom': slug})
    CompanyProfile.objects.get_or_create(company=company)
    return company


class _PeriodeFictive:
    """Une période en mémoire — `CouvertureAbsences` ne lit que ces
    attributs, jamais la base."""

    def __init__(self, utilisateur_id, debut, fin):
        self.pk = 1
        self.utilisateur_id = utilisateur_id
        self.remplacant_id = None
        self.motif = 'conge'
        self.date_debut = debut
        self.date_fin = fin

    def couvre(self, jour):
        return self.date_debut <= jour <= self.date_fin


class CouvertureTests(SimpleTestCase):
    """La règle de couverture, isolée de toute base."""

    def setUp(self):
        self.couverture = CouvertureAbsences([
            _PeriodeFictive(7, _jour(5), _jour(2)),
            _PeriodeFictive(None, _jour(20), _jour(19)),
        ])

    def test_un_jour_dans_MON_absence_est_couvert(self):
        self.assertTrue(self.couverture.couvre(7, _jour(3)))

    def test_les_bornes_sont_COMPRISES(self):
        self.assertTrue(self.couverture.couvre(7, _jour(5)))
        self.assertTrue(self.couverture.couvre(7, _jour(2)))

    def test_un_jour_hors_periode_nest_pas_couvert(self):
        self.assertFalse(self.couverture.couvre(7, _jour(1)))

    def test_labsence_dun_AUTRE_nexcuse_personne(self):
        self.assertFalse(self.couverture.couvre(9, _jour(3)))

    def test_une_fermeture_de_societe_couvre_TOUT_LE_MONDE(self):
        self.assertTrue(self.couverture.couvre(9, _jour(20)))
        self.assertTrue(self.couverture.couvre(None, _jour(19)))

    def test_sans_periode_rien_nest_couvert(self):
        vide = CouvertureAbsences([])
        self.assertFalse(bool(vide))
        self.assertFalse(vide.couvre(7, _jour(3)))
        self.assertEqual(vide.resume(), [])


class _Base(TestCase):
    slug = 'cad35'

    def setUp(self):
        gel = frozen(MAINTENANT)
        gel.start()
        self.addCleanup(gel.stop)
        self.company = _company(self.slug)
        self.acteur = User.objects.create_user(
            username=f'{self.slug}-resp', password='x',
            role_legacy='responsable', company=self.company)
        self.lead = Lead.objects.create(
            company=self.company, nom='Aziz', prenom='Benali',
            ville='Bouskoura', stage=stages.CONTACTED, owner=self.acteur)

    def _touche(self, *, statut, due_jours, traite_jours=None, ordre=1,
                canal=RelanceEtape.Canal.APPEL):
        due = _quand(due_jours)
        return RelanceEtape.objects.create(
            company=self.company, lead=self.lead, cadence='contact',
            ordre=ordre, due_at=due, due_date=due.date(), canal=canal,
            libelle='Appel d’ouverture', statut=statut,
            traite_le=(None if traite_jours is None
                       else _quand(traite_jours)),
            traite_par=(None if traite_jours is None else self.acteur))

    def _absence(self, *, debut_jours, fin_jours, utilisateur=-1,
                 remplacant=None):
        return PeriodeAbsence.objects.create(
            company=self.company,
            utilisateur=(self.acteur if utilisateur == -1 else utilisateur),
            date_debut=_jour(debut_jours), date_fin=_jour(fin_jours),
            remplacant=remplacant)


class ToucheEchuePendantUneAbsenceTests(_Base):
    """LE Done de CAD35."""

    slug = 'cad35-echue'

    def setUp(self):
        super().setUp()
        # Une touche due il y a 5 jours et faite il y a 2 : en retard.
        self.retard = self._touche(
            statut='fait', due_jours=5, traite_jours=2, ordre=1)
        # Une touche due et faite le même jour : à l'heure, témoin.
        self._touche(statut='fait', due_jours=1, traite_jours=1, ordre=2)

    def test_sans_absence_la_touche_en_retard_est_un_manquement(self):
        """Le décor : sans période déclarée, le comportement d'aujourd'hui
        est INCHANGÉ — une sur deux à l'heure."""
        kpi = kpi_adherence(self.company, self.acteur, 30)
        self.assertEqual(kpi['a_lheure_pct'], 50.0)

    def test_une_touche_echue_pendant_une_absence_nest_pas_en_retard(self):
        self._absence(debut_jours=6, fin_jours=3)
        kpi = kpi_adherence(self.company, self.acteur, 30)
        self.assertEqual(kpi['a_lheure_pct'], 100.0)

    def test_labsence_dun_COLLEGUE_ne_neutralise_rien(self):
        collegue = User.objects.create_user(
            username=f'{self.slug}-autre', password='x',
            role_legacy='normal', company=self.company)
        self._absence(debut_jours=6, fin_jours=3, utilisateur=collegue)
        kpi = kpi_adherence(self.company, self.acteur, 30)
        self.assertEqual(kpi['a_lheure_pct'], 50.0)

    def test_une_fermeture_de_societe_neutralise_pour_tous(self):
        self._absence(debut_jours=6, fin_jours=3, utilisateur=None)
        kpi = kpi_adherence(self.company, self.acteur, 30)
        self.assertEqual(kpi['a_lheure_pct'], 100.0)

    def test_AUCUNE_touche_nest_supprimee_avancee_ni_decalee(self):
        """Le garde-fou de la tâche, vérifié sur la ligne elle-même."""
        avant = (self.retard.due_at, self.retard.due_date,
                 self.retard.statut)
        self._absence(debut_jours=6, fin_jours=3)
        kpi_adherence(self.company, self.acteur, 30)
        mes_stats_relance(self.company, self.acteur)
        self.retard.refresh_from_db()
        self.assertEqual(
            (self.retard.due_at, self.retard.due_date, self.retard.statut),
            avant)
        self.assertEqual(
            RelanceEtape.objects.filter(lead=self.lead).count(), 2)


class TouchesOuvertesEtTuilesTests(_Base):
    """« En retard » là où le mot est écrit : les touches ouvertes et les
    tuiles personnelles."""

    slug = 'cad35-ouvertes'

    def setUp(self):
        super().setUp()
        self.ouverte = self._touche(statut='a_faire', due_jours=4, ordre=1)

    def test_une_touche_ouverte_echue_pendant_une_absence_sort_du_compte(
            self):
        kpi = kpi_adherence(self.company, self.acteur, 30)
        self.assertEqual(kpi['touches_en_retard_ouvertes'], 1)
        self._absence(debut_jours=6, fin_jours=3)
        kpi = kpi_adherence(self.company, self.acteur, 30)
        self.assertEqual(kpi['touches_en_retard_ouvertes'], 0)

    def test_ma_tuile_en_retard_ne_compte_pas_mes_jours_dabsence(self):
        stats = mes_stats_relance(self.company, self.acteur)
        self.assertEqual(stats['en_retard'], 1)
        self._absence(debut_jours=6, fin_jours=3)
        stats = mes_stats_relance(self.company, self.acteur)
        self.assertEqual(stats['en_retard'], 0)

    def test_la_touche_reste_A_FAIRE_dans_la_file(self):
        """Elle n'est pas comptée en retard — elle reste à faire : l'absence
        neutralise une MESURE, elle n'éteint pas le suivi."""
        self._absence(debut_jours=6, fin_jours=3)
        stats = mes_stats_relance(self.company, self.acteur)
        self.assertEqual(stats['a_faire_maintenant'], 1)
        self.ouverte.refresh_from_db()
        self.assertEqual(self.ouverte.statut, 'a_faire')


class AbsenceVisibleDansLeCockpitTests(_Base):
    """(b) de CAD35 : l'absence se VOIT, avec la reprise des dossiers."""

    slug = 'cad35-cockpit'

    def test_le_cockpit_sert_les_periodes_declarees(self):
        remplacant = User.objects.create_user(
            username=f'{self.slug}-remplacant', password='x',
            role_legacy='normal', company=self.company)
        absence = self._absence(debut_jours=6, fin_jours=3,
                                remplacant=remplacant)
        kpi = kpi_adherence(self.company, self.acteur, 30)
        self.assertEqual(len(kpi['absences_declarees']), 1)
        ligne = kpi['absences_declarees'][0]
        self.assertEqual(ligne['id'], absence.pk)
        self.assertEqual(ligne['utilisateur_id'], self.acteur.pk)
        self.assertEqual(ligne['remplacant_id'], remplacant.pk)
        self.assertEqual(ligne['motif'], 'conge')
        self.assertEqual(ligne['date_debut'], _jour(6).isoformat())
        self.assertEqual(ligne['date_fin'], _jour(3).isoformat())

    def test_sans_absence_la_liste_est_vide_jamais_absente(self):
        kpi = kpi_adherence(self.company, self.acteur, 30)
        self.assertEqual(kpi['absences_declarees'], [])

    def test_la_forme_reste_celle_de_lechantillon(self):
        import json
        from pathlib import Path
        echantillon = json.loads(
            (Path(__file__).resolve().parent / 'contract_samples'
             / 'kpi_adherence.json').read_text(encoding='utf-8'))
        kpi = kpi_adherence(self.company, self.acteur, 30)
        self.assertEqual(set(kpi), set(echantillon['exemple']))


class PeriodeAbsenceModeleTests(_Base):
    """Le modèle dit non proprement, en désignant LE champ fautif."""

    slug = 'cad35-modele'

    def test_une_fin_avant_le_debut_est_refusee_sur_le_champ_date_fin(self):
        periode = PeriodeAbsence(
            company=self.company, utilisateur=self.acteur,
            date_debut=_jour(2), date_fin=_jour(5))
        with self.assertRaises(ValidationError) as leve:
            periode.clean()
        self.assertIn('date_fin', leve.exception.error_dict)

    def test_une_periode_dun_seul_jour_est_valide(self):
        periode = PeriodeAbsence(
            company=self.company, utilisateur=self.acteur,
            date_debut=_jour(2), date_fin=_jour(2))
        periode.clean()
        self.assertTrue(periode.couvre(_jour(2)))
        self.assertFalse(periode.couvre(_jour(1)))

    def test_une_societe_ne_voit_pas_labsence_de_lautre(self):
        autre = _company(f'{self.slug}-bis')
        autre_user = User.objects.create_user(
            username=f'{self.slug}-bis-u', password='x',
            role_legacy='responsable', company=autre)
        autre_lead = Lead.objects.create(
            company=autre, nom='Karim', ville='Casablanca',
            stage=stages.CONTACTED, owner=autre_user)
        due = _quand(5)
        RelanceEtape.objects.create(
            company=autre, lead=autre_lead, cadence='contact', ordre=1,
            due_at=due, due_date=due.date(),
            canal=RelanceEtape.Canal.APPEL, libelle='Appel d’ouverture',
            statut='fait', traite_le=_quand(2), traite_par=autre_user)
        # Absence déclarée dans MA société : elle n'excuse rien chez l'autre.
        self._absence(debut_jours=6, fin_jours=3)
        kpi = kpi_adherence(autre, autre_user, 30)
        self.assertEqual(kpi['absences_declarees'], [])
        self.assertEqual(kpi['a_lheure_pct'], 0.0)
