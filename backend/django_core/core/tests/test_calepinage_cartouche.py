# -*- coding: utf-8 -*-
"""AOF64 — le cartouche ne connaît que la MARQUE DE RENDU, jamais la société.

Cas réel : les planches FRDISI du 27/07/2026 sont remises au nom d'ACCORDIA
TECH. TAQINOR exploite le moteur et ne doit apparaître NULLE PART.

Note sur le « test de contenu binaire » exigé par la tâche : matplotlib écrit
les PDF en polices **Type 3**, c'est-à-dire en suites de glyphes — aucune chaîne
de texte n'y figure littéralement. Un ``assertNotIn(b"TAQINOR", pdf)`` seul
serait donc VERT quoi qu'il arrive, y compris sur une planche contaminée : il
prouverait exactement rien. Le contrôle est donc mené aux deux niveaux, et la
partie binaire porte sur ce qui, lui, EST littéral dans le fichier — le
dictionnaire de métadonnées.
"""

import unittest

from core.calepinage.rendu import cartouche as K
from core.calepinage.rendu.feuille import Feuille

SOCIETE = "TAQINOR"
PARTENAIRE = "ACCORDIA TECH"
NOIR = "#111111"


def marque_temoin(**surcharges):
    valeurs = dict(
        soumissionnaire=PARTENAIRE,
        code_document="05H",
        objet="Consultation FRDISI : PV + stockage, Mohammedia",
        designation_ouvrage=("BÂT. C — TERRASSE ÉCOLE SUPTECH — "
                             "IMPLANTATION PHOTOVOLTAÏQUE"),
        date="Juillet 2026",
        indice_revision="H",
        base_releve="relevé contradictoire du 27/07/2026",
    )
    valeurs.update(surcharges)
    return K.MarqueRendu(**valeurs)


class ContenuDuCartouche(unittest.TestCase):
    def test_les_cinq_lignes_types_dans_l_ordre(self):
        lignes = marque_temoin().lignes()
        textes = [t for t, _ in lignes]
        self.assertEqual(len(textes), 5)
        self.assertEqual(
            textes[0],
            "ACCORDIA TECH — Consultation FRDISI : PV + stockage, Mohammedia")
        self.assertIn("BÂT. C", textes[1])
        self.assertEqual(textes[2], "Document 05H — Statut : Appel d'offres")
        self.assertEqual(
            textes[3],
            "Date : Juillet 2026 — Indice : H — relevé contradictoire du 27/07/2026")
        self.assertEqual(textes[4], K.MENTION_ECHELLE)

    def test_les_deux_premieres_lignes_sont_en_gras(self):
        gras = [g for _t, g in marque_temoin().lignes()]
        self.assertEqual(gras[:2], [True, True])
        self.assertNotIn(True, gras[2:])

    def test_l_echelle_annoncee_est_graphique_jamais_numerique(self):
        self.assertIn("barre graphique", K.MENTION_ECHELLE)
        self.assertIn("cotes en mètres", K.MENTION_ECHELLE)
        self.assertNotIn("1/", K.MENTION_ECHELLE)
        self.assertNotIn("1:", K.MENTION_ECHELLE)

    def test_les_codes_documents_reels_passent(self):
        for code in ("05H", "06H", "06I"):
            marque = marque_temoin(code_document=code)
            self.assertIn("Document %s" % code, marque.textes()[2])

    def test_mentions_libres_ajoutees_en_fin(self):
        marque = marque_temoin(mentions=("Plan non contractuel",))
        self.assertEqual(marque.textes()[-1], "Plan non contractuel")

    def test_marque_sans_soumissionnaire_ou_sans_code_refusee(self):
        with self.assertRaises(ValueError):
            K.MarqueRendu(soumissionnaire="", code_document="05H")
        with self.assertRaises(ValueError):
            K.MarqueRendu(soumissionnaire=PARTENAIRE, code_document=" ")
        with self.assertRaises(ValueError):
            K.MarqueRendu(soumissionnaire=PARTENAIRE, code_document="05H",
                          indice_revision="")

    def test_langue_non_redigee_refusee(self):
        with self.assertRaises(K.LangueNonSupportee):
            marque_temoin(langue="en")


class IndiceDeRevision(unittest.TestCase):
    """« l'indice s'incrémente sans réécrire le reste »."""

    def test_increment_alphabetique(self):
        for depart, attendu in (("A", "B"), ("H", "I"), ("Y", "Z"),
                                ("Z", "AA"), ("AZ", "BA"), ("ZZ", "AAA")):
            with self.subTest(depart=depart):
                self.assertEqual(
                    marque_temoin(indice_revision=depart).indice_suivant(),
                    attendu)

    def test_indice_non_alphabetique_refuse(self):
        with self.assertRaises(ValueError):
            marque_temoin(indice_revision="3").indice_suivant()

    def test_la_revision_ne_touche_QUE_l_indice(self):
        avant = marque_temoin()
        apres = avant.revisee()
        self.assertEqual(apres.indice_revision, "I")
        self.assertEqual(avant.indice_revision, "H")     # l'original est intact
        for champ in ("soumissionnaire", "code_document", "objet",
                      "designation_ouvrage", "date", "statut", "base_releve",
                      "mentions", "langue", "logo"):
            self.assertEqual(getattr(apres, champ), getattr(avant, champ), champ)
        # toutes les lignes sont identiques SAUF celle qui porte l'indice
        differentes = [i for i, (a, b) in enumerate(zip(avant.textes(),
                                                        apres.textes()))
                       if a != b]
        self.assertEqual(differentes, [3])

    def test_avec_indice_explicite(self):
        self.assertEqual(marque_temoin().avec_indice("J").indice_revision, "J")


