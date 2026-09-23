"""CAD26 — « Rappelez-moi dans trois semaines » = une MISE EN VEILLE.

Avant : ``reporter_prochaine_touche`` translatait toute la cadence (clôture
comprise) de l'écart choisi, sans plafond ni bifurcation. Désormais deux
gestes : « Décaler ce rappel » (inchangé) et « Mettre en veille jusqu'au… »
(``mode=veille`` sur ``relance-etapes/<id>/reporter/``).

Done de la tâche :

  * veille de 21 jours → aucune touche intermédiaire ne part, la reprise se
    fait au MÊME barreau ;
  * veille de plus d'un mois → bascule en réveil daté, TRACÉE.

Contrat partagé : la réponse porte exactement les clés de l'exemple committé
``contract_samples/relance_etape_v2.json``.

Temps gelé : les échéances et les créneaux de la société sont exactement ce
qu'une horloge vivante rend instable.
"""
import datetime
import json
from pathlib import Path

from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from authentication.models import Company
from testkit.time import frozen

from apps.crm import horaires, stages
from apps.crm.models import Lead, LeadActivity, RelanceEtape
from apps.crm.services import (
    calculer_echeances_cadence, marquer_etape_relance)
from apps.parametres.models import CompanyProfile
from apps.parametres.models_relance import CadenceRelanceEtape

User = get_user_model()

#: Mercredi 23 septembre 2026, 10 h à Casablanca — le lead arrive, jour ouvré.
MERCREDI = datetime.datetime(2026, 9, 23, 10, 0, tzinfo=horaires.CASABLANCA)

#: « Rappelez-moi dans trois semaines » : mercredi 14 octobre 2026.
TROIS_SEMAINES = '2026-10-14'
#: Plus d'un mois : jeudi 12 novembre 2026.
DEUX_MOIS = '2026-11-12'
HEURE = '11:00'

CONTRATS = Path(__file__).resolve().parent / 'contract_samples'


class _Base(TestCase):
    slug = 'cad26'

    def setUp(self):
        self.gel = frozen(MERCREDI)
        self.gel.start()
        self.addCleanup(self._arreter_gel)
        self.company = Company.objects.create(
            nom='CAD26 Solaire', slug=self.slug)
        CompanyProfile.objects.get_or_create(company=self.company)
        self.acteur = User.objects.create_user(
            username=f'{self.slug}-resp', password='x',
            role_legacy='responsable', company=self.company)
        self.lead = Lead.objects.create(
            company=self.company, nom='Aziz', stage=stages.CONTACTED,
            owner=self.acteur, telephone='+212661002601')
        self.api = APIClient()
        self.api.credentials(
            HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(self.acteur)}')
        # Le plan de prise de contact en cours : la touche « Appel 3 »
        # (ordre 4, J+1) est la seule ouverte (cadence réactive, CKP2).
        gabarits = CadenceRelanceEtape.cadence_pour(self.company, 'contact')
        echeances = calculer_echeances_cadence(
            self.lead, 'contact', MERCREDI, gabarits=gabarits)
        gabarit, echeance = next(
            (g, e) for g, e in echeances if g.ordre == 4)
        self.etape = RelanceEtape.objects.create(
            company=self.company, lead=self.lead, cadence='contact',
            ordre=gabarit.ordre, due_at=echeance,
            due_date=echeance.astimezone(horaires.CASABLANCA).date(),
            canal=gabarit.canal, libelle=gabarit.libelle,
            template_cle=gabarit.template_cle or '', cadence_depart=MERCREDI)

    def _arreter_gel(self):
        if self.gel is not None:
            self.gel.stop()
            self.gel = None

    def _veille(self, jour, mode='veille'):
        corps = {'rappel_le': jour, 'rappel_heure': HEURE}
        if mode:
            corps['mode'] = mode
        return self.api.post(
            f'/api/django/crm/relance-etapes/{self.etape.pk}/reporter/',
            corps, format='json')

    def _ouvertes(self):
        return list(self.lead.relance_etapes.filter(
            statut=RelanceEtape.Statut.A_FAIRE))


