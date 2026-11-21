"""ACAL107 (D-ACAL-2, D-ACAL-23) — retenir une variante l'ÉCRIT comme
conception courante ; le chantier et l'as-built lisent l'instantané figé de
la version ACCEPTÉE en vigueur, sinon la conception courante.

Ce qui est prouvé ici (catalogue tarifé réel, HTTP réel, aucun mock) :

* POST variantes/<A>/retenir/ : Calepinage.roof_layout == A.roof_layout, une
  version « Variante « A » retenue », A.retenue ; retenir A une seconde fois
  ⇒ aucune nouvelle version ;
* « Générer le devis » puis « Resynchroniser » chiffrent la RETENUE ;
* l'as-built lit la conception (plus la variante en parallèle) ;
* le chantier lit l'instantané V1 tant que V2 n'est pas acceptée, puis V2 ;
* l'import d'un projet restaure la retenue SANS réécrire la conception ;
* la bascule est journalisée AVEC son auteur.

Run :
    python manage.py test apps.calepinage.tests.test_acal_retenir_conception -v2
"""

from unittest import mock

from django.contrib.contenttypes.models import ContentType
from django.test import SimpleTestCase

from apps.calepinage.models import (
    Calepinage, CalepinageVariante, CalepinageVersion,
)
from apps.calepinage.selectors import calepinage_retenu_pour_devis
from apps.calepinage.services import asbuilt
from apps.calepinage.services.layout import enregistrer_layout
from apps.calepinage.services.variantes import creer_variante
from apps.records.models import Activity
from apps.ventes.models import Devis

from .test_api_liste import BaseApiCalepinage, url_detail


def _toit(panneaux):
    return {
        'areas': [{
            'vertices': [[0, 0], [10, 0], [10, 6], [0, 6]],
            'obstacles': [], 'roofType': 'flat', 'pitch': 10,
            'azimuth': 180,
        }],
        'scenario': 'reseau',
        'result': {'panels': panneaux, 'kwc': round(panneaux * 0.55, 2),
                   'annualKwh': 10800, 'savings': 9200},
    }


def _panneaux_du_devis(devis_id):
    devis = Devis.objects.get(pk=devis_id)
    return sum(int(li.quantite) for li in devis.lignes.all()
               if 'panneau' in (li.designation or '').lower())


