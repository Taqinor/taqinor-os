"""QJR429 / DR6 — la pastille PVGIS NOMME sa ville de référence.

**CLOS EN « DÉJÀ CORRIGÉ — PREUVE JOINTE ».** Le rouge annoncé ne se reproduit
pas à l'analyse, et la règle du groupe interdit d'inventer un correctif :

* le constat disait « le client lit qu'une ville de référence a été utilisée,
  **sans jamais savoir laquelle** » ;
* or ``generate_devis_premium.page1`` imprime la ville AVANT le suffixe —
  ``… kWh par kWc et par an **à {_prod_ville.title()}** {_prod_suffixe}`` — et
  ``_prod_ville`` EST la ville de RÉFÉRENCE : ``builder`` pose
  ``hypotheses['productible_ville'] = ville_reference(_client_city)``
  (``productible.ville_reference`` : « rend le nom de la ville de RÉFÉRENCE
  (``'casablanca'`` pour Settat) »), jamais la ville du client hors table.

C'est le correctif QJR127 lui-même, que le texte de la tâche déclare
« CONFIRMÉ et son correctif tient » : il NOMME déjà la ville. Aucun octet n'a
donc été changé ; ce module reste comme GARDE — il échouera le jour où un
rendu cesserait de nommer la ville de référence, ou toucherait au rendu de la
ville reconnue (``white-space:nowrap`` compris).

(La mention « à confirmer » n'existe pas sur cette pastille : rien à retirer.)

Run :
    powershell -File scripts/test-backend.ps1 -RestoreDb \
        -Modules "apps.ventes.tests.test_qjr429_pastille_ville_reference"
"""
from django.test import SimpleTestCase

from apps.ventes.tests import _moteur_fixtures as F


#: Le fragment qui ouvre la pastille : il précède la valeur et la ville.
DEBUT_PASTILLE = 'kWh par kWc et par an'


def _html_pastille(ville, est_reference):
    """Le HTML legacy rendu avec CETTE hypothèse de productible."""
    base = dict(F.donnees_legacy('deux').get('hypotheses') or {})
    base.update({
        'productible_net_kwh_kwc': 1600,
        'productible_ville': ville,
        'productible_ville_est_reference': est_reference,
    })
    return F.html_legacy('deux', hypotheses=base)


def _extrait_pastille(html):
    """Le contenu de la pastille, de l'ouverture de son span à sa fermeture."""
    fin = html.index('</span>', html.index(DEBUT_PASTILLE))
    return html[html.rindex('<span', 0, fin):fin]


def _valeur_productible(pastille):
    """Le NOMBRE imprimé par la pastille (entre le « ≈ » et « kWh »)."""
    debut = pastille.index('&#8776;')
    return pastille[debut:pastille.index(DEBUT_PASTILLE)]


class VilleHorsTablePvgis(SimpleTestCase):
    """Client à Settat → la table PVGIS sert la valeur de Casablanca."""

    def setUp(self):
        self.pastille = _extrait_pastille(_html_pastille('casablanca', False))

    def test_la_pastille_nomme_la_ville_de_reference(self):
        """DR6 : la ville de référence est NOMMÉE, pas seulement évoquée."""
        self.assertIn('Casablanca', self.pastille)

    def test_elle_dit_que_c_est_une_ville_de_reference(self):
        self.assertIn('ville de r&#233;f&#233;rence la plus proche',
                      self.pastille)


class VilleReconnueRenduInchange(SimpleTestCase):
    """Ville DANS la table : rendu inchangé à l'octet, ``nowrap`` compris."""

    def setUp(self):
        self.html = _html_pastille('casablanca', True)
        self.pastille = _extrait_pastille(self.html)

    def test_le_suffixe_reste_la_forme_courte(self):
        self.assertIn('&#224; Casablanca (donn&#233;e PVGIS)', self.pastille)
        self.assertNotIn('ville de r&#233;f&#233;rence', self.pastille)

    def test_le_nowrap_est_conserve(self):
        self.assertIn('white-space:nowrap;', self.html)


class LaValeurImprimeeNeChangeJamais(SimpleTestCase):
    """Seule la mention de PROVENANCE distingue les deux cas."""

    def test_le_productible_est_le_meme_des_deux_cotes(self):
        reconnue = _extrait_pastille(_html_pastille('casablanca', True))
        reference = _extrait_pastille(_html_pastille('casablanca', False))
        valeur = _valeur_productible(reconnue)
        self.assertTrue(valeur.strip())
        self.assertEqual(valeur, _valeur_productible(reference))
