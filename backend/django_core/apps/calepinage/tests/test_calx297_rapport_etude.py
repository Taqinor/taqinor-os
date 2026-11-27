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
import importlib
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


#: ACAL834 — un dimensionnement de pompage enregistré (clé ``exemple_enregistre``
#: de ``calepinage_pompage.json``, posée par ACAL831).
POMPAGE_STOCKE = {'pompage_dernier': json.loads(
    (RACINE_APP / 'contract_samples' / 'calepinage_pompage.json')
    .read_text(encoding='utf-8'))['exemple_enregistre']}


def resultat(cle='exemple'):
    return copy.deepcopy(ECHANTILLON[cle])


def rapport(**options):
    options.setdefault('resultat', resultat())
    options.setdefault('resultat_stocke', POMPAGE_STOCKE)  # ACAL834
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


class NoteDeValidationTest(unittest.TestCase):
    """ACAL475 — les écarts du banc, tels que figés, dans le rapport."""

    def html(self, **modif):
        res = resultat()
        res.update(modif)
        return html_du_rapport(NU, resultat=res, site=SITE,
                               identite=IDENTITE, styles=STYLES)

    def test_la_note_de_validation_imprime_les_ecarts_du_banc(self):
        from apps.calepinage.services.rapport import nombre_tel_que_servi
        banc = json.loads((RACINE_APP / 'donnees' / 'banc_validation.json')
                          .read_text(encoding='utf-8'))
        page = self.html()
        self.assertIn('Note de validation', page)
        for nom, site in banc['sites'].items():
            self.assertIn(nom.capitalize(), page)
            self.assertIn(nombre_tel_que_servi(
                site['ecart_pvcalc_annuel_pct']), page)
            for valeur in site['ecart_pvcalc_mensuel_pct'].values():
                self.assertIn('>%s<' % nombre_tel_que_servi(valeur), page)

    def test_la_ligne_de_cette_etude_et_aucun_mot_valide(self):
        page = self.html(validation={
            'ecart_pct': -1.96, 'tolerance_pct': 5.0,
            'tolerance_source': 'réglage société'})
        self.assertIn('-1,96', page)
        self.assertIn('réglage société', page)
        sans = self.html(validation=None)
        self.assertIn('non calculé — lancez la simulation', sans)
        self.assertNotRegex(page + sans, r'(?i)\bvalidée?s?\b')


class ConsommationEtSectionsOmisesTest(unittest.TestCase):
    """ACAL832 — la consommation servie est imprimée telle quelle ; sans
    consommation, ni section ni ligne « non calculé » à l'annexe."""

    def page(self, res):
        return html_du_rapport(NU, resultat=res, site=SITE,
                               identite=IDENTITE, styles=STYLES,
                               paginer=False)

    def test_la_consommation_servie_est_imprimee_telle_quelle(self):
        from apps.calepinage.services.rapport import nombre_tel_que_servi
        res = resultat()
        page = self.page(res)
        self.assertIn('data-section="consommation"', page)
        self.assertIn('Consommation et hypothèses', page)
        bloc = res['consommation']
        self.assertIn(nombre_tel_que_servi(bloc['total_kwh']), page)
        # ACAL1744 — l'origine en mots (« profil_mensuel » → « profil mensuel saisi »).
        from apps.calepinage.services.rapport.consommation import ORIGINES_COURBE
        self.assertIn(ORIGINES_COURBE[bloc['courbe_origine']], page)
        charge = bloc['charges'][0]
        self.assertIn(charge['libelle'].replace("'", '&#x27;'), page)
        self.assertIn(nombre_tel_que_servi(charge['kwh_an']), page)

    def test_sans_consommation_ni_section_ni_ligne_non_calcule(self):
        res = resultat()
        res['consommation'] = None
        sections = [s['code'] for s in rapport(resultat=res)['sections']]
        self.assertNotIn('consommation', sections)
        page = self.page(res)
        self.assertNotIn('data-section="consommation"', page)
        self.assertNotIn('consommation.total_kwh', page)

    def test_acal1744_mois_en_lettres_et_origine_traduite(self):
        from apps.calepinage.services import courbe_charge
        from apps.calepinage.services.rapport.consommation import ORIGINES_COURBE

        self.assertEqual(set(ORIGINES_COURBE), set(courbe_charge.ORIGINES))
        res = resultat()
        res['consommation']['courbe_origine'] = 'layout'
        res['consommation']['profil_mensuel'] = [{'mois': 1, 'kwh': 800.0},
                                                 {'mois': 12, 'kwh': 900.0}]
        page = self.page(res)
        section = re.search(r'data-section="consommation".*?</section>', page, re.S).group(0)
        self.assertIn('saisie du calepinage', section)
        self.assertNotIn('>layout<', section)
        self.assertIn('<td>Janvier</td>', section)
        self.assertIn('<td>Décembre</td>', section)
        self.assertNotIn('<td class="valeur">12</td>', section)

    def test_le_total_n_est_pas_arrondi(self):
        res = resultat()
        res['consommation']['total_kwh'] = 9600.123
        self.assertIn('9\u202f600,123', self.page(res))