class RetenirConceptionTest(BaseApiCalepinage):
    def setUp(self):
        super().setUp()
        from apps.ventes.tests.test_from_layout_endpoint import seed_catalogue
        seed_catalogue(self.company)
        self.calepinage = Calepinage.objects.create(
            company=self.company, lead_id=self.lead.pk, titre='QA-ACAL-VAR')
        enregistrer_layout(self.calepinage, _toit(10), user=self.user)
        self.a = creer_variante(self.calepinage, nom='A',
                                roof_layout=_toit(14), user=self.user)

    def _retenir(self, variante):
        reponse = self.api.post(
            f'{url_detail(self.calepinage.pk)}variantes/{variante.pk}/'
            'retenir/', {}, format='json')
        self.assertEqual(reponse.status_code, 200, reponse.data)
        self.calepinage.refresh_from_db()
        return reponse

    def test_retenir_ecrit_la_conception_et_versionne(self):
        self._retenir(self.a)
        self.a.refresh_from_db()
        self.assertTrue(self.a.retenue)
        self.assertEqual(self.calepinage.roof_layout, self.a.roof_layout)
        versions = CalepinageVersion.objects.filter(
            calepinage=self.calepinage, libelle='Variante « A » retenue')
        self.assertEqual(versions.count(), 1)
        avant = CalepinageVersion.objects.filter(
            calepinage=self.calepinage).count()
        self._retenir(self.a)
        self.assertEqual(CalepinageVersion.objects.filter(
            calepinage=self.calepinage).count(), avant)
        # Rouvrir l'atelier : le document EST la variante.
        reponse = self.api.get(f'{url_detail(self.calepinage.pk)}layout/')
        self.assertEqual(reponse.data['roof_layout'], self.a.roof_layout)

    def test_generer_chiffre_la_retenue(self):
        self._retenir(self.a)
        reponse = self.api.post(
            f'{url_detail(self.calepinage.pk)}generer-devis/', {},
            format='json')
        self.assertEqual(reponse.status_code, 201, reponse.data)
        self.assertEqual(_panneaux_du_devis(reponse.data['devis']), 14)

    def test_resynchroniser_chiffre_la_retenue(self):
        reponse = self.api.post(
            f'{url_detail(self.calepinage.pk)}generer-devis/', {},
            format='json')
        self.assertEqual(reponse.status_code, 201, reponse.data)
        devis_id = reponse.data['devis']
        self.assertEqual(_panneaux_du_devis(devis_id), 10)
        self._retenir(self.a)
        reponse = self.api.post(
            f'{url_detail(self.calepinage.pk)}sync-devis/', {},
            format='json')
        self.assertEqual(reponse.status_code, 200, reponse.data)
        self.assertEqual(_panneaux_du_devis(devis_id), 14)

    def test_asbuilt_lit_la_conception(self):
        self._retenir(self.a)
        # ACON25 (D-ACAL-2) : un enregistrement ultérieur de l'atelier est
        # recopié dans la variante RETENUE (résultat périmé) ; l'as-built lit
        # la CONCEPTION.
        plus_tard = {'version': 2, 'zones': [
            {'id': 'z1', 'label': 'Pan Sud',
             'geometry': {'count': 9, 'azimuthDeg': 180, 'tiltDeg': 15}}]}
        enregistrer_layout(self.calepinage, plus_tard, user=self.user)
        self.a.refresh_from_db()
        self.calepinage.refresh_from_db()
        self.assertEqual(self.a.roof_layout, self.calepinage.roof_layout)
        self.assertEqual(self.a.roof_layout['zones'][0]['label'], 'Pan Sud')
        self.assertIsNone(self.a.resultat)
        prevus, source = asbuilt._pans_prevus(self.calepinage)
        self.assertEqual(source, asbuilt.SOURCE_CALEPINAGE)
        self.assertEqual(sum(p['modules'] for p in prevus), 9)

    def _chaine_v1_v2(self):
        v1 = Devis.objects.create(
            company=self.company, client=self.client_a,
            reference='DEV-ACAL107-V1', statut=Devis.Statut.ACCEPTE,
            roof_layout=_toit(10), is_active=False)
        v2 = Devis.objects.create(
            company=self.company, client=self.client_a,
            reference='DEV-ACAL107-V2', statut=Devis.Statut.BROUILLON,
            roof_layout=_toit(14))
        Devis.objects.filter(pk=v1.pk).update(superseded_by=v2)
        Calepinage.objects.filter(pk=self.calepinage.pk).update(devis=v2)
        self.calepinage.refresh_from_db()
        return v1, v2

    def test_chantier_lit_l_instantane_v1_tant_que_v2_non_acceptee(self):
        self._retenir(self.a)
        _v1, v2 = self._chaine_v1_v2()
        document, source = asbuilt.conception_du_chantier(self.calepinage)
        self.assertEqual(source, asbuilt.SOURCE_DEVIS_ACCEPTE)
        self.assertEqual(document['result']['panels'], 10)
        bloc = calepinage_retenu_pour_devis(v2.pk, self.company)
        self.assertEqual(bloc['nb_modules'], 10)

    def test_chantier_bascule_sur_v2_a_son_acceptation(self):
        self._retenir(self.a)
        _v1, v2 = self._chaine_v1_v2()
        Devis.objects.filter(pk=v2.pk).update(statut=Devis.Statut.ACCEPTE)
        document, source = asbuilt.conception_du_chantier(self.calepinage)
        self.assertEqual(source, asbuilt.SOURCE_DEVIS_ACCEPTE)
        self.assertEqual(document['result']['panels'], 14)
        bloc = calepinage_retenu_pour_devis(v2.pk, self.company)
        self.assertEqual(bloc['nb_modules'], 14)

    def test_import_restaure_sans_reecrire(self):
        from apps.calepinage.services.export_projet import importer_projet

        from .test_calx370_projet_json import fichier

        document = fichier()
        self.assertIn('outline', document['roof_layout'])
        resume = importer_projet(document, self.company,
                                 client_id=self.client_a.pk)
        copie = Calepinage.objects.get(pk=resume['calepinage'])
        retenue = CalepinageVariante.objects.get(calepinage=copie,
                                                 retenue=True)
        self.assertNotIn('outline', retenue.roof_layout)
        # La conception importée reste LE document (jamais la variante).
        self.assertIn('outline', copie.roof_layout)

    def test_retenue_journalisee_avec_auteur(self):
        self._retenir(self.a)
        entree = (Activity.objects
                  .filter(content_type=ContentType.objects.get_for_model(
                      Calepinage), object_id=self.calepinage.pk,
                      field='variante')
                  .order_by('-id').first())
        self.assertIsNotNone(entree)
        self.assertEqual(entree.new_value, 'A')
        self.assertEqual(entree.created_by_id, self.user.pk)


