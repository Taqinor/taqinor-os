"""ACAL58 — l'orientation POSÉE des modules avant la pente du toit.

Constat C-ACAL-022 (C1, S1) : un toit PLAT (``pitchDeg: 0``) portant des
tables inclinées à 10° partait à PVGIS à 0° — ``extract_roof_config`` ne
lisait que la pente du TOIT. ``orientation_du_pan`` (ventes/domain/geometrie.py)
lit désormais ``geometry.tiltDeg``/``azimuthDeg`` d'abord ; sans ``geometry``,
la lecture du toit est inchangée au bit près ; une pose est-ouest garde la
lecture actuelle (C-ACAL-081, non tranchée ici).

Run :
    python manage.py test apps.ventes.tests.test_acal_orientation_pose -v2
"""
import copy
from io import StringIO
from types import SimpleNamespace

from django.core.management import call_command
from django.test import SimpleTestCase, TestCase

from apps.crm.models import Client
from apps.ventes.calepinage_options import _pan_principal
from apps.ventes.domain.creation_calepinage import _calepinage_range
from apps.ventes.models import Devis
from apps.ventes.services import extract_roof_config, orientation_du_pan
from apps.ventes.tasks import zones_etude_du_devis
from authentication.models import Company


def _zone_plate_inclinee(**geo):
    geometrie = {'tiltDeg': 10, 'azimuthDeg': 180, 'family': 'south',
                 'count': 12, 'kwc': 7.44}
    geometrie.update(geo)
    return {'label': 'Toit plat', 'roofType': 'flat', 'pitchDeg': 0,
            'facingAzimuthDeg': None, 'geometry': geometrie}


def _layout(zone):
    return {'version': 1, 'pin': {'lat': 33.57, 'lng': -7.59},
            'zones': [zone]}


