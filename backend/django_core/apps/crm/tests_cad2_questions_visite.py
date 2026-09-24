"""CAD2 — les étapes de VISITE ne posent plus la question du suivi de
proposition, et leur clôture ne relance aucun plan après-devis.

Avant : les trois gestes du rendez-vous vivent dans la cadence
``apres_devis`` (pour s'afficher dans la même frise) et l'écran choisissait ses
questions PAR CADENCE ; sur « Débrief visite — rappeler le client », la
réponse naturelle « le client est joint » faisait redémarrer le suivi de
proposition depuis son barreau 1 dès qu'aucun barreau n'avait encore été
consommé (plan annulé par le moteur, jamais démarré) — « Le PDF s'ouvre
bien ? » après une visite.

Ce fichier verrouille la moitié SERVEUR :

  * le contrat ``relance_etape_v2`` porte un état « débrief de visite »
    (``exemple_debrief_visite``) que l'écran importe — ses ``suites`` sont
    EXACTEMENT celles du moteur, lues sur le LIBELLÉ, et n'annoncent aucun
    démarrage du plan ;
  * une étape de visite close ne DÉMARRE jamais le suivi de proposition, par
    aucun des deux chemins (filet du « Fait » et récepteur d'issue MRY9) ; le
    POURSUIVRE reste permis (CAD1).

La moitié ÉCRAN (le jeu de questions de visite dans ``RelanceEtapeRow``,
« Intéressé » absent) importe ``exemple_debrief_visite``.
"""
import datetime
import json
from decimal import Decimal
from pathlib import Path

from django.contrib.auth import get_user_model
from django.test import SimpleTestCase, TestCase

from authentication.models import Company
from testkit.time import frozen

from apps.crm import horaires, services, stages
from apps.crm import suite_touche as st
from apps.crm.models import Client, Lead, LeadActivity, RelanceEtape
from apps.parametres.models import CompanyProfile
from apps.parametres.models_relance import CADENCES_DEFAUT

User = get_user_model()

GEL = datetime.datetime(2026, 9, 23, 10, 0, tzinfo=horaires.CASABLANCA)

ICI = Path(__file__).resolve().parent
CONTRAT = json.loads((ICI / 'contract_samples' / 'relance_etape_v2.json')
                     .read_text(encoding='utf-8'))
PHRASES = json.loads(
    (ICI.parents[3] / 'frontend' / 'src' / 'features' / 'crm' / 'relances'
     / 'suite_phrases.json').read_text(encoding='utf-8'))['effets']

A_FAIRE = RelanceEtape.Statut.A_FAIRE
FAIT = RelanceEtape.Statut.FAIT


def _ordres(cadence):
    return frozenset(e['ordre'] for e in CADENCES_DEFAUT.get(cadence, []))


class ContratDebriefVisiteTests(SimpleTestCase):

    def setUp(self):
        [self.touche] = CONTRAT['exemple_debrief_visite']['results']

    def test_meme_forme_que_l_exemple(self):
        self.assertEqual(set(self.touche),
                         set(CONTRAT['exemple']['results'][0]))

    def test_la_nature_se_lit_sur_le_libelle(self):
        self.assertIn(self.touche['libelle'], services._LIBELLES_VISITE)
        etape = RelanceEtape(cadence=self.touche['cadence'],
                             libelle=self.touche['libelle'])
        self.assertEqual(st.nature_touche(etape), st.NATURE_VISITE)

    def test_les_suites_sont_celles_du_moteur(self):
        etape = RelanceEtape(
            cadence=self.touche['cadence'], ordre=self.touche['ordre'],
            canal=self.touche['canal'], libelle=self.touche['libelle'],
            statut=self.touche['statut'], devis_id=self.touche['devis'])
        etape.lead = Lead(nom=self.touche['lead_nom'],
                          stage=stages.QUOTE_SENT)
        self.assertEqual(
            st.promesses_touche(etape, ordres=_ordres('apres_devis')),
            self.touche['suites'])

    def test_aucune_suite_n_annonce_un_demarrage_du_plan(self):
        for cle, codes in self.touche['suites'].items():
            with self.subTest(reponse=cle):
                self.assertNotIn(st.TOUCHE_SUIVANTE, codes)
                self.assertNotIn(st.SUIVI_PROPOSITION_DEMARRE, codes)
                self.assertTrue(set(codes) <= set(PHRASES))

    def test_la_cloture_d_une_etape_de_visite_se_reconnait(self):
        visite = RelanceEtape(libelle=services.VISITE_DEBRIEF_LIBELLE)
        barreau = RelanceEtape(libelle='Preuve — installation comparable')
        corps = ' (Appel, cadence apres_devis) marquée faite.'
        self.assertTrue(services.est_cloture_d_etape_visite(LeadActivity(
            body=services.prefixe_activite_touche(visite) + corps)))
        self.assertFalse(services.est_cloture_d_etape_visite(LeadActivity(
            body=services.prefixe_activite_touche(barreau) + corps)))


