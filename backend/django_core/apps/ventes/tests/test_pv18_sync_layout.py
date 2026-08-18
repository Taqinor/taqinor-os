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
                'lignes_modifiees', 'lignes_ajoutees', 'avertissements'}


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
            company=None, nom='Batterie Dyness 5 kWh', sku='PV18-BAT-GLOBAL',
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
        ligne = devis.lignes.get(designation='Batterie Dyness 5 kWh')
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
            produit=self.batterie, designation='Batterie Dyness 5 kWh',
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
            produit=self.batterie, designation='Batterie Dyness 5 kWh',
            quantite=Decimal('1'), prix_unitaire=Decimal('16000'), ordre=3)
        resp = self._post(devis, layout(panels=12, scenario='reseau'))
        self.assertEqual(resp.status_code, 200)
        self.assertFalse(resp.data['batterie'])
        self.assertFalse(
            devis.lignes.filter(designation__icontains='Batterie').exists())

    def test_batterie_deja_presente_n_est_pas_dupliquee(self):
        devis = self._devis(panneaux=12)
        devis.lignes.create(
            produit=self.batterie, designation='Batterie Dyness 5 kWh',
            quantite=Decimal('1'), prix_unitaire=Decimal('16000'), ordre=3)
        resp = self._post(devis, layout(panels=12, scenario='avec_batterie'))
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(
            devis.lignes.filter(designation__icontains='Batterie').count(), 1)
        # Le prix NÉGOCIÉ de la batterie en place est conservé.
        self.assertEqual(
            devis.lignes.get(designation='Batterie Dyness 5 kWh')
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


# ── PVHEAL — la resynchronisation COMPLÈTE le kit manquant ──────────────────
#
# Les devis nés avant PVKIT sont des SQUELETTES : panneau + onduleur, parfois
# une pose. Le client, lui, reçoit des structures, des socles et un tableau de
# protection AC/DC que le devis ne mentionne nulle part. Ces tests verrouillent
# la guérison — et surtout ses trois interdits : ne rien modifier, ne rien
# dupliquer, ne rien inventer en silence.

#: Le catalogue COMPLET, aux désignations exactes de ``seed_catalogue`` (c'est
#: par elles que le classifieur partagé range les produits). Prix de vente HT.
CATALOGUE_KIT = [
    ('Panneau Jinko 550W', 'HEAL-PAN', '1100'),
    ('Onduleur réseau Huawei 5kW', 'HEAL-ONDR', '14000'),
    ('Onduleur hybride Deye 5kW', 'HEAL-ONDH', '17000'),
    ('Batterie Dyness 5 kWh', 'HEAL-BAT', '16000'),
    ('Structures acier', 'HEAL-STR', '500'),
    ('Socles', 'HEAL-SOC', '80'),
    ('Smart Meter', 'HEAL-SMART', '1800'),
    ('Wifi Dongle', 'HEAL-WIFI', '1200'),
    ('Accessoires', 'HEAL-ACC', '2000'),
    ('Tableau De Protection AC/DC', 'HEAL-TAB', '2000'),
    ('Installation', 'HEAL-INST', '4800'),
    ('Transport', 'HEAL-TRANS', '1000'),
]

#: Les huit classes que la complétion sait ajouter, par leur désignation
#: catalogue — l'ordre n'a pas d'importance ici, la présence si.
KIT_ATTENDU = ('Smart Meter', 'Wifi Dongle', 'Structures acier', 'Socles',
               'Accessoires', 'Tableau De Protection AC/DC', 'Installation',
               'Transport')


class TestCompletionDuKit(TestCase):
    """Un devis SQUELETTE resynchronisé repart avec le kit réellement vendu."""

    def setUp(self):
        self.company = make_company('pvheal-co')
        self.user = User.objects.create_user(
            username='pvhealuser', password='x', role_legacy='responsable',
            company=self.company)
        self.api = auth_client(self.user)
        self.client_obj = Client.objects.create(
            company=self.company, nom='Client PVHEAL')
        self.compteur = 0

    def _catalogue(self, *, sans=()):
        """Sème le catalogue, éventuellement AMPUTÉ de certains produits."""
        self.produits = {}
        for nom, sku, prix in CATALOGUE_KIT:
            if nom in sans:
                continue
            self.produits[nom] = Produit.objects.create(
                company=self.company, nom=nom, sku=sku,
                prix_vente=Decimal(prix), prix_achat=Decimal('1'),
                quantite_stock=500)
        return self.produits

    def _squelette(self, *, panneaux=12, onduleur='Onduleur réseau Huawei 5kW',
                   prix_onduleur='13500'):
        """Le devis d'hier : un panneau à prix NÉGOCIÉ + un onduleur. Rien de
        plus — ni structure, ni socle, ni tableau."""
        self.compteur += 1
        devis = Devis.objects.create(
            company=self.company, reference='DEV-HEAL-%s' % self.compteur,
            client=self.client_obj, statut=Devis.Statut.BROUILLON,
            created_by=self.user)
        devis.lignes.create(
            produit=self.produits['Panneau Jinko 550W'],
            designation='Panneau Jinko 550W',
            quantite=Decimal(str(panneaux)), prix_unitaire=Decimal('980'),
            remise=Decimal('5'), ordre=1)
        devis.lignes.create(
            produit=self.produits[onduleur], designation=onduleur,
            quantite=Decimal('1'), prix_unitaire=Decimal(prix_onduleur),
            ordre=2)
        return devis

    def _post(self, devis, corps):
        return self.api.post(
            '/api/django/ventes/devis/%s/sync-layout/' % devis.id,
            corps, format='json')

    def _par_designation(self, devis):
        return {ligne.designation: ligne for ligne in devis.lignes.all()}

    # ── (a) Le kit COMPLET est ajouté, l'existant n'est pas touché ──────────
    def test_le_kit_manquant_est_ajoute_avec_les_bonnes_quantites(self):
        self._catalogue()
        devis = self._squelette(panneaux=12)
        # Empreinte de l'onduleur AVANT : il ne doit pas bouger d'un octet.
        onduleur_avant = devis.lignes.get(designation__icontains='Onduleur')

        resp = self._post(devis, layout(panels=16, kwc=8.8))
        self.assertEqual(resp.status_code, 200, resp.content)
        self.assertEqual(set(resp.data), CLES_REPONSE)

        lignes = self._par_designation(devis)
        for designation in KIT_ATTENDU:
            self.assertIn(designation, lignes,
                          '%s manque au kit' % designation)
        self.assertEqual(resp.data['lignes_ajoutees'], len(KIT_ATTENDU))
        self.assertEqual(resp.data['avertissements'], [])

        # Quantités : une structure par panneau, DEUX socles par panneau, et
        # les forfaits à l'unité (16 panneaux de 550 Wc = 8,8 kWc → 2 blocs).
        self.assertEqual(int(lignes['Structures acier'].quantite), 16)
        self.assertEqual(int(lignes['Socles'].quantite), 32)
        self.assertEqual(int(lignes['Accessoires'].quantite), 1)
        self.assertEqual(int(lignes['Smart Meter'].quantite), 1)

        # Prix des forfaits : le simulateur les exprime en TTC par bloc de
        # 5 kWc, le devis stocke du HT (TVA 20 %).
        self.assertEqual(lignes['Accessoires'].prix_unitaire,
                         Decimal('1666.67'))   # 2 × 1000 TTC
        self.assertEqual(lignes['Tableau De Protection AC/DC'].prix_unitaire,
                         Decimal('2500.00'))   # 2 × 1500 TTC
        self.assertEqual(lignes['Installation'].prix_unitaire,
                         Decimal('6000.00'))   # (2+1) × 2400 TTC
        # …et un produit non forfaitaire garde son prix catalogue.
        self.assertEqual(lignes['Structures acier'].prix_unitaire,
                         Decimal('500.00'))

        # L'EXISTANT est intact : prix négocié, remise et ordre du panneau
        # (seule sa quantité suit le calepinage), onduleur inchangé.
        panneau = lignes['Panneau Jinko 550W']
        self.assertEqual(int(panneau.quantite), 16)
        self.assertEqual(panneau.prix_unitaire, Decimal('980.00'))
        self.assertEqual(panneau.remise, Decimal('5.00'))
        self.assertEqual(panneau.ordre, 1)
        onduleur_apres = devis.lignes.get(pk=onduleur_avant.pk)
        self.assertEqual(onduleur_apres.prix_unitaire, Decimal('13500.00'))
        self.assertEqual(onduleur_apres.produit_id, onduleur_avant.produit_id)
        self.assertEqual(int(onduleur_apres.quantite), 1)
        # Les ajouts se rangent APRÈS l'existant.
        self.assertGreater(lignes['Structures acier'].ordre, panneau.ordre)

    def test_le_smart_meter_ne_suit_que_huawei(self):
        """Derrière un Deye, le duo Smart Meter + Wifi ne se vend pas — et son
        absence n'est donc PAS un avertissement."""
        self._catalogue()
        devis = self._squelette(onduleur='Onduleur hybride Deye 5kW')
        resp = self._post(devis, layout(panels=16, kwc=8.8,
                                        scenario='avec_batterie'))
        self.assertEqual(resp.status_code, 200)
        lignes = self._par_designation(devis)
        self.assertNotIn('Smart Meter', lignes)
        self.assertNotIn('Wifi Dongle', lignes)
        self.assertEqual(resp.data['avertissements'], [])
        # Le reste du kit, lui, est bien là.
        self.assertIn('Tableau De Protection AC/DC', lignes)

    def test_le_duo_huawei_suit_l_onduleur_DU_DEVIS_pas_celui_compose(self):
        """Le devis porte un onduleur Huawei, la composition choisirait un Deye
        (plus gros palier) : le Smart Meter est bien dû, et son absence de la
        composition ne doit PAS passer pour une absence du catalogue."""
        self._catalogue()
        Produit.objects.create(
            company=self.company, nom='Onduleur hybride Deye 10kW',
            sku='HEAL-ONDH10', prix_vente=Decimal('30000'),
            prix_achat=Decimal('1'), quantite_stock=5)
        self.produits['Onduleur hybride Huawei 5kW'] = Produit.objects.create(
            company=self.company, nom='Onduleur hybride Huawei 5kW',
            sku='HEAL-ONDH-HW', prix_vente=Decimal('18000'),
            prix_achat=Decimal('1'), quantite_stock=5)
        devis = self._squelette(onduleur='Onduleur hybride Huawei 5kW',
                                prix_onduleur='18000')

        resp = self._post(devis, layout(panels=16, kwc=8.8,
                                        scenario='avec_batterie'))
        self.assertEqual(resp.status_code, 200)
        lignes = self._par_designation(devis)
        self.assertIn('Smart Meter', lignes)
        self.assertIn('Wifi Dongle', lignes)
        self.assertEqual(int(lignes['Smart Meter'].quantite), 1)
        self.assertEqual(lignes['Smart Meter'].prix_unitaire,
                         Decimal('1800.00'))
        self.assertEqual(resp.data['avertissements'], [])

    def test_une_classe_deja_presente_n_est_jamais_dupliquee(self):
        """La présence se lit au CLASSIFIEUR, pas au libellé : une pose
        rebaptisée à la main compte quand même comme l'installation."""
        self._catalogue()
        devis = self._squelette()
        devis.lignes.create(
            produit=self.produits['Installation'],
            designation='Pose et mise en service',
            quantite=Decimal('1'), prix_unitaire=Decimal('7500'), ordre=3)

        resp = self._post(devis, layout(panels=16, kwc=8.8))
        self.assertEqual(resp.status_code, 200)
        self.assertFalse(
            devis.lignes.filter(designation='Installation').exists())
        pose = devis.lignes.get(designation='Pose et mise en service')
        self.assertEqual(pose.prix_unitaire, Decimal('7500.00'))
        self.assertEqual(resp.data['lignes_ajoutees'], len(KIT_ATTENDU) - 1)

    # ── (b) Catalogue amputé : on saute ET on le DIT ────────────────────────
    def test_sans_structure_au_catalogue_on_avertit_et_on_ajoute_le_reste(self):
        self._catalogue(sans=('Structures acier',))
        devis = self._squelette()
        resp = self._post(devis, layout(panels=16, kwc=8.8))
        self.assertEqual(resp.status_code, 200)

        lignes = self._par_designation(devis)
        self.assertNotIn('Structures acier', lignes)
        self.assertEqual(resp.data['lignes_ajoutees'], len(KIT_ATTENDU) - 1)
        # Un avertissement FRANÇAIS, explicite, affichable tel quel.
        self.assertEqual(len(resp.data['avertissements']), 1)
        message = resp.data['avertissements'][0]
        self.assertIn('Structure de fixation', message)
        self.assertIn('ligne non ajoutée', message)
        # Tout le reste du kit est bien entré.
        for designation in KIT_ATTENDU:
            if designation == 'Structures acier':
                continue
            self.assertIn(designation, lignes)

    def test_un_produit_sans_prix_est_traite_comme_absent(self):
        """Un tableau de protection à 0 MAD n'est pas coté — il est annoncé."""
        self._catalogue()
        Produit.objects.filter(
            pk=self.produits['Tableau De Protection AC/DC'].pk).update(
            prix_vente=Decimal('0'))
        devis = self._squelette()
        resp = self._post(devis, layout(panels=16, kwc=8.8))
        self.assertEqual(resp.status_code, 200)
        self.assertFalse(devis.lignes.filter(
            designation='Tableau De Protection AC/DC').exists())
        self.assertTrue(any('Tableau de protection' in a
                            for a in resp.data['avertissements']))

    # ── (c) Re-synchro immédiate : rien ne se répète ────────────────────────
    def test_resynchro_immediate_inchange_et_zero_ajout(self):
        self._catalogue()
        devis = self._squelette()
        corps = layout(panels=16, kwc=8.8)
        premier = self._post(devis, corps)
        self.assertEqual(premier.data['lignes_ajoutees'], len(KIT_ATTENDU))
        compte = devis.lignes.count()

        second = self._post(devis, corps)
        self.assertEqual(second.status_code, 200)
        self.assertTrue(second.data['inchange'])
        self.assertEqual(second.data['lignes_ajoutees'], 0)
        self.assertEqual(second.data['lignes_modifiees'], 0)
        self.assertEqual(devis.lignes.count(), compte)

    def test_un_layout_different_ne_redouble_pas_le_kit(self):
        """Même sans le court-circuit d'empreinte, le kit ne revient pas : les
        classes sont désormais présentes."""
        self._catalogue()
        devis = self._squelette()
        self._post(devis, layout(panels=16, kwc=8.8))
        compte = devis.lignes.count()

        resp = self._post(devis, layout(panels=18, kwc=9.9))
        self.assertEqual(resp.status_code, 200)
        self.assertFalse(resp.data['inchange'])
        self.assertEqual(resp.data['lignes_ajoutees'], 0)
        self.assertEqual(devis.lignes.count(), compte)

    # ── (d) L'artefact « deux onduleurs » ───────────────────────────────────
    def test_deux_onduleurs_l_intrus_au_prix_catalogue_est_retire(self):
        self._catalogue()
        devis = self._squelette(onduleur='Onduleur hybride Deye 5kW',
                                prix_onduleur='17000')
        # L'artefact : un SECOND onduleur, réseau, resté au prix catalogue.
        devis.lignes.create(
            produit=self.produits['Onduleur réseau Huawei 5kW'],
            designation='Onduleur réseau Huawei 5kW',
            quantite=Decimal('1'), prix_unitaire=Decimal('14000'),
            remise=Decimal('0'), ordre=3)

        resp = self._post(devis, layout(panels=16, kwc=8.8,
                                        scenario='avec_batterie'))
        self.assertEqual(resp.status_code, 200)
        self.assertFalse(devis.lignes.filter(
            designation='Onduleur réseau Huawei 5kW').exists())
        hybride = devis.lignes.get(designation='Onduleur hybride Deye 5kW')
        self.assertEqual(hybride.prix_unitaire, Decimal('17000.00'))
        devis.refresh_from_db()
        self.assertEqual(devis.etude_params['scenario'], 'Avec batterie')

    def test_deux_onduleurs_l_intrus_a_prix_modifie_est_conserve(self):
        self._catalogue()
        devis = self._squelette(onduleur='Onduleur hybride Deye 5kW',
                                prix_onduleur='17000')
        devis.lignes.create(
            produit=self.produits['Onduleur réseau Huawei 5kW'],
            designation='Onduleur réseau Huawei 5kW',
            quantite=Decimal('1'), prix_unitaire=Decimal('11900'),
            remise=Decimal('0'), ordre=3)

        resp = self._post(devis, layout(panels=16, kwc=8.8,
                                        scenario='avec_batterie'))
        self.assertEqual(resp.status_code, 200)
        # Rien n'est supprimé en silence : la ligne reste, l'écran est prévenu.
        reseau = devis.lignes.get(designation='Onduleur réseau Huawei 5kW')
        self.assertEqual(reseau.prix_unitaire, Decimal('11900.00'))
        self.assertTrue(any('DEUX onduleurs' in a
                            for a in resp.data['avertissements']),
                        resp.data['avertissements'])

    def test_une_remise_protege_l_intrus_de_la_suppression(self):
        """Prix catalogue MAIS remise posée à la main : c'est négocié aussi."""
        self._catalogue()
        devis = self._squelette(onduleur='Onduleur hybride Deye 5kW',
                                prix_onduleur='17000')
        devis.lignes.create(
            produit=self.produits['Onduleur réseau Huawei 5kW'],
            designation='Onduleur réseau Huawei 5kW',
            quantite=Decimal('1'), prix_unitaire=Decimal('14000'),
            remise=Decimal('10'), ordre=3)

        resp = self._post(devis, layout(panels=16, kwc=8.8,
                                        scenario='avec_batterie'))
        self.assertEqual(resp.status_code, 200)
        self.assertTrue(devis.lignes.filter(
            designation='Onduleur réseau Huawei 5kW').exists())
        self.assertTrue(any('DEUX onduleurs' in a
                            for a in resp.data['avertissements']))

    # ── Les devis dont le kit ne se déduit pas d'une composition résidentielle
    def test_devis_agricole_aucun_kit_de_toiture(self):
        self._catalogue()
        devis = self._squelette()
        Devis.objects.filter(pk=devis.pk).update(
            mode_installation=Devis.ModeInstallation.AGRICOLE)
        resp = self._post(devis, layout(panels=16, kwc=8.8))
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.data['lignes_ajoutees'], 0)
        self.assertFalse(devis.lignes.filter(designation='Socles').exists())

    def test_devis_multi_villa_le_kit_n_est_pas_devine(self):
        self._catalogue()
        devis = self._squelette()
        devis.lignes.create(
            produit=self.produits['Panneau Jinko 550W'],
            designation='Panneau Jinko 550W', quantite=Decimal('4'),
            prix_unitaire=Decimal('1100'), ordre=3, groupe_index=1,
            groupe_label='Villa B')
        resp = self._post(devis, layout(panels=20, kwc=11.0))
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.data['lignes_ajoutees'], 0)
        self.assertTrue(any('chaque villa a le sien' in a
                            for a in resp.data['avertissements']),
                        resp.data['avertissements'])