class OrientationPoseeTest(SimpleTestCase):
    def test_toit_plat_incline_10_part_a_10(self):
        cfg = extract_roof_config(_layout(_zone_plate_inclinee()))
        pan = cfg['pans'][0]
        self.assertEqual(pan['inclinaison_deg'], 10)
        self.assertEqual(pan['azimut_deg'], 180)       # boussole (F3)
        self.assertEqual(pan['orientation'], 'Sud')
        self.assertEqual(pan['source_orientation'], 'pose')
        self.assertEqual(cfg['inclinaison_deg'], 10)
        self.assertEqual(cfg['azimut_deg'], 180)

    def test_zone_sans_geometry_garde_le_toit_au_bit_pres(self):
        zone = {'label': 'Pan', 'roofType': 'pitched', 'pitchDeg': 30,
                'facingAzimuthDeg': 135,
                'result': {'count': 10, 'kwc': 5.5, 'areaM2': 20}}
        pan = extract_roof_config(_layout(zone))['pans'][0]
        self.assertEqual(pan['inclinaison_deg'], 30)
        self.assertEqual(pan['azimut_deg'], 135)
        self.assertEqual(pan['orientation'], 'Sud-Est')
        self.assertEqual(pan['source_orientation'], 'toit')
        # Repli ``aspect`` (PVGIS) et ``pitch`` : inchangés eux aussi.
        zone2 = {'pitch': 12, 'aspect': 0,
                 'result': {'count': 4, 'kwc': 2.0}}
        pan2 = extract_roof_config(_layout(zone2))['pans'][0]
        self.assertEqual(pan2['inclinaison_deg'], 12)
        self.assertEqual(pan2['azimut_deg'], 180.0)
        self.assertEqual(pan2['source_orientation'], 'toit')

    def test_geometry_sans_angles_garde_le_toit(self):
        zone = _zone_plate_inclinee()
        zone['geometry'] = {'count': 12, 'kwc': 7.44, 'family': 'south'}
        zone['pitchDeg'] = 5
        zone['facingAzimuthDeg'] = 170
        o = orientation_du_pan(zone)
        self.assertEqual((o['inclinaison_deg'], o['azimut_deg'],
                          o['source_orientation']), (5, 170, 'toit'))

    def test_eastwest_lit_les_deux_faces_posees(self):
        """ACAL911 (réalignement de C-ACAL-081) : une pose est-ouest lit les
        TABLES posées et porte ses deux faces ; sans face déclarée ½ / ½."""
        zone = _zone_plate_inclinee(family='eastwest', azimuthDeg=90,
                                    tiltDeg=10)
        zone['facingAzimuthDeg'] = 180
        o = orientation_du_pan(zone)
        self.assertEqual((o['inclinaison_deg'], o['azimut_deg'],
                          o['source_orientation']), (10, 90, 'pose'))
        self.assertEqual([(f['face'], f['azimut_deg'], f['part'], f['hypothese'])
                          for f in o['faces']],
                         [('E', 90.0, 0.5, True), ('W', 270.0, 0.5, True)])
        pans = extract_roof_config(_layout(zone))['pans']
        self.assertEqual([(p['azimut_deg'], p['inclinaison_deg'], p['source_orientation'])
                          for p in pans], [(90.0, 10, 'pose'), (270.0, 10, 'pose')])
        self.assertEqual(sum(p['nb_panneaux'] for p in pans), 12)

    def test_orientation_principale_pese_la_pose_est_ouest_entiere(self):
        """Critique D7 — 10 kWc est-ouest + 6 kWc sud : le pan principal est
        la pose est-ouest (son kWc ENTIER), décrite par sa face la plus forte."""
        ew = _zone_plate_inclinee(family='eastwest', azimuthDeg=90, kwc=10.0,
                                  panels=[{'cx': i, 'cy': 0, 'face': 'EW'[i % 2]}
                                          for i in range(16)])
        sud = _zone_plate_inclinee(tiltDeg=20, kwc=6.0)
        cfg = extract_roof_config({'zones': [ew, sud]})
        self.assertEqual((cfg['azimut_deg'], cfg['inclinaison_deg']), (90.0, 10))
        self.assertEqual(cfg['orientation_principale'], 'Est')
        # Un pan simple plus fort que la pose est-ouest entière gagne toujours.
        sud['geometry']['kwc'] = 12.0
        self.assertEqual(extract_roof_config({'zones': [ew, sud]})['azimut_deg'], 180)

    def test_resynchroniser_deux_fois_meme_geometrie(self):
        layout = _layout(_zone_plate_inclinee())
        premier = extract_roof_config(copy.deepcopy(layout))
        second = extract_roof_config(copy.deepcopy(layout))
        self.assertEqual(premier, second)

    def test_dry_run_compare_l_annexe_sans_pans_geometry(self):
        """Critique 22/11 (ACAL911) — sans ``_pans_geometry``, la première zone
        est-ouest : toit (≤ 14, envoyés) → tables (niveau 15) ; sud : rien."""
        from apps.ventes.management.commands.acal_dryrun_orientation import _comparer

        zone = _zone_plate_inclinee(family='eastwest', azimuthDeg=90, tiltDeg=10)
        zone['facingAzimuthDeg'] = 180
        self.assertEqual(_comparer(SimpleNamespace(roof_layout=_layout(zone))),
                         [('annexe (sans _pans_geometry)', (0, 180), (10, 90))])
        self.assertEqual(_comparer(SimpleNamespace(roof_layout=_layout(_zone_plate_inclinee()))), [])

    def test_annexe_client_branche_zones_lit_la_pose(self):
        pan = _pan_principal({'zones': [_zone_plate_inclinee()]})
        self.assertEqual(pan['inclinaison_deg'], 10)
        self.assertEqual(pan['azimut_deg'], 180)
        self.assertEqual(pan['roof_type'], 'flat')


def _toit_plat_vide():
    """D-ACAL-149 — toit plat au curseur (22), sans tables ni module."""
    return {'version': 2,
            'outline': [[33.5, -7.6], [33.5, -7.5999], [33.5001, -7.5999], [33.5001, -7.6]],
            'zones': [{'id': 'z1', 'label': 'Terrasse', 'roofType': 'flat', 'pitchDeg': 22,
                       'facingAzimuthDeg': 180,
                       'vertices': [[-7.6, 33.5], [-7.5999, 33.5], [-7.5999, 33.5001],
                                    [-7.6, 33.5001]]}]}


