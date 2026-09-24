"""CALX327 — interdire tout mot de montant dans le TEXTE EXTRAIT de chaque
document du module.

Le constat
==========
Les pare-feu existants inspectent les DONNÉES D'ENTRÉE — les CLÉS d'un
``dict`` (``note_calcul.CLES_INTERDITES``/``CLES_INTERDITES_EXACTES``,
``export_tableur.py:67-87``, en-têtes et cellules du tableur) — jamais le
TEXTE RÉELLEMENT IMPRIMÉ. Une chaîne de GABARIT (un champ texte libre, comme
``services/documents/manuel_proprietaire.py`` en lit un depuis
``GabaritDocument.champs``) peut faire entrer un montant SANS AUCUNE clé
fautive : c'est exactement le trou que ce fichier ferme.

Deux paliers, comme CALX328
============================
1. PUR (ci-dessous, ``python -m pytest``, AUCUN WeasyPrint) — la mise en
   page HTML de chaque document est appelée DIRECTEMENT (les mêmes fonctions
   que l'aperçu HTML de CALX323, ``services.documents.MISES_EN_PAGE``, plus
   les équivalents des pièces CAL175 hors de ce registre) et son texte
   VISIBLE (balises retirées) est passé au pare-feu.
2. RÉEL (``@tag('pdf')``, WeasyPrint + PyMuPDF, image de production) —
   les MÊMES documents, RÉELLEMENT rendus en PDF, texte EXTRAIT par PyMuPDF.
   Ce palier existe en plus du premier parce qu'une boîte de marge
   ``@top-center``/``@bottom-left`` (contenu CSS généré,
   ``services/documents/gabarit_document.py``) n'est PAS du texte dans la
   chaîne HTML brute que le palier PUR inspecte — elle ne devient du texte
   qu'après le moteur de mise en page.

La liste des documents COUVERTS n'est PAS écrite en dur
=========================================================
``_codes_pdf_derives()`` REJOUE les deux inventaires DÉCLARATIFS du dépôt —
``views.sorties.inventaire_des_sorties`` (CAL175, les 12 sorties
techniques) et ``services.documents.inventaire_des_documents`` (CALX321, les
9 pièces du lot 6) — et ne garde que les codes de format ``pdf`` rendus PAR
LE SERVEUR. ``RENDEURS_HTML_PURS``/``EXEMPTIONS_DOCUMENTEES`` doivent
COUVRIR cette liste EN ENTIER : un document neuf déclaré demain dans l'un
des deux inventaires, sans entrée ici, fait ÉCHOUER
``test_chaque_code_pdf_derive_est_couvert_ou_exempte_avec_motif`` en le
NOMMANT — il n'est jamais silencieusement sauté.

Deux exemptions de TEXTE, VÉRIFIÉES sur le dépôt réel (pas devinées)
======================================================================
Un jeton de montant NU peut apparaître dans du texte LÉGITIME de ce module,
et le pare-feu le SAIT plutôt que de rougir dessus :

* « marge » — ``services/note_calcul.py`` imprime TOUJOURS
  ``LIBELLE_MARGE['troncon_min_cm']``/``['bande_min_cm']`` (« Marge minimale
  de tronçon (cm) » / « … de bande (cm) », la table des marges GÉOMÉTRIQUES
  du régime de preuve, CAL177 — repris tel quel par la section « preuve » du
  rapport d'étude, ``services/rapport/preuve.py``) — même nuance que le
  commentaire de ``note_calcul.py:55`` sur la clé ``marge`` ;
* « prix » — ``services/documents/presentation_compacte.py``
  ``MENTION_PAS_UN_DEVIS`` imprime EN TOUTES LETTRES, sur ses deux pages,
  que la pièce « ne vaut pas offre de prix » : c'est le DISCLAIMER D5
  lui-même, pas un montant.

Retirer une exemption TEXTE AUJOURD'HUI VÉRIFIÉE la ferait rougir contre un
document parfaitement conforme — retirer une entrée qui ne correspond plus à
rien (le texte source a changé) est signalé par
``test_les_deux_exemptions_de_texte_sont_reellement_presentes``.

Run (structure, pur, sans WeasyPrint) :
    cd backend/django_core
    python -m pytest apps/calepinage/tests/test_calx327_aucun_montant.py -q

Run (avec rendu réel, image prod dotée de WeasyPrint) :
    python manage.py test \
        apps.calepinage.tests.test_calx327_aucun_montant -v2
"""
import copy
import datetime
import json
import pathlib
import re
import unittest
from types import SimpleNamespace

