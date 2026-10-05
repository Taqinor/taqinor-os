# -*- coding: utf-8 -*-
"""AOF70 — profils INTERNE / DÉPÔT, lexique de substitution, métadonnées forcées.

Les trois preuves exigées :

1. un rendu DÉPÔT contenant un mot du lexique interdit est REFUSÉ, avec le mot
   cité ;
2. les métadonnées par défaut du moteur de rendu n'apparaissent plus dans le
   binaire (et un témoin négatif prouve que le contrôle n'est pas vide) ;
3. aucun chemin local dans le PDF — contrôle binaire.
"""

import unittest
from datetime import datetime, timezone

from core.calepinage.rendu import metadata as M
from core.calepinage.rendu import profils as PR
from core.calepinage.rendu.feuille import Feuille

CONTEXTE = PR.ContexteLexique(date_releve="27/07/2026",
                              date_decision="27/07/2026")
SOUMISSIONNAIRE = "ACCORDIA TECH"
SOCIETE = "TAQINOR"


def metadonnees():
    return M.MetadonneesPdf(
        code_document="05H_IMPLANTATION_BAT_C_ECOLE",
        soumissionnaire=SOUMISSIONNAIRE,
        objet="Consultation FRDISI : PV + stockage, Mohammedia",
        date_creation=datetime(2026, 7, 27, tzinfo=timezone.utc))


class LexiqueDeSubstitution(unittest.TestCase):
    def test_les_quatre_traductions_mesurees(self):
        cas = (
            ("décision client du 27/07", "DÉCISION D'ÉTUDES DU 27/07/2026"),
            ("le client dit que ça n'existe pas", "ÉCARTÉ AU RELEVÉ"),
            ("consigne client : allées 0,60 mini", "prescription"),
            ("relevé au croquis", "relevé contradictoire du 27/07/2026"),
        )
        for interne, attendu in cas:
            with self.subTest(interne=interne):
                self.assertIn(attendu, PR.traduire(interne, CONTEXTE))

    def test_la_traduction_fait_disparaitre_le_mot_interdit(self):
        for interne in ("décision client", "consigne client",
                        "le client dit que ça n'existe pas",
                        "d'après le croquis"):
            traduit = PR.traduire(interne, CONTEXTE)
            self.assertIsNone(PR.mot_interdit(traduit), traduit)

    def test_l_ordre_des_substitutions_est_le_contrat(self):
        """« décision client » ne doit pas être charcuté par « client » seul."""
        traduit = PR.traduire("décision client actée", CONTEXTE)
        self.assertEqual(traduit, "DÉCISION D'ÉTUDES DU 27/07/2026 actée")

    def test_la_traduction_est_insensible_a_la_casse(self):
        self.assertIn("prescription",
                      PR.traduire("CONSIGNE CLIENT", CONTEXTE))

    def test_l_apostrophe_typographique_est_reconnue(self):
        self.assertIn("ÉCARTÉ AU RELEVÉ",
                      PR.traduire("le client dit que ça n’existe pas",
                                  CONTEXTE))

    def test_les_dates_ne_sont_pas_codees_en_dur(self):
        autre = PR.ContexteLexique(date_releve="03/09/2026")
        self.assertIn("03/09/2026", PR.traduire("croquis", autre))

    def test_un_contexte_sans_date_de_releve_est_refuse(self):
        with self.assertRaises(ValueError):
            PR.ContexteLexique(date_releve="  ")


