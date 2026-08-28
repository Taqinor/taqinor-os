"""L-SECT (fondateur 24/08/2026) — « le commercial choisit ce que le client
reçoit AVANT d'envoyer la page devis ».

``ShareLink.sections`` est un dict {clé: bool} à TROIS états :
  · clé ABSENTE → comportement par défaut ;
  · clé à False → section retirée du payload / de la page ;
  · clé à True  → section servie.

Couvert ici :
  (a) modèle — défaut ``{}`` (donc aucun lien existant ne change) et
      ``section_servie`` (absent → servie, False → non servie).
  (b) action share-link — accepte/persiste/renvoie ``sections``, whitelist
      STRICTE de clés et valeurs BOOLÉENNES seulement, jeton jamais régénéré.
  (c) payload ``proposal_data`` — chaque case, servie puis retirée.
  (d) DÉCISION FONDATEUR : le calepinage 3D (``roof3d``) est servi par défaut
      AUX DEUX NIVEAUX, y compris « standard ».
  (e) ``pdf`` à False → 404 sur les DEUX flux PDF publics (proposal_pdf ET
      public_document), sans effet de bord (aucune consultation comptée).

Run:
    docker compose exec django_core python manage.py test \
        apps.ventes.tests.test_l_sect_sections -v 2
"""
import uuid
from unittest import mock

from django.test import Client as DjangoClient, TestCase
from rest_framework.test import APIClient

from apps.ventes.models import ShareLink

from .test_l_niv_niveau import (
    make_client, make_company, make_devis, make_user, sample_layout,
)


PV = 'apps.ventes.public_views'


class SectionsBase(TestCase):
    """Socle commun : une société, un devis rendable, un lien par test."""

    slug = 'lsect'

    def setUp(self):
        self.company = make_company(self.slug)
        self.user = make_user(self.company, role='admin')
        self.client_obj = make_client(self.company)
        self._n = 0

    def _devis(self, avec_layout=False):
        self._n += 1
        return make_devis(
            self.company, self.user, self.client_obj,
            f'DEV-LSECT-{self.slug[-4:]}-{self._n}',
            roof_layout=sample_layout() if avec_layout else None)

    def _lien(self, devis, sections=None, niveau=ShareLink.NIVEAU_STANDARD):
        return ShareLink.objects.create(
            company=self.company, devis=devis, token=str(uuid.uuid4()),
            niveau=niveau, sections=sections if sections is not None else {})

    def _payload(self, link):
        resp = DjangoClient().get(
            f'/api/django/public/proposal/{link.token}/data/')
        self.assertEqual(resp.status_code, 200, resp.content[:400])
        return resp.json()


# ═══════════════════════════════════════════════════════════════════════════
# (a) Modèle
# ═══════════════════════════════════════════════════════════════════════════

class TestSectionsModele(SectionsBase):
    slug = 'lsect-mdl'

    def test_defaut_dict_vide(self):
        """Additif : un lien fraîchement créé ne porte AUCUNE clé — donc
        exactement le comportement d'avant L-SECT."""
        link = ShareLink.objects.create(company=self.company,
                                        devis=self._devis())
        self.assertEqual(link.sections, {})

    def test_section_servie_trois_etats(self):
        link = ShareLink.objects.create(
            company=self.company, devis=self._devis(),
            sections={'sld': False, 'pdf': True})
        self.assertFalse(link.section_servie('sld'))       # False → retirée
        self.assertTrue(link.section_servie('pdf'))        # True  → servie
        self.assertTrue(link.section_servie('roof3d'))     # absente → servie

    def test_section_servie_tolere_valeur_non_dict(self):
        """Défensif : un lien dont ``sections`` serait nul (donnée héritée ou
        test bricolé) se comporte comme « tout servi », jamais comme « tout
        retiré » — une régression silencieuse doit ouvrir, pas fermer."""
        link = ShareLink.objects.create(company=self.company,
                                        devis=self._devis())
        link.sections = None
        self.assertTrue(link.section_servie('roof3d'))


