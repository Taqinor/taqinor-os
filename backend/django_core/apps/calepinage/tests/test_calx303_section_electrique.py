"""CALX303 — la section « Électrique » du rapport, schéma unifilaire inclus.

Ce qui est prouvé ici, PUREMENT (aucune base) :

* le chaînage (``electrique.chainage``) et les onduleurs (avec leur ratio
  DC/AC) s'impriment depuis ``resultat`` ;
* 5 verdicts servis → 5 lignes ; ``bloquant``/``conforme``/``source``/
  ``detail`` sont imprimés TELS QUE SERVIS (aucun recalcul) ; un verdict
  ``conforme: null`` imprime « non vérifiable », jamais « OK » ;
* sans schéma disponible (``rendre_rapport_avec_schema`` avec un
  ``construire_bloc`` injecté), le rapport porte le motif MOT POUR MOT de
  ``services/reglementaire.py::_rendus_du_module`` et NE GROSSIT PAS d'une
  page vide (``@tag('pdf')``).

``bloc_schema_unifilaire`` touche la base (il prend le CALEPINAGE, lit son
devis lié — voir la docstring de ``electrique.py``) : ``BlocSchemaDbTest``
le prouve sur une fixture réelle, ÉCRITE mais NON EXÉCUTÉE localement (règle
de lane — CI validera).

Run (partie pure) :
    cd backend/django_core
    python -m pytest apps/calepinage/tests/test_calx303_section_electrique.py \
        -q
"""
import unittest
from unittest import mock

from apps.calepinage.services.rapport.electrique import (
    MENTION_NON_VERIFIABLE, MOTIF_SCHEMA_INDISPONIBLE, bloc_schema_unifilaire,
    html_de_section, html_table_verdicts, rendre_rapport_avec_schema,
)

# ``services.rapport.*`` est un paquet PUR — voir la note de
# ``test_calx299_section_systeme.py``. Mêmes garanties ici :
# ``BlocSchemaDbTest`` n'est définie que si Django est configuré.
try:
    from apps.calepinage.models import Calepinage
    from apps.crm.models import Client
    from apps.ventes.models import Devis

    from .test_api_liste import BaseApiCalepinage
except Exception:  # noqa: BLE001 - Django non configuré (essais purs)
    BaseApiCalepinage = None

MOTIF = "motif de test — section electrique"


def contexte(resultat, langue='fr'):
    return {'resultat': resultat, 'langue': langue,
            'section': {'code': 'electrique', 'motif_si_absent': MOTIF}}


VERDICTS_5 = [
    {'code': 'voc_cold_under_vmax', 'libelle': 'Voc à froid', 'conforme': True,
     'bloquant': True, 'source': 'fiche', 'detail': ''},
    {'code': 'vmp_cold_under_mppt_max', 'libelle': 'Vmp à froid',
     'conforme': True, 'bloquant': True, 'source': 'fiche', 'detail': ''},
    {'code': 'vmp_hot_over_mppt_min', 'libelle': 'Vmp à chaud',
     'conforme': True, 'bloquant': True, 'source': 'fiche', 'detail': ''},
    {'code': 'courant_par_entree_mppt', 'libelle': 'Courant MPPT',
     'conforme': True, 'bloquant': True, 'source': 'fiche', 'detail': ''},
    {'code': 'ratio_dc_ac', 'libelle': 'Ratio DC/AC', 'conforme': None,
     'bloquant': False, 'source': 'saisie', 'detail': ''},
]


# ── Chaînage, onduleurs, verdicts ────────────────────────────────────────────