class PompageTest(unittest.TestCase):
    """ACAL834 — le pompage enregistré, imprimé tel que servi."""

    def page(self, stocke):
        return html_du_rapport(NU, resultat=resultat(), resultat_stocke=stocke,
                               site=SITE, identite=IDENTITE, styles=STYLES,
                               paginer=False)

    def test_pompage_enregistre_imprime_tel_que_servi(self):
        page = self.page(copy.deepcopy(POMPAGE_STOCKE))
        self.assertIn('data-section="pompage"', page)
        for attendu in ('62,4', 'calculee', '49,6', '4,8', '8,2', '4,0',
                        'Variateur VEICHI', '1\u202f441,3', '1\u202f330,1', 'pvgis_live',
                        '103,3', '95,3', '1,3', '2026-11-21T10:15:00+00:00'):
            self.assertIn(attendu, page)
        self.assertNotIn('1\u202f607,2', page)  # février plat : PVGIS prime

    def test_volumes_nuls_aucun_m3_imprime(self):
        stocke = copy.deepcopy(POMPAGE_STOCKE)
        stocke['pompage_dernier']['volumes'] = None
        page = self.page(stocke)
        self.assertIn('Volumes mensuels : non calculés', page)
        self.assertNotIn('1\u202f441,3', page)

    def test_sans_enregistrement_la_section_est_absente(self):
        for stocke in ({}, {'pompage_dernier': {}}, None):
            with self.subTest(stocke=stocke):
                codes = [s['code'] for s in rapport(
                    resultat_stocke=stocke)['sections']]
                self.assertNotIn('pompage', codes)
                self.assertNotIn('data-section="pompage"',
                                 self.page(stocke))

    def test_un_volume_arrondi_est_detecte(self):
        stocke = copy.deepcopy(POMPAGE_STOCKE)
        stocke['pompage_dernier']['volumes']['m3_mois_pvgis'][0] = 1441.0
        self.assertNotIn('1\u202f441,3', self.page(stocke))


