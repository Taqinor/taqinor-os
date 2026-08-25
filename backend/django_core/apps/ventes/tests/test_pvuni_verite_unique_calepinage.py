"""PVUNI / PVSTR / PVFRESH — UNE SEULE SOURCE DE VÉRITÉ : LES LIGNES DU DEVIS.

Incident fondateur du 18/08/2026, sur la proposition EN LIGNE de
``DEV-202608-0007`` : « la page du devis et le devis PDF ont deux nombres de
panneaux différents, et donc un coût différent aussi ». La charge utile publique
servie ce jour-là porte les trois symptômes reproduits ici :

* ``avec_items`` : Panneau Canadien Solar 710W ×9, **Structures acier ×8**,
  **Socles ×16** — le compte de panneaux était passé de 8 à 9 et la ferrure
  n'avait pas suivi (il en faut 9 et 18) ;
* ``puissance_kwc = 6.48`` servi à côté de ``watt_par_panneau = 710`` :
  6,48 kWc = 9 × **720 W** (la constante du calepinage roofPro), alors que les
  lignes disent 9 × 710 W = **6,39 kWc**. Deux bases de puissance dans un seul
  document — l'annexe technique du même PDF imprimait bien « 9 modules × 710 Wc
  = 6,39 kWc » ;
* la 3D montrait le calepinage joué pour un autre compte que celui des lignes,
  sans que rien ne le dise.

Ce module verrouille les invariants réparés. Chaque test part de la forme RÉELLE
du devis de production, jamais d'un cas d'école.

Run:
    powershell -File scripts/test-backend.ps1 -RestoreDb \
        -Modules "apps.ventes.tests.test_pvuni_verite_unique_calepinage"
"""
from decimal import Decimal
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.test import TestCase

from apps.crm.models import Client
from apps.stock.models import Produit
from apps.ventes.models import Devis
from apps.ventes.quote_engine import (
    build_quote_data, clean_pdf_options, cle_pdf_a_jour, empreinte_donnees_pdf,
)
from apps.ventes.services import sync_devis_from_layout

User = get_user_model()

#: Le calepinage roofPro dimensionne sur 720 W par panneau ; le panneau
#: RÉELLEMENT vendu sur ce devis en fait 710. C'est tout l'écart de l'incident.
WATT_CALEPINAGE = 720
WATT_PANNEAU_VENDU = 710
NB_PANNEAUX_LIVE = 9
#: 9 × 720 / 1000 — ce que le calepinage annonçait, et ce que la page servait.
KWC_CALEPINAGE = 6.48
#: 9 × 710 / 1000 — ce que les LIGNES disent, seule vérité admise désormais.
KWC_DES_LIGNES = 6.39
#: ``result.annualKwh`` du calepinage live (base 720 W, donc à recaler).
PROD_CALEPINAGE = 9952


def _company(slug='pvuni-co'):
    from authentication.models import Company
    company, _ = Company.objects.get_or_create(slug=slug,
                                               defaults={'nom': slug})
    return company


def layout_live(panneaux=NB_PANNEAUX_LIVE, kwc=KWC_CALEPINAGE):
    """Le calepinage tel que la proposition live le portait."""
    return {
        'scenario': 'avec_batterie',
        'result': {'panels': panneaux, 'kwc': kwc,
                   'annualKwh': PROD_CALEPINAGE},
        'pans': [{'label': 'Zone 1', 'nb_panneaux': panneaux, 'kwc': kwc,
                  'azimut_deg': 180, 'inclinaison_deg': 22}],
    }


