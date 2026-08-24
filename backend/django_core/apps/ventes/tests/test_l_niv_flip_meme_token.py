"""L-NIV-FLIP — le niveau bascule sur le MÊME jeton, et la page client change.

CONSTAT FONDATEUR (24/08/2026) : « en basculant Client standard ↔ Client de
confiance, je ne vois AUCUNE différence sur la page client ».

Les tests existants (``test_l_niv_niveau.py``) couvrent chaque niveau
SÉPARÉMENT, avec un jeton NEUF par niveau. Ils ne prouvent donc PAS le geste
réel du commercial : garder le lien déjà envoyé et changer son niveau. C'est
exactement ce trou-là que ce fichier ferme, bout en bout et sur le MÊME jeton :

    POST share-link (défaut standard) → GET data → bascule confiance
    → GET data (MÊME URL) → re-bascule standard → GET data

À chaque GET on ré-affirme les TROIS dégradations encore actives au niveau
standard, et l'invariant fondateur (marques + montants identiques). Un futur
lot qui débrancherait ``est_standard`` quelque part fait rougir ce fichier
au lieu de passer inaperçu en production.

Run :
    DB_NAME=erp_ventes python manage.py test \
        apps.ventes.tests.test_l_niv_flip_meme_token -v 2
"""
import json
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import Client as DjangoClient, TestCase
from rest_framework.test import APIClient

from apps.crm.models import Client
from apps.stock.models import FicheTechnique, Produit
from apps.ventes.models import Devis, LigneDevis, ShareLink
from authentication.models import Company

User = get_user_model()

KIT_AGREGE = 'Kit de fixation, câblage et protection complet'
KIT_LIGNES = (
    ('Rail de fixation aluminium', '20', '35'),
    ('Câble DC 6mm² rouge/noir', '30', '4.5'),
    ('Disjoncteur AC 20A tétrapolaire', '1', '180'),
)


