"""CALX299 — la section « Système », son annexe de fiches, et la jonction
des PDF constructeur.

Ce qui est prouvé ici, PUREMENT (aucune base, comme ``test_calx300_section_
pertes.py``) :

* le module posé (``pose``) et les onduleurs (``electrique.onduleurs``,
  avec leur ratio DC/AC) s'impriment depuis ``resultat`` ; un onduleur
  ``conforme: None`` imprime « non vérifiable », jamais « OK » ;
* l'annexe des fiches (``html_annexe_equipements``) : une fiche à 3 champs
  RENSEIGNÉS imprime EXACTEMENT 3 lignes et AUCUN zéro fabriqué ; un champ
  MANQUANT porte ``MENTION_FICHE_NON_RENSEIGNE`` ; un équipement SANS fiche
  (``specs`` quasi vide, comme le sert réellement ``services/equipements.py``
  pour une ``FicheTechnique`` nue) imprime la ligne d'incomplétude pour
  CHAQUE champ manquant — jamais un blanc silencieux ;
* AUCUN mot d'argent dans l'annexe (D5) ;
* la jonction PDF : ``fusionner_octets_pdf`` additionne les pages (PyMuPDF,
  même outillage que ``pack_technique.compter_pages``) ; deux fiches AVEC
  PDF ajoutent chacune une page de séparation + leur PDF ; une fiche SANS
  PDF n'ajoute AUCUNE page, seulement sa mention.

``annexes_pdf``/``equipements_pour_rapport`` touchent la base (ils prennent
le CALEPINAGE, pas ``contexte`` — voir la docstring de ``systeme.py``) : la
classe ``AnnexesPdfDbTest`` ci-dessous les prouve sur une fixture réelle,
ÉCRITE mais NON EXÉCUTÉE localement (règle de lane — CI validera).

Run (partie pure) :
    cd backend/django_core
    python -m pytest apps/calepinage/tests/test_calx299_section_systeme.py -q
"""
import unittest
from decimal import Decimal
from unittest import mock

from apps.calepinage.services.rapport.systeme import (
    LIBELLE_FAMILLE, MENTION_FICHE_NON_RENSEIGNE, MENTION_PDF_ABSENT,
    annexes_pdf, fusionner_octets_pdf, html_annexe_equipements,
    html_de_section, rendre_rapport_avec_annexes,
)

# ``services.rapport.*`` est un paquet PUR (aucun import Django au niveau du
# module — voir ``services/rapport/__init__.py``) : les essais ci-dessus
# tournent sans base ni réglages Django. ``AnnexesPdfDbTest`` prouve la
# partie qui LIT la base (``annexes_pdf`` prend le calepinage, pas
# ``contexte`` — voir la docstring de ``systeme.py``) ; ses imports Django
# sont donc TENTÉS ici et la classe n'est définie QUE si Django est
# configuré (``manage.py test`` / CI) — un ``pytest`` nu sur ce seul fichier
# continue de s'exécuter, purement, sans la toucher.
try:
    from apps.calepinage.models import Calepinage
    from apps.stock.models import FicheTechnique, Produit
    from apps.ventes.models import Devis, LigneDevis

    from .test_api_liste import BaseApiCalepinage
except Exception:  # noqa: BLE001 - Django non configuré (essais purs)
    BaseApiCalepinage = None

MOTIF = "motif de test — section systeme"


def contexte(resultat, langue='fr'):
    return {'resultat': resultat, 'langue': langue,
            'section': {'code': 'systeme', 'motif_si_absent': MOTIF}}


def _pdf_dune_page(texte=''):
    """Un PDF A4 MINIMAL, fabriqué par PyMuPDF — aucun rendu HTML nécessaire
    pour ces essais purs (même bibliothèque que ``pack_technique.py``)."""
    import fitz

    document = fitz.open()
    try:
        page = document.new_page(width=595, height=842)
        if texte:
            page.insert_textbox((50, 50, 500, 100), texte, fontsize=12)
        return document.tobytes()
    finally:
        document.close()


# ── Le corps de la section : module, onduleurs, batterie ────────────────────