class ToitPlatAuCurseurTest(SimpleTestCase):
    """D-ACAL-149 — la lecture corrigée est OPT-IN ; par défaut, au bit près."""

    def _devis(self, ouvert):
        import datetime

        from apps.ventes.domain.regles_calcul import COUPURE_TOIT_PLAT
        jour = datetime.datetime(*COUPURE_TOIT_PLAT, 9, 0)
        envoi = jour if ouvert else jour - datetime.timedelta(days=1)
        return SimpleNamespace(statut='envoye', date_envoi=envoi, date_creation=None,
                               regles_calcul=1, roof_layout=_toit_plat_vide())

    def test_defaut_lecture_d_avant(self):
        zone = _toit_plat_vide()['zones'][0]
        o = orientation_du_pan(zone)
        self.assertEqual(o['inclinaison_deg'], 22)
        self.assertNotIn('inclinaison_supposee', o)
        cfg = extract_roof_config(_toit_plat_vide())
        self.assertEqual(cfg['inclinaison_deg'], 22)
        self.assertNotIn('suppositions', cfg)

    def test_lecture_corrigee_sans_inclinaison_et_dite(self):
        from apps.ventes.domain.geometrie import SUPPOSITION_INCLINAISON_TOIT_PLAT
        from apps.ventes.services import pans_du_document

        zone = _toit_plat_vide()['zones'][0]
        o = orientation_du_pan(zone, toit_plat_corrige=True)
        self.assertIsNone(o['inclinaison_deg'])
        self.assertTrue(o['inclinaison_supposee'])
        cfg = extract_roof_config(_toit_plat_vide(), toit_plat_corrige=True)
        # D-ACAL-168 (fondateur, 26/11/2026) — la production prend 20°, plus « aucune inclinaison ».
        self.assertEqual(cfg['inclinaison_deg'], 20)
        self.assertEqual(cfg['suppositions'], [SUPPOSITION_INCLINAISON_TOIT_PLAT])
        self.assertNotIn('inclinaison_supposee', cfg['pans'][0])
        self.assertIsNone(pans_du_document(_toit_plat_vide(), toit_plat_corrige=True)[0]['inclinaison_deg'])
        self.assertEqual(pans_du_document(_toit_plat_vide())[0]['inclinaison_deg'], 22)
        from apps.ventes.domain.geometrie import lire_layout
        self.assertEqual(lire_layout(_toit_plat_vide()).toiture['inclinaison_deg'], 22)
        self.assertEqual(lire_layout(_toit_plat_vide(), toit_plat_corrige=True).toiture['suppositions'],
                         [SUPPOSITION_INCLINAISON_TOIT_PLAT])
        # Les tables posées priment toujours, et rien n'est supposé.
        pose = orientation_du_pan(_zone_plate_inclinee(), toit_plat_corrige=True)
        self.assertEqual((pose['inclinaison_deg'], 'inclinaison_supposee' in pose), (10, False))

    def test_annexe_et_planche_concordent_de_part_et_d_autre_de_la_coupure(self):
        """Le cas limite : tous les pans plats, sans tables ni module. Fermé, la
        planche et l'annexe « paramètres du site » disent 22 (ce que le client a
        reçu) ; ouvert, aucune des deux ne dit 22 (planche : pente 0 du toit ;
        annexe : inclinaison omise, la production prend le réglage société)."""
        from apps.calepinage.services.planche import geometrie_de_planche
        from apps.ventes.calepinage_options import parametres_site_publics
        from apps.ventes.domain.regles_calcul import toit_plat_ouvert

        for ouvert in (False, True):
            devis = self._devis(ouvert)
            self.assertIs(toit_plat_ouvert(devis), ouvert)
            annexe = parametres_site_publics(devis, _toit_plat_vide()) or {}
            planche = geometrie_de_planche(_toit_plat_vide(), toit_plat_corrige=toit_plat_ouvert(devis))
            pente = planche['pans'][0]['pente_deg']
            if ouvert:
                self.assertNotIn('inclinaison_deg', annexe)
                self.assertEqual(pente, 0.0)
            else:
                self.assertEqual(annexe.get('inclinaison_deg'), 22.0)
                self.assertEqual(pente, 22.0)