class HtmlDeSectionTest(unittest.TestCase):
    def test_chainage_imprime(self):
        resultat = {'electrique': {'chainage': {
            'modules': 12, 'modules_par_chaine': 6, 'chaines': 2, 'reste': 0}}}
        html = html_de_section(contexte(resultat))
        self.assertIn('12', html)
        self.assertIn('Nombre de chaînes', html)

    def test_onduleurs_avec_ratio_dc_ac(self):
        resultat = {'electrique': {'chainage': {}, 'onduleurs': [{
            'reference': 'ONDULEUR-1', 'nombre': 1, 'puissance_dc_kwc': 8.64,
            'ratio_dc_ac': 0.864, 'conforme': True, 'motif': ''}]}}
        html = html_de_section(contexte(resultat))
        self.assertIn('ONDULEUR-1', html)
        self.assertIn('0,864', html)
        self.assertIn('Ratio DC/AC', html)

    def test_cinq_verdicts_servis_cinq_lignes(self):
        html = html_table_verdicts(VERDICTS_5)
        self.assertEqual(html.count('<tr'), 6)  # en-tête + 5 lignes

    def test_verdict_non_calculable_imprime_non_verifiable_jamais_ok(self):
        html = html_table_verdicts(VERDICTS_5)
        self.assertIn(MENTION_NON_VERIFIABLE, html)
        self.assertNotIn('>OK<', html)

    def test_bloquant_conforme_source_detail_servis_tels_quels(self):
        verdicts = [{
            'code': 'x', 'libelle': 'Contrôle X', 'conforme': False,
            'bloquant': True, 'source': 'norme',
            'detail': 'chute cumulée de 1,18 % — au-dessus de la cible.'}]
        html = html_table_verdicts(verdicts)
        self.assertIn('non conforme', html)
        self.assertIn('oui', html)  # bloquant
        self.assertIn('norme', html)
        self.assertIn('chute cumulée de 1,18 %', html)

    def test_verdict_avec_mention_de_temperature(self):
        verdicts = [{
            'code': 'voc_cold_under_vmax', 'libelle': 'Voc à froid',
            'conforme': True, 'bloquant': True, 'source': 'fiche',
            'detail': '', 'temperature_c': -5.0,
            'temperature_source': 'saisie',
            'temperature_mention': 'températures de référence, non sourcées'}]
        html = html_table_verdicts(verdicts)
        self.assertIn('températures de référence, non sourcées', html)

    def test_sans_electrique_section_vide(self):
        self.assertEqual(html_de_section(contexte({})), '')

    def test_sans_verdicts_ni_onduleurs_seul_le_chainage_optionnel(self):
        html = html_de_section(contexte({'electrique': {}}))
        self.assertEqual(html, '')


# ── Le schéma unifilaire : motif mot pour mot, aucune page vide ─────────────

def _pdf_dune_page(texte=''):
    import fitz

    document = fitz.open()
    try:
        page = document.new_page(width=595, height=842)
        if texte:
            page.insert_textbox((50, 50, 500, 100), texte, fontsize=12)
        return document.tobytes()
    finally:
        document.close()


class RendreRapportAvecSchemaTest(unittest.TestCase):
    def test_sans_schema_le_motif_mot_pour_mot_et_aucune_page_ajoutee(self):
        from apps.calepinage.services.pack_technique import compter_pages

        rapport_de_base = _pdf_dune_page('Rapport')

        def construire_bloc(calepinage, *, company=None):
            return None, MOTIF_SCHEMA_INDISPONIBLE

        octets, motif = rendre_rapport_avec_schema(
            object(), rapport_de_base, construire_bloc=construire_bloc)
        self.assertEqual(motif, MOTIF_SCHEMA_INDISPONIBLE)
        self.assertEqual(compter_pages(octets), compter_pages(rapport_de_base))
        self.assertEqual(octets, rapport_de_base)

    def test_avec_schema_le_rapport_gagne_sa_page_et_aucun_motif(self):
        from apps.calepinage.services.pack_technique import compter_pages

        rapport_de_base = _pdf_dune_page('Rapport')
        schema = _pdf_dune_page('Schéma')

        def construire_bloc(calepinage, *, company=None):
            return schema, None

        octets, motif = rendre_rapport_avec_schema(
            object(), rapport_de_base, construire_bloc=construire_bloc)
        self.assertEqual(motif, '')
        self.assertEqual(
            compter_pages(octets),
            compter_pages(rapport_de_base) + compter_pages(schema))

    def test_bloc_schema_unifilaire_est_le_point_d_injection_par_defaut(self):
        with mock.patch(
                'apps.calepinage.services.rapport.electrique'
                '.bloc_schema_unifilaire',
                return_value=(None, MOTIF_SCHEMA_INDISPONIBLE)) as simule:
            octets, motif = rendre_rapport_avec_schema(
                object(), _pdf_dune_page())
        simule.assert_called_once()
        self.assertEqual(motif, MOTIF_SCHEMA_INDISPONIBLE)


# ── DB — prouve bloc_schema_unifilaire sur une fixture réelle ──────────────

if BaseApiCalepinage is not None:

    class BlocSchemaDbTest(BaseApiCalepinage):
        """CI validera (nécessite la base de données)."""

        def setUp(self):
            super().setUp()
            self.calepinage = Calepinage.objects.create(
                company=self.company, lead_id=self.lead.pk, titre='Villa DB')

        def test_sans_devis_lie_le_motif_mot_pour_mot(self):
            octets, motif = bloc_schema_unifilaire(self.calepinage)
            self.assertIsNone(octets)
            self.assertEqual(motif, MOTIF_SCHEMA_INDISPONIBLE)

        def test_devis_lie_sans_schema_publiable_le_meme_motif(self):
            devis = Devis.objects.create(
                company=self.company,
                client=Client.objects.filter(company=self.company).first()
                or self.client_a,
                reference='DEV-CALX303-1')
            self.calepinage.devis = devis
            self.calepinage.save()
            octets, motif = bloc_schema_unifilaire(self.calepinage)
            self.assertIsNone(octets)
            self.assertEqual(motif, MOTIF_SCHEMA_INDISPONIBLE)


if __name__ == '__main__':  # pragma: no cover
    unittest.main()
