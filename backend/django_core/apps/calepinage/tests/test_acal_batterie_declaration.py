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

#: ACAL800 — un groupe d'appoint d'essai : démarre à 20 %, s'arrête à 80 %.
GROUPE = {'actif': True, 'puissance_kw': 5.0, 'soc_demarrage_pct': 20,
          'soc_arret_pct': 80, 'heures_max_par_jour': 6}

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

    def test_acal796_coupures_enregistrees_et_champ_faux_nomme(self):
        coupures = {'nombre_par_an': 12, 'duree_h': 4, 'heure_debut': 18}
        enregistrer_entree(self.calepinage, {'batterie': {
            'strategie': 'backup', 'coupures': coupures}})
        self.calepinage.refresh_from_db()
        self.assertEqual(
            entree_stockee(self.calepinage)['batterie']['coupures'],
            coupures)
        for fausses, champ in (
                (dict(coupures, heure_debut=24),
                 'batterie.coupures.heure_debut'),
                (dict(coupures, duree_h=0), 'batterie.coupures.duree_h'),
                ({'duree_h': 4, 'heure_debut': 18},
                 'batterie.coupures.nombre_par_an')):
            with self.subTest(champ=champ):
                with self.assertRaises(EntreeInvalide) as refus:
                    enregistrer_entree(self.calepinage, {'batterie': {
                        'strategie': 'backup', 'coupures': fausses}})
                self.assertEqual(refus.exception.champ, champ)
        enregistrer_entree(self.calepinage, {'batterie': {
            'strategie': 'backup', 'coupures': None}})  # null efface

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

    def test_acal800_groupe_d_appoint_enregistre_et_faute_nommee(self):
        groupe = dict(GROUPE)
        reseau = {'actif': True, 'jours_autonomie': 2}
        enregistrer_entree(self.calepinage, {'hors_reseau': dict(
            reseau, groupe=groupe)})
        self.calepinage.refresh_from_db()
        self.assertEqual(entree_stockee(self.calepinage)['hors_reseau'][
            'groupe'], groupe)
        for fautif, champ in (
                (dict(groupe, soc_demarrage_pct=80),
                 'hors_reseau.groupe.soc_demarrage_pct'),
                (dict(groupe, puissance_kw=0),
                 'hors_reseau.groupe.puissance_kw'),
                (dict(groupe, heures_max_par_jour=25),
                 'hors_reseau.groupe.heures_max_par_jour'),
                ({k: v for k, v in groupe.items() if k != 'soc_arret_pct'},
                 'hors_reseau.groupe.soc_arret_pct')):
            with self.subTest(champ=champ):
                with self.assertRaises(EntreeInvalide) as refus:
                    enregistrer_entree(self.calepinage, {'hors_reseau': dict(
                        reseau, groupe=fautif)})
                self.assertEqual(refus.exception.champ, champ)
        for accepte in ({'actif': False}, None):
            enregistrer_entree(self.calepinage, {'hors_reseau': dict(
                reseau, groupe=accepte)})

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


class CoupuresDeclareesTest(SimpleTestCase):
    """ACAL796 — sans base : la forme des coupures, refus nommé."""

    COUPURES = {'nombre_par_an': 12, 'duree_h': 4, 'heure_debut': 18}

    def test_corps_conforme_accepte_et_null_efface(self):
        self.assertIn('coupures', CLES_BATTERIE)
        saisie = {'strategie': 'backup', 'coupures': dict(self.COUPURES)}
        valider_batterie(saisie)
        valider_secours(saisie)
        valider_secours({'coupures': None})
        saisie = CONTRAT_ENTREE['exemple_secours']['batterie']
        self.assertEqual(saisie['coupures'], self.COUPURES)
        valider_secours(saisie)

    def test_chaque_champ_faux_nomme_son_champ(self):
        cas = (
            (dict(self.COUPURES, heure_debut=24), 'heure_debut'),
            (dict(self.COUPURES, heure_debut=-1), 'heure_debut'),
            (dict(self.COUPURES, duree_h=0), 'duree_h'),
            (dict(self.COUPURES, nombre_par_an=1.5), 'nombre_par_an'),
            (dict(self.COUPURES, nombre_par_an=True), 'nombre_par_an'),
            ({'duree_h': 4, 'heure_debut': 18}, 'nombre_par_an'),
            ({'nombre_par_an': 12, 'duree_h': 4}, 'heure_debut'),
        )
        for coupures, champ in cas:
            with self.subTest(coupures=coupures):
                with self.assertRaises(EntreeInvalide) as refus:
                    valider_secours({'coupures': coupures})
                self.assertEqual(refus.exception.champ,
                                 'batterie.coupures.%s' % champ)
        with self.assertRaises(EntreeInvalide) as refus:
            valider_secours({'coupures': 'trois'})
        self.assertEqual(refus.exception.champ, 'batterie.coupures')


