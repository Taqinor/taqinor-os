"""QJR135 — l'écran de confirmation lit le devis QU'IL VIENT D'ÉCRIRE.

Constat ES4 de l'audit du 30/08/2026, vérifié en code : ``accept_devis`` REBIND
son nom local sur la relecture VERROUILLÉE (``select_for_update().get(...)``),
si bien que l'objet de l'APPELANT reste celui d'AVANT. Les deux appelants
sérialisaient cette instance périmée :

  · ``public_views.proposal_accept`` — ``option_acceptee`` y valait ``''``,
    donc ``option_effective`` retombait sur AVEC_BATTERIE : **un client qui
    venait de signer « sans batterie » voyait l'acompte de l'option AVEC**,
    plus élevé — pendant que l'email, qui reçoit l'instance FRAÎCHE, annonçait
    le bon montant. ``statut`` renvoyé valait ``envoye`` et ``accepte_par_nom``
    ``''`` juste après une signature réussie ;
  · ``views/devis.accepter`` — même ``DevisSerializer(devis)`` sur l'instance
    périmée.

Jumeau exact de QJR20 (sync-layout) sur un autre chemin. Le dépôt sait faire
ailleurs : ``apps/portail/views_client.py`` fait un ``refresh_from_db``.

Lancer :
    docker compose exec django_core python manage.py test \
        apps.ventes.tests.test_qjr135_acceptation_instance_fraiche -v 2
"""
import uuid
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from apps.crm.models import Client
from apps.stock.models import Produit
from apps.ventes.domain.lignes import creer_ligne
from apps.ventes.models import Devis, EmailLog, ShareLink
from apps.ventes.utils.echeancier import next_tranche
from apps.ventes.utils.options import (
    AVEC_BATTERIE, SANS_BATTERIE, option_totaux,
)
from authentication.models import Company

User = get_user_model()

RESEAU = 'Onduleur réseau Huawei 10kW Monophasé'
HYBRIDE = 'Onduleur hybride Deye 10kW Monophasé'
BATTERIE = 'Batterie Dyness 10 kWh'
PANNEAU = 'Panneau Canadian Solar 710W'


def _montant_email(acompte):
    """Le format EXACT de ``_acceptance_deposit_block`` (espace fine, 2 déc.)."""
    return f'{acompte:,.2f}'.replace(',', ' ') + ' MAD'


class _BaseDeuxOptions(TestCase):
    """Un devis à DEUX options dont les deux paniers ne coûtent PAS pareil :
    sans cela, l'instance périmée et l'instance fraîche donneraient le même
    acompte et le test ne prouverait rien."""

    slug = 'qjr135'

    def setUp(self):
        self.company, _ = Company.objects.get_or_create(
            slug=self.slug, defaults={'nom': self.slug})
        self.user = User.objects.create_user(
            username='qjr135-%s' % self.slug, password='x',
            role_legacy='responsable', company=self.company)
        self.client_obj = Client.objects.create(
            company=self.company, nom='Client', prenom='QJR135',
            email='qjr135-%s@example.com' % self.slug)
        self.api = APIClient()
        self.api.credentials(
            HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(self.user)}')
        self._sku = 0
        self.devis = self._devis_deux_options()

    def _produit(self, nom, prix):
        self._sku += 1
        return Produit.objects.create(
            company=self.company, nom=nom,
            sku='QJR135-%d-%s' % (self._sku, self.company.pk),
            prix_vente=Decimal(prix), prix_achat=Decimal('1'),
            quantite_stock=100)

    def _devis_deux_options(self):
        devis = Devis.objects.create(
            company=self.company, reference='DEV-QJR135-%s' % self.slug[-3:],
            client=self.client_obj, statut=Devis.Statut.ENVOYE,
            taux_tva=Decimal('20'), mode_installation='residentiel',
            etude_params={'scenario': 'Les deux (Sans + Avec)'})
        # Champs PV DIVERGENTS (L-2OPT) : l'option « sans » vend 8 panneaux,
        # l'option « avec » en vend 14 — les deux totaux s'écartent nettement.
        for nom, qte, pu, variante in (
                (PANNEAU, '8', '1166.67', 'sans'),
                (PANNEAU, '14', '1166.67', 'avec'),
                (RESEAU, '1', '15000.00', ''),
                (HYBRIDE, '1', '23333.33', ''),
                (BATTERIE, '1', '25000.00', ''),
        ):
            creer_ligne(devis, produit=self._produit(nom, pu),
                        designation=nom, quantite=Decimal(qte),
                        prix_unitaire=Decimal(pu), remise=Decimal('0'),
                        variante=variante)
        return devis

    def _corps_email(self, devis):
        log = EmailLog.objects.filter(devis=devis).order_by('-id').first()
        self.assertIsNotNone(log, 'aucun email de confirmation envoyé')
        return log.corps or ''


