"""AOF112 — le contrat `ResultatCalepinage` et l'interdiction de dériver.

    python -m unittest apps.ao.tests.test_aof_contrat_calepinage -v
"""
import ast
import pathlib
import unittest

from apps.ao.fabrique.resultat_calepinage import (
    ContratCalepinageInvalide, LotCalepinage, Marges, Planche,
    ResultatCalepinage, Sensibilite, valider_lot)

HASH = 'a' * 64
FABRIQUE = pathlib.Path(__file__).resolve().parents[1] / 'fabrique'


def resultat(**champs):
    """Le bâtiment C de FRDISI : 314 modules, optimum prouvé au DP exact."""
    base = {
        'batiment': 'C', 'compte_retenu': 314, 'compte_optimal': 314,
        'optimal': True, 'kwc': 196.25, 'methode': 'dp_exact',
        'pas_recherche_m': 0.01, 'hash_entree': HASH,
        'version_moteur': '1.0.0',
    }
    base.update(champs)
    return ResultatCalepinage(**base)


class TestValidationStricte(unittest.TestCase):

    def test_cas_reel_valide(self):
        self.assertIs(resultat().valider().compte_retenu, 314)

    def test_refuse_un_retenu_inferieur_a_l_optimum(self):
        """LE refus structurant du contrat."""
        with self.assertRaises(ContratCalepinageInvalide) as cm:
            resultat(compte_retenu=288, optimal=False).valider()
        self.assertIn('INFÉRIEUR', str(cm.exception))

    def test_accepte_un_retenu_superieur_a_l_optimum_publie(self):
        """Un optimum publié comme BORNE peut être dépassé par le retenu."""
        resultat(compte_retenu=320, compte_optimal=314,
                 optimal=False).valider()

    def test_optimum_prouve_interdit_sur_methode_non_exacte(self):
        with self.assertRaises(ContratCalepinageInvalide):
            resultat(methode='heuristique').valider()

    def test_optimum_prouve_exige_l_egalite(self):
        with self.assertRaises(ContratCalepinageInvalide):
            resultat(compte_retenu=320, optimal=True).valider()

    def test_methode_inconnue_refusee(self):
        with self.assertRaises(ContratCalepinageInvalide):
            resultat(methode='au_jugé').valider()

    def test_compte_non_entier_refuse(self):
        for mauvais in (314.0, '314', True, None):
            with self.assertRaises(ContratCalepinageInvalide, msg=mauvais):
                resultat(compte_retenu=mauvais).valider()

    def test_modules_sans_puissance_refuses(self):
        with self.assertRaises(ContratCalepinageInvalide):
            resultat(kwc=0.0).valider()

    def test_hash_entree_obligatoire_et_hexadecimal(self):
        for mauvais in ('', 'pas-un-hash', 'z' * 64, HASH[:63]):
            with self.assertRaises(ContratCalepinageInvalide, msg=mauvais):
                resultat(hash_entree=mauvais).valider()

    def test_version_moteur_obligatoire(self):
        with self.assertRaises(ContratCalepinageInvalide):
            resultat(version_moteur='  ').valider()

    def test_non_engageable_exige_un_motif(self):
        with self.assertRaises(ContratCalepinageInvalide):
            resultat(engageable=False).valider()
        resultat(engageable=False,
                 motifs_non_engageable=('relevé incomplet',)).valider()


class TestSensibilites(unittest.TestCase):

    def test_delta_incoherent_refuse(self):
        """Une sensibilité recopiée à la main est attrapée au contrat."""
        with self.assertRaises(ContratCalepinageInvalide) as cm:
            resultat(sensibilites=(
                Sensibilite('S1', 'obstacle +20 cm', 300, -10),)).valider()
        self.assertIn('recopiée', str(cm.exception))

    def test_delta_coherent_accepte(self):
        resultat(sensibilites=(
            Sensibilite('S1', 'obstacle +20 cm', 300, -14),)).valider()

    def test_plancher_doit_egaler_le_pire_cas(self):
        sensibilites = (Sensibilite('S1', 'x', 300, -14),
                        Sensibilite('S2', 'y', 290, -24))
        resultat(sensibilites=sensibilites, plancher=290).valider()
        with self.assertRaises(ContratCalepinageInvalide):
            resultat(sensibilites=sensibilites, plancher=300).valider()


