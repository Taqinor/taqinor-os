"""APRF6 (C-APRF-003) — la conception électrique (``electrical_design``) est
absente de la représentation LISTE des devis (``GET /ventes/devis/``) et
servie identique, octet pour octet, au détail (``GET /ventes/devis/<id>/``).

Test-du-test : remettre le champ en liste ⇒ ``test_liste_sans_conception``
échoue ; le retirer aussi du détail ⇒ ``test_detail_avec_conception``
échoue. Réponses HTTP réelles, aucun mock.
"""
import json
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient

from authentication.models import Company
from apps.crm.models import Client
from apps.ventes.models import Devis

User = get_user_model()
URL = '/api/django/ventes/devis/'

CONCEPTION = {
    'version': 1,
    'chaines': [{'mppt': 1, 'panneaux': 9, 'voc_v': 412.5}],
    'protections': {'dc': 'Fusible 15 A', 'ac': 'Disjoncteur 32 A'},
    'cables': [{'troncon': 'DC', 'section_mm2': 6, 'longueur_m': 25}],
}


class ListeSansConceptionTests(TestCase):
    def setUp(self):
        self.company = Company.objects.create(nom='APRF6 SARL')
        self.user = User.objects.create_user(
            username='aprf6_admin', password='x', role_legacy='admin',
            company=self.company)
        self.api = APIClient()
        self.api.force_authenticate(user=self.user)
        client = Client.objects.create(
            company=self.company, nom='Client', prenom='APRF6')
        self.devis = Devis.objects.create(
            company=self.company, reference='DEV-APRF6-0001', client=client,
            created_by=self.user, taux_tva=Decimal('20'),
            electrical_design=CONCEPTION,
            roof_layout={'result': {'panels': 9}})

    def _ligne_liste(self):
        resp = self.api.get(URL)
        self.assertEqual(resp.status_code, 200)
        data = resp.data
        lignes = data.get('results', data) if isinstance(data, dict) else data
        return next(r for r in lignes if r['id'] == self.devis.pk)

    def test_liste_sans_conception(self):
        ligne = self._ligne_liste()
        self.assertNotIn('electrical_design', ligne)
        # T4-X4-005 — le calepinage ne voyage plus en liste : la ligne dit
        # seulement qu'il existe (DevisRow.jsx lit ``a_plan_toiture``).
        self.assertNotIn('roof_layout', ligne)
        self.assertTrue(ligne['a_plan_toiture'])

    def test_detail_avec_conception(self):
        resp = self.api.get('%s%s/' % (URL, self.devis.pk))
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(
            json.dumps(resp.data['electrical_design'], sort_keys=True),
            json.dumps(CONCEPTION, sort_keys=True))

    def test_liste_puis_detail_conception_intacte(self):
        # CLAUSE PERSISTANCE — ouvrir le devis après la liste.
        self._ligne_liste()
        self.devis.refresh_from_db()
        self.assertEqual(self.devis.electrical_design, CONCEPTION)
        resp = self.api.get('%s%s/' % (URL, self.devis.pk))
        self.assertEqual(resp.data['electrical_design'], CONCEPTION)


# ---------------------------------------------------------------------------
# T4-X4-005 (S2) — sur une copie de la production, la liste des devis servait
# 52 à 82 Ko PAR devis (25 devis = 2,0 Mo) : le bloc d'étude ``etude_params``
# (profil horaire de 8 760 valeurs, simulation), les lignes et le calepinage
# voyageaient sur chaque ligne de liste. La LISTE sert une forme légère ; le
# DÉTAIL (et ``?forme=complete``, envoyé par le seul dialogue « Signé ») garde
# la forme complète. Réponses HTTP réelles, comptage des requêtes réel.
# ---------------------------------------------------------------------------
def _etude_reelle(i):
    """Un bloc d'étude de la taille de ceux de la production (≈ 60 Ko)."""
    return {
        'recommended_option': 'Avec batterie',
        'gamme': {'nom': 'Essentielle'},
        'scenario': 'Avec batterie',
        'profil_horaire': [round(0.31 + ((h + i) % 24) / 97, 4)
                           for h in range(8760)],
        'simulation': {'mensuel': [
            {'mois': m, 'production_kwh': 612.5 + m, 'pertes_pct': 14.2}
            for m in range(1, 13)], 'p50': 7420.4, 'p90': 6890.1},
    }