class BaseDevisLive(TestCase):
    """Le devis de production DEV-202608-0007, reconstitué ligne à ligne."""

    def setUp(self):
        self.company = _company()
        self.user = User.objects.create_user(
            username='pvuni-user', password='x', role_legacy='responsable',
            company=self.company)
        self.client_obj = Client.objects.create(
            company=self.company, nom='Mohammed kasri',
            email='pvuni@example.test')
        self.panneau = Produit.objects.create(
            company=self.company, nom='Panneau Canadien Solar 710W',
            sku='PVUNI-PAN', prix_vente=Decimal('1272.73'),
            prix_achat=Decimal('900'), quantite_stock=500)
        self.onduleur = Produit.objects.create(
            company=self.company, nom='Onduleur hybride Deye 5kW Monophasé',
            sku='PVUNI-ONDH', prix_vente=Decimal('14166.67'),
            prix_achat=Decimal('9000'), quantite_stock=50)
        self.batterie = Produit.objects.create(
            company=self.company, nom='Batterie Deyness 5 kWh',
            sku='PVUNI-BAT', prix_vente=Decimal('14166.67'),
            prix_achat=Decimal('9500'), quantite_stock=50)
        self.structure = Produit.objects.create(
            company=self.company, nom='Structures acier', sku='PVUNI-STR',
            prix_vente=Decimal('416.67'), prix_achat=Decimal('280'),
            quantite_stock=500)
        self.socle = Produit.objects.create(
            company=self.company, nom='Socles', sku='PVUNI-SOC',
            prix_vente=Decimal('67'), prix_achat=Decimal('40'),
            quantite_stock=500)
        self.compteur = 0

    def devis_live(self, *, panneaux=NB_PANNEAUX_LIVE, structures=8, socles=16,
                   layout=None, etude=None, statut=Devis.Statut.BROUILLON):
        """Le devis live : 9 panneaux, mais 8 structures et 16 socles."""
        self.compteur += 1
        devis = Devis.objects.create(
            company=self.company, reference=f'DEV-PVUNI-{self.compteur}',
            client=self.client_obj, created_by=self.user, statut=statut,
            roof_layout=layout if layout is not None else layout_live(),
            etude_params=etude if etude is not None else {
                'puissance_kwc': KWC_CALEPINAGE,
                'production_annuelle': PROD_CALEPINAGE,
                'scenario': 'Avec batterie',
                'toiture': {'kwc': KWC_CALEPINAGE, 'nb_panneaux': panneaux,
                            'pans': [{'label': 'Zone 1', 'kwc': KWC_CALEPINAGE,
                                      'nb_panneaux': panneaux}]},
            })
        devis.lignes.create(
            produit=self.onduleur,
            designation='Onduleur hybride Deye 5kW Monophasé',
            quantite=Decimal('1'), prix_unitaire=Decimal('14166.67'), ordre=0)
        devis.lignes.create(
            produit=self.batterie, designation='Batterie Deyness 5 kWh',
            quantite=Decimal('1'), prix_unitaire=Decimal('14166.67'), ordre=0)
        devis.lignes.create(
            produit=self.panneau, designation='Panneau Canadien Solar 710W',
            quantite=Decimal(str(panneaux)), prix_unitaire=Decimal('1272.73'),
            ordre=0)
        devis.lignes.create(
            produit=self.structure, designation='Structures acier',
            quantite=Decimal(str(structures)), prix_unitaire=Decimal('416.67'),
            ordre=1)
        devis.lignes.create(
            produit=self.socle, designation='Socles',
            quantite=Decimal(str(socles)), prix_unitaire=Decimal('67'),
            ordre=2)
        return devis