class ToitPlatPartieDeuxTest(SimpleTestCase):
    """D-ACAL-149 (ii) / D-ACAL-168 — création et resynchro : 20° supposés pour la production, dits
    au vendeur, jamais rangés ni imprimés pour le client."""

    def _plat_avec_compte(self):
        layout = _toit_plat_vide()
        layout['zones'][0]['result'] = {'count': 10, 'kwc': 7.1, 'areaM2': 30}  # estimé, sans tables
        return layout

    def test_la_lecture_corrigee_prend_20_degres_nommes(self):
        from apps.ventes.domain.geometrie import SUPPOSITION_INCLINAISON_TOIT_PLAT
        from apps.ventes.domain.regles_calcul import INCLINAISON_TOIT_PLAT_SUPPOSEE_DEG

        self.assertEqual(INCLINAISON_TOIT_PLAT_SUPPOSEE_DEG, 20)
        cfg = extract_roof_config(self._plat_avec_compte(), toit_plat_corrige=True)
        self.assertEqual((cfg['pans'][0]['inclinaison_deg'], cfg['inclinaison_deg']), (20, 20))
        self.assertIn('20°', SUPPOSITION_INCLINAISON_TOIT_PLAT['message'])
        self.assertIn('Posez les panneaux dans le calepinage', SUPPOSITION_INCLINAISON_TOIT_PLAT['message'])
        # Un toit en pente à 22° ne change nulle part.
        pente = _toit_plat_vide()
        pente['zones'][0]['roofType'] = 'pitched'
        for corrige in (False, True):
            cfg_pente = extract_roof_config(pente, toit_plat_corrige=corrige)
            self.assertEqual((cfg_pente['inclinaison_deg'], 'suppositions' in cfg_pente), (22, False))

    def test_la_supposition_n_est_pas_rangee_et_va_au_vendeur(self):
        from apps.ventes.domain.creation_calepinage import phrases_des_suppositions, toiture_sans_suppositions
        from apps.ventes.domain.geometrie import SUPPOSITION_INCLINAISON_TOIT_PLAT

        toiture = extract_roof_config(self._plat_avec_compte(), toit_plat_corrige=True)
        stocke, etude = _calepinage_range(self._plat_avec_compte(), toiture, 7.1)
        self.assertNotIn('suppositions', etude['toiture'])
        self.assertNotIn('suppositions', toiture_sans_suppositions(toiture))
        self.assertEqual(phrases_des_suppositions(toiture), [SUPPOSITION_INCLINAISON_TOIT_PLAT['message']])
        for pan in stocke['_pans_geometry']:
            self.assertFalse({'suppositions', 'inclinaison_supposee'} & set(pan))
        texte = repr(etude) + repr(stocke)
        self.assertNotIn(SUPPOSITION_INCLINAISON_TOIT_PLAT['message'], texte)
        self.assertNotIn('inclinaison_supposee', texte)

    def test_l_annexe_client_n_imprime_pas_l_inclinaison_supposee(self):
        pans = extract_roof_config(_toit_plat_vide(), toit_plat_corrige=True)['pans']  # aucun module posé
        self.assertEqual(pans[0]['inclinaison_deg'], 20)
        self.assertNotIn('inclinaison_deg', _pan_principal({'pans': pans}, toit_plat_corrige=True))
        self.assertEqual(_pan_principal({'pans': pans})['inclinaison_deg'], 20)  # lecture d'avant : inchangée
        poses = extract_roof_config(_layout(_zone_plate_inclinee()), toit_plat_corrige=True)['pans']
        self.assertEqual(_pan_principal({'pans': poses}, toit_plat_corrige=True)['inclinaison_deg'], 10)

    def test_l_etude_electrique_recoit_la_pente_de_la_production(self):
        """Point 5 — un pan plat AVEC modules et sans ``tiltDeg`` : l'étude électrique lit 20°, la
        valeur de la production, jamais 0,0 par accident (``_flottant(None, 0.0)``)."""
        from apps.ventes.electrical_service import _flottant

        pan = extract_roof_config(self._plat_avec_compte(), toit_plat_corrige=True)['pans'][0]
        self.assertGreater(pan['nb_panneaux'], 0)
        self.assertEqual(_flottant(pan['inclinaison_deg'], 0.0), 20.0)


