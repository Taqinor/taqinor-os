"""QJR144 — l'empreinte du document signé couvre ce qui détermine le prix.

Constat ES12 de l'audit du 30/08/2026, vérifié en code. Le payload de
``DevisSignature.compute_content_hash`` portait ``reference|client|created|
tva(global)|remise|lignes(designation:quantite:prix_unitaire:remise)`` et ne
couvrait :

  · NI le ``taux_tva`` PAR LIGNE (``LigneDevis.taux_tva``, consommé par
    ``taux_tva_effectif`` et ``tva_par_taux``) — passer une ligne de 20 % à
    10 % change le TTC payé par le client SANS changer l'empreinte ;
  · NI ``optionnelle``, qui décide de l'entrée d'une ligne dans les totaux ;
  · NI ``option_acceptee``, qui détermine ce qui sera facturé.

Pire : une recherche sur tout ``apps/`` montrait que ``content_hash`` n'était
JAMAIS recalculé ni comparé — écrit une fois, relu seulement par des tests. Un
sceau qu'aucun code ne savait vérifier.

ATTÉNUATION VÉRIFIÉE (à préserver) : l'édition post-acceptation est déjà
refusée, donc c'était une lacune de VALEUR PROBANTE, pas une brèche ouverte.

Lancer :
    docker compose exec django_core python manage.py test \
        apps.ventes.tests.test_qjr144_empreinte_signature -v 2
"""
from decimal import Decimal

from django.test import TestCase
from django.utils import timezone

from apps.crm.models import Client
from apps.stock.models import Produit
from apps.ventes.domain.lignes import creer_ligne
from apps.ventes.models import Devis, DevisSignature
from apps.ventes.services import verifier_empreinte_signature
from authentication.models import Company


class _BaseEmpreinte(TestCase):
    slug = 'qjr144'

    def setUp(self):
        self.company, _ = Company.objects.get_or_create(
            slug=self.slug, defaults={'nom': self.slug})
        self.client_obj = Client.objects.create(
            company=self.company, nom='Client', prenom='QJR144',
            email='qjr144-%s@example.com' % self.slug)
        self.devis = Devis.objects.create(
            company=self.company, reference='DEV-QJR144-%s' % self.slug[-3:],
            client=self.client_obj, statut=Devis.Statut.ENVOYE,
            taux_tva=Decimal('20'))
        produit = Produit.objects.create(
            company=self.company, nom='Panneau 710W',
            sku='QJR144-PAN-%s' % self.company.pk,
            prix_vente=Decimal('1000'), prix_achat=Decimal('1'),
            quantite_stock=50)
        self.ligne = creer_ligne(
            self.devis, produit=produit, designation='Panneau 710W',
            quantite=Decimal('10'), prix_unitaire=Decimal('1000'),
            remise=Decimal('0'), taux_tva=Decimal('20'))

    def _sceller(self, *, version=None):
        """Pose une signature dont l'empreinte est celle du contenu ACTUEL."""
        return DevisSignature.objects.create(
            company=self.company, devis=self.devis,
            signataire_nom='M. Client', consentement_explicite=True,
            content_hash=DevisSignature.compute_content_hash(
                self.devis, version=version),
            signed_at=timezone.now())


class LePayloadCouvreCeQuiDetermineLePrix(_BaseEmpreinte):
    """ES12 — les trois données manquantes."""

    slug = 'qjr144-payload'

    def test_le_taux_de_tva_de_ligne_change_l_empreinte(self):
        """Le cas le plus démonstratif : 20 % → 10 % change le TTC du client."""
        avant = DevisSignature.compute_content_hash(self.devis)
        self.ligne.taux_tva = Decimal('10')
        self.ligne.save(update_fields=['taux_tva'])
        self.assertNotEqual(
            DevisSignature.compute_content_hash(self.devis), avant)

    def test_le_caractere_optionnel_d_une_ligne_change_l_empreinte(self):
        avant = DevisSignature.compute_content_hash(self.devis)
        self.ligne.optionnelle = True
        self.ligne.save(update_fields=['optionnelle'])
        self.assertNotEqual(
            DevisSignature.compute_content_hash(self.devis), avant)

    def test_l_option_acceptee_change_l_empreinte(self):
        avant = DevisSignature.compute_content_hash(self.devis)
        self.devis.option_acceptee = 'sans_batterie'
        self.devis.save(update_fields=['option_acceptee'])
        self.assertNotEqual(
            DevisSignature.compute_content_hash(self.devis), avant)

    def test_le_payload_ne_porte_jamais_de_prix_d_achat(self):
        """Règle #4 — préservée mot pour mot par l'extension."""
        payload = DevisSignature._payload_content_hash(self.devis)
        self.assertNotIn('prix_achat', payload)
        self.assertNotIn('marge', payload)

    def test_l_empreinte_reste_reproductible_sans_requete(self):
        """NPLUS1 — les lignes déjà chargées donnent le MÊME hash, sans
        requête : une empreinte qui changerait selon la voie de lecture serait
        invérifiable."""
        attendu = DevisSignature.compute_content_hash(self.devis)
        lignes = list(self.devis.lignes.select_related('produit').all())[::-1]
        with self.assertNumQueries(0):
            obtenu = DevisSignature.compute_content_hash(
                self.devis, lignes=lignes)
        self.assertEqual(obtenu, attendu)