class ListeLegereT4X4005Tests(TestCase):
    """Le budget : une page de 25 devis pèse moins de 100 Ko, avec un nombre
    de requêtes qui ne grandit pas avec le nombre de devis."""

    def setUp(self):
        from apps.ventes.models import LigneDevis
        self.company = Company.objects.create(nom='T4X4005 SARL')
        self.admin = User.objects.create_user(
            username='t4x4005_admin', password='x', role_legacy='admin',
            company=self.company)
        self.commercial = User.objects.create_user(
            username='t4x4005_com', password='x', role_legacy='commercial',
            company=self.company)
        self.api = APIClient()
        self.api.force_authenticate(user=self.admin)
        self.client_obj = Client.objects.create(
            company=self.company, nom='Benali', prenom='Karim')
        self.autre_client = Client.objects.create(
            company=self.company, nom='Zerouali', prenom='Nadia')
        self._ligne = LigneDevis
        self.n = 0

    def _creer(self, nombre, client=None, created_by=None, **extra):
        crees = []
        for _ in range(nombre):
            self.n += 1
            d = Devis.objects.create(
                company=self.company, reference='DEV-T4X4-%04d' % self.n,
                client=client or self.client_obj,
                created_by=created_by or self.admin,
                taux_tva=Decimal('20'), etude_params=_etude_reelle(self.n),
                roof_layout={'version': 1, 'zones': [
                    {'id': 'z%d' % k, 'vertices': [[k, k + 0.5]] * 40}
                    for k in range(6)]},
                electrical_design=CONCEPTION, marge_snapshot=Decimal('23.5'),
                **extra)
            for k in range(12):
                self._ligne.objects.create(
                    devis=d, designation='Panneau 580 Wc %d' % k,
                    quantite=Decimal('2'), prix_unitaire=Decimal('1450'))
            crees.append(d)
        return crees

    def _page(self, api=None, **params):
        params.setdefault('page_size', 25)
        resp = (api or self.api).get(URL, params)
        self.assertEqual(resp.status_code, 200, getattr(resp, 'data', resp))
        return resp

    def test_page_de_25_sous_100_ko(self):
        self._creer(25)
        complete = self._page(forme='complete')
        legere = self._page()
        self.assertEqual(len(legere.json()['results']), 25)
        print('\nT4-X4-005 octets page 25 : complete=%d legere=%d' % (
            len(complete.content), len(legere.content)))
        self.assertLess(len(legere.content), 100_000)

    def test_nombre_de_requetes_constant_et_borne(self):
        from django.db import connection
        from django.test.utils import CaptureQueriesContext
        self._creer(5)
        self._page()  # premier appel : profils et réglages créés une fois
        with CaptureQueriesContext(connection) as a_cinq:
            self._page()
        self._creer(20)
        with CaptureQueriesContext(connection) as a_25:
            self._page()
        print('\nT4-X4-005 requetes : 5 devis=%d 25 devis=%d' % (
            len(a_cinq.captured_queries), len(a_25.captured_queries)))
        self.assertEqual(len(a_cinq.captured_queries),
                         len(a_25.captured_queries))
        self.assertLessEqual(len(a_25.captured_queries), 40)

    def test_forme_legere_dit_ce_que_la_ligne_montre(self):
        self._creer(1)
        ligne = self._page().json()['results'][0]
        for lourd in ('etude_params', 'lignes', 'roof_layout',
                      'pdf_render_meta', 'offres_tailles_config', 'overrides',
                      'clauses_appliquees', 'custom_data', 'electrical_design'):
            self.assertNotIn(lourd, ligne)
        self.assertTrue(ligne['detail_partiel'])
        self.assertTrue(ligne['a_plan_toiture'])
        self.assertEqual(ligne['etude_resume'], {
            'recommended_option': 'Avec batterie', 'gamme_nom': 'Essentielle',
            'a_etude': True})
        for lu in ('reference', 'client_nom', 'statut', 'total_affiche',
                   'nb_options', 'solde', 'vente', 'is_expired',
                   'date_expiration', 'bon_commande_etat', 'factures_liees',
                   'chantier', 'comparaison_options', 'modifiable',
                   'echeancier', 'mode_installation', 'is_active'):
            self.assertIn(lu, ligne)

    def test_detail_et_forme_complete_gardent_tout(self):
        (d,) = self._creer(1)
        detail = self.api.get('%s%s/' % (URL, d.pk)).json()
        self.assertEqual(detail['etude_params'], d.etude_params)
        self.assertEqual(len(detail['lignes']), 12)
        complete = self._page(forme='complete').json()['results'][0]
        self.assertEqual(len(complete['lignes']), 12)
        self.assertEqual(complete['etude_params'], d.etude_params)
        self.assertEqual(self.api.get(URL, {'forme': 'abc'}).status_code, 400)

    def test_marge_masquee_au_commercial(self):
        self._creer(1, created_by=self.commercial)
        api_com = APIClient()
        api_com.force_authenticate(user=self.commercial)
        resp = self._page(api=api_com)
        self.assertIsNone(resp.json()['results'][0]['marge_snapshot'])
        self.assertNotIn('prix_achat', resp.content.decode())
        ligne_admin = self._page().json()['results'][0]
        self.assertEqual(ligne_admin['marge_snapshot'], '23.50')

    def test_recherche_filtres_et_compte_par_le_serveur(self):
        from datetime import timedelta
        from django.utils import timezone
        jour = timezone.localdate()
        self._creer(1)
        (zero,) = self._creer(1, client=self.autre_client)
        (expire,) = self._creer(1, statut=Devis.Statut.ENVOYE,
                                date_validite=jour - timedelta(days=3))
        (envoye,) = self._creer(1, statut=Devis.Statut.ENVOYE,
                                date_validite=jour + timedelta(days=3))
        (remplace,) = self._creer(1, is_active=False)
        (du_com,) = self._creer(1, created_by=self.commercial)

        def ids(**p):
            data = self._page(**p).json()
            return {r['id'] for r in data['results']}, data['count']

        self.assertEqual(ids(q='zeroua')[0], {zero.pk})
        self.assertEqual(ids(q=zero.reference.lower())[0], {zero.pk})
        self.assertEqual(ids(statut_effectif='expire')[0], {expire.pk})
        self.assertEqual(ids(statut_effectif='envoye')[0], {envoye.pk})
        self.assertNotIn(remplace.pk, ids(actifs='1')[0])
        self.assertIn(remplace.pk, ids()[0])
        self.assertEqual(ids(auteurs=str(self.commercial.pk))[0], {du_com.pk})
        self.assertEqual(ids(page_size=2)[1], 6)
        self.assertEqual(len(ids(page_size=2)[0]), 2)
        self.assertEqual(self.api.get(URL, {'auteurs': 'x'}).status_code, 400)
        self.assertEqual(
            self.api.get(URL, {'statut_effectif': 'zz'}).status_code, 400)

    def test_synthese_compte_toute_la_portee(self):
        from datetime import timedelta
        from django.utils import timezone
        jour = timezone.localdate()
        self._creer(2)
        self._creer(1, statut=Devis.Statut.ENVOYE,
                    date_validite=jour - timedelta(days=3))
        (bientot,) = self._creer(1, statut=Devis.Statut.ENVOYE,
                                 date_validite=jour + timedelta(days=3))
        self._creer(1, statut=Devis.Statut.ACCEPTE,
                    option_acceptee='avec_batterie')
        self._creer(1, is_active=False)
        resp = self.api.get(URL + 'synthese/')
        self.assertEqual(resp.status_code, 200, getattr(resp, 'data', resp))
        s = resp.json()
        self.assertEqual(s['total'], 6)
        self.assertEqual(s['remplaces'], 1)
        self.assertEqual(s['par_statut']['brouillon']['count'], 2)
        self.assertEqual(s['par_statut']['expire']['count'], 1)
        self.assertEqual(s['par_statut']['envoye']['count'], 1)
        self.assertEqual(s['par_statut']['accepte']['count'], 1)
        self.assertEqual(s['a_relancer'], [
            {'id': bientot.pk, 'reference': bientot.reference}])
        self.assertEqual(s['batterie'], {'avec': 1, 'sans': 0})
        # Le total d'argent est celui que la liste affiche (total_affiche).
        ligne = self._page(statut_effectif='accepte').json()['results'][0]
        self.assertAlmostEqual(
            s['par_statut']['accepte']['total'], float(ligne['total_affiche']))
        # Portée du rôle : la synthèse compte ce que la liste montre à ce rôle.
        self._creer(1, created_by=self.commercial)
        api_com = APIClient()
        api_com.force_authenticate(user=self.commercial)
        self.assertEqual(api_com.get(URL + 'synthese/').json()['total'],
                         self._page(api=api_com).json()['count'])
