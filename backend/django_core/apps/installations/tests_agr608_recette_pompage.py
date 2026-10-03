"""AGR608 — modèle et endpoints de la recette POMPAGE (fiche structurée,
scopée société, verrouillée après PV signé).

Run :
    python manage.py test apps.installations.tests_agr608_recette_pompage -v2
"""
import itertools
import json
from pathlib import Path

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.utils import timezone
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from apps.crm.models import Client
from apps.installations.models import Installation, RecettePompage

User = get_user_model()
_seq = itertools.count(1)
BASE = '/api/django/installations'
CONTRATS = Path(__file__).resolve().parent / 'contract_samples'


def _contrat(nom):
    return json.loads((CONTRATS / f'{nom}.json').read_text(encoding='utf-8'))


def make_company():
    from authentication.models import Company
    n = next(_seq)
    company, _ = Company.objects.get_or_create(
        slug=f'agr608-co-{n}', defaults={'nom': f'AGR608 Co {n}'})
    return company


def make_user(company, role='responsable'):
    return User.objects.create_user(
        username=f'agr608-{next(_seq)}', password='x',
        role_legacy=role, company=company)


def auth(user):
    api = APIClient()
    api.credentials(HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(user)}')
    return api


def make_installation(company, type_installation='agricole'):
    n = next(_seq)
    client = Client.objects.create(
        company=company, nom='Client', prenom='AGR608',
        email=f'agr608-{company.id}-{n}@example.invalid')
    return Installation.objects.create(
        company=company, reference=f'CHT-AGR608-{n}', client=client,
        type_installation=type_installation)


