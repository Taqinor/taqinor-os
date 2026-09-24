"""CALX316 — le manuel du propriétaire, depuis un gabarit société.

Ce qui est prouvé ici :

* SANS gabarit de genre « manuel » déposé, aucun manuel n'est produit — le
  refus NOMME le champ ``gabarit`` et cite le genre attendu ;
* AVEC un gabarit, les variables ``{{cle}}`` de son texte SONT substituées
  par les données système RÉELLEMENT lues (onduleur référencé, nombre de
  chaînes) et AUCUN ``{{...}}`` ne subsiste dans la sortie — une variable
  absente imprime « non renseigné », jamais un texte inventé ;
* une variable HORS de ``VARIABLES_SYSTEME`` fait refuser le document, en la
  NOMMANT (gabarit invalide) ;
* aucun montant : le pare-feu de ``services.rapport.resultat_du_rapport``
  s'applique au résultat lu ;
* en base (CI) : ``GET …/manuel-proprietaire.pdf/`` borné société et
  permission, 400 + champ nommé sans gabarit.

Run (pur, sans base) :
    cd backend/django_core
    python -m pytest apps/calepinage/tests/test_calx316_manuel_proprietaire.py
"""
import copy
import json
import pathlib
import unittest
from types import SimpleNamespace
from unittest import mock

from django.test import tag

from apps.calepinage.services.documents import mise_en_page
from apps.calepinage.services.documents.manuel_proprietaire import (
    CODE_DOCUMENT,
    MESSAGE_AUCUN_GABARIT_MANUEL,
    ManuelRefuse,
    construire_manuel,
    html_de_manuel,
    html_du_manuel,
    rendre_manuel,
    substituer_variables,
    variables_systeme,
)
from apps.calepinage.services.rapport import RapportRefuse

from .test_api_liste import BaseApiCalepinage, url_detail

RACINE_APP = pathlib.Path(__file__).resolve().parents[1]
ECHANTILLON = json.loads(
    (RACINE_APP / 'contract_samples' / 'calepinage_resultat.json')
    .read_text(encoding='utf-8'))

#: Un calepinage NON ENREGISTRÉ, sans société ni client — même patron que
#: ``NU`` dans ``test_calx297_rapport_etude.py``.
NU = SimpleNamespace(company=None, client_id=None, lead_id=None, pk=None,
                     titre='Villa Anfa', resultat=None)
SITE = {'ville': 'Bouskoura', 'adresse': 'Zone industrielle'}
IDENTITE = {'titre_document': 'Manuel du propriétaire', 'projet': 'Villa Anfa',
            'client': 'Mme Bennani', 'produit_le': '23/09/2026'}
STYLES = {'nom_affiche': 'Soleil Atlas', 'logo_url': '',
          'couleur_primaire': '', 'couleur_secondaire': ''}


def resultat():
    return copy.deepcopy(ECHANTILLON['exemple'])


def gabarit(champs):
    return SimpleNamespace(champs=champs, intitule='Manuel standard')


GABARIT_CONSIGNES = gabarit([
    {'code': 'consignes_securite', 'libelle': 'Consignes de sécurité',
     'type': 'texte',
     'texte': ("Couper l'onduleur {{onduleurs}} avant toute intervention. "
               "{{nombre_chaines}} chaîne(s). Contact : "
               "{{installateur_nom}} — {{installateur_telephone}}.")},
    {'code': 'consignes_arret', 'libelle': "Consignes d'arrêt",
     'type': 'texte', 'texte': 'Modules retenus : {{modules}}.'},
    # Un champ SANS texte n'imprime rien — jamais une section vide.
    {'code': 'sans_texte', 'libelle': 'Ignoré', 'type': 'texte', 'texte': ''},
])


def manuel(**options):
    options.setdefault('resultat', resultat())
    options.setdefault('gabarit', GABARIT_CONSIGNES)
    options.setdefault('site', SITE)
    options.setdefault('identite', IDENTITE)
    options.setdefault('styles', STYLES)
    return construire_manuel(NU, **options)


class SansGabaritTest(unittest.TestCase):
    def test_sans_gabarit_aucun_manuel_et_le_message_nomme_le_genre(self):
        with self.assertRaises(ManuelRefuse) as capture:
            construire_manuel(NU, resultat=resultat(), gabarit=None,
                              site=SITE, identite=IDENTITE, styles=STYLES)
        self.assertEqual(capture.exception.champ, 'gabarit')
        self.assertEqual(str(capture.exception),
                         MESSAGE_AUCUN_GABARIT_MANUEL)
        self.assertIn('manuel', str(capture.exception))

    def test_le_refus_est_une_sous_classe_de_rapport_refuse(self):
        # L'aperçu HTML (CALX323) capture (RapportRefuse,) : ManuelRefuse en
        # est une sous-classe, jamais une seconde liste de refus à tenir.
        self.assertTrue(issubclass(ManuelRefuse, RapportRefuse))


