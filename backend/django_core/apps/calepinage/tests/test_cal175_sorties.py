"""CAL175 — l'agrégat « sorties » SERT la forme que le contrat publie.

L'échantillon ``contract_samples/calepinage_sorties.json`` est parti SEUL sur la
branche avant toute lane (PACT10) ; ce fichier est l'autre moitié du contrat :
il confronte la réponse RÉELLE à l'échantillon, dans les deux sens. Sans lui,
l'échantillon pourrirait dans son coin — ce qui est pire que pas d'échantillon
du tout.

Deux niveaux :

1. PURS (exécutables ici) — la forme, les codes, les motifs et la discipline du
   null sont vérifiés sur un faux calepinage, sans base ;
2. HTTP (base) — la route existe, elle est bornée société et bornée permission.

Run :
    python manage.py test apps.calepinage.tests.test_cal175_sorties -v2
"""
import json
import pathlib

from django.test import SimpleTestCase

from apps.calepinage.views.sorties import inventaire_des_sorties

from .test_cal171_planche import LAYOUT

RACINE_APP = pathlib.Path(__file__).resolve().parents[1]
CONTRAT = json.loads(
    (RACINE_APP / 'contract_samples' / 'calepinage_sorties.json')
    .read_text(encoding='utf-8'))


class FauxCalepinage:
    """Les seuls champs que l'inventaire LIT — rien de plus."""

    def __init__(self, **champs):
        self.pk = champs.get('pk', 41)
        self.titre = champs.get('titre', 'Toiture atelier — Bouskoura')
        self.layout_hash = champs.get('layout_hash', '0' * 63 + '1')
        self.version_moteur = champs.get('version_moteur', 'calepinage-1.0.0')
        self.roof_layout = champs.get('roof_layout', LAYOUT)
        self.resultat = champs.get('resultat', {'pose': {'total_modules': 2}})
        self.roof_image = champs.get('roof_image', 'roofs/1/calepinage-41.png')


class FormeDuContratTest(SimpleTestCase):
    def setUp(self):
        self.reponse = inventaire_des_sorties(FauxCalepinage())

    def test_les_cles_de_racine_sont_celles_du_contrat(self):
        self.assertEqual(sorted(self.reponse),
                         sorted(CONTRAT['exemple']))

    def test_les_cles_d_une_sortie_sont_celles_du_contrat(self):
        attendues = sorted(CONTRAT['exemple']['sorties'][0])
        for sortie in self.reponse['sorties']:
            self.assertEqual(sorted(sortie), attendues,
                             'sortie « %s » hors contrat' % sortie.get('code'))

    def test_les_codes_et_l_ordre_sont_ceux_du_contrat(self):
        self.assertEqual([s['code'] for s in self.reponse['sorties']],
                         [s['code'] for s in CONTRAT['exemple']['sorties']])

    def test_les_adresses_sont_celles_du_contrat_pour_ce_calepinage(self):
        attendues = [s['endpoint'] for s in CONTRAT['exemple']['sorties']]
        self.assertEqual([s['endpoint'] for s in self.reponse['sorties']],
                         attendues)

    def test_le_png_est_produit_par_le_navigateur(self):
        png = [s for s in self.reponse['sorties']
               if s['code'] == 'planche_png'][0]
        svg = [s for s in self.reponse['sorties']
               if s['code'] == 'planche_svg'][0]
        self.assertEqual(png['produit_par'], 'navigateur')
        # Le navigateur convertit le SVG FRÈRE : même adresse, pas une route
        # `planche.png` qui n'existe pas côté serveur.
        self.assertEqual(png['endpoint'], svg['endpoint'])


class DisponibiliteTest(SimpleTestCase):
    def test_une_sortie_prete_ne_porte_aucun_motif(self):
        for sortie in inventaire_des_sorties(FauxCalepinage())['sorties']:
            if sortie['disponible']:
                self.assertIsNone(sortie['motif_indisponible'])

    def test_sans_conception_tout_est_indisponible_avec_son_motif(self):
        reponse = inventaire_des_sorties(
            FauxCalepinage(roof_layout=None, resultat=None, roof_image='',
                           layout_hash='', version_moteur=''))
        self.assertEqual(len(reponse['sorties']),
                         len(CONTRAT['exemple_vide']['sorties']))
        for sortie in reponse['sorties']:
            self.assertFalse(sortie['disponible'], sortie['code'])
            self.assertTrue(sortie['motif_indisponible'], sortie['code'])

    def test_une_sortie_indisponible_reste_listee(self):
        # La masquer laisserait l'écran muet sur une absence qui a une cause.
        codes = [s['code'] for s in inventaire_des_sorties(
            FauxCalepinage(roof_layout=None))['sorties']]
        self.assertIn('planche_pdf', codes)

    def test_sans_parcelle_seul_le_plan_de_masse_tombe(self):
        reponse = inventaire_des_sorties(FauxCalepinage())
        masse = [s for s in reponse['sorties']
                 if s['code'] == 'plan_masse_pdf'][0]
        toiture = [s for s in reponse['sorties']
                   if s['code'] == 'plan_toiture_pdf'][0]
        self.assertFalse(masse['disponible'])
        self.assertIn('parcelle', masse['motif_indisponible'])
        self.assertTrue(toiture['disponible'])

    def test_sans_resultat_la_note_de_calcul_tombe_seule(self):
        reponse = inventaire_des_sorties(FauxCalepinage(resultat=None))
        note = [s for s in reponse['sorties']
                if s['code'] == 'note_calcul_pdf'][0]
        planche = [s for s in reponse['sorties']
                   if s['code'] == 'planche_pdf'][0]
        self.assertFalse(note['disponible'])
        self.assertTrue(planche['disponible'])

    def test_l_empreinte_non_calculee_vaut_null_jamais_chaine_vide(self):
        reponse = inventaire_des_sorties(
            FauxCalepinage(layout_hash='', version_moteur=''))
        self.assertIsNone(reponse['layout_hash'])
        self.assertIsNone(reponse['version_moteur'])
