"""CALX297 — le rapport d'étude PDF et son endpoint.

Ce qui est prouvé ici :

* le rapport assemble les sections DÉCLARÉES par ``rapport_etude.json``
  (CALX292), dans leur ordre, titrées dans la langue servie ;
* une section dont une ``entrees_exigees`` manque est imprimée AVEC sa phrase
  de motif et le nom des données manquantes — jamais vide, jamais masquée ;
* un résultat porteur d'une clé de coût est REFUSÉ à l'entrée, clé nommée
  (pare-feu repris de la note de calcul) ; un calepinage sans résultat est
  refusé en nommant ``resultat`` ;
* le HTML ne contient aucun mot de montant, aucun accès réseau, et porte
  l'empreinte (``hash_entree`` court + ``version_moteur``) dans son pied
  courant ; ``?langue=ar`` rend le français EN LE DISANT ;
* le PDF et l'aperçu partagent UNE fonction de mise en page, et le PDF passe
  par ``core.pdf.render_pdf`` ;
* en base (CI) : ``GET …/rapport-etude.pdf/`` rend le PDF borné société et
  permission, 400 + champ nommé sans résultat ou sur une clé de coût ;
* ``@tag('pdf')`` : un calepinage simulé rend un PDF NON VIDE dont le texte
  extrait ne contient aucun mot de montant.

Run :
    python manage.py test apps.calepinage.tests.test_calx297_rapport_etude -v2
"""
import copy
import json
import pathlib
import re
import unittest
from types import SimpleNamespace
from unittest import mock

from django.test import tag

from apps.calepinage.models import Calepinage
from apps.calepinage.services.documents import mise_en_page
from apps.calepinage.services.rapport import (
    RapportRefuse, construire_rapport, html_de_rapport, html_du_rapport,
    rendre_rapport, sections_declarees,
)

from .test_api_liste import BaseApiCalepinage, url_detail
from .test_cal171_planche import LAYOUT

RACINE_APP = pathlib.Path(__file__).resolve().parents[1]
ECHANTILLON = json.loads(
    (RACINE_APP / 'contract_samples' / 'calepinage_resultat.json')
    .read_text(encoding='utf-8'))
CONTRAT = json.loads(
    (RACINE_APP / 'contract_samples' / 'rapport_etude.json')
    .read_text(encoding='utf-8'))['exemple']['sections']
SOURCE = (RACINE_APP / 'services' / 'rapport' / '__init__.py').read_text(
    encoding='utf-8')

#: Un calepinage NON ENREGISTRÉ, sans société ni client : aucune lecture en
#: base (ni verrou, ni corbeille, ni CRM).
NU = SimpleNamespace(company=None, client_id=None, lead_id=None,
                     titre='Villa Anfa', resultat=None, pk=None)
SITE = {'ville': 'Bouskoura', 'adresse': 'Zone industrielle',
        'source': 'roof_point', 'pin': None, 'outline': None}
IDENTITE = {'titre_document': "Rapport d'étude", 'projet': 'Villa Anfa',
            'client': 'Mme Bennani', 'produit_le': '23/09/2026'}
STYLES = {'nom_affiche': 'Soleil Atlas', 'logo_url': '',
          'couleur_primaire': '', 'couleur_secondaire': ''}

#: Mots de montant, en JETONS ENTIERS (CALX327 élargira la garde à tout
#: document) — « marge » n'y est pas : c'est un mot GÉOMÉTRIQUE du moteur.
MOTS_DE_MONTANT = re.compile(
    r'(?<![\w-])(MAD|DH|prix|coût|cout|montant|remise|TTC|HT)(?![\w-])|€',
    re.IGNORECASE)


def resultat(cle='exemple'):
    return copy.deepcopy(ECHANTILLON[cle])


def rapport(**options):
    options.setdefault('resultat', resultat())
    options.setdefault('site', SITE)
    options.setdefault('identite', IDENTITE)
    options.setdefault('styles', STYLES)
    return construire_rapport(NU, **options)