class RapportDePompageTest(unittest.TestCase):
    """Décision fondateur 6 (27/11/2026) — le rapport d'un calepinage de
    POMPAGE (conception du marché agricole) n'imprime ni production ni
    autoconsommation : il garde débit, HMT et volume par jour. Tout autre
    calepinage rend le rapport d'aujourd'hui, octet pour octet."""

    CONCEPTION = 'apps.calepinage.services.devis_retenu.conception_du_calepinage'

    def page(self, marche, res=None):
        with mock.patch(self.CONCEPTION, return_value={'marche': marche}):
            return html_du_rapport(
                NU, resultat=res or resultat(),
                resultat_stocke=copy.deepcopy(POMPAGE_STOCKE), site=SITE,
                identite=IDENTITE, styles=STYLES, paginer=False)

    @staticmethod
    def texte(page):
        page = re.sub(r'<style.*?</style>', ' ', page, flags=re.S)
        return re.sub(r'<[^>]+>', ' ', page)

    def resultat_de_pompe(self):
        res = resultat()
        res['batterie'] = None  # une composition de pompage n'a pas de batterie
        return res

    def test_ni_production_ni_autoconsommation_dans_le_texte(self):
        from apps.calepinage.services.rapport import nombre_tel_que_servi
        res = self.resultat_de_pompe()
        texte = self.texte(self.page('agricole', res))
        # « Date de production » de la page de garde est la date d'édition du
        # document, pas une énergie : c'est la seule occurrence admise.
        texte = texte.replace('Date de production', 'Date d’édition')
        self.assertNotRegex(texte, r'(?i)production|autoconsomm|productible')
        total = res['production']['total']
        energie = res['autoconsommation']['energie']
        for chiffre in (total['p50_kwh'], total['p90_kwh'],
                        total['specific_yield_kwh_kwc'],
                        energie['production_brute_kwh'],
                        energie['export_reseau_kwh']):
            with self.subTest(chiffre=chiffre):
                self.assertNotIn(nombre_tel_que_servi(chiffre), texte)

    def test_les_sections_de_production_sont_omises(self):
        with mock.patch(self.CONCEPTION, return_value={'marche': 'agricole'}):
            codes = [s['code'] for s in rapport()['sections']]
        for code in ('production', 'autoconsommation', 'validation'):
            self.assertNotIn(code, codes)
        self.assertIn('pompage', codes)

    def synthese(self, volumes):
        stocke = copy.deepcopy(POMPAGE_STOCKE)
        stocke['pompage_dernier']['volumes'] = volumes
        with mock.patch(self.CONCEPTION, return_value={'marche': 'agricole'}):
            page = html_du_rapport(NU, resultat=self.resultat_de_pompe(),
                                   resultat_stocke=stocke, site=SITE,
                                   identite=IDENTITE, styles=STYLES,
                                   paginer=False)
        return re.search(r'data-section="synthese".*?</section>', page,
                         re.S).group(0)

    def test_la_synthese_garde_debit_hmt_et_renvoie_aux_volumes(self):
        synthese = self.synthese(
            copy.deepcopy(POMPAGE_STOCKE['pompage_dernier']['volumes']))
        for attendu in ('8,2 m³/h', '62,4 m<'):
            self.assertIn(attendu, synthese)
        self.assertNotIn('Onduleurs', synthese)

    def test_plafond_atteint_aucun_m3_jour_plat(self):
        """Revue 12 — le calcul PLAT (débit × heures) ignore le plafond du
        forage : jamais imprimé quand le plafond est atteint."""
        volumes = copy.deepcopy(POMPAGE_STOCKE['pompage_dernier']['volumes'])
        self.assertTrue(volumes['plafond_atteint'])
        synthese = self.synthese(volumes)
        self.assertNotIn('57,4', synthese)
        self.assertIn('plafond du forage atteint', synthese)
        self.assertIn('section Pompage', synthese)
        # même sans série physique : le plat n'est pas imprimé non plus.
        volumes['m3_mois_pvgis'] = None
        self.assertNotIn('57,4', self.synthese(volumes))

    def test_serie_physique_servie_la_synthese_renvoie_a_la_section(self):
        """La section Pompage imprime la série physique d'abord : la synthèse
        n'imprime pas un autre chiffre (le plat), elle y renvoie."""
        volumes = copy.deepcopy(POMPAGE_STOCKE['pompage_dernier']['volumes'])
        volumes['plafond_atteint'] = False
        synthese = self.synthese(volumes)
        self.assertNotIn('57,4', synthese)
        self.assertIn('section Pompage', synthese)

    def test_plafond_non_atteint_sans_serie_physique_plat_etiquete(self):
        """Seul le plat est servi : la section imprime m3_mois_plat (= m³/jour
        plat × jours) ; la synthèse imprime le m³/jour plat, étiqueté."""
        volumes = copy.deepcopy(POMPAGE_STOCKE['pompage_dernier']['volumes'])
        volumes.update(plafond_atteint=False, m3_mois_pvgis=None)
        synthese = self.synthese(volumes)
        self.assertIn('Volume pompé par jour (calcul plat : débit × heures '
                      'de pompage)</th><td>57,4 m³/jour', synthese)
        self.assertAlmostEqual(volumes['m3_mois_plat'][0],
                               volumes['m3_jour_plat'] * 31, places=0)

    def test_sans_volume_servi_aucun_m3_jour(self):
        res = self.resultat_de_pompe()
        with mock.patch(self.CONCEPTION, return_value={'marche': 'agricole'}):
            stocke = copy.deepcopy(POMPAGE_STOCKE)
            stocke['pompage_dernier']['volumes'] = None
            page = html_du_rapport(NU, resultat=res, resultat_stocke=stocke,
                                   site=SITE, identite=IDENTITE,
                                   styles=STYLES, paginer=False)
        self.assertNotIn('57,4', page)
        self.assertIn('Volume pompé par jour</th><td>non calculée', page)

    def test_un_autre_marche_rend_le_rapport_d_aujourd_hui(self):
        aujourd_hui = html_du_rapport(
            NU, resultat=resultat(),
            resultat_stocke=copy.deepcopy(POMPAGE_STOCKE), site=SITE,
            identite=IDENTITE, styles=STYLES, paginer=False)
        for marche in ('residentiel', 'commercial', 'industriel', None):
            with self.subTest(marche=marche):
                self.assertEqual(self.page(marche), aujourd_hui)
        self.assertIn('Production annuelle P50', aujourd_hui)