class TestSerialisation(unittest.TestCase):

    def test_aller_retour_sans_perte(self):
        source = resultat(
            marges=Marges(4.15, 4.90, 'R3', 'edicule'),
            planche=Planche('PL-05H', 'B'),
            sensibilites=(Sensibilite('S1', 'obstacle', 300, -14),),
            plancher=300, verdict='engagement tenu partout (300 ≥ 288)')
        rejoue = ResultatCalepinage.depuis_dict(source.vers_dict())
        self.assertEqual(rejoue.vers_dict(), source.vers_dict())
        self.assertEqual(rejoue.code_planche, 'PL-05HB')

    def test_document_de_contrat_plus_recent_refuse(self):
        document = resultat().vers_dict()
        document['version_contrat'] = 99
        with self.assertRaises(ContratCalepinageInvalide):
            ResultatCalepinage.depuis_dict(document)

    def test_depuis_dict_valide_par_defaut(self):
        document = resultat().vers_dict()
        document['compte_retenu'] = 288
        document['optimal'] = False
        with self.assertRaises(ContratCalepinageInvalide):
            ResultatCalepinage.depuis_dict(document)

    def test_libelle_de_preuve_genere(self):
        self.assertEqual(resultat().libelle_preuve,
                         'optimum prouvé (314 modules)')
        self.assertIn('borne supérieure',
                      resultat(compte_retenu=316, optimal=False).libelle_preuve)


class FauxPreuve:
    methode = 'dp_exact_multi'
    pas_recherche_m = 0.01
    compte_optimal = 120
    optimal = True


class FauxResultat:
    """Sosie du `core.calepinage.types.Resultat` — duck-typing, zéro import."""

    modules = 120
    kwc = 75.0
    preuve = FauxPreuve()
    rangees = ((12.4, 'R1'), (12.4, 'R2'))
    hash_entree = 'b' * 64
    version_moteur = '1.0.0'
    sensibilites = ()
    plancher_sensibilites = 120
    engageable = True
    motifs_non_engageable = ()
    marges = None


class TestAdaptateurMoteur(unittest.TestCase):

    def test_depuis_moteur_sans_importer_le_moteur(self):
        r = ResultatCalepinage.depuis_moteur(FauxResultat(), batiment='B')
        self.assertEqual(r.compte_retenu, 120)
        self.assertTrue(r.optimal)
        self.assertEqual(r.methode, 'dp_exact_multi')


class TestLot(unittest.TestCase):

    def test_lot_frdisi(self):
        lot = valider_lot([
            resultat(batiment='A', compte_retenu=152, compte_optimal=152,
                     kwc=95.0).vers_dict(),
            resultat(batiment='B', compte_retenu=120, compte_optimal=120,
                     kwc=75.0).vers_dict(),
            resultat().vers_dict()])
        self.assertEqual(lot.par_batiment('C').compte_retenu, 314)

    def test_doublon_de_batiment_refuse(self):
        with self.assertRaises(ContratCalepinageInvalide):
            valider_lot([resultat().vers_dict(), resultat().vers_dict()])

    def test_deux_versions_de_moteur_refusees(self):
        autre = resultat(batiment='A', version_moteur='2.0.0')
        with self.assertRaises(ContratCalepinageInvalide):
            LotCalepinage((resultat(), autre)).valider()

    def test_batiment_inconnu_leve(self):
        with self.assertRaises(ContratCalepinageInvalide):
            valider_lot([resultat().vers_dict()]).par_batiment('Z')


class TestContratOpposeAuContexte(unittest.TestCase):
    """Le contrat est opposé À L'ENTRÉE — pas au moment du rendu d'une pièce."""

    def dossier(self, calepinage):
        return {'identite': {'raison_sociale': 'TAQINOR SARL'},
                'marche': {'objet': 'centrale PV'},
                'calepinage': calepinage,
                'montants': {'total_ht': '1', 'total_ttc': '1.2'}}

    def test_un_lot_valide_entre_dans_le_contexte(self):
        from apps.ao.fabrique.contexte import construire_contexte
        c = construire_contexte(self.dossier([resultat().vers_dict()]))
        self.assertEqual(c['calepinage'][0]['compte_retenu'], 314)

    def test_un_sous_optimum_n_entre_pas_dans_un_dossier(self):
        from apps.ao.fabrique.contexte import construire_contexte
        document = resultat(compte_retenu=288, optimal=False).vers_dict()
        with self.assertRaises(ContratCalepinageInvalide):
            construire_contexte(self.dossier([document]))

    def test_un_resultat_sans_hash_n_entre_pas(self):
        from apps.ao.fabrique.contexte import construire_contexte
        with self.assertRaises(ContratCalepinageInvalide):
            construire_contexte(
                self.dossier([{'batiment': 'C', 'compte_retenu': 314}]))


# --------------------------------------------------------------------------
# Le test STATIQUE : la fabrique consomme, elle ne dérive pas.
# --------------------------------------------------------------------------

