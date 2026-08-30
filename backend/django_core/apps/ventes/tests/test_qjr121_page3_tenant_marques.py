"""QJR121 — la page 3 du PDF premium ne signe plus TAQINOR et n'affirme plus
des marques qu'elle ne vend pas.

Trois constats vérifiés, tous sur ``generate_devis_premium.page3`` :

* « Pourquoi choisir **TAQINOR** ? » et « Signature **TAQINOR** » étaient des
  LITTÉRAUX que DC1 a manqués, alors que ``_apply_entreprise`` a variabilisé
  les pieds de page (``ENT_NOM_MARQUE``) : le devis d'un autre tenant demandait
  au client de choisir TAQINOR ;
* « Panneaux Canadian Solar, onduleurs Huawei & Deye — certifiés IEC » était
  affirmé sur TOUT devis, contredit par le tableau de la page 2 dès que les
  lignes portent d'autres marques ;
* « Application de monitoring 24/7 » ne se rattachait à AUCUNE ligne vendue —
  un composant fictif au sens de la règle fondateur.

Run (sans base de données) :
    docker compose exec django_core python manage.py test \
        apps.ventes.tests.test_qjr121_page3_tenant_marques -v 2
"""
import inspect
import re

from django.test import SimpleTestCase

from apps.ventes.quote_engine import generate_devis_premium as moteur


def _data(**surcharges):
    """Jeu de données du moteur (démo intégrée), surchargeable."""
    entree = dict(moteur.QUOTE_INPUT)
    entree.update({k: v for k, v in surcharges.items()
                   if k in ("puissance_kwc", "nb_panneaux", "battery_option",
                            "overrides")})
    data = dict(entree)
    data.update(moteur.calculate_quote(entree))
    data["pdf_mode"] = "full"
    for cle, val in surcharges.items():
        if cle not in ("battery_option", "overrides"):
            data[cle] = val
    return data


def _code(fonction):
    """Source d'une fonction, commentaires Python retirés (les commentaires
    EXPLIQUENT les marques historiques ; seul le code rendu compte)."""
    src = inspect.getsource(fonction)
    return "\n".join(ligne for ligne in src.splitlines()
                     if not ligne.lstrip().startswith("#"))


def _page3(html):
    """Dernier bloc ``class="page"`` du document rendu."""
    return html.split('class="page"')[-1]


def _visible(html):
    """Texte visible : styles, commentaires, balises et data-URI retirés."""
    txt = re.sub(r"<style>.*?</style>", " ", html, flags=re.S)
    txt = re.sub(r"<!--.*?-->", " ", txt, flags=re.S)
    txt = re.sub(r"<[^>]+>", " ", txt)
    txt = txt.replace("&#160;", " ").replace("&nbsp;", " ")
    return re.sub(r"[\s  ]+", " ", txt)


class TestTenantSurPage3(SimpleTestCase):
    """Un autre tenant n'est plus invité à choisir TAQINOR."""

    def setUp(self):
        self.html = moteur.render_html_for(_data(entreprise={
            "nom": "Soleil Atlas SARL", "email": "contact@soleilatlas.ma",
            "telephone": "+212 6 00 00 00 00"}))
        self.txt = _visible(_page3(self.html))

    def test_le_titre_et_la_signature_portent_le_tenant(self):
        self.assertIn("Pourquoi choisir SOLEIL ATLAS SARL", self.txt)
        self.assertIn("Signature SOLEIL ATLAS SARL", self.txt)

    def test_aucun_taqinor_visible_sur_la_page_signature(self):
        self.assertNotIn("TAQINOR", self.txt)
        self.assertNotIn("Taqinor", self.txt)

    def test_aucun_litteral_taqinor_dans_le_code_de_page3(self):
        self.assertNotIn("TAQINOR", _code(moteur.page3))

    def test_le_document_reste_a_trois_pages(self):
        self.assertEqual(self.html.count('class="page"'), 3)


class TestMarquesDerivees(SimpleTestCase):
    """La phrase « équipements » nomme les marques RÉELLEMENT vendues."""

    def test_les_marques_du_devis_sont_celles_imprimees(self):
        html = moteur.render_html_for(_data())
        txt = _visible(_page3(html))
        self.assertIn("Panneaux Canadian Solar", txt)
        self.assertIn("onduleurs Huawei", txt)
        # …et plus la liste gravée dans le moteur.
        self.assertNotIn("certifiés IEC", txt)

    def test_un_devis_a_marques_differentes_dit_SES_marques(self):
        data = _data()
        for it in data["sans_items"]:
            if "Panneaux" in it["designation"]:
                it["marque"] = "Longi"
            if "Onduleur" in it["designation"]:
                it["marque"] = "SMA"
        txt = _visible(_page3(moteur.render_html_for(data)))
        self.assertIn("Panneaux Longi", txt)
        self.assertIn("onduleurs SMA", txt)
        self.assertNotIn("Canadian Solar", txt)
        self.assertNotIn("Huawei", txt)

    def test_aucune_marque_lisible_omet_la_carte(self):
        data = _data()
        for it in data["sans_items"] + data["avec_items"]:
            it["marque"] = ""
        txt = _visible(_page3(moteur.render_html_for(data)))
        self.assertNotIn("Équipements de votre installation", txt)
        self.assertNotIn("garantie fabricant de chaque produit", txt)

    def test_aucun_nom_de_marque_code_en_dur_dans_page3(self):
        src = _code(moteur.page3)
        for marque in ("Canadian Solar", "Huawei", "Deye", "Longi"):
            with self.subTest(marque=marque):
                self.assertNotIn(marque, src)


class TestSupervisionAdossee(SimpleTestCase):
    """« Suivi en temps réel » n'est promis que si une ligne le porte."""

    def test_promesse_rendue_quand_le_devis_porte_le_materiel(self):
        # La démo vend un Smart Meter + un Wifi Dongle.
        txt = _visible(_page3(moteur.render_html_for(_data())))
        self.assertIn("Suivi en temps réel", txt)

    def test_promesse_omise_sans_materiel_de_communication(self):
        data = _data()
        garde = ("smart meter", "wifi", "dongle", "monitoring", "supervis")
        for cle in ("sans_items", "avec_items"):
            data[cle] = [it for it in data[cle]
                         if not any(m in it["designation"].lower()
                                    for m in garde)]
        txt = _visible(_page3(moteur.render_html_for(data)))
        self.assertNotIn("Suivi en temps réel", txt)
        self.assertNotIn("monitoring 24/7", txt)