class ZonesEtudeDuDevisTest(TestCase):
    def setUp(self):
        self.co = Company.objects.create(nom='ACAL58', slug='acal58')
        self.client_ = Client.objects.create(company=self.co, nom='Plat')

    def _devis(self, reference, layout, statut=Devis.Statut.BROUILLON):
        return Devis.objects.create(
            company=self.co, client=self.client_, reference=reference,
            statut=statut, roof_layout=layout)

    def test_zones_etude_du_devis_tilt_pose(self):
        layout = _layout(_zone_plate_inclinee())
        stocke, _etude = _calepinage_range(
            layout, extract_roof_config(layout), 7.44)
        devis = self._devis('DEV-ACAL58-001', stocke)
        devis.refresh_from_db()

        zones = zones_etude_du_devis(devis)

        self.assertEqual(len(zones), 1)
        self.assertEqual(zones[0]['tilt'], 10.0)
        self.assertEqual(zones[0]['azimuth'], 0.0)   # PVGIS : 0 = Sud

    def test_devis_cree_d_un_toit_plat_sans_tables_20_degres_dits_au_vendeur(self):
        """D-ACAL-149 (ii) / D-ACAL-168 — la création lit corrigé : production à 20°, la phrase dans
        ``avertissements``, rien de la supposition dans ``etude_params`` ni ``_pans_geometry``."""
        from django.contrib.auth import get_user_model

        from apps.crm.models import Lead
        from apps.ventes.domain.geometrie import SUPPOSITION_INCLINAISON_TOIT_PLAT
        from apps.ventes.services import build_devis_from_layout
        from apps.ventes.tests.test_build_from_layout import seed_catalogue

        seed_catalogue(self.co)
        user = get_user_model().objects.create_user(username='acal149ii', password='x', role_legacy='responsable',
                                                    company=self.co)
        lead = Lead.objects.create(company=self.co, nom='Plat', prenom='Toit', email='plat149@ex.com')
        layout = _toit_plat_vide()
        layout['zones'][0]['result'] = {'count': 10, 'kwc': 5.5, 'areaM2': 30}
        layout['result'] = {'panels': 10, 'kwc': 5.5}
        journal = {}
        devis = build_devis_from_layout(layout=layout, user=user, company=self.co, lead=lead, journal=journal)
        devis.refresh_from_db()
        self.assertIn(SUPPOSITION_INCLINAISON_TOIT_PLAT['message'], journal['avertissements'])
        self.assertEqual([p['inclinaison_deg'] for p in devis.roof_layout['_pans_geometry']], [20])
        self.assertEqual(zones_etude_du_devis(devis)[0]['tilt'], 20.0)
        texte = repr(devis.etude_params) + repr(devis.roof_layout.get('_pans_geometry'))
        for interdit in ('suppositions', 'inclinaison_supposee', SUPPOSITION_INCLINAISON_TOIT_PLAT['message']):
            self.assertNotIn(interdit, texte)

    def test_dry_run_liste_le_devis_envoye_sans_le_reecrire(self):
        layout = _layout(_zone_plate_inclinee())
        ancien = dict(layout)
        # La géométrie STOCKÉE avant ACAL58 : la pente du toit (0°).
        ancien['_pans_geometry'] = [{'label': 'Toit plat', 'kwc': 7.44,
                                     'inclinaison_deg': 0,
                                     'azimut_deg': None}]
        devis = self._devis('DEV-ACAL58-ENV', ancien,
                            statut=Devis.Statut.ENVOYE)
        self._devis('DEV-ACAL58-BRO', dict(ancien))

        sortie = StringIO()
        call_command('acal_dryrun_orientation', stdout=sortie)
        texte = sortie.getvalue()

        self.assertIn('DEV-ACAL58-ENV', texte)
        self.assertNotIn('DEV-ACAL58-BRO', texte)
        self.assertIn('inclinaison 0 → 10', texte)
        self.assertIn('Devis concernés : 1', texte)
        devis.refresh_from_db()
        self.assertEqual(devis.roof_layout['_pans_geometry'][0]
                         ['inclinaison_deg'], 0)

    def test_dry_run_liste_l_annexe_d_un_envoye_sans_pans_geometry(self):
        zone = _zone_plate_inclinee(family='eastwest', azimuthDeg=90, tiltDeg=10)
        zone['facingAzimuthDeg'] = 180
        self._devis('DEV-ACAL911-ENV', _layout(zone), statut=Devis.Statut.ENVOYE)
        self._devis('DEV-ACAL911-SUD', _layout(_zone_plate_inclinee()),
                    statut=Devis.Statut.ENVOYE)

        sortie = StringIO()
        call_command('acal_dryrun_orientation', stdout=sortie)
        texte = sortie.getvalue()

        self.assertIn('DEV-ACAL911-ENV', texte)
        self.assertIn('annexe (sans _pans_geometry) : inclinaison 0 → 10, azimut 180 → 90', texte)
        self.assertNotIn('DEV-ACAL911-SUD', texte)
        self.assertIn('Devis concernés : 1', texte)
