"""ACAL92 (D-ACAL-3) — « la CONCEPTION lue pour une V1 n'est jamais la
conception courante re-liée » : le PDF d'un devis envoyé puis RÉVISÉ se rend
de son instantané figé (« Version envoyée »), même après que la conception
re-liée à la V2 a changé. La page planche reste (même compte de pages) et
elle dessine ce qui a été ENVOYÉ ; l'entrée électrique / l'ombrage de la V2
ne sont jamais servis au nom de la V1.

Vraie révision (``reviser_devis`` + l'abonné réel du calepinage), vrai
moteur (``build_quote_data``), vraie planche. Rendu SEUL : aucun statut lu ou
écrit autrement que par la révision elle-même (règle #4).

Run:
    powershell -File scripts/test-backend.ps1 -RestoreDb \
        -Modules "apps.ventes.tests.test_acal_planche_devis_remplace"
"""
import copy

from django.test import TestCase

from apps.calepinage import selectors as calepinage_selectors
from apps.calepinage import services as calepinage_services
from apps.calepinage.models import Calepinage
from apps.ventes.domain.geometrie import layout_hash
from apps.ventes.domain.revision import reviser_devis
from apps.ventes.models import Devis
from apps.ventes.quote_engine.builder import (
    _svg_planche_inline, build_quote_data)
from apps.ventes.tests._quote_engine_common import (
    make_client, make_company, make_devis, make_user)
from apps.ventes.tests.test_quote_engine_formats import LAYOUT_CAL182

LIGNES = [
    ('Onduleur réseau 3kW', '1', '6000'),
    ('Panneau mono 550W', '2', '1100'),
]
OPTIONS_RENDU = {'_embed_calepinage_planche': True,
                 'include_calepinage': True}
DIVERGENCE = ('planche : le calepinage a changé depuis la dernière '
              'resynchronisation')


def _conception(panneaux):
    document = copy.deepcopy(LAYOUT_CAL182)
    cases = [{'cx': 1.0 + 2.5 * i, 'cy': 1.0} for i in range(panneaux)]
    document['zones'][0]['geometry'].update(count=panneaux, panels=cases)
    document['result'] = {'panels': panneaux}
    return document


class PlancheDevisRemplace(TestCase):

    def setUp(self):
        self.company = make_company()
        self.user = make_user(self.company)
        self.client_obj = make_client(self.company)
        self.v1 = make_devis(self.company, self.user, self.client_obj,
                             LIGNES, reference='DEV-ACAL92-0001')
        envoyee = _conception(2)
        self.v1.roof_layout = envoyee
        self.v1.layout_hash = layout_hash(envoyee)
        self.v1.statut = Devis.Statut.ENVOYE
        self.v1.save(update_fields=['roof_layout', 'layout_hash', 'statut'])
        self.c = Calepinage.objects.create(
            company=self.company, client=self.client_obj, devis=self.v1,
            titre='ACAL92 planche', roof_layout=copy.deepcopy(envoyee),
            layout_hash=self.v1.layout_hash, version_moteur='2.1.0',
            resultat={'entree_electrique': {'dc_m': 30}})

    def _reviser(self):
        with self.captureOnCommitCallbacks(execute=True):
            v2 = reviser_devis(self.v1, user=self.user)
        self.v1.refresh_from_db()
        self.c.refresh_from_db()
        self.assertEqual(self.c.devis_id, v2.pk)
        return v2

    def _modifier_conception_v2(self):
        nouvelle = _conception(3)
        Calepinage.objects.filter(pk=self.c.pk).update(
            roof_layout=nouvelle, layout_hash=layout_hash(nouvelle))
        self.c.refresh_from_db()

    def test_v1_planche_figee_apres_modification_v2(self):
        avant = build_quote_data(self.v1, dict(OPTIONS_RENDU))
        self.assertTrue(avant.get('calepinage_svg'))
        self.assertTrue(avant.get('include_calepinage'))

        self._reviser()
        self._modifier_conception_v2()

        apres = build_quote_data(self.v1, dict(OPTIONS_RENDU))
        # Même page (compte de pages inchangé) …
        self.assertTrue(apres.get('calepinage_svg'))
        self.assertEqual(bool(apres.get('include_calepinage')),
                         bool(avant.get('include_calepinage')))
        self.assertNotIn(DIVERGENCE,
                         apres.get('avertissements_internes') or [])
        # … dessinée de la conception ENVOYÉE (version figée), pas de la
        # conception courante re-liée à la V2.
        figee = calepinage_selectors.conception_figee_du_devis(
            self.v1.pk, self.company)
        self.assertEqual(figee['source'], 'version')
        self.assertEqual(figee['roof_layout'], _conception(2))
        pied = calepinage_services.texte_d_empreinte(
            figee['layout_hash'], '', None)
        attendu = _svg_planche_inline(calepinage_services.rendre_planche_svg(
            self.c, pied=pied, document=_conception(2)))
        courante = _svg_planche_inline(calepinage_services.rendre_planche_svg(
            self.c, pied=pied))
        self.assertNotEqual(attendu, courante)
        self.assertEqual(apres['calepinage_svg'], attendu)
        # Règle #4 : aucun statut écrit par le rendu.
        self.v1.refresh_from_db()
        self.assertEqual(self.v1.statut, Devis.Statut.ENVOYE)

    def test_lien_direct_inchange(self):
        # Sans révision : pas de conception figée, la conception courante.
        self.assertIsNone(calepinage_selectors.conception_figee_du_devis(
            self.v1.pk, self.company))

    def test_donnees_v2_jamais_servies_a_v1(self):
        self._reviser()
        # Conception identique à l'envoi : les grandeurs restent lisibles.
        self.assertEqual(calepinage_selectors.entree_electrique_du_devis(
            self.v1.pk, self.company)['dc_m'], 30.0)
        self._modifier_conception_v2()
        self.assertIsNone(calepinage_selectors.entree_electrique_du_devis(
            self.v1.pk, self.company))
        self.assertIsNone(calepinage_selectors.ombrage_servi(
            self.v1.pk, self.company))
