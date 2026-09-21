# -*- coding: utf-8 -*-
"""CALX233 — les libellés et les repères ÉDITÉS du schéma unifilaire.

CE QUE CE FICHIER ARME
----------------------
1. **Un libellé posé** est persisté sur le calepinage
   (``resultat['sld_edition']``), relu tel quel, et il devient le TITRE du
   bloc — dans ``blocs`` comme dans le SVG.
2. **Un repère posé** suit la même route et se retrouve en ``data-repere``
   du groupe dessiné.
3. **Une clef inconnue est refusée EN LA NOMMANT** : l'édition ne peut pas
   faire apparaître un organe que les protections n'ont pas retenu.
4. **Rien d'autre ne bouge.** Le tableau d'équipements — calibres, sections,
   quantités — est identique avant et après édition, dans le SVG comme dans
   ``lignes_tableau``.
5. **Aucun prix.** La garde de mot-prix du contrat CALX204 est rejouée à
   l'écriture : « prix », « marge », « montant », « MAD », « TVA »,
   « remise » sont refusés dans un libellé comme dans un repère.

``SimpleTestCase`` : aucune base de données. Le pivot est un objet factice
qui porte ``resultat`` (le ``JSONField``) et compte ses ``save()`` — c'est
tout ce que le service touche.

Run :
    python manage.py test apps.calepinage.tests.test_calx233_sld_libelles
"""
from __future__ import annotations

import re

from django.test import SimpleTestCase

from core.electrique import concevoir
from core.electrique.schema import lignes_tableau
from core.electrique.types import (
    EntreeElectrique, GroupePan, SpecModule, SpecOnduleur,
)

from apps.calepinage.services.sld import (
    CLE_EDITION, SldRefuse, edition_sld, enregistrer_edition_sld,
    rendu_du_schema,
)

MODULE = SpecModule(vmp_v=34.0, voc_v=41.0, isc_a=13.8, imp_a=13.0,
                    pmax_wc=550.0, temp_coeff_voc_pct_c=-0.27,
                    temp_coeff_pmax_pct_c=-0.35,
                    designation='Canadian Solar 550 Wc')
ONDULEUR = SpecOnduleur(n_mppt=2, mppt_v_min=120.0, mppt_v_max=850.0,
                        v_max_abs=1000.0, i_max_mppt_a=26.0, ac_kw=10.0,
                        v_demarrage_v=90.0,
                        designation='Deye SUN-10K-SG05LP3')

#: Les lignes du TABLEAU d'équipements dans le SVG : le noyau les enveloppe
#: dans ``<g data-repere="…">`` (un bloc dessiné, lui, ouvre sur
#: ``<g data-bloc=``) — le motif ne peut donc pas les confondre.
LIGNES_TABLEAU_SVG = re.compile(r'<g data-repere="[^"]*">.*?</g>')


def _entree():
    return EntreeElectrique(module=MODULE, onduleur=ONDULEUR,
                            groupes=(GroupePan('Sud', 24, 180.0, 15.0),),
                            dc_m=30.0, ac_m=12.0)


class CalepinageFactice:
    """Le pivot RÉDUIT à ce que le service touche : ``resultat`` et ``save``.

    ``pk`` à ``None`` reproduit le calcul hors base (le service ne sauvegarde
    alors pas, comme ``services/electrique.py`` le fait déjà) ; un ``pk``
    posé fait compter l'appel et ses ``update_fields``.
    """

    def __init__(self, resultat=None, pk=None):
        self.pk = pk
        self.resultat = resultat
        self.sauvegardes = []

    def save(self, **kwargs):
        self.sauvegardes.append(kwargs)


class ScenarioSld(SimpleTestCase):
    """Le décor commun : une conception complète et son dessin."""

    def setUp(self):
        self.entree = _entree()
        self.resultat = concevoir(self.entree)
        self.dessin = rendu_du_schema(self.entree, self.resultat)
        self.calepinage = CalepinageFactice(pk=7)

    def _poser(self, corps):
        return enregistrer_edition_sld(self.calepinage, corps,
                                       dessin=self.dessin)

    def _dessin_edite(self, edition):
        return rendu_du_schema(self.entree, self.resultat, edition=edition)

    def _bloc(self, dessin, clef):
        for bloc in dessin['blocs']:
            if bloc['clef'] == clef:
                return bloc
        self.fail('Bloc « %s » absent du dessin.' % clef)


