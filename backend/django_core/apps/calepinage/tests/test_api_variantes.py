"""CAL21 — les variantes : CRUD, bascule idempotente, comparatif.

Ce qui est prouvé ici :

* le CRUD de variante vit sous LA seule forme d'URL du module
  (``/calepinages/<pk>/variantes/…``) et n'écrit JAMAIS ``retenue`` ;
* ``retenir`` bascule atomiquement — et deux appels portant la MÊME
  ``Idempotency-Key`` ne basculent qu'UNE fois ;
* la variante RETENUE ne se supprime pas (sinon : zéro option choisie) ;
* le comparatif a EXACTEMENT les clés de premier niveau de
  ``contract_samples/variantes_comparer.json`` ;
* une variante NON SIMULÉE le dit et toutes ses grandeurs de production valent
  ``null`` — jamais ``0`` ;
* l'écart est relatif à la retenue (``0`` sur elle) et vaut ``null`` quand il
  n'y a rien à quoi se comparer (une seule variante) ;
* une variante d'un autre calepinage est introuvable (404).

Run :
    python manage.py test apps.calepinage.tests.test_api_variantes -v2
"""
import json
import pathlib

from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import SimpleTestCase
from apps.calepinage.models import Calepinage, CalepinageVariante
from apps.calepinage.services.variantes import retenir_variante
from apps.calepinage.tests._m0_en_attente import affirmer_non_servies, sans

from .test_api_liste import BaseApiCalepinage, url_detail

CONTRAT = json.loads(
    (pathlib.Path(__file__).resolve().parents[1] / 'contract_samples'
     / 'variantes_comparer.json').read_text(encoding='utf-8'))

RESULTAT_SIMULE = {
    'total_modules': 12, 'kwc': 8.64, 'total_optimal': 12, 'optimal': True,
    'methode': 'programmation_dynamique', 'version_moteur': 'essai',
    'entree_hash': 'a' * 64,
    'production': {'p50_kwh': 13000.0, 'p75_kwh': 12400.0, 'p90_kwh': 11900.0,
                   'performance_ratio': 0.8,
                   'specific_yield_kwh_kwc': 1504.6,
                   'self_consumption_rate': 0.62},
}
RESULTAT_SIMULE_2 = dict(RESULTAT_SIMULE, total_modules=10, kwc=7.2,
                         production=dict(RESULTAT_SIMULE['production'],
                                         p50_kwh=10400.0))

#: ACON26 — on ne retient qu'une variante DESSINÉE.
DESSIN = {'zones': [{'id': 'z1', 'panels': 12}]}
#: Lot 2 critique #30 — simulée, ``total_modules``/``kwc`` se LISENT dans la
#: conception : la retenue des écarts porte un dessin qui pose ses 12 modules.
DESSIN_12_MODULES = {'zones': [{'id': 'z1', 'geometry': {'count': 12, 'kwc': 8.64}}]}


def url_variantes(pk):
    return f'{url_detail(pk)}variantes/'


def url_variante(pk, vid):
    return f'{url_detail(pk)}variantes/{vid}/'


def url_retenir(pk, vid):
    return f'{url_detail(pk)}variantes/{vid}/retenir/'


def url_comparer(pk):
    return f'{url_detail(pk)}comparer/'


class BaseVariantes(BaseApiCalepinage):
    def setUp(self):
        super().setUp()
        self.calepinage = Calepinage.objects.create(
            company=self.company, lead_id=self.lead.pk, titre='Villa Anfa')