class GroupeAppointTest(SimpleTestCase):
    """ACAL800 — sans base : la forme du groupe d'appoint, refus nommé."""

    def _refus(self, groupe):
        from apps.calepinage.services.hors_reseau_declaration import (
            valider_hors_reseau,
        )

        with self.assertRaises(EntreeInvalide) as refus:
            valider_hors_reseau({'actif': True, 'groupe': groupe})
        return refus.exception.champ

    def test_corps_conforme_actif_faux_et_null_acceptes(self):
        from apps.calepinage.services.hors_reseau_declaration import (
            CLES_HORS_RESEAU, valider_hors_reseau,
        )

        self.assertIn('groupe', CLES_HORS_RESEAU)
        for groupe in (dict(GROUPE), {'actif': False}, None):
            valider_hors_reseau({'actif': True, 'groupe': groupe})
        corps = CONTRAT_ENTREE['exemple_hors_reseau_avance']['hors_reseau']
        self.assertEqual(corps['groupe'], GROUPE | {'soc_demarrage_pct': 20})
        valider_hors_reseau(corps)

    def test_demarrage_au_dessus_de_l_arret_nomme_le_demarrage(self):
        for demarrage in (80, 90):  # égal et au-dessus de l'arrêt
            with self.subTest(demarrage=demarrage):
                self.assertEqual(
                    self._refus(dict(GROUPE, soc_demarrage_pct=demarrage)),
                    'hors_reseau.groupe.soc_demarrage_pct')

    def test_chaque_faute_nomme_son_champ(self):
        cas = (
            (dict(GROUPE, puissance_kw=0), 'puissance_kw'),
            (dict(GROUPE, puissance_kw=True), 'puissance_kw'),
            (dict(GROUPE, soc_arret_pct=101), 'soc_arret_pct'),
            (dict(GROUPE, soc_demarrage_pct=-1), 'soc_demarrage_pct'),
            (dict(GROUPE, heures_max_par_jour=0), 'heures_max_par_jour'),
            (dict(GROUPE, heures_max_par_jour=24.5), 'heures_max_par_jour'),
            (dict(GROUPE, actif='oui'), 'actif'),
            (dict(GROUPE, carburant='diesel'), 'carburant'),
            ({'actif': True, 'puissance_kw': 5, 'soc_demarrage_pct': 20,
              'soc_arret_pct': 80}, 'heures_max_par_jour'),
        )
        for groupe, champ in cas:
            with self.subTest(groupe=groupe):
                self.assertEqual(self._refus(groupe),
                                 'hors_reseau.groupe.%s' % champ)
        self.assertEqual(self._refus('gros'), 'hors_reseau.groupe')


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


