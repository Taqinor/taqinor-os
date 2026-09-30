"""COCKPIT-CONTRÔLE B5 — le bloc « Contrôle du suivi » (``controle_suivi.py``).

Ordre fondateur du 30/09/2026 : « make reading the data [easy] and [see] if the
commercial did everything as she should ». Contrat PACT10 posé seul et en
premier : ``contract_samples/controle_suivi.json`` — ses ``pourquoi`` et
``notes`` sont les règles de mesure que ces tests épinglent :

  * la FORME est celle du contrat, à tous les niveaux (``exemple``), et une
    société vide rend EXACTEMENT ``exemple_vide`` ;
  * chaque niveau de verdict (alerte / attention / ok / vide) se lit sur
    l'état ACTUEL (les exceptions), jamais sur le seul pourcentage ;
  * chaque état de case (vert / orange / rouge / en_cours / vide), une case
    par jour calendaire, ``ouvre`` selon le calendrier de la société ;
  * chaque liste d'exceptions (en retard, tâches en attente — un report ne
    les en sort pas —, reports, sans prochaine étape — un lead jamais placé
    n'y est pas —, premier contact hors délai), triées, plafonnées à 10 ;
  * les absences déclarées excusent ; les annulations du moteur sortent du
    dénominateur ; la période précédente se mesure pareil ;
  * le détail par type suit l'ordre de la table ; la médiane (jamais la
    moyenne) ; trois résultats lus par les sélecteurs de visites et ventes ;
  * la portée de visibilité et ``owner`` bornent tout ; ``jours`` hors
    7/14/30 et ``owner`` inconnu ou hors portée → 400 ``erreurs``.

Horloge FIXE : mercredi 30/09/2026, 10 h à Casablanca (``frozen``, jamais
tick/move_to). Période par défaut : du jeudi 17/09 au mercredi 30/09.
"""
import datetime
import itertools
import json
from decimal import Decimal
from pathlib import Path

from django.contrib.auth import get_user_model
from django.test import SimpleTestCase, TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from authentication.models import Company
from testkit.time import frozen

from apps.crm import cadence_absence
from apps.crm import controle_suivi as cs
from apps.crm import horaires, services, stages
from apps.crm import suite_touche as st
from apps.crm.cadence_config import CLE_DEVIS
from apps.crm.models import Client, Lead, PeriodeAbsence, RelanceEtape
from apps.parametres.models import CompanyProfile
from apps.roles.models import Role
from apps.ventes.models import Devis
from apps.visites.models import VisiteTerrain

User = get_user_model()

CASA = horaires.CASABLANCA
GEL = datetime.datetime(2026, 9, 30, 10, 0, tzinfo=CASA)
AUJOURDHUI = GEL.date()
URL = '/api/django/crm/relance-etapes/controle/'
A_FAIRE = RelanceEtape.Statut.A_FAIRE
FAIT = RelanceEtape.Statut.FAIT
SAUTEE = RelanceEtape.Statut.SAUTEE
ANNULEE = RelanceEtape.Statut.ANNULEE

RACINE = Path(__file__).resolve().parents[4]
CONTRAT = json.loads(
    (Path(__file__).resolve().parent / 'contract_samples'
     / 'controle_suivi.json').read_text(encoding='utf-8'))
TABLE = json.loads(
    (RACINE / 'frontend' / 'src' / 'features' / 'crm' / 'relances'
     / 'parcours_suivi.json').read_text(encoding='utf-8'))

_seq = itertools.count(1)


def _jour(decalage):
    """Le jour ``decalage`` jours après le jour gelé (négatif = passé)."""
    return AUJOURDHUI + datetime.timedelta(days=decalage)


def _a(jour, heure=10, minute=0):
    return datetime.datetime.combine(jour, datetime.time(heure, minute),
                                     tzinfo=CASA)


class TableEtParametresTests(SimpleTestCase):
    """Sans base : l'ordre de la table, les refus de ``jours``, les états."""

    def test_l_ordre_des_types_est_celui_de_la_table(self):
        self.assertEqual(list(st.TYPES_ORDONNES),
                         [etape['id'] for etape in TABLE['etapes']])

    def test_jours_par_defaut_et_autorises(self):
        self.assertEqual(cs.parametres_controle(None, None), (14, None, {}))
        for jours in (7, 14, 30):
            self.assertEqual(
                cs.parametres_controle(None, None, str(jours)),
                (jours, None, {}))

    def test_jours_hors_periode_refuse_en_nommant_le_champ(self):
        for brut in ('15', '0', 'abc', '-7', '14.0'):
            with self.subTest(jours=brut):
                _jours, _owner, erreurs = cs.parametres_controle(
                    None, None, brut)
                self.assertEqual(erreurs, {'jours': cs.MESSAGE_JOURS})

    def test_les_etats_d_une_case(self):
        def case(**valeurs):
            base = {'du': 0, cs.A_TEMPS: 0, cs.EN_RETARD: 0, cs.SAUTEES: 0,
                    cs.OUVERT: 0}
            base.update(valeurs)
            return base

        self.assertEqual(cs._etat_du_jour(case(), False), cs.ETAT_VIDE)
        self.assertEqual(cs._etat_du_jour(case(du=2, a_temps=2), False),
                         cs.ETAT_VERT)
        self.assertEqual(
            cs._etat_du_jour(case(du=2, a_temps=1, en_retard=1), False),
            cs.ETAT_ORANGE)
        self.assertEqual(
            cs._etat_du_jour(case(du=2, a_temps=1, sautees=1), False),
            cs.ETAT_ORANGE)
        self.assertEqual(
            cs._etat_du_jour(case(du=2, a_temps=1, ouvert=1), False),
            cs.ETAT_ROUGE)
        self.assertEqual(
            cs._etat_du_jour(case(du=2, a_temps=1, ouvert=1), True),
            cs.ETAT_EN_COURS)
        self.assertEqual(cs._etat_du_jour(case(du=1, a_temps=1), True),
                         cs.ETAT_VERT)


