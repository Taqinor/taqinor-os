"""CAD8 — la réponse « Demande un devis modifié », atteignable au téléphone.

Avant : l'étape « Préparer le devis modifié — rappeler le client »
(``VISITE_DEVIS_LIBELLE``) n'était posée que depuis la qualification d'une
visite ; un client qui demandait une variante au téléphone n'avait pas de
réponse, et « Intéressé » relançait le protocole sur un devis écarté.

Done : l'étape est posée, et AUCUNE touche après-devis (barreau du protocole)
n'est ouverte tant que le nouveau devis n'est pas envoyé. Contrat partagé :
la réponse porte les clés de l'exemple committé ``relance_etape_v2.json``
(plus ``prochaine_touche``).
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
    VISITE_DEBRIEF_LIBELLE, VISITE_DEVIS_LIBELLE, VISITE_ORDRE_DEBRIEF,
    calculer_echeances_cadence)
from apps.parametres.models import CompanyProfile
from apps.parametres.models_relance import CadenceRelanceEtape
from apps.ventes.models import Devis

User = get_user_model()

MERCREDI = datetime.datetime(2026, 9, 23, 10, 0, tzinfo=horaires.CASABLANCA)
DEPART = MERCREDI - datetime.timedelta(days=1)

CONTRATS = Path(__file__).resolve().parent / 'contract_samples'


class _Base(TestCase):
    slug = 'cad8'

    def setUp(self):
        gel = frozen(MERCREDI)
        gel.start()
        self.addCleanup(gel.stop)
        self.company = Company.objects.create(
            nom='CAD8 Solaire', slug=self.slug)
        CompanyProfile.objects.get_or_create(company=self.company)
        self.acteur = User.objects.create_user(
            username=f'{self.slug}-resp', password='x',
            role_legacy='responsable', company=self.company)
        self.lead = Lead.objects.create(
            company=self.company, nom='Karim', stage=stages.QUOTE_SENT,
            owner=self.acteur, telephone='+212661000801')
        client = Client.objects.create(
            company=self.company, nom='Karim',
            email=f'{self.slug}@example.com')
        self.devis = Devis.objects.create(
            company=self.company, reference=f'DEV-{self.slug}-0001',
            client=client, lead=self.lead, statut=Devis.Statut.ENVOYE,
            taux_tva=Decimal('20.00'), date_envoi=DEPART)
        gabarits = CadenceRelanceEtape.cadence_pour(
            self.company, 'apres_devis')
        gabarit, echeance = next(
            (g, e) for g, e in calculer_echeances_cadence(
                self.lead, 'apres_devis', DEPART, gabarits=gabarits)
            if g.ordre == 2)
        self.touche = RelanceEtape.objects.create(
            company=self.company, lead=self.lead, cadence='apres_devis',
            ordre=gabarit.ordre, due_at=echeance,
            due_date=echeance.astimezone(horaires.CASABLANCA).date(),
            canal=gabarit.canal, libelle=gabarit.libelle,
            template_cle=gabarit.template_cle or '', devis=self.devis,
            cadence_depart=DEPART)
        self.api = APIClient()
        self.api.credentials(
            HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(self.acteur)}')

    def _repondre(self, **corps):
        return self.api.post(
            f'/api/django/crm/relance-etapes/{self.touche.pk}/fait/',
            {'reponse': 'devis_modifie', **corps}, format='json')

    def _barreaux_ouverts(self):
        """Les touches après-devis ouvertes qui sont des BARREAUX du
        protocole — les gestes de visite (dont l'étape « devis modifié »)
        portent la même cadence sans en être."""
        return list(self.lead.relance_etapes.filter(
            cadence='apres_devis', statut=RelanceEtape.Statut.A_FAIRE,
        ).exclude(ordre__gte=VISITE_ORDRE_DEBRIEF - 1))


class DevisModifieTests(_Base):
    slug = 'cad8-base'

    def test_l_etape_devis_modifie_est_posee(self):
        resp = self._repondre()
        self.assertEqual(resp.status_code, 200, resp.data)
        etape = self.lead.relance_etapes.get(
            libelle=VISITE_DEVIS_LIBELLE, statut=RelanceEtape.Statut.A_FAIRE)
        self.assertEqual(etape.canal, RelanceEtape.Canal.APPEL)
        self.assertEqual(etape.devis_id, self.devis.pk)
        self.assertEqual(etape.due_date, datetime.date(2026, 9, 24))

    def test_aucune_touche_apres_devis_tant_que_le_nouveau_n_est_pas_envoye(
            self):
        self._repondre()
        self.assertEqual(self._barreaux_ouverts(), [])
        ouvertes = list(self.lead.relance_etapes.filter(
            statut=RelanceEtape.Statut.A_FAIRE).values_list(
                'libelle', flat=True))
        self.assertEqual(ouvertes, [VISITE_DEVIS_LIBELLE])

    def test_la_touche_porte_la_note_typee(self):
        self._repondre(note='Veut 8 panneaux au lieu de 10')
        self.touche.refresh_from_db()
        self.assertEqual(self.touche.statut, RelanceEtape.Statut.FAIT)
        self.assertEqual(self.touche.outcome, 'rappel')
        ligne = LeadActivity.objects.get(
            lead=self.lead, kind=LeadActivity.Kind.APPEL)
        self.assertIn('Demande un devis modifié', ligne.body)
        self.assertIn('Veut 8 panneaux au lieu de 10', ligne.body)

    def test_un_debrief_ouvert_est_renomme_jamais_double(self):
        demain = MERCREDI + datetime.timedelta(days=1)
        debrief = RelanceEtape.objects.create(
            company=self.company, lead=self.lead, cadence='apres_devis',
            ordre=VISITE_ORDRE_DEBRIEF, canal=RelanceEtape.Canal.APPEL,
            libelle=VISITE_DEBRIEF_LIBELLE, due_at=demain,
            due_date=demain.date())
        self._repondre()
        debrief.refresh_from_db()
        self.assertEqual(debrief.libelle, VISITE_DEVIS_LIBELLE)
        self.assertEqual(self.lead.relance_etapes.filter(
            ordre=VISITE_ORDRE_DEBRIEF).count(), 1)


class ContratPartageTests(_Base):
    slug = 'cad8-contrat'

    def test_la_reponse_a_la_forme_du_contrat(self):
        resp = self._repondre()
        self.assertEqual(resp.status_code, 200, resp.data)
        contrat = json.loads((CONTRATS / 'relance_etape_v2.json')
                             .read_text(encoding='utf-8'))
        self.assertEqual(set(resp.data) - {'prochaine_touche'},
                         set(contrat['exemple']['results'][0]))
        # La prochaine étape annoncée est celle du devis modifié (demain).
        self.assertEqual(resp.data['prochaine_touche']['due_date'],
                         '2026-09-24')
