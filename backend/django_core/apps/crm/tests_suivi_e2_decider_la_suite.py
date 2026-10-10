"""SUIVI E2 — « Décider la suite » : la réponse « Perdu », et plus de boucle
sur « refus ».

SUIVI-PARCOURS 30/09/2026. L'étape « Décider la suite — perdu (motif) ou
relance ultérieure » n'offrait aucune façon de dire « perdu » : il fallait
quitter la file pour la fiche. Et « refus » coché dessus RE-POSAIT la même
étape à l'infini (le filet du récepteur MRY9 ne connaît pas la clé de la
touche close : la ceinture anti-tapis-roulant ne jouait pas).

Décisions :

* nouvelle réponse ``perdu`` (« Perdu — clore le dossier »), valable
  UNIQUEMENT sur l'étape de clé ``decider_suite`` ; ``motif_perte``
  OBLIGATOIRE, un motif ACTIF de la société (sans casse) — sinon 400 qui
  nomme le champ. Effet : la touche est close (FAIT, issue « refus », note
  « Perdu — <motif> »), le lead passe PERDU avec ce motif (journalisé comme la
  fiche), TOUTES ses touches ouvertes s'arrêtent, rien n'est posé ensuite ;
* ``outcome=refuse`` sur « Décider la suite » : 400 qui nomme ``outcome``.

``marquer_lead_perdu_junk`` (CAD11) reste un alias mince de
``marquer_lead_perdu``.

Horloge FIXE : mercredi 23/09/2026, 10 h à Casablanca.
"""
import datetime
import itertools

from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from authentication.models import Company
from testkit.time import frozen

from apps.crm import horaires, services, stages
from apps.crm import cadence_reponses
from apps.crm.cadence_config import CLE_DECIDER_SUITE, CLE_DEVIS, q_etape
from apps.crm.models import Lead, LeadActivity, MotifPerte, RelanceEtape
from apps.crm.views import MESSAGE_REFUS_SUR_DECIDER_SUITE
from apps.parametres.models import CompanyProfile

User = get_user_model()

GEL = datetime.datetime(2026, 9, 23, 10, 0, tzinfo=horaires.CASABLANCA)
A_FAIRE = RelanceEtape.Statut.A_FAIRE
FAIT = RelanceEtape.Statut.FAIT
MOTIF = 'Prix trop élevé'

_seq = itertools.count(1)


class _Base(TestCase):

    def setUp(self):
        gel = frozen(GEL)
        gel.start()
        self.addCleanup(gel.stop)
        n = next(_seq)
        self.company = Company.objects.create(
            nom=f'Suivi E2 {n}', slug=f'suivi-e2-{n}')
        CompanyProfile.objects.get_or_create(company=self.company)
        MotifPerte.objects.create(company=self.company, nom=MOTIF)
        MotifPerte.objects.create(company=self.company, nom='Ancien motif',
                                  archived=True)
        self.acteur = User.objects.create_user(
            username=f'suivi-e2-resp-{n}', password='x',
            role_legacy='responsable', company=self.company)
        self.api = APIClient()
        self.api.credentials(
            HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(self.acteur)}')
        self.lead = Lead.objects.create(
            company=self.company, nom=f'Prospect E2 {n}',
            stage=stages.CONTACTED, owner=self.acteur,
            telephone=f'+21266120{n:04d}')

    def _touche(self, **champs):
        valeurs = dict(company=self.company, lead=self.lead,
                       cadence='generique', ordre=1,
                       canal=RelanceEtape.Canal.APPEL, due_at=GEL,
                       due_date=GEL.date())
        valeurs.update(champs)
        return RelanceEtape.objects.create(**valeurs)

    def _decider(self):
        return self._touche(
            cle=CLE_DECIDER_SUITE, libelle=services.FILET_REFUS_LIBELLE)

    def _fait(self, etape, **corps):
        return self.api.post(
            f'/api/django/crm/relance-etapes/{etape.pk}/fait/', corps,
            format='json')

    def _ouvertes(self):
        return self.lead.relance_etapes.filter(statut=A_FAIRE)


