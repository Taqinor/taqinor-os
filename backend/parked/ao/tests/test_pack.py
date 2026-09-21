"""PACT25 — le trou central du dossier de soumission : le MONTEUR de pièces.

Toute la machinerie basse existait (écriture en flux, refus si un contrôle est
rouge, orchestration idempotente, suivi de tâche) mais **rien ne lui fournissait
les pièces**. Trois chemins (``generer-piece``, ``zip``, ``statut-de-job``)
étaient délibérément fermés : ouvrir la porte aurait produit une tâche se
terminant « terminée » avec ZÉRO pièce, donc un écran affichant « pack prêt »
sur une **archive vide**. Un faux succès est pire qu'un 404 parce qu'il se
dépose.

Ce module vérifie exactement les promesses du Done :
  1. le registre associe chaque type de pièce à un producteur RÉEL et NOMMÉ ;
  2. un générateur inconnu ne produit rien et rend le pack INCOMPLET ;
  3. un pack VIDE ne peut PAS se terminer vert (le job part en ÉCHEC) ;
  4. un pack vide ne peut PAS être marqué « prêt à déposer » ;
  5. le ZIP refuse une archive sans pièce déposable et refuse un contrôle rouge.

Ces tests sont volontairement SANS BASE (``SimpleTestCase``) là où c'est
possible : le registre et l'orchestrateur sont purs, et un test qui n'a pas
besoin de la base est un test qui tourne dans tous les shards.

Run :
    python manage.py test apps.ao.tests.test_pack -v2
"""
from django.test import SimpleTestCase

from apps.ao.fabrique import producteurs as registre
from apps.ao.tasks import ETAT_ECHOUEE, produire_pack

EMPREINTE = 'c' * 64

#: Les 9 pièces du gabarit de pack réel (``seed_pack_ao.PIECES_PACK``) : le
#: registre DOIT toutes les couvrir, sinon une pièce déclarée par le gabarit
#: partirait sans producteur, en silence.
GENERATEURS_DU_GABARIT = (
    'administratif', 'annexes', 'bordereau', 'checklist', 'lettre_soumission',
    'memoire', 'note_calcul', 'planches', 'simulation',
)


class RegistreProducteursTest(SimpleTestCase):
    """Le registre : chaque type de pièce a une entrée, et elle est nommée."""

    def test_les_neuf_pieces_du_gabarit_ont_une_entree(self):
        manquants = [code for code in GENERATEURS_DU_GABARIT
                     if registre.producteur_pour(code) is None]
        self.assertEqual(
            manquants, [],
            'Ces générateurs du gabarit de pack (seed_pack_ao) n\'ont aucune '
            'entrée au registre — ils partiraient sans producteur, en '
            f'silence : {manquants}')

    def test_chaque_entree_nomme_au_moins_une_fabrique(self):
        """PACT180 — un producteur sans fabrique nommée est un trou muet."""
        for code, producteur in registre.REGISTRE.items():
            with self.subTest(generateur=code):
                self.assertTrue(
                    producteur.fabriques,
                    f'Le producteur « {code} » ne nomme aucune fonction de '
                    f'fabrique : impossible de vérifier qu\'il n\'est pas '
                    f'orphelin.')
                self.assertTrue(producteur.libelle)

    def test_un_generateur_inconnu_n_a_pas_de_producteur(self):
        self.assertIsNone(registre.producteur_pour('inexistant'))
        self.assertIsNone(registre.producteur_pour(''))
        self.assertIsNone(registre.producteur_pour(None))

    def test_un_producteur_non_monte_echoue_en_le_disant(self):
        """Jamais une pièce vide : l'absence de monteur est un ÉCHEC NOMMÉ."""
        non_montes = [p for p in registre.REGISTRE.values() if not p.monte]
        self.assertTrue(
            non_montes,
            'Ce test perd son sens si tous les producteurs sont montés — '
            'le supprimer alors, ne pas le neutraliser.')
        for producteur in non_montes:
            with self.subTest(generateur=producteur.generateur):
                self.assertTrue(
                    producteur.motif_indisponible,
                    'Un producteur non monté DOIT porter un motif français : '
                    'un échec anonyme est un silence.')
                with self.assertRaises(registre.ProducteurIndisponible):
                    producteur.octets(None, None)

    def test_le_classeur_directeur_n_est_jamais_dans_un_pack(self):
        """``rentabilite_xlsx`` porte le coût de revient : il n'entre pas.

        L'inscrire au registre le ferait tomber dans un pack de dépôt CLIENT —
        exactement la fuite de marge que ``ao_rentabilite_voir`` ferme.
        """
        for producteur in registre.REGISTRE.values():
            for nom in producteur.fabriques:
                self.assertNotIn('rentabilite', nom, producteur.generateur)