class CrudVarianteTest(BaseVariantes):
    def test_creation_et_liste(self):
        reponse = self.api.post(url_variantes(self.calepinage.pk),
                                {'nom': 'Portrait plein sud'}, format='json')
        self.assertEqual(reponse.status_code, 201, reponse.data)
        self.assertFalse(reponse.data['retenue'])
        liste = self.api.get(url_variantes(self.calepinage.pk))
        self.assertEqual(liste.status_code, 200)
        self.assertEqual([v['nom'] for v in liste.data],
                         ['Portrait plein sud'])

    def test_creation_sans_nom_refusee_en_nommant_le_champ(self):
        reponse = self.api.post(url_variantes(self.calepinage.pk), {},
                                format='json')
        self.assertEqual(reponse.status_code, 400)
        self.assertIn('nom', reponse.data)

    def test_edition_ne_peut_pas_ecrire_retenue(self):
        variante = CalepinageVariante.objects.create(
            company=self.company, calepinage=self.calepinage, nom='A')
        reponse = self.api.patch(
            url_variante(self.calepinage.pk, variante.pk),
            {'nom': 'A bis', 'retenue': True}, format='json')
        self.assertEqual(reponse.status_code, 200, reponse.data)
        variante.refresh_from_db()
        self.assertEqual(variante.nom, 'A bis')
        self.assertFalse(variante.retenue)

    def test_edition_nom_publie_sans_nul(self):
        """ENF11 (fuzz 01/11) : le nom d'une variante est un texte strict
        publié sans NUL ; un NUL reste refusé 400 en nommant `nom`."""
        from core.champs_stricts import ChaineStricte
        from apps.calepinage.serializers import CalepinageVarianteSerializer
        self.assertIsInstance(
            CalepinageVarianteSerializer().fields['nom'], ChaineStricte)
        variante = CalepinageVariante.objects.create(
            company=self.company, calepinage=self.calepinage, nom='A')
        reponse = self.api.patch(
            url_variante(self.calepinage.pk, variante.pk),
            {'nom': 'a\x00b'}, format='json')
        self.assertEqual(reponse.status_code, 400, reponse.data)
        self.assertIn('nom', reponse.data)

    def test_edition_du_layout_recalcule_l_empreinte(self):
        variante = CalepinageVariante.objects.create(
            company=self.company, calepinage=self.calepinage, nom='A')
        reponse = self.api.patch(
            url_variante(self.calepinage.pk, variante.pk),
            {'roof_layout': {'result': {'panels': 9}}}, format='json')
        self.assertEqual(reponse.status_code, 200, reponse.data)
        variante.refresh_from_db()
        self.assertEqual(len(variante.layout_hash), 64)

    def test_edition_multipart_refusee_en_415(self):
        """api-fuzz (vague 10) — un PATCH multipart (« resultat » en fichier)
        plantait en 500 à l'écriture JSON : le corps est JSON seul → 415."""
        variante = CalepinageVariante.objects.create(
            company=self.company, calepinage=self.calepinage, nom='A')
        reponse = self.api.patch(
            url_variante(self.calepinage.pk, variante.pk),
            {'nom': 'B', 'resultat': SimpleUploadedFile('resultat', b'None')},
            format='multipart')
        self.assertEqual(reponse.status_code, 415)
        variante.refresh_from_db()
        self.assertEqual(variante.nom, 'A')

    def test_suppression_de_la_retenue_refusee(self):
        variante = CalepinageVariante.objects.create(
            company=self.company, calepinage=self.calepinage, nom='A',
            roof_layout=DESSIN)
        retenir_variante(variante)
        reponse = self.api.delete(
            url_variante(self.calepinage.pk, variante.pk))
        # ENF11 — refus d'ÉTAT (requête conforme) : 409, même corps.
        self.assertEqual(reponse.status_code, 409)
        self.assertIn('retenue', reponse.data)
        self.assertTrue(CalepinageVariante.objects.filter(
            pk=variante.pk).exists())

    def test_suppression_d_une_non_retenue(self):
        variante = CalepinageVariante.objects.create(
            company=self.company, calepinage=self.calepinage, nom='A')
        reponse = self.api.delete(
            url_variante(self.calepinage.pk, variante.pk))
        self.assertEqual(reponse.status_code, 204)
        self.assertFalse(CalepinageVariante.objects.filter(
            pk=variante.pk).exists())

    def test_variante_d_un_autre_calepinage_introuvable(self):
        autre = Calepinage.objects.create(
            company=self.company, lead_id=self.lead.pk, titre='Autre')
        variante = CalepinageVariante.objects.create(
            company=self.company, calepinage=self.calepinage, nom='A')
        reponse = self.api.get(url_variante(autre.pk, variante.pk))
        self.assertEqual(reponse.status_code, 404)