class PerduTests(_Base):

    def test_perdu_clot_le_dossier_avec_son_motif(self):
        decider = self._decider()
        autre = self._touche(cadence='reveil', ordre=1,
                             libelle='Réveil J30',
                             due_at=GEL + datetime.timedelta(days=30),
                             due_date=(GEL + datetime.timedelta(days=30))
                             .date())

        resp = self._fait(decider, reponse=cadence_reponses.REPONSE_PERDU,
                          motif_perte='prix TROP élevé', note='Trop cher')

        self.assertEqual(resp.status_code, 200, resp.data)
        self.lead.refresh_from_db()
        self.assertTrue(self.lead.perdu)
        self.assertEqual(self.lead.motif_perte, MOTIF)
        self.assertFalse(self._ouvertes().exists())
        decider.refresh_from_db()
        self.assertEqual(decider.statut, FAIT)
        self.assertEqual(decider.outcome, 'refuse')
        self.assertEqual(decider.note, f'Perdu — {MOTIF} — Trop cher')
        autre.refresh_from_db()
        self.assertEqual(autre.statut, RelanceEtape.Statut.ANNULEE)
        # Rien n'est posé ensuite — et surtout pas une seconde « décider ».
        self.assertEqual(self.lead.relance_etapes.filter(
            q_etape(CLE_DECIDER_SUITE)).count(), 1)
        self.assertIsNone(resp.data['prochaine_touche'])
        # Journalisé comme la fiche le ferait (ancien → nouveau).
        self.assertTrue(self.lead.activites.filter(
            kind=LeadActivity.Kind.MODIFICATION, field='perdu').exists())

    def test_motif_absent_refuse_en_nommant_le_champ(self):
        decider = self._decider()
        resp = self._fait(decider, reponse=cadence_reponses.REPONSE_PERDU)
        self.assertEqual(resp.status_code, 400, resp.data)
        self.assertIn('Motif de perte', resp.data['erreurs']['motif_perte'])
        self._rien_n_a_bouge(decider)

    def test_motif_hors_liste_refuse(self):
        decider = self._decider()
        resp = self._fait(decider, reponse=cadence_reponses.REPONSE_PERDU,
                          motif_perte='Inventé')
        self.assertEqual(resp.status_code, 400, resp.data)
        self.assertIn('« Inventé »', resp.data['erreurs']['motif_perte'])
        self._rien_n_a_bouge(decider)

    def test_motif_archive_refuse(self):
        decider = self._decider()
        resp = self._fait(decider, reponse=cadence_reponses.REPONSE_PERDU,
                          motif_perte='Ancien motif')
        self.assertEqual(resp.status_code, 400, resp.data)
        self.assertIn('motif_perte', resp.data['erreurs'])
        self._rien_n_a_bouge(decider)

    def test_motif_d_une_autre_societe_refuse(self):
        n = next(_seq)
        autre = Company.objects.create(nom=f'Suivi E2 autre {n}',
                                       slug=f'suivi-e2-autre-{n}')
        MotifPerte.objects.create(company=autre, nom='Motif étranger')
        decider = self._decider()
        resp = self._fait(decider, reponse=cadence_reponses.REPONSE_PERDU,
                          motif_perte='Motif étranger')
        self.assertEqual(resp.status_code, 400, resp.data)
        self._rien_n_a_bouge(decider)

    def test_perdu_hors_de_decider_la_suite_est_refuse(self):
        devis = self._touche(cle=CLE_DEVIS,
                             libelle=services.FILET_JOINT_LIBELLE)
        resp = self._fait(devis, reponse=cadence_reponses.REPONSE_PERDU,
                          motif_perte=MOTIF)
        self.assertEqual(resp.status_code, 400, resp.data)
        self.assertIn('« Perdu — clore le dossier »',
                      resp.data['erreurs']['reponse'])
        self.lead.refresh_from_db()
        self.assertFalse(self.lead.perdu)

    def _rien_n_a_bouge(self, decider):
        decider.refresh_from_db()
        self.assertEqual(decider.statut, A_FAIRE)
        self.lead.refresh_from_db()
        self.assertFalse(self.lead.perdu)


class RefusSurDeciderLaSuiteTests(_Base):

    def test_refus_est_refuse_et_ne_repose_rien(self):
        decider = self._decider()
        resp = self._fait(decider, outcome='refuse')
        self.assertEqual(resp.status_code, 400, resp.data)
        self.assertEqual(resp.data['erreurs']['outcome'],
                         MESSAGE_REFUS_SUR_DECIDER_SUITE)
        decider.refresh_from_db()
        self.assertEqual(decider.statut, A_FAIRE)
        self.assertEqual(self._ouvertes().count(), 1)

    def test_temoin_refus_sur_une_autre_etape_reste_accepte(self):
        devis = self._touche(cle=CLE_DEVIS,
                             libelle=services.FILET_JOINT_LIBELLE)
        resp = self._fait(devis, outcome='refuse')
        self.assertEqual(resp.status_code, 200, resp.data)
        self.assertTrue(self._ouvertes().filter(
            q_etape(CLE_DECIDER_SUITE)).exists())


class AliasJunkTests(_Base):

    def test_marquer_lead_perdu_junk_reste_un_alias(self):
        self._touche(cadence='contact', ordre=2, libelle="Appel d'ouverture")
        self.assertTrue(cadence_reponses.marquer_lead_perdu_junk(
            self.lead, self.acteur, 'Numéro invalide'))
        self.lead.refresh_from_db()
        self.assertTrue(self.lead.perdu)
        self.assertEqual(self.lead.motif_perte, 'Numéro invalide')
        self.assertFalse(self._ouvertes().exists())
        # Idempotent : un lead déjà perdu n'est pas réécrit.
        self.assertFalse(cadence_reponses.marquer_lead_perdu_junk(
            self.lead, self.acteur, 'Autre'))