class TestTaillesServies(TestCase):
    """ENVOI 1/2/3 OPTIONS — la lecture des deux cases, isolée."""

    def _servies(self, sections):
        from apps.ventes.public_views import _tailles_servies
        return _tailles_servies(ShareLink(sections=sections))

    def test_recommande_est_TOUJOURS_servie(self):
        # C'est LE devis. Aucune case ne la retire, y compris quand les deux
        # autres sont décochées.
        for sections in ({}, {'taille_eco': False, 'taille_max': False}):
            with self.subTest(sections=sections):
                self.assertIn('recommande', self._servies(sections))

    def test_absentes_les_trois_tailles_sont_servies(self):
        self.assertEqual(self._servies({}),
                         {'eco', 'recommande', 'max'})

    def test_chaque_case_retire_SA_taille(self):
        self.assertEqual(self._servies({'taille_eco': False}),
                         {'recommande', 'max'})
        self.assertEqual(self._servies({'taille_max': False}),
                         {'eco', 'recommande'})

    def test_les_deux_false_ne_laissent_que_le_devis(self):
        self.assertEqual(
            self._servies({'taille_eco': False, 'taille_max': False}),
            {'recommande'})

    def test_les_deux_cles_sont_dans_la_whitelist(self):
        # Sans quoi l'action share-link les refuserait en 400 et le dialogue
        # d'envoi ne pourrait rien poser.
        self.assertIn('taille_eco', ShareLink.SECTIONS_CLES)
        self.assertIn('taille_max', ShareLink.SECTIONS_CLES)


# ═══════════════════════════════════════════════════════════════════════════
# (b) Action share-link
# ═══════════════════════════════════════════════════════════════════════════

class TestShareLinkActionSections(SectionsBase):
    slug = 'lsect-act'

    def setUp(self):
        super().setUp()
        self.api = APIClient()
        self.api.force_authenticate(self.user)

    def _post(self, devis, body=None):
        return self.api.post(
            f'/api/django/ventes/devis/{devis.id}/share-link/',
            body if body is not None else {}, format='json')

    def test_sans_sections_dans_le_corps_le_lien_ne_bouge_pas(self):
        devis = self._devis()
        premier = self._post(devis, {'sections': {'sld': False}})
        self.assertEqual(premier.data['sections'], {'sld': False})
        second = self._post(devis, {'niveau': 'confiance'})
        self.assertEqual(second.data['sections'], {'sld': False})

    def test_persiste_et_renvoie_sections_sans_regenerer_le_jeton(self):
        devis = self._devis()
        premier = self._post(devis)
        token = premier.data['token']
        self.assertEqual(premier.data['sections'], {})
        second = self._post(devis, {'sections': {'roof3d': True, 'pdf': False}})
        self.assertEqual(second.status_code, 200, second.data)
        self.assertEqual(second.data['token'], token)  # MÊME jeton
        self.assertEqual(second.data['sections'], {'roof3d': True, 'pdf': False})
        link = ShareLink.objects.get(token=token)
        self.assertEqual(link.sections, {'roof3d': True, 'pdf': False})

    def test_toutes_les_cles_de_la_whitelist_sont_acceptees(self):
        devis = self._devis()
        corps = {cle: False for cle in ShareLink.SECTIONS_CLES}
        resp = self._post(devis, {'sections': corps})
        self.assertEqual(resp.status_code, 200, resp.data)
        self.assertEqual(resp.data['sections'], corps)

    def test_refuse_une_cle_hors_whitelist(self):
        devis = self._devis()
        resp = self._post(devis, {'sections': {'prix_achat': False}})
        self.assertEqual(resp.status_code, 400)
        self.assertIn('prix_achat', resp.data['detail'])
        self.assertFalse(
            ShareLink.objects.filter(devis=devis)
            .exclude(sections={}).exists())

    def test_refuse_une_valeur_non_booleenne(self):
        devis = self._devis()
        resp = self._post(devis, {'sections': {'sld': 'non'}})
        self.assertEqual(resp.status_code, 400)
        self.assertIn('sld', resp.data['detail'])

    def test_refuse_un_sections_qui_nest_pas_un_objet(self):
        devis = self._devis()
        resp = self._post(devis, {'sections': ['sld']})
        self.assertEqual(resp.status_code, 400)

    def test_multi_tenant_autre_societe_404(self):
        """Le devis reste borné à la société de l'utilisateur : L-SECT
        n'ouvre aucune brèche."""
        autre = make_company('lsect-autre')
        devis_autre = make_devis(
            autre, make_user(autre, role='admin'), make_client(autre),
            'DEV-LSECT-AUTRE-1')
        resp = self._post(devis_autre, {'sections': {'pdf': False}})
        self.assertEqual(resp.status_code, 404)


