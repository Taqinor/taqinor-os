"""L-VAR (ordre fondateur, 24/08/2026) — le choix avec/sans batterie n'engage
QUE la signature ; le téléchargement, lui, reste libre.

Le scénario vécu : un devis « auto » composé avec les DEUX options, le client
coche « avec batterie » sur sa page publique, et le PDF téléchargé ne montre
plus QUE cette option. Le fondateur veut l'inverse : la signature enregistre le
choix (``Devis.option_acceptee``, inchangé), et le client peut toujours
télécharger le devis COMPLET — avec un petit sélecteur au-dessus du bouton de
téléchargement pour choisir la version.

Couvert ici :
  (a) moteur — ``variante_option`` ('sans'|'avec'|'les_deux') rend le bon
      sous-ensemble, 'les_deux' rend le document complet, une valeur invalide
      (ou absente) retombe sur le document du commercial ;
  (b) PDF RÉEL — extraction de texte : chaque variante imprime (ou n'imprime
      pas) la batterie, avec un témoin positif ;
  (c) la variante NE PEUT PAS élargir un devis mono-option (jamais une option
      que le devis ne livre pas) ;
  (d) l'ACCEPTATION ne rétrécit plus rien : après signature « avec batterie »,
      le PDF public par défaut reste complet ;
  (e) la vue publique — paramètre whitelisté, dégradation anticopie
      (kit agrégé + filigrane) INCHANGÉE sur les 3 variantes, 404 quand
      ``sections['pdf'] = False`` sur les 3 variantes ;
  (f) clés MinIO distinctes par variante (aucune ne peut écraser l'autre) et
      aucune persistance sur ``devis.fichier_pdf`` ;
  (g) l'override suit la SERVABILITÉ PHYSIQUE des lignes, plus le scénario
      stocké (ordre fondateur du 24/08/2026) : un devis rétréci par la resync
      3D (scénario mono, lignes réseau + hybride + batterie) redevient
      téléchargeable en document COMPLET via ``?variante=les_deux``, tandis que
      l'artefact PV86 (deux onduleurs, aucun scénario) reste mono-option.

Run:
    docker compose exec django_core python manage.py test \
        apps.ventes.tests.test_l_var_variante_pdf_publique -v 2
"""
import uuid
from decimal import Decimal
from unittest.mock import patch

from django.test import Client as DjangoClient, TestCase, tag
from django.urls import reverse

from apps.stock.models import Produit
from apps.ventes.models import Devis, LigneDevis, ShareLink
from apps.ventes.quote_engine.builder import (
    build_quote_data, clean_pdf_options, _pdf_key,
)

from .test_l_niv_niveau import (
    add_kit_lines, make_client, make_company, make_devis, make_user,
)

SCENARIO_LES_DEUX = 'Les deux (Sans + Avec)'
DESIGNATION_BATTERIE = 'Batterie lithium Deye 5kWh'
DESIGNATION_HYBRIDE = 'Onduleur hybride Deye 8kW'
DESIGNATION_RESEAU = 'Onduleur réseau Deye 8kW'


def _add_ligne(devis, designation, qty, pu):
    produit = Produit.objects.create(
        company=devis.company, nom=designation,
        sku=f'{uuid.uuid4().hex[:10]}',
        prix_vente=Decimal(pu), prix_achat=Decimal('1'), quantite_stock=9)
    LigneDevis.objects.create(
        devis=devis, produit=produit, designation=designation,
        quantite=Decimal(qty), prix_unitaire=Decimal(pu),
        remise=Decimal('0'))
    return devis


def _designations(items):
    return {(it.get('designation') or '') for it in (items or [])}


class _Base(TestCase):
    """Un devis à DEUX VRAIES options, déclarées comme le fait le « devis
    auto » (U2 : ``etude_params['scenario'] = 'Les deux (Sans + Avec)'``)."""

    def setUp(self):
        self.company = make_company(f'lvar-{uuid.uuid4().hex[:8]}')
        self.user = make_user(self.company)
        self.client_obj = make_client(self.company)
        # make_devis pose déjà l'onduleur RÉSEAU + les panneaux.
        self.devis = make_devis(
            self.company, self.user, self.client_obj,
            f'DEV-LVAR-{uuid.uuid4().hex[:4]}')
        _add_ligne(self.devis, DESIGNATION_HYBRIDE, '1', '16000')
        _add_ligne(self.devis, DESIGNATION_BATTERIE, '1', '22000')
        add_kit_lines(self.devis)
        self.devis.etude_params = {'scenario': SCENARIO_LES_DEUX}
        self.devis.save(update_fields=['etude_params'])

    def _data(self, variante=None, **extra):
        raw = dict(extra)
        if variante is not None:
            raw['variante_option'] = variante
        return build_quote_data(self.devis, clean_pdf_options(raw))