class LaSocieteNeParaitNullePart(unittest.TestCase):
    def test_une_marque_contaminee_est_refusee_en_citant_le_terme(self):
        contaminee = marque_temoin(
            mentions=("Étude réalisée par TAQINOR pour le compte du groupement",))
        with self.assertRaises(K.MarqueContaminee) as capture:
            K.verifier_marque(contaminee, (SOCIETE,))
        self.assertIn(SOCIETE, str(capture.exception))

    def test_la_garde_est_insensible_a_la_casse_et_aux_espaces(self):
        contaminee = marque_temoin(soumissionnaire="Taqinor   SARL")
        with self.assertRaises(K.MarqueContaminee):
            K.verifier_marque(contaminee, ("TAQINOR",))

    def test_marque_partenaire_propre_acceptee(self):
        marque = marque_temoin()
        self.assertIs(K.verifier_marque(marque, (SOCIETE,)), marque)

    def test_le_cartouche_contamine_n_est_pas_dessine_a_moitie(self):
        contaminee = marque_temoin(mentions=("Moteur TAQINOR",))
        with Feuille("T", "s", (0, 10), (0, 10)) as feuille:
            avant = len(feuille.figure.texts)
            with self.assertRaises(K.MarqueContaminee):
                K.dessiner_cartouche(feuille, contaminee, NOIR, NOIR,
                                     noms_interdits=(SOCIETE,))
            self.assertEqual(len(feuille.figure.texts), avant)
            self.assertEqual(len(feuille.figure.artists), 0)

    def test_aucun_texte_rendu_ne_porte_le_nom_de_la_societe(self):
        with Feuille("IMPLANTATION PHOTOVOLTAÏQUE", "relevé du 27/07/2026",
                     (0, 30), (0, 55)) as feuille:
            K.dessiner_cartouche(feuille, marque_temoin(), NOIR, NOIR,
                                 noms_interdits=(SOCIETE,))
            rendus = [artiste.get_text() for artiste in feuille.artistes()
                      if hasattr(artiste, "get_text")]
        assemble = " ".join(rendus)
        self.assertIn(PARTENAIRE, assemble)
        self.assertNotIn(SOCIETE, assemble.upper())

    def test_contenu_binaire_du_pdf_ne_porte_pas_le_nom_de_la_societe(self):
        """Partie binaire : les métadonnées, seules chaînes LITTÉRALES du PDF."""
        marque = marque_temoin()
        metadonnees = {"Title": marque.code_document,
                       "Author": marque.soumissionnaire,
                       "Creator": "", "Producer": ""}
        with Feuille("IMPLANTATION PHOTOVOLTAÏQUE", "relevé du 27/07/2026",
                     (0, 30), (0, 55)) as feuille:
            K.dessiner_cartouche(feuille, marque, NOIR, NOIR,
                                 noms_interdits=(SOCIETE,))
            octets = feuille.pdf(metadonnees=metadonnees)
        self.assertNotIn(SOCIETE.encode("ascii"), octets)
        self.assertNotIn(SOCIETE.lower().encode("ascii"), octets)
        self.assertIn(PARTENAIRE.encode("ascii"), octets)   # via /Author

    def test_le_temoin_negatif_du_test_binaire(self):
        """Le contrôle binaire DÉTECTE réellement une contamination.

        Sans ce témoin, le test précédent pourrait être vert par construction.
        """
        with Feuille("T", "s", (0, 10), (0, 10)) as feuille:
            octets = feuille.pdf(metadonnees={"Author": SOCIETE,
                                              "Creator": "", "Producer": ""})
        self.assertIn(SOCIETE.encode("ascii"), octets)


class DessinDuCartouche(unittest.TestCase):
    def test_une_ligne_de_cartouche_par_texte_et_un_cadre(self):
        marque = marque_temoin()
        with Feuille("T", "s", (0, 10), (0, 10)) as feuille:
            textes_avant = len(feuille.figure.texts)
            K.dessiner_cartouche(feuille, marque, NOIR, NOIR)
            self.assertEqual(len(feuille.figure.texts) - textes_avant,
                             len(marque.lignes()))
            self.assertEqual(len(feuille.figure.artists), 1)   # le cadre

    def test_les_lignes_sont_empilees_de_haut_en_bas_dans_le_cadre(self):
        marque = marque_temoin()
        y, hauteur = 0.02, 0.115
        with Feuille("T", "s", (0, 10), (0, 10)) as feuille:
            avant = list(feuille.figure.texts)
            K.dessiner_cartouche(feuille, marque, NOIR, NOIR, y=y,
                                 hauteur=hauteur)
            poses = [t for t in feuille.figure.texts if t not in avant]
        hauteurs = [t.get_position()[1] for t in poses]
        self.assertEqual(hauteurs, sorted(hauteurs, reverse=True))
        for h in hauteurs:
            self.assertGreater(h, y)
            self.assertLess(h, y + hauteur)

    def test_logo_en_octets_jamais_un_chemin(self):
        with Feuille("T", "s", (0, 10), (0, 10)) as source:
            source.rectangle(1, 1, 3, 3, contour=NOIR, remplissage="#bbf7d0")
            logo = source.png(dpi=30, bbox_serre=False)
        marque = marque_temoin(logo=logo)
        with Feuille("T", "s", (0, 10), (0, 10)) as feuille:
            axes_avant = len(feuille.figure.axes)
            K.dessiner_cartouche(feuille, marque, NOIR, NOIR,
                                 largeur_logo=0.05)
            self.assertEqual(len(feuille.figure.axes) - axes_avant, 1)


if __name__ == "__main__":            # pragma: no cover
    unittest.main()