# ── ACAL588 — le plan de pose (SVG) du calepinage retenu d'un devis ─────────

_CHEMIN = 'apps.calepinage.selectors_chantier'


def _calepinage_de_pose():
    from .acal_livrables_helpers import (
        LAYOUT_PLANCHE_SIMULABLE, calepinage_simule_reel,
    )
    from .test_cal173_empreinte import FauxCalepinage

    simule = calepinage_simule_reel(LAYOUT_PLANCHE_SIMULABLE)
    faux = FauxCalepinage(layout_hash='b' * 64,
                          roof_layout=simule.roof_layout)
    faux.resultat = simule.resultat
    return faux


class PlanDePoseDuDevisTest(SimpleTestCase):
    """Le sélecteur rend le plan vendu, ou dit pourquoi il ne le rend pas."""

    def _appeler(self, calepinage, *, retenu=True, conception=None):
        from apps.calepinage import selectors_chantier
        from apps.calepinage.services.asbuilt import SOURCE_CALEPINAGE
        from .acal_livrables_helpers import patch_materiel

        conception = conception or (calepinage.roof_layout,
                                    SOURCE_CALEPINAGE)
        with mock.patch(f'{_CHEMIN}.calepinage_retenu_pour_devis',
                        return_value={'id': 41} if retenu else None), \
                mock.patch(f'{_CHEMIN}.calepinage_du_devis',
                           return_value=calepinage), \
                mock.patch('apps.calepinage.services.asbuilt.'
                           'conception_du_chantier',
                           return_value=conception), \
                patch_materiel():
            return selectors_chantier.plan_pose_svg_pour_devis(7, object())

    def test_un_projet_retenu_rend_le_svg_et_son_empreinte(self):
        calepinage = _calepinage_de_pose()
        plan = self._appeler(calepinage)
        self.assertEqual(plan['calepinage_id'], calepinage.pk)
        self.assertIn('<svg', plan['svg'])
        self.assertEqual(plan['empreinte'], 'b' * 64)
        self.assertEqual(plan['motif'], '')
        for interdit in ('prix', 'mad', 'montant'):
            self.assertNotIn(interdit, plan['svg'].lower())

    def test_conception_modifiee_apres_acceptation_ne_rend_pas_de_svg(self):
        from apps.calepinage.services.asbuilt import SOURCE_DEVIS_ACCEPTE
        from apps.calepinage.selectors_chantier import (
            MOTIF_CONCEPTION_CHANGEE,
        )

        calepinage = _calepinage_de_pose()
        vendu = {'version': 2, 'zones': []}
        plan = self._appeler(calepinage,
                             conception=(vendu, SOURCE_DEVIS_ACCEPTE))
        self.assertIsNone(plan['svg'])
        self.assertEqual(plan['motif'], MOTIF_CONCEPTION_CHANGEE)
        self.assertEqual(plan['empreinte'], 'b' * 64)

    def test_conception_inchangee_depuis_l_acceptation_rend_le_svg(self):
        from apps.calepinage.services.asbuilt import SOURCE_DEVIS_ACCEPTE

        calepinage = _calepinage_de_pose()
        plan = self._appeler(
            calepinage,
            conception=(calepinage.roof_layout, SOURCE_DEVIS_ACCEPTE))
        self.assertIsNotNone(plan['svg'])
        self.assertEqual(plan['motif'], '')

    def test_document_sans_geometrie_nomme_son_motif(self):
        from apps.calepinage.services.planche import PlancheRefusee

        calepinage = _calepinage_de_pose()
        calepinage.roof_layout = {'version': 2, 'zones': []}
        plan = self._appeler(calepinage)
        self.assertIsNone(plan['svg'])
        with self.assertRaises(PlancheRefusee) as capture:
            from apps.calepinage.services.planche import geometrie_de_planche
            geometrie_de_planche({'version': 2, 'zones': []})
        self.assertEqual(plan['motif'], str(capture.exception))

    def test_sans_retenue_ou_autre_societe_rien(self):
        self.assertIsNone(self._appeler(_calepinage_de_pose(),
                                        retenu=False))


