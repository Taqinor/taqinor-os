"""PV18 — POST /ventes/devis/<id>/sync-layout/ : mise à jour CHIRURGICALE.

Un devis vivant porte des prix négociés, des remises, des sections, des notes,
un ordre d'affichage et des groupes multi-villa que personne n'a le droit de
perdre parce que la toiture a bougé de deux panneaux. Ce chemin ne touche que
les quantités de panneaux et la présence de la batterie — et JAMAIS le statut
(règle #4).

Run:
    DJANGO_SETTINGS_MODULE=erp_agentique.settings._local_sqlite_test \
        python manage.py test apps.ventes.tests.test_pv18_sync_layout -v 2
"""
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from apps.crm.models import Client
from apps.stock.models import Produit
from apps.ventes.models import Devis
from apps.ventes.services import layout_hash

User = get_user_model()

CLES_REPONSE = {'inchange', 'panneaux', 'kwc', 'scenario', 'batterie',
                'lignes_modifiees', 'avertissements'}


def make_company(slug):
    from authentication.models import Company
    company, _ = Company.objects.get_or_create(
        slug=slug, defaults={'nom': slug})
    return company


def auth_client(user):
    api = APIClient()
    api.credentials(HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(user)}')
    return api


def layout(panels=16, kwc=8.8, *, scenario='reseau', **extra):
    corps = {
        'scenario': scenario,
        'panelWatt': 550,
        'result': {'panels': panels, 'kwc': kwc,
                   'annualKwh': 14000, 'savings': 12000},
    }
    corps.update(extra)
    return corps