class HorsReseauTest(unittest.TestCase):
    """ACAL833 — défaillance, pire mois et banque ; omise si raccordé."""

    BLOC = {
        'defaillance_kwh': 250.0, 'heures_defaillantes': 96,
        'taux_defaillance': 0.026, 'mois_le_plus_defavorable': 12,
        'par_mois': [{'mois': 11, 'defaillance_kwh': 8.0,
                      'heures_defaillantes': 3},
                     {'mois': 12, 'defaillance_kwh': 40.0,
                      'heures_defaillantes': 9}],
        'soc_minimal_pct': 18.4,
        'banque': {'capacite_utile_kwh': 10.0, 'capacite_nominale_kwh': 11.1,
                   'jours_autonomie': 2.0, 'dod_pct': 90.0,
                   'source_dod': 'fiche'},
        'mentions': ['Mention servie du bloc.'],
        'quantiles_publiables': False,
        'motif_quantiles': 'Aucun quantile P75/P90 hors réseau.',
        'motif_absence': '',
    }

    def page(self, res):
        return html_du_rapport(NU, resultat=res, site=SITE,
                               identite=IDENTITE, styles=STYLES,
                               paginer=False)

    def test_hors_reseau_imprime_defaillance_pire_mois_et_banque(self):
        res = resultat()
        res['hors_reseau'] = copy.deepcopy(self.BLOC)
        page = self.page(res)
        self.assertIn('data-section="hors_reseau"', page)
        for attendu in ('250,0', '18,4', '11,1', 'fiche',
                        'Mention servie du bloc.',
                        'Aucun quantile P75/P90 hors réseau.'):
            self.assertIn(attendu, page)
        # ACAL1744 — le mois en lettres, jamais son numéro.
        self.assertIn('Décembre (mois le plus défavorable)', page)
        self.assertNotIn('Novembre (mois le plus défavorable)', page)
        self.assertNotIn('12 (mois le plus défavorable)', page)

    def test_raccorde_la_section_est_absente(self):
        res = resultat()
        res['hors_reseau'] = dict(self.BLOC, defaillance_kwh=None)
        sections = [s['code'] for s in rapport(resultat=res)['sections']]
        self.assertNotIn('hors_reseau', sections)
        page = self.page(res)
        self.assertNotIn('data-section="hors_reseau"', page)
        self.assertNotIn('hors_reseau.defaillance_kwh', page)


class PhotosSiteTest(unittest.TestCase):
    """ACAL759 — les photos déposées, légendées et datées, dans le rapport."""

    PNG = 'data:image/png;base64,iVBORw0KGgo='
    DEUX = [
        {'genre': 'drone', 'legende': 'Toiture nord',
         'prise_le': '2026-09-01', 'url': PNG},
        {'genre': 'sol', 'legende': '', 'prise_le': '2026-09-03', 'url': PNG},
    ]

    def html(self, photos):
        return html_du_rapport(NU, resultat=resultat(), site=SITE,
                               identite=IDENTITE, styles=STYLES,
                               photos=photos, paginer=False)

    def test_deux_photos_deux_figures_dans_l_ordre_servi(self):
        page = self.html(self.DEUX)
        self.assertEqual(page.count('<figure class="photo-site">'), 2)
        self.assertLess(page.index('Toiture nord — 2026-09-01'),
                        page.index('sol — 2026-09-03'))

    def test_aucune_photo_dit_la_phrase(self):
        page = self.html([])
        self.assertIn('Aucune photo du site déposée pour ce calepinage.',
                      page)
        self.assertNotIn('<figure', page)

    def test_octets_illisibles_disent_image_indisponible(self):
        page = self.html([dict(self.DEUX[0], url='')])
        self.assertIn('Image indisponible.', page)
        self.assertNotIn('<img', page)

    def test_la_section_suit_le_site_et_la_meteo(self):
        page = self.html(self.DEUX)
        self.assertLess(page.index('Site et source météo'),
                        page.index('Photos du site'))


class AutoconsommationTest(unittest.TestCase):
    """ACAL757 — taux, bilan d'énergie, batterie et mois, tels que servis."""

    def section(self, res):
        from apps.calepinage.services.rapport import autoconsommation
        return autoconsommation.html_de_section({'resultat': res})

    def test_imprime_les_valeurs_de_l_exemple_du_contrat(self):
        from apps.calepinage.services.rapport import nombre_tel_que_servi
        res = resultat()
        page = self.section(res)
        for taux in ('62,0 %', '71,0 %', '58,0 %'):
            self.assertIn(taux, page)
        energie = res['autoconsommation']['energie']
        for cle in ('production_brute_kwh', 'export_reseau_kwh'):
            self.assertIn(nombre_tel_que_servi(energie[cle]), page)
        from html import escape
        self.assertIn(escape(res['autoconsommation']['definition']), page)
        self.assertIn('96', page)  # heures écrêtées du plafond
        total = res['batterie']['total']
        self.assertIn(nombre_tel_que_servi(total['energie_stockee_kwh']), page)
        self.assertIn(nombre_tel_que_servi(
            total['energie']['pertes_batterie_kwh']), page)
        self.assertIn('BAT-ESSAI-1', page)

    def test_douze_lignes_mensuelles(self):
        res = resultat()
        page = self.section(res)
        self.assertEqual(len(res['autoconsommation']['par_mois']), 12)
        for mois in res['autoconsommation']['par_mois']:
            self.assertIn('<td class="valeur">%d</td>' % mois['mois'], page)
        # en-tête + 12 lignes dans la table mensuelle
        self.assertIn('Autoconsommée (kWh)', page)

    def test_un_motif_d_absence_remplace_les_tables(self):
        res = resultat()
        res['autoconsommation'] = {'motif_absence': 'Aucune courbe de charge.'}
        page = self.section(res)
        self.assertIn('Aucune courbe de charge.', page)
        self.assertNotIn('Taux de couverture', page)

    def test_un_taux_absent_n_est_jamais_un_zero(self):
        res = resultat()
        res['autoconsommation']['taux_autonomie'] = None
        page = self.section(res)
        self.assertIn('non calculée', page)
        self.assertNotIn('0,0 %', page)

    def test_un_taux_n_est_pas_arrondi_a_l_entier(self):
        res = resultat()
        res['autoconsommation']['taux_couverture'] = 0.7123
        self.assertIn('71,23 %', self.section(res))


