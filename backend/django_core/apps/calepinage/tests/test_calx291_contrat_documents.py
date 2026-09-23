"""CALX291 — le contrat de l'inventaire « Documents » (PACT10, contrat seul).

CE QUE CE FICHIER GARDE
------------------------
`contract_samples/calepinage_documents.json` part SEUL sur `main`, avant
toute vue : ni `views/documents.py` ni `services/documents/` n'existent
encore (réservés à la phase 2 de ce lot). Ce test ne confronte donc RIEN à
une réponse HTTP réelle — il vérifie que l'ÉCHANTILLON lui-même tient les
quatre promesses de son « Done » :

1. l'enveloppe PACT10 est complète (`endpoint`/`pourquoi`/`exemple`) ;
2. les NEUF codes neufs déclarés par CALX291 sont bien les neuf documents de
   l'exemple, sans doublon ;
3. AUCUN mot de montant n'apparaît nulle part dans l'échantillon (D5 — ce
   sont des pièces TECHNIQUES, jamais un devis) ;
4. chaque document INDISPONIBLE porte AU MOINS une ligne `manque` qui NOMME
   le champ — jamais une phrase générique.

Aucune base de données, aucun réseau : un fichier JSON et le module
``json`` de la bibliothèque standard.

Run :
    python manage.py test apps.calepinage.tests.test_calx291_contrat_documents
"""
from __future__ import annotations

import json
import pathlib
import unittest

ECHANTILLONS = (pathlib.Path(__file__).resolve().parents[1]
                / 'contract_samples')


def charger(nom):
    return json.loads((ECHANTILLONS / nom).read_text(encoding='utf-8'))


CONTRAT = charger('calepinage_documents.json')

#: Les neuf codes neufs déclarés par CALX291 (lot 6, « Livrables & rapports »).
CODES_NEUFS = frozenset({
    'rapport_etude', 'rapport_ombrage', 'export_projet_json', 'plan_cablage',
    'manuel_proprietaire', 'document_asbuilt', 'dossier_fin_chantier',
    'diagramme_pertes', 'presentation_compacte',
})

#: Sous-chaînes qui trahissent un chiffre de montant — même vocabulaire que
#: la garde de surface CAL122 (`tests/test_aucun_prix_achat.py`), étendue
#: pour ce contrat aux mots que « aucun mot de montant » (Done CALX291)
#: recouvre explicitement.
MOTS_DE_MONTANT = ('prix', 'cout', 'marge', 'benefice', 'remise', 'montant',
                   'tarif', 'facture_ttc', 'mad')


def cles_de_montant(objet, chemin='<racine>'):
    """``[(chemin, cle)]`` — chaque CLÉ qui contient un mot de montant, où
    qu'elle vive dans une structure JSON imbriquée. Fonction PURE."""
    trouvees = []
    if isinstance(objet, dict):
        for cle, valeur in objet.items():
            texte = str(cle).lower()
            if any(mot in texte for mot in MOTS_DE_MONTANT):
                trouvees.append((chemin, str(cle)))
            trouvees.extend(cles_de_montant(valeur, f'{chemin}.{cle}'))
    elif isinstance(objet, (list, tuple)):
        for index, item in enumerate(objet):
            trouvees.extend(cles_de_montant(item, f'{chemin}[{index}]'))
    return trouvees


class EnveloppeTest(unittest.TestCase):
    """L'échantillon porte l'enveloppe PACT10 et vise la bonne route."""

    def test_enveloppe_complete(self):
        for cle in ('endpoint', 'pourquoi', 'exemple'):
            self.assertIn(cle, CONTRAT,
                          f'calepinage_documents.json : clé « {cle} » '
                          'absente — check_api_shapes ne saurait pas le '
                          'lire.')
        self.assertTrue(CONTRAT['endpoint'].strip())

    def test_la_route_est_bien_le_nouvel_inventaire_documents(self):
        self.assertEqual(
            CONTRAT['endpoint'],
            'GET /api/django/calepinage/calepinages/<int:pk>/documents/')

    def test_la_route_de_publication_image_est_documentee_a_part(self):
        """CAL175 : aucun rasteriseur serveur — le PNG vient du navigateur,
        déposé par une DEUXIÈME route, documentée mais pas confondue avec
        la première (jamais de `forme_serveur` dessus : elle ne PEUT pas
        être confrontée à une vue GET)."""
        publication = CONTRAT['publication_image']
        self.assertEqual(
            publication['endpoint'],
            'POST /api/django/calepinage/calepinages/<int:pk>/'
            'image-document/')
        self.assertNotIn('forme_serveur', publication)
        for cle in ('genre', 'fichier'):
            self.assertIn(cle, publication['body'])


class NeufCodesNeufsTest(unittest.TestCase):
    """Les neuf codes du lot 6, et rien de moins, dans `exemple`."""

    def test_les_neuf_codes_neufs_sont_tous_presents(self):
        codes = {doc['code'] for doc in CONTRAT['exemple']['documents']}
        self.assertEqual(codes, CODES_NEUFS)

    def test_exactement_neuf_documents_sans_doublon(self):
        codes = [doc['code'] for doc in CONTRAT['exemple']['documents']]
        self.assertEqual(len(codes), 9)
        self.assertEqual(len(codes), len(set(codes)),
                         'un code apparaît deux fois : `check_api_shapes` '
                         "et l'écran qui lira cet inventaire perdraient "
                         "l'un des deux.")

    def test_chaque_document_porte_les_neuf_cles_du_contrat(self):
        attendues = {'code', 'libelle', 'format', 'endpoint', 'produit_par',
                     'disponible', 'motif_indisponible', 'manque',
                     'versions'}
        for document in CONTRAT['exemple']['documents']:
            self.assertEqual(set(document), attendues,
                             f"document « {document.get('code')} » hors "
                             'contrat.')

    def test_exemple_vide_porte_les_memes_neuf_codes(self):
        """Discipline de la complétude (README règle 3) : un calepinage
        neuf continue de LISTER les neuf documents, tous indisponibles."""
        codes = {doc['code'] for doc in CONTRAT['exemple_vide']['documents']}
        self.assertEqual(codes, CODES_NEUFS)
        for document in CONTRAT['exemple_vide']['documents']:
            self.assertFalse(document['disponible'], document['code'])


