"""CAD124 — pas d'axe segment dans le gabarit de cadence, et c'est ÉCRIT.

[TRANCHÉ 21/09/2026] ``unique_together`` ne porte que (société, cadence,
ordre) et aucune occurrence de ``type_installation`` n'existe dans le
gabarit, les horaires ou les messages — alors que le CRM lit déjà le segment
pour scorer et pour exiger les bons champs au devis. La décision est de NE
PAS ouvrir cet axe : le levier langue/texte (CAD126) et le playbook
conditionné (CAD125) couvrent l'essentiel sans migration ni sélecteur de
plus.

Ce module verrouille les deux moitiés du Done : la clé n'a pas bougé, et la
décision est écrite ET datée à côté d'elle — pour qu'un futur audit ne la
re-soulève pas. Aucune migration : le test le vérifie aussi, en constatant
qu'aucun champ de segment n'est apparu sur le modèle.
"""
import pathlib

from django.test import SimpleTestCase

from apps.parametres.models_relance import CadenceRelanceEtape

SOURCE_GABARIT = (pathlib.Path(__file__).resolve().parent
                  / 'models_relance.py')


class LaCleNAPasBougeTests(SimpleTestCase):
    def test_unique_together_reste_societe_cadence_ordre(self):
        self.assertEqual(
            [tuple(clef) for clef in CadenceRelanceEtape._meta.unique_together],
            [('company', 'cadence', 'ordre')])

    def test_aucun_champ_de_SEGMENT_sur_le_gabarit(self):
        """Aucune migration : si un axe segment était apparu, il y aurait un
        champ, donc une migration."""
        noms = {champ.name for champ in CadenceRelanceEtape._meta.get_fields()}
        for interdit in ('type_installation', 'segment', 'marche'):
            with self.subTest(champ=interdit):
                self.assertNotIn(interdit, noms)


class LaDecisionEstEcriteEtDateeTests(SimpleTestCase):
    def setUp(self):
        self.source = SOURCE_GABARIT.read_text(encoding='utf-8')

    def test_le_gabarit_porte_la_decision_datee(self):
        self.assertIn('CAD124', self.source)
        self.assertIn('21/09/2026', self.source)

    def test_elle_dit_ce_qu_elle_decide(self):
        bas = self.source.lower()
        self.assertIn('axe segment', bas)
        self.assertIn('type_installation', bas)

    def test_elle_dit_CE_QUI_la_rouvrira(self):
        """« elle se rouvrira sur le volume par segment (CADM7), pas avant »
        — sans cette phrase, un futur audit re-poserait la question."""
        self.assertIn('CADM7', self.source)

    def test_la_decision_est_ECRITE_A_COTE_de_la_cle(self):
        avant = self.source.split(
            "unique_together = [('company', 'cadence', 'ordre')]")[0]
        self.assertIn('CAD124', avant[-1500:])