#: Vocabulaire de GÉOMÉTRIE DE POSE. Il appartient au moteur pur. Son apparition
#: comme identifiant dans `apps/ao/fabrique/` signifie qu'un document a
#: recommencé à calepiner — la porte ouverte à deux sources de vérité.
GEOMETRIE_INTERDITE = frozenset({
    'emprise', 'emprise_m', 'entraxe', 'allee', 'allee_m', 'pas_rangee',
    'inter_rangee', 'surface_utile', 'poser_rangee', 'calepiner',
    'ombrage_pas', 'largeur_module', 'hauteur_module',
})

#: Noms qui PORTENT un compte de modules. Leur affecter le résultat d'un calcul
#: revient à fabriquer un compte au lieu de lire celui du moteur.
NOMS_DE_COMPTE = frozenset({
    'modules', 'compte', 'compte_retenu', 'compte_optimal', 'nb_modules',
    'total_modules', 'compte_modules', 'nombre_modules',
})


def infractions(source, nom='<test>'):
    """Analyse AST d'un module de fabrique. Retourne la liste des motifs."""
    trouvees = []
    arbre = ast.parse(source, filename=nom)

    def cible(noeud):
        if isinstance(noeud, ast.Name):
            return noeud.id
        if isinstance(noeud, ast.Attribute):
            return noeud.attr
        return None

    for noeud in ast.walk(arbre):
        if isinstance(noeud, ast.Name) and noeud.id in GEOMETRIE_INTERDITE:
            trouvees.append('%s:%d géométrie de pose : %s'
                            % (nom, noeud.lineno, noeud.id))
        elif isinstance(noeud, ast.Attribute) and \
                noeud.attr in GEOMETRIE_INTERDITE:
            trouvees.append('%s:%d géométrie de pose : .%s'
                            % (nom, noeud.lineno, noeud.attr))
        elif isinstance(noeud, ast.arg) and noeud.arg in GEOMETRIE_INTERDITE:
            trouvees.append('%s:%d géométrie de pose (paramètre) : %s'
                            % (nom, noeud.lineno, noeud.arg))
        elif isinstance(noeud, ast.Assign) and isinstance(noeud.value,
                                                          ast.BinOp):
            for t in noeud.targets:
                if cible(t) in NOMS_DE_COMPTE:
                    trouvees.append('%s:%d arithmétique de comptage : %s = …'
                                    % (nom, noeud.lineno, cible(t)))
        elif isinstance(noeud, ast.AugAssign) and \
                cible(noeud.target) in NOMS_DE_COMPTE:
            trouvees.append('%s:%d arithmétique de comptage : %s op= …'
                            % (nom, noeud.lineno, cible(noeud.target)))
        elif isinstance(noeud, ast.Dict):
            for cle, val in zip(noeud.keys, noeud.values):
                if isinstance(cle, ast.Constant) and \
                        cle.value in NOMS_DE_COMPTE and \
                        isinstance(val, ast.BinOp):
                    trouvees.append(
                        '%s:%d arithmétique de comptage : {%r: …}'
                        % (nom, noeud.lineno, cle.value))
    return trouvees


class TestFabriqueNeDeriveRien(unittest.TestCase):

    def test_aucun_module_de_fabrique_ne_derive_un_compte(self):
        fautes = []
        fichiers = sorted(FABRIQUE.rglob('*.py'))
        self.assertTrue(fichiers, 'aucun module de fabrique trouvé')
        for fichier in fichiers:
            fautes.extend(infractions(fichier.read_text(encoding='utf-8'),
                                      fichier.name))
        self.assertEqual(fautes, [], '\n'.join(fautes))

    def test_le_garde_mord_sur_une_derivation_de_compte(self):
        self.assertTrue(infractions(
            'def f(surface, emprise):\n'
            '    modules = int(surface / emprise)\n'
            '    return modules\n'))

    def test_le_garde_mord_sur_le_vocabulaire_de_pose(self):
        self.assertTrue(infractions('def f(allee):\n    return allee\n'))
        self.assertTrue(infractions('x = plan.entraxe\n'))

    def test_le_garde_mord_sur_un_dict_de_compte_calcule(self):
        self.assertTrue(infractions("d = {'compte_retenu': a * b}\n"))

    def test_le_garde_laisse_passer_la_lecture_et_l_agregation(self):
        self.assertEqual(infractions(
            'total = sum(r.compte_retenu for r in resultats)\n'
            'modules = resultat.compte_retenu\n'
            'prix = quantite * pu\n'), [])


if __name__ == '__main__':
    unittest.main()
