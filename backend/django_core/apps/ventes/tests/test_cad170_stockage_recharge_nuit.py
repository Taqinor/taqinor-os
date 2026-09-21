# -*- coding: utf-8 -*-
"""CAD170 — la recharge nocturne se couvre par le STOCKAGE, pas par un conseil.

C'est le cas majoritaire : la fenêtre de recharge par défaut est 21h-6h, et
l'audit du 21/09/2026 a mesuré l'effet sur l'autoconsommation — NUL, même avec
une batterie de 10 kWh (reproduit deux fois par ses relecteurs).

DÉCISION FONDATEUR DU 21/09/2026 : on ne conseille pas « rechargez de jour »
comme argument principal — on DIMENSIONNE la batterie pour couvrir la recharge
nocturne. Les kWh/jour de recharge s'AJOUTENT au besoin de stockage, bornés par
les tailles d'offre RÉELLEMENT VENDUES : jamais une batterie sur mesure, jamais
au-delà du catalogue. Le conseil de décaler la recharge en journée est ÉCARTÉ —
le gain chiffré qui le soutenait était gonflé par l'absence de borne que
CAD165 (4) a corrigée.

Le dernier test lit `docs/crm/messages_meryem.md` : aucun texte client ne doit
conseiller de recharger le jour.
"""
from pathlib import Path

from django.test import SimpleTestCase

from apps.ventes import courbes_journalieres as CJ
from apps.ventes import etude_horaire as EH

#: Catalogue de tailles vendues, volontairement irrégulier.
TAILLES = (5.0, 10.0, 15.0, 20.0)


def _couches_ve(creneau=None, km=300, chargeur=None):
    entree = {'voiture_electrique': True, 've_km_semaine': km}
    if creneau:
        entree['ve_creneau'] = creneau
    if chargeur:
        entree['ve_chargeur_kw'] = chargeur
    return CJ.composer_equipements(entree)


class LaRechargeNocturneEstIdentifiee(SimpleTestCase):
    def test_la_fenetre_par_defaut_est_nocturne(self):
        couches = _couches_ve()
        self.assertEqual(couches['ve']['heures'], list(CJ.VE_HEURES))
        self.assertGreater(EH.recharge_ve_nocturne_kwh_jour(couches), 0)

    def test_le_creneau_NUIT_declare_est_nocturne(self):
        couches = _couches_ve(creneau='nuit')
        self.assertEqual(EH.recharge_ve_nocturne_kwh_jour(couches),
                         couches['ve']['kwh_jour'])

    def test_une_recharge_de_JOUR_n_entre_PAS_dans_le_stockage(self):
        couches = _couches_ve(creneau='jour')
        self.assertEqual(EH.recharge_ve_nocturne_kwh_jour(couches), 0.0)

    def test_une_recharge_du_SOIR_non_plus(self):
        couches = _couches_ve(creneau='soir')
        self.assertEqual(EH.recharge_ve_nocturne_kwh_jour(couches), 0.0)

    def test_sans_couche_vehicule_il_n_y_a_rien_a_couvrir(self):
        self.assertEqual(EH.recharge_ve_nocturne_kwh_jour({}), 0.0)
        self.assertEqual(EH.recharge_ve_nocturne_kwh_jour(None), 0.0)


