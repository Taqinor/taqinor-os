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

    def _devis_deux_options(self, suffixe):
        """PREVIEW-V3-FIX (C1) — un VRAI devis à deux options.

        Fixture reprise mot pour mot de ``test_qjr_solde_deux_options`` (la
        même composition, les mêmes prix) : ses totaux y sont déjà épinglés —
        37 320 TTC « sans », 68 880 TTC « avec » — donc les acomptes attendus
        ici (30 %) sont 11 196,00 et 20 664,00, eux aussi déjà assertés
        là-bas. Aucun chiffre neuf n'est inventé pour ce test.
        """
        from apps.stock.models import Produit
        devis = Devis.objects.create(
            company=self.company, reference=f'DEV-{MONTH}-{suffixe}',
            client=self.client_obj, statut=Devis.Statut.ENVOYE,
            taux_tva=Decimal('20'), created_by=self.seller,
            etude_params={'scenario': 'Les deux (Sans + Avec)'})
        for desig, qty, pu in (
                ('Onduleur réseau', '1', '11700'),
                ('Onduleur hybride', '1', '24000'),
                ('Panneau mono 550W', '14', '1100'),
                ('Batterie 5 kWh', '1', '14000'),
                ('Installation', '1', '4000')):
            produit = Produit.objects.create(
                company=self.company, nom=desig,
                sku=f'{suffixe}-{desig[:10]}',
                prix_vente=Decimal(pu), quantite_stock=100)
            LigneDevis.objects.create(
                devis=devis, produit=produit, designation=desig,
                quantite=Decimal(qty), prix_unitaire=Decimal(pu),
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
        # PREVIEW-V3-FIX (C9) — `libelle` n'est plus servi : il ne l'était
        # jamais lu, et la phrase de la page porte ses trois langues.
        self.assertNotIn('libelle', data['acompte'])

    def test_acompte_porte_un_montant_par_option_servable(self):
        """PREVIEW-V3-FIX (C1) — le client coche une option, il doit lire
        L'ACOMPTE DE CETTE OPTION. Devis mono-option : une seule entrée, du
        même montant que `ttc` (aucune option ne filtre les lignes)."""
        data = self._payload()
        montants = data['acompte']['montants']
        self.assertEqual(list(montants.values()), ['3240.00'])
        self.assertEqual(len(montants), 1)
        self.assertEqual(data['acompte']['option'], '')

    def test_acompte_porte_les_deux_montants_sur_un_devis_a_deux_options(self):
        """LE DÉFAUT C1, ÉPINGLÉ. Avant : un seul montant (celui de l'option
        effective) et la page DEVINAIT laquelle — un vendeur qui recommande
        « Sans batterie » faisait lire au client l'acompte de l'option AVEC.
        Maintenant : un montant par option, calculé par le MÊME
        ``next_tranche`` (même arrondi), et l'option de référence est dite."""
        devis = self._devis_deux_options('PV3003')
        data = self._payload(ShareLink.for_devis(devis))
        acompte = data['acompte']
        self.assertEqual(acompte['montants'], {
            'sans_batterie': '11196.00',   # 30 % de 37 320 TTC
            'avec_batterie': '20664.00',   # 30 % de 68 880 TTC
        })
        # Avant acceptation, l'ERP facture l'option du TOTAL AFFICHÉ (D9).
        self.assertEqual(acompte['option'], 'avec_batterie')
        self.assertEqual(acompte['ttc'], '20664.00')
        self.assertEqual(acompte['ttc'], acompte['montants']['avec_batterie'])

    def test_acompte_suit_loption_acceptee_une_fois_le_devis_signe(self):
        """Après acceptation de « Sans batterie », ``ttc`` bascule sur cette
        option — les DEUX montants restent servis, aucun ne se contredit."""
        devis = self._devis_deux_options('PV3004')
        devis.statut = Devis.Statut.ACCEPTE
        devis.option_acceptee = 'sans_batterie'
        devis.save(update_fields=['statut', 'option_acceptee'])
        acompte = self._payload(ShareLink.for_devis(devis))['acompte']
        self.assertEqual(acompte['option'], 'sans_batterie')
        self.assertEqual(acompte['ttc'], '11196.00')
        self.assertEqual(acompte['montants']['sans_batterie'], '11196.00')

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

    def test_les_conditions_suivent_lecheancier_negocie_du_devis(self):
        """LE DÉFAUT C3, ÉPINGLÉ. `acompte` venait de l'échéancier RÉEL du
        devis et `conditions` des pourcentages de la SOCIÉTÉ : sur un devis à
        échéancier négocié, le récap disait « Acompte de 40 % » et la puce,
        trois lignes plus bas, « Acompte à la commande : 30% ». Une seule
        source désormais — et la page ne peut plus afficher deux acomptes."""
        self.devis.echeancier = [
            {'libelle': 'Acompte', 'type': 'acompte', 'pct_or_montant': 40},
            {'libelle': 'Livraison du matériel', 'type': 'materiel',
             'pct_or_montant': 50},
            {'libelle': 'Solde', 'type': 'solde', 'pct_or_montant': 10},
        ]
        self.devis.save(update_fields=['echeancier'])
        data = self._payload()
        joint = ' | '.join(data['conditions'])
        self.assertIn('Acompte à la commande', joint)
        self.assertIn('40', joint)
        self.assertIn('50', joint)
        # LE point du correctif : UN SEUL pourcentage d'acompte à l'écran.
        self.assertEqual(Decimal(data['acompte']['pourcentage']),
                         Decimal('40'))
        self.assertNotIn('30%', joint.replace(' ', ''))

    def test_les_pourcentages_sont_ecrits_comme_on_les_lit(self):
        """« 40 », jamais « 40.00 » : les puces sont du texte client."""
        from apps.ventes.public_views import _pct_lisible
        from decimal import Decimal as D
        self.assertEqual(_pct_lisible(D('40.00')), '40')
        self.assertEqual(_pct_lisible(D('33.50')), '33,5')
        self.assertEqual(_pct_lisible(30), '30')
        self.assertEqual(_pct_lisible(30.0), '30')

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
