"""CAD122 — le formalisme de la loi 31-08 quand le bon se signe CHEZ le client.

Décision fondateur du 21/09/2026 (audit L3 cadence, section CAD-K). La visite
technique se passe au domicile, après le devis, et le bon de commande s'y
signe PARFOIS : la loi 31-08 (texte ONSSA) définit alors le démarchage à
l'art. 45 comme la proposition d'achat au domicile « même à sa demande », et
l'art. 46 n'exclut rien qui couvre le solaire. Le dépôt ne connaissait la
rétractation qu'à l'art. 32 (vente à DISTANCE).

Ce fichier verrouille les deux moitiés de la décision :

  * un document marqué « signé au domicile » porte l'ANNEXE DÉTACHABLE de
    rétractation et les mentions de l'art. 48 ;
  * un bon marqué « signé au domicile » REFUSE tout encaissement d'acompte
    avant J+7 (art. 49 et 50), avec un message qui NOMME la date ;

et, tout aussi important, que **rien ne change** pour une signature à
distance ou au bureau : même document, même encaissement, art. 32 intact.
"""
import datetime
import itertools
import re

from django.contrib.auth import get_user_model
from django.test import SimpleTestCase, TestCase

from apps.crm.models import Client
from apps.ventes.models import (
    DELAI_RETRACTATION_DOMICILE_JOURS, AcompteAvantDelaiLegal, BonCommande,
    Devis)
from apps.ventes.quote_engine import generate_devis_premium as moteur
from apps.ventes.tests import _moteur_fixtures as F

User = get_user_model()

_company_seq = itertools.count(1)


def _data(**surcharges):
    data = F.donnees_legacy(pdf_mode="full")
    data.update(surcharges)
    return data


def _visible(html):
    """Texte visible : styles, commentaires, balises et entités retirés."""
    txt = re.sub(r"<style>.*?</style>", " ", html, flags=re.S)
    txt = re.sub(r"<!--.*?-->", " ", txt, flags=re.S)
    txt = re.sub(r"<[^>]+>", " ", txt)
    txt = (txt.replace("&#160;", " ").replace("&nbsp;", " ")
              .replace("&#8217;", "'"))
    return re.sub(r"\s+", " ", txt)


class AnnexeRetractationTests(SimpleTestCase):
    """La page rendue — aucune base de données, aucun PDF."""

    def test_signature_a_distance_laisse_le_document_inchange(self):
        """Art. 32 : rien ne change. Même nombre de pages, aucune annexe."""
        html = moteur.render_html_for(_data())
        texte = _visible(html)
        self.assertNotIn("tractation", texte)
        self.assertNotIn("31-08", texte)
        self.assertEqual(html.count('class="page"'), 3)

    def test_signature_au_domicile_ajoute_lannexe_detachable(self):
        html = moteur.render_html_for(_data(signe_au_domicile=True))
        texte = _visible(html)
        self.assertIn("Formulaire d", texte)
        self.assertIn("rétractation", texte)
        # La page s'AJOUTE : les trois pages du document restent.
        self.assertEqual(html.count('class="page"'), 4)

    def test_lannexe_cite_les_articles_48_49_et_50(self):
        texte = _visible(
            moteur.render_html_for(_data(signe_au_domicile=True)))
        self.assertIn("48", texte)
        self.assertIn("49", texte)
        self.assertIn("50", texte)
        self.assertIn("31-08", texte)

    def test_lannexe_annonce_le_delai_de_la_loi_et_pas_un_autre(self):
        texte = _visible(
            moteur.render_html_for(_data(signe_au_domicile=True)))
        self.assertIn(f"{DELAI_RETRACTATION_DOMICILE_JOURS} jours", texte)

    def test_lannexe_est_la_derniere_page(self):
        """Elle se DÉTACHE : elle ne s'intercale pas au milieu du devis."""
        html = moteur.render_html_for(_data(signe_au_domicile=True))
        derniere = html.split('class="page"')[-1]
        self.assertIn("tractation", _visible(derniere))

    def test_aucun_prix_dans_lannexe(self):
        """Une pièce juridique ne republie aucun chiffrage."""
        html = moteur.render_html_for(_data(signe_au_domicile=True))
        derniere = _visible(html.split('class="page"')[-1])
        self.assertNotIn("MAD", derniere)