class TestPuissanceServieVientDesLignes(BaseDevisLive):
    """PVUNI — le calepinage ne dicte plus la puissance quand les lignes parlent."""

    def test_kwc_servi_derive_des_lignes_pas_de_la_constante_720(self):
        devis = self.devis_live()
        data = build_quote_data(devis, {'pdf_mode': 'full'})

        self.assertEqual(data['nb_panneaux'], NB_PANNEAUX_LIVE)
        self.assertEqual(data['watt_par_panneau'], WATT_PANNEAU_VENDU)
        # LE symptôme de l'incident : 6,48 servi pour 9 × 710 W.
        self.assertNotEqual(data['puissance_kwc'], KWC_CALEPINAGE)
        self.assertEqual(data['puissance_kwc'], KWC_DES_LIGNES)

    def test_le_document_ne_porte_plus_deux_bases_de_puissance(self):
        """L'invariant, écrit comme le client le lit : kWc == n × W.

        C'est la formulation qui échouait sur le devis live (6 480 W annoncés
        pour 9 × 710 = 6 390 W posés) et qui tiendrait encore si quelqu'un
        réintroduisait une source de puissance concurrente, quelle qu'elle soit.
        """
        devis = self.devis_live()
        data = build_quote_data(devis, {'pdf_mode': 'full'})

        watts_annonces = round(data['puissance_kwc'] * 1000)
        watts_des_lignes = data['nb_panneaux'] * data['watt_par_panneau']
        self.assertEqual(watts_annonces, watts_des_lignes)
        # Et la base 720 W du calepinage n'a laissé aucune trace.
        self.assertNotEqual(
            watts_annonces, NB_PANNEAUX_LIVE * WATT_CALEPINAGE)

    def test_production_du_calepinage_est_recalee_sur_les_lignes(self):
        """La modélisation de site du calepinage est gardée, pas son échelle."""
        devis = self.devis_live()
        data = build_quote_data(devis, {'pdf_mode': 'full'})

        attendu = int(round(PROD_CALEPINAGE * KWC_DES_LIGNES / KWC_CALEPINAGE))
        self.assertEqual(data['prod_kwh'], attendu)
        self.assertLess(data['prod_kwh'], PROD_CALEPINAGE)

    def test_le_kwc_de_l_etude_servie_suit_la_meme_verite(self):
        """``etude.puissance_kwc`` est servi tel quel au client : même règle."""
        devis = self.devis_live()
        data = build_quote_data(devis, {'pdf_mode': 'full'})

        self.assertEqual(data['etude']['puissance_kwc'], KWC_DES_LIGNES)
        self.assertEqual(data['etude']['toiture']['kwc'], KWC_DES_LIGNES)
        # Le devis lui-même n'est jamais muté par un simple rendu (règle #4).
        devis.refresh_from_db()
        self.assertEqual(devis.etude_params['puissance_kwc'], KWC_CALEPINAGE)

    def test_sans_ligne_de_panneau_le_calepinage_reste_le_repli(self):
        """Rien à lire côté lignes → la géométrie 3D garde son autorité."""
        devis = self.devis_live(panneaux=0)
        devis.lignes.filter(designation='Panneau Canadien Solar 710W').delete()
        data = build_quote_data(devis, {'pdf_mode': 'full'})

        self.assertEqual(data['puissance_kwc'], KWC_CALEPINAGE)

    def test_devis_sans_calepinage_inchange(self):
        """Aucun layout → sortie strictement historique (dérivée des lignes)."""
        devis = self.devis_live(layout={}, etude={})
        data = build_quote_data(devis, {'pdf_mode': 'full'})

        self.assertEqual(data['puissance_kwc'], KWC_DES_LIGNES)
        self.assertFalse(data['layout_stale'])