class HtmlDeSectionTest(unittest.TestCase):
    def test_module_et_onduleurs_imprimes(self):
        resultat = {
            'pose': {'total_modules': 12, 'kwc': 8.64,
                     'pans': [{'pan': 'PAN-A', 'modules': 8, 'kwc': 5.76,
                               'azimut_deg': 180.0, 'inclinaison_deg': 15.0}]},
            'electrique': {'onduleurs': [{
                'reference': 'ONDULEUR-1', 'taille_kw': 10.0, 'nombre': 1,
                'puissance_dc_kwc': 8.64, 'ratio_dc_ac': 0.864, 'n_mppt': 2,
                'conforme': True, 'motif': ''}]},
        }
        html = html_de_section(contexte(resultat))
        self.assertIn('12', html)
        self.assertIn('ONDULEUR-1', html)
        self.assertIn('0,864', html)
        self.assertIn('oui', html)
        self.assertIn('PAN-A', html)

    def test_onduleur_non_conforme_et_non_verifiable_jamais_ok(self):
        resultat = {
            'pose': {'total_modules': 1, 'kwc': 0.72, 'pans': []},
            'electrique': {'onduleurs': [
                {'reference': 'A', 'conforme': False,
                 'motif': 'ratio DC/AC hors fourchette société'},
                {'reference': 'B', 'conforme': None},
            ]},
        }
        html = html_de_section(contexte(resultat))
        self.assertIn('non vérifiable', html)
        self.assertIn('ratio DC/AC hors fourchette société', html)
        self.assertNotIn('>OK<', html)

    def test_batterie_declaree_est_imprimee(self):
        resultat = {
            'pose': {}, 'electrique': {},
            'batterie': {'groupes': [{
                'groupe': 'BAT-ESSAI-1', 'packs': 2,
                'capacite_utile_kwh': 10.0, 'strategie': 'autoconsommation',
                'cycles_an': 280.0}]},
        }
        html = html_de_section(contexte(resultat))
        self.assertIn('BAT-ESSAI-1', html)
        self.assertIn('autoconsommation', html)

    def test_sans_batterie_aucun_bloc_batterie(self):
        html = html_de_section(contexte({'pose': {}, 'electrique': {}}))
        self.assertNotIn('Batterie', html)

    def test_equipements_du_resultat_alimentent_l_annexe(self):
        resultat = {
            'pose': {'total_modules': 1, 'kwc': 0.55, 'pans': []},
            'electrique': {'onduleurs': []},
            'equipements': {'panneau': {
                'designation': 'Module PV 550 Wc',
                'specs': {'pmax_wc': 550},
                'champs_renseignes': ['pmax_wc'],
                'champs_manquants': ['voc_v']}},
        }
        html = html_de_section(contexte(resultat))
        self.assertIn('Annexe des fiches', html)
        self.assertIn('550', html)

    def test_sans_equipements_aucune_annexe(self):
        resultat = {'pose': {'total_modules': 1, 'kwc': 0.55, 'pans': []},
                    'electrique': {'onduleurs': []}}
        html = html_de_section(contexte(resultat))
        self.assertNotIn('Annexe des fiches', html)


# ── L'annexe des fiches, champ par champ ────────────────────────────────────

