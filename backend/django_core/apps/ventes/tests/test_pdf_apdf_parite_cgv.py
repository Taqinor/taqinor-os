"""APDF48 (C-APDF-005, critère C10) — garde de parité des conditions générales
entre le PDF client et la page publique de signature.

Given une puce marqueur « PARITE-APDF » dans ``DocumentTemplates.cgv_bullets``
(et dans la variante ``cgv_par_mode`` du commercial et de l'industriel, avec
SON titre), When on rend les quatre marchés (résidentiel, commercial,
industriel, agricole) au format défaut, ``onepage`` et ``include_etude``, en
brouillon puis envoyé (``mark_devis_sent``, envoi réel), Then le marqueur, le
titre et CHAQUE puce que la page publique sert
(``payload_conditions._conditions_publiques(build_quote_data(d), d)`` et
``_conditions_titre_publique``) sont présents dans le texte du PDF, sans aucun
marqueur ``{...}`` non substitué, ni d'un côté ni de l'autre.

Rendu RÉEL : ``test_pdf_apdf_identite.rendre_pdf`` (PDF servi par /proposal,
registre des renderers et repli legacy, stockage MinIO remplacé en mémoire),
texte extrait par PyMuPDF (``texte_pdf``) ; options de la page publique lues
de ``public_views._opts_quote_data_public``. Aucune doublure du moteur. Le
rendu ne touche ni au statut ni aux clauses gelées (empreinte avant = après) ;
``TestCase`` : transaction annulée.

Écart déclaré (constat, pas une exemption silencieuse) : le une-page du
moteur legacy imprime les puces (``_conditions_onepage_html``) mais AUCUN
titre de conditions — le titre n'y est donc pas exigé
(``FORMATS_SANS_TITRE``) ; les puces et le marqueur le sont.

Rouge d'abord : sur le commit pré-APDF13, le résidentiel premium composait en
dur son bloc « Conditions » (validité / paiement / TVA) sans lire
``cgv_bullets`` ⇒ ``assertIn(MARQUEUR, pdf)`` échoue pour
(résidentiel, défaut) ; sans APDF19, la page publique servait les puces
résidentielles au lieu de la variante C&I ⇒ le cas (commercial|industriel)
échoue sur le marqueur côté page publique. Test-du-test : remettre le bloc
« Conditions » en dur de ``residential/trust.py`` ⇒ le cas
résidentiel-défaut échoue.
"""
import re
import unicodedata

from django.test import TestCase, tag

from apps.ventes.models import Devis
from apps.ventes.tests._quote_engine_common import (
    make_client, make_company, make_devis, make_user,
)
from apps.ventes.tests.test_pdf_apdf_identite import (
    MARCHES, rendre_pdf, texte_pdf,
)
from apps.ventes.tests.test_qjr668_clauses_cgv import _compact

MARQUEUR = 'PARITE-APDF'
#: Puces société (résidentiel, agricole) : le marqueur + une case remplie.
PUCES_SOCIETE = [f'{MARQUEUR} clause témoin',
                 'Acompte à la commande&#160;: {acompte}&#37;']
#: Variantes C&I : le marqueur + le marqueur {echeancier} (C-APDF-005).
TITRES_CI = {'commercial': 'TITRE CG COMMERCIAL',
             'industriel': 'TITRE CG INDUSTRIEL'}
FORMATS = {
    'defaut': {},
    'onepage': {'pdf_mode': 'onepage'},
    'include_etude': {'include_etude': True},
}
#: Le une-page legacy n'imprime aucun titre de conditions (écart déclaré).
FORMATS_SANS_TITRE = {'onepage'}
NON_SUBSTITUE = re.compile(r'\{[A-Za-z_]+\}')


def _norme(texte):
    """Compacté (aucun blanc), NFC, casse repliée : un titre en
    ``text-transform:uppercase`` reste le même titre."""
    return unicodedata.normalize('NFC', _compact(texte)).casefold()


@tag('pdf')
class PariteCgvTests(TestCase):

    def setUp(self):
        from apps.parametres.models_documents import DocumentTemplates
        self.company = make_company(slug='apdf48-co', nom='APDF48')
        modele = DocumentTemplates.get(company=self.company)
        modele.cgv_bullets = list(PUCES_SOCIETE)
        modele.cgv_par_mode = {mode: {
            'titre': titre,
            'bullets': [f'{MARQUEUR} clause {mode}', 'Echeancier {echeancier}'],
        } for mode, titre in TITRES_CI.items()}
        modele.save()
        self.user = make_user(self.company)
        client = make_client(self.company)
        self.devis = {}
        for marche, (lignes, etude, mode) in MARCHES.items():
            devis = make_devis(self.company, self.user, client, lignes,
                               reference=f'DEV-APDF48-{marche[:4].upper()}',
                               etude_params=dict(etude) if etude else None)
            devis.mode_installation = mode
            devis.save(update_fields=['mode_installation'])
            self.devis[marche] = devis

    def _publique(self, devis):
        """(titre, puces) que la page publique de signature sert."""
        from apps.ventes.public.payload_conditions import (
            _conditions_publiques, _conditions_titre_publique)
        from apps.ventes.public_views import _opts_quote_data_public
        from apps.ventes.quote_engine.builder import build_quote_data
        data = build_quote_data(devis, _opts_quote_data_public(None))
        return _conditions_titre_publique(data), _conditions_publiques(data, devis)

    def _empreinte(self, devis):
        return Devis.objects.filter(pk=devis.pk).values_list(
            'statut', 'clauses_appliquees').get()

    def _verifier(self, etat, rendus):
        for marche, devis in self.devis.items():
            titre, puces = self._publique(devis)
            for nom, options in FORMATS.items():
                with self.subTest(marche=marche, format=nom, etat=etat):
                    self.assertTrue(puces)
                    self.assertTrue(any(MARQUEUR in p for p in puces), puces)
                    if marche in TITRES_CI:
                        self.assertEqual(titre, TITRES_CI[marche])
                    self.assertTrue(titre)
                    for texte in [titre, *puces]:
                        self.assertIsNone(NON_SUBSTITUE.search(texte), texte)
                    avant = self._empreinte(devis)
                    brut = texte_pdf(rendre_pdf(devis, options))
                    self.assertEqual(self._empreinte(devis), avant)
                    self.assertEqual(avant[0], etat)
                    rendus.append((marche, nom, etat))
                    pdf = _norme(brut)
                    self.assertIn(_norme(MARQUEUR), pdf)
                    for puce in puces:
                        self.assertIn(_norme(puce), pdf)
                    if nom not in FORMATS_SANS_TITRE:
                        self.assertIn(_norme(titre), pdf)
                    self.assertIsNone(NON_SUBSTITUE.search(brut))

    def test_parite_marche_format_statut(self):
        from apps.ventes.domain.envoi import mark_devis_sent
        rendus = []
        self._verifier(Devis.Statut.BROUILLON, rendus)
        for devis in self.devis.values():
            mark_devis_sent(devis=devis, user=self.user)
            devis.refresh_from_db()
            self.assertEqual(devis.statut, Devis.Statut.ENVOYE)
        self._verifier(Devis.Statut.ENVOYE, rendus)
        # Le test LISTE ses rendus : 4 marchés × 3 formats × 2 états.
        self.assertEqual(len(rendus), len(MARCHES) * len(FORMATS) * 2, rendus)
