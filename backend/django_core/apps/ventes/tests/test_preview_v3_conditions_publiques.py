"""PREVIEW-V3 (16/09/2026) — ce que la proposition dit AVANT la signature.

Jusqu'ici le client lisait un prix, puis découvrait l'acompte, l'échéance de
validité et les conditions générales APRÈS avoir signé (ou seulement dans le
PDF). Cinq clés additives le corrigent dans ``proposal_data`` :

* ``acompte``          — la PREMIÈRE tranche réelle (``echeancier.next_tranche``),
                         la même que l'écran de succès post-signature ;
* ``date_validite``    — l'échéance réelle (``utils.expiry.date_expiration``) ;
* ``conditions``       — les puces CGV du PDF, en texte, MÊME source ;
* ``paiement_moyens``  — constante (jamais « espèces » — art. 193 CGI) ;
* ``confirmation_email`` — vrai SEULEMENT si un e-mail partira vraiment.

Calqué sur ``test_qx33_deposit_success.py`` (le plus proche : il éprouve déjà
la tranche 1 sur le TTC remisé). Ici on éprouve la VALEUR servie au client et
les cas d'ABSENCE (clé absente, jamais ``null`` — règle `additif_vs_null` du
contrat ``contract_samples/proposal_data.json``).

Lancer :
    docker compose exec django_core python manage.py test \
        apps.ventes.tests.test_preview_v3_conditions_publiques -v 2
"""
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings
from django.utils import timezone
from rest_framework.test import APIClient

from authentication.models import Company
from apps.crm.models import Client
from apps.ventes.models import Devis, LigneDevis, ShareLink

User = get_user_model()
MONTH = timezone.now().strftime('%Y%m')


@override_settings(CACHES={'default': {
    'BACKEND': 'django.core.cache.backends.locmem.LocMemCache'}})
