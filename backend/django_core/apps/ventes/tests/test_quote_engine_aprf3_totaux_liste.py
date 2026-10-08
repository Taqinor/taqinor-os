"""APRF3 (C-APRF-001) — ``display_totals`` (chemin des totaux de liste) ne lit
plus rien hors préchargement : lignes depuis ``lignes__produit__fiche_technique``
préchargé (quand l'appelant le déclare), ``ContentType`` via
``get_for_model`` (cache), et AUCUNE lecture de pièces jointes, de révision
remplacée ni de ``ShareLink`` — mêmes totaux au centime ; le mode DOCUMENT
(``build_quote_data(d, {'pdf_mode': 'full'})``) est inchangé.

Comptage par table via ``CaptureQueriesContext`` à deux tailles (10 puis 25
devis), dans une portée ``request_cache``.

Test-du-test : remettre la requête ``select_related`` sans condition ⇒
``ventes_lignedevis`` repasse à une requête par devis, le premier test échoue.
"""
import re

from django.db import connection
from django.test import TestCase
from django.test.utils import CaptureQueriesContext

from apps.ventes.models import Devis
from apps.ventes.quote_engine.builder import build_quote_data, display_totals
from apps.ventes.tests._quote_engine_common import (
    DEUX_OPTIONS, make_client, make_company, make_devis, make_user,
)

TABLES_INTERDITES = ('ventes_lignedevis', 'records_attachment',
                     'ventes_sharelink', 'django_content_type')


class TotauxListeTests(TestCase):
    def setUp(self):
        self.company = make_company(slug='aprf3-co', nom='APRF3')
        self.user = make_user(self.company)
        self.client_obj = make_client(self.company)
        self.n = 0
        # Les réglages PAR SOCIÉTÉ que le moteur lit (profil — identité DC1,
        # modèles de documents, barème) sont des singletons créés à la
        # PREMIÈRE lecture (``Model.get`` = get_or_create, comportement
        # antérieur à APRF3). En production ils existent depuis longtemps ;
        # la fixture les pose ici pour que ``test_zero_ecriture`` mesure ce
        # qu'une liste écrit À CHAQUE affichage, pas l'amorçage d'une société
        # neuve.
        from apps.parametres.models import CompanyProfile, TariffSettings
        from apps.parametres.models_documents import DocumentTemplates
        CompanyProfile.get(company=self.company)
        DocumentTemplates.get(company=self.company)
        TariffSettings.get(company=self.company)

    def _creer(self, nombre):
        for i in range(nombre):
            self.n += 1
            lignes = [('Panneau mono 550W', '12', '1100'),
                      ('Onduleur réseau 5kW', '1', '11700')]
            etude = None
            if i % 2:
                lignes += [('Onduleur hybride 5kW', '1', '15000'),
                           ('Batterie 5 kWh', '1', '14000')]
                etude = dict(DEUX_OPTIONS)
            make_devis(self.company, self.user, self.client_obj, lignes,
                       reference='DEV-APRF3-%03d' % self.n,
                       etude_params=etude)

    def _page(self):
        return list(Devis.objects.filter(company=self.company)
                    .select_related('company', 'client', 'lead')
                    .prefetch_related('lignes__produit__fiche_technique'))

    def _compter(self):
        from core.request_cache import request_scope
        page = self._page()
        with request_scope(), \
                CaptureQueriesContext(connection) as ctx:
            totaux = [display_totals(d, lignes_prechargees=True)
                      for d in page]
        compte = {t: sum(1 for q in ctx.captured_queries
                         if re.search(r'"%s"' % t, q['sql']))
                  for t in TABLES_INTERDITES}
        ecritures = [q['sql'] for q in ctx.captured_queries
                     if q['sql'].lstrip().upper().startswith(
                         ('INSERT', 'UPDATE', 'DELETE'))]
        return compte, ecritures, totaux

    def test_requetes_constantes_10_25(self):
        self._creer(10)
        a_dix, _e, _t = self._compter()
        self._creer(15)
        a_vingt_cinq, _e, _t = self._compter()
        self.assertEqual(a_dix, a_vingt_cinq)
        self.assertEqual(a_vingt_cinq, {t: 0 for t in TABLES_INTERDITES})

    def test_zero_ecriture(self):
        self._creer(10)
        _c, ecritures, _t = self._compter()
        self.assertEqual(ecritures, [])

    def test_montants_et_document_identiques(self):
        self._creer(10)
        _c, _e, totaux = self._compter()
        for devis, total in zip(self._page(), totaux):
            frais = Devis.objects.get(pk=devis.pk)
            reference = display_totals(frais)
            self.assertAlmostEqual(float(total['total']),
                                   float(reference['total']), places=2)
            self.assertEqual(total['nb_options'], reference['nb_options'])
        # Le mode DOCUMENT garde ses clés de rendu (aucun drapeau « totaux »).
        frais = Devis.objects.filter(company=self.company).first()
        data = build_quote_data(frais, {'pdf_mode': 'full'})
        self.assertIn('roof_photo', data)
        self.assertIn('mis_a_jour_le', data)
        self.assertEqual(
            data['display_total'],
            build_quote_data(Devis.objects.get(pk=frais.pk),
                             {'pdf_mode': 'full'})['display_total'])