# ═══════════════════════════════════════════════════════════════════════════
# (c)/(d) Payload proposal_data — section par section
# ═══════════════════════════════════════════════════════════════════════════

class TestPayloadSections(SectionsBase):
    slug = 'lsect-pub'

    # ── roof3d : la DÉCISION FONDATEUR ────────────────────────────────────
    def test_roof3d_servi_par_defaut_meme_au_niveau_standard(self):
        """« le client ne voit pas ses panneaux sur son toit » — le calepinage
        3D est servi aux DEUX niveaux tant que la case n'est pas décochée."""
        devis = self._devis(avec_layout=True)
        for niveau in (ShareLink.NIVEAU_STANDARD, ShareLink.NIVEAU_CONFIANCE):
            payload = self._payload(self._lien(devis, niveau=niveau))
            self.assertIsNotNone(payload['roof_layout'], niveau)

    def test_roof3d_false_retire_le_calepinage_aux_deux_niveaux(self):
        devis = self._devis(avec_layout=True)
        for niveau in (ShareLink.NIVEAU_STANDARD, ShareLink.NIVEAU_CONFIANCE):
            payload = self._payload(
                self._lien(devis, {'roof3d': False}, niveau=niveau))
            self.assertIsNone(payload['roof_layout'], niveau)

    def test_roof3d_true_explicite_sert_le_calepinage(self):
        devis = self._devis(avec_layout=True)
        payload = self._payload(self._lien(devis, {'roof3d': True}))
        self.assertIsNotNone(payload['roof_layout'])

    # ── sld : schéma unifilaire + détail électrique, UNE section ──────────
    def test_sld_servi_par_defaut_et_retire_si_false(self):
        devis = self._devis()
        with mock.patch(f'{PV}._safe_sld_svg', return_value='<svg/>'), \
                mock.patch(f'{PV}._conception_electrique_publique',
                           return_value={'chaines': []}):
            servi = self._payload(self._lien(devis))
            retire = self._payload(self._lien(devis, {'sld': False}))
        self.assertIsNotNone(servi['sld_svg'])
        self.assertIsNotNone(servi['conception_electrique'])
        self.assertIsNone(retire['sld_svg'])
        self.assertIsNone(retire['conception_electrique'])

    # ── bankable ─────────────────────────────────────────────────────────
    def test_bankable_servi_par_defaut_et_absent_si_false(self):
        devis = self._devis()
        with mock.patch(f'{PV}._bankable_headline',
                        return_value={'p50_kwh': 14000}):
            servi = self._payload(self._lien(devis))
            retire = self._payload(self._lien(devis, {'bankable': False}))
        self.assertIn('bankable', servi)
        self.assertNotIn('bankable', retire)

    # ── economies : les 5 clés de synthèse partent ensemble ───────────────
    def test_economies_false_retire_la_synthese_entiere(self):
        devis = self._devis()
        synthese = {'pct_cut': 62, 'annual_before': 12000,
                    'annual_after': 4560, 'coverage_pct': 70,
                    'coverage_estimated': False}
        cible = 'apps.ventes.quote_engine.residential.renderer'
        with mock.patch(f'{cible}.is_residential', return_value=True), \
                mock.patch(f'{cible}.ancrage_reel_absent', return_value=False), \
                mock.patch(f'{cible}.synthese_economies', return_value=synthese):
            servi = self._payload(self._lien(devis))
            retire = self._payload(self._lien(devis, {'economies': False}))
        self.assertEqual(servi['pct_cut'], 62)
        self.assertEqual(servi['annual_before'], 12000)
        for cle in ('pct_cut', 'annual_before', 'annual_after',
                    'coverage_pct', 'coverage_estimated'):
            self.assertIsNone(retire[cle], cle)

    def test_economies_false_ne_touche_pas_les_montants_du_devis(self):
        """Règle absolue : retirer un BLOC D'AFFICHAGE ne change AUCUN
        montant du devis."""
        devis = self._devis()
        servi = self._payload(self._lien(devis))
        retire = self._payload(self._lien(devis, {'economies': False}))
        self.assertEqual(servi['option_totals'], retire['option_totals'])
        for cle in ('total_sans', 'total_avec', 'display_total'):
            self.assertEqual(servi['quote'][cle], retire['quote'][cle], cle)

    # ── jour_type : jours_types + courbes_journalieres ───────────────────
    def test_jour_type_false_retire_les_deux_cles(self):
        devis = self._devis()
        courbes = 'apps.ventes.courbes_journalieres'
        with mock.patch(f'{PV}._jours_types_publique',
                        return_value={'mois': []}), \
                mock.patch(f'{courbes}.construire_courbes_journalieres',
                           return_value={'saisons': []}):
            servi = self._payload(self._lien(devis))
            retire = self._payload(self._lien(devis, {'jour_type': False}))
        self.assertIn('jours_types', servi)
        self.assertIn('courbes_journalieres', servi)
        self.assertNotIn('jours_types', retire)
        self.assertNotIn('courbes_journalieres', retire)

    # ── gammes ───────────────────────────────────────────────────────────
    def test_gammes_false_retire_le_comparatif(self):
        devis = self._devis()
        with mock.patch(f'{PV}._gammes_public',
                        return_value={'envoi': 'les_deux'}):
            servi = self._payload(self._lien(devis))
            retire = self._payload(self._lien(devis, {'gammes': False}))
        self.assertIsNotNone(servi['gammes'])
        self.assertIsNone(retire['gammes'])

    # ── tailles : ENVOI 1/2/3 OPTIONS (fondateur, 28/08/2026) ────────────
    #
    # Deux cases seulement — `taille_eco` et `taille_max`. « Recommandé » n'en
    # a pas : c'est LE devis, la seule carte autorisée à ouvrir la signature.
    # La dérivation est bouchonnée (elle a ses propres tests dans
    # test_offres_tailles) : ce qu'on éprouve ici, c'est le CÂBLAGE lien →
    # payload.

    TROIS_TAILLES = {
        'avec_servable': False,
        'offres': [{'cle': 'eco', 'titre': 'Éco'},
                   {'cle': 'recommande', 'titre': 'Recommandé'},
                   {'cle': 'max', 'titre': 'Max'}],
    }

    def _tailles(self, devis, sections=None):
        """Les clés de tailles réellement SERVIES par ce lien (``None`` = la
        section entière est absente du payload)."""
        with mock.patch('apps.ventes.offres_tailles.deriver',
                        return_value=dict(self.TROIS_TAILLES)):
            payload = self._payload(self._lien(devis, sections))
        bloc = payload.get('offres_tailles')
        if bloc is None:
            return None
        return [o['cle'] for o in bloc['offres']]

    def test_tailles_absentes_de_sections_servent_les_TROIS(self):
        # Additif : tout lien DÉJÀ envoyé garde exactement ses trois cartes.
        self.assertEqual(self._tailles(self._devis()),
                         ['eco', 'recommande', 'max'])

    def test_taille_eco_false_retire_la_carte_eco_et_elle_seule(self):
        self.assertEqual(self._tailles(self._devis(), {'taille_eco': False}),
                         ['recommande', 'max'])

    def test_taille_max_false_retire_la_carte_max_et_elle_seule(self):
        self.assertEqual(self._tailles(self._devis(), {'taille_max': False}),
                         ['eco', 'recommande'])

    def test_les_deux_false_font_disparaitre_la_SECTION(self):
        # UNE option envoyée = la page d'avant ce chantier : pas de section
        # « Explorer d'autres tailles » (une carte seule n'explore rien).
        self.assertIsNone(self._tailles(
            self._devis(), {'taille_eco': False, 'taille_max': False}))

    def test_true_explicite_sert_la_taille(self):
        self.assertEqual(
            self._tailles(self._devis(),
                          {'taille_eco': True, 'taille_max': True}),
            ['eco', 'recommande', 'max'])

    def test_economies_false_retire_les_tailles_meme_cochees(self):
        # Ce bloc EST un bloc d'économies : la case « Économies » ne doit pas
        # être contournable par les cases de tailles.
        self.assertIsNone(self._tailles(
            self._devis(), {'economies': False, 'taille_eco': True,
                            'taille_max': True}))

    # ── aucune case ne change les montants ni le niveau ──────────────────
    def test_toutes_cases_decochees_laisse_les_montants_intacts(self):
        devis = self._devis(avec_layout=True)
        toutes_false = {cle: False for cle in ShareLink.SECTIONS_CLES
                        if cle != 'pdf'}  # 'pdf' ne concerne pas le payload
        reference = self._payload(self._lien(devis))
        depouille = self._payload(self._lien(devis, toutes_false))
        self.assertEqual(reference['option_totals'],
                         depouille['option_totals'])
        self.assertEqual(reference['quote']['display_total'],
                         depouille['quote']['display_total'])
        self.assertEqual(depouille['niveau'], 'standard')


