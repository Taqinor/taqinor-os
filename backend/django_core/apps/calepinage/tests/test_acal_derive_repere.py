"""ACAL191 (C-ACAL-003, D-ACAL-13) — GPS du lead corrigé après le tracé.

Ce qui est prouvé ici :

* le design-context MESURE la dérive (``repere_lead``, ``ecart_m``,
  ``derive.etat``) et la DIT en français — sans rien écrire ;
* « Recentrer sur le GPS du lead » translate TOUTES les coordonnées du
  document (parcours piloté par ``roof_layout_v2.schema.json`` : chaque
  coordonnée du schéma est translatée ou exemptée explicitement) par
  projection locale — les formes métriques sont conservées — et dépose une
  version restaurable ;
* « Garder ce repère » acquitte la dérive : la bannière ne revient pas.

Run :
    python manage.py test apps.calepinage.tests.test_acal_derive_repere -v2
"""
import json
import pathlib
from decimal import Decimal

from apps.calepinage.models import Calepinage, CalepinageVersion
from apps.calepinage.services import repere as service_repere
from apps.crm.models import Lead
from core.calepinage.geo import aire_contour_m2, projeteur_local

from .test_api_liste import BaseApiCalepinage, url_detail

SCHEMA = json.loads(
    (pathlib.Path(__file__).resolve().parents[1] / 'contract_samples'
     / 'roof_layout_v2.schema.json').read_text(encoding='utf-8'))

CASABLANCA = {'lat': 33.5731, 'lng': -7.5898}
MARRAKECH = {'lat': 31.6295, 'lng': -7.9811}

#: Un pan de ≈ 12 × 8 m autour de l'épingle de Casablanca ([lng, lat]).
PAN = [[-7.58986, 33.57306], [-7.58973, 33.57306],
       [-7.58973, 33.57313], [-7.58986, 33.57313]]


def _resoudre(noeud):
    ref = noeud.get('$ref') if isinstance(noeud, dict) else None
    if ref and ref.startswith('#/$defs/'):
        return SCHEMA['$defs'][ref.split('/')[-1]], ref.split('/')[-1]
    return noeud, None


def _branches(noeud):
    """Le nœud et ses alternatives (oneOf/anyOf/allOf, then/else)."""
    yield noeud
    for cle in ('oneOf', 'anyOf', 'allOf'):
        for sous in noeud.get(cle) or []:
            sous, _ = _resoudre(sous)
            yield from _branches(sous)
    for cle in ('then', 'else'):
        if isinstance(noeud.get(cle), dict):
            yield from _branches(noeud[cle])


def coordonnees_du_schema():
    """``{chemin: forme}`` de CHAQUE coordonnée que le schéma déclare."""
    trouvees = {}

    def visiter(noeud, chemin, pile):
        noeud, nom = _resoudre(noeud)
        if nom == 'couple':
            trouvees[chemin] = 'couple'
            return
        if nom is not None:
            if (nom, chemin) in pile:
                return
            pile = pile | {(nom, chemin)}
        for branche in _branches(noeud):
            proprietes = branche.get('properties') or {}
            if 'lat' in proprietes and 'lng' in proprietes:
                trouvees[chemin] = 'point'
            if 'centerLng' in proprietes and 'centerLat' in proprietes:
                trouvees[chemin] = 'centre'
            items = branche.get('items')
            if isinstance(items, dict):
                _resolu, nom_items = _resoudre(items)
                if nom_items == 'couple':
                    trouvees[chemin] = 'couples'
                else:
                    visiter(items, chemin + '[]', pile)
            for cle, sous in proprietes.items():
                if cle in ('lat', 'lng', 'centerLng', 'centerLat'):
                    continue
                visiter(sous, f'{chemin}.{cle}' if chemin else cle, pile)

    visiter(SCHEMA, '', frozenset())
    return trouvees


def _poser(document, chemin, valeur):
    """Pose ``valeur`` au chemin (``a[]`` = liste d'UN élément)."""
    segments = chemin.split('.')
    noeud = document
    for rang, segment in enumerate(segments):
        dernier = rang == len(segments) - 1
        if segment.endswith('[]'):
            cle = segment[:-2]
            liste = noeud.setdefault(cle, [{}])
            if dernier:
                liste[0].update(valeur)
                return
            noeud = liste[0]
        elif dernier:
            if isinstance(valeur, dict) and isinstance(noeud.get(segment),
                                                       dict):
                noeud[segment].update(valeur)
            else:
                noeud[segment] = valeur
        else:
            noeud = noeud.setdefault(segment, {})


def _lire(document, chemin):
    noeud = document
    for segment in chemin.split('.'):
        if segment.endswith('[]'):
            noeud = noeud[segment[:-2]][0]
        else:
            noeud = noeud[segment]
    return noeud


#: Un point près de l'épingle A, en [lng, lat].
POINT = (-7.58975, 33.57320)


