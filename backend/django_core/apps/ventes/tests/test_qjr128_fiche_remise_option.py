"""QJR128 — la fiche de remise / garantie ne liste que l'équipement RÉELLEMENT
installé.

Avant ce correctif, ``_chantier_composants`` itérait
``devis.lignes.select_related("produit").all()`` SANS filtre d'option : un
devis à deux options CONSERVE les deux jeux de lignes en base
(``Devis.option_acceptee`` disant seulement laquelle a été retenue), donc le
document remis au client à la mise en service listait l'onduleur réseau de
l'option « sans » À CÔTÉ de l'onduleur hybride et de la batterie de l'option
« avec » — et les lignes ``optionnelle`` non activées de la même façon.

Le correctif fait passer ``_chantier_composants`` par la voie canonique
``utils.options.option_lines`` (déjà utilisée par la facturation du bon de
commande, ``views/bon_commande.py``) : filtre par l'option RÉELLEMENT
acceptée (``option_effective``) et exclut toute ligne dont
``compte_dans_totaux`` est False (optionnelle non activée, ou section/note).

Run :
    powershell -File scripts/test-backend.ps1 -RestoreDb \
        -Modules "apps.ventes.tests.test_qjr128_fiche_remise_option"
"""
from datetime import date, timedelta
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase, tag

from authentication.models import Company
from apps.crm.models import Client
from apps.installations.models import Installation
from apps.stock.models import Produit
from apps.ventes.models import Devis, Facture, LigneDevis, LigneFacture
from apps.ventes.quote_engine.extra_docs import (
    _chantier_composants,
    _facture_resume,
    build_fiche_remise_html,
    build_lettre_relance_html,
    render_fiche_remise_pdf,
    render_lettre_relance_pdf,
)

User = get_user_model()


def _is_pdf(blob):
    return isinstance(blob, (bytes, bytearray)) and blob[:5] == b'%PDF-'


@tag('pdf')
class _Base(TestCase):
    def setUp(self):
        self.company, _ = Company.objects.get_or_create(
            slug='qjr128-co', defaults={'nom': 'QJR128 Co'})
        self.user = User.objects.create_user(
            username='qjr128_resp', password='x', role_legacy='responsable',
            company=self.company)
        self.client_obj = Client.objects.create(
            company=self.company, nom='Alaoui', prenom='Yassine',
            email='qjr128@example.invalid', telephone='+212600000128')
        self.compteur = 0

    def _produit(self, nom, sku_suffix, marque='TestMarque',
                 garantie='Garantie test 5 ans'):
        self.compteur += 1
        return Produit.objects.create(
            company=self.company, nom=nom,
            sku=f'QJR128-{sku_suffix}-{self.compteur}',
            marque=marque, garantie=garantie,
            prix_vente=Decimal('10000'), prix_achat=Decimal('1'),
            quantite_stock=10, tva=Decimal('20.00'))

    def _devis_deux_options_accepte_sans(self):
        """Devis « Les deux (Sans + Avec) » — DÉCLARÉ (``etude_params``) ET
        les lignes portent réellement les deux familles, comme
        ``test_qjr_solde_deux_options._devis_deux_options`` — accepté
        « sans batterie »."""
        devis = Devis.objects.create(
            company=self.company, reference='DEV-QJR128-0001',
            client=self.client_obj, statut=Devis.Statut.ACCEPTE,
            taux_tva=Decimal('20.00'), created_by=self.user,
            option_acceptee=Devis.OptionAcceptee.SANS_BATTERIE,
            etude_params={'scenario': 'Les deux (Sans + Avec)'})
        # Ligne COMMUNE aux deux options.
        LigneDevis.objects.create(
            devis=devis, produit=self._produit('Panneau mono 550W', 'PAN'),
            designation='Panneau mono 550W', quantite=Decimal('14'),
            prix_unitaire=Decimal('1100'), remise=Decimal('0'))
        # Option « sans batterie » — onduleur réseau (DOIT rester).
        LigneDevis.objects.create(
            devis=devis, produit=self._produit('Onduleur réseau', 'RES'),
            designation='Onduleur réseau', quantite=Decimal('1'),
            prix_unitaire=Decimal('11700'), remise=Decimal('0'))
        # Option « avec batterie » — NE DOIT PAS apparaître sur la fiche d'un
        # chantier issu d'un devis accepté « sans batterie ».
        LigneDevis.objects.create(
            devis=devis, produit=self._produit('Onduleur hybride', 'HYB'),
            designation='Onduleur hybride', quantite=Decimal('1'),
            prix_unitaire=Decimal('24000'), remise=Decimal('0'))
        LigneDevis.objects.create(
            devis=devis, produit=self._produit('Batterie 5 kWh', 'BAT'),
            designation='Batterie 5 kWh', quantite=Decimal('1'),
            prix_unitaire=Decimal('14000'), remise=Decimal('0'))
        # Ligne optionnelle add-on jamais activée par le client — doit AUSSI
        # rester absente de la fiche remise (QJR128, second volet).
        LigneDevis.objects.create(
            devis=devis, produit=self._produit('Monitoring premium', 'MON'),
            designation='Monitoring premium', quantite=Decimal('1'),
            prix_unitaire=Decimal('1500'), remise=Decimal('0'),
            optionnelle=True)
        return devis

    def _chantier(self, devis):
        return Installation.objects.create(
            company=self.company, reference='CH-QJR128-0001',
            client=self.client_obj, devis=devis,
            statut=Installation.Statut.RECEPTIONNE,
            puissance_installee_kwc=Decimal('7.70'),
            type_installation=Installation.TypeInstallation.RESIDENTIEL,
            raccordement=Installation.Raccordement.MONOPHASE,
            site_adresse='Site QJR128', site_ville='Rabat',
            date_mise_en_service=date.today() - timedelta(days=3),
            date_reception=date.today(), technicien_responsable=self.user)