class LesDeuxOptionsNeCoutentPasPareil(_BaseDeuxOptions):
    """Le TÉMOIN : sans écart entre les deux paniers, tout le module serait
    vert même avec l'ancienne instance périmée."""

    slug = 'qjr135-temoin'

    def test_les_totaux_des_deux_options_divergent(self):
        sans = option_totaux(self.devis, SANS_BATTERIE)['ttc']
        avec = option_totaux(self.devis, AVEC_BATTERIE)['ttc']
        self.assertNotEqual(sans, avec)
        self.assertLess(sans, avec)

    def test_sans_option_acceptee_l_argent_suit_l_option_avec(self):
        """La MÉCANIQUE du défaut : sur une instance dont ``option_acceptee``
        est vide, ``option_effective`` retombe sur AVEC_BATTERIE."""
        from apps.ventes.utils.options import option_effective

        self.assertEqual(option_effective(self.devis), AVEC_BATTERIE)


class LEcranPublicAnnonceCeQuiAEteSigne(_BaseDeuxOptions):
    """ES4 — le chemin nommé par l'audit."""

    slug = 'qjr135-public'

    def _signer_sans_batterie(self):
        link = ShareLink.objects.create(
            company=self.company, devis=self.devis, token=str(uuid.uuid4()))
        resp = self.api.post(
            f'/api/django/public/proposal/{link.token}/accept/',
            {'nom': 'M. Client', 'consent_esign': True,
             'option': 'sans_batterie'}, format='json')
        self.assertEqual(resp.status_code, 200, resp.data)
        return resp

    def test_le_statut_et_le_nom_renvoyes_sont_ceux_de_la_signature(self):
        resp = self._signer_sans_batterie()
        self.assertEqual(resp.data['statut'], Devis.Statut.ACCEPTE)
        self.assertEqual(resp.data['accepte_par_nom'], 'M. Client')

    def test_l_ecran_et_l_email_annoncent_le_MEME_acompte(self):
        resp = self._signer_sans_batterie()
        self.devis.refresh_from_db()
        self.assertEqual(self.devis.option_acceptee, SANS_BATTERIE)

        attendu = Decimal(str(next_tranche(self.devis)['ttc']))
        ecran = Decimal(resp.data['paiement']['acompte_ttc'])
        self.assertEqual(ecran, attendu)
        self.assertIn(_montant_email(attendu), self._corps_email(self.devis))

    def test_l_acompte_annonce_n_est_pas_celui_de_l_instance_perimee(self):
        """La preuve du dommage, chiffrée : on recompose EXACTEMENT ce que
        l'instance périmée (``option_acceptee`` vide) aurait servi, et on
        vérifie que l'écran ne l'annonce plus."""
        resp = self._signer_sans_batterie()
        ecran = Decimal(resp.data['paiement']['acompte_ttc'])

        self.devis.refresh_from_db()
        signe = Decimal(str(next_tranche(self.devis)['ttc']))
        perime = Devis.objects.get(pk=self.devis.pk)
        # L'état EXACT de l'objet que l'appelant gardait en main : accepté en
        # base, mais sans l'option — donc ``option_effective`` → AVEC_BATTERIE.
        perime.option_acceptee = ''
        acompte_perime = Decimal(str(next_tranche(perime)['ttc']))

        self.assertEqual(ecran, signe)
        self.assertNotEqual(
            signe, acompte_perime,
            "l'acompte de l'option AVEC est identique à celui de l'option "
            'SANS : le devis de test ne diverge plus, le témoin est mort.')


class LEcranInterneAnnonceCeQuiAEteAccepte(_BaseDeuxOptions):
    """Même défaut, autre appelant : ``views/devis.accepter``."""

    slug = 'qjr135-interne'

    def test_la_reponse_du_viewset_porte_l_etat_frais(self):
        resp = self.api.post(
            f'/api/django/ventes/devis/{self.devis.id}/accepter/',
            {'nom': 'M. Client', 'option': 'sans_batterie'}, format='json')
        self.assertEqual(resp.status_code, 200, resp.data)
        self.assertEqual(resp.data['statut'], Devis.Statut.ACCEPTE)
        self.assertEqual(resp.data['option_acceptee'], SANS_BATTERIE)
        self.assertEqual(resp.data['accepte_par_nom'], 'M. Client')