class TestFerrureSuitLeCompteDePanneaux(BaseDevisLive):
    """PVSTR — 1 structure et 2 socles par panneau, comme la composition."""

    def test_structures_et_socles_rattrapent_le_nouveau_compte(self):
        # Le devis live EXACT : 9 panneaux déjà posés, 8 structures, 16 socles.
        devis = self.devis_live(panneaux=8, structures=8, socles=16,
                                layout=layout_live(panneaux=8, kwc=5.76))
        resultat = sync_devis_from_layout(devis, layout_live(), self.user)

        self.assertFalse(resultat['inchange'])
        self.assertEqual(resultat['panneaux'], NB_PANNEAUX_LIVE)
        self.assertEqual(
            int(devis.lignes.get(designation='Structures acier').quantite),
            NB_PANNEAUX_LIVE)
        self.assertEqual(
            int(devis.lignes.get(designation='Socles').quantite),
            NB_PANNEAUX_LIVE * 2)

    def test_un_calepinage_qui_ne_touche_pas_les_panneaux_ne_touche_rien(self):
        """Aucun mouvement de panneau → la ferrure ne bouge pas non plus."""
        devis = self.devis_live(panneaux=NB_PANNEAUX_LIVE, structures=8,
                                socles=16, layout=layout_live(panneaux=8))
        # Même compte de panneaux que les lignes : seule la géométrie change.
        sync_devis_from_layout(devis, layout_live(), self.user)

        self.assertEqual(
            int(devis.lignes.get(designation='Structures acier').quantite), 8)
        self.assertEqual(
            int(devis.lignes.get(designation='Socles').quantite), 16)

    def test_aucune_ligne_de_ferrure_n_est_inventee(self):
        """Un devis sans structure n'en gagne pas une par CE chemin.

        La complétion du kit (PVHEAL) reste seule habilitée à en ajouter une —
        et elle le fait au bon compte. Ici on vérifie seulement que la
        resynchronisation ne fabrique rien.
        """
        devis = self.devis_live(panneaux=8, layout=layout_live(panneaux=8))
        devis.lignes.filter(designation='Socles').delete()
        # Socle non tarifé : ni la resynchro ni la complétion du kit n'ont le
        # droit de le quoter (garde catalogue ``_has_price``).
        self.socle.prix_vente = Decimal('0')
        self.socle.save(update_fields=['prix_vente'])

        sync_devis_from_layout(devis, layout_live(), self.user)
        self.assertFalse(devis.lignes.filter(designation='Socles').exists())


class TestDrapeauCalepinagePerime(BaseDevisLive):
    """PVUNI — la 3D et les lignes divergent : on le dit, on ne le cache pas."""

    def test_layout_stale_bascule_quand_les_lignes_divergent(self):
        # Calepinage joué pour 9 panneaux, lignes ramenées à 8 à la main.
        devis = self.devis_live(panneaux=8)
        data = build_quote_data(devis, {'pdf_mode': 'full'})

        self.assertTrue(data['layout_stale'])
        self.assertEqual(data['layout_nb_panneaux'], NB_PANNEAUX_LIVE)
        self.assertEqual(data['nb_panneaux'], 8)

    def test_devis_coherent_ne_leve_aucun_drapeau(self):
        devis = self.devis_live(panneaux=NB_PANNEAUX_LIVE)
        data = build_quote_data(devis, {'pdf_mode': 'full'})

        self.assertFalse(data['layout_stale'])

    def test_le_drapeau_est_servi_au_lien_public(self):
        from apps.ventes.models import ShareLink

        devis = self.devis_live(panneaux=8, statut=Devis.Statut.ENVOYE)
        link = ShareLink.objects.create(company=self.company, devis=devis)
        resp = self.client.get(
            f'/api/django/ventes/proposal/{link.token}/')

        self.assertEqual(resp.status_code, 200, resp.content)
        self.assertTrue(resp.data['layout_stale'])
        self.assertEqual(resp.data['layout_nb_panneaux'], NB_PANNEAUX_LIVE)


