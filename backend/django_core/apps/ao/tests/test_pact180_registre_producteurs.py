"""PACT180 — le registre de PACT25 doit NOMMER ses producteurs, et le prouver.

LA SONDE QUI A MOTIVÉ CE TEST
-----------------------------
Une sonde a chiffré à 70 les fonctions publiques de ``apps/ao/fabrique/**``
sans aucun appelant hors tests (``rendre_checklist``, ``rendre_page_garde``,
``rendre_note_calcul``, ``fusionner_pack``, ``ecrire_pack_zip``…), TOUTES en
aval du trou décrit par PACT25. Le risque nommé : fermer PACT25 en laissant une
partie du pack silencieusement vide, parce que son registre citerait deux ou
trois rendus et oublierait les autres.

CE QUE CE MODULE VÉRIFIE — MÉCANIQUEMENT, JAMAIS PAR RELECTURE
--------------------------------------------------------------
1. **Aucun producteur NOMMÉ n'est orphelin.** Chaque nom pointé cité par
   ``fabrique.producteurs.REGISTRE`` doit se résoudre en un appelable réel
   (test PARAMÉTRÉ, un ``subTest`` par nom) : renommer ou supprimer une
   fonction de fabrique sans toucher au registre devient impossible en silence.
2. **Chaque nom vit bien dans ``apps.ao.fabrique``.** Un registre qui
   dériverait vers un autre package cesserait d'être le registre de la
   fabrique.
3. **L'INVENTAIRE des producteurs est CLOS.** Toute fonction publique des
   modules qui produisent réellement un artefact (``rendus/**``, ``pack_pdf``,
   ``pack_zip``, ``stockage``) est soit CITÉE par le registre, soit rangée
   ci-dessous avec sa raison. Une nouvelle fonction non classée fait ROUGIR ce
   test en la nommant : c'est exactement le « silencieusement vide » que
   PACT180 refuse.
4. **Le reste à câbler ne peut que RÉTRÉCIR** (cliquet) : le plafond baisse à
   chaque producteur monté, il ne remonte jamais.
"""
import ast
import pathlib

from django.test import SimpleTestCase

from apps.ao.fabrique import producteurs as registre

RACINE_FABRIQUE = (pathlib.Path(__file__).resolve().parent.parent
                   / 'fabrique')

#: Les modules qui PRODUISENT un artefact de pack. Les autres modules de la
#: fabrique (ordonnancement, montants, clauses, cascade…) sont des CALCULS
#: partagés, pas des producteurs : les inventorier ici mélangerait deux
#: natures et rendrait le cliquet illisible.
MODULES_PRODUCTEURS = ('rendus', 'pack_pdf', 'pack_zip', 'stockage')

