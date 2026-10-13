"""APDF20 (C-APDF-006) — à l'envoi, l'ENSEMBLE des textes contractuels du
devis (``DocumentTemplates.as_doc_texts`` fusionné au défaut du moteur : CGV,
titre, garanties, bon pour accord, validité…) et ``DocumentTemplates.version``
sont gelés dans UNE entrée ``doc_texts_geles`` de ``clauses_appliquees`` —
même quand la société n'a rien personnalisé (les défauts sont gelés).

Contrat figé ici (lu par APDF14, builder) :
``{'type': 'doc_texts_geles', 'textes': {<DEVIS_TEXT_KEYS>}, 'version': int}``.
L'entrée ``cgv_gelees`` existante est conservée (compatibilité).

Rejoue les sondes PCGV-2 / PCGV-2b : avant, seulement ``cgv_gelees`` (et rien
du tout pour une société sans puces). Test-du-test : retirer l'écriture de
``doc_texts_geles`` dans ``figer_clauses_devis`` ⇒
``test_gel_complet_avec_version`` échoue. Source réelle, aucun mock.
"""
import re
import unicodedata
from django.test import TestCase, tag
from django.utils import timezone
from rest_framework.test import APIClient

from apps.parametres.models_documents import DEVIS_TEXT_KEYS, DocumentTemplates
from apps.ventes.domain.envoi import TYPE_DOC_TEXTS_GELES
from apps.ventes.models import Devis
from apps.ventes.quote_engine.generate_devis_premium import DEFAULT_DOC_TEXTS
from apps.ventes.tests._quote_engine_common import (
    make_client, make_company, make_devis, make_user,
)
from apps.ventes.tests.test_pdf_apdf_identite import (
    MARCHES, rendre_pdf, texte_pdf,
)
from apps.ventes.tests.test_qjr668_clauses_cgv import _compact

PUCES_A = ['CGV-A acompte {acompte} % à la commande', 'CGV-A solde']


def _gel(devis):
    gels = [c for c in (devis.clauses_appliquees or [])
            if isinstance(c, dict) and c.get('type') == TYPE_DOC_TEXTS_GELES]
    return gels[0] if len(gels) == 1 else gels or None


class GelTextesEnvoiTests(TestCase):

    def setUp(self):
        self.company = make_company()
        self.user = make_user(self.company)
        self.client_obj = make_client(self.company)
        self.n = 0

    def _devis(self, statut=None):
        self.n += 1
        devis = make_devis(self.company, self.user, self.client_obj, [
            ('Panneau mono 450W', '10', '1500'),
            ('Onduleur réseau 5kW', '1', '9000'),
        ], reference=f'DEV-{timezone.now():%Y%m}-20{self.n:02d}')
        if statut:
            Devis.objects.filter(pk=devis.pk).update(statut=statut)
            devis.refresh_from_db()
        return devis

    def _envoyer(self, devis):
        from apps.ventes.domain.envoi import mark_devis_sent
        mark_devis_sent(devis=devis, user=self.user)
        devis.refresh_from_db()
        self.assertEqual(devis.statut, Devis.Statut.ENVOYE)
        return devis

    def test_gel_complet_avec_version(self):
        modeles = DocumentTemplates.get(company=self.company)
        modeles.cgv_titre = 'TITRE-A'
        modeles.bpa_mention = 'BPA-A'
        modeles.garantie_detail = 'GARANTIE-A'
        modeles.cgv_bullets = PUCES_A
        modeles.version = 7
        modeles.save()
        devis = self._envoyer(self._devis())
        gel = _gel(devis)
        self.assertIsInstance(gel, dict, devis.clauses_appliquees)
        self.assertEqual(set(gel), {'type', 'textes', 'version'})
        self.assertEqual(gel['version'], 7)
        self.assertEqual(set(gel['textes']), set(DEVIS_TEXT_KEYS))
        self.assertEqual(gel['textes']['cgv_titre'], 'TITRE-A')
        self.assertEqual(gel['textes']['bpa_mention'], 'BPA-A')
        self.assertEqual(gel['textes']['garantie_detail'], 'GARANTIE-A')
        self.assertEqual(gel['textes']['cgv_bullets'], PUCES_A)
        # Les clés non personnalisées portent le défaut du moteur.
        self.assertEqual(gel['textes']['bpa_titre'],
                         DEFAULT_DOC_TEXTS['bpa_titre'])
        # L'entrée historique ``cgv_gelees`` est conservée (compatibilité).
        self.assertTrue(any(
            isinstance(c, dict) and c.get('type') == 'cgv_gelees'
            for c in devis.clauses_appliquees))
        # CLAUSE PERSISTANCE — éditer les modèles ensuite ne change rien.
        modeles.cgv_titre = 'TITRE-B'
        modeles.version = 8
        modeles.save()
        devis.refresh_from_db()
        self.assertEqual(_gel(devis)['textes']['cgv_titre'], 'TITRE-A')
        self.assertEqual(_gel(devis)['version'], 7)

    def test_gel_defaut_sans_personnalisation(self):
        devis = self._envoyer(self._devis())
        gel = _gel(devis)
        self.assertIsInstance(gel, dict, devis.clauses_appliquees)
        attendus = {cle: DEFAULT_DOC_TEXTS.get(cle, '')
                    for cle in DEVIS_TEXT_KEYS}
        self.assertEqual(gel['textes'], attendus)
        self.assertEqual(
            gel['version'], DocumentTemplates.get(company=self.company).version)

    def test_correction_sur_place_regele(self):
        """Un envoyé d'avant ce gel (aucune entrée) reçoit le gel à sa
        correction sur place ; une seconde correction, après édition des
        modèles, ne le change pas."""
        modeles = DocumentTemplates.get(company=self.company)
        modeles.cgv_titre = 'TITRE-A'
        modeles.save()
        devis = self._devis(statut=Devis.Statut.ENVOYE)
        self.assertIsNone(_gel(devis))
        api = APIClient()
        api.force_authenticate(self.user)
        r = api.patch(f'/api/django/ventes/devis/{devis.id}/',
                      {'remise_globale': '3'}, format='json')
        self.assertEqual(r.status_code, 200, r.content)
        devis.refresh_from_db()
        self.assertEqual(devis.statut, Devis.Statut.ENVOYE)
        self.assertEqual(_gel(devis)['textes']['cgv_titre'], 'TITRE-A')
        modeles.cgv_titre = 'TITRE-B'
        modeles.save()
        r = api.patch(f'/api/django/ventes/devis/{devis.id}/',
                      {'remise_globale': '4'}, format='json')
        self.assertEqual(r.status_code, 200, r.content)
        devis.refresh_from_db()
        self.assertEqual(_gel(devis)['textes']['cgv_titre'], 'TITRE-A')


