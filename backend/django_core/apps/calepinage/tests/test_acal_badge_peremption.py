"""ACAL47 (C-ACAL-112) — le badge « à jour » du MODULE compare le calepinage
IMPRIMÉ au devis (empreintes) et compte le document du CALEPINAGE.

Cas de la porte PUB-02 / LIVEX-12 : un devis composé à 12 panneaux, son
calepinage passé à 16 sans resynchronisation. Avant : ``layout_stale`` false
(la règle des comptes lisait la COPIE du devis, 12 = 12) et « Panneaux
posés » lisait aussi la copie. Désormais : périmé (conception divergente) et
16 panneaux (le document du calepinage).

Source réelle : ``apps.ventes.selectors.peremption_layout_devis`` (avec le
calepinage) — aucun mock ; APIClient réel, base réelle.
"""
from __future__ import annotations

from decimal import Decimal

from apps.calepinage.models import Calepinage
from apps.crm.models import Client, Lead
from apps.ventes.models import Devis, LigneDevis

from .test_api_liste import BaseApiCalepinage, url_detail

LAYOUT_DEVIS = {'schema_version': 2, 'result': {'panels': 12, 'kwc': 8.64}}
LAYOUT_CALEPINAGE = {'schema_version': 2, 'result': {'panels': 16, 'kwc': 11.52}}


class BadgePeremptionTest(BaseApiCalepinage):

    def setUp(self):
        super().setUp()
        client = Client.objects.create(company=self.company,
                                       nom='Bâtiment ACAL47')
        lead = Lead.objects.create(company=self.company, nom='Toiture ACAL47')
        self.devis = Devis.objects.create(
            company=self.company, client=client, lead=lead,
            reference='DEV-202610-0470', roof_layout=LAYOUT_DEVIS,
            layout_hash='d' * 64)
        LigneDevis.objects.create(
            devis=self.devis, designation='Panneau photovoltaïque 720 Wc',
            quantite=Decimal('12'), prix_unitaire=Decimal('1000'))
        # Le calepinage a été redessiné à 16 panneaux, SANS resynchronisation :
        # son empreinte imprimée n'est plus celle du devis.
        self.calepinage = Calepinage.objects.create(
            company=self.company, lead_id=lead.pk, devis=self.devis,
            titre='QA-ACAL47', roof_layout=LAYOUT_CALEPINAGE,
            layout_hash='c' * 64)

    def _detail(self):
        reponse = self.api.get(url_detail(self.calepinage.pk))
        self.assertEqual(reponse.status_code, 200, reponse.data)
        return reponse.data

    def _ligne_de_liste(self):
        reponse = self.api.get('/api/django/calepinage/calepinages/',
                               {'q': self.calepinage.titre})
        self.assertEqual(reponse.status_code, 200, reponse.data)
        lignes = (reponse.data['results'] if isinstance(reponse.data, dict)
                  else reponse.data)
        return next(ligne for ligne in lignes if ligne["id"] == self.calepinage.pk)

    def test_badge_perime_quand_calepinage_diverge(self):
        for source in (self._detail(), self._ligne_de_liste()):
            with self.subTest(source=sorted(source)[:3]):
                self.assertIs(source['layout_stale'], True)

    def test_nb_panneaux_du_document(self):
        for source in (self._detail(), self._ligne_de_liste()):
            with self.subTest(source=sorted(source)[:3]):
                self.assertEqual(source['layout_nb_panneaux'], 16)

    def test_meme_empreinte_et_comptes_alignes_a_jour(self):
        Calepinage.objects.filter(pk=self.calepinage.pk).update(
            roof_layout=LAYOUT_DEVIS, layout_hash='d' * 64)
        for source in (self._detail(), self._ligne_de_liste()):
            with self.subTest(source=sorted(source)[:3]):
                self.assertIs(source['layout_stale'], False)
                self.assertEqual(source['layout_nb_panneaux'], 12)
