"""CKP3 — la règle « à l'heure » du cockpit CRM.

ACRM64 (décision fondateur D-ACRM-6 (i)=(a), 09/10/2026) a RETIRÉ les deux
agrégats ``kpi_adherence`` / ``mes_stats_relance`` et leurs routes
(``relance-etapes/kpi-adherence/``, ``relance-etapes/mes-stats/`` — leurs écrans
étaient retirés depuis le 30/09) : leur 404 est verrouillé dans
``tests_acrm_routes_retirees``. Ce qui SURVIT, et que ce fichier garde, est la
règle de mesure qu'ils partageaient avec ``controle_suivi`` (le survivant du
« en retard », ALEA32) : ``selectors._a_lheure`` — une touche FAITE le jour
dû (ou avant) est à l'heure ; le jour compte, jamais la minute ; une touche
sautée ou ANNULÉE PAR LE MOTEUR (CKP1) n'est jamais « faite à l'heure ».

Le temps est GELÉ : « à l'heure » est exactement la question qu'une horloge
vivante rend instable.
"""
import datetime

from django.contrib.auth import get_user_model
from django.test import TestCase

from authentication.models import Company
from testkit.time import frozen

from apps.crm import horaires, stages
from apps.crm.models import Lead, RelanceEtape
from apps.crm.selectors import _a_lheure
from apps.parametres.models import CompanyProfile

User = get_user_model()

#: Jeudi 10 septembre 2026, 12 h à Casablanca — jour ouvré, en pleine fenêtre.
MAINTENANT = datetime.datetime(2026, 9, 10, 12, 0, tzinfo=horaires.CASABLANCA)
AUJOURDHUI = MAINTENANT.date()


def _quand(jours_avant, heure=10):
    return datetime.datetime.combine(
        AUJOURDHUI - datetime.timedelta(days=jours_avant),
        datetime.time(heure, 0), tzinfo=horaires.CASABLANCA)


class ALheureTests(TestCase):

    def setUp(self):
        gel = frozen(MAINTENANT)
        gel.start()
        self.addCleanup(gel.stop)
        self.company, _ = Company.objects.get_or_create(
            slug='ckp3-a-lheure', defaults={'nom': 'ckp3-a-lheure'})
        CompanyProfile.objects.get_or_create(company=self.company)
        self.acteur = User.objects.create_user(
            username='ckp3-resp', password='x',
            role_legacy='responsable', company=self.company)
        self.lead = Lead.objects.create(
            company=self.company, nom='Aziz', prenom='Benali',
            ville='Bouskoura', stage=stages.CONTACTED, owner=self.acteur)

    def _touche(self, *, statut, due_jours, traite_jours=None, ordre=1,
                heure_traite=10):
        due = _quand(due_jours)
        return RelanceEtape.objects.create(
            company=self.company, lead=self.lead, cadence='contact',
            ordre=ordre, due_at=due, due_date=due.date(),
            canal=RelanceEtape.Canal.APPEL, libelle="Appel d'ouverture",
            statut=statut,
            traite_le=(None if traite_jours is None
                       else _quand(traite_jours, heure_traite)),
            traite_par=(None if traite_jours is None else self.acteur))

    def test_faite_le_jour_du_est_a_lheure(self):
        self.assertTrue(_a_lheure(self._touche(
            statut='fait', due_jours=5, traite_jours=5)))

    def test_le_jour_compte_jamais_la_minute(self):
        """Faite le soir du jour dû : toujours à l'heure."""
        self.assertTrue(_a_lheure(self._touche(
            statut='fait', due_jours=5, traite_jours=5, heure_traite=21)))

    def test_faite_le_lendemain_est_en_retard(self):
        self.assertFalse(_a_lheure(self._touche(
            statut='fait', due_jours=3, traite_jours=2)))

    def test_une_sautee_ou_une_annulation_moteur_nest_jamais_a_lheure(self):
        """Une ANNULATION MOTEUR (CKP1) n'est jamais une touche faite."""
        for ordre, statut in ((1, 'sautee'), (2, 'annulee')):
            self.assertFalse(_a_lheure(self._touche(
                statut=statut, due_jours=2, traite_jours=2, ordre=ordre)),
                statut)

    def test_une_touche_ouverte_nest_jamais_a_lheure(self):
        self.assertFalse(_a_lheure(self._touche(
            statut='a_faire', due_jours=-2)))
