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

from apps.calepinage.models import Calepinage, CalepinageVariante
from apps.calepinage.services.variantes import retenir_variante

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

    def test_edition_du_layout_recalcule_l_empreinte(self):
        variante = CalepinageVariante.objects.create(
            company=self.company, calepinage=self.calepinage, nom='A')
        reponse = self.api.patch(
            url_variante(self.calepinage.pk, variante.pk),
            {'roof_layout': {'result': {'panels': 9}}}, format='json')
        self.assertEqual(reponse.status_code, 200, reponse.data)
        variante.refresh_from_db()
        self.assertEqual(len(variante.layout_hash), 64)

    def test_suppression_de_la_retenue_refusee(self):
        variante = CalepinageVariante.objects.create(
            company=self.company, calepinage=self.calepinage, nom='A')
        retenir_variante(variante)
        reponse = self.api.delete(
            url_variante(self.calepinage.pk, variante.pk))
        self.assertEqual(reponse.status_code, 400)
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
            company=self.company, calepinage=self.calepinage, nom='A')
        self.b = CalepinageVariante.objects.create(
            company=self.company, calepinage=self.calepinage, nom='B')
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
            resultat=RESULTAT_SIMULE)
        retenir_variante(variante)
        reponse = self.api.get(url_comparer(self.calepinage.pk))
        self.assertEqual(reponse.status_code, 200, reponse.data)
        self.assertEqual(set(reponse.data), set(CONTRAT['exemple']))
        self.assertEqual(set(reponse.data['lignes'][0]),
                         set(CONTRAT['exemple']['lignes'][0]))
        self.assertEqual(set(reponse.data['lignes'][0]['production']),
                         set(CONTRAT['exemple']['lignes'][0]['production']))

    def test_une_seule_variante_les_ecarts_valent_null(self):
        variante = CalepinageVariante.objects.create(
            company=self.company, calepinage=self.calepinage, nom='A',
            resultat=RESULTAT_SIMULE)
        retenir_variante(variante)
        ligne = self.api.get(url_comparer(self.calepinage.pk)).data['lignes'][0]
        self.assertIsNone(ligne['ecart_modules'])
        self.assertIsNone(ligne['ecart_kwc'])
        self.assertIsNone(ligne['ecart_p50_kwh'])

    def test_ecarts_relatifs_a_la_retenue(self):
        retenue = CalepinageVariante.objects.create(
            company=self.company, calepinage=self.calepinage, nom='A',
            resultat=RESULTAT_SIMULE)
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
            resultat=RESULTAT_SIMULE)
        retenir_variante(retenue)
        CalepinageVariante.objects.create(
            company=self.company, calepinage=self.calepinage, nom='B')
        lignes = {ligne['nom']: ligne
                  for ligne in self.api.get(
                      url_comparer(self.calepinage.pk)).data['lignes']}
        self.assertFalse(lignes['B']['simulee'])
        for cle, valeur in lignes['B']['production'].items():
            self.assertIsNone(valeur, cle)
        self.assertIsNone(lignes['B']['ecart_p50_kwh'])

    def test_sans_permission_403(self):
        reponse = self.api_sans.get(url_comparer(self.calepinage.pk))
        self.assertEqual(reponse.status_code, 403)