# ═══════════════════════════════════════════════════════════════════════════
# (a) — le moteur rend le bon sous-ensemble
# ═══════════════════════════════════════════════════════════════════════════

class TestMoteurVariante(_Base):
    def test_defaut_est_le_document_complet_du_commercial(self):
        """Aucune variante demandée = comportement historique, byte pour
        byte : le scénario stocké par le commercial fait foi."""
        self.assertIsNone(clean_pdf_options({})['variante_option'])
        data = self._data()
        self.assertEqual(data['nb_options'], 2)
        self.assertEqual(data['scenario'], SCENARIO_LES_DEUX)

    def test_variante_sans_rend_uniquement_l_option_sans_batterie(self):
        data = self._data('sans')
        self.assertEqual(data['scenario'], 'Sans batterie')
        self.assertEqual(data['nb_options'], 1)
        noms = _designations(data['sans_items'])
        self.assertIn(DESIGNATION_RESEAU, noms)
        self.assertNotIn(DESIGNATION_BATTERIE, noms)
        self.assertNotIn(DESIGNATION_HYBRIDE, noms)

    def test_variante_avec_rend_uniquement_l_option_avec_batterie(self):
        data = self._data('avec')
        self.assertEqual(data['scenario'], 'Avec batterie')
        self.assertEqual(data['nb_options'], 1)
        noms = _designations(data['avec_items'])
        self.assertIn(DESIGNATION_BATTERIE, noms)
        self.assertIn(DESIGNATION_HYBRIDE, noms)
        self.assertNotIn(DESIGNATION_RESEAU, noms)

    def test_variante_les_deux_est_le_document_complet(self):
        complet, deux = self._data(), self._data('les_deux')
        self.assertEqual(deux['nb_options'], 2)
        self.assertEqual(deux['scenario'], SCENARIO_LES_DEUX)
        for cle in ('totaux_sans', 'totaux_avec', 'display_total'):
            self.assertEqual(complet[cle], deux[cle], cle)

    def test_valeur_invalide_retombe_sur_le_defaut_sur(self):
        """Un paramètre bricolé ne peut RIEN faire d'autre que le défaut."""
        for brut in ('SANS', 'avec_batterie', 'les deux', '', 'null', 42,
                     None, {'x': 1}):
            opts = clean_pdf_options({'variante_option': brut})
            self.assertIsNone(opts['variante_option'], repr(brut))
            self.assertEqual(
                build_quote_data(self.devis, opts)['nb_options'], 2)

    def test_les_totaux_de_chaque_variante_sont_ceux_du_moteur(self):
        """Zéro chiffre inventé : la variante ne recalcule aucun montant, elle
        choisit quelle option est rendue."""
        complet = self._data()
        self.assertEqual(self._data('sans')['totaux_sans'],
                         complet['totaux_sans'])
        self.assertEqual(self._data('avec')['totaux_avec'],
                         complet['totaux_avec'])


# ═══════════════════════════════════════════════════════════════════════════
# (c) — une variante n'invente jamais une option absente
# ═══════════════════════════════════════════════════════════════════════════

class TestMonoOptionNonElargie(TestCase):
    def setUp(self):
        self.company = make_company(f'lvarmono-{uuid.uuid4().hex[:8]}')
        self.user = make_user(self.company)
        self.client_obj = make_client(self.company)
        # Devis SANS batterie ni hybride : une seule option possible.
        self.devis = make_devis(
            self.company, self.user, self.client_obj,
            f'DEV-LVARM-{uuid.uuid4().hex[:4]}')
        self.devis.etude_params = {'scenario': 'Sans batterie'}
        self.devis.save(update_fields=['etude_params'])

    def test_variante_avec_ignoree_sur_un_devis_sans_batterie(self):
        for variante in ('avec', 'les_deux'):
            data = build_quote_data(
                self.devis,
                clean_pdf_options({'variante_option': variante}))
            self.assertEqual(data['nb_options'], 1, variante)
            self.assertEqual(data['scenario'], 'Sans batterie', variante)
            self.assertNotIn(
                DESIGNATION_BATTERIE, _designations(data['all_items']),
                'une variante ne doit JAMAIS faire apparaître une option que '
                'le devis ne porte pas')