class FlipNiveauMemeTokenTest(TestCase):
    """Un devis RÉEL et complet (fiches techniques → schéma unifilaire, lignes
    kit → agrégation), un SEUL jeton, et le niveau qui bascule dessus."""

    def setUp(self):
        self.company = Company.objects.create(nom='LNIVFLIP', slug='lnivflip')
        self.user = User.objects.create_user(
            username='lnivflip', password='x', role_legacy='admin',
            company=self.company)
        self.crm_client = Client.objects.create(
            company=self.company, nom='Flip', prenom='Test',
            email='lnivflip@example.com', telephone='+212600000011')
        self.devis = Devis.objects.create(
            company=self.company, reference='DEV-LNIV-FLIP', statut='envoye',
            client=self.crm_client, taux_tva=Decimal('20.00'),
            remise_globale=Decimal('0'), created_by=self.user,
            roof_layout={'_pans_geometry': [
                {'label': 'Sud', 'nb_panneaux': 14, 'azimut_deg': 180,
                 'inclinaison_deg': 20}]})
        self._materiel_avec_fiches()
        self._lignes_kit()
        # PV41 — la conception électrique STOCKÉE est le portail du schéma
        # unifilaire et du détail électrique : sans elle, les deux clés valent
        # None AUX DEUX NIVEAUX (et ce test ne prouverait rien).
        from apps.ventes.electrical_service import build_electrical_design
        build_electrical_design(self.devis)
        self.devis.refresh_from_db()
        self.assertIsNotNone(
            self.devis.electrical_design,
            "montage invalide : sans conception électrique, le schéma "
            "unifilaire est absent AUX DEUX NIVEAUX")

        self.api = APIClient()
        self.api.force_authenticate(self.user)
        premier = self.api.post(
            f'/api/django/ventes/devis/{self.devis.id}/share-link/')
        self.assertEqual(premier.status_code, 200, premier.data)
        self.token = premier.data['token']
        self.assertEqual(premier.data['niveau'], 'standard')

    # ── montage ────────────────────────────────────────────────────────────
    def _materiel_avec_fiches(self):
        panneau = Produit.objects.create(
            company=self.company, nom='Panneau Canadian Solar 550W',
            sku='FLIP-PAN', prix_vente=Decimal('1400'),
            prix_achat=Decimal('900'), quantite_stock=100)
        onduleur = Produit.objects.create(
            company=self.company, nom='Onduleur réseau Deye 10kW triphasé',
            sku='FLIP-OND', prix_vente=Decimal('14000'),
            prix_achat=Decimal('9000'), quantite_stock=10)
        # PVFCH — un schéma ne se dessine QU'À PARTIR des fiches techniques.
        FicheTechnique.objects.create(
            company=self.company, produit=panneau, type_fiche='module',
            pmax_wc=Decimal('550.00'), voc_v=Decimal('49.90'),
            isc_a=Decimal('14.02'), vmp_v=Decimal('41.80'),
            imp_a=Decimal('13.16'),
            temp_coeff_voc_pct_c=Decimal('-0.270'),
            temp_coeff_pmax_pct_c=Decimal('-0.350'))
        FicheTechnique.objects.create(
            company=self.company, produit=onduleur, type_fiche='onduleur',
            ond_ac_kw=Decimal('10.00'), ond_phases=3, ond_n_mppt=2,
            ond_mppt_v_min=Decimal('200.0'), ond_mppt_v_max=Decimal('950.0'),
            ond_v_max_abs=Decimal('1100.0'), ond_i_max_mppt_a=Decimal('26.0'),
            ond_rendement_euro_pct=Decimal('98.0'), ond_bat_aucune=True)
        LigneDevis.objects.create(
            devis=self.devis, produit=panneau,
            designation='Panneau Canadian Solar 550W', quantite=Decimal('14'),
            prix_unitaire=Decimal('1400'), remise=Decimal('0'))
        LigneDevis.objects.create(
            devis=self.devis, produit=onduleur,
            designation='Onduleur réseau Deye 10kW triphasé',
            quantite=Decimal('1'), prix_unitaire=Decimal('14000'),
            remise=Decimal('0'))

    def _lignes_kit(self):
        for desig, qty, pu in KIT_LIGNES:
            produit = Produit.objects.create(
                company=self.company, nom=desig, sku=f'FLIP-K-{desig[:6]}',
                prix_vente=Decimal(pu), prix_achat=Decimal('1'),
                quantite_stock=99)
            LigneDevis.objects.create(
                devis=self.devis, produit=produit, designation=desig,
                quantite=Decimal(qty), prix_unitaire=Decimal(pu),
                remise=Decimal('0'))

    # ── utilitaires ────────────────────────────────────────────────────────
    def _basculer(self, niveau):
        """Repose la MÊME route share-link avec un autre niveau et vérifie que
        le jeton n'a pas bougé (le lien déjà envoyé continue de marcher)."""
        resp = self.api.post(
            f'/api/django/ventes/devis/{self.devis.id}/share-link/',
            {'niveau': niveau}, format='json')
        self.assertEqual(resp.status_code, 200, resp.data)
        self.assertEqual(resp.data['token'], self.token,
                         'le jeton ne doit JAMAIS être régénéré')
        self.assertEqual(resp.data['niveau'], niveau)

    def _payload(self):
        """Relit la page client SUR LE MÊME JETON — c'est exactement ce que
        fait le navigateur du client (SSR, prerender=false, aucun cache)."""
        resp = DjangoClient().get(
            f'/api/django/public/proposal/{self.token}/data/')
        self.assertEqual(resp.status_code, 200)
        return resp.json()

    def _designations(self, payload):
        items = (payload['quote'].get('sans_items')
                 or payload['quote'].get('avec_items') or [])
        return {it['designation'] for it in items}

    # ── ce que le niveau doit vraiment changer ─────────────────────────────
    def _affirmer_standard(self, payload):
        self.assertEqual(payload['niveau'], 'standard')
        # (1) kit agrégé — les 3 lignes fixation/câblage/protection fusionnent
        designations = self._designations(payload)
        self.assertIn(KIT_AGREGE, designations)
        self.assertFalse(designations & {d for d, _, _ in KIT_LIGNES})
        # (2) schéma unifilaire SANS le tableau « Nomenclature des
        #     équipements » (repères, calibres, sections)
        self.assertTrue(payload['sld_svg'])
        self.assertNotIn('Nomenclature des équipements', payload['sld_svg'])
        # (3) détail électrique : protections sans calibre, câbles omis en bloc
        detail = payload['conception_electrique']
        self.assertTrue(detail)
        self.assertNotIn('cables', detail)
        for protection in detail['protections']:
            self.assertNotIn('calibre', protection)

    def _affirmer_confiance(self, payload):
        self.assertEqual(payload['niveau'], 'confiance')
        designations = self._designations(payload)
        self.assertNotIn(KIT_AGREGE, designations)
        self.assertTrue({d for d, _, _ in KIT_LIGNES} <= designations)
        self.assertTrue(payload['sld_svg'])
        self.assertIn('Nomenclature des équipements', payload['sld_svg'])
        detail = payload['conception_electrique']
        self.assertTrue(detail)
        self.assertTrue(detail.get('cables'))
        self.assertTrue(any('calibre' in p for p in detail['protections']))

    # ── les tests ──────────────────────────────────────────────────────────
    def test_flip_standard_confiance_standard_change_le_payload(self):
        """LE test du constat fondateur : un SEUL jeton, trois lectures."""
        self._affirmer_standard(self._payload())

        self._basculer(ShareLink.NIVEAU_CONFIANCE)
        self._affirmer_confiance(self._payload())

        # Révocation : le commercial reprend le détail au client sans changer
        # de lien — la page REDEVIENT dégradée (donc aucun cache n'a servi
        # l'ancien niveau : ni ETag/Cache-Control côté API, ni SSR Astro).
        self._basculer(ShareLink.NIVEAU_STANDARD)
        self._affirmer_standard(self._payload())

    def test_les_marques_restent_visibles_aux_deux_niveaux(self):
        """RÈGLE FONDATEUR ABSOLUE (24/08/2026) : les marques/modèles sont
        TOUJOURS affichés, quel que soit le niveau. Une future dégradation ne
        doit jamais les emporter."""
        standard = json.dumps(self._payload())
        self._basculer(ShareLink.NIVEAU_CONFIANCE)
        confiance = json.dumps(self._payload())
        for blob in (standard, confiance):
            self.assertIn('Deye', blob)
            self.assertIn('Canadian Solar', blob)

    def test_niveau_masque_dit_la_verite_sur_ce_devis(self):
        """L-NIV-VU — la page ne peut annoncer « version simplifiée » que sur
        du réel : la liste énumère les dégradations qui ONT eu lieu, et se vide
        au niveau confiance."""
        standard = self._payload()
        self.assertEqual(
            sorted(standard['niveau_masque']),
            ['dimensionnement_electrique', 'nomenclature_kit'])
        self._basculer(ShareLink.NIVEAU_CONFIANCE)
        self.assertEqual(self._payload()['niveau_masque'], [])

    def test_aucun_montant_ne_bouge_entre_les_deux_niveaux(self):
        """L'autre invariant : le niveau change la GRANULARITÉ, jamais un
        chiffre d'argent."""
        standard = self._payload()
        self._basculer(ShareLink.NIVEAU_CONFIANCE)
        confiance = self._payload()
        for key in ('total_sans', 'total_avec', 'display_total'):
            self.assertEqual(standard['quote'][key], confiance['quote'][key])