class DelaiAcompteTests(TestCase):
    """La règle des articles 49 et 50, sur le bon de commande."""

    def setUp(self):
        from authentication.models import Company
        numero = next(_company_seq)
        self.company = Company.objects.create(
            nom=f'CAD122 {numero}', slug=f'cad122-{numero}')
        self.client_final = Client.objects.create(
            company=self.company, nom='Benali')
        self.devis = Devis.objects.create(
            company=self.company, reference=f'DV-CAD122-{numero}',
            client=self.client_final)
        self.signature = datetime.date(2026, 9, 21)

    def _bon(self, **extra):
        return BonCommande.objects.create(
            company=self.company, reference=f'BC-{next(_company_seq)}',
            client=self.client_final, devis=self.devis, **extra)

    def test_bon_signe_a_distance_nest_pas_concerne(self):
        bon = self._bon()
        self.assertIsNone(bon.acompte_encaissable_le)
        # Aucune exception, quelle que soit la date.
        bon.verifier_encaissement_acompte(a_la_date=self.signature)

    def test_bon_signe_au_domicile_refuse_avant_sept_jours(self):
        bon = self._bon(signe_au_domicile=True,
                        date_signature_domicile=self.signature)
        self.assertEqual(
            bon.acompte_encaissable_le,
            self.signature + datetime.timedelta(
                days=DELAI_RETRACTATION_DOMICILE_JOURS))
        veille = bon.acompte_encaissable_le - datetime.timedelta(days=1)
        with self.assertRaises(AcompteAvantDelaiLegal) as leve:
            bon.verifier_encaissement_acompte(a_la_date=veille)
        # Le message NOMME la date — jamais un refus générique.
        self.assertIn(bon.acompte_encaissable_le.strftime('%d/%m/%Y'),
                      str(leve.exception))

    def test_bon_signe_au_domicile_accepte_a_j7(self):
        bon = self._bon(signe_au_domicile=True,
                        date_signature_domicile=self.signature)
        bon.verifier_encaissement_acompte(
            a_la_date=bon.acompte_encaissable_le)

    def test_le_delai_part_de_la_date_ecrite_par_le_client(self):
        """Art. 47 al. 2 : c'est la date de SA main qui fait foi."""
        bon = self._bon(signe_au_domicile=True,
                        date_signature_domicile=self.signature)
        self.assertEqual(bon.date_commande_domicile, self.signature)

    def test_sans_date_ecrite_le_delai_part_de_la_creation_du_bon(self):
        """Le délai ne se raccourcit jamais au détriment du client."""
        bon = self._bon(signe_au_domicile=True)
        self.assertEqual(bon.date_commande_domicile,
                         bon.date_creation.date())
        self.assertEqual(
            bon.acompte_encaissable_le,
            bon.date_creation.date() + datetime.timedelta(
                days=DELAI_RETRACTATION_DOMICILE_JOURS))

    def test_un_instant_est_accepte_comme_date(self):
        """L'appelant peut passer un datetime : on compare des JOURS."""
        bon = self._bon(signe_au_domicile=True,
                        date_signature_domicile=self.signature)
        instant = datetime.datetime.combine(
            bon.acompte_encaissable_le, datetime.time(9, 0),
            tzinfo=datetime.timezone.utc)
        bon.verifier_encaissement_acompte(a_la_date=instant)

    def test_le_champ_porte_sa_question(self):
        """« Chaque champ EST le script d'appel » : la question vit ici."""
        champ = BonCommande._meta.get_field('signe_au_domicile')
        self.assertTrue(champ.help_text)
        self.assertFalse(champ.default)
        date = BonCommande._meta.get_field('date_signature_domicile')
        self.assertTrue(date.null)
        self.assertTrue(date.help_text)