class SyntheseTest(unittest.TestCase):
    """ACAL756 — la page de chiffres clés, lue dans le résultat servi."""

    def synthese(self, res):
        from apps.calepinage.services.rapport import synthese
        return synthese.html_de_section({'resultat': res})

    def test_imprime_les_chiffres_de_l_exemple_du_contrat(self):
        from apps.calepinage.services.rapport import nombre_tel_que_servi
        res = resultat()
        page = self.synthese(res)
        total = res['production']['total']
        self.assertIn(nombre_tel_que_servi(total['p50_kwh']), page)
        self.assertIn(nombre_tel_que_servi(total['p90_kwh']), page)
        self.assertIn(nombre_tel_que_servi(res['pose']['kwc']), page)
        self.assertIn('71,0 %', page)  # taux_couverture 0.71 x 100
        self.assertIn('aucun contrôle non conforme', page)
        self.assertLessEqual(page.count('<tr>'), 12)

    def test_la_synthese_suit_la_garde_dans_le_rapport(self):
        page = html_du_rapport(NU, resultat=resultat(), site=SITE,
                               identite=IDENTITE, styles=STYLES)
        self.assertIn('Synthèse', page)
        self.assertLess(page.index('Synthèse'),
                        page.index('Site et source météo'))

    def test_une_donnee_absente_est_non_calculee_jamais_zero(self):
        res = resultat('exemple_vide')
        page = self.synthese(res)
        self.assertIn('non calculée', page)
        self.assertNotIn('>0 kWh<', page)
        self.assertNotIn('>0,0 %<', page)

    def test_un_resultat_incomplet_porte_la_mention_borne_haute(self):
        res = resultat()
        res['production']['total']['complete'] = False
        res['production']['total']['mention'] = 'borne haute — 2 pertes'
        self.assertIn('borne haute — 2 pertes', self.synthese(res))

    def test_onduleur_choisi_sans_chaine_ne_dit_pas_aucun_onduleur(self):
        """T4-U2-014 — calepinage 1933 : Huawei 50 kW choisi à l'étape Électrique
        (la même ``resoudre_materiel`` que le rapport), mais le module n'est pas
        désigné : aucune chaîne, donc ``electrique.onduleurs`` vide. Le rapport
        imprimait « aucun onduleur désigné » ; il dit la VRAIE cause servie."""
        res = resultat()
        res['electrique'] = {'chainage': None, 'onduleurs': [],
                             'affectation': [], 'verdicts': []}
        absent = "module PV non désigné — désignez-le dans l'onglet Matériel électrique"
        res['avertissements'] = ['La production n’est pas encore calculée.', absent]
        page = self.synthese(res)
        attendu = ('non calculée — aucune chaîne calculée : module PV non désigné '
                   '— désignez-le dans l&#x27;onglet Matériel électrique')
        self.assertIn('<tr><th>Onduleurs</th><td>%s</td></tr>' % attendu, page)
        self.assertIn('<tr><th>Contrôles électriques non conformes</th><td>%s'
                      '</td></tr>' % attendu, page)
        self.assertNotIn('aucun onduleur désigné', page)
        # Fiche de l'onduleur incomplète : la cause est la fiche, pas l'absence.
        res['avertissements'] = ['onduleur : bas de plage MPPT']
        self.assertIn('aucune chaîne calculée : onduleur : bas de plage MPPT',
                      self.synthese(res))
        # Rien de servi qui l'explique : la chaîne absente est dite, sans inventer.
        res['avertissements'] = []
        self.assertIn('non calculée — aucune chaîne calculée</td>', self.synthese(res))

    def test_synthese_sans_onduleur_dit_son_motif(self):
        # ACAL1677 - cas 1898 : aucun onduleur désigné, aucun verdict. Les
        # deux lignes disaient « non calculée » SANS motif.
        res = resultat()
        res['electrique'] = {'chainage': None, 'onduleurs': [],
                             'affectation': [], 'verdicts': []}
        # T4-U2-014 — « aucun onduleur désigné » vient de l'absence SERVIE.
        res['avertissements'] = [
            "onduleur non désigné — désignez-le dans l'onglet Matériel électrique"]
        page = self.synthese(res)
        self.assertIn(
            '<tr><th>Onduleurs</th><td>non calculée — aucun onduleur '
            'désigné</td></tr>', page)
        self.assertIn(
            '<tr><th>Contrôles électriques non conformes</th><td>non '
            'calculée — aucun onduleur désigné</td></tr>', page)
        self.assertNotIn('<td>non calculée</td>', page)

    def test_synthese_controles_lisent_le_motif_servi(self):
        # ACAL1677 - un onduleur désigné mais aucun verdict : le motif
        # électrique SERVI sur l'onduleur (``onduleurs[].motif``) est imprimé
        # tel quel ; sans motif servi, la chaîne absente est nommée.
        res = resultat()
        res['electrique']['verdicts'] = []
        res['electrique']['onduleurs'][0]['motif'] = 'tension MPPT hors plage'
        page = self.synthese(res)
        self.assertIn('non calculée — tension MPPT hors plage', page)
        self.assertIn('ONDULEUR-ESSAI-1', page)
        res['electrique']['onduleurs'][0]['motif'] = ''
        self.assertIn('non calculée — aucune chaîne calculée',
                      self.synthese(res))

    def _cas_1945(self, complet=False):
        # ACAL1701 - calepinage 1945 : 5 × 710 Wc = 3,55 kWc ; P50 servi
        # 8 198,3 kWh ; productible = 8 198,3 / 3,55 = 2 309,4 kWh/kWc (fait
        # à la main : 3,55 × 2 309,4 = 8 198,37) ; 19 pertes non renseignées.
        res = resultat()
        res['pose']['kwc'] = 3.55
        total = res['production']['total']
        total.update(kwc=3.55, p50_kwh=8198.3, specific_yield_kwh_kwc=2309.4,
                     complete=complet,
                     mention='' if complet
                     else 'borne haute — 19 pertes non renseignées')
        return res

    def test_synthese_incomplete_le_productible_porte_la_mention(self):
        page = self.synthese(self._cas_1945())
        self.assertIn(
            '<tr><th>Productible spécifique</th><td>2 309,4 kWh/kWc'
            '<span class="detail">borne haute — 19 pertes non renseignées'
            '</span></td></tr>', page)
        self.assertIn('8 198,3 kWh<span class="detail">borne haute — '
                      '19 pertes non renseignées</span>', page)
        # Un résultat complet imprime les deux lignes comme avant.
        complet = self.synthese(self._cas_1945(complet=True))
        self.assertIn('<tr><th>Productible spécifique</th><td>2 309,4 '
                      'kWh/kWc</td></tr>', complet)
        self.assertNotIn('borne haute', complet)

    def test_section_production_incomplete_le_productible_porte_la_mention(
            self):
        from apps.calepinage.services.rapport import production

        page = production.html_de_section({'resultat': self._cas_1945()})
        self.assertIn(
            '<tr><th>Productible spécifique (kWh/kWc)</th><td>2 309,4 '
            '<span class="detail mention-borne-haute">borne haute — 19 pertes '
            'non renseignées</span></td></tr>', page)

    def test_la_mention_borne_haute_s_imprime_en_corps_lisible(self):
        # Le rendu COMPLET du rapport porte les feuilles de style des
        # sections : la mention (classe ``detail``) de la synthèse et de la
        # production est en 9 pt au moins (elle l'était en 7,5 pt gris).
        page = html_du_rapport(NU, resultat=self._cas_1945(), site=SITE,
                               identite=IDENTITE, styles=STYLES)
        tailles = re.findall(
            r'\.(?:synthese|production-totaux|production-quantiles) '
            r'\.detail[^{]*\{[^}]*font-size:([\d.]+)pt', page)
        self.assertTrue(tailles)
        for taille in tailles:
            self.assertGreaterEqual(float(taille), 9.0)

    def test_un_controle_non_conforme_est_nomme(self):
        res = resultat()
        res['electrique']['verdicts'][0]['conforme'] = False
        res['electrique']['verdicts'][0]['libelle'] = 'Voc trop haute'
        self.assertIn('Voc trop haute', self.synthese(res))


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
        self.assertIn('production mois par mois', html)  # ACAL1716 — plus la clé brute
        self.assertNotIn('production.mensuel[]', html)

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
        # production.total.p50_kwh = 13000.0 : ni arrondi ; les milliers se groupent (R3-18).
        self.assertIn('13\u202f000,0', self.html)

    def test_la_langue_anglaise_titre_les_sections_en_anglais(self):
        html = html_de_rapport(rapport(langue='en'))
        self.assertIn('<html lang="en"', html)
        self.assertIn('<h2>Loss chain</h2>', html)
        self.assertIn('Design report', html)

    def test_l_arabe_retombe_sur_le_francais_en_le_disant(self):
        html = html_de_rapport(rapport(langue='ar'))
        self.assertIn('<html lang="fr"', html)
        self.assertIn('Document demandé en arabe', html)