from django.test import tag

from .test_cal171_planche import LAYOUT as LAYOUT_PLANCHE
from .test_cal194_plans import layout_avec_parcelle

RACINE_APP = pathlib.Path(__file__).resolve().parents[1]
ECHANTILLON = json.loads(
    (RACINE_APP / 'contract_samples' / 'calepinage_resultat.json')
    .read_text(encoding='utf-8'))

#: Naïf jamais — même discipline que ``check_naive_datetime.py`` partout
#: dans le module, y compris les essais purs.
MOMENT = datetime.datetime(2026, 9, 23, 10, 0, tzinfo=datetime.timezone.utc)

SITE = {'ville': 'Bouskoura', 'adresse': 'Zone industrielle',
        'source': 'roof_point', 'pin': None, 'outline': None}
IDENTITE = {'titre_document': 'Document', 'projet': 'Villa Anfa',
            'client': 'Mme Bennani', 'produit_le': '23/09/2026'}
STYLES = {'nom_affiche': 'Soleil Atlas', 'logo_url': '',
          'couleur_primaire': '', 'couleur_secondaire': ''}

#: Gabarit « manuel » minimal, deux champs texte — même patron que CALX328
#: (aucun montant dedans : c'est le contrôle négatif du contrôle négatif).
GABARIT_MANUEL = SimpleNamespace(intitule='Manuel standard', champs=[
    {'code': 'consignes_securite', 'libelle': 'Consignes de sécurité',
     'type': 'texte',
     'texte': ("Couper l'onduleur {{onduleurs}} avant toute intervention. "
               "{{nombre_chaines}} chaîne(s).")},
    {'code': 'consignes_arret', 'libelle': "Consignes d'arrêt",
     'type': 'texte', 'texte': 'Modules retenus : {{modules}}.'},
])

#: Écarts prévu/posé, deux pans — même forme que CALX328/CALX318.
ECARTS_ASBUILT = {
    'calepinage': None,
    'source_prevu': 'variante retenue',
    'pans': [
        {'pan': 'Pan Sud', 'prevu': 12, 'pose': 11, 'ecart': -1,
         'ecarts_position': 'Une rangée décalée vers le faîtage',
         'releve_le': '2026-09-19', 'mention': ''},
        {'pan': 'Pan Nord', 'prevu': 6, 'pose': None, 'ecart': None,
         'ecarts_position': '', 'releve_le': None,
         'mention': 'Aucun relevé de terrain saisi pour ce pan.'},
    ],
    'pans_releves': 1,
    'total_prevu': 18,
    'total_pose': 11,
    'ecart_total': -1,
}

#: Matrice 12×24 « plate » — même patron que CALX328/CALX317, une conception
#: sans ombrage n'a pas besoin de valeurs variées pour publier un rapport.
MATRICE_12X24 = [[0.6] * 24 for _ in range(12)]
ROOF_LAYOUT_OMBRAGE = {'shading12x24': MATRICE_12X24, 'zones': []}

#: Un ``roof_layout`` de plan de câblage, REPRODUIT (jamais importé) de
#: ``test_calx310_plan_cablage.LAYOUT``/``AFFECTATION`` : ce fichier-là
#: importe ``apps.calepinage.models`` (donc exige DJANGO_SETTINGS_MODULE),
#: ce qui casserait la collecte ``python -m pytest`` PURE de CE fichier —
#: les valeurs sont recopiées à l'identique, pas réinventées.