class NiveauMasqueVideSurDevisNuTest(TestCase):
    """L-NIV-VU — LE cas qui explique le constat fondateur.

    Un devis SANS lignes de pose et SANS conception électrique n'a rien à
    masquer : au niveau standard, la charge utile est identique à celle du
    niveau confiance, et ``niveau_masque`` est VIDE. La page n'annonce donc
    rien — dire « version simplifiée » là serait un fait inventé."""

    def setUp(self):
        self.company = Company.objects.create(nom='LNIVNU', slug='lnivnu')
        self.user = User.objects.create_user(
            username='lnivnu', password='x', role_legacy='admin',
            company=self.company)
        crm_client = Client.objects.create(
            company=self.company, nom='Nu', prenom='Test',
            email='lnivnu@example.com', telephone='+212600000012')
        self.devis = Devis.objects.create(
            company=self.company, reference='DEV-LNIV-NU', statut='envoye',
            client=crm_client, taux_tva=Decimal('20.00'),
            remise_globale=Decimal('0'), created_by=self.user)
        for desig, qty, pu in [('Onduleur réseau Deye 8kW', '1', '14000'),
                               ('Panneau Canadian Solar 550W', '10', '1400')]:
            produit = Produit.objects.create(
                company=self.company, nom=desig, sku=f'NU-{desig[:8]}',
                prix_vente=Decimal(pu), prix_achat=Decimal('1'),
                quantite_stock=50)
            LigneDevis.objects.create(
                devis=self.devis, produit=produit, designation=desig,
                quantite=Decimal(qty), prix_unitaire=Decimal(pu),
                remise=Decimal('0'))

    def _payload(self, niveau):
        import uuid
        token = str(uuid.uuid4())
        ShareLink.objects.create(
            company=self.company, devis=self.devis, token=token,
            niveau=niveau)
        resp = DjangoClient().get(
            f'/api/django/public/proposal/{token}/data/')
        self.assertEqual(resp.status_code, 200)
        return resp.json()

    def test_rien_a_masquer_donc_aucune_annonce(self):
        standard = self._payload(ShareLink.NIVEAU_STANDARD)
        self.assertEqual(standard['niveau_masque'], [])
        # Et, de fait, aucune des deux dégradations n'a eu lieu.
        items = (standard['quote'].get('sans_items')
                 or standard['quote'].get('avec_items') or [])
        self.assertNotIn(KIT_AGREGE, {it['designation'] for it in items})
        self.assertIsNone(standard['conception_electrique'])
        self.assertIsNone(standard['sld_svg'])