class TestSyncLayout(TestCase):
    def setUp(self):
        self.company = make_company('pv18-co')
        self.user = User.objects.create_user(
            username='pv18user', password='x', role_legacy='responsable',
            company=self.company)
        self.api = auth_client(self.user)
        self.client_obj = Client.objects.create(
            company=self.company, nom='Client PV18')
        self.panneau = Produit.objects.create(
            company=self.company, nom='Panneau Jinko 550W', sku='PV18-PAN',
            prix_vente=Decimal('1100'), prix_achat=Decimal('700'),
            quantite_stock=100)
        self.panneau450 = Produit.objects.create(
            company=self.company, nom='Panneau Longi 450W', sku='PV18-PAN450',
            prix_vente=Decimal('900'), prix_achat=Decimal('600'),
            quantite_stock=100)
        self.onduleur = Produit.objects.create(
            company=self.company, nom='Onduleur réseau Huawei 5kW',
            sku='PV18-ONDR', prix_vente=Decimal('14000'),
            prix_achat=Decimal('9000'), quantite_stock=100)
        # PVSCE — un onduleur HYBRIDE au catalogue : sans lui, une resynchro
        # « avec batterie » laisserait un onduleur réseau face à une batterie
        # (le moteur PDF n'accorde alors que l'option « Sans », qui exclut la
        # batterie — donc une ligne facturée mais invisible).
        self.onduleur_hybride = Produit.objects.create(
            company=self.company, nom='Onduleur hybride Deye 5kW',
            sku='PV18-ONDH', prix_vente=Decimal('17000'),
            prix_achat=Decimal('11000'), quantite_stock=100)
        # Batterie GLOBALE (company=None) — le catalogue partagé doit être
        # quotable ici comme dans _pick_product.
        self.batterie = Produit.objects.create(
            company=None, nom='Batterie Deyness 5 kWh', sku='PV18-BAT-GLOBAL',
            prix_vente=Decimal('17000'), prix_achat=Decimal('12000'),
            quantite_stock=100)
        self.compteur = 0

    def _devis(self, *, statut=Devis.Statut.BROUILLON, panneaux=12,
               etude=None, mode=None, hash_layout=None):
        self.compteur += 1
        devis = Devis.objects.create(
            company=self.company, reference=f'DEV-PV18-{self.compteur}',
            client=self.client_obj, statut=statut, created_by=self.user,
            etude_params=etude, mode_installation=mode,
            layout_hash=hash_layout)
        if panneaux:
            devis.lignes.create(
                produit=self.panneau, designation='Panneau Jinko 550W',
                quantite=Decimal(str(panneaux)),
                prix_unitaire=Decimal('980'), remise=Decimal('5'), ordre=1)
        devis.lignes.create(
            produit=self.onduleur, designation='Onduleur réseau Huawei 5kW',
            quantite=Decimal('1'), prix_unitaire=Decimal('13500'), ordre=2)
        return devis

    def _post(self, devis, corps):
        return self.api.post(
            f'/api/django/ventes/devis/{devis.id}/sync-layout/',
            corps, format='json')

    # ── Les quatre comportements de statut ─────────────────────────────────
    def test_brouillon_applique_le_calepinage(self):
        devis = self._devis(panneaux=12)
        resp = self._post(devis, layout(panels=16))
        self.assertEqual(resp.status_code, 200, resp.content)
        self.assertEqual(set(resp.data), CLES_REPONSE)
        self.assertFalse(resp.data['inchange'])
        self.assertEqual(resp.data['panneaux'], 16)
        panneau = devis.lignes.get(designation='Panneau Jinko 550W')
        self.assertEqual(int(panneau.quantite), 16)
        devis.refresh_from_db()
        self.assertEqual(devis.statut, Devis.Statut.BROUILLON)

    def test_envoye_409_revision_possible(self):
        devis = self._devis(statut=Devis.Statut.ENVOYE, panneaux=12)
        resp = self._post(devis, layout(panels=16))
        self.assertEqual(resp.status_code, 409)
        self.assertTrue(resp.data['revision_possible'])
        self.assertIn('Réviser', resp.data['detail'])
        # Aucune écriture : ni ligne, ni layout, ni statut.
        self.assertEqual(
            int(devis.lignes.get(designation='Panneau Jinko 550W').quantite),
            12)
        devis.refresh_from_db()
        self.assertEqual(devis.statut, Devis.Statut.ENVOYE)
        self.assertIsNone(devis.roof_layout)

    def test_documents_clos_409_sans_revision(self):
        for statut in (Devis.Statut.ACCEPTE, Devis.Statut.REFUSE,
                       Devis.Statut.EXPIRE):
            with self.subTest(statut=statut):
                devis = self._devis(statut=statut, panneaux=12)
                resp = self._post(devis, layout(panels=16))
                self.assertEqual(resp.status_code, 409)
                self.assertFalse(resp.data['revision_possible'])
                self.assertEqual(
                    int(devis.lignes.get(
                        designation='Panneau Jinko 550W').quantite), 12)
                devis.refresh_from_db()
                self.assertEqual(devis.statut, statut)

    # ── Court-circuit : même empreinte, zéro écriture ──────────────────────
    def test_meme_layout_inchange_sans_ecriture(self):
        corps = layout(panels=16)
        devis = self._devis(panneaux=12, hash_layout=layout_hash(corps))
        resp = self._post(devis, corps)
        self.assertEqual(resp.status_code, 200)
        self.assertTrue(resp.data['inchange'])
        self.assertEqual(resp.data['lignes_modifiees'], 0)
        # La quantité N'A PAS été alignée : le court-circuit précède tout.
        self.assertEqual(
            int(devis.lignes.get(designation='Panneau Jinko 550W').quantite),
            12)
        devis.refresh_from_db()
        self.assertIsNone(devis.roof_layout)

    # ── Batterie : ajout / retrait selon le scénario ───────────────────────
    def test_batterie_ajoutee_depuis_le_catalogue_global(self):
        devis = self._devis(panneaux=12)
        resp = self._post(devis, layout(panels=12, scenario='avec_batterie'))
        self.assertEqual(resp.status_code, 200)
        self.assertTrue(resp.data['batterie'])
        self.assertEqual(resp.data['scenario'], 'avec_batterie')
        ligne = devis.lignes.get(designation='Batterie Deyness 5 kWh')
        self.assertEqual(ligne.produit_id, self.batterie.id)
        self.assertEqual(int(ligne.quantite), 1)

        # PVSCE — l'ONDULEUR a suivi : le devis ne garde pas un onduleur réseau
        # face à une batterie (ce serait la « batterie fantôme » : comptée dans
        # le total, absente du PDF).
        self.assertFalse(
            devis.lignes.filter(designation__icontains='réseau').exists())
        onduleur = devis.lignes.get(designation='Onduleur hybride Deye 5kW')
        self.assertEqual(onduleur.produit_id, self.onduleur_hybride.id)
        self.assertEqual(int(onduleur.quantite), 1)     # quantité INCHANGÉE
        self.assertEqual(onduleur.prix_unitaire, Decimal('17000.00'))
        devis.refresh_from_db()
        self.assertEqual(devis.etude_params['scenario'], 'Avec batterie')

    def test_la_batterie_apparait_dans_les_items_du_moteur(self):
        """La preuve par le moteur : l'option « Avec » porte la batterie.

        C'est le test qui aurait attrapé la batterie fantôme — le découpage des
        options est fait par ``build_quote_data`` (``avec_ok = has_hybride and
        has_batterie``), pas par la resynchro.
        """
        from apps.ventes.quote_engine.builder import build_quote_data

        devis = self._devis(panneaux=12)
        self._post(devis, layout(panels=12, scenario='avec_batterie'))
        devis.refresh_from_db()

        data = build_quote_data(devis)
        self.assertEqual(data['scenario'], 'Avec batterie')
        avec = ' '.join(it['designation'] for it in data['avec_items'])
        self.assertIn('Batterie', avec)
        self.assertIn('hybride', avec)
        # Et le total affiché porte bien la batterie qu'on facture.
        self.assertGreater(data['total_avec'], 0)

    def test_l_onduleur_redevient_reseau_quand_la_batterie_sort(self):
        """Sens inverse : un devis hybride sans batterie ne rendrait AUCUNE
        option (le moteur refuse alors le PDF à options)."""
        devis = self._devis(panneaux=12)
        devis.lignes.filter(designation__icontains='réseau').update(
            produit=self.onduleur_hybride,
            designation='Onduleur hybride Deye 5kW')
        devis.lignes.create(
            produit=self.batterie, designation='Batterie Deyness 5 kWh',
            quantite=Decimal('1'), prix_unitaire=Decimal('16000'), ordre=3)

        resp = self._post(devis, layout(panels=12, scenario='reseau'))
        self.assertEqual(resp.status_code, 200)
        self.assertFalse(resp.data['batterie'])
        self.assertFalse(
            devis.lignes.filter(designation__icontains='hybride').exists())
        onduleur = devis.lignes.get(designation='Onduleur réseau Huawei 5kW')
        self.assertEqual(onduleur.produit_id, self.onduleur.id)
        devis.refresh_from_db()
        self.assertEqual(devis.etude_params['scenario'], 'Sans batterie')

    def test_sans_hybride_au_catalogue_on_previent_au_lieu_de_mentir(self):
        Produit.objects.filter(pk=self.onduleur_hybride.pk).update(
            is_archived=True)
        devis = self._devis(panneaux=12)
        resp = self._post(devis, layout(panels=12, scenario='avec_batterie'))
        self.assertEqual(resp.status_code, 200)
        self.assertTrue(any('hybride' in a for a in resp.data['avertissements']))
        # L'onduleur réseau reste en place, et le scénario stocké ne promet pas
        # une option que l'équipement ne peut pas servir.
        self.assertTrue(
            devis.lignes.filter(designation__icontains='réseau').exists())
        devis.refresh_from_db()
        self.assertEqual(devis.etude_params['scenario'], 'Sans batterie')

    def test_batterie_retiree_quand_le_scenario_n_en_veut_plus(self):
        devis = self._devis(panneaux=12)
        devis.lignes.create(
            produit=self.batterie, designation='Batterie Deyness 5 kWh',
            quantite=Decimal('1'), prix_unitaire=Decimal('16000'), ordre=3)
        resp = self._post(devis, layout(panels=12, scenario='reseau'))
        self.assertEqual(resp.status_code, 200)
        self.assertFalse(resp.data['batterie'])
        self.assertFalse(
            devis.lignes.filter(designation__icontains='Batterie').exists())

    def test_batterie_deja_presente_n_est_pas_dupliquee(self):
        devis = self._devis(panneaux=12)
        devis.lignes.create(
            produit=self.batterie, designation='Batterie Deyness 5 kWh',
            quantite=Decimal('1'), prix_unitaire=Decimal('16000'), ordre=3)
        resp = self._post(devis, layout(panels=12, scenario='avec_batterie'))
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(
            devis.lignes.filter(designation__icontains='Batterie').count(), 1)
        # Le prix NÉGOCIÉ de la batterie en place est conservé.
        self.assertEqual(
            devis.lignes.get(designation='Batterie Deyness 5 kWh')
            .prix_unitaire, Decimal('16000.00'))

    # ── Plusieurs lignes de panneaux : l'écart va sur la PLUS GROSSE ───────
    def test_ecart_applique_a_la_plus_grosse_ligne(self):
        devis = self._devis(panneaux=14)  # Jinko 550W, la plus grosse
        devis.lignes.create(
            produit=self.panneau450, designation='Panneau Longi 450W',
            quantite=Decimal('4'), prix_unitaire=Decimal('900'), ordre=3)
        resp = self._post(devis, layout(panels=20))  # 18 → 20 : +2
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.data['panneaux'], 20)
        self.assertEqual(
            int(devis.lignes.get(designation='Panneau Jinko 550W').quantite),
            16)
        # La seconde marque n'a PAS bougé.
        self.assertEqual(
            int(devis.lignes.get(designation='Panneau Longi 450W').quantite),
            4)

    def test_retrait_ne_descend_jamais_sous_zero(self):
        devis = self._devis(panneaux=6)
        devis.lignes.create(
            produit=self.panneau450, designation='Panneau Longi 450W',
            quantite=Decimal('4'), prix_unitaire=Decimal('900'), ordre=3)
        resp = self._post(devis, layout(panels=1))  # 10 → 1 : −9 sur une de 6
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(
            int(devis.lignes.get(designation='Panneau Jinko 550W').quantite),
            0)
        self.assertTrue(any('0' in a for a in resp.data['avertissements']))

    # ── Aucune ligne de panneau : une seule est créée ──────────────────────
    def test_creation_d_une_ligne_panneau_au_wattage_du_layout(self):
        devis = self._devis(panneaux=0)
        resp = self._post(devis, layout(panels=10))
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.data['panneaux'], 10)
        lignes = devis.lignes.filter(designation__icontains='Panneau')
        self.assertEqual(lignes.count(), 1)
        # panelWatt = 550 → le panneau 550 W, pas le moins cher (450 W).
        self.assertEqual(lignes.first().produit_id, self.panneau.id)
        self.assertEqual(int(lignes.first().quantite), 10)

    def test_layout_sans_panneau_ne_detruit_rien(self):
        devis = self._devis(panneaux=12)
        resp = self._post(devis, {'scenario': 'reseau', 'result': {}})
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(
            int(devis.lignes.get(designation='Panneau Jinko 550W').quantite),
            12)
        self.assertTrue(resp.data['avertissements'])

    # ── Tout le reste est INTACT ───────────────────────────────────────────
    def test_prix_remises_sections_notes_ordre_et_groupes_intacts(self):
        devis = self._devis(panneaux=12)
        devis.lignes.create(
            designation='Équipements', quantite=None, prix_unitaire=None,
            type_ligne='section', ordre=0)
        devis.lignes.create(
            designation='Pose sous 4 semaines', quantite=None,
            prix_unitaire=None, type_ligne='note', ordre=9)
        commun = devis.lignes.create(
            produit=self.onduleur, designation='Onduleur réseau Huawei 5kW',
            quantite=Decimal('1'), prix_unitaire=Decimal('12000'),
            remise=Decimal('7'), ordre=5, groupe_index=1,
            groupe_label='Villa A')
        resp = self._post(devis, layout(panels=16))
        self.assertEqual(resp.status_code, 200)
        panneau = devis.lignes.get(designation='Panneau Jinko 550W')
        # Quantité alignée, MAIS prix négocié / remise / ordre inchangés.
        self.assertEqual(int(panneau.quantite), 16)
        self.assertEqual(panneau.prix_unitaire, Decimal('980.00'))
        self.assertEqual(panneau.remise, Decimal('5.00'))
        self.assertEqual(panneau.ordre, 1)
        commun.refresh_from_db()
        self.assertEqual(commun.prix_unitaire, Decimal('12000.00'))
        self.assertEqual(commun.remise, Decimal('7.00'))
        self.assertEqual(commun.groupe_index, 1)
        self.assertEqual(commun.groupe_label, 'Villa A')
        self.assertTrue(
            devis.lignes.filter(type_ligne='section',
                                designation='Équipements').exists())
        self.assertTrue(
            devis.lignes.filter(type_ligne='note').exists())

    # ── etude_params : les clés du calepinage + le scénario, pas une de plus ─
    def test_etude_params_chirurgical(self):
        devis = self._devis(
            panneaux=12,
            etude={'taux_autoconsommation': 72, 'payback_annees': 5.4,
                   'puissance_kwc': 6.6, 'pompe_cv': 3})
        resp = self._post(devis, layout(panels=16, kwc=8.8))
        self.assertEqual(resp.status_code, 200)
        devis.refresh_from_db()
        etude = devis.etude_params
        # Les quatre clés du calepinage sont (ré)écrites…
        self.assertAlmostEqual(float(etude['puissance_kwc']), 8.8, places=3)
        self.assertEqual(etude['production_annuelle'], 14000)
        self.assertEqual(etude['economies_annuelles'], 12000)
        # PVSCE — plus le scénario, aligné sur l'état RÉEL des lignes.
        self.assertEqual(etude['scenario'], 'Sans batterie')
        # …et les champs d'étude du générateur sont INTACTS.
        self.assertEqual(etude['taux_autoconsommation'], 72)
        self.assertEqual(etude['payback_annees'], 5.4)
        self.assertEqual(etude['pompe_cv'], 3)

    def test_layout_et_empreinte_reposes(self):
        corps = layout(panels=16)
        devis = self._devis(panneaux=12)
        self._post(devis, corps)
        devis.refresh_from_db()
        self.assertEqual(devis.layout_hash, layout_hash(corps))
        self.assertEqual(devis.roof_layout['result']['panels'], 16)
        # Re-soumettre le MÊME layout ne fait plus rien.
        resp = self._post(devis, corps)
        self.assertTrue(resp.data['inchange'])

    def test_enveloppe_layout_acceptee(self):
        devis = self._devis(panneaux=12)
        resp = self._post(devis, {'layout': layout(panels=16)})
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.data['panneaux'], 16)

    def test_corps_vide_400(self):
        devis = self._devis(panneaux=12)
        resp = self._post(devis, {})
        self.assertEqual(resp.status_code, 400)

    # ── Portée société & étanchéité ────────────────────────────────────────
    def test_devis_d_une_autre_societe_404(self):
        autre = make_company('pv18-autre-co')
        client_autre = Client.objects.create(company=autre, nom='Ailleurs')
        devis = Devis.objects.create(
            company=autre, reference='DEV-PV18-ETR', client=client_autre,
            statut=Devis.Statut.BROUILLON)
        self.assertEqual(self._post(devis, layout()).status_code, 404)

    def test_aucun_prix_achat_dans_la_reponse(self):
        devis = self._devis(panneaux=12)
        resp = self._post(devis, layout(panels=16))
        self.assertNotIn('prix_achat', str(resp.data))
