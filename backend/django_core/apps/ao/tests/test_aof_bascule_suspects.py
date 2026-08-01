"""AOF142 — reproduction du défaut réel « 2 800 vs 2 600 » + annexes.

Le cas est textuel : lors de la bascule batterie BOS-G → BOS-B Pro-A3, le
montant final a bien été cascadé (bordereau à 2 600 DH HT/kWh), mais une
parenthèse de justification d'un document annexe disait toujours
« batteries 2 800 DH HT/kWh ». Aucun contrôle STRUCTUREL ne voit ça : la
parenthèse est du texte libre et elle n'a pas changé — c'est précisément le
problème.

Run :
    python manage.py test apps.ao.tests.test_aof_bascule_suspects -v2
"""
from decimal import Decimal

from django.test import SimpleTestCase

from apps.ao.fabrique.annexes import (
    appliquer_bascule, controler_annexes, fiches_manquantes,
    fiches_orphelines, index_annexes,
)
from apps.ao.fabrique.bascule_rapport import (
    emplacements_suspects, nombres_du_texte, normaliser, plan_bascule,
    rapport_bascule,
)

ANCIEN = {
    'designation': 'Batterie lithium BOS-G 16,08 kWh',
    'reference': 'BOS-G',
    'marque': 'BOS',
    'prix_unitaire': Decimal('2800'),
    'unite': 'kWh',
    'caracteristiques': {'kwh_pack': Decimal('16.08'),
                         'tension_pack_v': Decimal('51.2')},
}
NOUVEAU = {
    'designation': 'Batterie lithium BOS-B Pro-A3 16,08 kWh',
    'reference': 'BOS-B Pro-A3',
    'marque': 'BOS',
    'prix_unitaire': Decimal('2600'),
    'unite': 'kWh',
    'caracteristiques': {'kwh_pack': Decimal('16.08'),
                         'tension_pack_v': Decimal('51.2'),
                         'cycles': 8000},
}


class DefautReelTest(SimpleTestCase):
    """La justification restée en arrière de son propre montant."""

    def test_la_parenthese_a_2800_est_detectee(self):
        textes = [{
            'emplacement': 'Word « À REMPLIR PAR ACCORDIA » — justification',
            'texte': ("Le montant total s'établit à 4 999 920 DH TTC "
                      "(batteries 2 800 DH HT/kWh, pose comprise)."),
        }]
        suspects = emplacements_suspects(textes, ANCIEN, NOUVEAU)
        motifs = [suspect['motif'] for suspect in suspects]
        self.assertIn('ancien_prix', motifs)
        prix = [s for s in suspects if s['motif'] == 'ancien_prix'][0]
        self.assertEqual(prix['valeur'], Decimal('2800'))
        self.assertEqual(prix['attendu'], Decimal('2600'))
        self.assertIn('ACCORDIA', prix['emplacement'])
        self.assertIn('2 800', prix['extrait'])

    def test_un_texte_deja_cascade_n_est_pas_suspect(self):
        textes = [{
            'emplacement': 'mémoire §4.2',
            'texte': ("Le montant total s'établit à 4 999 920 DH TTC "
                      "(batteries 2 600 DH HT/kWh, pose comprise)."),
        }]
        self.assertEqual(emplacements_suspects(textes, ANCIEN, NOUVEAU), [])

    def test_un_texte_qui_cite_les_deux_prix_n_est_pas_suspect(self):
        """Un tableau comparatif AVANT/APRÈS est légitime."""
        textes = [{
            'emplacement': 'note de variante',
            'texte': 'Prix antérieur 2 800 DH/kWh, prix retenu 2 600 DH/kWh.',
        }]
        suspects = [s for s in emplacements_suspects(textes, ANCIEN, NOUVEAU)
                    if s['motif'] == 'ancien_prix']
        self.assertEqual(suspects, [])

    def test_l_ancienne_reference_survivante_est_detectee(self):
        textes = [{'emplacement': 'mémoire §7 — maintenance',
                   'texte': 'Les packs bos-g seront maintenus annuellement.'}]
        suspects = emplacements_suspects(textes, ANCIEN, NOUVEAU)
        self.assertEqual(suspects[0]['motif'], 'ancienne_reference')
        self.assertEqual(suspects[0]['champ'], 'reference')

    def test_le_rapport_est_bloquant_tant_qu_un_suspect_subsiste(self):
        textes = [{'emplacement': 'annexe', 'texte': 'batteries 2 800 DH'}]
        rapport = rapport_bascule(ANCIEN, NOUVEAU, textes=textes,
                                  emplacements_modifies=['bordereau ligne 12'])
        self.assertTrue(rapport['bloquant'])
        self.assertEqual(rapport['modifies'], ['bordereau ligne 12'])
        propre = rapport_bascule(ANCIEN, NOUVEAU, textes=[])
        self.assertFalse(propre['bloquant'])


class NombresEtNormalisationTest(SimpleTestCase):
    def test_les_espaces_de_milliers_sont_absorbes(self):
        # Écritures en ÉCHAPPEMENTS : une espace fine invisible dans un
        # test est indébogable le jour où il devient rouge.
        ecritures = ('2\u202f800', '2\u00a0800', '2\u2009800',
                     '2 800', '2.800', '2800')
        for ecriture in ecritures:
            valeurs = [v for v, _b, _p in nombres_du_texte(ecriture)]
            self.assertIn(Decimal('2800'), valeurs, repr(ecriture))

    def test_la_virgule_decimale_est_reconnue(self):
        valeurs = [v for v, _b, _p in nombres_du_texte('4 999 920,50 DH')]
        self.assertIn(Decimal('4999920.50'), valeurs)

    def test_normaliser_rapproche_les_ecritures_d_une_reference(self):
        self.assertEqual(normaliser('BOS-G'), normaliser('bos g'))
        self.assertEqual(normaliser('Réf. BOS-B Pro-A3'),
                         'ref bos b pro a3')