# ═══════════════════════════════════════════════════════════════════════════
# (g) — L-VAR élargi (ordre fondateur 24/08/2026) : l'override suit la
#       SERVABILITÉ PHYSIQUE, plus le scénario stocké
# ═══════════════════════════════════════════════════════════════════════════

class TestVarianteSurDevisRetreciParResync(_Base):
    """Le devis de production DEV-202608-0023 : la resynchronisation 3D a
    rétréci ``etude_params['scenario']`` à « Avec batterie » alors que les
    LIGNES portent toujours réseau + hybride + batterie. L'ancienne garde
    (``scenario == 'Les deux'``) se neutralisait donc exactement là où le
    client avait besoin de choisir."""

    def setUp(self):
        super().setUp()
        self.devis.etude_params = {'scenario': 'Avec batterie'}
        self.devis.save(update_fields=['etude_params'])

    def test_sans_variante_le_document_du_commercial_est_inchange(self):
        """Aucune régression : le défaut reste ce que le commercial a composé
        (mono-option « Avec batterie »)."""
        data = self._data()
        self.assertEqual(data['scenario'], 'Avec batterie')
        self.assertEqual(data['nb_options'], 1)

    def test_variante_sans_rend_l_option_sans_batterie(self):
        data = self._data('sans')
        self.assertEqual(data['scenario'], 'Sans batterie')
        self.assertEqual(data['nb_options'], 1)
        noms = _designations(data['sans_items'])
        self.assertIn(DESIGNATION_RESEAU, noms)
        self.assertNotIn(DESIGNATION_BATTERIE, noms)

    def test_variante_les_deux_rend_le_document_complet(self):
        """Le cœur de l'ordre fondateur : « le téléchargement est TOUJOURS
        complet par défaut » — même quand le scénario stocké a été rétréci."""
        data = self._data('les_deux')
        self.assertEqual(data['scenario'], SCENARIO_LES_DEUX)
        self.assertEqual(data['nb_options'], 2)
        self.assertIn(DESIGNATION_RESEAU, _designations(data['sans_items']))
        self.assertIn(DESIGNATION_BATTERIE, _designations(data['avec_items']))

    def test_les_totaux_ne_sont_jamais_recalcules(self):
        """Zéro chiffre inventé : chaque variante sert les totaux du moteur."""
        complet = self._data('les_deux')
        self.assertEqual(self._data('sans')['totaux_sans'],
                         complet['totaux_sans'])
        self.assertEqual(self._data('avec')['totaux_avec'],
                         complet['totaux_avec'])

    def test_le_moteur_ne_change_aucun_statut(self):
        """Règle #4 — élargir la variante ne touche toujours à rien."""
        avant = (self.devis.statut, self.devis.option_acceptee,
                 self.devis.etude_params)
        for valeur in ('sans', 'avec', 'les_deux'):
            self._data(valeur)
        self.devis.refresh_from_db()
        self.assertEqual(
            (self.devis.statut, self.devis.option_acceptee,
             self.devis.etude_params), avant)


