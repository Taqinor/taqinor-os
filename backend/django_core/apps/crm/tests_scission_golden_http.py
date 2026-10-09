"""SPL71 — golden HTTP des écrans crm déplacés (capture seule).

RelanceEtapeViewSet + RelanceEtapeSerializer, la fiche lead, les clients, les
rendez-vous, les playbooks et les salles de vente sont des réponses JSON lues
par le cockpit et la fiche : les inventaires de SPL70 (routes, permissions,
champs) ne comparent pas ces RÉPONSES. Ce module rejoue une fixture
déterministe, horloge gelée (constante `GEL` de `tests_cockpit_gardes.py`,
2026-09-30 10:00 Africa/Casablanca) et compare UN json par appel sous
`golden/scission_crm_http/` :

* GET leads (liste, détail, historique, panneau-appel, kpi-cadences,
  mesure-cadence, kpi-premier-contact, visites, doublons), relance-etapes
  (liste, suivi, journal, controle, cadences-echues, kpi-adherence,
  mes-stats, chaine-commerciale), clients (liste, détail), appointments,
  playbooks, salles-vente ;
* POST relance-etapes/<id>/fait/, /sauter/, /reporter/ sur des étapes de la
  fixture.

Normalisation : ids -> ordinaux (par nom de clé, dans l'ordre de première
rencontre), ids bruts des textes masqués. Aucun mock de vue, de sélecteur ni
de service (seule l'horloge est gelée).

Règle : une tâche NON-SPL qui change légitimement une réponse capturée
re-capture ses seuls fichiers (`UPDATE_GOLDEN=1`) et le dit dans son commit ;
une tâche SPL ne re-capture JAMAIS. Capture :
`UPDATE_GOLDEN=1 python manage.py test apps.crm.tests_scission_golden_http`
(le test échoue tant que les json manquent).
"""
import datetime
import json
import os
import pathlib
import re

from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from authentication.models import Company
from testkit.time import frozen

from apps.crm import horaires, stages
from apps.crm.models import (
    Appointment, Client, Lead, LeadActivity, Playbook, RelanceEtape,
    SalleVente)
from apps.parametres.models import CompanyProfile

User = get_user_model()

_GOLDEN = pathlib.Path(__file__).resolve().parent / 'golden' / \
    'scission_crm_http'
GEL = datetime.datetime(2026, 9, 30, 10, 0, tzinfo=horaires.CASABLANCA)
BASE = '/api/django/crm/'
_MASQUE_IDS = re.compile(r'(#|lead=|/leads?/|/devis/|/clients?/|/etapes?/'
                         r'|/relance-etapes/|/appointments/|/playbooks/'
                         r'|/salles-vente/)\d+')
_CLES_ID = ('id', 'pk', 'lead', 'client', 'owner', 'etape', 'devis',
            'company', 'user', 'traite_par', 'responsable', 'commercial',
            'tiers')


#: valeurs aléatoires (jetons de lien public) : jamais comparées.
_CLES_SECRETES = ('token', 'lien_public', 'public_url', 'url_publique')


_MASQUE_REF = re.compile(r'\b([A-Z]{2,5})-\d+\b')


def _masquer(texte):
    """Ids bruts et numeros de reference (compteurs de sequence)."""
    return _MASQUE_REF.sub(r'\1-<n>', _MASQUE_IDS.sub(r'\1<id>', texte))


class _Ordinaux:
    """Remplace les ids par un ordinal (clé, première rencontre)."""

    def __init__(self):
        self.tables = {}

    def valeur(self, cle, v):
        if isinstance(v, bool):
            return v
        if isinstance(v, int) and (cle in _CLES_ID or cle.endswith(('_id', '_by'))):
            t = self.tables.setdefault(cle, {})
            return f'<{cle}#{t.setdefault(v, len(t) + 1)}>'
        if isinstance(v, str):
            if cle in _CLES_SECRETES:
                return '<secret>'
            return _masquer(v)
        if isinstance(v, dict):
            return {k: self.valeur(str(k), x) for k, x in v.items()}
        if isinstance(v, list):
            return [self.valeur(cle, x) for x in v]
        return v


def _ecarts(a, b, chemin=''):
    """Chemins (lisibles) où deux JSON diffèrent."""
    if type(a) is not type(b):
        return [f'{chemin}: {a!r} != {b!r}']
    if isinstance(a, dict):
        out = []
        for k in sorted(set(a) | set(b)):
            if k not in a or k not in b:
                out.append(f'{chemin}.{k}: clé absente d un côté')
            else:
                out += _ecarts(a[k], b[k], f'{chemin}.{k}')
        return out
    if isinstance(a, list):
        if len(a) != len(b):
            return [f'{chemin}: {len(a)} éléments != {len(b)}']
        return [e for i, (x, y) in enumerate(zip(a, b))
                for e in _ecarts(x, y, f'{chemin}[{i}]')]
    return [] if a == b else [f'{chemin}: {a!r} != {b!r}']