class LeBesoinDeStockageAUGMENTE(SimpleTestCase):
    def test_le_besoin_augmente_EXACTEMENT_du_besoin_de_recharge(self):
        """LE test de la tâche."""
        couches = _couches_ve()
        recharge = couches['ve']['kwh_jour']
        sortie = EH.besoin_stockage_avec_recharge_ve(8.0, couches, TAILLES)
        self.assertEqual(sortie['besoin_base_kwh'], 8.0)
        self.assertEqual(sortie['recharge_ve_kwh'], round(recharge, 2))
        self.assertAlmostEqual(sortie['besoin_total_kwh'],
                               round(8.0 + recharge, 2), places=2)

    def test_la_taille_retenue_est_la_plus_petite_qui_COUVRE(self):
        couches = _couches_ve(km=100)   # ~2,83 kWh/jour
        sortie = EH.besoin_stockage_avec_recharge_ve(8.0, couches, TAILLES)
        self.assertGreaterEqual(sortie['taille_retenue_kwh'],
                                sortie['besoin_total_kwh'])
        plus_petites = [t for t in TAILLES
                        if t < sortie['taille_retenue_kwh']]
        for taille in plus_petites:
            self.assertLess(taille, sortie['besoin_total_kwh'])
        self.assertFalse(sortie['plafonne'])

    def test_un_besoin_hors_catalogue_est_PLAFONNE_et_le_DIT(self):
        couches = _couches_ve(km=1000)
        sortie = EH.besoin_stockage_avec_recharge_ve(30.0, couches, TAILLES)
        self.assertEqual(sortie['taille_retenue_kwh'], max(TAILLES))
        self.assertTrue(sortie['plafonne'])
        self.assertIn('catalogue', sortie['motif'])

    def test_jamais_une_capacite_HORS_catalogue(self):
        for km in (50, 100, 300, 700, 2000):
            couches = _couches_ve(km=km)
            sortie = EH.besoin_stockage_avec_recharge_ve(8.0, couches, TAILLES)
            self.assertIn(sortie['taille_retenue_kwh'], TAILLES, km)

    def test_sans_catalogue_aucune_taille_n_est_INVENTEE(self):
        couches = _couches_ve()
        sortie = EH.besoin_stockage_avec_recharge_ve(8.0, couches, [])
        self.assertIsNone(sortie['taille_retenue_kwh'])
        self.assertIn('catalogue', sortie['motif'])
        # Le BESOIN, lui, reste chiffré : c'est une omission nommée, pas un trou.
        self.assertGreater(sortie['besoin_total_kwh'], 8.0)

    def test_une_recharge_de_JOUR_ne_change_pas_le_besoin(self):
        """Non-régression : seule la recharge nocturne est couverte ici."""
        couches = _couches_ve(creneau='jour')
        sortie = EH.besoin_stockage_avec_recharge_ve(8.0, couches, TAILLES)
        self.assertEqual(sortie['recharge_ve_kwh'], 0.0)
        self.assertEqual(sortie['besoin_total_kwh'], 8.0)
        self.assertEqual(sortie['taille_retenue_kwh'], 10.0)

    def test_sans_vehicule_le_besoin_est_servi_comme_avant(self):
        sortie = EH.besoin_stockage_avec_recharge_ve(12.0, {}, TAILLES)
        self.assertEqual(sortie['recharge_ve_kwh'], 0.0)
        self.assertEqual(sortie['taille_retenue_kwh'], 15.0)


class AucunTexteNeConseilleDeRechargerLeJour(SimpleTestCase):
    """Le conseil est ÉCARTÉ : il ne doit apparaître dans aucun texte client."""

    #: …/backend/django_core/apps/ventes/tests/<ce fichier> → racine du dépôt.
    FICHIER = (Path(__file__).resolve().parents[5]
               / 'docs' / 'crm' / 'messages_meryem.md')

    #: Tournures qui conseilleraient de déplacer la recharge en journée.
    INTERDITS = (
        'rechargez de jour',
        'rechargez le jour',
        'recharger de jour',
        'recharger le jour',
        'rechargez en journée',
        'recharger en journée',
        'rechargez pendant la journée',
        'recharger pendant la journée',
    )

    def test_le_fichier_de_textes_existe(self):
        self.assertTrue(self.FICHIER.is_file(), str(self.FICHIER))

    def test_aucune_tournure_ne_conseille_de_recharger_le_jour(self):
        contenu = self.FICHIER.read_text(encoding='utf-8').lower()
        for tournure in self.INTERDITS:
            self.assertNotIn(tournure, contenu, tournure)

    def test_la_decision_est_ECRITE_dans_le_fichier(self):
        """Pour qu'une rédaction future ne la re-soulève pas."""
        contenu = self.FICHIER.read_text(encoding='utf-8')
        self.assertIn('CAD170', contenu)
        self.assertIn('besoin de stockage', contenu)