class PreviewV3ConditionsPubliquesTests(TestCase):
    def setUp(self):
        self.company = Company.objects.create(nom='PV3 Co')
        self.seller = User.objects.create_user(
            username='pv3_seller', password='x', role_legacy='commercial',
            company=self.company)
        self.client_obj = Client.objects.create(
            company=self.company, nom='Client', prenom='PV3',
            telephone='+212600000073', email='client.pv3@example.com')
        self.devis = self._devis('PV3001')
        self.link = ShareLink.for_devis(self.devis)
        self.api = APIClient()

    # ── fixtures ────────────────────────────────────────────────────────
    def _produit(self):
        from apps.stock.models import Produit
        return Produit.objects.create(
            company=self.company, nom='Panneau PV3', sku='PV3-PANNEAU',
            prix_vente=Decimal('1000'), quantite_stock=100)

    def _devis(self, suffixe, avec_lignes=True, client=None):
        devis = Devis.objects.create(
            company=self.company, reference=f'DEV-{MONTH}-{suffixe}',
            client=self.client_obj if client is None else client,
            statut=Devis.Statut.ENVOYE, taux_tva=Decimal('20'),
            remise_globale=Decimal('10'), created_by=self.seller)
        if avec_lignes:
            LigneDevis.objects.create(
                devis=devis, produit=self._produit(), designation='Panneau',
                quantite=Decimal('10'), prix_unitaire=Decimal('1000'),
                remise=Decimal('0'))
        return devis

    def _payload(self, link=None):
        lien = link or self.link
        resp = self.api.get(
            f'/api/django/public/proposal/{lien.token}/data/')
        self.assertEqual(resp.status_code, 200, resp.data)
        return resp.data

    # ── acompte ─────────────────────────────────────────────────────────
    def test_acompte_porte_le_montant_reel_de_la_premiere_tranche(self):
        """10 000 HT − 10 % = 9 000 ; TTC 10 800 ; acompte 30 % = 3 240."""
        data = self._payload()
        self.assertIn('acompte', data)
        self.assertEqual(data['acompte']['ttc'], '3240.00')
        self.assertEqual(Decimal(data['acompte']['pourcentage']),
                         Decimal('30'))
        self.assertTrue(data['acompte']['libelle'].strip())

    def test_acompte_est_le_meme_chiffre_avant_et_apres_signature(self):
        """La page et l'écran de succès lisent LE MÊME helper — donc jamais
        deux acomptes pour un seul devis."""
        avant = self._payload()['acompte']
        resp = self.api.post(
            f'/api/django/public/proposal/{self.link.token}/accept/',
            {'nom': 'Client PV3', 'consent_esign': True}, format='json')
        self.assertEqual(resp.status_code, 200, resp.data)
        apres = resp.data['paiement']
        self.assertEqual(avant['ttc'], apres['acompte_ttc'])
        self.assertEqual(avant['pourcentage'], apres['pourcentage'])

    def test_acompte_jamais_servi_a_null_sur_un_devis_sans_ligne(self):
        """Règle `additif_vs_null` du contrat : une clé additive sans rien à
        montrer est ABSENTE — jamais `"acompte": null`. Un devis sans ligne
        n'annonce donc aucun chiffre trompeur."""
        vide = self._devis('PV3002', avec_lignes=False)
        data = self._payload(ShareLink.for_devis(vide))
        self.assertIsNotNone(
            data.get('acompte', {}),
            "une clé additive ne vaut JAMAIS `null` : elle est absente")
        if 'acompte' in data:
            self.assertEqual(Decimal(data['acompte']['ttc']),
                             Decimal('0.00'),
                             'un devis sans ligne ne peut pas porter '
                             "d'acompte non nul")

    # ── date de validité ────────────────────────────────────────────────
    def test_date_validite_est_la_date_reelle_en_iso(self):
        from apps.ventes.utils.expiry import date_expiration
        data = self._payload()
        self.assertIn('date_validite', data)
        self.assertEqual(data['date_validite'],
                         date_expiration(self.devis).isoformat())

    def test_date_validite_suit_la_date_posee_sur_le_devis(self):
        import datetime
        self.devis.date_validite = datetime.date(2030, 3, 15)
        self.devis.save(update_fields=['date_validite'])
        self.assertEqual(self._payload()['date_validite'], '2030-03-15')

    # ── conditions générales ────────────────────────────────────────────
    def test_conditions_reprennent_les_puces_cgv_du_pdf(self):
        """MÊME source que le PDF : les gabarits du moteur, substitués et
        dé-échappés. Aucune phrase réécrite à la main côté web."""
        data = self._payload()
        self.assertIn('conditions', data)
        conditions = data['conditions']
        self.assertTrue(conditions, 'aucune condition servie')
        self.assertTrue(all(isinstance(c, str) and c.strip()
                            for c in conditions))
        joint = ' | '.join(conditions)
        self.assertIn('Acompte à la commande', joint)
        self.assertIn('à la réception du matériel', joint)
        self.assertIn('après la mise en marche', joint)
        # Dé-échappées : plus aucune entité HTML ne part vers le JSON.
        self.assertNotIn('&#', joint)

    def test_conditions_reprennent_les_pourcentages_de_la_societe(self):
        """Une société qui change son échéancier change les conditions
        affichées — le texte n'est pas figé à 30/60/10."""
        from apps.parametres.models import CompanyProfile
        profil = CompanyProfile.get(self.company)
        profil.payment_terms = {
            'residentiel': {'acompte': 40, 'materiel': 50, 'solde': 10}}
        profil.save(update_fields=['payment_terms'])
        joint = ' | '.join(self._payload()['conditions'])
        self.assertIn('40', joint)
        self.assertIn('50', joint)

    # ── moyens de paiement ──────────────────────────────────────────────
    def test_paiement_moyens_ne_propose_jamais_les_especes(self):
        """Art. 193 CGI : au-delà de 20 000 MAD l'espèce expose LE VENDEUR à
        6 % d'amende — elle n'est donc jamais proposée au client."""
        data = self._payload()
        self.assertEqual(data['paiement_moyens'], ['virement', 'cheque'])
        self.assertNotIn('especes', data['paiement_moyens'])
        self.assertNotIn('espèces', data['paiement_moyens'])

    def test_le_rib_ne_franchit_pas_la_frontiere_avant_signature(self):
        """Le RIB reste POST-signature : rien à virer tant que la commande
        n'est pas ferme."""
        data = self._payload()
        self.assertNotIn('rib', data)

    # ── confirmation e-mail ─────────────────────────────────────────────
    def test_confirmation_email_vrai_quand_le_client_a_une_adresse(self):
        self.assertIs(self._payload()['confirmation_email'], True)

    def test_confirmation_email_faux_sans_adresse(self):
        """`_send_acceptance_emails` n'envoie que `if dest:` — la page ne
        promet donc rien quand l'adresse manque (loi 31-08 art. 32)."""
        self.client_obj.email = ''
        self.client_obj.save(update_fields=['email'])
        self.assertIs(self._payload()['confirmation_email'], False)
