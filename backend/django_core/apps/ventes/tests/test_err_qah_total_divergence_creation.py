"""ERR-QAH-VENTES-TOTAL-DIVERGENCE-CREATION — UN seul total « avec batterie ».

LE CONSTAT (qa-explorer 2026-09-28, DEV-202609-0003). Un devis résidentiel
« Les deux (Sans + Avec) » de 13 lignes (onduleur réseau Huawei + onduleur
hybride Deye + batteries + Smart Meter + clé Wi-Fi) affichait TROIS totaux
TTC :

* 97 391 sur le formulaire (``optionTotalsTTC`` : panier AVEC sans retirer les
  accessoires Huawei, QF9 n'y étant appliquée que sur des lignes VARIANTÉES) ;
* 117 391,16 sur l'écran « Devis enregistré » : la réponse de
  ``POST /devis/atomic/`` était calculée AVANT que l'écran ne pose
  ``etude_params['scenario']`` (par le ``PATCH etude-params`` qui SUIT) —
  sans scénario déclaré, le noyau voit un devis mono-option et additionne les
  13 lignes, les deux onduleurs compris ;
* 94 391,16 persisté (liste / API) une fois le scénario posé : panier AVEC,
  QF9 appliquée (Smart Meter 1 800 + clé Wi-Fi 1 200 = les 3 000 d'écart).

LE CORRECTIF CÔTÉ SERVEUR : ``atomic`` accepte les CHOIX de l'écran
(``etude_params``, écrits par l'unique écrivain ``etude_schema.ecrire`` sous la
MÊME transaction que le devis et ses lignes) — la réponse de création porte
donc déjà le total canonique, identique à celui relu ensuite.

ROUGE AVANT LE CORRECTIF : ``etude_params`` était ignoré en silence par
``DevisWriteSerializer`` (champ en lecture seule), donc la réponse atomique
valait la somme des 13 lignes — ``114092.00`` sur la composition ci-dessous
(l'équivalent du 117 391,16 observé) — au lieu de ``91292.00``. Depuis
ARRONDI-100 (02/10/2026) les totaux sont au palier de 100 MAD : le défaut
vaudrait ``114000.00`` au lieu de ``91200.00``.
"""
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from authentication.models import Company
from apps.crm.models import Client
from apps.stock.models import Produit

User = get_user_model()

LES_DEUX = 'Les deux (Sans + Avec)'

# (désignation, sku, quantité, prix unitaire HT, taux TVA)
COMPOSITION = [
    ('Panneau solaire 710W', 'QAH-PV', '13', '1000', '10'),
    ('Onduleur réseau Huawei 10kW', 'QAH-OND-RES', '1', '16500', '20'),
    ('Onduleur hybride Deye 10kW', 'QAH-OND-HYB', '1', '23000', '20'),
    ('Batterie Dyness 5 kWh', 'QAH-BAT', '2', '11500', '20'),
    ('Smart Meter', 'QAH-SM', '1', '1500', '20'),
    ('Wifi Dongle', 'QAH-WIFI', '1', '1000', '20'),
    ('Structures aluminium', 'QAH-STR', '13', '700', '20'),
    ('Socles', 'QAH-SOC', '26', '60', '20'),
    ('Câble solaire Nexans 6 mm² (au mètre)', 'QAH-CAB-DC', '60', '12', '20'),
    ('Câble de terre Nexans 6 mm² (au mètre)', 'QAH-CAB-T', '40', '12', '20'),
    ('Tableau De Protection AC/DC', 'QAH-TAB', '1', '1500', '20'),
    ('Installation', 'QAH-INST', '1', '4000', '20'),
    ('Transport', 'QAH-TRANS', '1', '800', '20'),
]

# Dérivés à la main de COMPOSITION (HT par taux → TVA → TTC, aucune remise) :
#   toutes les lignes : 13 000 × 1,10 + 83 160 × 1,20 = 114 092,00
#   panier AVEC (sans onduleur réseau ; onduleur Deye ⇒ QF9 retire Smart
#   Meter + clé Wi-Fi) : 14 300 + 64 160 × 1,20 = 91 292,00
#   panier SANS (sans hybride ni batterie ; Huawei ⇒ accessoires gardés) :
#   14 300 + 37 160 × 1,20 = 58 892,00
# ARRONDI-100 : chaque total est ramené au palier de 100 MAD inférieur (baisse
# de HT de 76,67 sur les trois paniers ; les prix des lignes ne bougent pas).
# Même chiffres que le jumeau écran ``optionTotalsScenario.test.jsx``.
TOTAL_TOUTES_LIGNES = Decimal('114000.00')    # ARRONDI-100 : 114092 → 114000
TOTAL_AVEC = Decimal('91200.00')              # ARRONDI-100 : 91292 → 91200
TOTAL_SANS = Decimal('58800.00')              # ARRONDI-100 : 58892 → 58800