class LeVerificateurDitLaVerite(_BaseEmpreinte):
    """Le sceau a enfin un lecteur."""

    slug = 'qjr144-verif'

    def test_un_contenu_inchange_est_conforme(self):
        self._sceller()
        rapport = verifier_empreinte_signature(self.devis)
        self.assertTrue(rapport['signee'])
        self.assertTrue(rapport['intacte'])
        self.assertEqual(rapport['version'], DevisSignature.CONTENT_HASH_V2)

    def test_un_taux_de_tva_de_ligne_modifie_rend_l_empreinte_ROUGE(self):
        self._sceller()
        self.ligne.taux_tva = Decimal('10')
        self.ligne.save(update_fields=['taux_tva'])

        rapport = verifier_empreinte_signature(self.devis)
        self.assertFalse(rapport['intacte'])
        self.assertIn('NE correspond PLUS', rapport['message'])

    def test_un_devis_sans_signature_le_dit(self):
        rapport = verifier_empreinte_signature(self.devis)
        self.assertFalse(rapport['signee'])
        self.assertIsNone(rapport['intacte'])

    def test_une_signature_sans_empreinte_nest_pas_declaree_falsifiee(self):
        """« On ne sait pas » n'est pas « falsifié »."""
        DevisSignature.objects.create(
            company=self.company, devis=self.devis,
            signataire_nom='M. Client', consentement_explicite=True,
            content_hash='', signed_at=timezone.now())
        rapport = verifier_empreinte_signature(self.devis)
        self.assertTrue(rapport['signee'])
        self.assertIsNone(rapport['intacte'])


class LesSignaturesDejaPoseesRestentValides(_BaseEmpreinte):
    """Le sceau est VERSIONNÉ : étendre le payload n'invalide rien."""

    slug = 'qjr144-legacy'

    def test_une_empreinte_v1_se_verifie_encore(self):
        self._sceller(version=DevisSignature.CONTENT_HASH_V1)
        rapport = verifier_empreinte_signature(self.devis)
        self.assertTrue(rapport['intacte'])
        self.assertEqual(rapport['version'], DevisSignature.CONTENT_HASH_V1)
        self.assertIn("sceau d'origine", rapport['message'])

    def test_la_portee_reduite_du_sceau_v1_est_DITE(self):
        """Une signature d'hier reste authentique — avec la portée qui était la
        sienne : son empreinte ne bouge pas quand le taux de TVA d'une ligne
        change, et le message le NOMME au lieu de laisser croire le contraire.
        """
        self._sceller(version=DevisSignature.CONTENT_HASH_V1)
        self.ligne.taux_tva = Decimal('10')
        self.ligne.save(update_fields=['taux_tva'])

        rapport = verifier_empreinte_signature(self.devis)
        self.assertTrue(rapport['intacte'])
        self.assertEqual(rapport['version'], DevisSignature.CONTENT_HASH_V1)
        self.assertIn('ne couvre ni le taux de TVA par ligne',
                      rapport['message'])

    def test_les_deux_versions_de_payload_sont_distinctes(self):
        """Un préfixe de version : deux payloads de versions différentes ne
        peuvent pas produire la même chaîne — donc jamais la même empreinte
        par accident."""
        v1 = DevisSignature.compute_content_hash(
            self.devis, version=DevisSignature.CONTENT_HASH_V1)
        v2 = DevisSignature.compute_content_hash(
            self.devis, version=DevisSignature.CONTENT_HASH_V2)
        self.assertNotEqual(v1, v2)

    def test_une_signature_neuve_est_scellee_dans_la_version_courante(self):
        """Le chemin d'acceptation ne demande aucune version : il doit sceller
        en v2 sans avoir à le savoir."""
        from apps.ventes.domain.cycle_vie import _create_esign_record

        _create_esign_record(
            devis=self.devis, nom='M. Client', ip='81.0.0.1',
            user_agent='pytest', consentement=True, signature_image='',
            signed_at_client=None, on_behalf_of='', lignes=None)
        signature = DevisSignature.objects.get(devis=self.devis)
        intacte, version = signature.verifier_contenu()
        self.assertTrue(intacte)
        self.assertEqual(version, DevisSignature.CONTENT_HASH_V2)