class MesurePureTests(SimpleTestCase):
    """Sans base : juger une étape, compter la frise, le verdict et le détail
    par type sont des calculs PURS sur des étapes déjà lues."""

    def _etape(self, jour, statut=A_FAIRE, fait=None, outcome='',
               cadence='contact', cle='', libelle='Appel', lead_id=1):
        return RelanceEtape(
            lead_id=lead_id, cadence=cadence, canal='appel', cle=cle,
            libelle=libelle, statut=statut, due_date=jour, due_at=_a(jour),
            traite_le=_a(fait, 11) if fait else None, outcome=outcome)

    def test_verdict_cases_et_detail_par_type(self):
        etapes = [
            self._etape(_jour(-9), FAIT, fait=_jour(-9), outcome='non_joint'),
            self._etape(_jour(-8), FAIT, fait=_jour(-7)),
            self._etape(_jour(-7), SAUTEE, fait=_jour(-7)),
            self._etape(_jour(-1)),
            self._etape(_jour(0)),
            self._etape(_jour(-4), FAIT, fait=_jour(-4), cadence='generique',
                        cle=CLE_DEVIS),
        ]
        cases, verdict, par_type = cs._mesure_de_la_periode(
            etapes, AUJOURDHUI, cadence_absence.CouvertureAbsences(), {1: 7})
        self.assertEqual(verdict, {'du': 5, 'a_temps': 2, 'en_retard': 1,
                                   'sautees': 1, 'ouvert': 1})
        self.assertEqual(cases[_jour(0)], {'du': 1, 'a_temps': 0,
                                           'en_retard': 0, 'sautees': 0,
                                           'ouvert': 1})
        self.assertEqual(cs._etat_du_jour(cases[_jour(0)], True),
                         cs.ETAT_EN_COURS)
        self.assertEqual(cs._etat_du_jour(cases[_jour(-1)], False),
                         cs.ETAT_ROUGE)
        lignes = cs._lignes_par_type(par_type)
        self.assertEqual([ligne['type_etape'] for ligne in lignes],
                         [st.TYPE_CONTACT_APPEL, st.TYPE_DEVIS])
        contact, devis = lignes
        self.assertEqual(
            (contact['du'], contact['a_temps'], contact['en_retard'],
             contact['sautees'], contact['ouvert']), (4, 1, 1, 1, 1))
        self.assertEqual(contact['reponses'],
                         [{'cle': 'non_joint', 'n': 1},
                          {'cle': 'sans_issue', 'n': 1}])
        self.assertIs(devis['est_tache'], True)
        self.assertEqual(devis['reponses'], [{'cle': 'sans_issue', 'n': 1}])

    def test_une_absence_du_responsable_excuse_un_retard(self):
        absences = cadence_absence.CouvertureAbsences([PeriodeAbsence(
            utilisateur_id=7, date_debut=_jour(-6), date_fin=_jour(-5))])
        etape = self._etape(_jour(-6), FAIT, fait=_jour(-4))
        self.assertEqual(cs._juger(etape, absences, {1: 7}), cs.A_TEMPS)
        self.assertEqual(cs._juger(etape, absences, {1: 8}), cs.EN_RETARD)

    def test_la_periode_precedente(self):
        etapes = [self._etape(_jour(-15), FAIT, fait=_jour(-15)),
                  self._etape(_jour(-16), FAIT, fait=_jour(-14)),
                  self._etape(_jour(-20))]
        self.assertEqual(
            cs._a_temps_pct(etapes, cadence_absence.CouvertureAbsences(),
                            {1: 7}), 33.3)
        self.assertIsNone(cs._a_temps_pct(
            [], cadence_absence.CouvertureAbsences(), {}))

    def test_une_liste_filtree_sur_owner_et_plafonnee(self):
        lignes = [(7, {'n': rang}) for rang in range(12)] + [(8, {'n': 99})]
        tout = cs._liste(lignes, None)
        self.assertEqual(tout['total'], 13)
        self.assertEqual(len(tout['lignes']), cs.LIGNES_MAX)
        self.assertEqual(cs._liste(lignes, 8),
                         {'total': 1, 'lignes': [{'n': 99}]})


