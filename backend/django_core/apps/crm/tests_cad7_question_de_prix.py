"""CAD7 — la réponse « Question de prix — veut négocier ».

Avant : la réponse la plus fréquente sur une proposition n'avait pas de
bouton — « Intéressé » (faux : il n'a pas dit oui) ou « Refuse la
proposition » (faux : il négocie) — et la négociation ne laissait aucune
trace dans l'ERP.

Done : l'issue ``rappel`` + la note typée « Question de prix », et AUCUN
message de cadence ne part tant que la touche n'est pas rouverte. Garde-fou :
ni ``annonce_appel_reda`` ni ``offre_reda`` ne partent (CAD60).
Contrat partagé : la réponse porte les clés de l'exemple committé
``relance_etape_v2.json`` (plus ``prochaine_touche``).
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
from apps.crm.models import Client, Lead, LeadActivity, RelanceEtape
from apps.crm.services import (
    QUESTION_PRIX_LIBELLE, calculer_echeances_cadence)
from apps.parametres.models import CompanyProfile
from apps.parametres.models_relance import CadenceRelanceEtape
from apps.ventes.models import Devis

User = get_user_model()

#: Mercredi 23 septembre 2026, 10 h à Casablanca.
MERCREDI = datetime.datetime(2026, 9, 23, 10, 0, tzinfo=horaires.CASABLANCA)
#: Le devis est parti la veille : la touche 2 (« Appel de suivi », J+2) est
#: le prochain geste du protocole.
DEPART = MERCREDI - datetime.timedelta(days=1)
TEXTES_DU_FONDATEUR = ('annonce_appel_reda', 'offre_reda')

CONTRATS = Path(__file__).resolve().parent / 'contract_samples'


class _Base(TestCase):
    slug = 'cad7'

    def setUp(self):
        gel = frozen(MERCREDI)
        gel.start()
        self.addCleanup(gel.stop)
        self.company = Company.objects.create(
            nom='CAD7 Solaire', slug=self.slug)
        CompanyProfile.objects.get_or_create(company=self.company)
        self.acteur = User.objects.create_user(
            username=f'{self.slug}-resp', password='x',
            role_legacy='responsable', company=self.company)
        self.lead = Lead.objects.create(
            company=self.company, nom='Salma', stage=stages.QUOTE_SENT,
            owner=self.acteur, telephone='+212661000701')
        client = Client.objects.create(
            company=self.company, nom='Salma',
            email=f'{self.slug}@example.com')
        self.devis = Devis.objects.create(
            company=self.company, reference=f'DEV-{self.slug}-0001',
            client=client, lead=self.lead, statut=Devis.Statut.ENVOYE,
            taux_tva=Decimal('20.00'), date_envoi=DEPART)
        gabarits = CadenceRelanceEtape.cadence_pour(
            self.company, 'apres_devis')
        echeances = calculer_echeances_cadence(
            self.lead, 'apres_devis', DEPART, gabarits=gabarits)
        self.etapes = {}
        for gabarit, echeance in echeances:
            if gabarit.ordre > 2:
                break
            ouverte = gabarit.ordre == 2
            self.etapes[gabarit.ordre] = RelanceEtape.objects.create(
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
        self.touche = self.etapes[2]
        self.api = APIClient()
        self.api.credentials(
            HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(self.acteur)}')

    def _repondre(self, etape=None, **corps):
        etape = etape or self.touche
        return self.api.post(
            f'/api/django/crm/relance-etapes/{etape.pk}/fait/',
            {'reponse': 'question_prix', **corps}, format='json')

    def _ouvertes(self, cadence=None):
        qs = self.lead.relance_etapes.filter(
            statut=RelanceEtape.Statut.A_FAIRE)
        if cadence:
            qs = qs.filter(cadence=cadence)
        return list(qs)


class QuestionDePrixTests(_Base):
    slug = 'cad7-base'

    def test_issue_rappel_et_note_typee(self):
        resp = self._repondre(note='Trouve 15 % trop cher')
        self.assertEqual(resp.status_code, 200, resp.data)
        self.touche.refresh_from_db()
        self.assertEqual(self.touche.statut, RelanceEtape.Statut.FAIT)
        self.assertEqual(self.touche.outcome, 'rappel')
        self.assertIn('Question de prix', self.touche.note)
        ligne = LeadActivity.objects.get(
            lead=self.lead, kind=LeadActivity.Kind.APPEL, outcome='rappel')
        self.assertIn('Question de prix', ligne.body)
        self.assertIn('Trouve 15 % trop cher', ligne.body)

    def test_aucun_message_de_cadence_tant_que_la_pause_est_ouverte(self):
        self._repondre()
        # Le tambour se tait : AUCUNE touche du suivi de proposition ouverte.
        self.assertEqual(self._ouvertes('apres_devis'), [])
        pauses = self._ouvertes('generique')
        self.assertEqual([e.libelle for e in pauses], [QUESTION_PRIX_LIBELLE])
        self.assertEqual(pauses[0].template_cle, '')

    def test_l_offre_du_fondateur_ne_part_jamais(self):
        self._repondre()
        self.assertFalse(self.lead.relance_etapes.filter(
            template_cle__in=TEXTES_DU_FONDATEUR).exists())
        for cle in TEXTES_DU_FONDATEUR:
            self.assertFalse(LeadActivity.objects.filter(
                lead=self.lead, body__contains=cle).exists())

    def test_traiter_la_pause_rouvre_le_suivi_au_barreau_suivant(self):
        self._repondre()
        pause = self._ouvertes('generique')[0]
        resp = self.api.post(
            f'/api/django/crm/relance-etapes/{pause.pk}/fait/', {},
            format='json')
        self.assertEqual(resp.status_code, 200, resp.data)
        suivantes = self._ouvertes('apres_devis')
        self.assertEqual(len(suivantes), 1)
        # Le barreau SUIVANT, jamais le barreau 1 (CAD1) : le suivi reprend.
        self.assertGreater(suivantes[0].ordre, self.touche.ordre)

    def test_hors_suivi_de_proposition_la_reponse_est_refusee(self):
        quand = MERCREDI + datetime.timedelta(hours=2)
        contact = RelanceEtape.objects.create(
            company=self.company, lead=self.lead, cadence='contact',
            ordre=4, canal=RelanceEtape.Canal.APPEL, libelle='Appel 3',
            due_at=quand, due_date=quand.date())
        resp = self._repondre(etape=contact)
        self.assertEqual(resp.status_code, 400)
        self.assertIn('suivi de proposition', resp.data['erreurs']['reponse'])


class ContratPartageTests(_Base):
    slug = 'cad7-contrat'

    def test_la_reponse_a_la_forme_du_contrat(self):
        resp = self._repondre()
        self.assertEqual(resp.status_code, 200, resp.data)
        contrat = json.loads((CONTRATS / 'relance_etape_v2.json')
                             .read_text(encoding='utf-8'))
        self.assertEqual(set(resp.data) - {'prochaine_touche'},
                         set(contrat['exemple']['results'][0]))
        # Plus rien d'ouvert dans le suivi de proposition : pas de « prochain
        # message » à annoncer.
        self.assertIsNone(resp.data['prochaine_touche'])