class PackVideEtIncompletTest(SimpleTestCase):
    """Un pack vide ou incomplet ne peut PAS se terminer vert."""

    def test_un_pack_sans_piece_n_est_jamais_complet(self):
        rapport = produire_pack([], empreinte_contexte=EMPREINTE)
        self.assertEqual(rapport['total'], 0)
        self.assertFalse(
            rapport['complet'],
            'Un pack SANS AUCUNE pièce ne doit jamais être « complet » : '
            'c\'est exactement le faux succès que PACT25 supprime.')

    def test_une_piece_sans_producteur_rend_le_pack_incomplet(self):
        """Le cas d'un générateur absent du registre : nommé, jamais tu."""
        rapport = produire_pack(
            [{'code': '04', 'libelle': 'Bordereau des prix'}],
            empreinte_contexte=EMPREINTE)
        self.assertFalse(rapport['complet'])
        self.assertEqual(len(rapport['echecs']), 1)
        self.assertEqual(rapport['echecs'][0]['code'], '04')
        self.assertEqual(rapport['resultats'][0]['etat'], ETAT_ECHOUEE)

    def test_une_piece_produisant_du_vide_est_un_echec_nomme(self):
        def _vide():
            raise registre.ProducteurIndisponible(
                'contenu vide refusé pour la pièce 02')

        rapport = produire_pack(
            [{'code': '02', 'libelle': 'Mémoire', 'producteur': _vide}],
            empreinte_contexte=EMPREINTE)
        self.assertFalse(rapport['complet'])
        self.assertIn('vide', rapport['echecs'][0]['motif'])

    def test_un_pack_partiel_reste_incomplet(self):
        """Huit pièces vertes et une rouge : le pack N'EST PAS prêt."""
        pieces = [{'code': f'0{i}', 'libelle': f'Pièce {i}',
                   'producteur': (lambda: 'ok')} for i in range(8)]
        pieces.append({'code': '08', 'libelle': 'Administratif'})
        rapport = produire_pack(pieces, empreinte_contexte=EMPREINTE)
        self.assertEqual(rapport['produites'], 8)
        self.assertFalse(rapport['complet'])


class ZipRefusTest(SimpleTestCase):
    """Le ZIP refuse plutôt que de déposer une archive fausse."""

    def test_zip_refuse_sans_piece_deposable(self):
        import io

        from apps.ao.fabrique.pack_zip import PackRefuse, ecrire_pack_zip

        with self.assertRaises(PackRefuse):
            ecrire_pack_zip(io.BytesIO(), [], controle={'bloquants': []})

    def test_zip_refuse_quand_un_controle_est_rouge(self):
        import io

        from apps.ao.fabrique.pack_zip import PackRefuse, ecrire_pack_zip

        piece = {'code': '01', 'libelle': 'Lettre', 'visibilite': 'client',
                 'format': 'pdf', 'empreinte': EMPREINTE,
                 'flux': lambda: [b'%PDF-1.4']}
        with self.assertRaises(PackRefuse):
            ecrire_pack_zip(
                io.BytesIO(), [piece],
                controle={'bloquants': [
                    {'code': 'AO-COH-01', 'message': 'totaux divergents'}]})

    def test_zip_ecrit_toutes_les_pieces_deposables(self):
        """« le ZIP les contient toutes » — vérifié sur le manifeste écrit."""
        import io
        import zipfile

        from apps.ao.fabrique.pack_zip import ecrire_pack_zip

        pieces = [
            {'code': '01', 'libelle': 'Lettre de soumission',
             'visibilite': 'client', 'format': 'pdf', 'empreinte': EMPREINTE,
             'flux': lambda: [b'%PDF-1.4 lettre']},
            {'code': '04', 'libelle': 'Bordereau des prix',
             'visibilite': 'client', 'format': 'pdf', 'empreinte': EMPREINTE,
             'flux': lambda: [b'%PDF-1.4 bordereau']},
        ]
        tampon = io.BytesIO()
        manifeste = ecrire_pack_zip(
            tampon, pieces, controle={'bloquants': []},
            reference_dossier='AODOS-202608-0001', empreinte_pack=EMPREINTE)
        self.assertEqual(len(manifeste['pieces']), 2)
        with zipfile.ZipFile(io.BytesIO(tampon.getvalue())) as archive:
            noms = archive.namelist()
        for entree in manifeste['pieces']:
            self.assertIn(entree['fichier'], noms)