class SubstitutionTest(unittest.TestCase):
    def test_une_variable_declaree_est_substituee(self):
        html = substituer_variables('Chaînes : {{nombre_chaines}}.',
                                    {'nombre_chaines': '2'})
        self.assertEqual(html, 'Chaînes : 2.')

    def test_une_variable_sans_valeur_imprime_non_renseigne(self):
        html = substituer_variables('Contact : {{installateur_nom}}.', {})
        self.assertIn('non renseigné', html)
        self.assertNotIn('{{', html)

    def test_une_variable_inconnue_est_refusee_en_la_nommant(self):
        with self.assertRaises(ManuelRefuse) as capture:
            substituer_variables('{{variable_fantome}}', {})
        self.assertEqual(capture.exception.champ, 'champs')
        self.assertIn('variable_fantome', str(capture.exception))

    def test_le_texte_est_echappe_html(self):
        html = substituer_variables('<script>{{modules}}</script>',
                                    {'modules': '<b>24</b>'})
        self.assertNotIn('<script>', html)
        self.assertNotIn('<b>', html)


class VariablesSystemeTest(unittest.TestCase):
    def test_le_nombre_de_chaines_et_l_onduleur_sont_lus_du_resultat(self):
        variables = variables_systeme(NU, resultat=resultat())
        self.assertEqual(variables['nombre_chaines'], '2')
        self.assertIn('ONDULEUR-ESSAI-1', variables['onduleurs'])

    def test_sans_resultat_les_variables_de_resultat_sont_vides(self):
        variables = variables_systeme(NU, resultat=None)
        self.assertEqual(variables['nombre_chaines'], '')
        self.assertEqual(variables['onduleurs'], '')

    def test_sans_societe_les_coordonnees_installateur_sont_vides(self):
        variables = variables_systeme(NU, resultat=resultat())
        self.assertEqual(variables['installateur_nom'], '')
        self.assertEqual(variables['installateur_telephone'], '')


class ConstruireManuelTest(unittest.TestCase):
    def test_avec_gabarit_les_sections_sont_composees_dans_l_ordre(self):
        document = manuel()
        self.assertEqual(document['code'], CODE_DOCUMENT)
        codes = [s['code'] for s in document['sections']]
        # Le champ 'sans_texte' n'a pas de texte : il n'apparaît pas.
        self.assertEqual(codes, ['consignes_securite', 'consignes_arret'])

    def test_les_variables_du_systeme_sont_substituees(self):
        document = manuel()
        securite = document['sections'][0]['texte']
        self.assertIn('ONDULEUR-ESSAI-1', securite)
        self.assertIn('2 chaîne', securite)
        self.assertIn('non renseigné', securite)  # installateur, sans société
        self.assertNotIn('{{', securite)

    def test_une_variable_inconnue_dans_le_gabarit_refuse_tout_le_document(
            self):
        mauvais = gabarit([{'code': 'x', 'libelle': 'X', 'type': 'texte',
                            'texte': '{{variable_qui_n_existe_pas}}'}])
        with self.assertRaises(ManuelRefuse) as capture:
            manuel(gabarit=mauvais)
        self.assertIn('variable_qui_n_existe_pas', str(capture.exception))

    def test_sans_resultat_le_manuel_refuse_en_nommant_resultat(self):
        with self.assertRaises(RapportRefuse) as capture:
            manuel(resultat=None)
        self.assertEqual(capture.exception.champ, 'resultat')

    def test_une_cle_de_cout_est_refusee_a_l_entree(self):
        donnees = resultat()
        donnees['pose']['prix_achat_total'] = 12345
        with self.assertRaises(RapportRefuse) as capture:
            manuel(resultat=donnees)
        self.assertIn('prix_achat', capture.exception.champ)


