"""CALX310 — le plan de câblage des chaînes, en PDF et en DXF.

Ce qui est prouvé ici :

* 12 modules sur 2 chaînes produisent 2 entrées de légende et 12 formes
  teintées ; chaque entrée dit son numéro, son nombre de modules, l'onduleur
  et l'entrée MPPT publiés ;
* un module NON affecté (ligne à ``chaine: null`` ou absente de la table) est
  dessiné en contour seul, JAMAIS teinté d'une chaîne voisine, et compté dans
  l'encart « non affectés » ;
* un module en affectation MANUELLE porte un signe distinct ;
* le repère « <pan>#<rang> » est celui de ``services/chaines.affectation`` —
  un panneau illisible ne fait pas glisser le rang des suivants ;
* la teinte est la palette de l'écran (``AffectationChaines.jsx``), relue ;
* sans chaîne publiée, refus en nommant ``electrique.chainage`` ; sans
  géométrie, en nommant ``roof_layout`` ;
* le DXF produit porte le calque ``CHAINES`` et se RELIT par ``ezdxf`` ; sans
  le paramètre explicite, il reste celui de CAL178 ;
* aucun montant dans la légende ; le PDF passe par ``core.pdf.render_pdf`` et
  partage la mise en page de l'aperçu ;
* en base (CI) : ``GET …/plan-cablage.pdf/`` et ``…/plan-cablage.dxf/``
  bornés société (404) et permission (403), 400 + champ nommé.

Run :
    python manage.py test apps.calepinage.tests.test_calx310_plan_cablage -v2
"""
import copy
import datetime
import io
import pathlib
import re
import unittest
import xml.etree.ElementTree as ET
from types import SimpleNamespace
from unittest import mock

from apps.calepinage.models import Calepinage
from apps.calepinage.services.documents import mise_en_page
from apps.calepinage.services.documents.plan_cablage import (
    CHAMP_CHAINAGE, COULEUR_NON_AFFECTE, MOTS_DE_MONTANT, PALETTE_CHAINES,
    PlanCablageRefuse, affectation_du_calepinage, exporter_plan_cablage_dxf,
    html_du_plan_cablage, lignes_de_legende, modules_du_plan,
    plan_de_cablage, rendre_plan_cablage_pdf, rendre_plan_cablage_svg,
    svg_de_plan_cablage, verifier_legende_sans_montant,
)
from apps.calepinage.services.export_dxf import (
    CALQUE_CHAINES, CALQUE_MODULES, octets_dxf,
)
from apps.calepinage.services.planche import (
    PlancheRefusee, geometrie_de_planche,
)
from apps.calepinage.services.rapport import RapportRefuse

from .test_api_liste import BaseApiCalepinage, url_detail

RACINE_DEPOT = pathlib.Path(__file__).resolve().parents[5]
JSX = (RACINE_DEPOT / 'frontend' / 'src' / 'features' / 'calepinage' / 'plan'
       / 'AffectationChaines.jsx')
MOMENT = datetime.datetime(2026, 9, 23, 10, 0, tzinfo=datetime.timezone.utc)