class LibellePoseTest(ScenarioSld):
    """1 — un libellé posé, persisté, relu, et DESSINÉ."""

    def test_le_libelle_est_persiste_sous_sa_cle_json(self):
        self._poser({'libelles': {'ddr': 'Interrupteur différentiel'}})
        self.assertEqual(
            self.calepinage.resultat[CLE_EDITION]['libelles'],
            {'ddr': 'Interrupteur différentiel'})

    def test_le_libelle_est_relu_par_edition_sld(self):
        self._poser({'libelles': {'ddr': 'Interrupteur différentiel'}})
        self.assertEqual(edition_sld(self.calepinage)['libelles'],
                         {'ddr': 'Interrupteur différentiel'})

    def test_le_libelle_devient_le_titre_du_bloc(self):
        edition = self._poser({'libelles': {'ddr': 'Interrupteur diff.'}})
        dessin = self._dessin_edite(edition)
        self.assertEqual(self._bloc(dessin, 'ddr')['titre'],
                         'Interrupteur diff.')

    def test_le_libelle_est_ecrit_dans_le_svg(self):
        edition = self._poser({'libelles': {'ddr': 'Interrupteur diff.'}})
        dessin = self._dessin_edite(edition)
        self.assertIn('Interrupteur diff.', dessin['svg'])
        self.assertNotIn('Différentiel type A', dessin['svg'])

    def test_l_ecriture_ne_touche_que_le_champ_resultat(self):
        self._poser({'libelles': {'tgbt': 'Tableau général'}})
        self.assertEqual(self.calepinage.sauvegardes,
                         [{'update_fields': ['resultat', 'updated_at']}])

    def test_sans_pk_rien_n_est_sauvegarde(self):
        """Calcul hors base : l'édition vit en mémoire, aucune écriture."""
        calepinage = CalepinageFactice(pk=None)
        enregistrer_edition_sld(calepinage, {'libelles': {'tgbt': 'TGBT B'}},
                                dessin=self.dessin)
        self.assertEqual(calepinage.sauvegardes, [])
        self.assertEqual(calepinage.resultat[CLE_EDITION]['libelles'],
                         {'tgbt': 'TGBT B'})


class ReperePoseTest(ScenarioSld):
    """2 — un repère posé écrase celui de la protection AU DESSIN."""

    def test_le_repere_est_persiste_et_relu(self):
        self._poser({'reperes': {'ddr': 'Q2'}})
        self.assertEqual(edition_sld(self.calepinage)['reperes'],
                         {'ddr': 'Q2'})

    def test_le_repere_est_celui_du_bloc_publie(self):
        edition = self._poser({'reperes': {'ddr': 'Q2'}})
        self.assertEqual(self._bloc(self._dessin_edite(edition), 'ddr')
                         ['repere'], 'Q2')

    def test_le_repere_est_porte_par_le_groupe_dessine(self):
        edition = self._poser({'reperes': {'ddr': 'Q2'}})
        svg = self._dessin_edite(edition)['svg']
        self.assertIn('<g data-bloc="ddr" data-repere="Q2">', svg)

    def test_un_noeud_de_topologie_peut_recevoir_un_repere(self):
        """Le TGBT n'a pas de repère de bordereau : l'éditeur peut en poser
        un sans que rien ne soit inventé par le calcul."""
        edition = self._poser({'reperes': {'tgbt': 'TGBT-1'}})
        self.assertEqual(self._bloc(self._dessin_edite(edition), 'tgbt')
                         ['repere'], 'TGBT-1')


class ClefInconnueTest(ScenarioSld):
    """3 — l'édition ne crée AUCUN organe, et le refus nomme la clef."""

    def test_un_libelle_sur_une_clef_absente_est_refuse(self):
        with self.assertRaises(SldRefuse) as refus:
            self._poser({'libelles': {'coffret_ac': 'Coffret AC'}})
        self.assertIn('coffret_ac', str(refus.exception))
        self.assertEqual(refus.exception.champ,
                         'edition.libelles.coffret_ac')

    def test_un_repere_sur_une_clef_absente_est_refuse(self):
        with self.assertRaises(SldRefuse) as refus:
            self._poser({'reperes': {'batterie': 'BAT1'}})
        self.assertIn('batterie', str(refus.exception))
        self.assertEqual(refus.exception.champ, 'edition.reperes.batterie')

    def test_un_refus_n_ecrit_rien(self):
        with self.assertRaises(SldRefuse):
            self._poser({'libelles': {'coffret_ac': 'Coffret AC'}})
        self.assertEqual(self.calepinage.sauvegardes, [])
        self.assertIsNone(self.calepinage.resultat)

    def test_une_rubrique_inconnue_est_refusee_en_la_nommant(self):
        with self.assertRaises(SldRefuse) as refus:
            self._poser({'couleurs': {'ddr': 'rouge'}})
        self.assertIn('couleurs', str(refus.exception))
        self.assertEqual(refus.exception.champ, 'edition.couleurs')

    def test_un_texte_vide_est_refuse_plutot_qu_efface(self):
        with self.assertRaises(SldRefuse) as refus:
            self._poser({'libelles': {'ddr': '   '}})
        self.assertEqual(refus.exception.champ, 'edition.libelles.ddr')