class _Base(TestCase):

    def setUp(self):
        gel = frozen(GEL)
        gel.start()
        self.addCleanup(gel.stop)
        n = next(_seq)
        self.n = n
        self.company = Company.objects.create(
            nom=f'Cockpit controle {n}', slug=f'cockpit-controle-{n}')
        self.profil, _ = CompanyProfile.objects.get_or_create(
            company=self.company)
        self.acteur = User.objects.create_user(
            username=f'ctl-{n}-commerciale', password='x',
            role_legacy='responsable', company=self.company)
        self.api = APIClient()
        self.api.credentials(
            HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(self.acteur)}')
        self._k = itertools.count(1)

    # ── fabriques ──

    def _utilisateur(self, nom, **champs):
        return User.objects.create_user(
            username=f'ctl-{self.n}-{nom}', password='x',
            company=self.company, **champs)

    def _lead(self, *, owner=None, stage=stages.CONTACTED, cree_le=None,
              **champs):
        k = next(self._k)
        lead = Lead.objects.create(
            company=self.company, nom=f'Prospect {self.n}-{k}', stage=stage,
            owner=owner or self.acteur,
            telephone=f'+212662{self.n:03d}{k:03d}', **champs)
        if cree_le is not None:
            Lead.objects.filter(pk=lead.pk).update(date_creation=cree_le)
            lead.refresh_from_db()
        return lead

    def _etape(self, lead, jour, *, heure=10, statut=A_FAIRE, fait_le=None,
               outcome='', cadence='contact', canal='appel', cle='',
               libelle='Appel de suivi', cree_le=None, nb_reports=0):
        etape = RelanceEtape.objects.create(
            company=self.company, lead=lead, cadence=cadence, ordre=2,
            canal=canal, cle=cle, libelle=libelle, due_at=_a(jour, heure),
            due_date=jour, statut=statut, traite_le=fait_le,
            traite_par=(self.acteur if statut in (FAIT, SAUTEE) else None),
            outcome=outcome, nb_reports=nb_reports)
        if cree_le is not None:
            RelanceEtape.objects.filter(pk=etape.pk).update(
                created_at=cree_le)
            etape.refresh_from_db()
        return etape

    def _fait(self, lead, jour, *, le=None, heure=11, **champs):
        """Une étape due ``jour``, close « fait » le jour ``le`` (défaut :
        le jour même — donc à temps)."""
        return self._etape(lead, jour, statut=FAIT,
                           fait_le=_a(le or jour, heure), **champs)

    def _devis(self, lead, jour, **champs):
        return self._etape(lead, jour, cadence='generique', cle=CLE_DEVIS,
                           libelle='Préparer et envoyer le devis', **champs)

    def _suivi(self, lead):
        """Une étape OUVERTE à venir : le dossier reste suivi (jamais « sans
        prochaine étape »), rien n'est dû ni en retard."""
        return self._etape(lead, _jour(5))

    def _controle(self, **kw):
        return cs.controle_suivi(self.company, self.acteur, **kw)


# ═══════════════════════════════════════════════════════════════════════════
# 1. La forme — le contrat, à tous les niveaux
# ═══════════════════════════════════════════════════════════════════════════

class FormeTests(_Base):

    def _cles(self, obtenu, attendu, chemin='controle'):
        if isinstance(attendu, dict):
            self.assertIsInstance(obtenu, dict, chemin)
            self.assertEqual(set(obtenu), set(attendu), chemin)
            for cle, valeur in attendu.items():
                self._cles(obtenu[cle], valeur, f'{chemin}.{cle}')
        elif isinstance(attendu, list):
            self.assertIsInstance(obtenu, list, chemin)
            if attendu:
                self.assertTrue(obtenu, f'{chemin} : le scénario doit '
                                        'peupler cette liste')
                for element in obtenu:
                    self._cles(element, attendu[0], f'{chemin}[]')
        elif attendu is not None and obtenu is not None:
            if isinstance(attendu, bool):
                self.assertIsInstance(obtenu, bool, chemin)
            elif isinstance(attendu, (int, float)):
                self.assertIsInstance(obtenu, (int, float), chemin)
                self.assertNotIsInstance(obtenu, bool, chemin)
            else:
                self.assertIsInstance(obtenu, str, chemin)

    def _scenario(self):
        lead = self._lead()
        self._fait(lead, _jour(-9), outcome='non_joint')
        self._etape(lead, _jour(-2))                          # en retard
        self._devis(lead, _jour(2), cree_le=_a(_jour(-4)))    # en attente
        self._etape(lead, _jour(1), nb_reports=2)             # reportée
        sorti = self._lead()
        self._fait(sorti, _jour(-8))                          # sans suite
        self._lead(stage=stages.NEW, cree_le=_a(_jour(-6)))   # hors délai

    def test_la_forme_est_celle_du_contrat(self):
        self._scenario()
        self._cles(self._controle(), CONTRAT['exemple'])

    def test_la_forme_est_celle_de_l_exemple_alerte(self):
        """``exemple_alerte`` fixe AUSSI la ligne d'un dossier sans prochaine
        étape (``stage``, ``derniere_etape_le``, ``depuis_jours``)."""
        self._scenario()
        controle = self._controle()
        self.assertEqual(controle['verdict']['niveau'], cs.NIVEAU_ALERTE)
        self._cles(controle, CONTRAT['exemple_alerte'])

    def test_une_societe_vide_rend_exactement_l_exemple_vide(self):
        self.assertEqual(self._controle(), CONTRAT['exemple_vide'])

    def test_l_action_sert_la_forme_du_contrat(self):
        self._scenario()
        resp = self.api.get(URL)
        self.assertEqual(resp.status_code, 200, resp.data)
        self._cles(resp.data, CONTRAT['exemple'])

    def test_l_action_est_ouverte_a_tout_role(self):
        simple = self._utilisateur('simple', role_legacy='normal')
        api = APIClient()
        api.credentials(
            HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(simple)}')
        self.assertEqual(api.get(URL).status_code, 200)