class TestFicheRemiseFiltreParOption(_Base):
    def test_composants_excluent_lautre_option_et_loptionnelle_non_activee(self):
        devis = self._devis_deux_options_accepte_sans()
        chantier = self._chantier(devis)
        composants = _chantier_composants(chantier)
        designations = {c['designation'] for c in composants}

        # Ligne commune + ligne de l'option acceptée (« sans ») présentes.
        self.assertIn('Panneau mono 550W', designations)
        self.assertIn('Onduleur réseau', designations)

        # L'AUTRE option (« avec batterie ») est absente en totalité.
        self.assertNotIn('Onduleur hybride', designations)
        self.assertNotIn('Batterie 5 kWh', designations)

        # La ligne optionnelle add-on non activée est absente elle aussi.
        self.assertNotIn('Monitoring premium', designations)

    def test_devis_option_unique_garde_toutes_ses_lignes(self):
        """Comportement historique inchangé : un devis à option UNIQUE (pas
        de deuxième famille réellement présente) n'est jamais filtré."""
        devis = Devis.objects.create(
            company=self.company, reference='DEV-QJR128-0002',
            client=self.client_obj, statut=Devis.Statut.ACCEPTE,
            taux_tva=Decimal('20.00'), created_by=self.user)
        LigneDevis.objects.create(
            devis=devis, produit=self._produit('Onduleur réseau', 'RES2'),
            designation='Onduleur réseau', quantite=Decimal('1'),
            prix_unitaire=Decimal('11700'), remise=Decimal('0'))
        LigneDevis.objects.create(
            devis=devis, produit=self._produit('Panneau mono 550W', 'PAN2'),
            designation='Panneau mono 550W', quantite=Decimal('10'),
            prix_unitaire=Decimal('1100'), remise=Decimal('0'))
        chantier = self._chantier(devis)
        designations = {c['designation'] for c in _chantier_composants(chantier)}
        self.assertEqual(
            designations, {'Onduleur réseau', 'Panneau mono 550W'})

    def test_html_ne_mentionne_pas_lautre_option(self):
        devis = self._devis_deux_options_accepte_sans()
        chantier = self._chantier(devis)
        composants = _chantier_composants(chantier)
        ctx = {'entreprise_nom': 'QJR128 Co'}
        client = {'nom': 'Alaoui', 'prenom': 'Yassine'}
        info = {'reference': chantier.reference,
                'puissance_kwc': chantier.puissance_installee_kwc}
        html = build_fiche_remise_html(ctx, client, info, composants)
        self.assertIn('Onduleur réseau', html)
        self.assertIn('Panneau mono 550W', html)
        self.assertNotIn('Onduleur hybride', html)
        self.assertNotIn('Batterie 5 kWh', html)
        self.assertNotIn('Monitoring premium', html)

    def test_pdf_se_rend_toujours_correctement(self):
        """Le rendu PDF de bout en bout reste valide (octets non vides) une
        fois le filtre d'option appliqué."""
        devis = self._devis_deux_options_accepte_sans()
        chantier = self._chantier(devis)
        pdf = render_fiche_remise_pdf(chantier)
        self.assertTrue(_is_pdf(pdf))
        self.assertGreater(len(pdf), 1000)


class TestLettreRelanceInchangee(_Base):
    """QJR128 Done= : « lettre de relance inchangée » — le correctif ne
    touche que ``_chantier_composants`` (fiche de remise) ; la famille des
    lettres de relance (facture, pas chantier) doit se rendre exactement
    comme avant."""

    def test_lettre_relance_toujours_valide(self):
        facture = Facture.objects.create(
            company=self.company, reference='FAC-QJR128-0001',
            client=self.client_obj, statut=Facture.Statut.EMISE,
            taux_tva=Decimal('20.00'),
            date_echeance=date.today() - timedelta(days=10))
        LigneFacture.objects.create(
            facture=facture, produit=self._produit('Onduleur hybride', 'HYB3'),
            designation='Onduleur hybride', quantite=Decimal('1'),
            prix_unitaire=Decimal('24000'), taux_tva=Decimal('20.00'))
        for niveau in (1, 2, 3):
            pdf = render_lettre_relance_pdf(facture, niveau)
            self.assertTrue(_is_pdf(pdf), f'niveau {niveau} not a PDF')
            self.assertGreater(len(pdf), 1000)

    def test_lettre_relance_html_inchangee_pour_devis_deux_options(self):
        """Même quand le CLIENT associé porte par ailleurs un devis à deux
        options, la lettre de relance (qui ne lit jamais ``devis.lignes``)
        n'est affectée par rien de ce que QJR128 a changé."""
        self._devis_deux_options_accepte_sans()
        facture = Facture.objects.create(
            company=self.company, reference='FAC-QJR128-0002',
            client=self.client_obj, statut=Facture.Statut.EMISE,
            taux_tva=Decimal('20.00'),
            date_echeance=date.today() - timedelta(days=10))
        resume = _facture_resume(facture)
        ctx = {'entreprise_nom': 'QJR128 Co'}
        client = {'nom': 'Alaoui', 'prenom': 'Yassine'}
        html = build_lettre_relance_html(ctx, client, resume, 1)
        self.assertIn('class="sign"', html)