class PlanBasculeTest(SimpleTestCase):
    def test_le_plan_couvre_champs_caracteristiques_et_annexe(self):
        plan = plan_bascule(ANCIEN, NOUVEAU,
                            emplacements=['mémoire §3', 'bordereau L12'])
        natures = [changement['nature'] for changement in plan]
        self.assertIn('champ', natures)
        self.assertIn('caracteristique', natures)
        self.assertIn('emplacement', natures)
        self.assertIn('annexe', natures)
        champs = [c['champ'] for c in plan if c['nature'] == 'champ']
        self.assertIn('designation', champs)
        self.assertIn('reference', champs)
        self.assertIn('prix_unitaire', champs)
        annexe = [c for c in plan if c['nature'] == 'annexe'][0]
        self.assertEqual(annexe['retirer'], 'BOS-G')
        self.assertEqual(annexe['ajouter'], 'BOS-B Pro-A3')

    def test_une_caracteristique_inchangee_n_entre_pas_au_plan(self):
        plan = plan_bascule(ANCIEN, NOUVEAU)
        cles = [c['champ'] for c in plan if c['nature'] == 'caracteristique']
        self.assertNotIn('tension_pack_v', cles)
        self.assertIn('cycles', cles)


def equipements():
    return [
        {'reference': 'JKM-625', 'designation': 'Module 625 Wc',
         'role': 'module', 'actif': True},
        {'reference': 'BOS-B Pro-A3', 'designation': 'Batterie BOS-B Pro-A3',
         'role': 'batterie', 'actif': True},
        {'reference': 'BOS-G', 'designation': 'Batterie BOS-G',
         'role': 'batterie', 'actif': False},
        {'reference': 'OND-110', 'designation': 'Onduleur 110 kW',
         'role': 'onduleur', 'actif': True},
    ]


def fiches():
    return [
        {'reference_equipement': 'JKM-625', 'titre': 'Fiche module',
         'pages': 2, 'empreinte': 'a' * 64},
        {'reference_equipement': 'BOS-G', 'titre': 'Fiche BOS-G',
         'pages': 4, 'empreinte': 'b' * 64},
        {'reference_equipement': 'OND-110', 'titre': 'Fiche onduleur',
         'pages': 3, 'empreinte': 'c' * 64},
    ]


class AnnexesTest(SimpleTestCase):
    def test_une_fiche_orpheline_est_detectee(self):
        orphelines = fiches_orphelines(equipements(), fiches())
        self.assertEqual([f['reference_equipement'] for f in orphelines],
                         ['BOS-G'])

    def test_un_equipement_actif_sans_fiche_est_detecte(self):
        manquantes = fiches_manquantes(equipements(), fiches())
        self.assertEqual([e['reference'] for e in manquantes],
                         ['BOS-B Pro-A3'])

    def test_la_bascule_retire_l_ancienne_et_ajoute_la_nouvelle(self):
        resultat = appliquer_bascule(
            fiches(), ancienne_reference='BOS-G',
            nouvelle_fiche={'reference_equipement': 'BOS-B Pro-A3',
                            'titre': 'Fiche BOS-B Pro-A3', 'pages': 5,
                            'empreinte': 'd' * 64})
        references = [f['reference_equipement'] for f in resultat]
        self.assertNotIn('BOS-G', references)
        self.assertIn('BOS-B Pro-A3', references)
        # Aucune fiche orpheline ne survit à la bascule.
        controle = controler_annexes(equipements(), resultat)
        self.assertEqual(controle['orphelines'], [])
        self.assertEqual(controle['manquantes'], [])
        self.assertFalse(controle['bloquant'])

    def test_la_bascule_ne_mute_pas_la_liste_d_origine(self):
        origine = fiches()
        appliquer_bascule(origine, ancienne_reference='BOS-G')
        self.assertEqual(len(origine), 3)

    def test_une_fiche_sans_equipement_est_refusee(self):
        with self.assertRaises(ValueError):
            appliquer_bascule(fiches(), ancienne_reference='BOS-G',
                              nouvelle_fiche={'titre': 'Fiche sans repère'})

    def test_l_index_est_genere_numerote_et_ordonne(self):
        index = index_annexes(equipements(), fiches())
        self.assertEqual([e['numero'] for e in index], [1, 2, 3])
        # module → onduleur → batterie : l'ordre vient d'ORDRE_ROLES, pas de
        # l'ordre d'arrivée des équipements.
        self.assertEqual([e['role'] for e in index],
                         ['module', 'onduleur', 'batterie'])
        self.assertEqual([e['presente'] for e in index], [True, True, False])

    def test_une_fiche_ajoutee_se_numerote_toute_seule(self):
        complet = appliquer_bascule(
            fiches(), ancienne_reference='BOS-G',
            nouvelle_fiche={'reference_equipement': 'BOS-B Pro-A3',
                            'titre': 'Fiche BOS-B Pro-A3', 'pages': 5})
        index = index_annexes(equipements(), complet)
        self.assertTrue(all(entree['presente'] for entree in index))
        self.assertEqual([e['numero'] for e in index], [1, 2, 3])
