# -*- coding: utf-8 -*-
"""CALX231 — le coffret de REGROUPEMENT, quand plusieurs coffrets remontent.

``coffrets_dc`` accepte un niveau de regroupement : chaque équipement
``coffret_dc`` peut désigner un ``parentId`` vers un autre ``coffret_dc``. Le
courant d'entrée du parent CUMULE celui de ses enfants ; une boucle de
parenté ou une profondeur supérieure à deux est REFUSÉE en nommant le
coffret fautif. Zéro nouveau seuil : ``SEUIL_CHAINES_PARALLELES_FUSIBLE``
reste celui de ``core.electrique.protections``.

``SimpleTestCase`` pur — aucune base.
"""

from django.test import SimpleTestCase

from apps.calepinage.services.coffrets import coffrets_dc


def _chaine(repere, isc_a):
    return {'repere': repere, 'isc_a': isc_a}


def _eq(id_, capacite, parent_id=None):
    eq = {'id': id_, 'type': 'coffret_dc', 'label': id_,
          'lng': -7.6, 'lat': 33.5, 'source': 'saisie',
          'capaciteEntrees': capacite}
    if parent_id is not None:
        eq['parentId'] = parent_id
    return eq


class UnNiveauDeRegroupement(SimpleTestCase):
    """Deux enfants (rez-de-chaussée) remontent vers UN parent."""

    def test_isc_cumule_du_parent_egale_la_somme_des_enfants(self):
        chaines = [_chaine('CH1', 10.0), _chaine('CH2', 10.0),
                   _chaine('CH3', 8.0)]
        # Le parent lui-même ne reçoit aucune chaîne directe (capacité 0) :
        # il ne fait QUE regrouper ses deux enfants.
        equipements = [
            _eq('enfant1', capacite=2, parent_id='parent'),
            _eq('enfant2', capacite=1, parent_id='parent'),
            _eq('parent', capacite=0),
        ]
        resultat = coffrets_dc(chaines, equipements)
        self.assertEqual(resultat.refus, ())
        par_id = {c.id: c for c in resultat.coffrets}
        self.assertEqual(par_id['enfant1'].profondeur, 1)
        self.assertEqual(par_id['enfant2'].profondeur, 1)
        self.assertEqual(par_id['parent'].profondeur, 0)
        self.assertAlmostEqual(par_id['enfant1'].isc_propre_a, 20.0)
        self.assertAlmostEqual(par_id['enfant2'].isc_propre_a, 8.0)
        self.assertAlmostEqual(par_id['parent'].isc_cumule_a, 28.0)
        # Un coffret sans enfant : son cumul égale son propre courant.
        self.assertAlmostEqual(
            par_id['enfant1'].isc_cumule_a, par_id['enfant1'].isc_propre_a)


class DeuxNiveauxDeRegroupement(SimpleTestCase):
    """Chaîne -> coffret -> coffret de regroupement -> coffret racine."""

    def test_deux_niveaux_cumulent_jusqu_a_la_racine(self):
        chaines = [_chaine('CH1', 10.0), _chaine('CH2', 10.0),
                   _chaine('CH3', 5.0)]
        equipements = [
            _eq('feuille', capacite=2, parent_id='regroupement'),
            _eq('autre_feuille', capacite=1, parent_id='regroupement'),
            _eq('regroupement', capacite=0, parent_id='racine'),
            _eq('racine', capacite=0),
        ]
        resultat = coffrets_dc(chaines, equipements)
        self.assertEqual(resultat.refus, ())
        par_id = {c.id: c for c in resultat.coffrets}
        self.assertEqual(par_id['feuille'].profondeur, 2)
        self.assertEqual(par_id['regroupement'].profondeur, 1)
        self.assertEqual(par_id['racine'].profondeur, 0)
        self.assertAlmostEqual(par_id['regroupement'].isc_cumule_a, 25.0)
        self.assertAlmostEqual(par_id['racine'].isc_cumule_a, 25.0)


class BoucleDeParenteRefusee(SimpleTestCase):
    def test_boucle_directe_refusee_en_nommant_le_coffret(self):
        equipements = [_eq('a', capacite=1, parent_id='b'),
                       _eq('b', capacite=1, parent_id='a')]
        resultat = coffrets_dc([_chaine('CH1', 10.0)], equipements)
        self.assertEqual(resultat.coffrets, ())
        texte = " | ".join(resultat.refus)
        self.assertIn("boucle de parenté", texte)
        self.assertTrue("« a »" in texte or "« b »" in texte)

    def test_boucle_sur_soi_meme_refusee(self):
        equipements = [_eq('a', capacite=1, parent_id='a')]
        resultat = coffrets_dc([_chaine('CH1', 10.0)], equipements)
        self.assertEqual(resultat.coffrets, ())
        texte = " | ".join(resultat.refus)
        self.assertIn("« a »", texte)
        self.assertIn("boucle de parenté", texte)

    def test_profondeur_superieure_a_deux_refusee(self):
        equipements = [
            _eq('n0', capacite=1, parent_id='n1'),
            _eq('n1', capacite=0, parent_id='n2'),
            _eq('n2', capacite=0, parent_id='n3'),
            _eq('n3', capacite=0),
        ]
        resultat = coffrets_dc([_chaine('CH1', 10.0)], equipements)
        # Seul « n0 » (profondeur 3) est refusé — ses ancêtres, chacun dans
        # les deux niveaux admis pris isolément, restent des coffrets valides
        # (sans chaîne, faute d'en avoir reçu une de « n0 »).
        self.assertNotIn('n0', {c.id for c in resultat.coffrets})
        texte = " | ".join(resultat.refus)
        self.assertIn("« n0 »", texte)
        self.assertIn("profondeur de regroupement", texte)

    def test_parent_inconnu_refuse_en_le_nommant(self):
        equipements = [_eq('a', capacite=1, parent_id='fantome')]
        resultat = coffrets_dc([_chaine('CH1', 10.0)], equipements)
        self.assertEqual(resultat.coffrets, ())
        texte = " | ".join(resultat.refus)
        self.assertIn("« fantome »", texte)
        self.assertIn("n'est posé nulle part", texte)
