"""ACAL166 — la batterie et le mode hors réseau se DÉCLARENT dans l'entrée
électrique, et la simulation les lit là (plus sur ``roof_layout.battery``).

Ce qui est prouvé ici (fonctions réelles, produits réels en base, aucune
doublure de la déclaration) :

* une stratégie déclarée donne une déclaration que l'étape batterie SIMULE
  (bloc non nul — jusqu'ici : « aucune stratégie ») ;
* le produit et les packs par défaut viennent de la ligne batterie du devis lié,
  avec leur provenance ; une saisie explicite l'emporte ;
* sans stratégie, le bloc est OMIS en la nommant — aucune n'est supposée ;
* le mode hors réseau déclaré est lu dans l'entrée ;
* une forme refusée NOMME son champ (``batterie.<champ>``).

Run :
    python manage.py test apps.calepinage.tests.test_acal_batterie_declaration -v2
"""
from __future__ import annotations

import json
import pathlib
from decimal import Decimal
from unittest import mock

from django.test import SimpleTestCase

from apps.calepinage.models import Calepinage
from apps.calepinage.services.batterie_declaration import (
    CLES_BATTERIE, valider_secours,
)
from apps.calepinage.services.electrique import (
    CLE_ENTREE, EntreeInvalide, enregistrer_entree, entree_stockee,
)
from apps.calepinage.services.validation_batterie import valider_batterie
from apps.calepinage.services.etapes import batterie as bloc
from apps.calepinage.services.simulation import (
    _declaration_batterie, _section_de_l_entree,
)
from apps.stock.models import FicheTechnique, Produit

from .test_api_liste import BaseApiCalepinage
from .test_calx188_batterie import contexte_de_test, serie_de_test

FICHE = dict(bat_kwh_nominal=10.0, bat_kwh_usable=9.0, bat_dod_pct=90.0,
             bat_rendement_ar_pct=94.0, bat_cycles_publies=6000,
             bat_max_charge_kw=5.0, bat_max_decharge_kw=5.0)

CONTRAT_ENTREE = json.loads(
    (pathlib.Path(__file__).resolve().parents[1] / 'contract_samples'
     / 'calepinage_entree_electrique.json').read_text(encoding='utf-8'))

#: ACAL786 — un appareil secouru d'essai (valeurs d'essai, OpenSolar « Enter
#: by Appliance » : continue, pointe au démarrage, quantité).
APPAREIL = {'nom': 'Réfrigérateur', 'puissance_continue_kw': 0.15,
            'puissance_pointe_kw': 0.6, 'quantite': 1}

#: ACAL790 — des seuils de protection hors réseau d'essai, ordonnés.
SEUILS = {'veille_pct': 30, 'entretien_pct': 20, 'arret_pct': 10}

#: La ligne batterie du devis lié, telle que ``equipements_du_calepinage`` la rend.
CIBLE_EQUIPEMENTS = ('apps.calepinage.services.equipements'
                     '.equipements_du_calepinage')


