"""CAD68 — La légende de `reveil_a2` dans `docs/crm/messages_meryem.md`
promettait un envoi « J30 puis J60 » que le moteur ne tient jamais.

`apps/crm/services._adapter_gabarits_reveil` réassigne les gabarits de la
cadence réveil selon que le lead a déjà reçu un devis : à J30, `reveil_a1`
ou `reveil_a2` selon le dossier ; à J60, TOUJOURS `reveil_a3` — le barreau
J60 seedé sous `reveil_a2` (`CADENCE_REVEIL_DEFAUT`) n'est jamais envoyé tel
quel. Ce fichier verrouille que la légende du document dit le vrai
routage, pas un test d'écran (React, hors de portée d'un test Django).
"""
import pathlib

from django.test import SimpleTestCase


def _fichier_source():
    ici = pathlib.Path(__file__).resolve()
    for parent in ici.parents:
        candidat = parent / 'docs' / 'crm' / 'messages_meryem.md'
        if candidat.exists():
            return candidat
    raise AssertionError(
        'docs/crm/messages_meryem.md introuvable — source de vérité des '
        'textes de relance.')


class LegendeReveilA2Tests(SimpleTestCase):
    def setUp(self):
        self.texte = _fichier_source().read_text(encoding='utf-8')

    def test_la_legende_ne_promet_plus_j30_puis_j60(self):
        """Anti-faux-vert : ce test échoue sur le document d'avant CAD68."""
        self.assertNotIn('J30 puis J60', self.texte)

    def test_la_legende_reveil_a2_dit_j30_seulement(self):
        self.assertIn(
            '### reveil_a2 — J30 seulement, réveil des leads jamais '
            'chiffrés (M6)', self.texte)

    def test_le_document_explique_le_routage_reel(self):
        """`reveil_a1` OU `reveil_a2` selon le dossier à J30, `reveil_a3`
        TOUJOURS à J60 — la mécanique réelle de `_adapter_gabarits_reveil`,
        pas seulement le symptôme (« ne part jamais à J60 »)."""
        self.assertIn('_adapter_gabarits_reveil', self.texte)
        self.assertIn('TOUJOURS', self.texte)