class LeDepotRefuseLeVocabulaireInterne(unittest.TestCase):
    def test_un_mot_interdit_survivant_est_REFUSE_en_le_citant(self):
        with self.assertRaises(PR.LexiqueInterdit) as capture:
            PR.preparer("le client a validé cette implantation",
                        PR.Profil.DEPOT, CONTEXTE)
        self.assertIn("client", str(capture.exception))

    def test_chaque_mot_du_lexique_est_reellement_attrape(self):
        for mot in PR.MOTS_INTERDITS_AU_DEPOT:
            with self.subTest(mot=mot):
                self.assertEqual(PR.mot_interdit("note : %s ici" % (mot,)), mot)

    def test_les_derives_d_un_mot_interdit_sont_attrapes_aussi(self):
        for derive in ("clients", "clientèle", "croquis"):
            self.assertIsNotNone(PR.mot_interdit("selon le %s" % (derive,)))

    def test_les_couts_ne_passent_jamais_en_depot(self):
        for texte in ("prix d'achat du variateur", "marge commerciale retenue",
                      "coût d'achat catalogue"):
            with self.assertRaises(PR.LexiqueInterdit):
                PR.preparer(texte, PR.Profil.DEPOT, CONTEXTE)

    def test_le_profil_interne_laisse_le_texte_intact(self):
        texte = "décision client : le client dit que ça n'existe pas"
        self.assertEqual(PR.preparer(texte, PR.Profil.INTERNE), texte)

    def test_un_texte_de_depot_propre_passe(self):
        texte = ("Implantation définitive arrêtée après relevé d'exécution — "
                 "marché à prix unitaires")
        self.assertEqual(PR.preparer(texte, PR.Profil.DEPOT, CONTEXTE), texte)

    def test_le_bandeau_d_engagement_n_est_pas_pris_pour_du_vocabulaire_interne(self):
        """« marge +26 » est une grandeur publiable, pas une marge commerciale."""
        texte = ("Capacité démontrée sur le relevé : 314 modules — "
                 "ENGAGÉ AU MARCHÉ : 288 modules (marge +26)")
        self.assertEqual(PR.preparer(texte, PR.Profil.DEPOT, CONTEXTE), texte)

    def test_un_depot_sans_contexte_est_refuse(self):
        with self.assertRaises(ValueError):
            PR.preparer("croquis", PR.Profil.DEPOT)

    def test_preparer_tous_traite_la_planche_entiere(self):
        textes = ("consigne client : allées 0,60", "relevé au croquis")
        prepares = PR.preparer_tous(textes, PR.Profil.DEPOT, CONTEXTE)
        self.assertEqual(len(prepares), 2)
        for texte in prepares:
            self.assertIsNone(PR.mot_interdit(texte))


class BlocsSensibles(unittest.TestCase):
    BLOCS = (
        PR.BlocDePlanche(PR.BLOC_MARGES, ("marge de capacité : +26 modules",)),
        PR.BlocDePlanche(PR.BLOC_PROVENANCE_CRUE,
                         ("cage : profondeur déduite, non contradictoire",)),
        PR.BlocDePlanche(PR.BLOC_MAXIMUM_AGREGE,
                         ("maximum agrégé du site : 902 modules",)),
        PR.BlocDePlanche("legende", ("bleu = mesuré",)),
    )

    def test_le_depot_ne_montre_aucun_bloc_sensible(self):
        gardes = PR.filtrer_blocs(self.BLOCS, PR.Profil.DEPOT)
        self.assertEqual([b.cle for b in gardes], ["legende"])

    def test_l_interne_les_montre_tous(self):
        gardes = PR.filtrer_blocs(self.BLOCS, PR.Profil.INTERNE)
        self.assertEqual(len(gardes), len(self.BLOCS))

    def test_un_bloc_sensible_explicitement_demande_en_depot_est_refuse(self):
        with self.assertRaises(PR.BlocInterditAuDepot) as capture:
            PR.exiger_blocs_permis(self.BLOCS, PR.Profil.DEPOT)
        self.assertIn(PR.BLOC_MARGES, str(capture.exception))

    def test_les_trois_blocs_sensibles_sont_bien_ceux_annonces(self):
        self.assertEqual(set(PR.BLOCS_SENSIBLES),
                         {"marges", "provenance_crue", "maximum_agrege"})
        for bloc in self.BLOCS[:3]:
            self.assertTrue(bloc.sensible)
        self.assertFalse(self.BLOCS[3].sensible)