class DebriefCloseSansRelanceTests(TestCase):

    def setUp(self):
        gel = frozen(GEL)
        gel.start()
        self.addCleanup(gel.stop)
        self.company = Company.objects.create(nom='CAD2 Solaire',
                                              slug='cad2-solaire')
        CompanyProfile.objects.get_or_create(company=self.company)
        self.acteur = User.objects.create_user(
            username='cad2-resp', password='x', role_legacy='responsable',
            company=self.company)
        self.lead = Lead.objects.create(
            company=self.company, nom='Bennani', prenom='Rachid',
            stage=stages.QUOTE_SENT, owner=self.acteur,
            telephone='+212661000460')
        client = Client.objects.create(company=self.company, nom='Bennani',
                                       email='cad2@example.com')
        from apps.ventes.models import Devis

        self.devis = Devis.objects.create(
            company=self.company, reference='DEV-2609-CAD2', client=client,
            lead=self.lead, statut='envoye', taux_tva=Decimal('20.00'),
            date_envoi=GEL - datetime.timedelta(days=10))
        self.debrief = RelanceEtape.objects.create(
            company=self.company, lead=self.lead, cadence='apres_devis',
            ordre=services.VISITE_ORDRE_DEBRIEF,
            canal=RelanceEtape.Canal.APPEL,
            libelle=services.VISITE_DEBRIEF_LIBELLE, devis=self.devis,
            due_at=GEL, due_date=GEL.date())

    def _barreaux_ouverts(self):
        """Les barreaux du PLAN après-devis encore à faire — hors gestes de
        visite."""
        return (self.lead.relance_etapes
                .filter(cadence='apres_devis', statut=A_FAIRE)
                .exclude(libelle__in=services._LIBELLES_VISITE))

    def _barreau(self, ordre, statut):
        gabarit = next(e for e in CADENCES_DEFAUT['apres_devis']
                       if e['ordre'] == ordre)
        quand = GEL - datetime.timedelta(days=8)
        return RelanceEtape.objects.create(
            company=self.company, lead=self.lead, cadence='apres_devis',
            ordre=ordre, canal=gabarit['canal'], libelle=gabarit['libelle'],
            devis=self.devis, statut=statut, due_at=quand,
            due_date=quand.date(),
            cadence_depart=GEL - datetime.timedelta(days=10),
            traite_le=None if statut == A_FAIRE else quand)

    def test_debrief_joint_ne_redemarre_pas_le_plan(self):
        # Le plan avait été ANNULÉ par le moteur (aucun barreau consommé) :
        # c'est exactement le cas où l'ancien filet le rejouait depuis 1.
        self._barreau(1, RelanceEtape.Statut.ANNULEE)
        services.marquer_etape_relance(
            self.debrief, self.acteur, FAIT, outcome='joint')
        self.assertFalse(self._barreaux_ouverts().exists())
        # Le lead n'est jamais laissé sans suite : l'étape générique est là.
        self.assertTrue(self.lead.relance_etapes.filter(
            cadence='generique', statut=A_FAIRE).exists())

    def test_debrief_sans_reponse_ne_demarre_pas_le_plan(self):
        services.marquer_etape_relance(
            self.debrief, self.acteur, FAIT, outcome='non_joint')
        self.assertFalse(self._barreaux_ouverts().exists())

    def test_un_plan_deja_servi_est_poursuivi_jamais_rejoue(self):
        # CAD1 — poursuivre reste permis : le barreau 2 consommé fait naître
        # le 3, jamais le 1.
        self._barreau(2, FAIT)
        services.marquer_etape_relance(
            self.debrief, self.acteur, FAIT, outcome='joint')
        ordres = set(self._barreaux_ouverts().values_list('ordre', flat=True))
        self.assertNotIn(1, ordres)
        self.assertTrue(all(o > 2 for o in ordres), ordres)