class TestDrapeauCalepinageDeuxOptions(BaseDevisLive):
    """LAYSTALE (27/08/2026) — UN DOCUMENT À DEUX OPTIONS A DEUX COMPTES VALIDES.

    Depuis L-2OPT, les deux options d'un devis peuvent porter des nombres de
    panneaux différents (22 sans / 26 avec) et le scalaire ``nb_panneaux``
    porte alors celui de l'option AVEC. Le drapeau de péremption comparait le
    calepinage à ce SEUL scalaire : un calepinage joué sur l'option « sans »
    était déclaré périmé alors qu'il décrit fidèlement une des deux options
    imprimées — un avertissement faux, montré au client.
    """

    NB_SANS, NB_AVEC = 22, 26

    def _devis_deux_options(self, panneaux_layout, pdf_options=None):
        """Devis 22/26 (ligne panneau dédoublée par variante) + calepinage.

        Même mécanique que ``test_quote_engine_deux_optimiseurs`` : le champ
        modèle ``LigneDevis.variante`` est lu par l'unique point de lecture du
        moteur, remplacé ici — aucune dépendance à une migration.
        """
        self.compteur += 1
        reference = f'DEV-LAYSTALE-{self.compteur}'
        reseau = Produit.objects.create(
            company=self.company, nom='Onduleur réseau Huawei 10kW Triphasé',
            sku=f'{reference}-ONDR', prix_vente=Decimal('16666.67'),
            prix_achat=Decimal('11000'), quantite_stock=50)
        devis = Devis.objects.create(
            company=self.company, reference=reference, client=self.client_obj,
            created_by=self.user, statut=Devis.Statut.BROUILLON,
            roof_layout=layout_live(panneaux=panneaux_layout),
            etude_params={'scenario': 'Les deux (Sans + Avec)'})
        variantes = {}
        for nb, variante in ((self.NB_SANS, 'sans'), (self.NB_AVEC, 'avec')):
            ligne = devis.lignes.create(
                produit=self.panneau,
                designation='Panneau Canadien Solar 710W',
                quantite=Decimal(str(nb)), prix_unitaire=Decimal('1272.73'),
                ordre=0)
            variantes[ligne.pk] = variante
        devis.lignes.create(
            produit=reseau,
            designation='Onduleur réseau Huawei 10kW Triphasé',
            quantite=Decimal('1'), prix_unitaire=Decimal('16666.67'), ordre=1)
        devis.lignes.create(
            produit=self.onduleur,
            designation='Onduleur hybride Deye 5kW Monophasé',
            quantite=Decimal('1'), prix_unitaire=Decimal('14166.67'), ordre=2)
        devis.lignes.create(
            produit=self.batterie, designation='Batterie Deyness 5 kWh',
            quantite=Decimal('1'), prix_unitaire=Decimal('14166.67'), ordre=3)
        with patch('apps.ventes.quote_engine.builder._variante_de_ligne',
                   side_effect=lambda li: variantes.get(li.pk, '')):
            return build_quote_data(devis, pdf_options or {'pdf_mode': 'full'})

    def test_la_fixture_rend_bien_deux_options_divergentes(self):
        """Sans cette garantie, les cas ci-dessous ne prouveraient rien."""
        data = self._devis_deux_options(self.NB_SANS)

        self.assertTrue(data['deux_options'])
        self.assertTrue(data['panneaux_divergents'])
        self.assertEqual(data['nb_panneaux_sans'], self.NB_SANS)
        self.assertEqual(data['nb_panneaux_avec'], self.NB_AVEC)
        # Le scalaire legacy porte l'option AVEC : c'est LUI que l'ancienne
        # comparaison opposait au calepinage des 22.
        self.assertEqual(data['nb_panneaux'], self.NB_AVEC)

    def test_un_calepinage_cale_sur_l_option_sans_n_est_pas_perime(self):
        data = self._devis_deux_options(self.NB_SANS)

        self.assertEqual(data['layout_nb_panneaux'], self.NB_SANS)
        self.assertFalse(data['layout_stale'])

    def test_un_calepinage_cale_sur_l_option_avec_n_est_pas_perime(self):
        data = self._devis_deux_options(self.NB_AVEC)

        self.assertEqual(data['layout_nb_panneaux'], self.NB_AVEC)
        self.assertFalse(data['layout_stale'])

    def test_un_calepinage_cale_sur_aucune_des_deux_reste_perime(self):
        """La tolérance ne couvre QUE les deux comptes réellement imprimés."""
        data = self._devis_deux_options(24)

        self.assertEqual(data['layout_nb_panneaux'], 24)
        self.assertTrue(data['layout_stale'])

    def test_un_document_retreci_a_une_option_retrouve_un_seul_compte(self):
        """Rétréci à l'option « sans » (variante du lien public), le document
        n'imprime plus que 22 panneaux : le calepinage des 26 y est périmé."""
        data = self._devis_deux_options(
            self.NB_AVEC, {'pdf_mode': 'full', 'variante_option': 'sans'})

        self.assertFalse(data['deux_options'])
        self.assertEqual(data['nb_panneaux'], self.NB_SANS)
        self.assertTrue(data['layout_stale'])