# ═══════════════════════════════════════════════════════════════════════════
# 2. Le verdict — chaque niveau, lu sur l'état actuel
# ═══════════════════════════════════════════════════════════════════════════

class VerdictNiveauTests(_Base):

    def test_ok_quand_tout_est_fait_a_temps(self):
        lead = self._lead()
        self._suivi(lead)
        self._fait(lead, _jour(-9))
        self._fait(lead, _jour(-8))
        self._fait(lead, _jour(-1))
        verdict = self._controle()['verdict']
        self.assertEqual(verdict['niveau'], cs.NIVEAU_OK)
        self.assertEqual((verdict['du'], verdict['a_temps']), (3, 3))
        self.assertEqual(verdict['a_temps_pct'], 100.0)

    def test_attention_une_etape_en_retard_d_un_jour(self):
        lead = self._lead()
        self._etape(lead, _jour(-1))
        controle = self._controle()
        self.assertEqual(controle['verdict']['niveau'], cs.NIVEAU_ATTENTION)
        [ligne] = controle['exceptions']['en_retard']['lignes']
        self.assertEqual(ligne['jours_de_retard'], 1)

    def test_alerte_un_retard_de_deux_jours(self):
        self._etape(self._lead(), _jour(-2))
        self.assertEqual(self._controle()['verdict']['niveau'],
                         cs.NIVEAU_ALERTE)

    def test_attention_une_tache_en_attente(self):
        lead = self._lead()
        self._devis(lead, _jour(2), cree_le=_a(_jour(-2)))
        self.assertEqual(self._controle()['verdict']['niveau'],
                         cs.NIVEAU_ATTENTION)

    def test_attention_une_etape_reportee_deux_fois(self):
        self._etape(self._lead(), _jour(3), nb_reports=2)
        self.assertEqual(self._controle()['verdict']['niveau'],
                         cs.NIVEAU_ATTENTION)

    def test_un_seul_report_ne_leve_rien(self):
        lead = self._lead()
        self._fait(lead, _jour(-3))
        self._etape(lead, _jour(3), nb_reports=1)
        self.assertEqual(self._controle()['verdict']['niveau'],
                         cs.NIVEAU_OK)

    def test_alerte_un_dossier_sorti_du_suivi(self):
        self._fait(self._lead(), _jour(-3))
        self.assertEqual(self._controle()['verdict']['niveau'],
                         cs.NIVEAU_ALERTE)

    def test_alerte_un_premier_contact_hors_delai(self):
        self._lead(stage=stages.NEW, cree_le=_a(_jour(-6)))
        self.assertEqual(self._controle()['verdict']['niveau'],
                         cs.NIVEAU_ALERTE)

    def test_vide_sans_rien_de_du_ni_d_exception(self):
        self._suivi(self._lead())
        controle = self._controle()
        self.assertEqual(controle['verdict']['niveau'], cs.NIVEAU_VIDE)
        self.assertIsNone(controle['verdict']['a_temps_pct'])
        self.assertEqual(controle['jours'], [])

    def test_le_niveau_ne_se_lit_pas_sur_le_seul_pourcentage(self):
        """100 % à l'heure sur la période, mais un dossier en retard MAINTENANT
        (dû avant la période) : l'état actuel l'emporte."""
        lead = self._lead()
        self._fait(lead, _jour(-2))
        self._etape(lead, _jour(-20))
        verdict = self._controle()['verdict']
        self.assertEqual(verdict['a_temps_pct'], 100.0)
        self.assertEqual(verdict['niveau'], cs.NIVEAU_ALERTE)


# ═══════════════════════════════════════════════════════════════════════════
# 3. Les compteurs du verdict et la période précédente
# ═══════════════════════════════════════════════════════════════════════════

class VerdictCompteursTests(_Base):

    def test_juge_au_jour_de_l_echeance_courante(self):
        lead = self._lead()
        self._fait(lead, _jour(-9))                       # à temps
        self._fait(lead, _jour(-8), le=_jour(-7))         # en retard
        self._etape(lead, _jour(-7), statut=SAUTEE,
                    fait_le=_a(_jour(-7)))                # sautée
        self._etape(lead, _jour(-1))                      # ouvert (passé)
        self._etape(lead, _jour(0), heure=15)             # du jour : en cours
        self._etape(lead, _jour(-6), statut=ANNULEE,
                    fait_le=_a(_jour(-6)))                # moteur : hors compte
        verdict = self._controle()['verdict']
        self.assertEqual(
            {cle: verdict[cle] for cle in ('du', 'a_temps', 'en_retard',
                                           'sautees', 'ouvert')},
            {'du': 4, 'a_temps': 1, 'en_retard': 1, 'sautees': 1,
             'ouvert': 1})
        self.assertEqual(verdict['a_temps_pct'], 25.0)

    def test_une_etape_du_jour_deja_faite_compte(self):
        lead = self._lead()
        self._suivi(lead)
        self._fait(lead, _jour(0), heure=9)
        verdict = self._controle()['verdict']
        self.assertEqual((verdict['du'], verdict['a_temps']), (1, 1))

    def test_la_periode_precedente_se_mesure_pareil(self):
        lead = self._lead()
        self._suivi(lead)
        self._fait(lead, _jour(-15))                      # période d'avant
        self._fait(lead, _jour(-16), le=_jour(-14))       # période d'avant
        self._fait(lead, _jour(-2))                       # période courante
        verdict = self._controle()['verdict']
        self.assertEqual(verdict['precedent_a_temps_pct'], 50.0)
        self.assertEqual(verdict['a_temps_pct'], 100.0)

    def test_sans_periode_precedente_le_pourcentage_est_null(self):
        lead = self._lead()
        self._suivi(lead)
        self._fait(lead, _jour(-2))
        self.assertIsNone(
            self._controle()['verdict']['precedent_a_temps_pct'])

    def test_une_absence_declaree_excuse(self):
        lead = self._lead()
        self._suivi(lead)
        PeriodeAbsence.objects.create(
            company=self.company, utilisateur=self.acteur,
            date_debut=_jour(-6), date_fin=_jour(-5))
        self._fait(lead, _jour(-6), le=_jour(-4))         # excusée
        self._etape(lead, _jour(-5))                      # ouverte, excusée
        controle = self._controle()
        self.assertEqual(controle['verdict']['a_temps'], 1)
        self.assertEqual(controle['verdict']['en_retard'], 0)
        self.assertEqual(controle['exceptions']['en_retard']['total'], 0)

    def test_l_absence_d_un_autre_n_excuse_personne(self):
        collegue = self._utilisateur('collegue', role_legacy='responsable')
        lead = self._lead()
        self._suivi(lead)
        PeriodeAbsence.objects.create(
            company=self.company, utilisateur=collegue,
            date_debut=_jour(-6), date_fin=_jour(-5))
        self._fait(lead, _jour(-6), le=_jour(-4))
        self.assertEqual(self._controle()['verdict']['en_retard'], 1)


