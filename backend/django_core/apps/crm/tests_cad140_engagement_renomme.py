"""CAD140 — le docstring de ``engagement.py`` dit ce qu'il mesure, et pourquoi.

Round 1 (une lane précédente) n'avait livré que le renommage du docstring en
tête de fichier — la seconde branche du « Done » (« le signal est repris, OU
le module renommé ») — faute d'un sélecteur PAR CLIENT côté ``apps.ventes``.
Ce fichier verrouillait alors cette hypothèse : module renommé, signal
comportemental abandonné pour de bon, quatre signaux administratifs seuls.

Round 2 (audit L3 du 21/09/2026, LIVRÉ le 23/09/2026) a pris l'AUTRE branche :
le sélecteur existe désormais (``apps.ventes.selectors.
devis_ouverts_ratio_client``, verrouillé côté calcul par
``tests_cad140_ouverture_propositions.py``), le signal comportemental est
RÉINTÉGRÉ à son poids d'origine (20 pts, 5 signaux symétriques) et le nom
public du module NE bouge PAS — parce que la branche « signal repris » a été
choisie, pas parce qu'un renommage a eu lieu. Les 4 assertions ci-dessous, qui
verrouillaient l'hypothèse round 1, verrouillent maintenant les faits RÉELS du
docstring courant (voir le texte de la tâche, ``docs/PLAN.md`` CAD140, et le
DONE LOG du 24/09/2026 : « score d'engagement re-branché sur les ouvertures
réelles »).

Test PUR (``unittest``, aucune DB) : seulement l'import du module et la
lecture de son docstring + de ses noms publics — jamais un test qui appelle
réellement ``compute_engagement_score`` (verrouillé côté DB par
``tests_cad140_ouverture_propositions.py``).
"""
import unittest

from apps.crm import engagement


class Cad140EngagementRenommeTests(unittest.TestCase):
    def test_le_docstring_nomme_cad140_et_le_signal_reintegre(self):
        doc = engagement.__doc__ or ''
        self.assertIn('CAD140', doc)
        self.assertIn('RÉINTÉGRÉ', doc)

    def test_le_docstring_garde_la_trace_de_l_abandon_historique(self):
        # Round 1 avait abandonné le signal (redistribué sur quatre signaux
        # administratifs) ; round 2 l'a réintégré — le docstring garde les
        # deux faits, pour qui se demande pourquoi le poids était de 25 puis
        # redevenu 20.
        doc = engagement.__doc__ or ''
        self.assertIn('ABANDONNÉ', doc)
        self.assertIn('COMPORTEMENTAL', doc)

    def test_le_docstring_explique_pourquoi_le_nom_public_ne_bouge_pas(self):
        # Le nom ne bouge pas parce que la branche « signal repris » du Done
        # a été retenue en round 2 — pas parce que le module a été renommé
        # en « activité commerciale » (l'autre branche, non retenue).
        doc = engagement.__doc__ or ''
        self.assertIn('NTCRM16', doc)
        self.assertIn("Score d'engagement", doc)

    def test_le_docstring_nomme_la_frontiere_cross_app_qui_a_debloque_le_signal(self):
        # La réintégration passe par un SÉLECTEUR ventes, jamais par
        # `apps.ventes.models` (règle CLAUDE.md, frontière cross-app) — le
        # docstring le nomme explicitement pour le signal réintégré.
        doc = engagement.__doc__ or ''
        self.assertIn('apps.ventes.selectors', doc)
        self.assertIn('jamais `apps.ventes.', doc)

    def test_l_api_publique_reste_inchangee(self):
        # Consommée par ``apps/crm/views.py`` (fichier possédé par une autre
        # lane) : un renommage de ces noms aurait cassé cet import sans que
        # cette lane puisse le corriger dans le même commit.
        for nom in ('compute_engagement_score', 'engagement_label',
                    'engagement_for_client', 'engagement_bulk'):
            self.assertTrue(callable(getattr(engagement, nom, None)), nom)


if __name__ == '__main__':
    unittest.main()