class PagesDixOnzeTest(unittest.TestCase):
    """ACAL1635 — « où va l'énergie » : chaque poste porte le motif de SA
    grandeur, aucune ligne de texte ne dépasse son bloc, le schéma et la table
    de la cascade tiennent dans la largeur de la page."""

    MOTIF_HORIZON = 'Aucun profil d horizon joint au document.'
    MOTIF_OMBRAGE = 'Aucune matrice d ombrage proche publiée pour ce pan ' * 3

    def _svg(self):
        from apps.calepinage.services.diagramme_energie import svg_d_energie

        poste = {'poste': 'ombres_proches', 'libelle': 'Ombres proches',
                 'statut': 'non_compte', 'perte_kwh': None, 'etapes': [
                     {'etape': 'horizon', 'motif_omission': self.MOTIF_HORIZON},
                     {'etape': 'ombrage_proche',
                      'motif_omission': self.MOTIF_OMBRAGE.strip()}]}
        return svg_d_energie({'cascade': {'postes_lisibles': {
            'depart_kwh': 6380.0, 'arrivee_kwh': 5000.0, 'postes': [poste]}}})

    def test_ombres_proches_porte_le_motif_de_l_ombrage_proche(self):
        texte = re.sub(r'<[^>]+>', '\n', self._svg())
        self.assertIn('Aucune matrice d ombrage proche', texte)
        self.assertNotIn(self.MOTIF_HORIZON, texte)

    def test_aucune_ligne_ne_depasse_son_bloc(self):
        from apps.calepinage.services.diagramme_energie import CARACTERES_LIGNE

        lignes = re.findall(r'<text [^>]*>([^<]*)</text>', self._svg())
        self.assertGreater(len(lignes), 4)  # le long motif est réparti
        for ligne in lignes:
            self.assertLessEqual(len(ligne), CARACTERES_LIGNE + len(' kWh'), ligne)
        self.assertIn('6 380,0 kWh', self._svg())

    def test_schema_et_table_tiennent_dans_la_page(self):
        from apps.calepinage.services.rapport.pertes import CSS_SECTION

        self.assertIn('.diagramme-energie svg{display:block;width:100%', CSS_SECTION)
        self.assertIn('overflow-wrap:anywhere', CSS_SECTION)


