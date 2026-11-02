"""CAD43 — le drapeau `samedi_ok` PAR TOUCHE, symétrique de `dimanche_ok`.

Constat de l'audit L3 du 21/09/2026 : les jours ouvrés par défaut sont
lundi-vendredi, donc toute touche calculée un samedi est repoussée au lundi
08:30 — y compris le message d'identité J0, qui n'a pas `dimanche_ok`. La
case « Samedi » de Paramètres → Notifications existe, mais la cocher ouvrirait
le samedi aux SIX appels d'un coup. Ce drapeau ouvre UNE touche : le message
d'identité (canal silencieux) du lead arrivé le vendredi soir.

Garde-fou vérifié ici : **`samedi_ok = False` partout par défaut** — aucun
gabarit du protocole ne l'active, rien ne change tant que personne ne coche.

Contrat partagé (PACT10) : ce module AFFIRME l'exemple committé dans
``apps/parametres/contract_samples/cadence_relance_v2.json``, que le test
frontend IMPORTE — jamais un mock écrit à la main de chaque côté.
"""
import datetime
import json
import pathlib
from unittest import mock

from django.contrib.auth import get_user_model
from django.test import SimpleTestCase, TestCase

from authentication.models import Company
from testkit.time import frozen

from apps.crm import horaires, stages
from apps.crm.models import Lead, RelanceEtape
from apps.crm.cadence_plan import calculer_echeances_cadence
from apps.parametres.models import CompanyProfile
from apps.parametres.models_relance import (
    CADENCES_DEFAUT, CadenceRelanceEtape, CanalRelance,
)
from apps.parametres.serializers_referentiels import (
    CadenceRelanceEtapeSerializer,
)

User = get_user_model()

#: Samedi 5 septembre 2026 — non ouvré par défaut.
SAMEDI = datetime.date(2026, 9, 5)
#: Le lundi qui suit, où tout atterrissait jusqu'ici.
LUNDI = datetime.date(2026, 9, 7)

CONTRAT = (pathlib.Path(__file__).resolve().parent.parent / 'parametres'
           / 'contract_samples' / 'cadence_relance_v2.json')


def _quand(jour, heure, minute=0):
    return datetime.datetime.combine(
        jour, datetime.time(heure, minute), tzinfo=horaires.CASABLANCA)


class ContratPartageTests(SimpleTestCase):
    """PACT10 — la forme publiée est celle que le sérialiseur produit."""

    def setUp(self):
        self.contrat = json.loads(CONTRAT.read_text(encoding='utf-8'))

    def test_le_serialiseur_expose_exactement_les_cles_du_contrat(self):
        attendu = set(self.contrat['exemple'])
        self.assertEqual(
            set(CadenceRelanceEtapeSerializer().fields), attendu)

    def test_samedi_ok_figure_dans_le_contrat_et_ses_notes(self):
        self.assertIn('samedi_ok', self.contrat['exemple'])
        self.assertIn('samedi_ok', self.contrat['notes'])
        for ligne in self.contrat['exemple_liste']:
            self.assertIn('samedi_ok', ligne)


class DefautsDuProtocoleTests(SimpleTestCase):
    def test_aucun_gabarit_du_protocole_n_ouvre_le_samedi(self):
        """« Par défaut samedi_ok = False partout — rien ne change tant que
        personne ne coche. »"""
        for cadence, barreaux in CADENCES_DEFAUT.items():
            for barreau in barreaux:
                with self.subTest(cadence=cadence, ordre=barreau['ordre']):
                    self.assertFalse(barreau.get('samedi_ok', False))

    def test_le_champ_du_modele_est_faux_par_defaut(self):
        champ = CadenceRelanceEtape._meta.get_field('samedi_ok')
        self.assertIs(champ.default, False)


class _Base(TestCase):
    slug = 'cad43'

    def setUp(self):
        self.company = Company.objects.create(slug=self.slug, nom=self.slug)
        CompanyProfile.objects.create(company=self.company)
        self.acteur = User.objects.create_user(
            username=f'{self.slug}-resp', password='x',
            role_legacy='responsable', company=self.company)
        self.lead = Lead.objects.create(
            company=self.company, nom='Aziz', prenom='Benali',
            ville='Bouskoura', stage=stages.NEW, owner=self.acteur)

    def _barreau(self, **kw):
        kw.setdefault('cadence', 'contact')
        kw.setdefault('ordre', 1)
        kw.setdefault('delai_jours', 0)
        kw.setdefault('delai_minutes', 0)
        kw.setdefault('heure_cible', None)
        kw.setdefault('canal', CanalRelance.WHATSAPP)
        kw.setdefault('libelle', "Message d'identité")
        kw.setdefault('template_cle', 'identite')
        return CadenceRelanceEtape.objects.create(company=self.company, **kw)