def _valeur(forme, ordre):
    lng, lat = POINT
    couple = [lng, lat] if ordre == 'lng_lat' else [lat, lng]
    return {
        'point': {'lat': lat, 'lng': lng},
        'centre': {'centerLng': lng, 'centerLat': lat},
        'couple': couple,
        'couples': [couple, list(couple)],
    }[forme]


def _lng_lat(valeur, forme, ordre):
    """Le premier point de ``valeur`` en ``(lng, lat)``."""
    if forme == 'point':
        return valeur['lng'], valeur['lat']
    if forme == 'centre':
        return valeur['centerLng'], valeur['centerLat']
    couple = valeur if forme == 'couple' else valeur[0]
    return tuple(couple) if ordre == 'lng_lat' else (couple[1], couple[0])


def url_contexte(pk):
    return f'{url_detail(pk)}design-context/'


class DeriveRepereTest(BaseApiCalepinage):
    def setUp(self):
        super().setUp()
        # Le lead : épingle posée à Casablanca, GPS CORRIGÉ à Marrakech.
        self.lead = Lead.objects.create(
            company=self.company, nom='Lead dérive 191', ville='Marrakech',
            roof_point=dict(CASABLANCA),
            gps_lat=Decimal(str(MARRAKECH['lat'])),
            gps_lng=Decimal(str(MARRAKECH['lng'])))
        self.layout = {
            'version': 2, 'pin': dict(CASABLANCA),
            'outline': [[lat, lng] for lng, lat in PAN],
            'zones': [{'id': 'z1', 'vertices': [list(p) for p in PAN]}],
        }
        self.calepinage = Calepinage.objects.create(
            company=self.company, lead_id=self.lead.pk, titre='Dérive',
            roof_layout=self.layout)

    def _contexte(self, calepinage=None):
        reponse = self.api.get(url_contexte((calepinage
                                             or self.calepinage).pk))
        self.assertEqual(reponse.status_code, 200, reponse.data)
        return reponse.data

    def _poster(self, geste, calepinage=None):
        return self.api.post(
            f'{url_detail((calepinage or self.calepinage).pk)}{geste}/',
            {}, format='json')

    def test_design_context_signale_la_derive(self):
        geometrie = self._contexte()['geometrie']
        self.assertEqual(geometrie['repere_lead'],
                         dict(MARRAKECH, source='gps'))
        self.assertGreater(geometrie['ecart_m'], 200000)
        self.assertEqual(geometrie['derive'],
                         {'etat': 'a_decider', 'seuil_m': 100})
        avertissements = self._contexte()['avertissements']
        self.assertTrue(any(m.startswith('Le GPS du lead a été corrigé '
                                         'depuis le tracé (≈ ')
                            and 'km)' in m for m in avertissements),
                        avertissements)

    def test_epingle_qui_suit_le_lead_est_recentree_d_office(self):
        layout = dict(self.layout, pinSource='lead')
        Calepinage.objects.filter(pk=self.calepinage.pk).update(
            roof_layout=layout)
        self.assertEqual(self._contexte()['geometrie']['derive']['etat'],
                         'automatique')

    def test_sous_le_seuil_aucune_derive(self):
        self.lead.gps_lat = Decimal('33.573400')  # ≈ 33 m plus au nord
        self.lead.gps_lng = Decimal('-7.589800')
        self.lead.save()
        geometrie = self._contexte()['geometrie']
        self.assertLess(geometrie['ecart_m'], 100)
        self.assertEqual(geometrie['derive']['etat'], 'aucune')
        self.assertFalse(any('GPS du lead' in m for m in
                             self._contexte()['avertissements']))

    def test_get_ne_modifie_rien(self):
        avant = CalepinageVersion.objects.filter(
            calepinage=self.calepinage).count()
        for _ in range(2):
            self._contexte()
        self.calepinage.refresh_from_db()
        self.assertEqual(self.calepinage.roof_layout, self.layout)
        self.assertEqual(CalepinageVersion.objects.filter(
            calepinage=self.calepinage).count(), avant)

    def test_le_schema_est_entierement_couvert(self):
        schema = coordonnees_du_schema()
        declares = set(service_repere.CHEMINS_TRANSLATES) | set(
            service_repere.COORDONNEES_EXEMPTEES)
        self.assertEqual(set(schema) - declares, set(),
                         'coordonnée du schéma ni translatée ni exemptée')
        self.assertEqual(set(service_repere.CHEMINS_TRANSLATES)
                         - set(schema), set(), 'chemin translaté périmé')
        for chemin, (forme, _ordre) in (
                service_repere.CHEMINS_TRANSLATES.items()):
            self.assertEqual(schema[chemin], forme, chemin)

    def test_recentrer_translate_toutes_les_coordonnees_du_schema(self):
        schema = coordonnees_du_schema()
        document = {'version': 2, 'pin': dict(CASABLANCA)}
        for chemin, forme in sorted(schema.items()):
            ordre = service_repere.CHEMINS_TRANSLATES.get(
                chemin, (forme, 'lng_lat'))[1]
            _poser(document, chemin, _valeur(forme, ordre))
        _poser(document, 'pin', dict(CASABLANCA))
        Calepinage.objects.filter(pk=self.calepinage.pk).update(
            roof_layout=document)

        reponse = self._poster('recentrer-sur-lead')
        self.assertEqual(reponse.status_code, 200, reponse.data)
        relu = self.api.get(f'{url_detail(self.calepinage.pk)}layout/')
        nouveau = relu.data['roof_layout']
        self.assertEqual(nouveau['pin'], MARRAKECH)

        autour_a = projeteur_local((CASABLANCA['lng'], CASABLANCA['lat']))
        autour_b = projeteur_local((MARRAKECH['lng'], MARRAKECH['lat']))
        attendu = autour_a(POINT)
        for chemin, forme in schema.items():
            if chemin == 'pin':
                continue
            if chemin in service_repere.COORDONNEES_EXEMPTEES:
                self.assertEqual(_lire(nouveau, chemin),
                                 _lire(document, chemin), chemin)
                continue
            ordre = service_repere.CHEMINS_TRANSLATES[chemin][1]
            obtenu = autour_b(_lng_lat(_lire(nouveau, chemin), forme, ordre))
            self.assertAlmostEqual(obtenu[0], attendu[0], places=4,
                                   msg=chemin)
            self.assertAlmostEqual(obtenu[1], attendu[1], places=4,
                                   msg=chemin)

    def test_recentrer_conserve_les_formes_metriques(self):
        aire_avant = aire_contour_m2(PAN)
        reponse = self._poster('recentrer-sur-lead')
        self.assertEqual(reponse.status_code, 200, reponse.data)
        self.calepinage.refresh_from_db()
        sommets = self.calepinage.roof_layout['zones'][0]['vertices']
        aire_apres = aire_contour_m2(sommets)
        self.assertAlmostEqual(aire_apres / aire_avant, 1.0, delta=0.001)
        # Le pan est bien arrivé à Marrakech (pas resté à Casablanca).
        self.assertAlmostEqual(sommets[0][1], 31.6295, delta=0.01)
        contour = self.calepinage.roof_layout['outline']
        self.assertAlmostEqual(contour[0][0], 31.6295, delta=0.01)  # [lat,lng]

    def test_recentrer_depose_une_version_restaurable(self):
        avant = CalepinageVersion.objects.filter(
            calepinage=self.calepinage).count()
        reponse = self._poster('recentrer-sur-lead')
        self.assertEqual(reponse.status_code, 200, reponse.data)
        self.assertIsNotNone(reponse.data['version'])
        versions = CalepinageVersion.objects.filter(
            calepinage=self.calepinage)
        self.assertEqual(versions.count(), avant + 1)
        self.assertEqual(versions.order_by('-pk').first().libelle,
                         'Recentré sur le GPS du lead')
        geometrie = self._contexte()['geometrie']
        self.assertEqual(geometrie['derive']['etat'], 'aucune')
        self.assertEqual(geometrie['pin'], MARRAKECH)

    def test_garder_acquitte(self):
        reponse = self._poster('garder-repere')
        self.assertEqual(reponse.status_code, 200, reponse.data)
        self.calepinage.refresh_from_db()
        self.assertEqual(self.calepinage.roof_layout['repereAcquitte'],
                         MARRAKECH)
        # L'épingle n'a PAS bougé.
        self.assertEqual(self.calepinage.roof_layout['pin'], CASABLANCA)
        contexte = self._contexte()
        self.assertEqual(contexte['geometrie']['derive']['etat'], 'aucune')
        self.assertFalse(any('GPS du lead' in m
                             for m in contexte['avertissements']))
        # Le lead bouge de nouveau : la bannière revient.
        self.lead.gps_lat = Decimal('30.427800')
        self.lead.gps_lng = Decimal('-9.598100')
        self.lead.save()
        self.assertEqual(self._contexte()['geometrie']['derive']['etat'],
                         'a_decider')

    def test_lead_sans_repere_refus_nomme(self):
        lead = Lead.objects.create(company=self.company, nom='Sans GPS')
        calepinage = Calepinage.objects.create(
            company=self.company, lead_id=lead.pk, titre='Sans repère',
            roof_layout=dict(self.layout))
        reponse = self._poster('recentrer-sur-lead', calepinage)
        self.assertEqual(reponse.status_code, 400, reponse.data)
        self.assertIn('repere_lead', reponse.data)

    def test_autre_societe_introuvable(self):
        etranger = Calepinage.objects.create(
            company=self.autre, lead_id=self.lead.pk, titre='Voisine',
            roof_layout=dict(self.layout))
        for geste in ('recentrer-sur-lead', 'garder-repere'):
            self.assertEqual(self._poster(geste, etranger).status_code, 404)