#: Fonctions publiques des modules producteurs que le registre NE cite PAS et
#: n'a PAS à citer — chacune avec sa raison. Ce ne sont pas des producteurs de
#: pièce : les inscrire au registre serait faux.
HORS_REGISTRE_JUSTIFIE = {
    # Assemblage du ZIP lui-même : appelé par `viewsets.DossierAOViewSet.zip`
    # et `services.pieces_du_pack_en_flux`, pas par un producteur de pièce.
    'apps.ao.fabrique.pack_zip:ecrire_pack_zip',
    'apps.ao.fabrique.pack_zip:nom_de_fichier',
    'apps.ao.fabrique.pack_zip:pieces_deposables',
    # Page de séparation interne au PDF fusionné, jamais une pièce du pack.
    'apps.ao.fabrique.pack_pdf:intercalaire_html',
    # Archivage MinIO : appelé par `services._monter_producteur`, c'est le
    # SOCLE des producteurs, pas l'un d'eux.
    'apps.ao.fabrique.stockage:cle_artefact',
    'apps.ao.fabrique.stockage:ecrire_artefact',
    'apps.ao.fabrique.stockage:manifeste_courant',
    'apps.ao.fabrique.stockage:construire_manifeste',
    # DIRECTEUR — coût de revient et marge. Entrer au registre ferait tomber
    # ce classeur dans un pack de dépôt CLIENT : exactement la fuite que
    # `ao_rentabilite_voir` ferme. Son chemin est `services_directeur`.
    'apps.ao.fabrique.rendus.rentabilite_xlsx:construire_economie',
    'apps.ao.fabrique.rendus.rentabilite_xlsx:ecrire_classeur',
    # Contrôles et introspection de test, pas des rendus.
    'apps.ao.fabrique.rendus.acte_engagement:fiche_de_report',
    'apps.ao.fabrique.rendus.acte_engagement:valeur_du_blanc',
    'apps.ao.fabrique.rendus.bordereau_pdf:comparer',
    'apps.ao.fabrique.rendus.bordereau_xlsx:doit_passer_en_job',
    'apps.ao.fabrique.rendus.bordereau_xlsx:valeurs_de_controle',
    'apps.ao.fabrique.rendus.checklist_docx:texte_du_docx',
    'apps.ao.fabrique.rendus.simulation:empreinte_simulation',
    'apps.ao.fabrique.rendus.simulation:rafraichir_empreinte',
    'apps.ao.fabrique.rendus.simulation:html_simulation',
}

#: Producteurs RÉELS que le registre ne cite pas ENCORE. Chacun attend une
#: pièce de pack qui n'est pas déclarée par le gabarit d'aujourd'hui
#: (`seed_pack_ao`) : la page de garde/sommaire et le rapport de contrôle sont
#: des pages de TÊTE du pli, produites au moment du dépôt et non comme pièces
#: numérotées. CETTE LISTE NE PEUT QUE RÉTRÉCIR.
A_CABLER = {
    'apps.ao.fabrique.rendus.garde_sommaire:identite_de_garde',
    'apps.ao.fabrique.rendus.garde_sommaire:construire_sommaire',
    'apps.ao.fabrique.rendus.garde_sommaire:construire_bordereau_pieces',
    'apps.ao.fabrique.rendus.garde_sommaire:rendre_page_garde_html',
    'apps.ao.fabrique.rendus.garde_sommaire:rendre_page_garde',
    'apps.ao.fabrique.rendus.rapport_controle:construire_rapport',
    'apps.ao.fabrique.rendus.rapport_controle:est_perime',
    'apps.ao.fabrique.rendus.rapport_controle:rendre_rapport_html',
    'apps.ao.fabrique.rendus.rapport_controle:rendre_rapport',
    'apps.ao.fabrique.rendus.rapport_controle:archiver_rapport',
}

#: Cliquet : le reste à câbler ne remonte JAMAIS. Le baisser est un progrès à
#: committer ; le monter est un refus.
PLAFOND_A_CABLER = 10


def _fichiers_producteurs():
    fichiers = sorted((RACINE_FABRIQUE / 'rendus').glob('*.py'))
    fichiers += [RACINE_FABRIQUE / f'{nom}.py'
                 for nom in MODULES_PRODUCTEURS if nom != 'rendus']
    return [f for f in fichiers if f.name != '__init__.py' and f.is_file()]


def inventaire_des_producteurs():
    """Tous les noms pointés publics des modules producteurs (AST, sans import).

    Lecture STATIQUE : le test ne dépend d'aucun réglage Django ni d'aucune
    dépendance optionnelle (``python-docx``, ``openpyxl``) — un inventaire qui
    change selon les paquets installés ne serait pas un inventaire.
    """
    noms = set()
    for fichier in _fichiers_producteurs():
        relatif = fichier.relative_to(RACINE_FABRIQUE).with_suffix('')
        module = 'apps.ao.fabrique.' + '.'.join(relatif.parts)
        arbre = ast.parse(fichier.read_text(encoding='utf-8'))
        for noeud in arbre.body:
            if isinstance(noeud, (ast.FunctionDef, ast.AsyncFunctionDef)) \
                    and not noeud.name.startswith('_'):
                noms.add(f'{module}:{noeud.name}')
    return noms