class TableauInchangeTest(ScenarioSld):
    """4 — un libellé édité ne change AUCUN calibre, section ni quantité."""

    def test_les_lignes_du_bordereau_sont_identiques(self):
        avant = lignes_tableau(self.resultat)
        edition = self._poser({'libelles': {'ddr': 'Interrupteur diff.'},
                               'reperes': {'ddr': 'Q2'}})
        self._dessin_edite(edition)
        self.assertEqual(lignes_tableau(self.resultat), avant)

    def test_le_tableau_dessine_est_identique(self):
        avant = LIGNES_TABLEAU_SVG.findall(self.dessin['svg'])
        edition = self._poser({'libelles': {'ddr': 'Interrupteur diff.'},
                               'reperes': {'ddr': 'Q2'}})
        apres = LIGNES_TABLEAU_SVG.findall(self._dessin_edite(edition)['svg'])
        self.assertEqual(apres, avant,
                         "Le tableau d'équipements a bougé : un libellé "
                         "édité ne touche ni calibre, ni section, ni "
                         'quantité.')

    def test_le_sous_titre_du_bloc_garde_son_calibre(self):
        avant = self._bloc(self.dessin, 'ddr')['sous_titre']
        edition = self._poser({'libelles': {'ddr': 'Interrupteur diff.'}})
        self.assertEqual(self._bloc(self._dessin_edite(edition), 'ddr')
                         ['sous_titre'], avant)

    def test_aucun_bloc_n_apparait_ni_ne_disparait(self):
        avant = [bloc['clef'] for bloc in self.dessin['blocs']]
        edition = self._poser({'libelles': {'ddr': 'Interrupteur diff.'}})
        apres = [bloc['clef']
                 for bloc in self._dessin_edite(edition)['blocs']]
        self.assertEqual(apres, avant)


class MotDArgentTest(ScenarioSld):
    """5 — aucun montant dans un texte de planche (D-CALX 5)."""

    def test_un_libelle_qui_porte_un_prix_est_refuse(self):
        with self.assertRaises(SldRefuse) as refus:
            self._poser({'libelles': {'ddr': 'Différentiel (prix révisé)'}})
        self.assertIn('prix', str(refus.exception))
        self.assertEqual(refus.exception.champ, 'edition.libelles.ddr')

    def test_un_repere_qui_porte_un_montant_est_refuse(self):
        with self.assertRaises(SldRefuse):
            self._poser({'reperes': {'ddr': 'Q2 — 1200 MAD'}})

    def test_un_mot_qui_contient_un_mot_d_argent_reste_admis(self):
        """« Madrier » n'est pas « MAD » : la garde travaille par MOT."""
        edition = self._poser({'libelles': {'tgbt': 'Tableau madrier'}})
        self.assertEqual(edition['libelles']['tgbt'], 'Tableau madrier')


class LectureToleranteTest(SimpleTestCase):
    """Un stockage abîmé ne fait pas tomber une LECTURE."""

    def test_un_resultat_absent_rend_une_edition_vide(self):
        self.assertEqual(edition_sld(CalepinageFactice()),
                         {'libelles': {}, 'reperes': {}, 'positions': {}})

    def test_les_entrees_illisibles_sont_ignorees_pas_levees(self):
        calepinage = CalepinageFactice(resultat={CLE_EDITION: {
            'libelles': {'ddr': 'OK', 'tgbt': 42},
            'reperes': 'pas un objet',
            'positions': {'ddr': {'x': 1.0, 'y': 2.0}, 'tgbt': {'x': 'a'}},
        }})
        edition = edition_sld(calepinage)
        self.assertEqual(edition['libelles'], {'ddr': 'OK'})
        self.assertEqual(edition['reperes'], {})
        self.assertEqual(edition['positions'], {'ddr': {'x': 1.0, 'y': 2.0}})