# ── PVCBL — F8 : les câbles suivent la taille du calepinage ─────────────────
#
# Le panneau, la batterie et l'onduleur se resynchronisaient déjà ; les DEUX
# lignes de câble (DC solaire + terre AC), elles, restaient au métrage du
# PREMIER calepinage. Un devis ramené de 10 à 5 kWc gardait donc ses 120 m de
# câble DC — la moitié de trop, facturée pour rien. Ces tests verrouillent le
# métrage fondateur du 18/08 (60 m/palier de 5 kWc pour le DC, 25 m de base +
# 15 m/palier pour la terre) ET l'interdit : jamais une ligne câble INVENTÉE.

DESIGNATION_CABLE_DC = 'Câble solaire Nexans 6 mm² (au mètre)'
DESIGNATION_CABLE_TERRE = 'Câble de terre Nexans 6 mm² (au mètre)'


class TestSyncLayoutCables(TestCase):
    def setUp(self):
        self.company = make_company('pv18-cable')
        self.user = User.objects.create_user(
            username='pv18cableuser', password='x', role_legacy='responsable',
            company=self.company)
        self.api = auth_client(self.user)
        self.client_obj = Client.objects.create(
            company=self.company, nom='Client PV18 Câble')
        self.panneau = Produit.objects.create(
            company=self.company, nom='Panneau Jinko 550W', sku='PV18C-PAN',
            prix_vente=Decimal('1100'), prix_achat=Decimal('700'),
            quantite_stock=100)
        self.onduleur = Produit.objects.create(
            company=self.company, nom='Onduleur réseau Huawei 5kW',
            sku='PV18C-ONDR', prix_vente=Decimal('14000'),
            prix_achat=Decimal('9000'), quantite_stock=100)
        self.cable_dc = Produit.objects.create(
            company=self.company, nom=DESIGNATION_CABLE_DC, sku='PV18C-CDC',
            prix_vente=Decimal('12'), prix_achat=Decimal('8'),
            quantite_stock=1000)
        self.cable_terre = Produit.objects.create(
            company=self.company, nom=DESIGNATION_CABLE_TERRE,
            sku='PV18C-CTE', prix_vente=Decimal('9'), prix_achat=Decimal('6'),
            quantite_stock=1000)
        self.compteur = 0

    def _devis(self, *, panneaux=18, cable_dc_m=None, cable_terre_m=None,
               ref=None):
        self.compteur += 1
        devis = Devis.objects.create(
            company=self.company,
            reference=ref or f'DEV-PV18-CABLE-{self.compteur}',
            client=self.client_obj, statut=Devis.Statut.BROUILLON,
            created_by=self.user)
        devis.lignes.create(
            produit=self.panneau, designation='Panneau Jinko 550W',
            quantite=Decimal(str(panneaux)), prix_unitaire=Decimal('1100'),
            ordre=1)
        devis.lignes.create(
            produit=self.onduleur, designation='Onduleur réseau Huawei 5kW',
            quantite=Decimal('1'), prix_unitaire=Decimal('14000'), ordre=2)
        if cable_dc_m is not None:
            devis.lignes.create(
                produit=self.cable_dc, designation=DESIGNATION_CABLE_DC,
                quantite=Decimal(str(cable_dc_m)), prix_unitaire=Decimal('12'),
                ordre=3)
        if cable_terre_m is not None:
            devis.lignes.create(
                produit=self.cable_terre, designation=DESIGNATION_CABLE_TERRE,
                quantite=Decimal(str(cable_terre_m)), prix_unitaire=Decimal('9'),
                ordre=4)
        return devis

    def _post(self, devis, corps):
        return self.api.post(
            f'/api/django/ventes/devis/{devis.id}/sync-layout/',
            corps, format='json')

    def test_sync_10_vers_5_kwc_ajuste_les_deux_cables(self):
        """Le cas F8 littéral : 10 kWc (2 paliers, 120 m DC / 55 m terre)
        ramené à 5 kWc (1 palier) par une toiture plus petite — les DEUX
        lignes de câble suivent : 120 → 60, 55 → 40."""
        devis = self._devis(panneaux=18, cable_dc_m=120, cable_terre_m=55)
        resp = self._post(devis, layout(panels=9, kwc=5.0))
        self.assertEqual(resp.status_code, 200, resp.content)
        self.assertEqual(
            int(devis.lignes.get(designation=DESIGNATION_CABLE_DC).quantite),
            60)
        self.assertEqual(
            int(devis.lignes.get(
                designation=DESIGNATION_CABLE_TERRE).quantite),
            40)

    def test_sync_5_vers_10_kwc_augmente_les_deux_cables(self):
        """Sens inverse : une toiture agrandie fait MONTER le métrage,
        60 → 120 et 40 → 55."""
        devis = self._devis(panneaux=9, cable_dc_m=60, cable_terre_m=40)
        resp = self._post(devis, layout(panels=18, kwc=10.0))
        self.assertEqual(resp.status_code, 200, resp.content)
        self.assertEqual(
            int(devis.lignes.get(designation=DESIGNATION_CABLE_DC).quantite),
            120)
        self.assertEqual(
            int(devis.lignes.get(
                designation=DESIGNATION_CABLE_TERRE).quantite),
            55)

    def test_cable_absent_n_est_jamais_invente(self):
        """Un devis SANS ligne de câble n'en gagne pas une par la
        resynchro : seules les lignes AUTO-COMPOSÉES déjà présentes sont
        ajustées, jamais créées ici (PVHEAL/composition_residentielle est
        hors périmètre de ce chemin)."""
        devis = self._devis(panneaux=18, cable_dc_m=None, cable_terre_m=None)
        resp = self._post(devis, layout(panels=9, kwc=5.0))
        self.assertEqual(resp.status_code, 200, resp.content)
        self.assertFalse(
            devis.lignes.filter(designation__icontains='Câble').exists())

    def test_compte_de_panneaux_inchange_les_cables_ne_bougent_pas(self):
        """Aucun écart de calepinage (même compte de panneaux) : les câbles
        ne sont PAS recalculés — seul un vrai changement de panneaux
        déclenche la resynchro câble."""
        devis = self._devis(panneaux=18, cable_dc_m=120, cable_terre_m=55)
        resp = self._post(devis, layout(panels=18, kwc=10.0))
        self.assertEqual(resp.status_code, 200, resp.content)
        self.assertEqual(
            int(devis.lignes.get(designation=DESIGNATION_CABLE_DC).quantite),
            120)
        self.assertEqual(
            int(devis.lignes.get(
                designation=DESIGNATION_CABLE_TERRE).quantite),
            55)

    def test_cable_deja_au_bon_metrage_n_est_pas_recompte_en_modifie(self):
        """Le câble DÉJÀ au métrage cible ne doit pas gonfler
        ``lignes_modifiees`` — l'ajustement est un no-op silencieux."""
        devis = self._devis(panneaux=18, cable_dc_m=60, cable_terre_m=40)
        resp = self._post(devis, layout(panels=9, kwc=5.0))
        self.assertEqual(resp.status_code, 200, resp.content)
        # Seule la ligne panneau a bougé (18 → 9) : aucun câble.
        self.assertEqual(
            int(devis.lignes.get(designation=DESIGNATION_CABLE_DC).quantite),
            60)
        self.assertEqual(
            int(devis.lignes.get(
                designation=DESIGNATION_CABLE_TERRE).quantite),
            40)
        # lignes_modifiees ne compte QUE le panneau : les deux câbles étaient
        # déjà au métrage cible, donc chacun est un no-op (jamais compté).
        self.assertEqual(resp.data['lignes_modifiees'], 1)