class PertesNonRenseigneesEnMotsTest(unittest.TestCase):
    """ACAL1928 — pages 3 et 12 et écran : aucun code de poste (« ohmique_dc »)
    ni chemin pointé (« electrique_societe.seuil_bas_dc_ac ») n'est imprimé ;
    la donnée stockée, relue par ``a_renseigner``, ne change pas. Mutant :
    formater les codes bruts ⇒ échec."""

    POSTES = 'salissure, lid, ohmique_dc, ohmique_ac, qualite_module, indisponibilite'

    def _motif(self):
        from apps.calepinage.services.chaine_pertes import MOTIF_SOCLE_MANQUANT

        return MOTIF_SOCLE_MANQUANT.format(postes=self.POSTES)

    def _sans_code(self, texte):
        self.assertIn('LID (première exposition)', texte)
        self.assertIn('pertes ohmiques DC', texte)
        for code in ('ohmique_dc', 'qualite_module', 'indisponibilite,', ' lid,'):
            self.assertNotIn(code, texte)

    def test_page_de_synthese_et_production(self):
        from apps.calepinage.services.rapport.production import texte_non_publie
        from apps.calepinage.services.rapport.synthese import _valeur

        self._sans_code(_valeur(None, self._motif()))
        total = {'p75_kwh_motif': self._motif(), 'p50_kwh': 1000.0,
                 'portee': 'borne_haute', 'mention': 'borne haute'}
        with mock.patch('apps.calepinage.services.rapport.production._resultat_incomplet',
                        return_value=True):
            self._sans_code(texte_non_publie(total, 'p75_kwh'))

    def test_ecran_production_sans_chemin_pointe_stocke_intact(self):
        from apps.calepinage.services.rapport.champs_lisibles import avec_motifs_lisibles

        stocke = {'production': {'total': {
            'p75_kwh_motif': self._motif(),
            'performance_ratio_motif': ('Réglages à saisir : electrique_societe.'
                                        'seuil_bas_dc_ac')}}}
        avant = copy.deepcopy(stocke)
        total = avec_motifs_lisibles(stocke)['production']['total']
        self._sans_code(total['p75_kwh_motif'])
        self.assertNotIn('electrique_societe.', total['performance_ratio_motif'])
        self.assertEqual(stocke, avant)


