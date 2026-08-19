"""QG2 — Le cache d'idempotence du rendu PDF doit refléter les éditions.

Avant QG2, la signature de rendu était keyée sur (devis_id, pdf_options)
uniquement : après un « Éditer » (lignes/remise changées), les MÊMES options
renvoyaient l'ANCIEN PDF depuis MinIO. On intègre désormais une empreinte du
CONTENU du devis (`_content_version`) à la signature :

  * édition → la signature change (cache raté → re-rendu, PDF à jour) ;
  * contenu inchangé → la signature reste stable (cache conservé → pas de
    re-rendu inutile).

Ce module teste les fonctions PURES de signature (aucune infra MinIO/Celery
requise) : c'est ce qui gouverne le hit/miss du cache.
"""
from decimal import Decimal
from unittest import mock

from django.test import TestCase

from authentication.models import Company
from apps.crm.models import Client
from apps.stock.models import Produit
from apps.ventes.models import Devis, LigneDevis
from apps.ventes.tasks import _content_version, _render_signature


class RenderSignatureTests(TestCase):
    def setUp(self):
        self.company = Company.objects.create(nom='QG2 Co', slug='qg2-co')
        self.client_obj = Client.objects.create(
            company=self.company, nom='Client QG2')
        self.produit = Produit.objects.create(
            company=self.company, nom='Panneau 550W', sku='PV-550',
            prix_vente=Decimal('1000'))
        self.devis = Devis.objects.create(
            company=self.company, reference='DEV-QG2-0001',
            client=self.client_obj, statut=Devis.Statut.BROUILLON)
        self.ligne = LigneDevis.objects.create(
            devis=self.devis, produit=self.produit, designation='Panneau',
            quantite=Decimal('10'), prix_unitaire=Decimal('1000'),
            taux_tva=Decimal('20'))
        self.opts = {'pdf_mode': 'full'}

    def test_unchanged_devis_keeps_stable_signature(self):
        """À contenu inchangé, la signature est stable → cache conservé."""
        sig1 = _render_signature(self.devis.id, self.opts)
        sig2 = _render_signature(self.devis.id, self.opts)
        self.assertEqual(sig1, sig2)
        self.assertTrue(_content_version(self.devis.id))

    def test_editing_line_quantity_changes_signature(self):
        """Éditer une quantité change la signature → cache raté → re-rendu."""
        sig_before = _render_signature(self.devis.id, self.opts)
        self.ligne.quantite = Decimal('12')
        self.ligne.save(update_fields=['quantite'])
        sig_after = _render_signature(self.devis.id, self.opts)
        self.assertNotEqual(sig_before, sig_after)

    def test_editing_line_price_changes_signature(self):
        sig_before = _render_signature(self.devis.id, self.opts)
        self.ligne.prix_unitaire = Decimal('1100')
        self.ligne.save(update_fields=['prix_unitaire'])
        sig_after = _render_signature(self.devis.id, self.opts)
        self.assertNotEqual(sig_before, sig_after)

    def test_adding_and_removing_line_changes_signature(self):
        sig0 = _render_signature(self.devis.id, self.opts)
        extra = LigneDevis.objects.create(
            devis=self.devis, produit=self.produit, designation='Onduleur',
            quantite=Decimal('1'), prix_unitaire=Decimal('5000'),
            taux_tva=Decimal('20'))
        sig1 = _render_signature(self.devis.id, self.opts)
        self.assertNotEqual(sig0, sig1)
        extra.delete()
        sig2 = _render_signature(self.devis.id, self.opts)
        self.assertEqual(sig0, sig2)  # retour au contenu d'origine

    def test_changing_global_discount_changes_signature(self):
        sig_before = _render_signature(self.devis.id, self.opts)
        self.devis.remise_globale = Decimal('10')
        self.devis.save(update_fields=['remise_globale'])
        sig_after = _render_signature(self.devis.id, self.opts)
        self.assertNotEqual(sig_before, sig_after)

    def test_different_pdf_options_still_differ(self):
        """Les options de format restent discriminantes (comportement conservé)."""
        sig_full = _render_signature(self.devis.id, {'pdf_mode': 'full'})
        sig_one = _render_signature(self.devis.id, {'pdf_mode': 'onepage'})
        self.assertNotEqual(sig_full, sig_one)