class Declaration(BaseApiCalepinage):
    def setUp(self):
        super().setUp()
        self.produit = Produit.objects.create(
            company=self.company, nom='Batterie 10 kWh', sku='ACAL166-B',
            prix_achat=Decimal('999'), prix_vente=Decimal('1500'),
            quantite_stock=1)
        FicheTechnique.objects.create(
            company=self.company, produit=self.produit,
            type_fiche='batterie', **FICHE)
        self.calepinage = Calepinage.objects.create(
            company=self.company, lead_id=self.lead.pk, titre='Batterie',
            roof_layout={'zones': []}, resultat={})

    def _declaration(self, saisie, *, devis=None):
        donnees = {'batterie': saisie} if saisie is not None else {}
        with mock.patch(CIBLE_EQUIPEMENTS,
                        return_value={'batterie': devis}):
            return _declaration_batterie(
                self.calepinage, donnees, {'produits': {}}, self.company)

    def _bloc(self, declaration):
        contexte = contexte_de_test(heures=48)
        contexte[bloc.CLE_CONTEXTE] = declaration
        return bloc.bloc_batterie(serie_de_test(heures=48), contexte)[1]

    def test_strategie_declaree_donne_un_bloc_non_nul(self):
        declaration = self._declaration(
            {'produit': self.produit.pk, 'strategie': 'autoconso',
             'packs': 2})

        resultat = self._bloc(declaration)

        self.assertEqual(declaration['strategie'], 'autoconso')
        self.assertEqual(declaration['groupes'][0]['packs'], 2)
        self.assertEqual(declaration['provenance']['produit'], 'explicite')
        self.assertIsNotNone(resultat['total'], resultat['motif_absence'])

    def test_defaut_produit_et_packs_du_devis(self):
        declaration = self._declaration(
            {'strategie': 'autoconso'},
            devis={'produit': self.produit.pk, 'quantite': 3.0})

        self.assertEqual(declaration['groupes'][0]['packs'], 3)
        self.assertEqual(declaration['provenance'],
                         {'produit': 'devis', 'packs': 'devis'})

    def test_saisie_explicite_l_emporte_sur_le_devis(self):
        declaration = self._declaration(
            {'produit': self.produit.pk, 'packs': 1,
             'strategie': 'autoconso'},
            devis={'produit': self.produit.pk, 'quantite': 3.0})

        self.assertEqual(declaration['groupes'][0]['packs'], 1)
        self.assertEqual(declaration['provenance'],
                         {'produit': 'explicite', 'packs': 'explicite'})

    def test_sans_strategie_motif_nomme(self):
        declaration = self._declaration(
            None, devis={'produit': self.produit.pk, 'quantite': 1.0})

        resultat = self._bloc(declaration)

        # Produit et packs viennent du devis, mais AUCUNE stratégie n'est supposée.
        self.assertNotIn('strategie', declaration)
        self.assertIsNone(resultat['total'])
        self.assertIn('strategie', resultat['motif_absence'])

    def test_sans_batterie_ni_devis_aucune_declaration(self):
        self.assertEqual(self._declaration(None), {})

    def test_hors_reseau_declare_est_lu_dans_l_entree(self):
        donnees = {'hors_reseau': {'actif': True, 'jours_autonomie': 2}}

        self.assertEqual(_section_de_l_entree(donnees, 'hors_reseau'),
                         {'actif': True, 'jours_autonomie': 2})
        self.assertEqual(_section_de_l_entree({}, 'hors_reseau'), {})

    def test_forme_refusee_nomme_le_champ(self):
        for saisie, champ in (
                ({'strategie': 'inventee'}, 'batterie.strategie'),
                ({'couplage': 'xx'}, 'batterie.couplage'),
                ({'packs': 0}, 'batterie.packs'),
                ({'heures_charge': [25]}, 'batterie.heures_charge'),
                ({'inconnu': 1}, 'batterie.inconnu')):
            with self.subTest(champ=champ):
                with self.assertRaises(EntreeInvalide) as refus:
                    enregistrer_entree(self.calepinage, {'batterie': saisie})
                self.assertEqual(refus.exception.champ, champ)
        with self.assertRaises(EntreeInvalide) as refus:
            enregistrer_entree(self.calepinage,
                               {'hors_reseau': {'jours_autonomie': -1}})
        self.assertEqual(refus.exception.champ,
                         'hors_reseau.jours_autonomie')

    def test_acal786_appareils_et_duree_enregistres_puis_simules(self):
        saisie = {'produit': self.produit.pk, 'strategie': 'backup',
                  'appareils': [dict(APPAREIL)], 'duree_secours_h': 4}
        enregistrer_entree(self.calepinage, {'batterie': saisie})
        self.calepinage.refresh_from_db()
        stockee = entree_stockee(self.calepinage)['batterie']
        self.assertEqual(stockee, saisie)

        resultat = self._bloc(self._declaration(stockee))

        self.assertIsNotNone(resultat['total'], resultat['motif_absence'])
        self.assertTrue(any('déduite de 1 appareil' in texte
                            for texte in resultat['avertissements']))

    def test_acal786_forme_fausse_du_secours_nomme_le_champ(self):
        sans_pointe = {k: v for k, v in APPAREIL.items()
                       if k != 'puissance_pointe_kw'}
        for saisie, champ in (
                ({'appareils': [sans_pointe], 'duree_secours_h': 4},
                 'batterie.appareils[0].puissance_pointe_kw'),
                ({'appareils': [dict(APPAREIL)]}, 'batterie.duree_secours_h'),
                ({'fenetres': {'charge': [{'heures': [25]}],
                               'decharge': [{'heures': [20]}]}},
                 'batterie.fenetres.charge[0].heures'),
                ({'appareils': [dict(APPAREIL)], 'duree_secours_h': 4,
                  'reserve_backup_kwh': 2.0}, 'batterie.reserve_backup_kwh'),
                ({'part_effacable_pct': 120}, 'batterie.part_effacable_pct'),
                ({'inconnu': 1}, 'batterie.inconnu')):
            with self.subTest(champ=champ):
                with self.assertRaises(EntreeInvalide) as refus:
                    enregistrer_entree(self.calepinage, {'batterie': saisie})
                self.assertEqual(refus.exception.champ, champ)

    def test_acal790_seuils_hors_reseau_mal_formes_nomment_leur_seuil(self):
        for seuils, champ in (
                ({'veille_pct': 10, 'entretien_pct': 15, 'arret_pct': 20},
                 'hors_reseau.seuils.veille_pct'),
                ({'veille_pct': 50, 'arret_pct': 10},
                 'hors_reseau.seuils.entretien_pct'),
                (dict(SEUILS, arret_pct=-5), 'hors_reseau.seuils.arret_pct'),
                ('bas', 'hors_reseau.seuils')):
            with self.subTest(champ=champ):
                with self.assertRaises(EntreeInvalide) as refus:
                    enregistrer_entree(self.calepinage, {'hors_reseau': {
                        'actif': True, 'jours_autonomie': 2,
                        'seuils': seuils}})
                self.assertEqual(refus.exception.champ, champ)
        enregistrer_entree(self.calepinage, {'hors_reseau': {
            'actif': True, 'jours_autonomie': 2, 'seuils': dict(SEUILS)}})
        self.calepinage.refresh_from_db()
        self.assertEqual(entree_stockee(self.calepinage)['hors_reseau'][
            'seuils'], SEUILS)

    def test_declaration_enregistree_et_relue_telle_quelle(self):
        saisie = {'strategie': 'autoconso', 'packs': 2, 'couplage': 'ac'}

        enregistrer_entree(self.calepinage,
                           {'batterie': saisie,
                            'hors_reseau': {'actif': False}})

        self.calepinage.refresh_from_db()
        stockee = entree_stockee(self.calepinage)
        self.assertEqual(stockee['batterie'], saisie)
        self.assertEqual(stockee['hors_reseau'], {'actif': False})
        self.assertIn(CLE_ENTREE, self.calepinage.resultat)
        # La déclaration n'entre pas dans le document : layout_hash inchangé.
        self.assertNotIn('battery', self.calepinage.roof_layout)