# ═══════════════════════════════════════════════════════════════════════════
# 4. La frise — une case par jour, chaque état
# ═══════════════════════════════════════════════════════════════════════════

class FriseTests(_Base):

    def setUp(self):
        super().setUp()
        lead = self._lead()
        self._suivi(lead)
        self._fait(lead, _jour(-9))                        # 21/09 vert
        self._fait(lead, _jour(-9), heure=15)
        self._fait(lead, _jour(-8), le=_jour(-7))          # 22/09 orange
        self._etape(lead, _jour(-7), statut=SAUTEE,
                    fait_le=_a(_jour(-7)))                 # 23/09 orange
        self._etape(lead, _jour(-1))                       # 29/09 rouge
        self._etape(lead, _jour(0), heure=15)              # 30/09 en cours
        self._etape(lead, _jour(-6), statut=ANNULEE,
                    fait_le=_a(_jour(-6)))                 # 24/09 vide
        self.frise = {case['date']: case for case in self._controle()['jours']}

    def test_une_case_par_jour_du_plus_ancien_a_aujourdhui(self):
        dates = list(self.frise)
        self.assertEqual(len(dates), 14)
        self.assertEqual(dates[0], _jour(-13).isoformat())
        self.assertEqual(dates[-1], AUJOURDHUI.isoformat())
        self.assertEqual(
            [d for d, case in self.frise.items() if case['aujourdhui']],
            [AUJOURDHUI.isoformat()])

    def test_chaque_etat(self):
        attendus = {
            _jour(-9): cs.ETAT_VERT,
            _jour(-8): cs.ETAT_ORANGE,
            _jour(-7): cs.ETAT_ORANGE,
            _jour(-6): cs.ETAT_VIDE,
            _jour(-1): cs.ETAT_ROUGE,
            _jour(0): cs.ETAT_EN_COURS,
        }
        for jour, etat in attendus.items():
            with self.subTest(jour=jour):
                self.assertEqual(self.frise[jour.isoformat()]['etat'], etat)

    def test_la_case_du_jour_compte_ce_qui_reste_ouvert(self):
        case = self.frise[AUJOURDHUI.isoformat()]
        self.assertEqual((case['du'], case['ouvert']), (1, 1))

    def test_les_jours_non_ouvres_de_la_societe(self):
        samedi, dimanche = _jour(-11), _jour(-10)          # 19 et 20/09
        self.assertEqual(samedi.weekday(), 5)
        self.assertFalse(self.frise[samedi.isoformat()]['ouvre'])
        self.assertFalse(self.frise[dimanche.isoformat()]['ouvre'])
        self.assertEqual(self.frise[dimanche.isoformat()]['etat'],
                         cs.ETAT_VIDE)
        self.assertTrue(self.frise[_jour(-9).isoformat()]['ouvre'])

    def test_la_periode_suit_jours(self):
        for jours in (7, 30):
            with self.subTest(jours=jours):
                frise = self._controle(jours=jours)['jours']
                self.assertEqual(len(frise), jours)
                self.assertEqual(frise[0]['date'],
                                 _jour(-(jours - 1)).isoformat())


# ═══════════════════════════════════════════════════════════════════════════
# 5. Les exceptions de l'instant
# ═══════════════════════════════════════════════════════════════════════════