# ── ACAL596 — les points de contrôle de pose d'un calepinage retenu ─────────

def _ligne(module, pan, chaine, mppt, onduleur=1):
    return {'module': module, 'pan': pan, 'chaine': chaine, 'mppt': mppt,
            'onduleur': onduleur, 'source': 'automatique'}


def _deux_chaines():
    return ([_ligne('z1#%d' % n, 'Sud', 1, 1) for n in range(1, 13)]
            + [_ligne('z1#%d' % n, 'Sud', 2, 2) for n in range(13, 25)]
            + [_ligne('z1#25', 'Sud', None, None, None)])


class PointsDeControlePoseTest(SimpleTestCase):
    def _appeler(self, affectation, *, systeme=True, retenu=True):
        from types import SimpleNamespace

        from apps.calepinage import selectors_chantier

        stub = SimpleNamespace(pk=41)
        choisi = (SimpleNamespace(libelle='Système A', code='SYS-A')
                  if systeme else None)
        with mock.patch(f'{_CHEMIN}.calepinage_retenu_pour_devis',
                        return_value={'id': 41} if retenu else None), \
                mock.patch(f'{_CHEMIN}.calepinage_du_devis',
                           return_value=stub), \
                mock.patch(f'{_CHEMIN}.resultat_servi',
                           return_value={'electrique': {
                               'affectation': affectation}}), \
                mock.patch('apps.calepinage.services.fixation.'
                           'resoudre_systeme', return_value=(choisi, [])):
            return selectors_chantier.points_de_controle_pose(7, object())

    def test_deux_chaines_et_un_systeme_donnent_trois_points_en_ordre(self):
        rendu = self._appeler(_deux_chaines())
        self.assertEqual(rendu['calepinage_id'], 41)
        self.assertEqual(rendu['omissions'], [])
        self.assertEqual([p['code'] for p in rendu['points']],
                         ['systeme_fixation', 'chaine', 'chaine'])
        self.assertEqual(rendu['points'][0]['libelle'],
                         'Système de fixation : Système A (SYS-A)')
        self.assertEqual(
            rendu['points'][1]['libelle'],
            'Chaîne 1 : 12 modules, du n°1 au n°12 du pan Sud, dans '
            'l\'ordre de l\'affectation publiée ; entrée MPPT 1 ; '
            'onduleur 1')
        self.assertIn('du n°13 au n°24 du pan Sud',
                      rendu['points'][2]['libelle'])
        self.assertIn('entrée MPPT 2', rendu['points'][2]['libelle'])
        self.assertEqual(rendu['points'][1]['source'], 'affectation')

    def test_l_ordre_est_celui_de_l_affectation_pas_un_tri(self):
        affectation = ([_ligne('z1#13', 'Sud', 2, 2)]
                       + [_ligne('z1#1', 'Sud', 1, 1)])
        libelles = [p['libelle'] for p in self._appeler(
            affectation, systeme=False)['points']]
        self.assertTrue(libelles[0].startswith('Chaîne 2'))
        self.assertTrue(libelles[1].startswith('Chaîne 1'))

    def test_sans_systeme_une_omission_nommee(self):
        rendu = self._appeler(_deux_chaines(), systeme=False)
        self.assertEqual(rendu['omissions'], [
            'Aucun système de fixation retenu : rien à contrôler sur la '
            'fixation'])
        self.assertEqual(len(rendu['points']), 2)

    def test_sans_chaine_une_omission_nommee(self):
        rendu = self._appeler([_ligne('z1#1', 'Sud', None, None, None)])
        self.assertEqual(rendu['omissions'], [
            'Électrique non chaîné : aucun ordre de chaîne à contrôler'])
        self.assertEqual([p['code'] for p in rendu['points']],
                         ['systeme_fixation'])

    def test_sans_retenue_ou_autre_societe_rien(self):
        self.assertIsNone(self._appeler([], retenu=False))