class BatterieDesigneeD_ACAL_157(SimpleTestCase):
    """D-ACAL-157 — désigner une batterie à l'étape Électrique : candidats, drapeau hybride décidé par le SERVEUR,
    refus d'un produit étranger / non batterie / d'un onduleur non hybride ; une entrée sans batterie intacte."""

    def _produit(self, type_fiche='batterie'):
        return mock.Mock(nom='Batterie 5,1 kWh', fiche_technique=mock.Mock(type_fiche=type_fiche))

    def _valider(self, postee, *, produit, onduleur_hybride=None, onduleur_present=True):
        from apps.calepinage.services import ratio_devis
        from apps.calepinage.services.validation_batterie import valider_batterie_designee

        materiel = {'produits': {'onduleur': 901 if onduleur_present else None}, 'onduleur': {'ac_kw': 10},
                    'designations': {'onduleur': 'Onduleur X'}, 'familles': {'onduleur': ('', '')}}
        with mock.patch('apps.stock.selectors.get_produit_scoped', return_value=produit), \
                mock.patch('apps.calepinage.services.electrique.resoudre_materiel', return_value=materiel), \
                mock.patch.object(ratio_devis, 'onduleur_designe_est_hybride', return_value=bool(onduleur_hybride)):
            valider_batterie_designee(mock.Mock(company=object()), {}, postee)

    def test_les_categories_de_candidats_portent_les_batteries_sans_fiche_exigee(self):
        from apps.calepinage.services.electrique import CATEGORIES_CANDIDATS, _champs_manquants

        self.assertIn(('batteries', 'batterie'), CATEGORIES_CANDIDATS)
        self.assertEqual(_champs_manquants('batterie', {}), [])
        self.assertTrue(_champs_manquants('optimiseur', {}))  # les autres rôles gardent leurs champs exigés

    def test_le_drapeau_hybride_suit_le_role_puis_la_fiche_puis_le_nom(self):
        from apps.calepinage.services.ratio_devis import onduleur_designe_est_hybride as hybride

        self.assertTrue(hybride({}, 'Onduleur X', ('onduleur_hybride', '')))        # rôle déclaré
        self.assertFalse(hybride({'bat_max_charge_kw': 5}, 'Hybrid X', ('onduleur_reseau', '')))  # le rôle tranche
        self.assertTrue(hybride({'bat_max_charge_kw': 5}, 'Onduleur X', ('', '')))   # port batterie publié
        self.assertTrue(hybride({}, 'Onduleur hybride Deye 20kW', ('', '')))          # le nom, en dernier
        self.assertFalse(hybride({'ac_kw': 10}, 'Onduleur réseau 10 kW', ('', '')))   # réseau : non
        self.assertFalse(hybride({}, '', ('', '')))                                    # rien lu : non

    def test_le_materiel_servi_ne_porte_hybride_que_sur_l_onduleur(self):
        from apps.calepinage.services.validation_batterie import drapeau_hybride

        resolu = {'onduleur': {'bat_max_decharge_kw': 6}, 'designations': {'onduleur': 'Onduleur X'},
                  'familles': {'onduleur': ('', '')}}
        self.assertEqual(drapeau_hybride('onduleur', resolu), {'hybride': True})
        self.assertEqual(drapeau_hybride('module', resolu), {})
        self.assertEqual(drapeau_hybride('optimiseur', resolu), {})

    def test_batterie_sur_onduleur_hybride_acceptee_et_effacement_admis(self):
        self._valider({'batterie': {'produit': 905, 'packs': 2}}, produit=self._produit(), onduleur_hybride=True)
        self._valider({'batterie': {'produit': None}}, produit=None)
        self._valider({'batterie': {'produit': ''}}, produit=None)

    def test_batterie_sur_onduleur_reseau_refusee_sous_le_champ_avec_une_phrase_claire(self):
        from apps.calepinage.services.electrique import EntreeInvalide

        with self.assertRaises(EntreeInvalide) as refus:
            self._valider({'batterie': {'produit': 905}}, produit=self._produit(), onduleur_hybride=False)
        self.assertEqual(refus.exception.champ, 'batterie.produit')
        self.assertIn("n'est pas un onduleur hybride", str(refus.exception))
        self.assertIn('retirez la batterie', str(refus.exception))

    def test_produit_d_une_autre_societe_ou_non_batterie_refuse(self):
        from apps.calepinage.services.electrique import EntreeInvalide

        with self.assertRaises(EntreeInvalide) as etranger:  # get_produit_scoped borne la société : None
            self._valider({'batterie': {'produit': 7}}, produit=None, onduleur_hybride=True)
        self.assertEqual(etranger.exception.champ, 'batterie.produit')
        self.assertTrue(etranger.exception.introuvable)
        with self.assertRaises(EntreeInvalide) as module:
            self._valider({'batterie': {'produit': 8}}, produit=self._produit('module'), onduleur_hybride=True)
        self.assertIn("n'est pas une batterie", str(module.exception))

    def test_sans_onduleur_resolu_ou_sans_batterie_rien_n_est_juge(self):
        self._valider({'batterie': {'produit': 905}}, produit=self._produit(), onduleur_present=False)
        self._valider({'dc_m': 12}, produit=None)                    # une saisie sans batterie : aucun effet
        self._valider({'batterie': {'strategie': 'autoconsommation'}}, produit=None)  # sans produit : aucun effet

    def test_une_entree_sans_batterie_garde_ses_options_donc_ses_empreintes(self):
        from apps.calepinage.services.electrique import _options_entree

        entree = {'regime': 'TT', 'dc_m': 12, 'onduleur_produit': 901}
        avant = _options_entree(dict(entree))
        self._valider(dict(entree), produit=None)  # la validation n'écrit ni ne modifie rien
        self.assertEqual(_options_entree(dict(entree)), avant)
        self.assertNotIn('batterie', entree)
