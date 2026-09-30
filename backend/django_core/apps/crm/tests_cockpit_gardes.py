"""COCKPIT-CONTRÔLE B4 — deux gardes.

(a) ``sauter/`` sur une TÂCHE (préparer le devis, décider la suite, planifier
    la visite, devis modifié, question de prix) → 400 ``{"erreurs":
    {"etape": …}}`` et RIEN n'est écrit. L'écran masquait le bouton ; le
    serveur, lui, laissait tout passer.
(b) La note écrite par un REPORT (« Rappel demandé le … — touche « … »
    reportée. ») et par une MISE EN VEILLE ne pose plus
    ``first_contacted_at`` — même patron que CAD131 (la reconnaissance vit
    dans ``services``, là où la note est écrite ; le récepteur la consulte).
    Reporter la toute première touche d'un lead neuf ne l'horodate pas et
    n'éteint pas l'escalade.

Horloge FIXE : mercredi 30/09/2026, 10 h à Casablanca (jour ouvré).
"""
import datetime
import itertools

from django.contrib.auth import get_user_model
from django.test import SimpleTestCase, TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from authentication.models import Company
from testkit.time import frozen

from apps.crm import horaires, services, stages
from apps.crm import suite_touche as st
from apps.crm.cadence_config import (
    CLE_DECIDER_SUITE, CLE_DEVIS, CLE_DEVIS_MODIFIE, CLE_PLANIFIER)
from apps.crm.models import Lead, LeadActivity, RelanceEtape
from apps.crm.views import (
    MESSAGE_ETAPE_DEJA_TRAITEE, MESSAGE_TACHE_NON_SAUTABLE)
from apps.parametres.models import CompanyProfile

User = get_user_model()

GEL = datetime.datetime(2026, 9, 30, 10, 0, tzinfo=horaires.CASABLANCA)
URL = '/api/django/crm/relance-etapes/'
A_FAIRE = RelanceEtape.Statut.A_FAIRE

#: Une étape de chaque TYPE-TÂCHE de la table : (cadence, clé, libellé).
TACHES = (
    ('generique', CLE_DEVIS, 'Préparer le devis'),
    ('generique', CLE_DECIDER_SUITE, 'Décider la suite'),
    (services.VISITE_CADENCE, CLE_PLANIFIER, 'Planifier la visite'),
    (services.VISITE_CADENCE, CLE_DEVIS_MODIFIE, 'Devis modifié'),
    ('generique', '', services.QUESTION_PRIX_LIBELLE),
)

_seq = itertools.count(1)


class _Base(TestCase):

    def setUp(self):
        gel = frozen(GEL)
        gel.start()
        self.addCleanup(gel.stop)
        n = next(_seq)
        self.n = n
        self.company = Company.objects.create(
            nom=f'Cockpit gardes {n}', slug=f'cockpit-gardes-{n}')
        CompanyProfile.objects.get_or_create(company=self.company)
        self.acteur = User.objects.create_user(
            username=f'cockpit-gardes-resp-{n}', password='x',
            role_legacy='responsable', company=self.company)
        self.api = APIClient()
        self.api.credentials(
            HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(self.acteur)}')
        self._tel = itertools.count(1)

    def _lead(self, **champs):
        valeurs = {
            'company': self.company, 'nom': f'Prospect gardes {self.n}',
            'stage': stages.CONTACTED, 'owner': self.acteur,
            'telephone': f'+2126617{self.n:03d}{next(self._tel):02d}'}
        valeurs.update(champs)
        return Lead.objects.create(**valeurs)

    def _etape(self, lead, *, cadence='contact', cle='', libelle='Appel',
               canal=RelanceEtape.Canal.APPEL, ordre=2, heures=1, **champs):
        quand = GEL + datetime.timedelta(hours=heures)
        return RelanceEtape.objects.create(
            company=self.company, lead=lead, cadence=cadence, ordre=ordre,
            canal=canal, cle=cle, libelle=libelle, due_at=quand,
            due_date=quand.astimezone(horaires.CASABLANCA).date(),
            cadence_depart=GEL, **champs)


class SauterUneTacheTests(_Base):

    def test_chaque_tache_est_refusee_et_rien_n_est_ecrit(self):
        for cadence, cle, libelle in TACHES:
            lead = self._lead()
            etape = self._etape(lead, cadence=cadence, cle=cle,
                                libelle=libelle)
            self.assertTrue(st.est_tache(etape))
            activites_avant = LeadActivity.objects.filter(lead=lead).count()
            with self.subTest(cle=cle, libelle=libelle):
                resp = self.api.post(f'{URL}{etape.pk}/sauter/',
                                     {'note': 'essai'}, format='json')
                self.assertEqual(resp.status_code, 400, resp.data)
                self.assertEqual(resp.data,
                                 {'erreurs': {
                                     'etape': MESSAGE_TACHE_NON_SAUTABLE}})
                etape.refresh_from_db()
                self.assertEqual(etape.statut, A_FAIRE)
                self.assertIsNone(etape.traite_par)
                self.assertIsNone(etape.traite_le)
                self.assertEqual(etape.note, '')
                self.assertEqual(
                    LeadActivity.objects.filter(lead=lead).count(),
                    activites_avant)
                self.assertFalse(
                    lead.relance_etapes.exclude(pk=etape.pk).exists())

    def test_une_touche_du_protocole_se_saute_toujours(self):
        etape = self._etape(self._lead())
        resp = self.api.post(f'{URL}{etape.pk}/sauter/', {'note': ''},
                             format='json')
        self.assertEqual(resp.status_code, 200, resp.data)
        self.assertEqual(resp.data['statut'], RelanceEtape.Statut.SAUTEE)

    def test_deja_traitee_prime_sur_le_refus_de_tache(self):
        lead = self._lead()
        etape = self._etape(lead, cadence='generique', cle=CLE_DEVIS,
                            libelle='Préparer le devis',
                            statut=RelanceEtape.Statut.FAIT,
                            traite_le=GEL, traite_par=self.acteur)
        resp = self.api.post(f'{URL}{etape.pk}/sauter/', {'note': ''},
                             format='json')
        self.assertEqual(resp.status_code, 400, resp.data)
        self.assertEqual(resp.data['erreurs']['etape'],
                         MESSAGE_ETAPE_DEJA_TRAITEE)