def _slug(texte):
    return re.sub(r'[^0-9A-Za-z]+', '_', texte).strip('_')


class ScissionGoldenHttpTests(TestCase):

    def setUp(self):
        gel = frozen(GEL)
        gel.start()
        self.addCleanup(gel.stop)
        self.ord = _Ordinaux()
        self.company = Company.objects.create(
            nom='Scission HTTP', slug='scission-http')
        CompanyProfile.objects.get_or_create(company=self.company)
        self.resp = User.objects.create_user(
            username='scission-http-resp', password='x',
            role_legacy='responsable', company=self.company,
            first_name='Meryem')
        self.comm = User.objects.create_user(
            username='scission-http-comm', password='x',
            company=self.company, first_name='Hamza')
        self.api = APIClient()
        self.api.credentials(
            HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(self.resp)}')
        self._fixture()

    def _lead(self, nom, tel, stage, owner, **kw):
        return Lead.objects.create(
            company=self.company, nom=nom, prenom='Test', stage=stage,
            owner=owner, telephone=tel, ville='Casablanca',
            email=f'{nom.lower()}@example.test', **kw)

    def _etape(self, lead, ordre, libelle, heures, canal='appel',
               cadence='contact', **kw):
        quand = GEL + datetime.timedelta(hours=heures)
        return RelanceEtape.objects.create(
            company=self.company, lead=lead, cadence=cadence, ordre=ordre,
            canal=canal, libelle=libelle, due_at=quand,
            due_date=quand.astimezone(horaires.CASABLANCA).date(),
            cadence_depart=GEL, **kw)

    def _fixture(self):
        self.lead1 = self._lead('Alaoui', '+212661003001', stages.NEW,
                                self.resp)
        self.lead2 = self._lead('Bennani', '+212661003002',
                                stages.CONTACTED, self.comm)
        self.lead3 = self._lead('Cherkaoui', '+212661003003',
                                stages.QUOTE_SENT, self.comm)
        # Doublon du lead 1 (même téléphone) pour GET leads/doublons.
        self._lead('Alaoui bis', '+212661003001', stages.NEW, self.resp)
        self.e1 = self._etape(self.lead1, 1, "Appel d'ouverture", 1)
        self.e2 = self._etape(self.lead1, 2, 'Message de suivi', 26,
                              canal='whatsapp',
                              template_cle='relance_whatsapp')
        self.e3 = self._etape(self.lead2, 1, 'Relance devis', 2)
        self.e4 = self._etape(self.lead3, 1, 'Relance proposition', -3)
        self.e_fait = self._etape(self.lead2, 2, 'Appel clos', -30)
        self.e_fait.statut = RelanceEtape.Statut.FAIT
        self.e_fait.outcome = 'joint'
        self.e_fait.traite_par = self.comm
        self.e_fait.traite_le = GEL - datetime.timedelta(hours=20)
        self.e_fait.save()
        LeadActivity.objects.create(
            company=self.company, lead=self.lead1, user=self.resp,
            kind=LeadActivity.Kind.NOTE, body='Premier échange golden.')
        self.client = Client.objects.create(
            company=self.company, nom='Client Golden',
            email='client.golden@example.test', telephone='+212661003010')
        self.rdv = Appointment.objects.create(
            company=self.company, lead=self.lead2,
            scheduled_at=GEL + datetime.timedelta(days=2),
            notes='Visite golden', created_by=self.resp)
        self.playbook = Playbook.objects.create(
            company=self.company, nom='Playbook golden')
        self.salle = SalleVente.objects.create(
            company=self.company, lead=self.lead3, titre='Salle golden',
            created_by=self.resp)

    # ---------------------------------------------------------------- appels
    def _appels(self):
        l1, l2 = self.lead1.pk, self.lead2.pk
        e1, e3, e4 = self.e1.pk, self.e3.pk, self.e4.pk
        appels = [
            ('GET', 'leads', f'{BASE}leads/', {}),
            ('GET', 'leads_detail', f'{BASE}leads/{l1}/', {}),
            ('GET', 'leads_historique', f'{BASE}leads/{l1}/historique/', {}),
            ('GET', 'leads_panneau_appel',
             f'{BASE}leads/{l1}/panneau-appel/', {}),
            ('GET', 'leads_kpi_cadences', f'{BASE}leads/kpi-cadences/', {}),
            ('GET', 'leads_mesure_cadence',
             f'{BASE}leads/mesure-cadence/', {}),
            ('GET', 'leads_kpi_premier_contact',
             f'{BASE}leads/kpi-premier-contact/', {}),
            ('GET', 'leads_visites', f'{BASE}leads/{l2}/visites/', {}),
            ('GET', 'leads_doublons', f'{BASE}leads/doublons/', {}),
            ('GET', 'relance_etapes', f'{BASE}relance-etapes/', {}),
            ('GET', 'relance_etapes_suivi',
             f'{BASE}relance-etapes/suivi/',
             {'date_debut': '2026-09-23', 'date_fin': '2026-09-30'}),
            ('GET', 'relance_etapes_journal',
             f'{BASE}relance-etapes/journal/', {'lead': l1}),
            ('GET', 'relance_etapes_controle',
             f'{BASE}relance-etapes/controle/', {}),
            ('GET', 'relance_etapes_cadences_echues',
             f'{BASE}relance-etapes/cadences-echues/', {'jours': 1}),
            ('GET', 'relance_etapes_kpi_adherence',
             f'{BASE}relance-etapes/kpi-adherence/', {}),
            ('GET', 'relance_etapes_mes_stats',
             f'{BASE}relance-etapes/mes-stats/', {}),
            ('GET', 'relance_etapes_chaine_commerciale',
             f'{BASE}relance-etapes/chaine-commerciale/', {}),
            ('GET', 'clients', f'{BASE}clients/', {}),
            ('GET', 'clients_detail',
             f'{BASE}clients/{self.client.pk}/', {}),
            ('GET', 'appointments', f'{BASE}appointments/', {}),
            ('GET', 'playbooks', f'{BASE}playbooks/', {}),
            ('GET', 'salles_vente', f'{BASE}salles-vente/', {}),
            ('POST', 'relance_etapes_fait',
             f'{BASE}relance-etapes/{e1}/fait/',
             {'note': 'Client joint', 'outcome': 'joint'}),
            ('POST', 'relance_etapes_sauter',
             f'{BASE}relance-etapes/{e4}/sauter/', {'note': 'Pas pertinent'}),
            ('POST', 'relance_etapes_reporter',
             f'{BASE}relance-etapes/{e3}/reporter/',
             {'rappel_le': '2026-10-08', 'rappel_heure': '10:00'}),
        ]
        return appels

    def _jouer(self, methode, url, donnees):
        if methode == 'GET':
            r = self.api.get(url, donnees)
        else:
            r = self.api.post(url, donnees, format='json')
        try:
            corps = json.loads(r.content.decode('utf-8')) if r.content \
                else None
        except ValueError:
            corps = r.content.decode('utf-8', 'replace')
        return r.status_code, corps

    def test_reponses_identiques_au_golden(self):
        capture = os.environ.get('UPDATE_GOLDEN') == '1'
        if capture:
            _GOLDEN.mkdir(parents=True, exist_ok=True)
        for methode, nom, url, donnees in self._appels():
            statut, corps = self._jouer(methode, url, donnees)
            instantane = json.loads(json.dumps({
                'methode': methode,
                'url': _masquer(url),
                'donnees': self.ord.valeur('donnees', donnees),
                'statut': statut,
                'corps': self.ord.valeur('corps', corps)},
                ensure_ascii=False, sort_keys=True))
            chemin = _GOLDEN / f'{methode}_{_slug(nom)}.json'
            if capture:
                with open(chemin, 'w', encoding='utf-8') as f:
                    json.dump(instantane, f, indent=1, ensure_ascii=False,
                              sort_keys=True)
                    f.write('\n')
            with self.subTest(appel=f'{methode} {nom}'):
                with open(chemin, encoding='utf-8') as f:
                    attendu = json.load(f)
                self.assertEqual(
                    instantane, attendu,
                    msg='\n'.join(_ecarts(instantane, attendu)[:15]))

    def test_les_appels_de_la_liste_couvrent_toutes_les_surfaces(self):
        noms = {nom for _m, nom, _u, _d in self._appels()}
        for attendu in ('leads', 'leads_historique', 'leads_panneau_appel',
                        'relance_etapes_suivi', 'clients', 'appointments',
                        'playbooks', 'salles_vente', 'relance_etapes_fait',
                        'relance_etapes_sauter', 'relance_etapes_reporter'):
            self.assertIn(attendu, noms)