class RenderSignatureRoofLayoutTests(TestCase):
    """PVFRESH (résidu, fondateur 19/08/2026) — ``_content_version`` lisait
    les champs du devis à la main et OUBLIAIT ``roof_layout`` : rejouer le
    calepinage 3D SANS toucher une ligne ne changeait donc pas la signature
    Celery, alors que le PDF servi change bien (PVUNI — un devis sans ligne
    panneau sert son kWc depuis ``roof_layout.result.kwc``). La correction
    réutilise l'EXACTE empreinte PVFRESH (``build_quote_data`` +
    ``empreinte_donnees_pdf``, la même que ``Devis.pdf_render_meta``) plutôt
    qu'une seconde dérivation : ce module le verrouille sur un devis SANS
    ligne panneau, où le calepinage seul pilote le kWc servi."""

    def setUp(self):
        self.company = Company.objects.create(
            nom='QG2 Layout Co', slug='qg2-layout-co')
        self.client_obj = Client.objects.create(
            company=self.company, nom='Client QG2 Layout')
        self.produit = Produit.objects.create(
            company=self.company, nom='Structure acier', sku='PV-STR',
            prix_vente=Decimal('500'))
        self.devis = Devis.objects.create(
            company=self.company, reference='DEV-QG2-LAYOUT-0001',
            client=self.client_obj, statut=Devis.Statut.BROUILLON,
            roof_layout={'result': {'kwc': 6.6}})
        # Aucune ligne PANNEAU : le kWc servi vient donc du calepinage seul
        # (PVUNI — repli quand le devis ne porte aucune ligne panneau).
        LigneDevis.objects.create(
            devis=self.devis, produit=self.produit, designation='Structure',
            quantite=Decimal('1'), prix_unitaire=Decimal('500'),
            taux_tva=Decimal('20'))
        self.opts = {'pdf_mode': 'full'}

    def test_replaying_the_layout_changes_the_signature(self):
        """Rejouer le calepinage (autre kWc) invalide désormais le cache Celery."""
        sig_before = _render_signature(self.devis.id, self.opts)
        self.devis.roof_layout = {'result': {'kwc': 9.9}}
        self.devis.save(update_fields=['roof_layout'])
        sig_after = _render_signature(self.devis.id, self.opts)
        self.assertNotEqual(sig_before, sig_after)

    def test_unchanged_layout_keeps_stable_signature(self):
        """À calepinage inchangé, la signature reste stable (cache conservé)."""
        sig1 = _render_signature(self.devis.id, self.opts)
        sig2 = _render_signature(self.devis.id, self.opts)
        self.assertEqual(sig1, sig2)