# APDF48 (C-APDF-005, critère C10) — garde de parité des conditions générales
# entre le PDF client et la page publique de signature.
#
# Given une puce marqueur « PARITE-APDF » dans ``DocumentTemplates.cgv_bullets``
# (et dans la variante ``cgv_par_mode`` du commercial et de l'industriel, avec
# SON titre), When on rend les quatre marchés (résidentiel, commercial,
# industriel, agricole) au format défaut, ``onepage`` et ``include_etude``, en
# brouillon puis envoyé (``mark_devis_sent``, envoi réel), Then le marqueur, le
# titre et CHAQUE puce que la page publique sert
# (``payload_conditions._conditions_publiques(build_quote_data(d), d)`` et
# ``_conditions_titre_publique``) sont présents dans le texte du PDF, sans aucun
# marqueur ``{...}`` non substitué, ni d'un côté ni de l'autre.
#
# Rendu RÉEL : ``test_pdf_apdf_identite.rendre_pdf`` (PDF servi par /proposal,
# registre des renderers et repli legacy, stockage MinIO remplacé en mémoire),
# texte extrait par PyMuPDF (``texte_pdf``) ; options de la page publique lues
# de ``public_views._opts_quote_data_public``. Aucune doublure du moteur. Le
# rendu ne touche ni au statut ni aux clauses gelées (empreinte avant = après) ;
# ``TestCase`` : transaction annulée.
#
# Écart déclaré (constat, pas une exemption silencieuse) : le une-page du
# moteur legacy imprime les puces (``_conditions_onepage_html``) mais AUCUN
# titre de conditions — le titre n'y est donc pas exigé
# (``FORMATS_SANS_TITRE``) ; les puces et le marqueur le sont.
#
# Rouge d'abord : sur le commit pré-APDF13, le résidentiel premium composait en
# dur son bloc « Conditions » (validité / paiement / TVA) sans lire
# ``cgv_bullets`` ⇒ ``assertIn(MARQUEUR, pdf)`` échoue pour
# (résidentiel, défaut) ; sans APDF19, la page publique servait les puces
# résidentielles au lieu de la variante C&I ⇒ le cas (commercial|industriel)
# échoue sur le marqueur côté page publique. Test-du-test : remettre le bloc
# « Conditions » en dur de ``residential/trust.py`` ⇒ le cas
# résidentiel-défaut échoue.
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
