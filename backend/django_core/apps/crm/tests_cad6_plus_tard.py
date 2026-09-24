"""CAD6 — la réponse « Plus tard — pas maintenant ».

Avant : « rappelez-moi après l'Aïd » n'avait que « À rappeler le… », qui
CONSOMMAIT un barreau et programmait le barreau scripté SUIVANT à la date
convenue — reporter de six semaines envoyait « Je classe ? » à un client qui
demandait seulement du temps. Le texte ``rappel_plus_tard`` existait et
n'était porté par aucun barreau.

Done : après « Plus tard », AUCUN barreau scripté n'est consommé et la reprise
se fait AU MÊME BARREAU à la date convenue (mécanique de veille de CAD26).
Contrat partagé : la réponse porte les clés de l'exemple committé
``relance_etape_v2.json`` (plus ``prochaine_touche``) et le texte proposé la
forme de ``relance_etape_message.json``.
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
from apps.crm.services import calculer_echeances_cadence
from apps.parametres.models import CompanyProfile
from apps.parametres.models_relance import CadenceRelanceEtape

User = get_user_model()

MERCREDI = datetime.datetime(2026, 9, 23, 10, 0, tzinfo=horaires.CASABLANCA)
#: « Après la rentrée » : mercredi 14 octobre 2026.
DATE_CONVENUE = '2026-10-14'

CONTRATS = Path(__file__).resolve().parent / 'contract_samples'


def _contrat(nom):
    return json.loads((CONTRATS / f'{nom}.json').read_text(encoding='utf-8'))


class _Base(TestCase):
    slug = 'cad6'

    def setUp(self):
        gel = frozen(MERCREDI)
        gel.start()
        self.addCleanup(gel.stop)
        self.company = Company.objects.create(
            nom='CAD6 Solaire', slug=self.slug)
        CompanyProfile.objects.get_or_create(company=self.company)
        self.acteur = User.objects.create_user(
            username=f'{self.slug}-resp', password='x',
            role_legacy='responsable', company=self.company)
        self.lead = Lead.objects.create(
            company=self.company, nom='Aziz', stage=stages.CONTACTED,
            owner=self.acteur, telephone='+212661000601',
            whatsapp='+212661000601')
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
        self.api = APIClient()
        self.api.credentials(
            HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(self.acteur)}')

    def _plus_tard(self, etape=None, **corps):
        corps.setdefault('rappel_le', DATE_CONVENUE)
        corps.setdefault('rappel_heure', '11:00')
        etape = etape or self.etape
        return self.api.post(
            f'/api/django/crm/relance-etapes/{etape.pk}/fait/',
            {'reponse': 'plus_tard', **corps}, format='json')


class PlusTardTests(_Base):
    slug = 'cad6-base'

    def test_aucun_barreau_scripte_n_est_consomme(self):
        resp = self._plus_tard()
        self.assertEqual(resp.status_code, 200, resp.data)
        self.assertFalse(self.lead.relance_etapes.filter(
            statut__in=(RelanceEtape.Statut.FAIT,
                        RelanceEtape.Statut.SAUTEE)).exists())
        # Aucun barreau n'est NÉ non plus : la touche est la seule.
        self.assertEqual(self.lead.relance_etapes.count(), 1)

    def test_la_reprise_se_fait_au_meme_barreau_a_la_date_convenue(self):
        self._plus_tard()
        self.etape.refresh_from_db()
        self.assertEqual(self.etape.statut, RelanceEtape.Statut.A_FAIRE)
        self.assertEqual(self.etape.ordre, 4)
        self.assertEqual(self.etape.due_date,
                         datetime.date.fromisoformat(DATE_CONVENUE))

    def test_la_reponse_du_client_est_tracee_et_typee(self):
        self._plus_tard(note='Après les travaux de la cuisine')
        ligne = LeadActivity.objects.get(
            lead=self.lead, kind=LeadActivity.Kind.APPEL)
        self.assertEqual(ligne.outcome, 'rappel')
        self.assertIn('Plus tard — pas maintenant', ligne.body)
        self.assertIn('reprise à cette même touche', ligne.body)
        self.assertIn('Après les travaux de la cuisine', ligne.body)

    def test_la_date_convenue_est_obligatoire_et_nommee(self):
        resp = self._plus_tard(rappel_le='', rappel_heure='')
        self.assertEqual(resp.status_code, 400)
        self.assertIn('« Rappeler le »', resp.data['erreurs']['rappel_le'])

    def test_une_date_passee_est_refusee(self):
        resp = self._plus_tard(rappel_le='2026-09-22')
        self.assertEqual(resp.status_code, 400)
        self.assertIn('rappel_le', resp.data['erreurs'])
        self.etape.refresh_from_db()
        self.assertEqual(self.etape.due_date,
                         self.etape.due_at.astimezone(
                             horaires.CASABLANCA).date())
        self.assertFalse(LeadActivity.objects.filter(
            lead=self.lead, kind=LeadActivity.Kind.APPEL).exists())

    def test_sur_une_etape_de_filet_la_reponse_est_refusee(self):
        filet = RelanceEtape.objects.create(
            company=self.company, lead=self.lead, cadence='generique',
            ordre=1, canal=RelanceEtape.Canal.APPEL,
            libelle='Préparer et envoyer le devis (ou fixer un rappel)',
            due_at=MERCREDI, due_date=MERCREDI.date())
        resp = self._plus_tard(etape=filet)
        self.assertEqual(resp.status_code, 400)
        self.assertIn('reponse', resp.data['erreurs'])


class ContratPartageTests(_Base):
    slug = 'cad6-contrat'

    def test_la_reponse_a_la_forme_du_contrat(self):
        resp = self._plus_tard()
        self.assertEqual(resp.status_code, 200, resp.data)
        attendu = set(_contrat('relance_etape_v2')['exemple']['results'][0])
        self.assertEqual(set(resp.data) - {'prochaine_touche'}, attendu)
        # La prochaine touche annoncée EST la même, à la date convenue.
        self.assertEqual(resp.data['prochaine_touche']['due_date'],
                         DATE_CONVENUE)

    def test_le_texte_rappel_plus_tard_est_propose(self):
        self._plus_tard()
        resp = self.api.get(
            f'/api/django/crm/relance-etapes/{self.etape.pk}/message/',
            {'cle': 'rappel_plus_tard'})
        self.assertEqual(resp.status_code, 200, resp.data)
        self.assertEqual(set(resp.data),
                         set(_contrat('relance_etape_message')['exemple']))
        # Les crochets restent des crochets : jamais un jour inventé.
        self.assertIn('[jour]', resp.data['message'])