class DisponibiliteEtManqueTest(unittest.TestCase):
    """Done CALX291 : une entrée indisponible porte AU MOINS un `manque`."""

    def test_au_moins_une_entree_indisponible_dans_l_exemple(self):
        """Sinon la promesse ci-dessous ne serait vérifiée sur rien."""
        indisponibles = [doc for doc in CONTRAT['exemple']['documents']
                         if not doc['disponible']]
        self.assertTrue(indisponibles,
                        "l'exemple doit montrer au moins un document "
                        'indisponible : sinon le contrat ne prouve jamais '
                        'la discipline `manque`.')

    def test_chaque_entree_indisponible_porte_au_moins_une_ligne_manque(self):
        for document in CONTRAT['exemple']['documents']:
            if document['disponible']:
                continue
            self.assertTrue(
                document['manque'],
                f"document « {document['code']} » indisponible sans AUCUNE "
                'ligne `manque` : le motif ne peut pas rester une phrase '
                'libre non actionnable.')
            for ligne in document['manque']:
                for cle in ('champ', 'libelle', 'ou_saisir'):
                    self.assertIn(cle, ligne)
                    self.assertTrue(str(ligne[cle]).strip(),
                                    f"« {document['code']} » : la ligne "
                                    f'manque[{cle}] est vide.')

    def test_chaque_entree_indisponible_porte_un_motif_non_vide(self):
        for document in CONTRAT['exemple']['documents']:
            if document['disponible']:
                continue
            self.assertTrue((document['motif_indisponible'] or '').strip(),
                            document['code'])

    def test_une_entree_disponible_ne_porte_aucun_motif(self):
        for document in CONTRAT['exemple']['documents']:
            if document['disponible']:
                self.assertIsNone(document['motif_indisponible'],
                                  document['code'])

    def test_exemple_vide_aussi_nomme_le_champ_manquant(self):
        for document in CONTRAT['exemple_vide']['documents']:
            self.assertTrue(document['manque'], document['code'])
            self.assertIn('roof_layout', document['manque'][0]['champ'])


class DisciplineDuNullTest(unittest.TestCase):
    """Une grandeur non calculée vaut `null`, jamais une chaîne vide."""

    def test_layout_hash_et_version_moteur_valent_null_sur_le_neuf(self):
        vide = CONTRAT['exemple_vide']
        self.assertIsNone(vide['layout_hash'])
        self.assertIsNone(vide['version_moteur'])
        self.assertIsNone(vide['langue'])

    def test_les_images_sont_une_liste_vide_jamais_null_sur_le_neuf(self):
        self.assertEqual(CONTRAT['exemple_vide']['images'], [])

    def test_versions_est_toujours_une_liste_jamais_null(self):
        for etat in ('exemple', 'exemple_vide'):
            for document in CONTRAT[etat]['documents']:
                self.assertIsInstance(document['versions'], list,
                                      f"{etat} : « {document['code']} » "
                                      "porte des versions d'un autre type "
                                      'que `list`.')


class AucunMotDeMontantTest(unittest.TestCase):
    """D5 — ce sont des pièces TECHNIQUES : Done CALX291 l'exige au mot
    près (« l'absence de tout mot de montant »)."""

    def test_le_detecteur_rougit_sur_une_cle_ajoutee_volontairement(self):
        """Preuve que le détecteur fonctionne — sinon les assertions
        « propre » ci-dessous ne prouveraient rien."""
        self.assertEqual(
            cles_de_montant({'prix_ttc': 100}),
            [('<racine>', 'prix_ttc')])
        self.assertEqual(
            cles_de_montant({'documents': [{'tarif_pdf': 1}]}),
            [('<racine>.documents[0]', 'tarif_pdf')])
        self.assertEqual(cles_de_montant({'ok': True}), [])

    def test_l_exemple_ne_porte_aucun_mot_de_montant(self):
        self.assertEqual(cles_de_montant(CONTRAT['exemple']), [])

    def test_l_exemple_vide_ne_porte_aucun_mot_de_montant(self):
        self.assertEqual(cles_de_montant(CONTRAT['exemple_vide']), [])

    def test_la_publication_image_ne_porte_aucun_mot_de_montant(self):
        self.assertEqual(cles_de_montant(CONTRAT['publication_image']), [])

    def test_aucun_libelle_ne_contient_un_mot_de_montant(self):
        """Les CLÉS sont couvertes ci-dessus ; les LIBELLÉS affichés à
        l'écran le sont ici, séparément (un texte peut être propre en clé
        et fautif en valeur affichée)."""
        for document in CONTRAT['exemple']['documents']:
            texte = document['libelle'].lower()
            for mot in MOTS_DE_MONTANT:
                self.assertNotIn(mot, texte,
                                 f"« {document['code']} » : le libellé "
                                 f'contient le mot « {mot} ».')


if __name__ == '__main__':  # pragma: no cover
    unittest.main()