class ExceptionsTests(_Base):

    def test_en_retard_touches_et_taches_la_plus_ancienne_d_abord(self):
        lead = self._lead()
        touche = self._etape(lead, _jour(-2))
        tache = self._devis(lead, _jour(-5))
        lignes = self._controle()['exceptions']['en_retard']['lignes']
        self.assertEqual([ligne['etape'] for ligne in lignes],
                         [tache.pk, touche.pk])
        self.assertEqual(lignes[0]['type_etape'], st.TYPE_DEVIS)
        self.assertIs(lignes[0]['est_tache'], True)
        self.assertEqual(lignes[0]['jours_de_retard'], 5)
        self.assertEqual(lignes[0]['lead'], lead.pk)
        self.assertEqual(lignes[0]['owner_nom'], self.acteur.username)
        self.assertEqual(lignes[0]['due_date'], _jour(-5).isoformat())

    def test_dix_lignes_au_plus_et_le_vrai_total(self):
        lead = self._lead()
        for decalage in range(1, 13):
            self._etape(lead, _jour(-decalage))
        liste = self._controle()['exceptions']['en_retard']
        self.assertEqual(liste['total'], 12)
        self.assertEqual(len(liste['lignes']), cs.LIGNES_MAX)
        self.assertEqual(liste['lignes'][0]['jours_de_retard'], 12)

    def test_une_tache_en_attente_depuis_deux_jours(self):
        lead = self._lead()
        vieille = self._devis(lead, _jour(3), cree_le=_a(_jour(-3), 9))
        self._devis(lead, _jour(3), cree_le=_a(_jour(-1), 9))   # trop jeune
        self._etape(lead, _jour(3), cree_le=_a(_jour(-6)))      # une touche
        liste = self._controle()['exceptions']['taches_en_attente']
        self.assertEqual(liste['total'], 1)
        [ligne] = liste['lignes']
        self.assertEqual(ligne['etape'], vieille.pk)
        self.assertEqual(ligne['ouverte_depuis_jours'], 3)
        self.assertIs(ligne['est_tache'], True)

    def test_un_report_ne_sort_pas_une_tache_de_en_attente(self):
        lead = self._lead()
        tache = self._devis(lead, _jour(1), cree_le=_a(_jour(-4)))
        services.reporter_prochaine_touche(
            lead, self.acteur, _a(_jour(7), 11), etape=tache)
        tache.refresh_from_db()
        self.assertEqual(tache.nb_reports, 1)
        [ligne] = self._controle()['exceptions']['taches_en_attente'][
            'lignes']
        self.assertEqual(ligne['etape'], tache.pk)
        self.assertEqual(ligne['due_date'], tache.due_date.isoformat())
        self.assertEqual(ligne['ouverte_depuis_jours'], 4)

    def test_les_reports_d_une_etape_ouverte(self):
        lead = self._lead()
        etape = self._etape(lead, _jour(1))
        origine = etape.due_initial_at
        for jours in (3, 6):
            services.reporter_prochaine_touche(
                lead, self.acteur, _a(_jour(jours), 11), etape=etape)
        close = self._fait(lead, _jour(-2), nb_reports=3)
        liste = self._controle()['exceptions']['reports']
        self.assertEqual(liste['total'], 1)
        [ligne] = liste['lignes']
        self.assertEqual(ligne['etape'], etape.pk)
        self.assertNotEqual(ligne['etape'], close.pk)
        self.assertEqual(ligne['nb_reports'], 2)
        self.assertEqual(ligne['due_initial'],
                         origine.astimezone(CASA).date().isoformat())
        self.assertNotEqual(ligne['due_date'], ligne['due_initial'])

    def test_sans_prochaine_etape(self):
        sorti = self._lead()
        self._fait(sorti, _jour(-3), heure=16)
        plus_ancien = self._lead()
        self._fait(plus_ancien, _jour(-8))
        self._lead()                                   # jamais placé
        suivi = self._lead()
        self._fait(suivi, _jour(-3))
        self._suivi(suivi)
        for champs in ({'perdu': True, 'motif_perte': 'Prix'},
                       {'ne_plus_contacter': True},
                       {'stage': stages.SIGNED}, {'stage': stages.COLD},
                       {'is_archived': True}):
            clos = self._lead(**champs)
            self._fait(clos, _jour(-3))
        liste = self._controle()['exceptions']['sans_prochaine_etape']
        self.assertEqual(liste['total'], 2)
        # Tri par `depuis_jours` décroissant : le plus ancien d'abord.
        self.assertEqual([ligne['lead'] for ligne in liste['lignes']],
                         [plus_ancien.pk, sorti.pk])
        ligne = liste['lignes'][1]
        self.assertEqual(ligne['owner_nom'], self.acteur.username)
        self.assertEqual(ligne['stage'], stages.CONTACTED)
        self.assertEqual(ligne['derniere_etape_le'], _jour(-3).isoformat())
        self.assertEqual(ligne['depuis_jours'], 3)
        self.assertEqual(liste['lignes'][0]['depuis_jours'], 8)

    def test_un_lead_jamais_place_n_est_pas_sans_prochaine_etape(self):
        self._lead()
        self._lead(stage=stages.NEW)
        self.assertEqual(
            self._controle()['exceptions']['sans_prochaine_etape'],
            {'total': 0, 'lignes': []})

    def test_premier_contact_hors_delai(self):
        attend = self._lead(stage=stages.NEW, cree_le=_a(_jour(-6)))
        self._lead(stage=stages.NEW, cree_le=_a(_jour(-1), 18))  # dans le délai
        self._lead(stage=stages.NEW, cree_le=_a(_jour(-6)),
                   first_contacted_at=_a(_jour(-6), 11))         # contacté
        self._lead(stage=stages.NEW, cree_le=_a(_jour(-6)), perdu=True,
                   motif_perte='Prix')
        self._lead(stage=stages.NEW, cree_le=_a(_jour(-6)),
                   source=Lead.Source.ODOO_IMPORT_TEST)
        liste = self._controle()['exceptions']['premier_contact_hors_delai']
        self.assertEqual(liste['total'], 1)
        [ligne] = liste['lignes']
        self.assertEqual(ligne['lead'], attend.pk)
        minutes = horaires.minutes_ouvrees_entre(
            attend.date_creation, GEL, self.company)
        self.assertGreaterEqual(minutes, 24 * 60)
        self.assertEqual(ligne['attend_depuis_heures'],
                         round(minutes / 60.0, 1))
        self.assertTrue(ligne['cree_le'].startswith(
            _jour(-6).isoformat()))

    def test_un_delai_desactive_ne_signale_personne(self):
        self.profil.lead_sla_hours = 0
        self.profil.save(update_fields=['lead_sla_hours'])
        self._lead(stage=stages.NEW, cree_le=_a(_jour(-6)))
        controle = self._controle()
        self.assertEqual(
            controle['exceptions']['premier_contact_hors_delai'],
            {'total': 0, 'lignes': []})
        self.assertEqual(controle['seuils']['premier_contact_heures'], 0)
        self.assertEqual(controle['premier_contact']['delai_heures'], 0)


