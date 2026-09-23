"""CAD9 — la réponse « Décision à plusieurs (famille / propriétaire) ».

Avant : le barreau « dimanche famille » n'était posé que si le lead portait
DÉJÀ l'étiquette « Décision à plusieurs » au démarrage du plan, et aucune
réponse de touche ne la posait — le lead moyen recevait 9 touches
après-devis, pas 10.

Done : poser l'étiquette en cours de plan (ici sur l'« Appel de suivi », le
barreau qui précède le dimanche famille) fait RÉAPPARAÎTRE le barreau
dimanche famille dans le plan : ``materialiser_touche_suivante`` recalcule la
partition à chaque touche. La note distingue « famille » (un délai) de
« propriétaire » (un interlocuteur à changer). Contrat partagé : la réponse
porte les clés de l'exemple committé ``relance_etape_v2.json``.
"""
import datetime
import json
from decimal import Decimal
from pathlib import Path

from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from authentication.models import Company
from testkit.time import frozen

from apps.crm import horaires, stages
from apps.crm.models import Client, Lead, RelanceEtape
from apps.crm.services import calculer_echeances_cadence
from apps.parametres.models import CompanyProfile
from apps.parametres.models_relance import CadenceRelanceEtape
from apps.ventes.models import Devis

User = get_user_model()

MERCREDI = datetime.datetime(2026, 9, 23, 10, 0, tzinfo=horaires.CASABLANCA)
#: Devis parti la veille : la touche 2 (« Appel de suivi », J+2) est ouverte,
#: le dimanche famille (J+3 → dimanche 27/09) n'est pas encore dépassé.
DEPART = MERCREDI - datetime.timedelta(days=1)
DIMANCHE_FAMILLE = 'dimanche_famille'

CONTRATS = Path(__file__).resolve().parent / 'contract_samples'


class _Base(TestCase):
    slug = 'cad9'

    def setUp(self):
        gel = frozen(MERCREDI)
        gel.start()
        self.addCleanup(gel.stop)
        self.company = Company.objects.create(
            nom='CAD9 Solaire', slug=self.slug)
        CompanyProfile.objects.get_or_create(company=self.company)
        self.acteur = User.objects.create_user(
            username=f'{self.slug}-resp', password='x',
            role_legacy='responsable', company=self.company)
        self.lead = Lead.objects.create(
            company=self.company, nom='Youssef', stage=stages.QUOTE_SENT,
            owner=self.acteur, telephone='+212661000901')
        client = Client.objects.create(
            company=self.company, nom='Youssef',
            email=f'{self.slug}@example.com')
        self.devis = Devis.objects.create(
            company=self.company, reference=f'DEV-{self.slug}-0001',
            client=client, lead=self.lead, statut=Devis.Statut.ENVOYE,
            taux_tva=Decimal('20.00'), date_envoi=DEPART)
        self.gabarits = CadenceRelanceEtape.cadence_pour(
            self.company, 'apres_devis')
        # Le plan SANS l'étiquette : le dimanche famille n'y est pas.
        echeances = calculer_echeances_cadence(
            self.lead, 'apres_devis', DEPART, gabarits=self.gabarits)
        self.assertNotIn(DIMANCHE_FAMILLE,
                         [g.template_cle for g, _e in echeances])
        for gabarit, echeance in echeances:
            if gabarit.ordre > 2:
                break
            ouverte = gabarit.ordre == 2
            etape = RelanceEtape.objects.create(
                company=self.company, lead=self.lead, cadence='apres_devis',
                ordre=gabarit.ordre, due_at=echeance,
                due_date=echeance.astimezone(horaires.CASABLANCA).date(),
                canal=gabarit.canal, libelle=gabarit.libelle,
                template_cle=gabarit.template_cle or '', devis=self.devis,
                cadence_depart=DEPART,
                statut=(RelanceEtape.Statut.A_FAIRE if ouverte
                        else RelanceEtape.Statut.FAIT),
                traite_par=None if ouverte else self.acteur,
                traite_le=None if ouverte else echeance)
            if ouverte:
                self.touche = etape
        self.api = APIClient()
        self.api.credentials(
            HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(self.acteur)}')

    def _fait(self, **corps):
        return self.api.post(
            f'/api/django/crm/relance-etapes/{self.touche.pk}/fait/',
            corps, format='json')

    def _ouverte(self):
        ouvertes = list(self.lead.relance_etapes.filter(
            statut=RelanceEtape.Statut.A_FAIRE))
        self.assertEqual(len(ouvertes), 1, [e.libelle for e in ouvertes])
        return ouvertes[0]


class DimancheFamilleReinjecteTests(_Base):
    slug = 'cad9-dimanche'

    def test_poser_l_etiquette_reinjecte_le_dimanche_famille(self):
        resp = self._fait(reponse='decision_famille')
        self.assertEqual(resp.status_code, 200, resp.data)
        self.lead.refresh_from_db()
        self.assertIn('Décision à plusieurs', self.lead.tags or '')
        suivante = self._ouverte()
        self.assertEqual(suivante.template_cle, DIMANCHE_FAMILLE)
        self.assertEqual(suivante.ordre, 3)
        # Le barreau tombe bien un dimanche, dans la fenêtre 16 h-19 h.
        locale = suivante.due_at.astimezone(horaires.CASABLANCA)
        self.assertEqual(locale.weekday(), 6)
        # Et la partition du plan le contient désormais.
        echeances = calculer_echeances_cadence(
            self.lead, 'apres_devis', DEPART, gabarits=self.gabarits)
        self.assertIn(DIMANCHE_FAMILLE,
                      [g.template_cle for g, _e in echeances])

    def test_temoin_sans_la_reponse_le_dimanche_n_apparait_pas(self):
        resp = self._fait(outcome='non_joint')
        self.assertEqual(resp.status_code, 200, resp.data)
        self.assertNotEqual(self._ouverte().template_cle, DIMANCHE_FAMILLE)

    def test_l_etiquette_n_est_jamais_doublee(self):
        self.lead.tags = 'Decision a plusieurs'
        self.lead.save(update_fields=['tags'])
        self._fait(reponse='decision_famille')
        self.lead.refresh_from_db()
        self.assertEqual(self.lead.tags, 'Decision a plusieurs')


class NoteDistingueTests(_Base):
    slug = 'cad9-note'

    def test_famille_est_un_delai(self):
        self._fait(reponse='decision_famille')
        self.touche.refresh_from_db()
        self.assertEqual(self.touche.outcome, 'rappel')
        self.assertIn('en famille', self.touche.note)
        self.assertIn('un délai', self.touche.note)

    def test_proprietaire_est_un_interlocuteur_a_changer(self):
        self._fait(reponse='decision_proprietaire')
        self.touche.refresh_from_db()
        self.assertIn('le propriétaire décide', self.touche.note)
        self.assertIn('interlocuteur à changer', self.touche.note)


class ContratPartageTests(_Base):
    slug = 'cad9-contrat'

    def test_la_reponse_a_la_forme_du_contrat(self):
        resp = self._fait(reponse='decision_famille')
        self.assertEqual(resp.status_code, 200, resp.data)
        contrat = json.loads((CONTRATS / 'relance_etape_v2.json')
                             .read_text(encoding='utf-8'))
        self.assertEqual(set(resp.data) - {'prochaine_touche'},
                         set(contrat['exemple']['results'][0]))
        self.assertEqual(resp.data['prochaine_touche']['canal'],
                         RelanceEtape.Canal.WHATSAPP)
