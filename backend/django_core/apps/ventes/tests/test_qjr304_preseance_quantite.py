"""QJR304 — LA PHRASE 2 DE LA RÈGLE R4-A, ENFIN VRAIE DANS LES DEUX SENS.

LE ROUGE QUE CES TESTS REPRODUISENT. ``PreseanceQuantite`` déclare trois
champs (``domain/overrides.py``), mais un ``grep`` hors tests sur tout
``backend/django_core`` ne rendait que sa PROPRE définition pour
``quantite_ligne`` : **zéro consommateur de production**. Côté dimensionnement,
``pipeline.decider_taille`` dérivait son compte de panneaux du seul
dimensionneur horaire et ne lisait JAMAIS le ``taille.nb_panneaux`` du
registre. QJR217 n'avait donc câblé que l'AVERTISSEMENT et la branche kWc.

CE QUI EST PROUVÉ ICI, et les deux canaux restent DISTINCTS :

1. une ligne panneau NON verrouillée est FACTURÉE à ``verdict.quantite_ligne``
   (donc à la déclaration de niveau devis), pas à sa quantité brute ;
2. un ``taille.nb_panneaux`` posé au registre est la taille que
   ``decider_taille`` retient — sans écraser la quantité d'une ligne
   VERROUILLÉE, qui reste souveraine (D12) ;
3. quand les deux niveaux s'accordent, aucun avertissement n'est émis et rien
   ne bouge.

Lancer :
    docker compose exec django_core python manage.py test \
        apps.ventes.tests.test_qjr304_preseance_quantite -v 2
"""
import itertools
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase

from apps.crm.models import Client
from apps.stock.models import Produit
from apps.ventes.domain import overrides as R
from apps.ventes.domain import pipeline
from apps.ventes.models import Devis, LigneDevis

User = get_user_model()

_seq = itertools.count(1)

#: Réseau + panneaux : le minimum pour que le lecteur unique des lignes
#: (PVUNI) rende un compte et un wattage.
LIGNES = (
    ('Onduleur réseau Huawei 10kW Triphasé', 1, '11700'),
    ('Panneau Canadian Solar 710W', 14, '1100'),
)

PANNEAU = 'Panneau Canadian Solar 710W'


class _Base(TestCase):
    @classmethod
    def setUpTestData(cls):
        from authentication.models import Company

        cls.company = Company.objects.create(slug='qjr304-co',
                                             nom='QJR304 Co')
        cls.user = User.objects.create_user(
            username='qjr304', password='x', role_legacy='responsable',
            company=cls.company)
        cls.client_obj = Client.objects.create(
            company=cls.company, nom='Bennani', prenom='Salma',
            email='qjr304@example.com', telephone='+212600000304')
        cls.produits = {
            designation: Produit.objects.create(
                company=cls.company, nom=designation, sku=f'QJR304-{index}',
                prix_vente=Decimal(prix), prix_achat=Decimal('1'),
                quantite_stock=100)
            for index, (designation, _qte, prix) in enumerate(LIGNES)
        }

    def devis_neuf(self):
        devis = Devis.objects.create(
            company=self.company, reference=f'DEV-QJR304-{next(_seq):04d}',
            client=self.client_obj, statut=Devis.Statut.BROUILLON,
            taux_tva=Decimal('20.00'), remise_globale=Decimal('0'),
            created_by=self.user, mode_installation='residentiel')
        for designation, qte, prix in LIGNES:
            LigneDevis.objects.create(
                devis=devis, produit=self.produits[designation],
                designation=designation, quantite=Decimal(qte),
                prix_unitaire=Decimal(prix), remise=Decimal('0'))
        return devis

    def poser(self, devis, chemin, valeur):
        """Pose l'override par les fonctions du registre (aucun endpoint)."""
        R.ecrire_colonne(devis, R.poser(devis, chemin, valeur))
        devis.refresh_from_db()
        devis._prefetched_objects_cache = {}
        return devis

    def specs(self, devis, **surcharges):
        """Les specs de l'écrivain unique, telles que l'écran les envoie."""
        return [
            dict({
                'produit': self.produits[ligne.designation].id,
                'designation': ligne.designation,
                'quantite': str(int(ligne.quantite)),
                'prix_unitaire': str(ligne.prix_unitaire),
                'ordre': index,
            }, **(surcharges if ligne.designation == PANNEAU else {}))
            for index, ligne in enumerate(devis.lignes.order_by('ordre', 'id'))
        ]

    def ligne_panneau(self, devis):
        devis.refresh_from_db()
        devis._prefetched_objects_cache = {}
        return devis.lignes.get(designation=PANNEAU)