# ═══════════════════════════════════════════════════════════════════════════
# 6. Le détail par type, le premier contact, les résultats
# ═══════════════════════════════════════════════════════════════════════════

class ParTypeTests(_Base):

    def test_l_ordre_de_la_table_et_les_reponses(self):
        lead = self._lead()
        self._suivi(lead)
        self._fait(lead, _jour(-5), cadence='apres_devis')
        self._devis(lead, _jour(-4), statut=FAIT, fait_le=_a(_jour(-4)))
        self._fait(lead, _jour(-3), outcome='non_joint')
        self._fait(lead, _jour(-2), outcome='non_joint')
        self._fait(lead, _jour(-1), outcome='joint', le=_jour(0), heure=9)
        self._etape(lead, _jour(0), heure=16)            # en cours : absent
        lignes = self._controle()['par_type']
        self.assertEqual([ligne['type_etape'] for ligne in lignes],
                         [st.TYPE_CONTACT_APPEL, st.TYPE_DEVIS,
                          st.TYPE_SUIVI_APPEL])
        contact = lignes[0]
        self.assertIs(contact['est_tache'], False)
        self.assertEqual(
            (contact['du'], contact['a_temps'], contact['en_retard']),
            (3, 2, 1))
        self.assertEqual(contact['reponses'],
                         [{'cle': 'non_joint', 'n': 2},
                          {'cle': 'joint', 'n': 1}])
        devis = lignes[1]
        self.assertIs(devis['est_tache'], True)
        self.assertEqual(devis['reponses'], [{'cle': 'sans_issue', 'n': 1}])


class PremierContactTests(_Base):

    def test_la_mediane_jamais_la_moyenne(self):
        cree = _a(_jour(-1), 10)                          # mardi 29/09
        for minutes in (10, 20, 300):
            self._lead(cree_le=cree, first_contacted_at=cree
                       + datetime.timedelta(minutes=minutes))
        self._lead(cree_le=_a(_jour(-20)),                # hors période
                   first_contacted_at=_a(_jour(-20), 11))
        self._lead(cree_le=cree, source=Lead.Source.ODOO_IMPORT_TEST,
                   first_contacted_at=cree + datetime.timedelta(minutes=5))
        bloc = self._controle()['premier_contact']
        self.assertEqual(bloc['nouveaux'], 3)
        self.assertEqual(bloc['mediane_minutes'], 20)
        self.assertEqual(bloc['dans_le_delai'], 3)
        self.assertEqual(bloc['delai_heures'], 24)
        self.assertIsNone(bloc['plus_longue_attente_heures'])

    def test_hors_delai_et_plus_longue_attente(self):
        cree = _a(_jour(-6), 10)                          # jeudi 24/09
        self._lead(cree_le=cree, first_contacted_at=_a(_jour(-1), 10))
        attend = self._lead(stage=stages.NEW, cree_le=_a(_jour(-2), 10))
        bloc = self._controle()['premier_contact']
        self.assertEqual(bloc['nouveaux'], 2)
        self.assertEqual(bloc['dans_le_delai'], 0)
        minutes = horaires.minutes_ouvrees_entre(
            attend.date_creation, GEL, self.company)
        self.assertEqual(bloc['plus_longue_attente_heures'],
                         round(minutes / 60.0, 1))


class ResultatsTests(_Base):

    def _client_devis(self, lead, **champs):
        k = next(self._k)
        client = Client.objects.create(
            company=self.company, nom=f'Client {self.n}-{k}',
            email=f'ctl-{self.n}-{k}@example.com')
        return Devis.objects.create(
            company=self.company, reference=f'DEV-CTL-{self.n:03d}{k:03d}',
            client=client, lead=lead, taux_tva=Decimal('20.00'), **champs)

    def test_trois_resultats_sur_la_periode_et_la_portee(self):
        lead = self._lead()
        self._suivi(lead)
        VisiteTerrain.objects.create(
            company=self.company, lead=lead, date_prevue=_jour(4))
        VisiteTerrain.objects.create(                     # rendez-vous annulé
            company=self.company, lead=lead, date_prevue=None)
        self._client_devis(lead, statut=Devis.Statut.ENVOYE,
                           date_envoi=_a(_jour(-3)))
        self._client_devis(lead, statut=Devis.Statut.ACCEPTE,
                           date_envoi=_a(_jour(-4)),
                           date_acceptation=_jour(-1))
        self._client_devis(lead, statut=Devis.Statut.ENVOYE,
                           date_envoi=_a(_jour(-40)))     # hors période
        self.assertEqual(self._controle()['resultats'], {
            'visites_planifiees': 1, 'devis_envoyes': 2,
            'devis_acceptes': 1})