class TestPdfStockeJamaisPerime(BaseDevisLive):
    """PVFRESH — servir le fichier stocké, oui ; servir un fichier périmé, non."""

    def _meta_a_jour(self, devis, options=None):
        options = clean_pdf_options(options)
        return {'empreinte': empreinte_donnees_pdf(
            build_quote_data(devis, options)), 'options': options}

    def test_donnees_inchangees_le_fichier_stocke_est_reutilise(self):
        devis = self.devis_live()
        devis.fichier_pdf = 'devis/1/DEV-PVUNI.pdf'
        devis.pdf_render_meta = self._meta_a_jour(devis)
        devis.save(update_fields=['fichier_pdf', 'pdf_render_meta'])

        with patch('apps.ventes.quote_engine.builder'
                   '.generate_premium_devis_pdf') as rendu:
            cle = cle_pdf_a_jour(devis)

        rendu.assert_not_called()
        self.assertEqual(cle, 'devis/1/DEV-PVUNI.pdf')

    def test_une_ligne_editee_force_le_re_rendu(self):
        """LE scénario de l'incident : « Générer PDF », on corrige, on télécharge."""
        devis = self.devis_live()
        devis.fichier_pdf = 'devis/1/DEV-PVUNI.pdf'
        devis.pdf_render_meta = self._meta_a_jour(devis)
        devis.save(update_fields=['fichier_pdf', 'pdf_render_meta'])

        ligne = devis.lignes.get(designation='Panneau Canadien Solar 710W')
        ligne.quantite = Decimal('10')
        ligne.save(update_fields=['quantite'])
        devis.refresh_from_db()

        with patch('apps.ventes.quote_engine.builder'
                   '.generate_premium_devis_pdf',
                   return_value='devis/1/frais.pdf') as rendu:
            cle = cle_pdf_a_jour(devis)

        rendu.assert_called_once()
        self.assertEqual(cle, 'devis/1/frais.pdf')

    def test_fichier_sans_empreinte_est_re_rendu(self):
        """Devis antérieurs à PVFRESH : on ne sert jamais à l'aveugle."""
        devis = self.devis_live()
        devis.fichier_pdf = 'devis/1/ancien.pdf'
        devis.save(update_fields=['fichier_pdf'])

        with patch('apps.ventes.quote_engine.builder'
                   '.generate_premium_devis_pdf',
                   return_value='devis/1/frais.pdf') as rendu:
            cle = cle_pdf_a_jour(devis)

        rendu.assert_called_once()
        self.assertEqual(cle, 'devis/1/frais.pdf')

    def test_le_format_du_dernier_rendu_est_respecte(self):
        """Un devis rendu en UNE page ne se re-rend pas en trois."""
        devis = self.devis_live()
        options = clean_pdf_options({'pdf_mode': 'onepage'})
        devis.fichier_pdf = 'devis/1/DEV-PVUNI.pdf'
        devis.pdf_render_meta = {'empreinte': 'perimee', 'options': options}
        devis.save(update_fields=['fichier_pdf', 'pdf_render_meta'])

        with patch('apps.ventes.quote_engine.builder'
                   '.generate_premium_devis_pdf',
                   return_value='devis/1/frais.pdf') as rendu:
            cle_pdf_a_jour(devis)

        self.assertEqual(rendu.call_args[0][1]['pdf_mode'], 'onepage')
