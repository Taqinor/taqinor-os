"""ACAL22 (C-ACAL-044) — écriture par SECTION du document + jeton If-Match.

Avant : un onglet du rail (Horizon, Terrain…) et l'atelier écrivaient chacun
le document ENTIER depuis leur copie ; le dernier arrivé annulait l'autre en
silence (200 ``inchange: true`` et géométrie D1 perdue — porte CYC-G2-05,
live ATL-02). Désormais :

* ``POST layout/section/`` remplace UNE clé (liste blanche) après avoir
  comparé ``base_empreinte`` à l'empreinte « document » STOCKÉE, relue sous
  verrou de ligne ;
* ``POST layout/`` compare l'en-tête ``If-Match`` de la même façon ;
* un jeton périmé ⇒ 409 ``{detail, code: 'document_modifie',
  empreinte_courante}`` et le document reste octet-identique.

Source réelle : ``services.layout`` + l'action réelle, APIClient réel, base
réelle — aucun mock.
"""
from __future__ import annotations

import copy
import json
import threading
import time
import uuid
from pathlib import Path

from django.db import connection, transaction
from django.test import TransactionTestCase

from apps.calepinage.models import Calepinage
from apps.calepinage.services.layout import (
    DocumentModifie, empreinte_document, enregistrer_layout,
    enregistrer_section,
)
from apps.crm.models import Client
from apps.ventes.models import Devis
from authentication.models import Company

from .test_api_liste import BaseApiCalepinage, url_detail

CONTRAT = json.loads(
    (Path(__file__).resolve().parent.parent / 'contract_samples'
     / 'calepinage_layout_section.json').read_text(encoding='utf-8'))

D0 = {
    'version': 2,
    'zones': [{'id': 'z1', 'label': 'Pan sud', 'pitchDeg': 15,
               'vertices': [[0, 0], [10, 0], [10, 6], [0, 6]]}],
    'panelWatt': 575,
}
# D1 : la géométrie redessinée par l'atelier (un second pan).
D1 = {
    'version': 2,
    'zones': [
        {'id': 'z1', 'label': 'Pan sud', 'pitchDeg': 15,
         'vertices': [[0, 0], [10, 0], [10, 6], [0, 6]]},
        {'id': 'z2', 'label': 'Pan est', 'pitchDeg': 20,
         'vertices': [[12, 0], [18, 0], [18, 5], [12, 5]]},
    ],
    'panelWatt': 575,
}
HORIZON = copy.deepcopy(CONTRAT['exemple_corps_section']['valeur'])