class MiseEnPageTest(unittest.TestCase):
    def test_aucun_mot_de_montant(self):
        html = html_de_manuel(manuel())
        mots_de_montant = (
            'MAD', 'DH', 'prix', 'coût', 'cout', 'montant', 'remise',
            'marge', 'TTC', 'HT', '€')
        for mot in mots_de_montant:
            self.assertNotIn(mot, html, mot)

    def test_le_titre_et_la_garde_sont_presents(self):
        html = html_de_manuel(manuel())
        self.assertIn('Manuel du propriétaire', html)
        self.assertEqual(html.count('class="page-de-garde"'), 1)

    def test_l_apercu_et_le_pdf_partagent_une_seule_fonction(self):
        self.assertIs(mise_en_page('manuel_proprietaire'), html_du_manuel)


class RenduPartageTest(unittest.TestCase):
    def test_le_pdf_passe_par_la_plomberie_partagee(self):
        options = dict(resultat=resultat(), gabarit=GABARIT_CONSIGNES,
                       site=SITE, identite=IDENTITE, styles=STYLES)
        with mock.patch('core.pdf.render_pdf',
                        return_value=b'%PDF-simule') as rendu:
            octets = rendre_manuel(NU, **options)
        self.assertEqual(octets, b'%PDF-simule')
        self.assertEqual(rendu.call_args.kwargs['html'],
                         html_du_manuel(NU, **options))


@tag('pdf')
class RenduReelTest(unittest.TestCase):
    """WeasyPrint réel — étiqueté ``pdf`` (hors du palier CI — routeur M4)."""

    def setUp(self):
        try:
            import weasyprint  # noqa: F401
        except Exception:  # noqa: BLE001 — bibliothèque native absente
            self.skipTest('WeasyPrint indisponible sur ce poste')

    def test_un_manuel_simule_rend_un_pdf_non_vide(self):
        octets = rendre_manuel(NU, resultat=resultat(),
                               gabarit=GABARIT_CONSIGNES, site=SITE,
                               identite=IDENTITE, styles=STYLES)
        self.assertGreater(len(octets), 0)


PDF = b'%PDF-1.7 manuel simule'


class EndpointManuelEnBaseTest(BaseApiCalepinage):
    """``GET …/manuel-proprietaire.pdf/`` — câblage, société, permission (CI).

    Le rendu WeasyPrint est simulé (``core.pdf.render_pdf`` a ses propres
    essais) : ce qui est vérifié ici, c'est la porte.
    """

    def setUp(self):
        super().setUp()
        from apps.calepinage.models import Calepinage

        from .test_cal171_planche import LAYOUT

        # AUCUN gabarit « manuel » déposé par défaut : le test du refus
        # (``test_sans_gabarit_400_en_nommant_gabarit``) en dépend. Le test
        # « avec gabarit » le DÉPOSE lui-même, sur SA société.
        self.calepinage = Calepinage.objects.create(
            company=self.company, lead_id=self.lead.pk, titre='Villa Anfa',
            roof_layout=LAYOUT, layout_hash='a' * 64, resultat=resultat())
        self.etranger = Calepinage.objects.create(
            company=self.autre, lead_id=7, titre='Chez la voisine',
            roof_layout=LAYOUT, resultat=resultat())

    def _url(self, calepinage):
        return f'{url_detail(calepinage.pk)}manuel-proprietaire.pdf/'

    def _deposer_gabarit(self, company):
        from apps.calepinage.models import GabaritDossierReglementaire

        champ = {
            'code': 'consignes_securite', 'type': 'texte',
            'libelle': 'Consignes de sécurité',
            'texte': 'Chaînes : {{nombre_chaines}}.',
        }
        return GabaritDossierReglementaire.objects.create(
            company=company, pays='ma', code='manuel-standard',
            genre='manuel', intitule='Manuel standard', champs=[champ])

    def test_le_pdf_se_telecharge_borne_societe(self):
        self._deposer_gabarit(self.company)
        with mock.patch('core.pdf.render_pdf', return_value=PDF) as rendu:
            reponse = self.api.get(self._url(self.calepinage))
        self.assertEqual(reponse.status_code, 200)
        self.assertEqual(reponse.content, PDF)
        self.assertEqual(rendu.call_args.kwargs['company'], self.company)

    def test_sans_gabarit_400_en_nommant_gabarit(self):
        reponse = self.api.get(self._url(self.calepinage))
        self.assertEqual(reponse.status_code, 400)
        self.assertIn('gabarit', reponse.data)
        self.assertIn('manuel', reponse.data['gabarit'])

    def test_une_autre_societe_est_introuvable(self):
        reponse = self.api.get(self._url(self.etranger))
        self.assertEqual(reponse.status_code, 404)

    def test_sans_permission_de_lecture_c_est_403(self):
        reponse = self.api_sans.get(self._url(self.calepinage))
        self.assertEqual(reponse.status_code, 403)