class ProvenanceDesPostesTest(unittest.TestCase):
    """ACAL1656 — pp. 7-9 et 19 : chaque poste dit sa provenance réelle, aucun
    chemin de code ni nom de tâche."""

    def _html(self, pertes):
        from apps.calepinage.services.rapport.pertes import html_de_section

        etapes = [
            # Seule la PROVENANCE est lue ici : aucune part de perte chiffrée
            # (garde CAL238) ; la colonne « part » imprime alors « — ».
            {'etape': 'lid', 'libelle': 'LID', 'kwh_avant': 100.0, 'kwh_apres': 98.0,
             'motif_omission': '', 'source': 'saisie'},
            {'etape': 'iam', 'libelle': 'IAM', 'kwh_avant': 98.0, 'kwh_apres': 97.0,
             'motif_omission': '', 'source': 'texte',
             'reference': 'core.calepinage.soleil (CALX146)'}]
        return html_de_section({'resultat': {'cascade': {'etapes': etapes, 'total_pct': 3.0},
                                             'pertes': pertes},
                                'langue': 'fr', 'section': {'motif_si_absent': 'x'}})

    def ligne(self, html, etape):
        return re.search(r'<tr[^>]*data-etape="%s">.*?</tr>' % etape, html).group(0)

    def test_poste_du_calepinage_dit_saisie_du_calepinage(self):
        html = self._html([{'poste': 'lid', 'pct': 2.0, 'source': 'saisie'}])
        self.assertIn('saisie du calepinage', self.ligne(html, 'lid'))
        self.assertNotIn('saisie société', self.ligne(html, 'lid'))
        # Sans poste saisi en face : le glossaire de la note (inchangé).
        self.assertIn('saisie société', self.ligne(self._html([]), 'lid'))

    def test_source_texte_et_reference_sans_code(self):
        iam = self.ligne(self._html([]), 'iam')
        self.assertIn('page publiée', iam)
        self.assertIn('position du soleil', iam)
        self.assertNotIn('CALX146', iam)
        self.assertNotIn('core.calepinage', iam)

    def test_donnee_manquante_en_intitule(self):
        from apps.calepinage.services.rapport import _motif_html

        html = _motif_html({'motif_si_absent': 'Absent.',
                            'manque': ['electrique.chainage', 'production.total.p50_kwh']}, 'fr')
        self.assertIn('câblage des chaînes', html)
        self.assertIn('production annuelle P50 (kWh)', html)
        self.assertNotIn('electrique.chainage', html)


class RenduPartageTest(unittest.TestCase):
    OPTIONS = dict(resultat=None, site=SITE, identite=IDENTITE, styles=STYLES)

    def test_le_pdf_passe_par_la_plomberie_partagee_et_la_meme_mise_en_page(
            self):
        options = dict(self.OPTIONS, resultat=resultat())
        with mock.patch('core.pdf.render_pdf',
                        return_value=b'%PDF-simule') as rendu:
            octets = rendre_rapport(NU, **options)
            servi = rendu.call_args.kwargs['html']
            # Le sommaire compte les pages de chaque section par
            # ``core.pdf.render_pdf`` : l'attendu est composé sous le MÊME
            # rendu simulé (au vrai rendu, la section production d'ACAL694/708
            # tient sur deux pages et décale le sommaire d'une page).
            attendu = html_du_rapport(NU, **options)
        self.assertEqual(octets, b'%PDF-simule')
        self.assertEqual(servi, attendu)

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
            importlib.import_module('fitz')
            importlib.import_module('weasyprint')
        except Exception:  # bibliothèques natives absentes
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
        self.assertEqual(reponse.status_code, 409)
        self.assertIn('resultat', reponse.data)
        rendu.assert_not_called()

    def test_une_cle_de_cout_stockee_est_refusee_400(self):
        donnees = resultat()
        donnees['pose']['prix_achat_total'] = 1
        self.calepinage.resultat = donnees
        self.calepinage.save(update_fields=['resultat'])
        reponse, _rendu = self._get(self.calepinage)
        self.assertEqual(reponse.status_code, 409)
        self.assertTrue(any('prix_achat' in cle for cle in reponse.data))

    def test_une_autre_societe_est_introuvable(self):
        reponse, _rendu = self._get(self.etranger)
        self.assertEqual(reponse.status_code, 404)

    def test_sans_permission_de_lecture_c_est_403(self):
        reponse, _rendu = self._get(self.calepinage, api=self.api_sans)
        self.assertEqual(reponse.status_code, 403)


if __name__ == '__main__':  # pragma: no cover
    unittest.main()


class AnnexeEtValidationSansCleBruteTest(unittest.TestCase):
    """ACAL1716 — « Donnée manquante » et la méthode de validation parlent
    métier : aucun chemin pointé (``production.total.p50_kwh``) ni code de
    poste (``thermique, ohmique_ac``) dans le texte imprimé."""

    def test_table_non_calcule_sans_chemin_pointe(self):
        from apps.calepinage.services.rapport.annexe_hypotheses import _table_non_calcule

        html = _table_non_calcule([
            ('production.total.p50_kwh', 'Donnée manquante'),
            ('production.base', 'Donnée manquante'),
            ('production.mensuel[]', 'Donnée manquante')])
        for brut in ('production.total', 'production.base', 'production.mensuel', 'p50_kwh'):
            self.assertNotIn(brut, html)

    def test_methode_de_validation_sans_code_de_poste(self):
        from apps.calepinage.services.rapport.validation import html_de_section

        html = html_de_section({'resultat': {}})
        for code in ('thermique', 'ohmique_ac'):
            self.assertNotIn(code, html)