# ═══════════════════════════════════════════════════════════════════════════
# (e) pdf → 404 sur les DEUX flux
# ═══════════════════════════════════════════════════════════════════════════

class TestSectionPdf(SectionsBase):
    slug = 'lsect-pdf'

    def test_pdf_false_404_sur_proposal_pdf(self):
        link = self._lien(self._devis(), {'pdf': False})
        resp = DjangoClient().get(
            f'/api/django/public/proposal/{link.token}/pdf/')
        self.assertEqual(resp.status_code, 404)

    def test_pdf_false_404_sur_public_document(self):
        link = self._lien(self._devis(), {'pdf': False})
        resp = DjangoClient().get(
            f'/api/django/public/document/{link.token}/')
        self.assertEqual(resp.status_code, 404)

    def test_pdf_false_ne_compte_aucune_consultation(self):
        """Le refus est posé AVANT tout effet de bord : une tentative bloquée
        n'est ni comptée ni notifiée au commercial."""
        link = self._lien(self._devis(), {'pdf': False})
        DjangoClient().get(f'/api/django/public/proposal/{link.token}/pdf/')
        DjangoClient().get(f'/api/django/public/document/{link.token}/')
        link.refresh_from_db()
        self.assertEqual(link.view_count, 0)
        self.assertIsNone(link.first_viewed_at)

    def test_pdf_false_ne_bloque_pas_la_page_elle_meme(self):
        """Seul le PDF part : la page devis reste consultable."""
        link = self._lien(self._devis(), {'pdf': False})
        resp = DjangoClient().get(
            f'/api/django/public/proposal/{link.token}/data/')
        self.assertEqual(resp.status_code, 200)

    def test_pdf_absent_de_sections_sert_le_pdf_comme_avant(self):
        """Comportement par défaut inchangé : sans la clé, le flux PDF passe
        le gate L-SECT (le rendu lui-même est bouchonné ici — on teste le
        gate, pas le moteur)."""
        link = self._lien(self._devis())
        with mock.patch(f'{PV}.generate_premium_devis_pdf',
                        return_value='k'), \
                mock.patch(f'{PV}.download_pdf', return_value=b'%PDF-1.4'):
            resp = DjangoClient().get(
                f'/api/django/public/proposal/{link.token}/pdf/')
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp['Content-Type'], 'application/pdf')