class FenetreDuSamediTests(_Base):
    slug = 'cad43-fenetre'

    def test_sans_le_drapeau_le_samedi_reste_ferme(self):
        self.assertIsNone(horaires.fenetre_du_jour(SAMEDI, self.company))

    def test_avec_le_drapeau_le_samedi_ouvre_a_la_fenetre_du_canal(self):
        message = horaires.fenetre_du_jour(
            SAMEDI, self.company, samedi=True, canal='whatsapp')
        appel = horaires.fenetre_du_jour(
            SAMEDI, self.company, samedi=True, canal='appel')
        self.assertEqual(message[0], datetime.time(8, 30))
        self.assertEqual(appel[0], datetime.time(9, 0))
        self.assertEqual(message[1], datetime.time(20, 0))

    def test_le_drapeau_n_ouvre_pas_les_AUTRES_jours_fermes(self):
        dimanche = datetime.date(2026, 9, 6)
        self.assertIsNone(
            horaires.fenetre_du_jour(dimanche, self.company, samedi=True))

    def test_un_samedi_FERIE_reste_ferme(self):
        from apps.notifications.models import Holiday
        Holiday.objects.create(
            company=self.company, date=SAMEDI, nom='Aïd al-Fitr',
            recurrent_annuel=False)
        self.assertIsNone(
            horaires.fenetre_du_jour(SAMEDI, self.company, samedi=True))


class LeLeadDuVendrediSoirTests(_Base):
    slug = 'cad43-vendredi'

    def test_avec_samedi_ok_le_message_part_le_SAMEDI(self):
        """Le Done : le lead du samedi reçoit son message le samedi."""
        self._barreau(samedi_ok=True)
        echeances = calculer_echeances_cadence(
            self.lead, 'contact', _quand(SAMEDI, 7))
        self.assertEqual(len(echeances), 1)
        _gabarit, echeance = echeances[0]
        self.assertEqual(echeance.astimezone(horaires.CASABLANCA).date(),
                         SAMEDI)

    def _numero_mobile(self):
        # CAD34 — sans numéro joignable, le message naîtrait en appel.
        self.lead.telephone = '+212661234567'
        self.lead.save(update_fields=['telephone'])

    def _identite_et_appel(self, depart):
        self._numero_mobile()
        self._barreau(ordre=1, samedi_ok=True)
        self._barreau(ordre=2, delai_minutes=3, canal=CanalRelance.APPEL,
                      libelle="Appel d'ouverture",
                      template_cle='appel_ouverture', samedi_ok=False)
        return {g.ordre: e.astimezone(horaires.CASABLANCA)
                for g, e in calculer_echeances_cadence(self.lead, 'contact', depart)}

    def test_le_lead_du_week_end_part_au_balayage_du_samedi_10h_ou_du_dimanche_17h(self):
        """CADV30 (D-CADV-6). Mutant : ignorer ``samedi_ok`` ⇒ le dimanche repart au
        lundi."""
        lundi = datetime.date(2026, 11, 16)
        for depart, attendu in (
                (_quand(datetime.date(2026, 11, 14), 3), (datetime.date(2026, 11, 14), 10)),
                (_quand(datetime.date(2026, 11, 15), 11), (datetime.date(2026, 11, 15), 17)),
                # Vendredi soir, fenêtre fermée : le balayage du lendemain.
                (_quand(datetime.date(2026, 11, 13), 21), (datetime.date(2026, 11, 14), 10))):
            with self.subTest(depart=depart):
                CadenceRelanceEtape.objects.filter(company=self.company).delete()
                touches = self._identite_et_appel(depart)
                self.assertEqual((touches[1].date(), touches[1].hour, touches[1].minute),
                                 (*attendu, 0))
                self.assertEqual(touches[2].date(), lundi)

    def test_la_semaine_garde_l_identite_immediate(self):
        depart = _quand(datetime.date(2026, 11, 17), 11)  # mardi
        self.assertEqual(self._identite_et_appel(depart)[1], depart)

    def test_le_samedi_apres_10h_part_a_l_arrivee(self):
        depart = _quand(datetime.date(2026, 11, 14), 11, 20)
        self.assertEqual(self._identite_et_appel(depart)[1], depart)

    def test_le_dimanche_soir_attend_le_lundi(self):
        touches = self._identite_et_appel(_quand(datetime.date(2026, 11, 15), 21))
        self.assertEqual(touches[1].date(), datetime.date(2026, 11, 16))

    def test_la_touche_materialisee_garde_l_echeance_du_balayage(self):
        from apps.crm.cadence_plan import initialiser_plan_relance
        self._numero_mobile()
        self._barreau(ordre=1, samedi_ok=True)
        depart = _quand(datetime.date(2026, 11, 15), 11)
        with frozen(depart):
            [touche] = initialiser_plan_relance(self.lead, None, cadence='contact',
                                                depart=depart)
        touche.refresh_from_db()
        locale = touche.due_at.astimezone(horaires.CASABLANCA)
        self.assertEqual((locale.date(), locale.hour), (datetime.date(2026, 11, 15), 17))

    def test_sans_samedi_ok_le_message_attend_le_lundi(self):
        """Anti-faux-vert : c'est bien le drapeau qui ouvre la journée."""
        self._barreau(samedi_ok=False)
        echeances = calculer_echeances_cadence(
            self.lead, 'contact', _quand(SAMEDI, 7))
        _gabarit, echeance = echeances[0]
        self.assertEqual(echeance.astimezone(horaires.CASABLANCA).date(),
                         LUNDI)

    def test_le_samedi_ouvert_au_message_n_ouvre_AUCUN_appel(self):
        """Le cœur de la tâche : ouvrir le samedi sans ouvrir les 6 appels."""
        self._barreau(ordre=1, samedi_ok=True)
        self._barreau(ordre=2, delai_minutes=3, canal=CanalRelance.APPEL,
                      libelle="Appel d'ouverture",
                      template_cle='appel_ouverture', samedi_ok=False)
        echeances = calculer_echeances_cadence(
            self.lead, 'contact', _quand(SAMEDI, 7))
        jours = {g.ordre: e.astimezone(horaires.CASABLANCA).date()
                 for g, e in echeances}
        self.assertEqual(jours[1], SAMEDI)
        self.assertEqual(jours[2], LUNDI)