class RetenirTest(BaseVariantes):
    def setUp(self):
        super().setUp()
        self.a = CalepinageVariante.objects.create(
            company=self.company, calepinage=self.calepinage, nom='A',
            roof_layout=DESSIN)
        self.b = CalepinageVariante.objects.create(
            company=self.company, calepinage=self.calepinage, nom='B',
            roof_layout=DESSIN)
        retenir_variante(self.a)

    def test_bascule(self):
        reponse = self.api.post(url_retenir(self.calepinage.pk, self.b.pk), {},
                                format='json')
        self.assertEqual(reponse.status_code, 200, reponse.data)
        self.a.refresh_from_db()
        self.b.refresh_from_db()
        self.assertFalse(self.a.retenue)
        self.assertTrue(self.b.retenue)

    def test_deux_appels_meme_cle_ne_basculent_qu_une_fois(self):
        entetes = {'HTTP_IDEMPOTENCY_KEY': 'cle-essai-21'}
        self.api.post(url_retenir(self.calepinage.pk, self.b.pk), {},
                      format='json', **entetes)
        # Entre les deux appels, on rebascule À LA MAIN sur A : si le second
        # appel n'était pas idempotent, il re-basculerait sur B.
        retenir_variante(self.a)
        reponse = self.api.post(url_retenir(self.calepinage.pk, self.b.pk), {},
                                format='json', **entetes)
        self.assertEqual(reponse.status_code, 200, reponse.data)
        self.a.refresh_from_db()
        self.b.refresh_from_db()
        self.assertTrue(self.a.retenue)
        self.assertFalse(self.b.retenue)

    def test_sans_permission_d_ecriture_403(self):
        reponse = self.api_sans.post(
            url_retenir(self.calepinage.pk, self.b.pk), {}, format='json')
        self.assertEqual(reponse.status_code, 403)


class ComparerTest(BaseVariantes):
    def test_forme_conforme_au_contrat(self):
        variante = CalepinageVariante.objects.create(
            company=self.company, calepinage=self.calepinage, nom='A',
            roof_layout=DESSIN, resultat=RESULTAT_SIMULE)
        retenir_variante(variante)
        reponse = self.api.get(url_comparer(self.calepinage.pk))
        self.assertEqual(reponse.status_code, 200, reponse.data)
        # ACAL7 (M0) a posé les colonnes de fraîcheur avant leurs
        # producteurs : chaque tâche nommée sert sa clé et retire l'entrée.
        # ACAL111 (simulation_perimee) et ACAL112 (source_mesures) sont
        # livrées : plus rien en attente.
        en_attente = {}
        affirmer_non_servies(self, reponse.data, en_attente)
        exemple = sans(CONTRAT['exemple'], en_attente)
        self.assertEqual(set(reponse.data), set(exemple))
        # ACAL978 — ``lignes[0]`` est la conception COURANTE, la variante
        # suit : les deux lignes portent la carte complète du contrat.
        courante, ligne_variante = reponse.data['lignes']
        self.assertIsNone(courante['id'])
        self.assertTrue(courante['courante'])
        self.assertEqual(ligne_variante['id'], variante.pk)
        self.assertFalse(ligne_variante['courante'])
        for rang, ligne in enumerate((courante, ligne_variante)):
            self.assertEqual(set(ligne), set(exemple['lignes'][rang]))
            self.assertEqual(set(ligne['production']),
                             set(exemple['lignes'][rang]['production']))

    def test_une_seule_variante_les_ecarts_valent_null(self):
        """ACAL978 — une variante unique se compare à la courante : la
        courante NON simulée et sans dessin porte des écarts ``null`` (jamais
        ``0``), la retenue un écart de production MESURÉ, nul contre
        elle-même."""
        variante = CalepinageVariante.objects.create(
            company=self.company, calepinage=self.calepinage, nom='A',
            roof_layout=DESSIN, resultat=RESULTAT_SIMULE)
        retenir_variante(variante)
        courante, ligne_variante = self.api.get(
            url_comparer(self.calepinage.pk)).data['lignes']
        self.assertTrue(courante['courante'])
        self.assertIsNone(courante['ecart_modules'])
        self.assertIsNone(courante['ecart_kwc'])
        self.assertIsNone(courante['ecart_p50_kwh'])
        self.assertEqual(ligne_variante['id'], variante.pk)
        self.assertEqual(ligne_variante['ecart_p50_kwh'], 0.0)

    def test_sans_variante_les_ecarts_valent_null(self):
        """Rien à quoi se comparer (la courante seule) ⇒ écarts ``null``."""
        lignes = self.api.get(url_comparer(self.calepinage.pk)).data['lignes']
        self.assertEqual(len(lignes), 1)
        self.assertTrue(lignes[0]['courante'])
        self.assertIsNone(lignes[0]['ecart_modules'])
        self.assertIsNone(lignes[0]['ecart_kwc'])
        self.assertIsNone(lignes[0]['ecart_p50_kwh'])

    def test_ecarts_relatifs_a_la_retenue(self):
        retenue = CalepinageVariante.objects.create(
            company=self.company, calepinage=self.calepinage, nom='A',
            roof_layout=DESSIN_12_MODULES, resultat=RESULTAT_SIMULE)
        retenir_variante(retenue)
        CalepinageVariante.objects.create(
            company=self.company, calepinage=self.calepinage, nom='B',
            resultat=RESULTAT_SIMULE_2)
        lignes = {ligne['nom']: ligne
                  for ligne in self.api.get(
                      url_comparer(self.calepinage.pk)).data['lignes']}
        self.assertEqual(lignes['A']['ecart_modules'], 0)
        self.assertEqual(lignes['B']['ecart_modules'], -2)
        self.assertEqual(lignes['B']['ecart_p50_kwh'], -2600.0)

    def test_variante_non_simulee_dit_null_jamais_zero(self):
        retenue = CalepinageVariante.objects.create(
            company=self.company, calepinage=self.calepinage, nom='A',
            roof_layout=DESSIN, resultat=RESULTAT_SIMULE)
        retenir_variante(retenue)
        CalepinageVariante.objects.create(
            company=self.company, calepinage=self.calepinage, nom='B')
        lignes = {ligne['nom']: ligne
                  for ligne in self.api.get(
                      url_comparer(self.calepinage.pk)).data['lignes']}
        self.assertFalse(lignes['B']['simulee'])
        for cle, valeur in lignes['B']['production'].items():
            if cle == 'pertes_dominantes':
                # Une LISTE, jamais ``None`` : « aucun poste dominant » se
                # lit, « pas de liste » ne se lit pas (contrat CAL3/CAL145).
                self.assertEqual(valeur, [])
                continue
            self.assertIsNone(valeur, cle)
        self.assertIsNone(lignes['B']['ecart_p50_kwh'])

    def test_sans_permission_403(self):
        reponse = self.api_sans.get(url_comparer(self.calepinage.pk))
        self.assertEqual(reponse.status_code, 403)