def _panneaux(n):
    """``n`` centres ENU (m) en rangées de 4, dans l'ordre du document."""
    return [{'cx': 1.2 + 2.2 * (rang % 4), 'cy': 1.0 + 2.5 * (rang // 4)}
            for rang in range(n)]


#: Un pan de 12 modules posés (720 Wc : emprise SOURCÉE par le kit villa).
LAYOUT = {
    'version': 2,
    'outline': [[33.5, -7.6], [33.5, -7.5999], [33.5001, -7.5999],
                [33.5001, -7.6]],
    'panelWatt': 720,
    'zones': [{
        'id': 'z1',
        'label': 'Pan Sud',
        'vertices': [[-7.6, 33.5], [-7.5999, 33.5], [-7.5999, 33.5001],
                     [-7.6, 33.5001]],
        'geometry': {'azimuthDeg': 180.0, 'tiltDeg': 15.0, 'count': 12,
                     'origin': [-7.6, 33.5], 'panels': _panneaux(12)},
    }],
}


def ligne(rang, chaine, *, mppt=None, onduleur=1, source='automatique',
          pan='Pan Sud'):
    return {'module': '%s#%d' % (pan, rang), 'pan': pan, 'chaine': chaine,
            'onduleur': onduleur if chaine is not None else None,
            'mppt': (mppt if mppt is not None else chaine)
            if chaine is not None else None,
            'source': source}


#: La table PUBLIÉE : 6 modules sur la chaîne 1 (MPPT 1), 6 sur la 2 (MPPT 2).
AFFECTATION = [ligne(r, 1) for r in range(1, 7)] + \
    [ligne(r, 2) for r in range(7, 13)]


def layout(**zone):
    donnees = copy.deepcopy(LAYOUT)
    donnees['zones'][0].update(zone)
    return donnees


def svg_de(plan):
    return svg_de_plan_cablage(plan, titre='Plan de câblage — Villa Anfa',
                               pied='calepinage abababababab')


def formes(svg, classe):
    racine = ET.fromstring(svg.split('?>', 1)[1])
    return [e for e in racine.iter() if e.get('class') == classe]


class PlanDeCablageTest(unittest.TestCase):
    def setUp(self):
        self.plan = plan_de_cablage(LAYOUT, AFFECTATION)
        self.svg = svg_de(self.plan)

    def test_12_modules_sur_2_chaines_2_entrees_et_12_formes_teintees(self):
        self.assertEqual([e['chaine'] for e in self.plan['legende']], [1, 2])
        self.assertEqual([e['modules'] for e in self.plan['legende']], [6, 6])
        teintees = formes(self.svg, 'module-chaine')
        self.assertEqual(len(teintees), 12)
        self.assertEqual(len(formes(self.svg, 'legende-chaine')), 2)
        self.assertEqual(formes(self.svg, 'module-non-affecte'), [])
        self.assertEqual(self.plan['non_affectes'], 0)

    def test_chaque_module_porte_la_couleur_de_sa_chaine(self):
        couleurs = {e.get('data-module'): (e.get('data-chaine'), e.get('fill'))
                    for e in formes(self.svg, 'module-chaine')}
        self.assertEqual(couleurs['Pan Sud#1'], ('1', PALETTE_CHAINES[0]))
        self.assertEqual(couleurs['Pan Sud#12'], ('2', PALETTE_CHAINES[1]))

    def test_la_legende_dit_numero_modules_onduleur_et_mppt(self):
        lignes = lignes_de_legende(self.plan)
        self.assertIn('Chaîne 1 — 6 modules', lignes)
        self.assertIn('onduleur 1 · entrée MPPT 1', lignes)
        self.assertIn('Chaîne 2 — 6 modules', lignes)
        self.assertIn('onduleur 1 · entrée MPPT 2', lignes)
        self.assertIn('Non affectés : 0 module', lignes)

    def test_un_onduleur_non_attribue_est_dit_jamais_numerote(self):
        table = [dict(entree, onduleur=None) for entree in AFFECTATION]
        lignes = lignes_de_legende(plan_de_cablage(LAYOUT, table))
        self.assertIn('onduleur non attribué · entrée MPPT 1', lignes)

    def test_aucun_montant_dans_la_legende(self):
        for texte in lignes_de_legende(self.plan):
            self.assertIsNone(MOTS_DE_MONTANT.search(texte), texte)
        visible = re.sub(r'<[^>]+>', ' ', self.svg.split('legende-cablage')[1])
        self.assertIsNone(MOTS_DE_MONTANT.search(visible))

    def test_une_legende_porteuse_d_un_montant_est_refusee(self):
        with self.assertRaises(PlanCablageRefuse) as capture:
            verifier_legende_sans_montant(['Chaîne 1 — 1200 MAD'])
        self.assertEqual(capture.exception.champ, 'legende')
        self.assertIn('MAD', str(capture.exception))

    def test_le_svg_se_parse_et_ne_charge_rien(self):
        ET.fromstring(self.svg.split('?>', 1)[1])
        sans_espace_de_noms = self.svg.replace(
            'xmlns="http://www.w3.org/2000/svg"', '')
        for interdit in ('http://', 'https://', '@import', '<image'):
            self.assertNotIn(interdit, sans_espace_de_noms)

    def test_la_toiture_reste_celle_de_la_planche_sans_module_vert(self):
        # Contenu « toiture » : la planche ne dessine pas ses modules verts —
        # la couche de câblage est la SEULE à dessiner les modules.
        from apps.calepinage.services.planche import VERT_MODULE_FOND

        self.assertNotIn(VERT_MODULE_FOND, self.svg)
        self.assertIn('Plan de câblage — Villa Anfa', self.svg)
        self.assertIn('calepinage abababababab', self.svg)


class NonAffectesTest(unittest.TestCase):
    def test_un_module_a_chaine_nulle_reste_en_contour_seul(self):
        table = AFFECTATION[:11] + [ligne(12, None)]
        plan = plan_de_cablage(LAYOUT, table)
        svg = svg_de(plan)
        seuls = formes(svg, 'module-non-affecte')
        self.assertEqual([e.get('data-module') for e in seuls], ['Pan Sud#12'])
        self.assertEqual(seuls[0].get('fill'), 'none')
        self.assertEqual(seuls[0].get('stroke'), COULEUR_NON_AFFECTE)
        self.assertEqual(seuls[0].get('data-chaine'), '')
        self.assertEqual(len(formes(svg, 'module-chaine')), 11)
        self.assertEqual(plan['non_affectes'], 1)
        self.assertIn('Non affectés : 1 module', lignes_de_legende(plan))

    def test_un_module_absent_de_la_table_n_emprunte_aucune_teinte(self):
        # Le 12e module n'a AUCUNE ligne : il n'hérite pas de la chaîne 2 de
        # son voisin — il est non affecté.
        plan = plan_de_cablage(LAYOUT, AFFECTATION[:11])
        dernier = [m for m in plan['modules']
                   if m['module'] == 'Pan Sud#12'][0]
        self.assertIsNone(dernier['chaine'])
        self.assertIsNone(dernier['couleur'])
        voisin = [m for m in plan['modules']
                  if m['module'] == 'Pan Sud#11'][0]
        self.assertEqual(voisin['chaine'], 2)
        self.assertEqual(plan['non_affectes'], 1)
        for module in formes(svg_de(plan), 'module-non-affecte'):
            self.assertNotIn(module.get('stroke'), PALETTE_CHAINES)
            self.assertEqual(module.get('fill'), 'none')

    def test_un_module_affecte_mais_non_dessine_est_compte_a_part(self):
        table = AFFECTATION + [ligne(13, 2)]
        plan = plan_de_cablage(LAYOUT, table)
        self.assertEqual(plan['non_dessines'], 1)
        self.assertEqual(plan['legende'][1]['modules'], 7)
        self.assertEqual(len(formes(svg_de(plan), 'module-chaine')), 12)


class AffectationManuelleTest(unittest.TestCase):
    def test_un_module_manuel_porte_un_signe_distinct(self):
        table = copy.deepcopy(AFFECTATION)
        table[2]['source'] = 'affectation manuelle'
        plan = plan_de_cablage(LAYOUT, table)
        svg = svg_de(plan)
        marques = formes(svg, 'marque-manuelle')
        self.assertEqual([m.get('data-module') for m in marques],
                         ['Pan Sud#3'])
        self.assertEqual(plan['manuels'], 1)
        self.assertIn('× affectation manuelle : 1 module',
                      lignes_de_legende(plan))

    def test_sans_affectation_manuelle_aucun_signe(self):
        svg = svg_de(plan_de_cablage(LAYOUT, AFFECTATION))
        self.assertEqual(formes(svg, 'marque-manuelle'), [])


class JointDocumentElectriqueTest(unittest.TestCase):
    def test_un_panneau_illisible_ne_fait_pas_glisser_les_rangs(self):
        panneaux = _panneaux(12)
        panneaux[4] = {'cx': None, 'cy': 1.0}  # rang 5 non dessinable
        donnees = layout(geometry=dict(LAYOUT['zones'][0]['geometry'],
                                       panels=panneaux))
        geometrie = geometrie_de_planche(donnees)
        reperes = [m['module'] for m in modules_du_plan(donnees, geometrie)]
        self.assertEqual(len(reperes), 11)
        self.assertNotIn('Pan Sud#5', reperes)
        self.assertEqual(reperes[4], 'Pan Sud#6')
        plan = plan_de_cablage(donnees, AFFECTATION)
        sixieme = [m for m in plan['modules'] if m['module'] == 'Pan Sud#6'][0]
        self.assertEqual(sixieme['chaine'], 1)
        self.assertEqual(plan['non_dessines'], 1)

    def test_le_repere_de_pan_suit_la_regle_des_chaines(self):
        # Sans label : l'identifiant ; sans l'un ni l'autre : PAN-<rang>.
        sans_label = layout(label=None)
        geometrie = geometrie_de_planche(sans_label)
        self.assertEqual(modules_du_plan(sans_label, geometrie)[0]['module'],
                         'z1#1')
        anonyme = layout(label=None, id=None)
        geometrie = geometrie_de_planche(anonyme)
        self.assertEqual(modules_du_plan(anonyme, geometrie)[0]['module'],
                         'PAN-1#1')

    def test_la_palette_est_celle_de_l_ecran(self):
        source = JSX.read_text(encoding='utf-8')
        bloc = re.search(r'AFFECTATION_PALETTE = \[(.*?)\]', source, re.S)
        self.assertIsNotNone(bloc)
        self.assertEqual(tuple(re.findall(r"'(rgb\([^)]*\))'",
                                          bloc.group(1))), PALETTE_CHAINES)
        gris = re.search(r"AFFECTATION_UNASSIGNED = '(rgb\([^)]*\))'", source)
        self.assertEqual(gris.group(1), COULEUR_NON_AFFECTE)


class RefusTest(unittest.TestCase):
    def test_sans_chaine_publiee_refus_nommant_le_chainage(self):
        for table in ([], [ligne(r, None) for r in range(1, 13)], None):
            with self.subTest(table=table):
                with self.assertRaises(PlanCablageRefuse) as capture:
                    plan_de_cablage(LAYOUT, table)
                self.assertEqual(capture.exception.champ, CHAMP_CHAINAGE)
                self.assertEqual(capture.exception.champ,
                                 'electrique.chainage')

    def test_sans_geometrie_refus_nommant_roof_layout(self):
        with self.assertRaises(PlancheRefusee) as capture:
            plan_de_cablage(None, AFFECTATION)
        self.assertEqual(capture.exception.champ, 'roof_layout')

    def test_une_cle_de_cout_dans_la_table_publiee_est_refusee(self):
        table = copy.deepcopy(AFFECTATION)
        table[0]['prix_achat'] = 1
        with mock.patch(
                'apps.calepinage.services.electrique.resultat_calepinage',
                return_value={'electrique': {'affectation': table}}):
            with self.assertRaises(RapportRefuse) as capture:
                affectation_du_calepinage(NU)
        self.assertIn('prix_achat', capture.exception.champ)


class DxfChainesTest(unittest.TestCase):
    @staticmethod
    def relire(octets):
        import ezdxf

        return ezdxf.read(io.StringIO(octets.decode('utf-8')))

    def setUp(self):
        self.plan = plan_de_cablage(LAYOUT, AFFECTATION)
        self.document = self.relire(octets_dxf(self.plan['geometrie'],
                                               chaines=self.plan['modules']))

    def test_le_dxf_porte_le_calque_chaines_et_se_relit(self):
        self.assertIn(CALQUE_CHAINES, self.document.layers)
        sur_chaines = [e for e in self.document.modelspace()
                       if e.dxf.layer == CALQUE_CHAINES]
        formes_ = [e for e in sur_chaines if e.dxftype() == 'LWPOLYLINE']
        reperes = sorted(e.dxf.text for e in sur_chaines
                         if e.dxftype() == 'TEXT')
        self.assertEqual(len(formes_), 12)
        self.assertEqual(reperes, sorted(['C1'] * 6 + ['C2'] * 6))

    def test_la_couleur_vraie_est_celle_de_la_chaine(self):
        from ezdxf import colors

        attendues = {colors.rgb2int((36, 130, 214)),
                     colors.rgb2int((232, 125, 33))}
        lues = {e.dxf.true_color for e in self.document.modelspace()
                if e.dxf.layer == CALQUE_CHAINES}
        self.assertEqual(lues, attendues)

    def test_les_modules_de_pose_restent_sur_leur_calque(self):
        modules = [e for e in self.document.modelspace()
                   if e.dxf.layer == CALQUE_MODULES]
        self.assertEqual(len(modules), 12)

    def test_un_module_non_affecte_n_entre_pas_sur_le_calque(self):
        plan = plan_de_cablage(LAYOUT, AFFECTATION[:11] + [ligne(12, None)])
        document = self.relire(octets_dxf(plan['geometrie'],
                                          chaines=plan['modules']))
        formes_ = [e for e in document.modelspace()
                   if e.dxf.layer == CALQUE_CHAINES
                   and e.dxftype() == 'LWPOLYLINE']
        self.assertEqual(len(formes_), 11)

    def test_sans_le_parametre_le_dxf_reste_celui_de_cal178(self):
        document = self.relire(octets_dxf(self.plan['geometrie']))
        self.assertNotIn(CALQUE_CHAINES, document.layers)

    def test_l_export_du_calepinage_passe_par_l_affectation_publiee(self):
        with mock.patch(
                'apps.calepinage.services.electrique.resultat_calepinage',
                return_value={'electrique': {'affectation': AFFECTATION}}):
            document = self.relire(exporter_plan_cablage_dxf(NU))
        self.assertIn(CALQUE_CHAINES, document.layers)


#: Un calepinage NON ENREGISTRÉ, sans société : aucune lecture en base.
NU = SimpleNamespace(pk=None, company=None, titre='Villa Anfa',
                     roof_layout=LAYOUT, resultat=None, layout_hash='ab' * 32,
                     version_moteur='calepinage-1.0.0')


class RenduPartageTest(unittest.TestCase):
    def test_le_svg_du_calepinage_porte_l_empreinte(self):
        svg = rendre_plan_cablage_svg(NU, moment=MOMENT,
                                      affectation=AFFECTATION)
        self.assertIn('calepinage abababababab', svg)
        self.assertIn('23/09/2026', svg)

    def test_le_pdf_passe_par_la_plomberie_partagee(self):
        with mock.patch('core.pdf.render_pdf',
                        return_value=b'%PDF-simule') as rendu:
            octets = rendre_plan_cablage_pdf(NU, moment=MOMENT,
                                             affectation=AFFECTATION)
        self.assertEqual(octets, b'%PDF-simule')
        self.assertEqual(
            rendu.call_args.kwargs['html'],
            html_du_plan_cablage(NU, moment=MOMENT, affectation=AFFECTATION))

    def test_l_apercu_et_le_pdf_partagent_une_seule_fonction(self):
        self.assertIs(mise_en_page('plan_cablage'), html_du_plan_cablage)

    def test_aucun_import_weasyprint_direct_ni_marque_en_dur(self):
        source = (pathlib.Path(__file__).resolve().parents[1] / 'services'
                  / 'documents' / 'plan_cablage.py').read_text(
                      encoding='utf-8')
        self.assertNotIn('import weasyprint', source)
        self.assertNotRegex(source, r'TAQINOR|taqinor\.ma')


PDF = b'%PDF-1.7 plan de cablage simule'


class EndpointPlanCablageEnBaseTest(BaseApiCalepinage):
    """``GET …/plan-cablage.pdf/`` et ``…/plan-cablage.dxf/`` (CI)."""

    def setUp(self):
        super().setUp()
        self.calepinage = Calepinage.objects.create(
            company=self.company, lead_id=self.lead.pk,
            titre='Villa Anfa', roof_layout=LAYOUT, layout_hash='a' * 64)
        self.etranger = Calepinage.objects.create(
            company=self.autre, lead_id=7, titre='Chez la voisine',
            roof_layout=LAYOUT)

    def _get(self, calepinage, suffixe, *, api=None, table=None):
        servi = {'electrique': {
            'affectation': AFFECTATION if table is None else table}}
        with mock.patch(
                'apps.calepinage.services.electrique.resultat_calepinage',
                return_value=servi), \
                mock.patch('core.pdf.render_pdf', return_value=PDF) as rendu:
            reponse = (api or self.api).get(
                '%s%s/' % (url_detail(calepinage.pk), suffixe))
        return reponse, rendu

    def test_le_pdf_se_telecharge_borne_societe(self):
        reponse, rendu = self._get(self.calepinage, 'plan-cablage.pdf')
        self.assertEqual(reponse.status_code, 200)
        self.assertEqual(reponse['Content-Type'], 'application/pdf')
        self.assertEqual(reponse.content, PDF)
        self.assertTrue(reponse['Content-Disposition'].endswith(
            'plan-cablage.pdf"'))
        self.assertEqual(rendu.call_args.kwargs['company'], self.company)
        self.assertIn('module-chaine', rendu.call_args.kwargs['html'])

    def test_le_dxf_porte_le_calque_chaines(self):
        reponse, _rendu = self._get(self.calepinage, 'plan-cablage.dxf')
        self.assertEqual(reponse.status_code, 200)
        self.assertIn(b'CHAINES', reponse.content)
        self.assertTrue(reponse['Content-Disposition'].endswith(
            'plan-cablage.dxf"'))

    def test_sans_chaine_400_en_nommant_le_chainage(self):
        for suffixe in ('plan-cablage.pdf', 'plan-cablage.dxf'):
            reponse, rendu = self._get(self.calepinage, suffixe, table=[])
            self.assertEqual(reponse.status_code, 400)
            self.assertIn('electrique.chainage', reponse.data)
            rendu.assert_not_called()

    def test_une_autre_societe_est_introuvable(self):
        for suffixe in ('plan-cablage.pdf', 'plan-cablage.dxf'):
            reponse, _rendu = self._get(self.etranger, suffixe)
            self.assertEqual(reponse.status_code, 404)

    def test_sans_permission_de_lecture_c_est_403(self):
        reponse, _rendu = self._get(self.calepinage, 'plan-cablage.pdf',
                                    api=self.api_sans)
        self.assertEqual(reponse.status_code, 403)


if __name__ == '__main__':  # pragma: no cover
    unittest.main()