class BalayageWeekendTests(_Base):
    """CADV30 — les cas de fenêtre de ``horaires.prochain_balayage_weekend``."""
    slug = 'cad43-balayage'

    def _balayage(self, jour, heure):
        return horaires.prochain_balayage_weekend(_quand(jour, heure), self.company)

    def test_ramadan_l_ouverture_de_la_fenetre_du_mois(self):
        samedi = datetime.date(2026, 11, 14)
        with mock.patch('apps.crm.horaires.est_en_ramadan', return_value=True):
            arrivee = self._balayage(samedi, 3).astimezone(horaires.CASABLANCA)
        self.assertEqual(arrivee.date(), samedi)
        self.assertEqual(arrivee.time(), datetime.time(9, 0))

    def test_un_samedi_ferie_passe_au_dimanche(self):
        samedi = datetime.date(2026, 11, 14)
        with mock.patch('apps.crm.horaires._est_ferie',
                        side_effect=lambda d, _company: d == samedi):
            arrivee = self._balayage(samedi, 3).astimezone(horaires.CASABLANCA)
        self.assertEqual((arrivee.date(), arrivee.hour),
                         (datetime.date(2026, 11, 15), 17))

    def test_le_vendredi_dans_sa_fenetre_et_la_semaine_ne_balaient_rien(self):
        self.assertIsNone(self._balayage(datetime.date(2026, 11, 13), 11))
        self.assertIsNone(self._balayage(datetime.date(2026, 11, 17), 3))

    def test_une_societe_ouverte_le_samedi_garde_son_ouverture(self):
        with mock.patch('apps.crm.horaires._jour_ouvre', return_value=True):
            self.assertIsNone(self._balayage(datetime.date(2026, 11, 14), 3))


class ApiEtIsolationTests(_Base):
    slug = 'cad43-api'

    def test_le_serialiseur_rend_le_champ_sur_une_vraie_ligne(self):
        barreau = self._barreau(samedi_ok=True)
        donnees = CadenceRelanceEtapeSerializer(barreau).data
        self.assertIs(donnees['samedi_ok'], True)

    def test_le_champ_est_MODIFIABLE_par_l_api(self):
        barreau = self._barreau(samedi_ok=False)
        serialiseur = CadenceRelanceEtapeSerializer(
            barreau, data={'samedi_ok': True}, partial=True)
        self.assertTrue(serialiseur.is_valid(), serialiseur.errors)
        serialiseur.save()
        barreau.refresh_from_db()
        self.assertTrue(barreau.samedi_ok)

    def test_aucune_touche_materialisee_n_est_touchee_par_ce_champ(self):
        """`RelanceEtape` (la COPIE par lead) n'apprend pas un champ de
        gabarit : le drapeau agit au moment du calcul, pas après."""
        self.assertNotIn(
            'samedi_ok',
            {champ.name for champ in RelanceEtape._meta.get_fields()})
