# -*- coding: utf-8 -*-
"""ACAL55 — le schéma unifilaire d'une conception RÉELLE, sans doublure.

LE CONSTAT (C-ACAL-059)
-----------------------
Dès qu'un calepinage devenait calculable (module + onduleur désignés sur des
fiches complètes), ``GET schema-unifilaire/``, le ``POST`` d'édition et
``GET schema-unifilaire.dxf/`` levaient ``AttributeError: 'ResultatChaines'
object has no attribute 'protections'`` (``core/electrique/schema.py``) : le
dessin recevait le ``ResultatChaines`` de la conception au lieu d'un
``ResultatElectrique`` complet. Les tests existants ne le voyaient pas parce
qu'ils remplaçaient ``conception_du_calepinage`` par une doublure.

Ici : AUCUNE doublure de ``conception_du_calepinage`` ni de
``resoudre_materiel`` — les Produit et leurs FicheTechnique sont créés en
base, l'entrée électrique est posée par ``enregistrer_entree``, et la source
réelle (``core.electrique.concevoir``, via l'adaptateur unique
``electrique.resultat_electrique_complet``) est exercée de bout en bout.
"""
from __future__ import annotations

from decimal import Decimal

from apps.calepinage.models import Calepinage, ParametresCalepinage
from apps.calepinage.services.electrique import (
    conception_du_calepinage, enregistrer_entree,
    resultat_electrique_complet,
)
from apps.calepinage.services.sld import rendu_du_schema
from apps.stock.models import FicheTechnique, Produit

from .test_api_liste import BaseApiCalepinage, url_detail

LAYOUT = {
    'pin': {'lat': 33.5731, 'lng': -7.5898},
    'zones': [{
        'id': 'z1', 'label': 'Sud', 'neededPanels': 12,
        'result': {'count': 12},
        'facingAzimuthDeg': 180.0, 'pitchDeg': 15.0,
    }],
}


def url_schema(pk):
    return f'{url_detail(pk)}schema-unifilaire/'


def url_dxf(pk):
    return f'{url_detail(pk)}schema-unifilaire.dxf/'


def contenu(reponse):
    if getattr(reponse, 'streaming', False):
        return b''.join(reponse.streaming_content)
    return reponse.content


class BaseConceptionReelle(BaseApiCalepinage):
    """Un calepinage réel : zone de 12 modules, épingle, matériel désigné."""

    def setUp(self):
        super().setUp()
        self.module = self._produit(
            nom='Module 710', type_fiche='module', vmp_v=41.4, voc_v=49.3,
            isc_a=18.59, imp_a=17.59, pmax_wc=710.0)
        self.onduleur = self._produit(
            nom='Onduleur 10 kW', type_fiche='onduleur', ond_n_mppt=2,
            ond_mppt_v_min=160.0, ond_mppt_v_max=950.0,
            ond_v_max_abs=1100.0, ond_i_max_mppt_a=26.0, ond_ac_kw=10.0,
            ond_phases=3)
        self.calepinage = Calepinage.objects.create(
            company=self.company, lead_id=self.lead.pk, titre='Villa Anfa',
            roof_layout=LAYOUT)
        enregistrer_entree(self.calepinage, {
            'module_produit': self.module.pk,
            'onduleur_produit': self.onduleur.pk,
            # Températures SAISIES : aucun appel réseau (TMY) pendant le test.
            'temperature_min_c': -5.0, 'temperature_max_c': 70.0,
            'phases': 3,
        })

    def _produit(self, *, nom, type_fiche, **champs_fiche):
        produit = Produit.objects.create(
            company=self.company, nom=nom, sku=f'ACAL55-{nom}',
            prix_achat=Decimal('999'), prix_vente=Decimal('1500'),
            quantite_stock=1)
        FicheTechnique.objects.create(
            company=self.company, produit=produit, type_fiche=type_fiche,
            **champs_fiche)
        return produit

    def _norme_francaise(self):
        ParametresCalepinage.objects.create(
            company=self.company,
            norme_electrique={'norme': 'nf_c_15_100'})


class ConceptionReelle(BaseConceptionReelle):

    def test_get_post_dxf_sans_doublure(self):
        self._norme_francaise()
        reponse = self.api.get(url_schema(self.calepinage.pk))
        self.assertEqual(reponse.status_code, 200, reponse.data)
        self.assertEqual(reponse.data['manquantes'], [])
        self.assertTrue(reponse.data['svg'])
        clefs = [bloc['clef'] for bloc in reponse.data['blocs']]
        for attendu in ('champ', 'onduleur', 'disjoncteur_ac'):
            self.assertIn(attendu, clefs)

        poste = self.api.post(url_schema(self.calepinage.pk),
                              {'libelles': {'champ': 'X'}}, format='json')
        self.assertEqual(poste.status_code, 200, poste.data)
        champ = next(bloc for bloc in poste.data['blocs']
                     if bloc['clef'] == 'champ')
        self.assertEqual(champ['titre'], 'X')
        self.assertEqual(poste.data['edition']['libelles'], {'champ': 'X'})
        self.calepinage.refresh_from_db()
        self.assertEqual(
            self.calepinage.resultat['sld_edition']['libelles'],
            {'champ': 'X'})

        dxf = self.api.get(url_dxf(self.calepinage.pk))
        self.assertEqual(dxf.status_code, 200)
        self.assertTrue(contenu(dxf))

    def test_deux_get_successifs_rendent_le_meme_svg(self):
        self._norme_francaise()
        premier = self.api.get(url_schema(self.calepinage.pk))
        second = self.api.get(url_schema(self.calepinage.pk))
        self.assertEqual(premier.status_code, 200, premier.data)
        self.assertEqual(premier.data['svg'], second.data['svg'])

    def test_sans_norme_topologie_sans_calibre(self):
        reponse = self.api.get(url_schema(self.calepinage.pk))
        self.assertEqual(reponse.status_code, 200, reponse.data)
        self.assertTrue(reponse.data['svg'])
        clefs = [bloc['clef'] for bloc in reponse.data['blocs']]
        self.assertIn('champ', clefs)
        self.assertIn('onduleur', clefs)
        # Aucun organe décidé sans norme : ni disjoncteur, ni sectionneur,
        # ni différentiel — et donc aucun calibre ni repère imprimé.
        for organe in ('disjoncteur_ac', 'sectionneur_dc', 'ddr',
                       'parafoudre_ac', 'fusibles'):
            self.assertNotIn(organe, clefs)
        for bloc in reponse.data['blocs']:
            self.assertFalse(bloc['repere'], bloc)

    def test_annexe_devis_inchangee(self):
        """Le jumeau client (``apps.ventes.selectors.schema_unifilaire_svg``)
        dessine, sur le MÊME résultat complet, le MÊME SVG que le calepinage
        sans édition — la porte cross-app n'a pas bougé."""
        from apps.ventes.selectors import schema_unifilaire_svg
        from core.electrique import concevoir

        conception, _m, _d, _doc = conception_du_calepinage(self.calepinage)
        complet = resultat_electrique_complet(conception)
        self.assertEqual(complet, concevoir(conception.entree))
        cartouche = {'client': 'Atlas', 'reference': 'CAL-1',
                     'date': '21/09/2026'}
        self.assertEqual(
            rendu_du_schema(conception.entree, complet,
                            cartouche=cartouche)['svg'],
            schema_unifilaire_svg(entree=conception.entree, resultat=complet,
                                  cartouche=cartouche))