def _panneaux_cablage(n):
    return [{'cx': 1.2 + 2.2 * (rang % 4), 'cy': 1.0 + 2.5 * (rang // 4)}
            for rang in range(n)]


LAYOUT_CABLAGE = {
    'version': 2,
    'outline': [[33.5, -7.6], [33.5, -7.5999], [33.5001, -7.5999],
                [33.5001, -7.6]],
    'panelWatt': 720,
    'zones': [{
        'id': 'z1',
        'label': 'Pan Sud',
        'vertices': [[-7.6, 33.5], [-7.5999, 33.5], [-7.5999, 33.5001],
                     [-7.6, 33.5001]],
        'geometry': {'azimuthDeg': 180.0, 'tiltDeg': 15.0, 'count': 12,
                     'origin': [-7.6, 33.5], 'panels': _panneaux_cablage(12)},
    }],
}


def _ligne_cablage(rang, chaine, *, mppt=None, onduleur=1,
                   source='automatique', pan='Pan Sud'):
    return {'module': '%s#%d' % (pan, rang), 'pan': pan, 'chaine': chaine,
            'onduleur': onduleur if chaine is not None else None,
            'mppt': (mppt if mppt is not None else chaine)
            if chaine is not None else None,
            'source': source}


AFFECTATION_CABLAGE = [_ligne_cablage(r, 1) for r in range(1, 7)] + \
    [_ligne_cablage(r, 2) for r in range(7, 13)]


def _resultat():
    return copy.deepcopy(ECHANTILLON['exemple'])


# ── Le pare-feu de TEXTE — jetons entiers, jamais une sous-chaîne ──────────
#
# Le jeu de jetons est CELUI du Done= (« MAD, €, DH, prix, coût, montant,
# marge, remise, TTC, HT ») — la seule différence avec une copie littérale
# est le retrait d'appariement AVEUGLE que les deux exemptions ci-dessus
# neutralisent déjà par retrait de PHRASE, pas par affaiblissement du jeton :
# TOUTE AUTRE apparition de « marge » ou « prix » reste refusée.
MOTS_DE_MONTANT = re.compile(
    r'(?<![\w-])(MAD|DH|prix|co[uû]t|montant|marge|remise|TTC|HT)(?![\w-])'
    r'|€',
    re.IGNORECASE)

_BALISE = re.compile(r'<[^>]+>')
_STYLE = re.compile(r'<style[^>]*>.*?</style>', re.IGNORECASE | re.DOTALL)


def _texte_visible(html):
    """Le texte SANS balise ni feuille de style — la feuille de style porte
    des couleurs et des règles ``@page``, jamais un mot de montant, mais un
    sélecteur CSS mal formé pourrait accidentellement matcher un jeton."""
    return _BALISE.sub(' ', _STYLE.sub(' ', html or ''))


def _exemptions_texte_connu():
    """Les DEUX phrases RÉELLES du dépôt, vérifiées sans montant — importées
    de LEUR SOURCE (jamais recopiées à la main : un changement de wording là
    suit ici automatiquement)."""
    from apps.calepinage.services.documents.presentation_compacte import (
        MENTION_PAS_UN_DEVIS,
    )
    from apps.calepinage.services.note_calcul import LIBELLE_MARGE

    return (
        MENTION_PAS_UN_DEVIS,
        LIBELLE_MARGE['troncon_min_cm'],
        LIBELLE_MARGE['bande_min_cm'],
    )


def _mots_de_montant_dans(texte):
    """Les jetons interdits trouvés dans ``texte``, APRÈS avoir retiré les
    deux phrases connues et vérifiées sans montant (voir le docstring du
    module) — une AUTRE apparition du même mot, ailleurs dans le texte,
    reste détectée."""
    sans_exemption = texte or ''
    for phrase in _exemptions_texte_connu():
        sans_exemption = sans_exemption.replace(phrase, ' ')
    return sorted({m.group(0)
                   for m in MOTS_DE_MONTANT.finditer(sans_exemption)})


# ── La liste des documents à couvrir, DÉRIVÉE des deux inventaires ────────

def _codes_pdf_derives():
    """Les codes de format ``pdf`` rendus PAR LE SERVEUR, déclarés par
    ``inventaire_des_sorties`` (CAL175) ET ``inventaire_des_documents``
    (CALX321) — sur un calepinage MINIMAL : ``code``/``format`` sont
    déclarés pour CHAQUE pièce dans la boucle des deux fonctions, disponible
    ou non ; l'état de disponibilité N'ENTRE PAS dans cette dérivation."""
    from apps.calepinage.services.documents import inventaire_des_documents
    from apps.calepinage.views.sorties import inventaire_des_sorties

    nu = SimpleNamespace(pk=None, company=None, titre='', roof_layout=None,
                         resultat=None, layout_hash='', version_moteur='',
                         roof_image=None)
    sorties = inventaire_des_sorties(nu)['sorties']
    documents = inventaire_des_documents(nu)['documents']
    codes_serveur = {e['code'] for e in sorties
                     if e['format'] == 'pdf' and e['produit_par'] == 'serveur'}
    codes_documents = {d['code'] for d in documents if d['format'] == 'pdf'}
    return codes_serveur | codes_documents


# ── Une fonction HTML PURE par document (aucun WeasyPrint) ─────────────────

def _html_note_calcul():
    from apps.calepinage.services.note_calcul import (
        construire_note_calcul, html_de_note_calcul,
    )

    note = construire_note_calcul(_resultat(), site=SITE, identite=IDENTITE,
                                  styles=STYLES)
    return html_de_note_calcul(note)


def _html_rapport_etude():
    from apps.calepinage.services.rapport import html_du_rapport

    nu = SimpleNamespace(company=None, client_id=None, lead_id=None,
                         titre='Villa Anfa', resultat=None, pk=None)
    return html_du_rapport(nu, resultat=_resultat(), site=SITE,
                           identite=IDENTITE, styles=STYLES)


def _html_rapport_ombrage():
    from apps.calepinage.services.rapport_ombrage import (
        html_du_rapport_ombrage,
    )

    nu = SimpleNamespace(company=None, client_id=None, lead_id=None,
                         titre='Villa Anfa', pk=None,
                         roof_layout=ROOF_LAYOUT_OMBRAGE)
    return html_du_rapport_ombrage(nu, resultat=_resultat(), site=SITE,
                                   identite=IDENTITE, styles=STYLES, etat={})


def _html_document_asbuilt():
    from apps.calepinage.services.documents.document_asbuilt import (
        html_du_document_asbuilt,
    )

    nu = SimpleNamespace(company=None, client_id=None, lead_id=None,
                         titre='Villa Anfa', pk=None, layout_hash='',
                         version_moteur='')
    return html_du_document_asbuilt(
        nu, ecarts=ECARTS_ASBUILT, photos=[], svg_planche='', site=SITE,
        identite=IDENTITE, styles=STYLES)


def _html_manuel_proprietaire(gabarit=GABARIT_MANUEL):
    from apps.calepinage.services.documents.manuel_proprietaire import (
        html_du_manuel,
    )

    nu = SimpleNamespace(company=None, client_id=None, lead_id=None,
                         titre='Villa Anfa', pk=None, resultat=None)
    return html_du_manuel(nu, resultat=_resultat(), gabarit=gabarit,
                          site=SITE, identite=IDENTITE, styles=STYLES)


def _html_presentation_compacte():
    from apps.calepinage.services.documents.presentation_compacte import (
        html_de_presentation_compacte,
    )

    nu = SimpleNamespace(company=None, pk=None, titre='Villa Anfa',
                         resultat=None, layout_hash='', version_moteur='')
    return html_de_presentation_compacte(
        nu, resultat=_resultat(), roof_layout=LAYOUT_PLANCHE, svg_planche='',
        styles=STYLES)


def _html_plan_cablage():
    from apps.calepinage.services.documents.plan_cablage import (
        html_du_plan_cablage,
    )

    nu = SimpleNamespace(pk=None, company=None, titre='Villa Anfa',
                         roof_layout=LAYOUT_CABLAGE, resultat=None,
                         layout_hash='ab' * 32,
                         version_moteur='calepinage-1.0.0')
    return html_du_plan_cablage(nu, moment=MOMENT,
                                affectation=AFFECTATION_CABLAGE)


def _html_planche():
    from apps.calepinage.services.planche import (
        html_de_planche, rendre_planche_svg,
    )

    nu = SimpleNamespace(pk=None, company=None, titre='Villa Anfa',
                         roof_layout=LAYOUT_PLANCHE)
    return html_de_planche(
        rendre_planche_svg(nu, moment=MOMENT, titre='Villa Anfa'))


def _html_plan_pose():
    from apps.calepinage.services.planche import (
        html_de_planche, rendre_plan_pose_svg,
    )

    nu = SimpleNamespace(pk=None, company=None, titre='Villa Anfa',
                         roof_layout=LAYOUT_PLANCHE, resultat=_resultat())
    return html_de_planche(
        rendre_plan_pose_svg(nu, moment=MOMENT, titre='Villa Anfa'))


def _html_plan_toiture():
    from apps.calepinage.services.planche import (
        CONTENU_TOITURE, html_de_planche, rendre_plan_svg,
    )

    nu = SimpleNamespace(pk=None, company=None, titre='Villa Anfa',
                         roof_layout=LAYOUT_PLANCHE)
    return html_de_planche(
        rendre_plan_svg(nu, contenu=CONTENU_TOITURE, moment=MOMENT,
                        titre='Villa Anfa'))


def _html_plan_masse():
    from apps.calepinage.services.planche import (
        CONTENU_MASSE, html_de_planche, rendre_plan_svg,
    )

    nu = SimpleNamespace(pk=None, company=None, titre='Villa Anfa',
                         roof_layout=layout_avec_parcelle())
    return html_de_planche(
        rendre_plan_svg(nu, contenu=CONTENU_MASSE, moment=MOMENT,
                        titre='Villa Anfa'))


#: ``code (de l'inventaire) -> fonction HTML PURE`` — la couverture réelle.
RENDEURS_HTML_PURS = {
    'note_calcul_pdf': _html_note_calcul,
    'rapport_etude': _html_rapport_etude,
    'rapport_ombrage': _html_rapport_ombrage,
    'document_asbuilt': _html_document_asbuilt,
    'manuel_proprietaire': _html_manuel_proprietaire,
    'presentation_compacte': _html_presentation_compacte,
    'plan_cablage': _html_plan_cablage,
    'planche_pdf': _html_planche,
    'plan_pose_pdf': _html_plan_pose,
    'plan_toiture_pdf': _html_plan_toiture,
    'plan_masse_pdf': _html_plan_masse,
}

#: Deux codes DÉCLARÉS par les inventaires mais HORS de portée d'une mise en
#: page HTML unique — chacun avec un motif VÉRIFIÉ, jamais un silence.
EXEMPTIONS_DOCUMENTEES = {
    'pack_technique': (
        "fusion d'OCTETS de 7 pièces déjà TOUTES couvertes ci-dessus "
        "(pack_technique.SPEC_PIECES : planche, note_calcul, plan_toiture, "
        "plan_masse, rapport_etude, plan_cablage, rapport_ombrage) — "
        "fusionner_pdf (XGED10) recopie des octets, il n'introduit aucun "
        "texte neuf ; vérifier chaque pièce couvre donc le dossier fusionné."
    ),
    'dossier_fin_chantier': (
        "aucune mise en page n'existe encore pour cette pièce — "
        "services/documents/__init__.py le dit lui-même TOUJOURS "
        "indisponible aujourd'hui (CALX321, aucune preuve terrain déposée "
        "n'est honnêtement possible tant que la porte n'existe pas) : "
        "crochet laissé pour la phase 2."
    ),
}


class DerivationEtCouvertureTest(unittest.TestCase):
    """PUR — la liste des documents à vérifier est DÉRIVÉE des deux
    inventaires (CAL175 + CALX321), jamais écrite en dur."""

    def test_chaque_code_pdf_derive_est_couvert_ou_exempte_avec_motif(self):
        codes = _codes_pdf_derives()
        couverts = set(RENDEURS_HTML_PURS)
        exemptes = set(EXEMPTIONS_DOCUMENTEES)
        manquants = codes - couverts - exemptes
        self.assertEqual(
            manquants, set(),
            'document(s) de la liste DÉRIVÉE sans vérification NI '
            'exemption documentée — %s' % sorted(manquants))

    def test_les_exemptions_correspondent_encore_a_un_code_reel(self):
        # Une exemption qui ne matche plus RIEN serait un filtre mort —
        # cette égalité doit être retirée avec elle, jamais laissée à
        # protéger dans le vide.
        codes = _codes_pdf_derives()
        for code in EXEMPTIONS_DOCUMENTEES:
            self.assertIn(
                code, codes,
                "exemption « %s » obsolète : ce code n'est plus déclaré "
                "par aucun inventaire — la retirer." % code)

    def test_chaque_exemption_porte_un_motif_non_vide(self):
        for code, motif in EXEMPTIONS_DOCUMENTEES.items():
            with self.subTest(document=code):
                self.assertTrue(motif.strip())

    def test_les_deux_inventaires_sont_bien_distincts(self):
        # Sanity du docstring : CAL175 (5 pièces PDF serveur + le pack) et
        # CALX321 (7 pièces PDF) ne se recouvrent QUE sur aucun code — un
        # même code déclaré deux fois signalerait une confusion des deux
        # familles.
        self.assertEqual(
            _codes_pdf_derives(),
            {'planche_pdf', 'plan_pose_pdf', 'plan_toiture_pdf',
             'plan_masse_pdf', 'note_calcul_pdf', 'pack_technique',
             'rapport_etude', 'rapport_ombrage', 'plan_cablage',
             'manuel_proprietaire', 'document_asbuilt',
             'dossier_fin_chantier', 'presentation_compacte'})


class AucunMontantDansLeHtmlTest(unittest.TestCase):
    """PUR — SANS rendu PDF (aucun WeasyPrint) : la mise en page HTML de
    CHAQUE document couvert ne porte aucun mot de montant en jeton entier."""

    def test_aucun_document_ne_porte_de_montant_dans_son_html(self):
        for code, rendeur in RENDEURS_HTML_PURS.items():
            with self.subTest(document=code):
                html = rendeur()
                self.assertTrue(html and html.strip(),
                                '« %s » : mise en page vide' % code)
                trouves = _mots_de_montant_dans(_texte_visible(html))
                self.assertEqual(
                    trouves, [],
                    '« %s » : mot(s) de montant trouvé(s) dans le texte '
                    'imprimé — %s' % (code, trouves))

    def test_les_deux_exemptions_de_texte_sont_reellement_presentes(self):
        # Une exemption qui ne matche plus RIEN serait, ici aussi, un
        # filtre mort : elle doit rester VÉRIFIÉE contre le texte réel.
        from apps.calepinage.services.documents.presentation_compacte import (
            MENTION_PAS_UN_DEVIS,
        )
        from apps.calepinage.services.note_calcul import LIBELLE_MARGE

        texte_presentation = _texte_visible(RENDEURS_HTML_PURS[
            'presentation_compacte']())
        texte_note = _texte_visible(RENDEURS_HTML_PURS['note_calcul_pdf']())
        self.assertIn(MENTION_PAS_UN_DEVIS, texte_presentation)
        self.assertIn(LIBELLE_MARGE['troncon_min_cm'], texte_note)


class MontantInjecteParUnGabaritEstDetecteTest(unittest.TestCase):
    """L'ESSAI NÉGATIF exigé par le Done= : un montant entré par un GABARIT
    (texte LIBRE, AUCUNE clé fautive) est détecté — la raison d'être de
    CALX327, que note_calcul/export_tableur (pare-feux sur les CLÉS de
    données) ne peuvent pas voir."""

    def test_un_montant_dans_un_champ_de_gabarit_est_detecte(self):
        gabarit_piege = SimpleNamespace(intitule='Manuel standard', champs=[
            {'code': 'consignes_paiement', 'libelle': 'Consignes',
             'type': 'texte',
             'texte': ('Solde restant dû à la mise en service : 3 200 MAD '
                       'TTC.')},
        ])
        html = _html_manuel_proprietaire(gabarit=gabarit_piege)
        trouves = _mots_de_montant_dans(_texte_visible(html))
        self.assertTrue(
            trouves, "un montant injecté par un CHAMP DE GABARIT (texte "
            "libre) doit être détecté — aucune clé de donnée n'est fautive "
            "ici, seul le TEXTE le révèle.")
        self.assertIn('MAD', trouves)
        self.assertIn('TTC', trouves)

    def test_un_gabarit_sans_montant_reste_muet(self):
        # Contrôle négatif DU contrôle négatif : la MÊME construction, sans
        # montant, ne déclenche rien — la garde ne fauche pas à l'aveugle.
        html = _html_manuel_proprietaire()
        self.assertEqual(_mots_de_montant_dans(_texte_visible(html)), [])


@tag('pdf')
class AucunMontantDansLePdfReelTest(unittest.TestCase):
    """RÉEL — WeasyPrint + PyMuPDF (hors du palier CI léger, image de
    production). Reprend les MÊMES documents que le palier PUR ci-dessus,
    depuis le PDF RÉELLEMENT rendu et son texte EXTRAIT."""

    def setUp(self):
        try:
            import fitz  # noqa: F401
            import weasyprint  # noqa: F401
        except Exception:  # noqa: BLE001 — bibliothèques natives absentes
            self.skipTest('WeasyPrint ou PyMuPDF indisponible sur ce poste')

    def _octets_par_code(self):
        from apps.calepinage.services import note_calcul as _note_calcul
        from apps.calepinage.services import planche as _planche
        from apps.calepinage.services import rapport_ombrage as _ombrage
        from apps.calepinage.services.documents import (
            document_asbuilt as _asbuilt,
        )
        from apps.calepinage.services.documents import (
            manuel_proprietaire as _manuel,
        )
        from apps.calepinage.services.documents import (
            plan_cablage as _cablage,
        )
        from apps.calepinage.services.documents import (
            presentation_compacte as _presentation,
        )
        from apps.calepinage.services.rapport import rendre_rapport

        nu_note = SimpleNamespace(company=None, pk=None, titre='Villa Anfa',
                                  resultat=_resultat())
        nu_rapport = SimpleNamespace(company=None, client_id=None,
                                     lead_id=None, titre='Villa Anfa',
                                     resultat=None, pk=None)
        nu_ombrage = SimpleNamespace(company=None, client_id=None,
                                     lead_id=None, titre='Villa Anfa', pk=None,
                                     roof_layout=ROOF_LAYOUT_OMBRAGE)
        nu_asbuilt = SimpleNamespace(company=None, client_id=None,
                                     lead_id=None, titre='Villa Anfa', pk=None,
                                     layout_hash='', version_moteur='')
        nu_manuel = SimpleNamespace(company=None, client_id=None,
                                    lead_id=None, titre='Villa Anfa', pk=None,
                                    resultat=None)
        nu_presentation = SimpleNamespace(company=None, pk=None,
                                          titre='Villa Anfa', resultat=None,
                                          layout_hash='', version_moteur='')
        nu_cablage = SimpleNamespace(pk=None, company=None,
                                     titre='Villa Anfa',
                                     roof_layout=LAYOUT_CABLAGE, resultat=None,
                                     layout_hash='ab' * 32,
                                     version_moteur='calepinage-1.0.0')
        nu_planche = SimpleNamespace(pk=None, company=None,
                                     titre='Villa Anfa',
                                     roof_layout=LAYOUT_PLANCHE)
        nu_pose = SimpleNamespace(pk=None, company=None, titre='Villa Anfa',
                                  roof_layout=LAYOUT_PLANCHE,
                                  resultat=_resultat())
        nu_masse = SimpleNamespace(pk=None, company=None, titre='Villa Anfa',
                                   roof_layout=layout_avec_parcelle())

        return {
            'note_calcul_pdf': _note_calcul.rendre_note_calcul(
                nu_note, site=SITE, identite=IDENTITE, styles=STYLES),
            'rapport_etude': rendre_rapport(
                nu_rapport, resultat=_resultat(), site=SITE,
                identite=IDENTITE, styles=STYLES),
            'rapport_ombrage': _ombrage.rendre_rapport_ombrage(
                nu_ombrage, resultat=_resultat(), site=SITE,
                identite=IDENTITE, styles=STYLES, etat={}),
            'document_asbuilt': _asbuilt.rendre_document_asbuilt(
                nu_asbuilt, ecarts=ECARTS_ASBUILT, photos=[], svg_planche='',
                site=SITE, identite=IDENTITE, styles=STYLES),
            'manuel_proprietaire': _manuel.rendre_manuel(
                nu_manuel, resultat=_resultat(), gabarit=GABARIT_MANUEL,
                site=SITE, identite=IDENTITE, styles=STYLES),
            'presentation_compacte':
                _presentation.rendre_presentation_compacte(
                    nu_presentation, resultat=_resultat(),
                    roof_layout=LAYOUT_PLANCHE, svg_planche='',
                    styles=STYLES),
            'plan_cablage': _cablage.rendre_plan_cablage_pdf(
                nu_cablage, moment=MOMENT, affectation=AFFECTATION_CABLAGE),
            'planche_pdf': _planche.rendre_planche_pdf(
                nu_planche, moment=MOMENT, titre='Villa Anfa'),
            'plan_pose_pdf': _planche.rendre_plan_pose_pdf(
                nu_pose, moment=MOMENT, titre='Villa Anfa'),
            'plan_toiture_pdf': _planche.rendre_plan_pdf(
                nu_planche, contenu=_planche.CONTENU_TOITURE, moment=MOMENT,
                titre='Villa Anfa'),
            'plan_masse_pdf': _planche.rendre_plan_pdf(
                nu_masse, contenu=_planche.CONTENU_MASSE, moment=MOMENT,
                titre='Villa Anfa'),
        }

    def test_aucun_montant_dans_le_texte_extrait_par_pymupdf(self):
        import fitz

        for code, octets in self._octets_par_code().items():
            with self.subTest(document=code):
                self.assertTrue(octets, '« %s » : PDF vide' % code)
                document = fitz.open(stream=octets, filetype='pdf')
                try:
                    texte = ''.join(page.get_text() for page in document)
                finally:
                    document.close()
                trouves = _mots_de_montant_dans(texte)
                self.assertEqual(
                    trouves, [],
                    '« %s » : mot(s) de montant trouvé(s) dans le PDF '
                    'RÉELLEMENT rendu — %s' % (code, trouves))


if __name__ == '__main__':  # pragma: no cover
    unittest.main()