# ═══════════════════════════════════════════════════════════════════════════
# 7. La portée, ``owner`` et les deux refus
# ═══════════════════════════════════════════════════════════════════════════

class PorteeEtOwnerTests(_Base):

    def setUp(self):
        super().setUp()
        self.collegue = self._utilisateur('ab-collegue',
                                          role_legacy='responsable')
        mien = self._lead()
        self._suivi(mien)
        self._fait(mien, _jour(-3))
        sien = self._lead(owner=self.collegue)
        self._suivi(sien)
        self._fait(sien, _jour(-2), le=_jour(0), heure=9)
        self._etape(sien, _jour(-4))

    def test_sans_owner_toute_la_portee(self):
        controle = self._controle()
        self.assertEqual(controle['verdict']['du'], 3)
        self.assertEqual(controle['exceptions']['en_retard']['total'], 1)
        self.assertEqual(
            [ligne['nom'] for ligne in controle['commerciaux']],
            sorted([self.acteur.username, self.collegue.username]))

    def test_owner_restreint_tout_sauf_la_liste_des_commerciaux(self):
        controle = self._controle(owner=self.acteur.pk)
        self.assertEqual(controle['owner'], self.acteur.pk)
        self.assertEqual(controle['verdict']['du'], 1)
        self.assertEqual(controle['verdict']['niveau'], cs.NIVEAU_OK)
        self.assertEqual(controle['exceptions']['en_retard']['total'], 0)
        self.assertEqual(len(controle['commerciaux']), 2)
        chez_lui = self._controle(owner=self.collegue.pk)
        self.assertEqual(chez_lui['verdict']['du'], 2)
        self.assertEqual(chez_lui['exceptions']['en_retard']['total'], 1)

    def test_un_role_restreint_ne_voit_que_sa_portee(self):
        role = Role.objects.create(
            company=self.company, nom=f'Commercial ctl {self.n}',
            permissions=['crm_voir', 'records_scope_equipe'],
            est_systeme=False)
        restreint = self._utilisateur('restreint', role=role,
                                      role_legacy='responsable')
        lead = self._lead(owner=restreint)
        self._suivi(lead)
        self._fait(lead, _jour(-1))
        controle = cs.controle_suivi(self.company, restreint)
        self.assertEqual(controle['verdict']['du'], 1)
        self.assertEqual(controle['exceptions']['en_retard']['total'], 0)
        self.assertEqual([ligne['id'] for ligne in controle['commerciaux']],
                         [restreint.pk])
        _j, _o, erreurs = cs.parametres_controle(
            self.company, restreint, None, str(self.collegue.pk))
        self.assertEqual(erreurs, {'owner': cs.MESSAGE_OWNER})
        self.assertEqual(
            cs.parametres_controle(self.company, restreint, None,
                                   str(restreint.pk)),
            (14, restreint.pk, {}))

    def test_une_autre_societe_ne_se_lit_jamais(self):
        autre = Company.objects.create(
            nom=f'Cockpit controle autre {self.n}',
            slug=f'cockpit-controle-autre-{self.n}')
        autre_resp = User.objects.create_user(
            username=f'ctl-{self.n}-autre', password='x',
            role_legacy='responsable', company=autre)
        autre_lead = Lead.objects.create(
            company=autre, nom='Ailleurs', stage=stages.CONTACTED,
            owner=autre_resp, telephone=f'+212663{self.n:06d}')
        RelanceEtape.objects.create(
            company=autre, lead=autre_lead, cadence='contact', ordre=2,
            canal='appel', due_at=_a(_jour(-3)), due_date=_jour(-3))
        controle = self._controle()
        self.assertEqual(controle['verdict']['du'], 3)
        self.assertEqual(controle['exceptions']['en_retard']['total'], 1)
        self.assertNotIn(autre_resp.pk,
                         [ligne['id'] for ligne in controle['commerciaux']])
        _j, _o, erreurs = cs.parametres_controle(
            self.company, self.acteur, None, str(autre_resp.pk))
        self.assertEqual(erreurs, {'owner': cs.MESSAGE_OWNER})


class RefusTests(_Base):

    def test_jours_hors_periode_400(self):
        resp = self.api.get(URL, {'jours': '15'})
        self.assertEqual(resp.status_code, 400, resp.data)
        self.assertEqual(resp.data, {'erreurs': {'jours': cs.MESSAGE_JOURS}})

    def test_owner_inconnu_400(self):
        for brut in ('999999', 'abc'):
            with self.subTest(owner=brut):
                resp = self.api.get(URL, {'owner': brut})
                self.assertEqual(resp.status_code, 400, resp.data)
                self.assertEqual(resp.data,
                                 {'erreurs': {'owner': cs.MESSAGE_OWNER}})

    def test_owner_et_jours_valides(self):
        resp = self.api.get(URL, {'jours': '7', 'owner': self.acteur.pk})
        self.assertEqual(resp.status_code, 200, resp.data)
        self.assertEqual(resp.data['periode_jours'], 7)
        self.assertEqual(resp.data['owner'], self.acteur.pk)