class MetadonneesForcees(unittest.TestCase):
    def test_le_dictionnaire_porte_le_code_le_soumissionnaire_et_un_creator_neutre(self):
        valeurs = metadonnees().pour_matplotlib()
        self.assertEqual(valeurs["Title"], "05H_IMPLANTATION_BAT_C_ECOLE")
        self.assertEqual(valeurs["Author"], SOUMISSIONNAIRE)
        self.assertEqual(valeurs["Creator"], M.CREATOR_NEUTRE)
        self.assertEqual(valeurs["Producer"], M.CREATOR_NEUTRE)
        self.assertNotIn("atplotlib", valeurs["Creator"])

    def test_une_declaration_incomplete_est_refusee(self):
        with self.assertRaises(ValueError):
            M.MetadonneesPdf(code_document=" ", soumissionnaire=SOUMISSIONNAIRE)
        with self.assertRaises(ValueError):
            M.MetadonneesPdf(code_document="05H", soumissionnaire="")

    def test_un_horodatage_sans_fuseau_est_refuse(self):
        with self.assertRaises(ValueError):
            M.MetadonneesPdf(code_document="05H",
                             soumissionnaire=SOUMISSIONNAIRE,
                             date_creation=datetime(2026, 7, 27))

    def test_sans_horodatage_la_cle_est_absente(self):
        valeurs = M.MetadonneesPdf(code_document="05H",
                                   soumissionnaire=SOUMISSIONNAIRE
                                   ).pour_matplotlib()
        self.assertNotIn("CreationDate", valeurs)

    def test_l_horodatage_stable_rend_deux_planches_comparables(self):
        stable = metadonnees().horodatee()
        premier = _rendre(stable.pour_matplotlib())
        second = _rendre(stable.pour_matplotlib())
        self.assertEqual(premier, second)


def _rendre(metadonnees_pdf=None):
    with Feuille("IMPLANTATION PHOTOVOLTAÏQUE", "relevé du 27/07/2026",
                 (0, 30), (0, 55)) as feuille:
        feuille.rectangle(1, 1, 25, 50, contour="#111111")
        feuille.texte(13, 53, "BÂT. C — TERRASSE ÉCOLE", "#111111")
        return feuille.pdf(metadonnees=metadonnees_pdf)


class ControlesBinairesDuLivrable(unittest.TestCase):
    def test_le_pdf_force_ne_porte_plus_les_metadonnees_par_defaut(self):
        octets = _rendre(metadonnees().pour_matplotlib())
        self.assertTrue(M.verifier_sans_metadonnees_par_defaut(octets))

    def test_TEMOIN_NEGATIF_un_pdf_sans_metadonnees_les_porte(self):
        """Le trou réel : les trois scripts de dépôt n'ont AUCUN metadata=."""
        octets = _rendre(None)
        with self.assertRaises(M.MetadonneesParDefaut) as capture:
            M.verifier_sans_metadonnees_par_defaut(octets)
        self.assertIn("atplotlib", str(capture.exception))

    def test_aucun_chemin_local_dans_le_pdf(self):
        octets = _rendre(metadonnees().pour_matplotlib())
        self.assertTrue(M.verifier_sans_chemin_local(octets))

    def test_TEMOIN_NEGATIF_le_controle_de_chemin_detecte_reellement(self):
        faux = b"%PDF-1.4 /Producer (C:/Users/kasri/OneDrive - Atlencia/x)"
        with self.assertRaises(M.CheminLocalDansLeLivrable) as capture:
            M.verifier_sans_chemin_local(faux)
        self.assertIn("OneDrive", str(capture.exception))

    def test_le_nom_de_la_societe_ne_figure_pas_dans_un_livrable_partenaire(self):
        octets = _rendre(metadonnees().pour_matplotlib())
        self.assertTrue(M.verifier_sans_terme_interdit(octets, (SOCIETE,)))
        self.assertIn(SOUMISSIONNAIRE.encode("ascii"), octets)

    def test_TEMOIN_NEGATIF_un_author_contamine_est_detecte(self):
        contaminees = M.MetadonneesPdf(code_document="05H",
                                       soumissionnaire=SOCIETE)
        octets = _rendre(contaminees.pour_matplotlib())
        with self.assertRaises(M.CheminLocalDansLeLivrable) as capture:
            M.verifier_sans_terme_interdit(octets, (SOCIETE,))
        self.assertIn(SOCIETE, str(capture.exception))

    def test_le_png_neutralise_aussi_sa_cle_d_outil(self):
        with Feuille("T", "s", (0, 10), (0, 10)) as feuille:
            feuille.rectangle(1, 1, 3, 3, contour="#111111")
            octets = feuille.png(dpi=50,
                                 metadonnees=metadonnees().pour_png())
        self.assertTrue(M.verifier_sans_metadonnees_par_defaut(octets))
        self.assertTrue(M.verifier_sans_chemin_local(octets))


if __name__ == "__main__":            # pragma: no cover
    unittest.main()