class TotalUniqueCreationTests(TestCase):

    def setUp(self):
        self.company, _ = Company.objects.get_or_create(
            slug='qah-total-co', defaults={'nom': 'QAH Total Co'})
        self.user = User.objects.create_user(
            username='qah_total_resp', password='x',
            role_legacy='responsable', company=self.company)
        self.api = APIClient()
        self.api.credentials(
            HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(self.user)}')
        self.client_obj = Client.objects.create(
            company=self.company, nom='Alaoui', prenom='QAH',
            telephone='+212600000729')
        self.lignes = []
        for ordre, (nom, sku, qte, pu_ht, tva) in enumerate(COMPOSITION):
            produit = Produit.objects.create(
                company=self.company, nom=nom, sku=sku,
                prix_vente=Decimal(pu_ht), quantite_stock=500)
            self.lignes.append({
                'produit': produit.id, 'designation': nom, 'quantite': qte,
                'prix_unitaire': pu_ht, 'remise': '0', 'taux_tva': tva,
                'type_ligne': 'produit', 'ordre': ordre, 'variante': '',
            })

    def _creer(self, **extra):
        corps = {
            'client': self.client_obj.id, 'statut': 'brouillon',
            'taux_tva': '20', 'remise_globale': '0',
            'mode_installation': 'residentiel', 'lignes': self.lignes,
        }
        corps.update(extra)
        return self.api.post('/api/django/ventes/devis/atomic/', corps,
                             format='json')

    def test_meme_total_creation_persistance_liste(self):
        choix = {'scenario': LES_DEUX, 'recommended_option': 'Avec batterie',
                 'nombre_proprietes': None}
        resp = self._creer(etude_params=choix)
        self.assertEqual(resp.status_code, 201, resp.content)
        devis_id = resp.data['id']
        # Observé avant le correctif : '114092.00' (somme des 13 lignes) —
        # '114000.00' depuis ARRONDI-100.
        self.assertEqual(Decimal(str(resp.data['total_ttc'])), TOTAL_AVEC)
        self.assertEqual(resp.data['nb_options'], 2)
        self.assertEqual(
            Decimal(str(resp.data['total_affiche'])), TOTAL_AVEC)

        # L'écran PATCHe ensuite les mêmes choix (+ ses entrées réelles) :
        # le total ne doit plus bouger d'un centime.
        patch = self.api.patch(
            f'/api/django/ventes/devis/{devis_id}/etude-params/', choix,
            format='json')
        self.assertEqual(patch.status_code, 200, patch.content)

        detail = self.api.get(f'/api/django/ventes/devis/{devis_id}/')
        self.assertEqual(detail.status_code, 200, detail.content)
        self.assertEqual(Decimal(str(detail.data['total_ttc'])), TOTAL_AVEC)
        self.assertEqual(
            Decimal(str(detail.data['total_affiche'])), TOTAL_AVEC)
        comparaison = detail.data['comparaison_options']
        self.assertIsNotNone(comparaison)
        self.assertEqual(Decimal(str(comparaison['avec']['ttc'])), TOTAL_AVEC)
        self.assertEqual(Decimal(str(comparaison['sans']['ttc'])), TOTAL_SANS)

        liste = self.api.get('/api/django/ventes/devis/')
        self.assertEqual(liste.status_code, 200, liste.content)
        rows = liste.data.get('results', liste.data) \
            if isinstance(liste.data, dict) else liste.data
        row = next(r for r in rows if r['id'] == devis_id)
        self.assertEqual(Decimal(str(row['total_ttc'])), TOTAL_AVEC)
        self.assertEqual(Decimal(str(row['total_affiche'])), TOTAL_AVEC)

    def test_sans_choix_le_comportement_historique_est_inchange(self):
        """Un appelant qui n'envoie aucun choix (API, anciens écrans) garde la
        réponse d'hier : mono-option, toutes les lignes."""
        resp = self._creer()
        self.assertEqual(resp.status_code, 201, resp.content)
        self.assertEqual(
            Decimal(str(resp.data['total_ttc'])), TOTAL_TOUTES_LIGNES)

    def test_choix_invalide_refuse_sur_le_champ_sans_creer(self):
        from apps.ventes.models import Devis
        avant = Devis.objects.filter(company=self.company).count()
        resp = self._creer(etude_params={'cle_inconnue_qah': 1})
        self.assertEqual(resp.status_code, 400, resp.content)
        self.assertIn('etude_params', resp.data)
        self.assertEqual(
            Devis.objects.filter(company=self.company).count(), avant)

    def test_choix_non_objet_refuse_sur_le_champ(self):
        resp = self._creer(etude_params=['Les deux'])
        self.assertEqual(resp.status_code, 400, resp.content)
        self.assertIn('etude_params', resp.data)