class SecoursEtCommandeAdmisTest(SimpleTestCase):
    """ACAL786 — sans base : les cinq clés sont admises et jugées par les
    règles du calcul (``services/batterie.py``), refus nommé."""

    def test_les_cinq_cles_sont_admises(self):
        for cle in ('appareils', 'duree_secours_h', 'fenetres',
                    'part_effacable_pct', 'plafond_effacable_kw'):
            self.assertIn(cle, CLES_BATTERIE)
        saisie = {'strategie': 'backup', 'appareils': [dict(APPAREIL)],
                  'duree_secours_h': 4, 'part_effacable_pct': 60,
                  'plafond_effacable_kw': 5.0}
        valider_batterie(saisie)
        valider_secours(saisie)
        valider_secours({'fenetres': {'charge': [{'heures': [10, 11]}],
                                      'decharge': [{'heures': [19]}]}})

    def test_les_corps_du_contrat_sont_acceptes(self):
        for cle in ('exemple_secours', 'exemple_commande_avancee'):
            saisie = CONTRAT_ENTREE[cle]['batterie']
            valider_batterie(saisie)
            valider_secours(saisie)

    def test_refus_traduit_en_batterie_champ(self):
        with self.assertRaises(EntreeInvalide) as refus:
            valider_secours({'appareils': [dict(APPAREIL)],
                             'duree_secours_h': 0})
        self.assertEqual(refus.exception.champ, 'batterie.duree_secours_h')
        with self.assertRaises(EntreeInvalide) as refus:
            valider_secours({'plafond_effacable_kw': -1})
        self.assertEqual(refus.exception.champ,
                         'batterie.plafond_effacable_kw')


class SeuilsHorsReseauTest(SimpleTestCase):
    """ACAL790 — sans base : la forme des seuils, règle de
    ``services/hors_reseau.py::_seuils_de_protection``, refus nommé."""

    def test_veille_sous_l_arret_nomme_la_veille(self):
        from apps.calepinage.services.hors_reseau_declaration import (
            CLES_HORS_RESEAU, valider_hors_reseau,
        )

        self.assertIn('seuils', CLES_HORS_RESEAU)
        with self.assertRaises(EntreeInvalide) as refus:
            valider_hors_reseau({'seuils': {'veille_pct': 5,
                                            'entretien_pct': 5,
                                            'arret_pct': 10}})
        self.assertEqual(refus.exception.champ,
                         'hors_reseau.seuils.veille_pct')
        valider_hors_reseau({'actif': True, 'seuils': dict(SEUILS)})
        valider_hors_reseau({'seuils': None})  # null efface
        valider_hors_reseau(CONTRAT_ENTREE['exemple_hors_reseau_avance'][
            'hors_reseau'])