# ── ACAL594 — une variante par module du stock ─────────────────────────────

CONTRAT_PAR_MODULE = json.loads(
    (pathlib.Path(__file__).resolve().parents[1] / 'contract_samples'
     / 'calepinage_variantes_par_module.json').read_text(encoding='utf-8'))


def _module_a():
    return {'id': 'produit-1', 'produitId': 1, 'libelle': 'A 460',
            'longueurMm': 2278.0, 'largeurMm': 1134.0, 'epaisseurMm': None,
            'poidsKg': None, 'pmaxWc': 460.0, 'source': 'fiche produit'}


def _layout_sur_a():
    return {
        'modules': [_module_a()], 'panelWatt': 460.0,
        'zones': [
            {'id': 'z1', 'geometry': {'count': 10, 'kwc': 4.6,
                                      'moduleId': 'produit-1'}},
            {'id': 'z2', 'geometry': {'count': 5, 'kwc': 2.3,
                                      'moduleId': 'produit-1'}}],
        'result': {'kwc': 6.9, 'annualKwh': 9999.0},
    }


class VariantePourModuleTest(SimpleTestCase):
    """La réécriture du document, sans base (service pur)."""

    def test_memes_cotes_valide_telle_quelle_et_kwc_recalcule(self):
        from apps.calepinage.services.variantes_modules import (
            variante_pour_module)

        layout = _layout_sur_a()
        b = dict(_module_a(), id='produit-2', produitId=2, libelle='B 430',
                 pmaxWc=430.0)
        document, a_repaver = variante_pour_module(layout, b)
        self.assertFalse(a_repaver)
        self.assertEqual(
            [z['geometry']['moduleId'] for z in document['zones']],
            ['produit-2', 'produit-2'])
        self.assertAlmostEqual(document['zones'][0]['geometry']['kwc'], 4.3)
        self.assertEqual(document['panelWatt'], 430.0)
        self.assertEqual(document['modules'], [b])
        self.assertAlmostEqual(document['result']['kwc'], 6.45)
        self.assertNotIn('annualKwh', document['result'])
        # l'original n'est pas touché
        self.assertEqual(layout['zones'][0]['geometry']['moduleId'],
                         'produit-1')
        self.assertEqual(layout['result']['annualKwh'], 9999.0)

    def test_cotes_differentes_a_repaver(self):
        from apps.calepinage.services.variantes_modules import (
            variante_pour_module)

        c = dict(_module_a(), id='produit-3', longueurMm=2384.0,
                 largeurMm=1303.0)
        _document, a_repaver = variante_pour_module(_layout_sur_a(), c)
        self.assertTrue(a_repaver)

    def test_un_pan_sans_module_est_a_repaver(self):
        from apps.calepinage.services.variantes_modules import (
            variante_pour_module)

        layout = {'zones': [{'id': 'z1', 'geometry': {'count': 4}}]}
        document, a_repaver = variante_pour_module(layout, _module_a())
        self.assertTrue(a_repaver)
        self.assertAlmostEqual(document['zones'][0]['geometry']['kwc'], 1.84)