class TestArtefactDeuxOnduleursNonElargi(TestCase):
    """PV86 — deux onduleurs en lignes NON optionnelles et AUCUN scénario
    stocké : c'est un ÉTAT DE DONNÉES, pas une alternative commerciale. Le
    repli l'a ramené à UNE présentation ; la variante ne doit pas ressusciter
    les deux options (ni le prix fantôme que PV86 a banni)."""

    def setUp(self):
        self.company = make_company(f'lvarart-{uuid.uuid4().hex[:8]}')
        self.user = make_user(self.company)
        self.client_obj = make_client(self.company)
        self.devis = make_devis(
            self.company, self.user, self.client_obj,
            f'DEV-LVARA-{uuid.uuid4().hex[:4]}')
        _add_ligne(self.devis, DESIGNATION_HYBRIDE, '1', '16000')
        _add_ligne(self.devis, DESIGNATION_BATTERIE, '1', '22000')
        # AUCUN scénario stocké — c'est ce qui fait l'artefact.
        self.devis.etude_params = {}
        self.devis.save(update_fields=['etude_params'])

    def test_aucune_variante_ne_reouvre_les_deux_options(self):
        reference = build_quote_data(self.devis, clean_pdf_options({}))
        self.assertEqual(reference['nb_options'], 1)
        for valeur in ('sans', 'avec', 'les_deux'):
            data = build_quote_data(
                self.devis, clean_pdf_options({'variante_option': valeur}))
            self.assertEqual(data['nb_options'], 1, valeur)
            self.assertEqual(data['scenario'], reference['scenario'], valeur)
            self.assertEqual(data['display_total'],
                             reference['display_total'], valeur)


# ═══════════════════════════════════════════════════════════════════════════
# (b) + (f) — LE PDF RÉEL et ses clés de stockage
# ═══════════════════════════════════════════════════════════════════════════

@tag('pdf')
class TestPdfReelParVariante(_Base):
    def _rendu(self, variante=None, standard=False):
        """(texte du PDF, clé MinIO) par le chemin COMPLET."""
        import fitz
        from apps.ventes.quote_engine import generate_premium_devis_pdf
        raw = {}
        if variante is not None:
            raw['variante_option'] = variante
        opts = clean_pdf_options(raw)
        if standard:
            opts['kit_agrege'] = True
            opts['watermark'] = True
        with patch('apps.ventes.quote_engine.builder._ensure_pdf_bucket'), \
                patch('apps.ventes.utils.pdf._upload_pdf') as upload:
            key = generate_premium_devis_pdf(
                self.devis.id, opts, persist=False)
        pdf_bytes = upload.call_args[0][0]
        doc = fitz.open(stream=pdf_bytes, filetype='pdf')
        return '\n'.join(p.get_text() for p in doc), key

    #: Fragment DISTINCTIF de la ligne batterie — « batterie » seul ne prouve
    #: rien (l'étiquette « Sans batterie » le contient déjà).
    FRAGMENT_BATTERIE = 'lithium'

    def test_temoin_positif_le_document_complet_liste_bien_la_batterie(self):
        texte, _ = self._rendu()
        self.assertIn(self.FRAGMENT_BATTERIE, texte.lower(),
                      "témoin positif : sans lui, l'absence constatée plus "
                      "bas ne prouverait rien")

    def test_variante_sans_n_imprime_pas_la_ligne_batterie(self):
        texte, _ = self._rendu('sans')
        self.assertNotIn(self.FRAGMENT_BATTERIE, texte.lower())

    def test_variante_avec_imprime_la_ligne_batterie(self):
        texte, _ = self._rendu('avec')
        self.assertIn(self.FRAGMENT_BATTERIE, texte.lower())

    def test_cles_minio_distinctes_par_variante(self):
        cles = {v: self._rendu(v)[1]
                for v in (None, 'sans', 'avec', 'les_deux')}
        self.assertEqual(len(set(cles.values())), 4, cles)
        # La clé historique (aucune variante) est inchangée.
        self.assertEqual(cles[None], _pdf_key(self.devis))

    def test_une_variante_n_est_jamais_persistee_sur_le_devis(self):
        """Le bouton interne « Télécharger » doit toujours pointer sur le
        document COMPLET du commercial."""
        from apps.ventes.quote_engine import generate_premium_devis_pdf
        avant = self.devis.fichier_pdf
        with patch('apps.ventes.quote_engine.builder._ensure_pdf_bucket'), \
                patch('apps.ventes.utils.pdf._upload_pdf'):
            generate_premium_devis_pdf(
                self.devis.id,
                clean_pdf_options({'variante_option': 'avec'}), persist=True)
        self.devis.refresh_from_db()
        self.assertEqual(self.devis.fichier_pdf, avant)


# ═══════════════════════════════════════════════════════════════════════════
# (e) — la vue publique : whitelist, anticopie, section « pdf »
# ═══════════════════════════════════════════════════════════════════════════