class ReconnaissanceNoteDeReportTests(SimpleTestCase):
    """La règle vit là où la note est ÉCRITE — jamais un texte deviné."""

    def _note(self, corps, kind=LeadActivity.Kind.NOTE):
        return LeadActivity(kind=kind, body=corps)

    def test_la_note_d_un_report(self):
        corps = (services.PREFIXE_NOTE_REPORT
                 + '01/10/2026 à 09:00 — touche « Appel »'
                 + services.FIN_NOTE_REPORT)
        self.assertEqual(
            corps,
            'Rappel demandé le 01/10/2026 à 09:00 — touche « Appel » '
            'reportée.')
        self.assertTrue(services.est_note_de_report(self._note(corps)))

    def test_les_deux_notes_de_veille(self):
        for corps in ('Mise en veille jusqu’au 12/10/2026 à la demande du '
                      'client — la cadence reprendra à la touche « Appel ».',
                      'Mise en veille demandée jusqu’au 12/12/2026 : plus '
                      'd’un mois d’attente.'):
            with self.subTest(corps=corps):
                self.assertTrue(corps.startswith(services.PREFIXE_NOTE_VEILLE))
                self.assertTrue(
                    services.est_note_de_report(self._note(corps)))

    def test_une_note_ordinaire_reste_un_contact(self):
        for corps in ('Appelé, pas de réponse',
                      'Rappel demandé par le client : la prochaine touche '
                      'est ramenée au 30/09/2026 à 10:00.'):
            with self.subTest(corps=corps):
                self.assertFalse(
                    services.est_note_de_report(self._note(corps)))

    def test_une_ligne_typee_n_est_jamais_une_note_de_report(self):
        corps = services.PREFIXE_NOTE_VEILLE + 'jusqu’au 12/10/2026'
        self.assertFalse(services.est_note_de_report(
            self._note(corps, kind=LeadActivity.Kind.APPEL)))
        self.assertFalse(services.est_note_de_report(None))


class ReportNePosePasLePremierContactTests(_Base):

    def setUp(self):
        super().setUp()
        self.lead = self._lead(stage=stages.NEW)
        self.touche = self._etape(self.lead, ordre=1,
                                  canal=RelanceEtape.Canal.WHATSAPP,
                                  libelle="Message d'identité")

    def _toujours_escalade(self):
        """Mêmes critères que ``escalader_premier_contact`` (CAD31) : le lead
        reste visé tant qu'il n'est pas horodaté."""
        self.lead.refresh_from_db()
        self.assertIsNone(self.lead.first_contacted_at)
        self.assertEqual(self.lead.stage, stages.NEW)
        candidats = Lead.objects.filter(
            company=self.company, first_contacted_at__isnull=True,
            perdu=False, is_archived=False,
        ).exclude(source=Lead.Source.ODOO_IMPORT_TEST).exclude(
            stage__in=[stages.SIGNED, stages.COLD])
        self.assertIn(self.lead, list(candidats))

    def _jour(self, jours):
        return (GEL + datetime.timedelta(days=jours)).date().isoformat()

    def test_reporter_la_premiere_touche_ne_l_horodate_pas(self):
        resp = self.api.post(
            f'{URL}{self.touche.pk}/reporter/',
            {'rappel_le': self._jour(1), 'rappel_heure': '11:00'},
            format='json')
        self.assertEqual(resp.status_code, 200, resp.data)
        self.assertTrue(LeadActivity.objects.filter(
            lead=self.lead,
            body__startswith=services.PREFIXE_NOTE_REPORT).exists())
        self._toujours_escalade()

    def test_mettre_en_veille_ne_l_horodate_pas(self):
        resp = self.api.post(
            f'{URL}{self.touche.pk}/reporter/',
            {'rappel_le': self._jour(12), 'rappel_heure': '11:00',
             'mode': 'veille'}, format='json')
        self.assertEqual(resp.status_code, 200, resp.data)
        self.assertTrue(LeadActivity.objects.filter(
            lead=self.lead,
            body__startswith=services.PREFIXE_NOTE_VEILLE).exists())
        self._toujours_escalade()

    def test_la_date_de_relance_de_la_fiche_ne_l_horodate_pas(self):
        resp = self.api.patch(
            f'/api/django/crm/leads/{self.lead.pk}/',
            {'relance_date': self._jour(5)}, format='json')
        self.assertEqual(resp.status_code, 200, resp.data)
        self._toujours_escalade()

    def test_un_vrai_contact_horodate_toujours(self):
        """Témoin : la touche FAITE (un message réellement envoyé) reste une
        tentative — MRY19/CAD131 ne sont pas défaits."""
        services.marquer_etape_relance(
            self.touche, self.acteur, RelanceEtape.Statut.FAIT)
        self.lead.refresh_from_db()
        self.assertIsNotNone(self.lead.first_contacted_at)