class LayoutSectionApiTest(BaseApiCalepinage):

    def setUp(self):
        super().setUp()
        self.calepinage = Calepinage.objects.create(
            company=self.company, lead_id=self.lead.pk, titre='QA-ACAL22')
        enregistrer_layout(self.calepinage, copy.deepcopy(D0), user=self.user)
        self.url = f'{url_detail(self.calepinage.pk)}layout/'
        self.url_section = f'{self.url}section/'

    def _lire(self):
        reponse = self.api.get(self.url)
        self.assertEqual(reponse.status_code, 200, reponse.data)
        return reponse.data

    def _poster_layout(self, document, if_match=None):
        extra = {'HTTP_IF_MATCH': if_match} if if_match is not None else {}
        return self.api.post(self.url, {'roof_layout': document},
                             format='json', **extra)

    def _section(self, cle, valeur, base, **autres):
        corps = {'cle': cle, 'valeur': valeur, 'base_empreinte': base}
        corps.update(autres)
        return self.api.post(self.url_section, corps, format='json')

    # ── le scénario S-B : l'atelier périmé ne détruit plus la section ──────
    def test_atelier_perime_apres_section_horizon_409_et_document_intact(self):
        # L'atelier enregistre D1, puis lit sa base E(D1).
        e0 = self._lire()['empreinte_document']
        premier = self._poster_layout(copy.deepcopy(D1), if_match=e0)
        self.assertEqual(premier.status_code, 200, premier.data)
        base_atelier = premier.data['empreinte_document']
        self.assertEqual(base_atelier, empreinte_document(D1))

        # L'onglet Horizon écrit SA section avec la base lue.
        section = self._section('horizonProfile', HORIZON, base_atelier)
        self.assertEqual(section.status_code, 200, section.data)
        self.assertFalse(section.data['inchange'])

        # L'atelier (resté sur E(D1)) ré-enregistre sa copie SANS horizon.
        avant = self._lire()['roof_layout']
        modifie = copy.deepcopy(D1)
        modifie['zones'][1]['pitchDeg'] = 25
        refus = self._poster_layout(modifie, if_match=base_atelier)
        self.assertEqual(refus.status_code, 409, refus.data)
        self.assertEqual(refus.data['code'], 'document_modifie')
        self.assertEqual(sorted(refus.data),
                         sorted(CONTRAT['exemple_conflit_409']))

        apres = self._lire()
        self.assertEqual(apres['roof_layout'], avant)
        self.assertEqual(apres['roof_layout']['horizonProfile'], HORIZON)
        self.assertEqual(apres['roof_layout']['zones'], D1['zones'])
        self.assertEqual(refus.data['empreinte_courante'],
                         apres['empreinte_document'])

    def test_onglet_perime_ne_reverse_pas_la_geometrie_d1(self):
        base_onglet = self._lire()['empreinte_document']  # E(D0)
        atelier = self._poster_layout(copy.deepcopy(D1), if_match=base_onglet)
        self.assertEqual(atelier.status_code, 200, atelier.data)
        versions = self.calepinage.versions.count()

        refus = self._section('horizonProfile', HORIZON, base_onglet)
        self.assertEqual(refus.status_code, 409, refus.data)
        self.assertEqual(refus.data['code'], 'document_modifie')

        relu = self._lire()
        self.assertEqual(relu['roof_layout'], D1)
        self.assertNotIn('horizonProfile', relu['roof_layout'])
        self.assertEqual(self.calepinage.versions.count(), versions)

    def test_section_hors_liste_blanche_400(self):
        base = self._lire()['empreinte_document']
        for cle in ('pin', 'zones_bidon', None):
            with self.subTest(cle=cle):
                reponse = self._section(cle, {'x': 1}, base)
                self.assertEqual(reponse.status_code, 400, reponse.data)
                self.assertIn('cle', reponse.data)
        champ = self.api.post(self.url_section, {
            'cle': 'zones', 'zone_id': 'z1', 'base_empreinte': base,
            'champs': {'vertices': [[0, 0], [1, 1], [0, 1]]}}, format='json')
        self.assertEqual(champ.status_code, 400, champ.data)
        self.assertIn('champs', champ.data)
        self.assertEqual(self._lire()['roof_layout'], D0)

    def test_section_de_zone_ecrit_les_seuls_champs_du_pan(self):
        base = self._lire()['empreinte_document']
        corps = copy.deepcopy(CONTRAT['exemple_zone']['corps'])
        corps['base_empreinte'] = base
        reponse = self.api.post(self.url_section, corps, format='json')
        self.assertEqual(reponse.status_code, 200, reponse.data)
        zone = self._lire()['roof_layout']['zones'][0]
        self.assertEqual(zone['pitchDeg'], 18)
        self.assertEqual(zone['pitchSource'], {'mode': 'degres', 'degres': 18})
        self.assertEqual(zone['vertices'], D0['zones'][0]['vertices'])

    def test_section_renvoyee_a_l_identique_inchange(self):
        base = self._lire()['empreinte_document']
        premier = self._section('horizonProfile', HORIZON, base)
        self.assertEqual(premier.status_code, 200, premier.data)
        versions = self.calepinage.versions.count()
        second = self._section('horizonProfile', HORIZON,
                               premier.data['empreinte_document'])
        self.assertEqual(second.status_code, 200, second.data)
        self.assertTrue(second.data['inchange'])
        self.assertIsNone(second.data['version'])
        self.assertEqual(self.calepinage.versions.count(), versions)

    def test_post_layout_sans_if_match_428(self):
        # ACAL316 — If-Match OBLIGATOIRE : rien n'est écrit sans jeton.
        avant = self._lire()
        versions = self.calepinage.versions.count()
        reponse = self._poster_layout(copy.deepcopy(D1))
        self.assertEqual(reponse.status_code, 428, reponse.data)
        self.assertEqual(
            reponse.data['detail'],
            'Jeton de version manquant : rechargez la conception avant '
            'd\'enregistrer.')
        apres = self._lire()
        self.assertEqual(apres, avant)
        self.assertEqual(apres['roof_layout'], D0)
        self.assertEqual(self.calepinage.versions.count(), versions)

    def test_post_layout_etag_vide_est_le_jeton_d_un_document_vide(self):
        # Un document encore vide n'a pas d'empreinte : ``If-Match: ""``.
        neuf = Calepinage.objects.create(
            company=self.company, lead_id=self.lead.pk, titre='QA-ACAL316')
        url = f'{url_detail(neuf.pk)}layout/'
        sans = self.api.post(url, {'roof_layout': copy.deepcopy(D1)},
                             format='json')
        self.assertEqual(sans.status_code, 428, sans.data)
        vide = self.api.post(url, {'roof_layout': copy.deepcopy(D1)},
                             format='json', HTTP_IF_MATCH='""')
        self.assertEqual(vide.status_code, 200, vide.data)
        perime = self.api.post(url, {'roof_layout': copy.deepcopy(D0)},
                               format='json', HTTP_IF_MATCH='""')
        self.assertEqual(perime.status_code, 409, perime.data)

    def test_verrou_reste_409_roof_layout(self):
        client = Client.objects.create(company=self.company, nom='Verrou 22')
        devis = Devis.objects.create(
            company=self.company, client=client, reference='DEV-ACAL22-1',
            statut=Devis.Statut.ACCEPTE)
        self.calepinage.devis = devis
        self.calepinage.save(update_fields=['devis'])
        base = self._lire()['empreinte_document']
        reponse = self._section('horizonProfile', HORIZON, base)
        self.assertEqual(reponse.status_code, 409, reponse.data)
        self.assertIn('roof_layout', str(reponse.data))
        self.assertNotEqual(
            (reponse.data or {}).get('code'), 'document_modifie')
        self.assertEqual(self._lire()['roof_layout'], D0)

    def test_autre_societe_404(self):
        base = self._lire()['empreinte_document']
        reponse = self.api_autre.post(self.url_section, {
            'cle': 'horizonProfile', 'valeur': HORIZON,
            'base_empreinte': base}, format='json')
        self.assertEqual(reponse.status_code, 404)

    def test_exemple_contrat_section(self):
        base = self._lire()['empreinte_document']
        reponse = self._section('horizonProfile', HORIZON, base)
        self.assertEqual(reponse.status_code, 200, reponse.data)
        self.assertEqual(sorted(reponse.data), sorted(CONTRAT['exemple']))
        refus = self._section('pin', {}, reponse.data['empreinte_document'])
        self.assertEqual(sorted(refus.data),
                         sorted(CONTRAT['exemple_refus_cle_400']))
        perime = self._section('horizonProfile', None, base)
        self.assertEqual(perime.status_code, 409, perime.data)
        self.assertEqual(sorted(perime.data),
                         sorted(CONTRAT['exemple_conflit_409']))

    def test_design_context_rend_l_empreinte_document(self):
        reponse = self.api.get(f'{url_detail(self.calepinage.pk)}'
                               'design-context/')
        self.assertEqual(reponse.status_code, 200, reponse.data)
        self.assertEqual(reponse.data['geometrie']['empreinte_document'],
                         empreinte_document(D0))


