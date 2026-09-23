"""CAD140 — le module ``engagement.py`` dit maintenant ce qu'il mesure.

Le « score d'engagement » avait ABANDONNÉ le seul signal COMPORTEMENTAL
qu'il devait porter (l'ouverture de PDF/ShareLink) sans jamais le dire :
son entête prétendait toujours mesurer un « engagement » alors qu'il ne
fait que sommer quatre signaux ADMINISTRATIFS (fréquence de contact,
récence, paiements à temps, taux d'acceptation). Reprendre le signal
exigerait un sélecteur PAR CLIENT côté ``apps.ventes`` — HORS PÉRIMÈTRE de
cette lane (``apps/ventes/*`` interdit, voir la garde de lane). Done =
« le signal est repris, OU le module renommé et sa note de tête
corrigée » : cette lane prend la seconde branche.

Test PUR (``unittest``, aucune DB) : seulement l'import du module et la
lecture de son docstring + de ses noms publics — jamais un test qui
appelle réellement ``compute_engagement_score`` (ça exigerait la DB, hors
scope ici).
"""
import unittest

from apps.crm import engagement


class Cad140EngagementRenommeTests(unittest.TestCase):
    def test_le_docstring_dit_activite_commerciale_pas_engagement_client(self):
        doc = engagement.__doc__ or ''
        self.assertIn('ACTIVITÉ COMMERCIALE', doc)
        self.assertIn('CAD140', doc)

    def test_le_docstring_dit_que_le_signal_comportemental_est_abandonne(self):
        doc = engagement.__doc__ or ''
        self.assertIn('ABANDONNÉ', doc)
        self.assertIn('ADMINISTRATIFS', doc)

    def test_le_docstring_explique_pourquoi_le_nom_public_ne_bouge_pas(self):
        doc = engagement.__doc__ or ''
        self.assertIn('views.py', doc)
        self.assertIn('hors du périmètre de cette lane', doc)

    def test_le_docstring_nomme_le_blocage_apps_ventes_hors_perimetre(self):
        doc = engagement.__doc__ or ''
        # La note de périmètre doit rester lisible : ventes = hors scope,
        # pas juste « à réintégrer un jour » sans dire pourquoi c'est bloqué
        # MAINTENANT (règle grounding : un blocage se nomme).
        self.assertIn('apps/ventes/*', doc)
        self.assertIn('apps.ventes', doc)

    def test_l_api_publique_reste_inchangee(self):
        # Consommée par ``apps/crm/views.py`` (fichier possédé par une autre
        # lane) : un renommage de ces noms aurait cassé cet import sans que
        # cette lane puisse le corriger dans le même commit.
        for nom in ('compute_engagement_score', 'engagement_label',
                    'engagement_for_client', 'engagement_bulk'):
            self.assertTrue(callable(getattr(engagement, nom, None)), nom)


if __name__ == '__main__':
    unittest.main()