class AssemblageTest(unittest.TestCase):
    def test_les_sections_sont_celles_du_contrat_dans_son_ordre(self):
        codes = [s['code'] for s in rapport()['sections']]
        attendus = [s['code'] for s in sorted(CONTRAT,
                                              key=lambda s: s['ordre'])]
        self.assertEqual(codes, attendus)
        self.assertEqual([s['code'] for s in sections_declarees()], attendus)

    def test_un_resultat_simule_rend_toutes_les_sections_disponibles(self):
        for section in rapport()['sections']:
            with self.subTest(section=section['code']):
                self.assertTrue(section['disponible'], section['manque'])
                self.assertIsNone(section['motif'])

    def test_une_entree_manquante_rend_la_section_avec_son_motif(self):
        sections = {s['code']: s for s in
                    rapport(resultat=resultat('exemple_vide'))['sections']}
        production = sections['production']
        self.assertFalse(production['disponible'])
        self.assertEqual(production['manque'],
                         ['production.total.p50_kwh', 'production.mensuel[]'])
        self.assertTrue(production['motif'])
        # La pose est connue d'un calepinage non simulé : le système reste.
        self.assertTrue(sections['systeme']['disponible'])

    def test_sans_resultat_le_rapport_refuse_en_nommant_resultat(self):
        for vide in (None, {}):
            with self.subTest(resultat=vide):
                with self.assertRaises(RapportRefuse) as capture:
                    construire_rapport(NU, resultat=vide, site=SITE,
                                       identite=IDENTITE, styles=STYLES)
                self.assertEqual(capture.exception.champ, 'resultat')

    def test_une_cle_de_cout_est_refusee_a_l_entree(self):
        donnees = resultat()
        donnees['pose']['prix_achat_total'] = 12345
        with self.assertRaises(RapportRefuse) as capture:
            rapport(resultat=donnees)
        self.assertIn('prix_achat', capture.exception.champ)
        self.assertIn('prix_achat', str(capture.exception))

    def test_une_cle_de_cout_du_resultat_stocke_est_refusee_aussi(self):
        with self.assertRaises(RapportRefuse) as capture:
            rapport(resultat_stocke={'cout_revient': 1})
        self.assertIn('cout_revient', capture.exception.champ)

    def test_les_marges_geometriques_ne_sont_pas_des_couts(self):
        donnees = resultat()
        donnees['marges'] = {'troncon_min_cm': 12}
        donnees['marge_troncon_min'] = 12
        rapport(resultat=donnees)  # ne lève pas

    def test_une_section_inconnue_est_refusee_en_la_nommant(self):
        with self.assertRaises(RapportRefuse) as capture:
            rapport(sections=['garde', 'section_fantome'])
        self.assertEqual(capture.exception.champ, 'sections')
        self.assertIn('section_fantome', str(capture.exception))

    def test_une_selection_garde_l_ordre_du_contrat(self):
        codes = [s['code'] for s in
                 rapport(sections=['pertes', 'garde'])['sections']]
        self.assertEqual(codes, ['garde', 'pertes'])


class MiseEnPageTest(unittest.TestCase):
    def setUp(self):
        self.html = html_de_rapport(rapport())

    def test_une_garde_puis_une_section_par_code(self):
        self.assertEqual(self.html.count('class="page-de-garde"'), 1)
        imprimees = re.findall(r'data-section="([a-z_]+)"', self.html)
        self.assertEqual(imprimees, [s['code'] for s in rapport()['sections']
                                     if s['code'] != 'garde'])

    def test_aucune_section_n_est_imprimee_vide(self):
        html = html_de_rapport(rapport(resultat=resultat('exemple_vide')))
        for bloc in re.findall(r'<section class="section-rapport".*?'
                               r'</section>', html):
            corps = re.sub(r'<h2>.*?</h2>', '', bloc)
            self.assertTrue(re.sub(r'<[^>]+>', '', corps).strip(), bloc)
        self.assertIn('Donnée manquante', html)
        self.assertIn('production.mensuel[]', html)

    def test_le_pied_porte_l_empreinte_et_la_version_du_moteur(self):
        pied = re.search(r'<div class="gabarit-pied">.*?</div></div>',
                         self.html).group(0)
        self.assertIn('entrée abababababab', pied)
        self.assertIn('moteur non-publie-dans-cet-exemple', pied)
        self.assertIn('@bottom-left{content:element(gabarit-pied)', self.html)

    def test_aucun_mot_de_montant_aucun_acces_reseau(self):
        texte = re.sub(r'<style>.*?</style>', '', self.html, flags=re.S)
        texte = re.sub(r'<[^>]+>', ' ', texte)
        self.assertIsNone(MOTS_DE_MONTANT.search(texte),
                          MOTS_DE_MONTANT.search(texte))
        for interdit in ('http://', 'https://', '@import', '<img'):
            self.assertNotIn(interdit, self.html)

    def test_les_nombres_sont_imprimes_tels_que_servis(self):
        # production.total.p50_kwh = 13000.0 : ni arrondi, ni séparateur.
        self.assertIn('13000,0', self.html)

    def test_la_langue_anglaise_titre_les_sections_en_anglais(self):
        html = html_de_rapport(rapport(langue='en'))
        self.assertIn('<html lang="en"', html)
        self.assertIn('<h2>Loss chain</h2>', html)
        self.assertIn('Design report', html)

    def test_l_arabe_retombe_sur_le_francais_en_le_disant(self):
        html = html_de_rapport(rapport(langue='ar'))
        self.assertIn('<html lang="fr"', html)
        self.assertIn('Document demandé en arabe', html)


class RenduPartageTest(unittest.TestCase):
    OPTIONS = dict(resultat=None, site=SITE, identite=IDENTITE, styles=STYLES)

    def test_le_pdf_passe_par_la_plomberie_partagee_et_la_meme_mise_en_page(
            self):
        options = dict(self.OPTIONS, resultat=resultat())
        with mock.patch('core.pdf.render_pdf',
                        return_value=b'%PDF-simule') as rendu:
            octets = rendre_rapport(NU, **options)
        self.assertEqual(octets, b'%PDF-simule')
        self.assertEqual(rendu.call_args.kwargs['html'],
                         html_du_rapport(NU, **options))

    def test_l_apercu_et_le_pdf_partagent_une_seule_fonction(self):
        self.assertIs(mise_en_page('rapport_etude'), html_du_rapport)

    def test_aucun_import_weasyprint_direct(self):
        self.assertNotIn('import weasyprint', SOURCE)
        self.assertNotIn('from weasyprint', SOURCE)
        self.assertNotRegex(SOURCE, r'TAQINOR|taqinor\.ma')