class CourseDeuxConnexionsTest(TransactionTestCase):
    """Deux écrivains concurrents : le second attend le verrou de ligne, relit
    le document du premier et refuse (409) — sans ``select_for_update`` il
    lirait l'ancien document, verrait son jeton « valide » et écraserait D2."""

    def setUp(self):
        self.company = Company.objects.create(nom='Course Co',
                                              slug=f'course-co-acal22-{uuid.uuid4().hex[:8]}')
        self.client_a = Client.objects.create(company=self.company,
                                              nom='Client Course')
        self.calepinage = Calepinage.objects.create(
            company=self.company, client=self.client_a, roof_layout=D1)

    def test_le_second_ecrivain_voit_le_jeton_perime(self):
        base_d1 = empreinte_document(D1)
        d2 = dict(copy.deepcopy(D1), horizonProfile=HORIZON)
        issues = []

        def ecrivain():
            try:
                cible = Calepinage.objects.get(pk=self.calepinage.pk)
                enregistrer_section(cible, 'poseSurfaces', [{'id': 'sol-1'}],
                                    base_empreinte=base_d1)
                issues.append('ecrit')
            except DocumentModifie as conflit:
                issues.append(conflit)
            except Exception as autre:  # pragma: no cover - diagnostic
                issues.append(autre)
            finally:
                connection.close()

        with transaction.atomic():
            Calepinage.objects.select_for_update().get(pk=self.calepinage.pk)
            Calepinage.objects.filter(pk=self.calepinage.pk).update(
                roof_layout=d2)
            fil = threading.Thread(target=ecrivain)
            fil.start()
            time.sleep(1.0)
        fil.join(timeout=20)

        self.assertEqual(len(issues), 1, issues)
        self.assertIsInstance(issues[0], DocumentModifie)
        self.assertEqual(issues[0].empreinte_courante, empreinte_document(d2))
        self.calepinage.refresh_from_db()
        self.assertEqual(self.calepinage.roof_layout, d2)
