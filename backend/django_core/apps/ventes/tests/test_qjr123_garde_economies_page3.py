"""QJR123 — la garde « aucune économie » couvre AUSSI la page 3.

``build_html`` posait ``_sans_economies = MASQUER_ECONOMIES or
PUISSANCE_INCONNUE`` et supprimait les deux graphes ; ``page1`` supprimait les
pastilles ROI. Mais ``_savings_method_html()`` et ``_hypotheses_html()``
n'avaient AUCUNE garde, et leur producteur les construit inconditionnellement
avec des NOMBRES (tarif MAD/kWh, « Production estimée ≈ N kWh par kWc et par
an »). Sur un dossier MOYENNE TENSION, les pages 1 et 2 omettent donc
scrupuleusement les économies — parce que les chiffres sont au barème BASSE
tension — et la page 3 imprimait juste après « COMMENT NOUS CALCULONS VOS
ÉCONOMIES » + « NOS HYPOTHÈSES » avec ce même tarif BT.

Sous-point : dans le modèle « estimation », ``approximatif=True`` mais
``exemple=None``, donc la mention d'estimation ne s'affichait jamais alors que
``SAVINGS_ESTIMATED`` est ingéré.

Run (sans base de données) :
    docker compose exec django_core python manage.py test \
        apps.ventes.tests.test_qjr123_garde_economies_page3 -v 2
"""
from django.test import SimpleTestCase

from apps.ventes.quote_engine import generate_devis_premium as moteur


#: Textes que le builder produit AU BARÈME BASSE TENSION.
METHODE_BT = {
    "ligne_methode": ("Estimation : production annuelle × part autoconsommée "
                      "× tarif kWh (loi 82-21)."),
    "exemple": None,
    "approximatif": True,
}
HYPOTHESES_BT = {
    "titre": "Nos hypothèses",
    "items": [
        "Tarif électricité retenu : 1,42 MAD/kWh (barème national).",
        "Production estimée ≈ 1 620 kWh par kWc et par an.",
    ],
}


def _data(**surcharges):
    data = dict(moteur.QUOTE_INPUT)
    data.update(moteur.calculate_quote(moteur.QUOTE_INPUT))
    data["pdf_mode"] = "full"
    data["savings_method"] = dict(METHODE_BT)
    data["hypotheses"] = dict(HYPOTHESES_BT)
    data.update(surcharges)
    return data


class TestDossierMT(SimpleTestCase):
    """Un dossier moyenne tension ne publie AUCUN chiffre du barème BT."""

    def setUp(self):
        self.html = moteur.render_html_for(_data(masquer_economies=True))

    def test_les_deux_blocs_de_la_page3_sont_omis(self):
        self.assertNotIn("Comment nous calculons vos", self.html)
        self.assertNotIn("Nos hypoth", self.html)

    def test_aucun_tarif_bt_dans_le_document(self):
        for chiffre in ("1,42 MAD/kWh", "1 620 kWh par kWc"):
            with self.subTest(chiffre=chiffre):
                self.assertNotIn(chiffre, self.html)

    def test_le_document_reste_rendu(self):
        self.assertGreaterEqual(self.html.count('class="page"'), 3)


class TestPuissanceInconnue(SimpleTestCase):
    """Même garde quand la puissance n'a aucun ancrage réel (M2)."""

    def test_les_deux_blocs_sont_omis(self):
        html = moteur.render_html_for(_data(puissance_inconnue=True))
        self.assertNotIn("Comment nous calculons vos", html)
        self.assertNotIn("Nos hypoth", html)


class TestDossierNormal(SimpleTestCase):
    """Hors garde, les deux blocs restent rendus à l'identique."""

    def setUp(self):
        self.html = moteur.render_html_for(_data())

    def test_les_deux_blocs_sont_rendus(self):
        self.assertIn("Comment nous calculons vos", self.html)
        self.assertIn("Nos hypoth", self.html)

    def test_les_hypotheses_portent_leurs_chiffres(self):
        self.assertIn("1,42 MAD/kWh", self.html)


class TestMentionEstimation(SimpleTestCase):
    """La mention d'estimation ne dépend plus de l'existence d'un exemple."""

    def test_mention_rendue_sans_exemple(self):
        html = moteur.render_html_for(_data())
        self.assertIn("(approximatif)", html)
        self.assertIn("Économies estimées", html)

    def test_mention_rendue_depuis_savings_estimated(self):
        data = _data(savings_estimated=True)
        data["savings_method"] = dict(METHODE_BT, approximatif=False)
        html = moteur.render_html_for(data)
        self.assertIn("(approximatif)", html)

    def test_aucune_mention_sur_un_calcul_exact(self):
        data = _data(savings_estimated=False)
        data["savings_method"] = dict(
            METHODE_BT, approximatif=False,
            exemple="Facture actuelle ≈ 18 000 MAD/an")
        html = moteur.render_html_for(data)
        self.assertIn("Facture actuelle", html)
        self.assertNotIn("(approximatif)", html)


class TestSourceUniqueDeLaGarde(SimpleTestCase):
    """Une seule définition, partagée par les graphes et la page 3."""

    def test_la_garde_suit_les_deux_drapeaux(self):
        anciens = (moteur.MASQUER_ECONOMIES, moteur.PUISSANCE_INCONNUE)
        try:
            moteur.MASQUER_ECONOMIES = moteur.PUISSANCE_INCONNUE = False
            self.assertFalse(moteur._sans_economies_publiees())
            moteur.MASQUER_ECONOMIES = True
            self.assertTrue(moteur._sans_economies_publiees())
            moteur.MASQUER_ECONOMIES = False
            moteur.PUISSANCE_INCONNUE = True
            self.assertTrue(moteur._sans_economies_publiees())
        finally:
            (moteur.MASQUER_ECONOMIES,
             moteur.PUISSANCE_INCONNUE) = anciens