@tag('pdf')
class RenduReelTest(unittest.TestCase):
    """WeasyPrint + PyMuPDF réels — étiqueté ``pdf`` (hors du palier CI)."""

    def setUp(self):
        try:
            import fitz  # noqa: F401
            import weasyprint  # noqa: F401
        except Exception:  # noqa: BLE001 — bibliothèques natives absentes
            self.skipTest('WeasyPrint ou PyMuPDF indisponible sur ce poste')

    def test_un_calepinage_simule_rend_un_pdf_non_vide_sans_montant(self):
        import fitz

        from apps.calepinage.services.pack_technique import compter_pages

        octets = rendre_rapport(NU, resultat=resultat(), site=SITE,
                                identite=IDENTITE, styles=STYLES)
        self.assertGreater(compter_pages(octets), 1)
        document = fitz.open(stream=octets, filetype='pdf')
        try:
            texte = '\n'.join(page.get_text() for page in document)
        finally:
            document.close()
        self.assertIsNone(MOTS_DE_MONTANT.search(texte),
                          MOTS_DE_MONTANT.search(texte))
        self.assertIn('abababababab', texte)


PDF = b'%PDF-1.7 rapport simule'


class EndpointRapportEnBaseTest(BaseApiCalepinage):
    """``GET …/rapport-etude.pdf/`` — câblage, société, permission (CI).

    Le rendu WeasyPrint est simulé (``core.pdf.render_pdf`` a ses propres
    essais) et le résultat servi est celui du CONTRAT (``resultat_calepinage``
    a les siens) : ce qui est vérifié ici, c'est la porte.
    """

    def setUp(self):
        super().setUp()
        self.calepinage = Calepinage.objects.create(
            company=self.company, lead_id=self.lead.pk,
            titre='Villa Anfa', roof_layout=LAYOUT,
            layout_hash='a' * 64, resultat=resultat())
        self.etranger = Calepinage.objects.create(
            company=self.autre, lead_id=7, titre='Chez la voisine',
            roof_layout=LAYOUT, resultat=resultat())
        self.sans_resultat = Calepinage.objects.create(
            company=self.company, lead_id=self.lead.pk,
            titre='Jamais calculé', roof_layout=LAYOUT)

    def _url(self, calepinage, suite=''):
        return f'{url_detail(calepinage.pk)}rapport-etude.pdf/{suite}'

    def _get(self, calepinage, api=None, suite=''):
        with mock.patch(
                'apps.calepinage.services.electrique.resultat_calepinage',
                return_value=resultat()), \
                mock.patch('core.pdf.render_pdf', return_value=PDF) as rendu:
            reponse = (api or self.api).get(self._url(calepinage, suite))
        return reponse, rendu

    def test_le_pdf_se_telecharge_borne_societe(self):
        reponse, rendu = self._get(self.calepinage)
        self.assertEqual(reponse.status_code, 200)
        self.assertEqual(reponse['Content-Type'], 'application/pdf')
        self.assertEqual(reponse.content, PDF)
        self.assertTrue(reponse['Content-Disposition'].endswith(
            'rapport-etude.pdf"'))
        self.assertEqual(rendu.call_args.kwargs['company'], self.company)
        self.assertIn('data-section="pertes"', rendu.call_args.kwargs['html'])

    def test_la_langue_demandee_est_servie(self):
        _reponse, rendu = self._get(self.calepinage, suite='?langue=en')
        self.assertIn('<html lang="en"', rendu.call_args.kwargs['html'])

    def test_sans_resultat_400_en_nommant_resultat(self):
        reponse, rendu = self._get(self.sans_resultat)
        self.assertEqual(reponse.status_code, 400)
        self.assertIn('resultat', reponse.data)
        rendu.assert_not_called()

    def test_une_cle_de_cout_stockee_est_refusee_400(self):
        donnees = resultat()
        donnees['pose']['prix_achat_total'] = 1
        self.calepinage.resultat = donnees
        self.calepinage.save(update_fields=['resultat'])
        reponse, _rendu = self._get(self.calepinage)
        self.assertEqual(reponse.status_code, 400)
        self.assertTrue(any('prix_achat' in cle for cle in reponse.data))

    def test_une_autre_societe_est_introuvable(self):
        reponse, _rendu = self._get(self.etranger)
        self.assertEqual(reponse.status_code, 404)

    def test_sans_permission_de_lecture_c_est_403(self):
        reponse, _rendu = self._get(self.calepinage, api=self.api_sans)
        self.assertEqual(reponse.status_code, 403)


if __name__ == '__main__':  # pragma: no cover
    unittest.main()