class TestVuePubliqueVariante(_Base):
    def _link(self, niveau=ShareLink.NIVEAU_CONFIANCE, **extra):
        return ShareLink.objects.create(
            company=self.company, devis=self.devis,
            token=str(uuid.uuid4()), niveau=niveau, **extra)

    @patch('apps.ventes.public_views.download_pdf', return_value=b'%PDF-fake')
    @patch('apps.ventes.public_views.generate_premium_devis_pdf',
           return_value='k')
    def _opts_servies(self, link, query, mock_gen, mock_dl):
        url = reverse('public-proposal-pdf', args=[link.token])
        resp = DjangoClient().get(url + query)
        self.assertEqual(resp.status_code, 200, resp.content[:200])
        return mock_gen.call_args[0][1]

    def test_chaque_variante_est_transmise_au_moteur(self):
        link = self._link()
        for valeur in ('sans', 'avec', 'les_deux'):
            opts = self._opts_servies(link, f'?variante={valeur}')
            self.assertEqual(opts['variante_option'], valeur)

    def test_parametre_invalide_ou_absent_donne_le_document_complet(self):
        link = self._link()
        for query in ('', '?variante=', '?variante=bidon',
                      '?variante=avec_batterie'):
            opts = self._opts_servies(link, query)
            self.assertIsNone(opts['variante_option'], query)

    def test_degradation_anticopie_identique_sur_les_trois_variantes(self):
        """Le client ne peut pas contourner le niveau « standard » par un
        paramètre : filigrane + kit agrégé restent posés SERVEUR."""
        link = self._link(niveau=ShareLink.NIVEAU_STANDARD)
        for valeur in ('sans', 'avec', 'les_deux'):
            opts = self._opts_servies(link, f'?variante={valeur}')
            self.assertTrue(opts.get('kit_agrege'), valeur)
            self.assertTrue(opts.get('watermark'), valeur)

    def test_confiance_ne_degrade_aucune_variante(self):
        link = self._link()
        for valeur in ('sans', 'avec', 'les_deux'):
            opts = self._opts_servies(link, f'?variante={valeur}')
            self.assertFalse(opts.get('kit_agrege'), valeur)
            self.assertFalse(opts.get('watermark'), valeur)

    def test_section_pdf_decochee_404_sur_toutes_les_variantes(self):
        link = self._link()
        link.sections = {'pdf': False}
        link.save(update_fields=['sections'])
        url = reverse('public-proposal-pdf', args=[link.token])
        for query in ('', '?variante=sans', '?variante=avec',
                      '?variante=les_deux'):
            resp = DjangoClient().get(url + query)
            self.assertEqual(resp.status_code, 404, query)


# ═══════════════════════════════════════════════════════════════════════════
# (d) — la SIGNATURE n'engage que la signature
# ═══════════════════════════════════════════════════════════════════════════

class TestSignatureNeRetrecitPasLeTelechargement(_Base):
    @patch('apps.ventes.services._store_signed_pdf')
    def test_apres_acceptation_avec_batterie_le_pdf_par_defaut_reste_complet(
            self, _mock_pdf):
        from apps.ventes.services import accept_devis
        accept_devis(devis=self.devis, user=self.user, nom='Client',
                     option=Devis.OptionAcceptee.AVEC_BATTERIE)
        self.devis.refresh_from_db()
        # L'option choisie est bien enregistrée (comportement inchangé)…
        self.assertEqual(self.devis.option_acceptee,
                         Devis.OptionAcceptee.AVEC_BATTERIE)
        # …et le document par défaut reste celui du commercial : les DEUX.
        data = build_quote_data(self.devis, clean_pdf_options({}))
        self.assertEqual(data['nb_options'], 2)
        self.assertEqual(data['scenario'], SCENARIO_LES_DEUX)
        self.assertIn(DESIGNATION_RESEAU, _designations(data['sans_items']))

    @patch('apps.ventes.services._store_signed_pdf')
    def test_le_moteur_ne_change_aucun_statut(self, _mock_pdf):
        """Règle #4 : rendre une variante ne touche à rien."""
        avant = (self.devis.statut, self.devis.option_acceptee)
        for valeur in ('sans', 'avec', 'les_deux'):
            build_quote_data(
                self.devis, clean_pdf_options({'variante_option': valeur}))
        self.devis.refresh_from_db()
        self.assertEqual((self.devis.statut, self.devis.option_acceptee),
                         avant)