class NomsDuRegistreTest(SimpleTestCase):
    """1 & 2 — aucun producteur nommé n'est orphelin, et tous sont d'ici."""

    def test_le_registre_nomme_des_fabriques(self):
        noms = registre.noms_de_fabrique()
        self.assertGreaterEqual(
            len(noms), 30,
            'Un registre qui ne cite qu\'une poignée de fabriques laisserait '
            'le reste du pack silencieusement vide — c\'est le constat de '
            'PACT180.')

    def test_chaque_nom_se_resout_en_appelable(self):
        """LE test paramétré du Done : un nom par ``subTest``."""
        for nom in registre.noms_de_fabrique():
            with self.subTest(fabrique=nom):
                fonction = registre.resoudre(nom)
                self.assertTrue(
                    callable(fonction),
                    f'{nom} ne se résout pas en appelable : le registre cite '
                    f'un producteur ORPHELIN.')

    def test_chaque_nom_vit_dans_la_fabrique_ao(self):
        for nom in registre.noms_de_fabrique():
            with self.subTest(fabrique=nom):
                self.assertTrue(
                    nom.startswith('apps.ao.fabrique.'),
                    f'{nom} sort de apps.ao.fabrique : le registre de la '
                    f'fabrique ne doit pointer que la fabrique.')
                self.assertIn(':', nom, 'Format attendu « module:fonction ».')

    def test_un_nom_inexistant_leve(self):
        """La garde ne peut pas être verte par accident."""
        with self.assertRaises((AttributeError, ImportError)):
            registre.resoudre('apps.ao.fabrique.pack_zip:fonction_fantome')


class InventaireClosTest(SimpleTestCase):
    """3 & 4 — l'inventaire est CLOS et le reste à câbler ne grandit pas."""

    def test_aucune_fonction_productrice_n_est_non_classee(self):
        inventaire = inventaire_des_producteurs()
        classees = (set(registre.noms_de_fabrique())
                    | HORS_REGISTRE_JUSTIFIE | A_CABLER)
        non_classees = sorted(inventaire - classees)
        self.assertEqual(
            non_classees, [],
            'Ces fonctions publiques de la fabrique ne sont NI citées par le '
            'registre NI classées dans ce module : une pièce pourrait partir '
            'sans producteur, en silence. Les câbler au registre, ou les '
            'ranger dans HORS_REGISTRE_JUSTIFIE avec leur raison :\n  '
            + '\n  '.join(non_classees))

    def test_aucun_classement_ne_designe_une_fonction_disparue(self):
        """Un classement qui survit à sa fonction est un mensonge figé."""
        inventaire = inventaire_des_producteurs()
        fantomes = sorted(
            (HORS_REGISTRE_JUSTIFIE | A_CABLER) - inventaire)
        self.assertEqual(
            fantomes, [],
            'Ces noms classés ne désignent plus aucune fonction publique de '
            'la fabrique — les retirer :\n  ' + '\n  '.join(fantomes))

    def test_le_reste_a_cabler_ne_peut_que_retrecir(self):
        self.assertLessEqual(
            len(A_CABLER), PLAFOND_A_CABLER,
            'Le cliquet de PACT180 est REMONTÉ : un producteur réel de plus '
            'attend son câblage. Baisser PLAFOND_A_CABLER est un progrès ; le '
            'monter est un refus.')

    def test_les_trois_ensembles_sont_disjoints(self):
        nommes = set(registre.noms_de_fabrique())
        self.assertEqual(nommes & HORS_REGISTRE_JUSTIFIE, set())
        self.assertEqual(nommes & A_CABLER, set())
        self.assertEqual(HORS_REGISTRE_JUSTIFIE & A_CABLER, set())