class VariantesParModuleTest(BaseVariantes):
    """``POST variantes-par-module/`` (base de données)."""

    def setUp(self):
        super().setUp()
        self.a = self._module('A 460', 460.0, 2278, 1134)
        self.b = self._module('B 430', 430.0, 2278, 1134)
        self.c = self._module('C 600', 600.0, 2384, 1303)
        layout = _layout_sur_a()
        layout['modules'][0].update(id='produit-%s' % self.a.pk,
                                    produitId=self.a.pk)
        for zone in layout['zones']:
            zone['geometry']['moduleId'] = 'produit-%s' % self.a.pk
        self.calepinage.roof_layout = layout
        self.calepinage.save()

    def _module(self, nom, wc, longueur, largeur):
        from decimal import Decimal

        from apps.stock.models import FicheTechnique, Produit

        produit = Produit.objects.create(
            company=self.company, nom=nom, sku='ACAL594-%s' % nom,
            prix_achat=Decimal('999'), prix_vente=Decimal('1500'),
            quantite_stock=1)
        FicheTechnique.objects.create(
            company=self.company, produit=produit, type_fiche='module',
            vmp_v=41.4, voc_v=49.3, isc_a=18.59, imp_a=17.59, pmax_wc=wc,
            longueur_mm=longueur, largeur_mm=largeur)
        return produit

    def _poster(self, modules, api=None):
        return (api or self.api).post(
            f'{url_detail(self.calepinage.pk)}variantes-par-module/',
            {'modules': modules}, format='json')

    def test_deux_modules_deux_variantes_nommees(self):
        reponse = self._poster(['produit-%s' % self.b.pk,
                                'produit-%s' % self.c.pk])
        self.assertEqual(reponse.status_code, 201, reponse.data)
        noms = [v['nom'] for v in reponse.data['variantes']]
        self.assertEqual(noms, ['Module B 430', 'Module C 600 — à re-poser'])
        self.assertEqual([v['a_repaver'] for v in reponse.data['variantes']],
                         [False, True])
        variante_b = CalepinageVariante.objects.get(
            pk=reponse.data['variantes'][0]['id'])
        document = variante_b.roof_layout
        self.assertEqual(document['panelWatt'], 430.0)
        self.assertAlmostEqual(document['zones'][0]['geometry']['kwc'], 4.3)
        self.assertEqual(document['zones'][0]['geometry']['moduleId'],
                         'produit-%s' % self.b.pk)
        self.assertIsNone(variante_b.resultat)
        self.assertEqual(set(reponse.data),
                         set(CONTRAT_PAR_MODULE['exemple']))

    def test_fiche_incomplete_ou_inconnue_refusee_en_nommant_modules(self):
        for modules in (['produit-999999'], 'produit-1', []):
            with self.subTest(modules=modules):
                reponse = self._poster(modules)
                self.assertEqual(reponse.status_code, 400, reponse.data)
                self.assertIn('modules', reponse.data)
        self.assertEqual(CalepinageVariante.objects.count(), 0)

    def test_calepinage_archive_refuse_en_409(self):
        from django.utils import timezone

        Calepinage.objects.filter(pk=self.calepinage.pk).update(
            archive_le=timezone.now())
        reponse = self._poster(['produit-%s' % self.b.pk])
        self.assertEqual(reponse.status_code, 409, reponse.data)
        self.assertEqual(CalepinageVariante.objects.count(), 0)

    def test_autre_societe_404(self):
        reponse = self._poster(['produit-%s' % self.b.pk],
                               api=self.api_autre)
        self.assertEqual(reponse.status_code, 404)

    def test_sans_permission_403(self):
        reponse = self._poster(['produit-%s' % self.b.pk], api=self.api_sans)
        self.assertEqual(reponse.status_code, 403)
