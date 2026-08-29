# -*- coding: utf-8 -*-
"""QJR19 (29/08/2026) — le PDF pro-forma cesse d'être une DEUXIÈME arithmétique
monétaire client, et ne brûle plus de numéro PF.

DÉCISION FONDATEUR D1 du 29/08/2026 : l'endpoint pro-forma est CONSERVÉ, jamais
retiré — c'est son ARGENT qui est recâblé.

CE QUI ÉTAIT FAUX.
  * ``templates/pdf/proforma.html`` imprimait ``Devis.total_ht``/``total_ttc``,
    qui ignorent ``remise_globale`` ET somment les DEUX options d'un devis à
    deux paniers : un montant qui n'existe dans aucun autre document.
  * le gabarit itérait ``devis.lignes.all()`` et formatait ``prix_unitaire`` :
    une ligne de section/note (sans prix) faisait PLANTER le rendu (XSAL14) ;
  * une ligne optionnelle non activée était imprimée avec son total alors
    qu'elle est hors des totaux (XSAL5).
  * le ``ProformaDocument`` et sa référence ``PF-`` étaient créés AVANT le
    rendu : un rendu qui échouait consommait quand même le numéro.

Run :
    powershell -File scripts/test-backend.ps1 -RestoreDb \\
        -Modules "apps.ventes.tests.test_qjr_proforma"
"""
from decimal import Decimal
from unittest import mock

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.utils import timezone
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from apps.crm.models import Client
from apps.stock.models import Produit
from apps.ventes.models import Devis, LigneDevis, ProformaDocument
from apps.ventes.utils.options import AVEC_BATTERIE, option_totaux
from authentication.models import Company

User = get_user_model()
MOIS = timezone.now().strftime('%Y%m')


class _ProformaBase(TestCase):
    """Devis REMISÉ à DEUX options, avec une ligne de section ET une ligne
    optionnelle non activée — les trois défauts dans un seul devis."""

    def setUp(self):
        self.company, _ = Company.objects.get_or_create(
            slug='qjr19-co', defaults={'nom': 'QJR19 Co'})
        self.client_obj = Client.objects.create(
            company=self.company, nom='Proforma', prenom='QJR19',
            email='qjr19@example.com', telephone='+212600000093',
            adresse='Casablanca')
        self.admin = User.objects.create_user(
            username='qjr19_admin', password='x', role_legacy='admin',
            company=self.company)
        self.api = APIClient()
        self.api.credentials(
            HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(self.admin)}')
        self.devis = self._devis()

    def _produit(self, nom, prix):
        return Produit.objects.create(
            company=self.company, nom=nom, prix_vente=Decimal(str(prix)),
            quantite_stock=100, tva=Decimal('20.00'))

    def _ligne(self, designation, *, quantite=1, prix=0, variante='',
               optionnelle=False, type_ligne='produit', produit=True):
        return LigneDevis.objects.create(
            devis=self.devis,
            produit=self._produit(designation, prix) if produit else None,
            designation=designation,
            quantite=Decimal(str(quantite)) if quantite is not None else None,
            prix_unitaire=Decimal(str(prix)) if prix is not None else None,
            remise=Decimal('0'), taux_tva=Decimal('20.00'),
            variante=variante, optionnelle=optionnelle,
            type_ligne=type_ligne)

    def _devis(self):
        devis = Devis.objects.create(
            company=self.company, reference=f'DEV-{MOIS}-0001',
            client=self.client_obj, statut=Devis.Statut.ENVOYE,
            taux_tva=Decimal('20.00'),
            remise_globale=Decimal('10.00'))
        self.devis = devis
        # Option « sans batterie » : 8 panneaux + onduleur réseau.
        self._ligne('Panneau Jinko 550W (sans)', quantite=8, prix=1000,
                    variante='sans')
        self._ligne('Onduleur réseau Huawei 5kW Monophasé', prix=5000,
                    variante='sans')
        # Option « avec batterie » : 10 panneaux + hybride + batterie.
        self._ligne('Panneau Jinko 550W (avec)', quantite=10, prix=1000,
                    variante='avec')
        self._ligne('Onduleur hybride Deye 5kW Monophasé', prix=7000,
                    variante='avec')
        self._ligne('Batterie Dyness 10 kWh', prix=12000, variante='avec')
        # Ligne COMMUNE (les deux paniers).
        self._ligne('Transport et mise en service', prix=1000)
        # XSAL14 — ligne de SECTION : ni produit, ni quantité, ni prix.
        self._ligne('Prestations complémentaires', quantite=None, prix=None,
                    type_ligne='section', produit=False)
        # XSAL5 — ligne OPTIONNELLE non activée : hors des totaux.
        self._ligne('Extension de garantie 10 ans', prix=3000,
                    optionnelle=True)
        return devis

    def _html_rendu(self):
        """HTML EXACT envoyé à WeasyPrint (le rendu PDF lui-même n'est pas le
        sujet : le défaut vivait dans le gabarit et dans les nombres)."""
        from apps.ventes.utils import pdf as pdf_utils

        capture = {}

        def _capture(html):
            capture['html'] = html
            return b'%PDF-1.4 test'

        with mock.patch.object(pdf_utils, '_html_to_pdf', _capture):
            pdf_utils.generate_proforma_pdf(self.devis, 'PF-TEST-0001')
        return capture['html']


