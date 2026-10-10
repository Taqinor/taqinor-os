"""SPL71 — golden HTTP des écrans crm déplacés (capture seule, aucun déplacement).

Les inventaires de SPL70 (`tests_scission_golden.py`) comparent des surfaces
statiques ; aucun ne compare les RÉPONSES JSON lues par le cockpit des
relances, la fiche lead, les clients, les rendez-vous, les playbooks et les
salles de vente. Ce module rejoue ces appels sur une fixture déterministe et
écrit UN json PAR APPEL sous `golden/scission_crm_http/` :
`{"appel": "GET leads", "statut": 200, "corps": …}`.

Déterminisme :
- horloge gelée sur `GEL` (mercredi 30/09/2026 10 h Africa/Casablanca, la
  constante de `tests_cockpit_gardes.py`) — seule l'horloge est gelée, aucune
  vue, aucun sélecteur ni service crm n'est remplacé ;
- noms, téléphones et dates fixes ;
- normalisation : identifiants remappés dans l'ordre de création de la
  fixture (`lead#1`, `etape#2`…), horodatages automatiques masqués, jeton de
  la salle de vente masqué.

Règle : une tâche NON-SPL qui change légitimement une réponse re-capture ses
seuls fichiers (`UPDATE_GOLDEN=1`) et le dit dans son commit ; une tâche SPL ne
re-capture JAMAIS. Un json manquant en mode normal FAIT ÉCHOUER le test.

Capture : `UPDATE_GOLDEN=1 python manage.py test apps.crm.tests_scission_golden_http`
(`scripts/test-backend.ps1 -RestoreDb -Modules "apps.crm.tests_scission_golden_http"`).
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
    Appointment, Client, Lead, Playbook, PlaybookEtape, RelanceEtape,
    SalleVente)
from apps.parametres.models import CompanyProfile

User = get_user_model()

GEL = datetime.datetime(2026, 9, 30, 10, 0, tzinfo=horaires.CASABLANCA)
BASE = '/api/django/crm/'
_GOLDEN = pathlib.Path(__file__).resolve().parent / 'golden' / 'scission_crm_http'
_CAPTURE = os.environ.get('UPDATE_GOLDEN') == '1'
_MASQUE = '<masque>'

#: Clés dont la valeur est un horodatage posé par le serveur (auto_now*).
_CLES_HORODATAGE = frozenset({
    'created_at', 'updated_at', 'date_creation', 'date_modification',
    'created', 'modified'})
#: Clé -> famille d'identifiants (voir `_Fixture.familles`).
_FAMILLE_PAR_CLE = {
    'lead': 'lead', 'lead_id': 'lead', 'client': 'client',
    'client_id': 'client', 'etape': 'etape', 'etape_id': 'etape',
    'owner': 'user', 'owner_id': 'user', 'assigned_to': 'user',
    'responsable': 'user', 'user': 'user', 'created_by': 'user',
    'traite_par': 'user', 'playbook': 'playbook',
    'playbook_id': 'playbook'}
_CLES_ID = {'id', 'pk'}


class _Fixture:
    """Table pk -> étiquette stable, par famille, dans l'ordre de création."""

    def __init__(self):
        self.familles = {}

    def noter(self, famille, objet):
        table = self.familles.setdefault(famille, {})
        table[objet.pk] = f'{famille}#{len(table) + 1}'
        return objet


class _Normaliseur:
    def __init__(self, fixture, defaut, secrets):
        self.fixture = fixture
        self.defaut = defaut
        self.secrets = [s for s in secrets if s]
        self.vus = {}

    def _etiquette(self, famille, valeur):
        table = self.fixture.familles.get(famille, {})
        if valeur in table:
            return table[valeur]
        vus = self.vus.setdefault(famille, {})
        if valeur not in vus:
            vus[valeur] = f'{famille}?#{len(vus) + 1}'
        return vus[valeur]

    def __call__(self, valeur, cle=None):
        if isinstance(valeur, dict):
            return {k: self(v, k) for k, v in valeur.items()}
        if isinstance(valeur, list):
            return [self(v, cle) for v in valeur]
        if cle in _CLES_HORODATAGE and valeur is not None:
            return _MASQUE
        if cle == 'token' and valeur:
            return _MASQUE
        if isinstance(valeur, str):
            for secret in self.secrets:
                valeur = valeur.replace(secret, _MASQUE)
            return valeur
        if isinstance(valeur, int) and not isinstance(valeur, bool):
            if cle in _CLES_ID:
                return self._etiquette(self.defaut, valeur)
            if cle in _FAMILLE_PAR_CLE:
                return self._etiquette(_FAMILLE_PAR_CLE[cle], valeur)
        return valeur