class RecettePompageApiTests(TestCase):
    def setUp(self):
        self.company = make_company()
        self.user = make_user(self.company)
        self.api = auth(self.user)

    def _url(self, inst):
        return f'{BASE}/chantiers/{inst.id}/recette-pompage/'

    def test_get_sans_fiche_puis_creation_et_lecture(self):
        inst = make_installation(self.company)
        r = self.api.get(self._url(inst))
        self.assertEqual(r.status_code, 200, r.data)
        self.assertEqual(r.data, {'installation': inst.id, 'record': None})
        self.assertEqual(
            set(r.data), set(_contrat('recette_pompage')['exemple_vide']))
        r = self.api.post(self._url(inst), {}, format='json')
        self.assertEqual(r.status_code, 201, r.data)
        self.assertEqual(r.data['installation'], inst.id)
        self.assertEqual(r.data['record']['resultat'], 'en_cours')
        self.assertEqual(r.data['record']['cadre'], 'IEC 62253:2011')
        rec = RecettePompage.objects.get(installation=inst)
        self.assertEqual(rec.company_id, self.company.id)
        # Un 2e POST ne crée pas de doublon.
        r2 = self.api.post(self._url(inst), {}, format='json')
        self.assertEqual(r2.status_code, 200, r2.data)
        self.assertEqual(RecettePompage.objects.filter(
            installation=inst).count(), 1)
        r3 = self.api.get(self._url(inst))
        self.assertEqual(r3.data['record']['id'], rec.id)

    def test_company_jamais_lue_du_corps(self):
        autre = make_company()
        inst = make_installation(self.company)
        self.api.post(self._url(inst), {'company': autre.id}, format='json')
        rec = RecettePompage.objects.get(installation=inst)
        r = self.api.patch(f'{BASE}/recettes-pompage/{rec.id}/',
                           {'company': autre.id, 'hmt_mesuree_m': 50.5},
                           format='json')
        self.assertEqual(r.status_code, 200, r.data)
        rec.refresh_from_db()
        self.assertEqual(rec.company_id, self.company.id)
        self.assertEqual(rec.hmt_mesuree_m, 50.5)

    def test_chantier_autre_societe_404(self):
        autre = make_company()
        inst = make_installation(autre)
        self.assertEqual(self.api.get(self._url(inst)).status_code, 404)
        self.assertEqual(
            self.api.post(self._url(inst), {}, format='json').status_code, 404)
        rec = RecettePompage.objects.create(company=autre, installation=inst)
        r = self.api.patch(f'{BASE}/recettes-pompage/{rec.id}/',
                           {'hmt_mesuree_m': 10}, format='json')
        self.assertEqual(r.status_code, 404)

    def test_chantier_residentiel_400(self):
        inst = make_installation(self.company, 'residentiel')
        r = self.api.post(self._url(inst), {}, format='json')
        self.assertEqual(r.status_code, 400, r.data)
        self.assertIn('agricole', r.data['detail'])
        self.assertFalse(RecettePompage.objects.exists())

    def test_pv_signe_verrouille_la_fiche(self):
        inst = make_installation(self.company)
        self.api.post(self._url(inst), {}, format='json')
        rec = RecettePompage.objects.get(installation=inst)
        inst.signe_le = timezone.now()
        inst.save(update_fields=['signe_le'])
        r = self.api.patch(f'{BASE}/recettes-pompage/{rec.id}/',
                           {'debit_mesure_m3h': 12.5}, format='json')
        self.assertEqual(r.status_code, 400, r.data)
        self.assertIn('verrouillee', r.data)
        rec.refresh_from_db()
        self.assertIsNone(rec.debit_mesure_m3h)
        self.assertTrue(
            self.api.get(self._url(inst)).data['record']['verrouillee'])

    def test_sortie_conforme_au_contrat_partage(self):
        """Le test AFFIRME l'exemple committé (mêmes clés, mêmes types)."""
        contrat = _contrat('recette_pompage')
        exemple = contrat['exemple']['record']
        inst = make_installation(self.company)
        self.api.post(self._url(inst), {}, format='json')
        rec = RecettePompage.objects.get(installation=inst)
        corps = {
            cle: val for cle, val in exemple.items()
            if cle not in ('id', 'verrouillee', 'cadre', 'comparaison',
                           'vue_portail', 'technicien')}
        corps['technicien'] = self.user.id
        r = self.api.patch(f'{BASE}/recettes-pompage/{rec.id}/', corps,
                           format='json')
        self.assertEqual(r.status_code, 200, r.data)
        self.assertEqual(set(r.data), set(contrat['exemple']))
        record = r.data['record']
        self.assertEqual(set(record), set(exemple))

        def _meme_forme(servi, attendu, chemin):
            if attendu is None:
                return
            if isinstance(attendu, dict):
                self.assertIsInstance(servi, dict, chemin)
                self.assertEqual(set(servi), set(attendu), chemin)
                for k, v in attendu.items():
                    _meme_forme(servi[k], v, f'{chemin}.{k}')
            elif isinstance(attendu, list):
                self.assertIsInstance(servi, list, chemin)
            elif isinstance(attendu, bool):
                self.assertIsInstance(servi, bool, chemin)
            elif isinstance(attendu, (int, float)):
                if servi is not None:
                    self.assertIsInstance(servi, (int, float), chemin)
            else:
                if servi is not None:
                    self.assertIsInstance(servi, type(attendu), chemin)

        _meme_forme(record, exemple, 'record')
        for cle in ('hmt_mesuree_m', 'debit_mesure_m3h', 'tension_v',
                    'methode_debit', 'resultat', 'instrument_id'):
            self.assertEqual(record[cle], exemple[cle], cle)
        # La vue portail ne porte jamais l'instrument, le technicien ni un
        # prix.
        self.assertEqual(set(record['vue_portail']),
                         set(exemple['vue_portail']))
        for interdit in ('instrument_id', 'technicien', 'prix_achat'):
            self.assertNotIn(interdit, record['vue_portail'])
        self.assertNotIn('prix_achat', json.dumps(r.data))
        # Aucun verdict automatique : le seuil reste non saisi.
        self.assertIsNone(record['comparaison']['seuil_ecart_pct'])
        self.assertIsNone(record['comparaison']['hors_seuil'])

    def test_technicien_autre_societe_refuse(self):
        autre = make_company()
        etranger = make_user(autre)
        inst = make_installation(self.company)
        self.api.post(self._url(inst), {}, format='json')
        rec = RecettePompage.objects.get(installation=inst)
        r = self.api.patch(f'{BASE}/recettes-pompage/{rec.id}/',
                           {'technicien': etranger.id}, format='json')
        self.assertEqual(r.status_code, 400, r.data)