class HtmlAnnexeEquipementsTest(unittest.TestCase):
    def test_trois_champs_renseignes_trois_lignes_et_aucun_zero(self):
        equipements = {'panneau': {
            'designation': 'Module PV 550 Wc',
            'specs': {'pmax_wc': 550, 'voc_v': 49.8, 'isc_a': 13.9},
            'champs_renseignes': ['pmax_wc', 'voc_v', 'isc_a'],
            'champs_manquants': [],
        }}
        html = html_annexe_equipements(equipements)
        self.assertEqual(html.count('<tr>'), 3)
        self.assertIn('550', html)
        self.assertIn('49,8', html)
        self.assertIn('13,9', html)
        self.assertNotIn('>0<', html)
        self.assertNotIn('<td>0</td>', html)

    def test_un_champ_manquant_porte_la_mention(self):
        equipements = {'onduleur': {
            'designation': 'Onduleur hybride 10 kW',
            'specs': {'n_mppt': 2},
            'champs_renseignes': ['n_mppt'],
            'champs_manquants': ['dc_max_kwc'],
        }}
        html = html_annexe_equipements(equipements)
        self.assertIn(MENTION_FICHE_NON_RENSEIGNE, html)
        self.assertIn('class="manquant"', html)

    def test_equipement_sans_fiche_imprime_l_incompletude_du_service(self):
        # Reprend EXACTEMENT ce que ``services/equipements.py`` sert pour un
        # produit dont la ``FicheTechnique`` est NUE (voir
        # ``test_api_equipements.py::test_fiche_vide_tous_les_champs_
        # manquants`` : ``specs == {'bifacial': False}``, tout le reste
        # manquant).
        champs_manquants = [
            'vmp_v', 'voc_v', 'isc_a', 'imp_a', 'pmax_wc',
            'temp_coeff_voc_pct_c', 'temp_coeff_pmax_pct_c', 'epaisseur_mm',
            'techno_cellule', 'noct_c',
        ]
        equipements = {'panneau': {
            'designation': 'Module sans specs',
            'specs': {'bifacial': False},
            'champs_renseignes': ['bifacial'],
            'champs_manquants': champs_manquants,
        }}
        html = html_annexe_equipements(equipements)
        self.assertEqual(html.count(MENTION_FICHE_NON_RENSEIGNE),
                         len(champs_manquants))
        self.assertIn('non</td>', html)  # bifacial: False -> 'non'

    def test_famille_non_retenue_est_omise(self):
        html = html_annexe_equipements({'panneau': None, 'onduleur': None,
                                        'batterie': None, 'optimiseur': None})
        self.assertEqual(html, '')

    def test_equipements_absent_ou_invalide_rend_une_chaine_vide(self):
        self.assertEqual(html_annexe_equipements(None), '')
        self.assertEqual(html_annexe_equipements({}), '')

    def test_aucun_mot_de_montant_dans_l_annexe(self):
        equipements = {'panneau': {
            'designation': 'Module PV 550 Wc',
            'specs': {'pmax_wc': 550},
            'champs_renseignes': ['pmax_wc'], 'champs_manquants': []}}
        html = html_annexe_equipements(equipements).lower()
        for mot in ('prix', 'achat', 'cout', 'coût', 'marge', 'mad'):
            self.assertNotIn(mot, html)


# ── La jonction des PDF constructeur ────────────────────────────────────────

class FusionOctetsPdfTest(unittest.TestCase):
    def test_fusionner_additionne_les_pages(self):
        from apps.calepinage.services.pack_technique import compter_pages

        fusion = fusionner_octets_pdf(
            [_pdf_dune_page(), _pdf_dune_page(), _pdf_dune_page()])
        self.assertEqual(compter_pages(fusion), 3)

    def test_fusionner_ignore_les_entrees_vides(self):
        from apps.calepinage.services.pack_technique import compter_pages

        fusion = fusionner_octets_pdf([_pdf_dune_page(), None, b'',
                                       _pdf_dune_page()])
        self.assertEqual(compter_pages(fusion), 2)


class RendreRapportAvecAnnexesTest(unittest.TestCase):
    """``annexes_pdf`` est REMPLACÉE (elle lit la base) : ces essais restent
    purs en injectant directement sa sortie et ``recuperer_pdf``."""

    def test_deux_fiches_avec_pdf_le_rapport_compte_les_pages(self):
        from apps.calepinage.services.pack_technique import compter_pages

        rapport_de_base = _pdf_dune_page('Rapport')
        octets_par_cle = {
            'k1': _pdf_dune_page('Fiche module'),
            'k2': _pdf_dune_page('Fiche onduleur'),
        }
        annexes = [
            {'famille': 'panneau', 'designation': 'Module', 'pdf_key': 'k1',
             'pdf_filename': 'module.pdf', 'motif': ''},
            {'famille': 'onduleur', 'designation': 'Onduleur',
             'pdf_key': 'k2', 'pdf_filename': 'onduleur.pdf', 'motif': ''},
        ]

        def recuperer(cle):
            return octets_par_cle[cle], None

        with mock.patch(
                'apps.calepinage.services.rapport.systeme.annexes_pdf',
                return_value=annexes):
            fusion, manques = rendre_rapport_avec_annexes(
                object(), rapport_de_base, recuperer_pdf=recuperer)

        self.assertEqual(manques, [])
        # Le rapport fusionné compte les pages de la note PLUS celles des
        # deux PDF constructeur — chacun précédé d'UNE page de séparation
        # qui le nomme (D-CALX 13, même discipline que
        # ``pack_technique`` : le total est la somme EXACTE des pièces).
        self.assertEqual(
            compter_pages(fusion),
            compter_pages(rapport_de_base)
            + sum(1 + compter_pages(o) for o in octets_par_cle.values()))

    def test_fiche_sans_pdf_la_mention_et_aucune_page_ajoutee(self):
        from apps.calepinage.services.pack_technique import compter_pages

        rapport_de_base = _pdf_dune_page('Rapport')
        annexes = [{'famille': 'panneau', 'designation': 'Module nu',
                    'pdf_key': None, 'pdf_filename': '',
                    'motif': MENTION_PDF_ABSENT}]

        def recuperer_jamais_appele(cle):
            raise AssertionError(
                'aucune fiche PDF disponible : recuperer_pdf ne doit pas '
                'être appelé')

        with mock.patch(
                'apps.calepinage.services.rapport.systeme.annexes_pdf',
                return_value=annexes):
            fusion, manques = rendre_rapport_avec_annexes(
                object(), rapport_de_base,
                recuperer_pdf=recuperer_jamais_appele)

        self.assertEqual(compter_pages(fusion), compter_pages(rapport_de_base))
        self.assertEqual(manques,
                         ['Module nu : %s' % MENTION_PDF_ABSENT])

    def test_libelle_famille_couvre_les_quatre_familles(self):
        self.assertEqual(set(LIBELLE_FAMILLE),
                         {'panneau', 'onduleur', 'batterie', 'optimiseur'})