class QuantiteLigneEstConsommeeEnProduction(_Base):
    """CANAL 1 — ``quantite_ligne`` atteint enfin ce qui est FACTURÉ."""

    def test_la_ligne_non_verrouillee_est_facturee_au_niveau_devis(self):
        """LE ROUGE : la ligne restait facturée à 14 pendant que le kWc du
        devis annonçait déjà 21 panneaux (QJR217) — deux nombres, une vente."""
        devis = self.poser(self.devis_neuf(), 'taille.nb_panneaux', 21)
        avertissements = []
        pipeline.ecrire_lignes(devis, self.specs(devis),
                               company=self.company,
                               avertissements=avertissements)

        ligne = self.ligne_panneau(devis)
        self.assertEqual(int(ligne.quantite), 21)
        # Ce que le client PAIE pour cette ligne suit la quantité retenue.
        self.assertEqual(ligne.quantite * ligne.prix_unitaire,
                         Decimal('21') * Decimal('1100'))

    def test_la_ligne_verrouillee_garde_sa_quantite(self):
        """D12 — la saisie du vendeur sur CETTE ligne fait foi (phrase 1)."""
        devis = self.poser(self.devis_neuf(), 'taille.nb_panneaux', 21)
        avertissements = []
        pipeline.ecrire_lignes(devis,
                               self.specs(devis, quantite_manuelle=True),
                               company=self.company,
                               avertissements=avertissements)

        self.assertEqual(int(self.ligne_panneau(devis).quantite), 14)
        # Phrase 3 — le désaccord est DIT, et il NOMME la ligne.
        self.assertEqual(len(avertissements), 1, avertissements)
        self.assertIn(PANNEAU, avertissements[0])
        self.assertIn('14', avertissements[0])
        self.assertIn('21', avertissements[0])

    def test_sans_surcharge_de_devis_rien_ne_bouge(self):
        """Non-régression : le chemin sans registre est byte-identique."""
        devis = self.devis_neuf()
        avertissements = []
        pipeline.ecrire_lignes(devis, self.specs(devis),
                               company=self.company,
                               avertissements=avertissements)
        self.assertEqual(int(self.ligne_panneau(devis).quantite), 14)
        self.assertEqual(avertissements, [])

    def test_une_surcharge_illisible_ne_facture_rien_d_invente(self):
        """Zéro chiffre inventé : un override non entier vaut une absence."""
        devis = self.poser(self.devis_neuf(), 'taille.nb_panneaux',
                           'beaucoup')
        pipeline.ecrire_lignes(devis, self.specs(devis),
                               company=self.company)
        self.assertEqual(int(self.ligne_panneau(devis).quantite), 14)


class DeciderTailleLitLeRegistre(_Base):
    """CANAL 2 — ``decider_taille`` lit enfin le ``taille.nb_panneaux``."""

    def _intention(self):
        return pipeline.IntentionDevis(
            origine=pipeline.ORIGINE_ECRAN, company=self.company,
            client=self.client_obj)

    def test_le_registre_est_la_taille_retenue(self):
        """LE ROUGE : sans cible ni lead, l'étape 2 rendait ``None`` — le
        ``taille.nb_panneaux`` du registre n'était lu par personne."""
        devis = self.poser(self.devis_neuf(), 'taille.nb_panneaux', 21)
        cible = pipeline.decider_taille(self._intention(), devis)

        self.assertIsNotNone(cible)
        self.assertEqual(cible.nb_panneaux, 21)
        self.assertEqual(int(cible.panel_watt), 710)
        self.assertAlmostEqual(cible.kwc, 14.91, places=2)
        self.assertEqual(cible.source, pipeline.SOURCE_CIBLE_REGISTRE)

    def test_les_deux_canaux_restent_distincts(self):
        """La cible de dimensionnement N'ÉCRASE PAS la quantité d'une ligne
        verrouillée — c'est ce que la table de préséance existe pour garantir."""
        devis = self.poser(self.devis_neuf(), 'taille.nb_panneaux', 21)
        ligne = self.ligne_panneau(devis)
        ligne.quantite_manuelle = True
        ligne.save(update_fields=['quantite_manuelle'])
        devis.refresh_from_db()
        devis._prefetched_objects_cache = {}

        cible = pipeline.decider_taille(self._intention(), devis)
        self.assertEqual(cible.nb_panneaux, 21)

        _dominante, quantite = R.quantite_ligne_panneau(
            devis, list(devis.lignes.all()))
        self.assertEqual(quantite, 14)

    def test_une_cible_deja_arretee_reste_souveraine(self):
        """Non-régression : l'écran / le calepinage priment sur le registre."""
        devis = self.poser(self.devis_neuf(), 'taille.nb_panneaux', 21)
        cible = pipeline.CibleDevis(nb_panneaux=9, panel_watt=550, kwc=4.95)
        intention = pipeline.IntentionDevis(
            origine=pipeline.ORIGINE_ECRAN, company=self.company, cible=cible)
        self.assertIs(pipeline.decider_taille(intention, devis), cible)

    def test_sans_surcharge_l_etape_est_inchangee(self):
        """Sans registre lisible, l'étape 2 rend exactement ce qu'elle rendait."""
        devis = self.devis_neuf()
        self.assertIsNone(pipeline.decider_taille(self._intention(), devis))
        self.assertIsNone(pipeline.decider_taille(self._intention()))


class LesDeuxNiveauxDAccord(_Base):
    """Un désaccord seul mérite un avertissement — pas la coexistence."""

    def test_aucun_avertissement_et_rien_ne_bouge(self):
        devis = self.poser(self.devis_neuf(), 'taille.nb_panneaux', 14)
        ligne = self.ligne_panneau(devis)
        ligne.quantite_manuelle = True
        ligne.save(update_fields=['quantite_manuelle'])
        devis.refresh_from_db()
        devis._prefetched_objects_cache = {}

        avertissements = []
        pipeline.ecrire_lignes(devis,
                               self.specs(devis, quantite_manuelle=True),
                               company=self.company,
                               avertissements=avertissements)

        self.assertEqual(int(self.ligne_panneau(devis).quantite), 14)
        self.assertEqual(avertissements, [])
        cible = pipeline.decider_taille(
            pipeline.IntentionDevis(origine=pipeline.ORIGINE_ECRAN,
                                    company=self.company),
            devis)
        self.assertEqual(cible.nb_panneaux, 14)