class LEmpreinteNeSeffondreJamaisSurLaConstanteVide(TestCase):
    """RVCEL2 — l'empreinte de contenu ne doit JAMAIS retomber sur ``''``.

    Le partage d'empreinte (PVFRESH/RVCEL) avait été posé sous un
    ``except Exception: return ''``. Or le moteur REFUSE (règle dure) de bâtir
    le format « full » d'un devis dont aucune option ne porte d'onduleur — un
    devis de structure, d'accessoires ou de pompage, c'est-à-dire un cas
    banal. L'erreur était avalée, l'empreinte devenait la CONSTANTE ``''``, et
    la signature de rendu redevenait keyée sur les seules options : le cache
    servait de nouveau l'ANCIEN PDF après une édition — exactement le défaut
    que QG2 existe pour empêcher, désormais en silence et pour toujours.

    Ce module verrouille les trois issues : refus déclaré du moteur, empreinte
    de rendu indisponible, erreur inattendue. Dans AUCUNE, deux états
    différents d'un devis ne partagent une empreinte vide.
    """

    def setUp(self):
        self.company = Company.objects.create(
            nom='RVCEL2 Co', slug='rvcel2-co')
        self.client_obj = Client.objects.create(
            company=self.company, nom='Client RVCEL2')
        self.produit = Produit.objects.create(
            company=self.company, nom='Structure acier', sku='RV-STR',
            prix_vente=Decimal('500'))
        # AUCUN onduleur : le moteur refuse le format « full » pour ce devis.
        self.devis = Devis.objects.create(
            company=self.company, reference='DEV-RVCEL2-0001',
            client=self.client_obj, statut=Devis.Statut.BROUILLON)
        self.ligne = LigneDevis.objects.create(
            devis=self.devis, produit=self.produit, designation='Structure',
            quantite=Decimal('4'), prix_unitaire=Decimal('500'),
            taux_tva=Decimal('20'))

    def _empreintes_des_deux_etats(self, options=None):
        """Empreintes AVANT et APRÈS une édition réelle du devis."""
        avant = _content_version(self.devis.id, options)
        self.ligne.quantite = Decimal('9')
        self.ligne.save(update_fields=['quantite'])
        apres = _content_version(self.devis.id, options)
        return avant, apres

    def _assert_jamais_vide_et_discriminante(self, avant, apres):
        self.assertTrue(avant, "empreinte AVANT vide : le cache retombe sur "
                               "les seules options → PDF périmé")
        self.assertTrue(apres, "empreinte APRÈS vide : le cache retombe sur "
                               "les seules options → PDF périmé")
        self.assertNotEqual(
            avant, apres,
            "deux états différents du devis partagent la même empreinte : "
            "l'édition ne casse plus le cache de rendu")

    def test_un_devis_sans_onduleur_garde_une_empreinte_pleine(self):
        """Le cas EXACT du refus moteur : empreinte pleine et discriminante."""
        self._assert_jamais_vide_et_discriminante(
            *self._empreintes_des_deux_etats({'pdf_mode': 'full'}))

    def test_options_par_defaut_aussi(self):
        """``pdf_options=None`` vaut « full » (défaut) — même garantie."""
        self._assert_jamais_vide_et_discriminante(
            *self._empreintes_des_deux_etats())

    def test_empreinte_de_rendu_indisponible_repli_qui_varie_encore(self):
        """Empreinte de rendu ``None`` → repli sur l'état stocké, pas ``''``."""
        with mock.patch('apps.ventes.quote_engine.empreinte_donnees_pdf',
                        return_value=None):
            avant, apres = self._empreintes_des_deux_etats(
                {'pdf_mode': 'onepage'})
        self._assert_jamais_vide_et_discriminante(avant, apres)

    def test_le_repli_reste_stable_a_contenu_inchange(self):
        """Le repli garde le bénéfice du cache : contenu inchangé ⇒ stable.

        Verrouille aussi la raison d'être de ``_CHAMPS_DE_RENDU`` : le tout
        premier ``build_quote_data`` d'une société crée son profil, ce qui
        remet à '' le ``fichier_pdf`` de ses devis. Un repli qui empreindrait
        les champs de SORTIE du rendu changerait donc entre deux appels
        strictement identiques — cache raté en boucle, sans qu'une seule
        donnée du devis ait bougé.
        """
        with mock.patch('apps.ventes.quote_engine.empreinte_donnees_pdf',
                        return_value=None):
            self.assertEqual(_content_version(self.devis.id),
                             _content_version(self.devis.id))

    def test_une_erreur_inattendue_remonte_au_lieu_de_setre_avalee(self):
        """Aucune erreur inconnue n'est avalée : elle remonte, bruyamment.

        Les appelants (``_idempotent_cached_key``/``_remember_render``) la
        traitent comme « pas de cache » → le PDF est RE-RENDU. Une empreinte
        vide, elle, aurait figé le cache sur un PDF périmé.
        """
        with mock.patch('apps.ventes.quote_engine.build_quote_data',
                        side_effect=RuntimeError('moteur cassé')):
            with self.assertRaises(RuntimeError):
                _content_version(self.devis.id, {'pdf_mode': 'onepage'})

    def test_une_erreur_inattendue_ne_fige_pas_le_cache_de_rendu(self):
        """Bout en bout : moteur cassé ⇒ aucune clé réutilisée (re-rendu)."""
        from apps.ventes.tasks import _idempotent_cached_key
        with mock.patch('apps.ventes.quote_engine.build_quote_data',
                        side_effect=RuntimeError('moteur cassé')):
            self.assertIsNone(
                _idempotent_cached_key(self.devis.id, {'pdf_mode': 'full'}))