class ArgentCanoniqueTests(_ProformaBase):
    def test_le_total_est_celui_de_la_chaine_canonique_pas_la_somme_des_deux(self):
        """LE défaut monétaire : ``Devis.total_ttc`` somme les deux options ET
        ignore la remise globale. Le pro-forma imprime désormais le total de
        l'option AVEC (règle canonique du builder), remise comprise."""
        attendu = option_totaux(self.devis, AVEC_BATTERIE)
        # Dérivation : (10 000 + 7 000 + 12 000 + 1 000) = 30 000 HT brut,
        # −10 % = 27 000 HT net, TVA 20 % = 5 400, TTC = 32 400.
        self.assertEqual(attendu['ht_brut'], Decimal('30000.00'))
        self.assertEqual(attendu['remise'], Decimal('3000.00'))
        self.assertEqual(attendu['ht'], Decimal('27000.00'))
        self.assertEqual(attendu['ttc'], Decimal('32400.00'))

        html = self._html_rendu()
        self.assertIn('32400.00 MAD', html)
        self.assertIn('27000.00 MAD', html)
        self.assertIn('30000.00 MAD', html)
        # Le montant mensonger (somme des deux paniers, sans remise) a disparu.
        self.assertEqual(self.devis.total_ttc, Decimal('51600.00'))
        self.assertNotIn('51600.00 MAD', html)

    def test_la_remise_globale_est_visible_ligne_a_ligne(self):
        html = self._html_rendu()
        self.assertIn('Remise globale', html)
        self.assertIn('3000.00 MAD', html)

    def test_sans_remise_la_chaine_reste_lisible(self):
        """Non-régression : un devis sans remise n'affiche pas de ligne de
        remise et son TTC reste celui de l'option retenue."""
        self.devis.remise_globale = Decimal('0')
        self.devis.save(update_fields=['remise_globale'])
        html = self._html_rendu()
        self.assertNotIn('Remise globale', html)
        self.assertIn('36000.00 MAD', html)   # 30 000 HT + 20 % de TVA


class LignesImprimeesTests(_ProformaBase):
    def test_une_ligne_de_section_ne_fait_plus_planter_le_rendu(self):
        """XSAL14 — ``"%.2f"|format(None)`` sur une ligne sans prix levait."""
        html = self._html_rendu()
        self.assertNotIn('Prestations complémentaires', html)

    def test_une_ligne_optionnelle_non_activee_n_est_pas_imprimee(self):
        """XSAL5 — elle était listée avec son total alors qu'elle est hors
        des totaux : le document ne s'additionnait pas lui-même."""
        html = self._html_rendu()
        self.assertNotIn('Extension de garantie 10 ans', html)

    def test_seule_l_option_retenue_est_imprimee(self):
        html = self._html_rendu()
        self.assertIn('Panneau Jinko 550W (avec)', html)
        self.assertIn('Batterie Dyness 10 kWh', html)
        self.assertIn('Transport et mise en service', html)
        self.assertNotIn('Panneau Jinko 550W (sans)', html)
        self.assertNotIn('Onduleur réseau Huawei 5kW Monophasé', html)

    def test_l_option_acceptee_prime_quand_le_client_a_tranche(self):
        from apps.ventes.utils.options import SANS_BATTERIE

        self.devis.option_acceptee = SANS_BATTERIE
        self.devis.save(update_fields=['option_acceptee'])
        html = self._html_rendu()
        self.assertIn('Panneau Jinko 550W (sans)', html)
        self.assertNotIn('Panneau Jinko 550W (avec)', html)
        attendu = option_totaux(self.devis, SANS_BATTERIE)
        self.assertIn('%.2f MAD' % attendu['ttc'], html)


class NumeroNonBruleTests(_ProformaBase):
    URL = '/api/django/ventes/devis/%s/proforma-pdf/'

    def test_un_rendu_qui_leve_ne_cree_aucun_document(self):
        """Second volet de D1 : la séquence PF ne doit pas avancer pour un
        document qui n'a jamais existé."""
        with mock.patch('apps.ventes.utils.pdf.generate_proforma_pdf',
                        side_effect=RuntimeError('gabarit cassé')):
            resp = self.api.post(self.URL % self.devis.id, {}, format='json')
        self.assertEqual(resp.status_code, 500, resp.content[:400])
        self.assertEqual(ProformaDocument.objects.count(), 0)

    def test_la_sequence_reste_intacte_apres_un_echec(self):
        with mock.patch('apps.ventes.utils.pdf.generate_proforma_pdf',
                        side_effect=RuntimeError('gabarit cassé')):
            self.api.post(self.URL % self.devis.id, {}, format='json')
        resp = self.api.post(self.URL % self.devis.id, {}, format='json')
        self.assertEqual(resp.status_code, 200, resp.content[:400])
        proforma = ProformaDocument.objects.get()
        self.assertTrue(proforma.reference.endswith('-0001'),
                        'numéro brûlé : %s' % proforma.reference)

    def test_le_numero_imprime_est_celui_enregistre(self):
        resp = self.api.post(self.URL % self.devis.id, {}, format='json')
        self.assertEqual(resp.status_code, 200, resp.content[:400])
        proforma = ProformaDocument.objects.get()
        self.assertEqual(resp['Content-Disposition'],
                         'inline; filename="%s.pdf"' % proforma.reference)

    def test_le_devis_a_deux_options_rend_sans_planter_de_bout_en_bout(self):
        """Le chemin COMPLET (WeasyPrint compris) sur le devis piégé."""
        resp = self.api.post(self.URL % self.devis.id, {}, format='json')
        self.assertEqual(resp.status_code, 200, resp.content[:400])
        self.assertEqual(resp['Content-Type'], 'application/pdf')