class VeilleCourteTests(_Base):
    slug = 'cad26-courte'

    def test_aucune_touche_intermediaire_ne_part(self):
        resp = self._veille(TROIS_SEMAINES)
        self.assertEqual(resp.status_code, 200, resp.data)
        cible = datetime.date.fromisoformat(TROIS_SEMAINES)
        ouvertes = self._ouvertes()
        self.assertTrue(ouvertes)
        for etape in ouvertes:
            self.assertGreaterEqual(etape.due_date, cible, etape.libelle)

    def test_la_reprise_se_fait_au_meme_barreau(self):
        self._veille(TROIS_SEMAINES)
        self.etape.refresh_from_db()
        # MÊME touche : ni consommée, ni recréée.
        self.assertEqual(self.etape.statut, RelanceEtape.Statut.A_FAIRE)
        self.assertEqual(self.etape.ordre, 4)
        self.assertEqual(
            self.etape.due_date, datetime.date.fromisoformat(TROIS_SEMAINES))
        self.assertEqual(self.lead.relance_etapes.count(), 1)
        self.assertFalse(self.lead.relance_etapes.filter(
            statut__in=(RelanceEtape.Statut.FAIT,
                        RelanceEtape.Statut.SAUTEE)).exists())

    def test_a_la_reprise_le_barreau_suivant_nait_apres_la_date(self):
        self._veille(TROIS_SEMAINES)
        self.etape.refresh_from_db()
        # On se place au jour de la reprise, et la touche est traitée.
        self._arreter_gel()
        reprise = datetime.datetime(
            2026, 10, 14, 11, 30, tzinfo=horaires.CASABLANCA)
        self.gel = frozen(reprise)
        self.gel.start()
        marquer_etape_relance(self.etape, self.acteur,
                              RelanceEtape.Statut.FAIT, outcome='non_joint')
        suivante = self._ouvertes()
        self.assertEqual(len(suivante), 1)
        self.assertGreater(suivante[0].ordre, 4)
        self.assertGreaterEqual(
            suivante[0].due_date, datetime.date.fromisoformat(TROIS_SEMAINES))

    def test_la_veille_est_ecrite_dans_le_chatter(self):
        self._veille(TROIS_SEMAINES)
        self.assertTrue(LeadActivity.objects.filter(
            lead=self.lead, kind=LeadActivity.Kind.NOTE,
            body__startswith='Mise en veille jusqu’au 14/10/2026').exists())


class BasculeReveilTests(_Base):
    slug = 'cad26-reveil'

    def test_plus_d_un_mois_bascule_en_reveil_date(self):
        resp = self._veille(DEUX_MOIS)
        self.assertEqual(resp.status_code, 200, resp.data)
        self.assertEqual(resp.data['cadence'], 'reveil')
        self.etape.refresh_from_db()
        # La cadence en cours est ARRÊTÉE, et elle le dit.
        self.assertEqual(self.etape.statut, RelanceEtape.Statut.ANNULEE)
        self.assertIn('réveil daté', self.etape.note)
        reveils = [e for e in self._ouvertes() if e.cadence == 'reveil']
        self.assertTrue(reveils)
        premier = min(reveils, key=lambda e: e.ordre)
        self.assertEqual(
            premier.due_date, datetime.date.fromisoformat(DEUX_MOIS))
        self.assertFalse(any(e.cadence == 'contact' for e in self._ouvertes()))

    def test_la_bascule_est_tracee(self):
        self._veille(DEUX_MOIS)
        self.assertTrue(LeadActivity.objects.filter(
            lead=self.lead, kind=LeadActivity.Kind.NOTE,
            body__contains='plus d’un mois d’attente').exists())


class DecalerInchangeTests(_Base):
    """Garde-fou : le geste historique « Décaler ce rappel » est intact."""

    slug = 'cad26-decaler'

    def test_sans_mode_le_report_reste_un_decalage(self):
        resp = self._veille(TROIS_SEMAINES, mode='')
        self.assertEqual(resp.status_code, 200, resp.data)
        self.etape.refresh_from_db()
        self.assertEqual(self.etape.statut, RelanceEtape.Statut.A_FAIRE)
        self.assertFalse(LeadActivity.objects.filter(
            lead=self.lead, body__startswith='Mise en veille').exists())

    def test_un_mode_inconnu_nomme_le_champ(self):
        resp = self._veille(TROIS_SEMAINES, mode='pause')
        self.assertEqual(resp.status_code, 400)
        self.assertIn('mode', resp.data['erreurs'])


class ContratPartageTests(_Base):
    slug = 'cad26-contrat'

    def test_la_reponse_a_la_forme_du_contrat(self):
        resp = self._veille(TROIS_SEMAINES)
        self.assertEqual(resp.status_code, 200, resp.data)
        contrat = json.loads((CONTRATS / 'relance_etape_v2.json')
                             .read_text(encoding='utf-8'))
        self.assertEqual(set(resp.data),
                         set(contrat['exemple']['results'][0]))
