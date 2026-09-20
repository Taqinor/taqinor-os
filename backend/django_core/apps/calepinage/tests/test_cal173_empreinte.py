"""CAL173 — la planche porte l'empreinte du layout et la version du moteur.

Une planche sans provenance n'est pas rejouable : devant deux tirages du même
toit, personne ne peut dire lequel correspond à la conception d'aujourd'hui.

Ces essais sont PURS : ils comparent DEUX RENDUS, ce qui est exactement la
question posée (« deux rendus du même layout portent le même hash, un layout
modifié en change »). L'empreinte elle-même n'est pas recalculée ici — elle est
posée par ``services.layout.enregistrer_layout`` (CAL13), qui a ses propres
essais ; la refaire ici serait une seconde vérité.

Run :
    python manage.py test apps.calepinage.tests.test_cal173_empreinte -v2
"""
from datetime import datetime

from django.test import SimpleTestCase

from apps.calepinage.services.planche import (
    TAILLE_HASH_COURT, empreinte_du_calepinage, hash_court,
    rendre_planche_svg, texte_d_empreinte,
)
from apps.calepinage.tests.test_cal171_planche import LAYOUT

MOMENT = datetime(2026, 9, 20, 11, 30)
HASH_A = 'a' * 64
HASH_B = 'b' * 64


class FauxCalepinage:
    """Le strict nécessaire : ce module ne lit QUE des champs stockés."""

    def __init__(self, layout_hash=HASH_A, version_moteur='calepinage-1.0.0',
                 roof_layout=None):
        self.pk = 41
        self.titre = 'Toiture atelier'
        self.layout_hash = layout_hash
        self.version_moteur = version_moteur
        self.roof_layout = LAYOUT if roof_layout is None else roof_layout

    def __str__(self):
        return self.titre


class TexteDEmpreinteTest(SimpleTestCase):
    def test_le_pied_porte_hash_court_moteur_et_date(self):
        self.assertEqual(
            texte_d_empreinte(HASH_A, 'calepinage-1.0.0', MOMENT),
            'calepinage aaaaaaaaaaaa · moteur calepinage-1.0.0 · 20/09/2026')

    def test_le_hash_court_est_recopiable_a_la_main(self):
        self.assertEqual(len(hash_court(HASH_A)), TAILLE_HASH_COURT)
        self.assertEqual(hash_court(''), '')
        self.assertEqual(hash_court(None), '')

    def test_un_terme_absent_est_omis_jamais_invente(self):
        # Une version de moteur inventée serait pire que pas de version.
        self.assertEqual(texte_d_empreinte(HASH_A, '', MOMENT),
                         'calepinage aaaaaaaaaaaa · 20/09/2026')
        self.assertEqual(texte_d_empreinte('', '', MOMENT), '20/09/2026')

    def test_l_empreinte_est_lue_du_calepinage_jamais_recalculee(self):
        self.assertIn('aaaaaaaaaaaa',
                      empreinte_du_calepinage(FauxCalepinage(), moment=MOMENT))


class DeuxRendusTest(SimpleTestCase):
    def test_deux_rendus_de_la_meme_conception_sont_identiques(self):
        calepinage = FauxCalepinage()
        premier = rendre_planche_svg(calepinage, moment=MOMENT)
        second = rendre_planche_svg(calepinage, moment=MOMENT)
        self.assertEqual(premier, second)
        self.assertIn('calepinage aaaaaaaaaaaa', premier)

    def test_une_conception_modifiee_change_l_empreinte_imprimee(self):
        # `layout_hash` EST l'empreinte de la conception (CAL13) : deux
        # conceptions différentes ne peuvent pas porter le même pied.
        avant = rendre_planche_svg(FauxCalepinage(layout_hash=HASH_A),
                                   moment=MOMENT)
        apres = rendre_planche_svg(FauxCalepinage(layout_hash=HASH_B),
                                   moment=MOMENT)
        self.assertNotEqual(avant, apres)
        self.assertIn('calepinage bbbbbbbbbbbb', apres)
        self.assertNotIn('calepinage aaaaaaaaaaaa', apres)

    def test_la_version_du_moteur_voyage_jusqu_au_pied_de_planche(self):
        svg = rendre_planche_svg(
            FauxCalepinage(version_moteur='calepinage-2.3.1'), moment=MOMENT)
        self.assertIn('moteur calepinage-2.3.1', svg)