def _nom_fichier(libelle):
    return re.sub(r'[^0-9A-Za-z_.-]+', '_', libelle).strip('_') + '.json'


def _ecrire(nom, contenu):
    _GOLDEN.mkdir(parents=True, exist_ok=True)
    with open(_GOLDEN / nom, 'w', encoding='utf-8') as f:
        json.dump(contenu, f, indent=1, ensure_ascii=False, sort_keys=True)
        f.write('\n')


def _lire(nom):
    with open(_GOLDEN / nom, encoding='utf-8') as f:
        return json.load(f)


class ScissionGoldenHttpTests(TestCase):

    def setUp(self):
        gel = frozen(GEL)
        gel.start()
        self.addCleanup(gel.stop)
        self.fx = _Fixture()
        self.company = Company.objects.create(
            nom='Golden HTTP crm', slug='golden-http-crm')
        CompanyProfile.objects.get_or_create(company=self.company)
        self.resp = self.fx.noter('user', User.objects.create_user(
            username='golden-http-resp', password='x',
            role_legacy='responsable', company=self.company))
        self.commerciale = self.fx.noter('user', User.objects.create_user(
            username='golden-http-comm', password='x',
            role_legacy='commercial', company=self.company))
        self.api = APIClient()
        self.api.credentials(
            HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(self.resp)}')

        def lead(i, nom, stage, owner):
            return self.fx.noter('lead', Lead.objects.create(
                company=self.company, nom=nom, stage=stage, owner=owner,
                telephone=f'+212661000{i:03d}'))

        self.lead1 = lead(1, 'Prospect Golden Un', stages.NEW, self.resp)
        self.lead2 = lead(
            2, 'Prospect Golden Deux', stages.CONTACTED, self.commerciale)
        self.lead3 = lead(
            3, 'Prospect Golden Trois', stages.QUOTE_SENT, self.commerciale)

        self.etapes = []
        for i, (lead_, libelle) in enumerate((
                (self.lead1, 'Premier appel'),
                (self.lead2, 'Appel de suite'),
                (self.lead2, 'Appel à reporter'),
                (self.lead3, 'Appel à sauter'),
                (self.lead3, 'Appel de relance'))):
            quand = GEL + datetime.timedelta(hours=i + 1)
            self.etapes.append(self.fx.noter('etape', (
                RelanceEtape.objects.create(
                    company=self.company, lead=lead_, cadence='contact',
                    ordre=i + 1, canal=RelanceEtape.Canal.APPEL, cle='',
                    libelle=libelle, due_at=quand,
                    due_date=quand.astimezone(horaires.CASABLANCA).date(),
                    cadence_depart=GEL))))

        self.client_ = self.fx.noter('client', Client.objects.create(
            company=self.company, nom='Client Golden', prenom='Un',
            email='client.golden@example.test', telephone='+212661999001',
            adresse='1 rue du Golden, Casablanca'))
        self.fx.noter('rdv', Appointment.objects.create(
            company=self.company, lead=self.lead2,
            scheduled_at=GEL + datetime.timedelta(days=2)))
        self.playbook = self.fx.noter('playbook', Playbook.objects.create(
            company=self.company, nom='Playbook Golden'))
        PlaybookEtape.objects.create(
            playbook=self.playbook, stage=stages.NEW, ordre=1)
        self.salle = self.fx.noter('salle', SalleVente.objects.create(
            company=self.company, lead=self.lead3, titre='Salle Golden',
            created_by=self.resp))

    def _appels(self):
        """(libellé, méthode, chemin, famille de l'`id` racine, corps)."""
        l1, l2 = self.lead1.pk, self.lead2.pk
        e = [x.pk for x in self.etapes]
        periode = 'date_debut=2026-09-28&date_fin=2026-10-04'
        gets = [
            ('GET leads', 'leads/', 'lead'),
            ('GET leads detail', f'leads/{l2}/', 'lead'),
            ('GET leads historique', f'leads/{l2}/historique/', 'lead'),
            ('GET leads panneau-appel', f'leads/{l2}/panneau-appel/', 'lead'),
            ('GET leads kpi-cadences', 'leads/kpi-cadences/', 'lead'),
            ('GET leads mesure-cadence', 'leads/mesure-cadence/', 'lead'),
            ('GET leads kpi-premier-contact',
             'leads/kpi-premier-contact/', 'lead'),
            ('GET leads visites', f'leads/{l1}/visites/', 'lead'),
            ('GET leads doublons', 'leads/doublons/', 'lead'),
            ('GET relance-etapes', 'relance-etapes/', 'etape'),
            ('GET relance-etapes suivi',
             f'relance-etapes/suivi/?{periode}', 'etape'),
            ('GET relance-etapes journal',
             f'relance-etapes/journal/?lead={l2}', 'etape'),
            ('GET relance-etapes controle',
             'relance-etapes/controle/?jours=7', 'etape'),
            ('GET relance-etapes cadences-echues',
             'relance-etapes/cadences-echues/', 'etape'),
            ('GET relance-etapes kpi-adherence',
             'relance-etapes/kpi-adherence/', 'etape'),
            ('GET relance-etapes mes-stats',
             'relance-etapes/mes-stats/', 'etape'),
            ('GET relance-etapes chaine-commerciale',
             'relance-etapes/chaine-commerciale/', 'etape'),
            ('GET clients', 'clients/', 'client'),
            ('GET clients detail', f'clients/{self.client_.pk}/', 'client'),
            ('GET appointments', 'appointments/', 'rdv'),
            ('GET playbooks', 'playbooks/', 'playbook'),
            ('GET salles-vente', 'salles-vente/', 'salle'),
        ]
        # Les écritures viennent APRÈS les lectures (elles changent la file).
        posts = [
            ('POST relance-etapes fait',
             f'relance-etapes/{e[1]}/fait/', 'etape', {}),
            ('POST relance-etapes sauter',
             f'relance-etapes/{e[3]}/sauter/', 'etape',
             {'note': 'sauté pour le golden'}),
            ('POST relance-etapes reporter',
             f'relance-etapes/{e[2]}/reporter/', 'etape',
             {'mode': 'decaler', 'note': 'report golden',
              'due_at': '2026-10-02T10:00:00+01:00'}),
        ]
        return ([(n, 'get', p, f, None) for n, p, f in gets]
                + [(n, 'post', p, f, corps) for n, p, f, corps in posts])

    def _jouer(self, methode, chemin, corps):
        if methode == 'get':
            return self.api.get(BASE + chemin)
        return self.api.post(BASE + chemin, corps, format='json')

    def _reponse_normalisee(self, resp, famille):
        try:
            corps = (json.loads(resp.content.decode('utf-8'))
                     if resp.content else None)
        except ValueError:
            corps = {'brut': resp.content.decode('utf-8', 'replace')}
        norm = _Normaliseur(self.fx, famille, [self.salle.token])
        return {'statut': resp.status_code, 'corps': norm(corps)}

    def test_golden_http(self):
        appels = self._appels()
        attendus = {_nom_fichier(a[0]) for a in appels}
        if not _CAPTURE:
            manquants = sorted(
                n for n in attendus if not (_GOLDEN / n).is_file())
            self.assertFalse(
                manquants,
                'Golden HTTP absent — capturer avec UPDATE_GOLDEN=1 '
                '(python manage.py test apps.crm.tests_scission_golden_http) '
                f': {manquants}')
        for libelle, methode, chemin, famille, corps in appels:
            nom = _nom_fichier(libelle)
            with self.subTest(appel=libelle):
                resp = self._jouer(methode, chemin, corps)
                # Le libellé (jamais l'URL) : aucun id brut dans le json.
                obtenu = {'appel': libelle,
                          **self._reponse_normalisee(resp, famille)}
                if _CAPTURE:
                    _ecrire(nom, obtenu)
                else:
                    self.assertEqual(obtenu, _lire(nom), libelle)
        if not _CAPTURE:
            en_trop = sorted(
                p.name for p in _GOLDEN.glob('*.json')
                if p.name not in attendus)
            self.assertFalse(en_trop, f'Golden HTTP orphelin : {en_trop}')