# ── DB — prouve ``annexes_pdf``/``equipements_pour_rapport`` sur une
# fixture RÉELLE (mêmes helpers que test_api_equipements.py). Règle de
# lane : un test qui exige l'ORM/la base est ÉCRIT mais NON EXÉCUTÉ
# localement ici (pas de docker/DB dans ce worktree) — CI validera via
# ``manage.py test apps.calepinage.tests.test_calx299_section_systeme``.

if BaseApiCalepinage is not None:

    class AnnexesPdfDbTest(BaseApiCalepinage):
        """CI validera (nécessite la base de données)."""

        def setUp(self):
            super().setUp()
            self.calepinage = Calepinage.objects.create(
                company=self.company, lead_id=self.lead.pk, titre='Villa DB')

        def _produit_avec_fiche(self, *, nom, type_fiche, pdf_key='',
                                **champs):
            produit = Produit.objects.create(
                company=self.company, nom=nom, sku='CALX299-%s' % nom,
                prix_achat=Decimal('999'), prix_vente=Decimal('1500'),
                quantite_stock=1)
            FicheTechnique.objects.create(
                company=self.company, produit=produit, type_fiche=type_fiche,
                pdf_key=pdf_key,
                pdf_filename=('%s.pdf' % nom if pdf_key else ''), **champs)
            return produit

        def _devis_avec_lignes(self, *, reference, lignes):
            devis = Devis.objects.create(
                company=self.company, client=self.client_a,
                reference=reference)
            for produit, quantite in lignes:
                LigneDevis.objects.create(
                    devis=devis, produit=produit, designation=produit.nom,
                    quantite=quantite, prix_unitaire=Decimal('100'),
                    type_ligne='produit')
            return devis

        def test_une_fiche_avec_pdf_et_une_sans(self):
            panneau = self._produit_avec_fiche(
                nom='Module', type_fiche='module',
                pdf_key='minio/module.pdf', pmax_wc=Decimal('550'))
            onduleur = self._produit_avec_fiche(nom='Onduleur nu',
                                                type_fiche='onduleur')
            devis = self._devis_avec_lignes(
                reference='DEV-CALX299-1',
                lignes=[(panneau, Decimal('12')), (onduleur, Decimal('1'))])
            self.calepinage.devis = devis
            self.calepinage.save()

            par_famille = {a['famille']: a
                           for a in annexes_pdf(self.calepinage)}
            self.assertEqual(par_famille['panneau']['pdf_key'],
                             'minio/module.pdf')
            self.assertIsNone(par_famille['onduleur']['pdf_key'])
            self.assertEqual(par_famille['onduleur']['motif'],
                             MENTION_PDF_ABSENT)

        def test_sans_devis_lie_aucune_annexe(self):
            self.assertEqual(annexes_pdf(self.calepinage), [])


if __name__ == '__main__':  # pragma: no cover
    unittest.main()
