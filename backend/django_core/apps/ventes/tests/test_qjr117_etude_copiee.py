"""QJR117 — une COPIE de devis ne sert plus les chiffres d'étude du source.

CE QUE CE MODULE ÉPINGLE. Constats CS4 / CS5 / CS6 de l'audit du 30/08/2026 :

  · CS4 — ``dupliquer_devis`` recopiait ``etude_params`` SANS ``roof_layout``.
    Le recalage par layout (``quote_engine/builder``) ne s'exécute que dans la
    branche ``if roof_layout:`` : la copie tombait dans le ``else`` et le
    moteur prenait ``production_annuelle`` / ``economies_annuelles``
    **verbatim**, écrasant le ROI qu'il venait de calculer sur les lignes
    réelles de la copie.
  · CS5 — ``creer_variante_gamme`` donnait à la sœur le bloc chiffré du frère,
    alors que sa docstring annonce « chaque gamme a sa composition et ses prix
    PROPRES » — et les deux gammes partent ENSEMBLE par défaut.
  · CS6 — ``renouveler_devis`` re-tarife les lignes au catalogue courant et
    gardait l'étude chiffrée aux ANCIENS prix.

Aucun rafraîchisseur n'était appelé (0 sur 4), et l'édition de ligne ne
rattrapait pas (le dimensionnement se court-circuite sur empreinte
concordante).

LA MESURE. On donne au devis source une étude MARQUÉE (production annuelle
99 999 kWh, économies 88 888 MAD, blocs portant ``_marqueur='SOURCE'``), on
copie, on change les lignes de la copie, puis on demande au MOTEUR ce qu'il
publierait : ``build_quote_data`` ne doit plus servir 99 999. La configuration
saisie par le commercial, elle, doit survivre intacte.

Lancer :
    docker compose exec django_core python manage.py test \
        apps.ventes.tests.test_qjr117_etude_copiee -v 2
"""
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import SimpleTestCase, TestCase

from apps.ventes.domain.etude_schema import DERIVEE, SCHEMA
from apps.ventes.domain.etudes import (
    CLES_DERIVEES_NON_COPIEES, etude_params_pour_copie,
)

User = get_user_model()

#: La production que le devis SOURCE affirme. Aucun calcul du moteur sur les
#: lignes de la fixture ne peut tomber dessus par hasard.
PROD_SOURCE = 99999
ECO_SOURCE = 88888


class LeJeuPurgeEstCoherentAvecLeSchema(SimpleTestCase):
    """La liste purgée n'est pas un choix libre : chaque clé doit être
    DÉCLARÉE dérivée dans ``domain/etude_schema``. Une clé renommée au schéma
    ne peut donc plus être purgée « à côté » en silence."""

    def test_les_six_cles_sont_declarees_derivees(self):
        for cle in CLES_DERIVEES_NON_COPIEES:
            with self.subTest(cle=cle):
                regle = SCHEMA.get(cle)
                self.assertIsNotNone(
                    regle, 'clé « %s » absente du schéma' % cle)
                self.assertEqual(
                    regle['nature'], DERIVEE,
                    'clé « %s » : purger une ENTRÉE du commercial '
                    'supprimerait une saisie qu\'aucun serveur ne sait '
                    'reconstruire.' % cle)

    def test_la_configuration_survit_et_les_derivees_partent(self):
        """La fonction pure, sans base."""
        bloc = etude_params_pour_copie({
            'scenario': 'Les deux (Sans + Avec)',
            'factures_mensuelles_reelles': [1800] * 12,
            'production_annuelle': PROD_SOURCE,
            'etude_horaire': {'_marqueur': 'SOURCE'},
        })
        self.assertEqual(bloc, {'scenario': 'Les deux (Sans + Avec)',
                                'factures_mensuelles_reelles': [1800] * 12})

    def test_un_bloc_sans_configuration_rend_none(self):
        """``Devis.etude_params`` est ``null=True`` : un devis dont l'étude
        n'était QUE dérivée repart sans étude, pas avec un dict vide."""
        self.assertIsNone(
            etude_params_pour_copie({'production_annuelle': PROD_SOURCE}))
        self.assertIsNone(etude_params_pour_copie(None))

    def test_le_bloc_rendu_est_un_dict_neuf(self):
        """``etude_params=devis.etude_params`` partageait la MÊME référence
        entre source et copie : une mutation de l'un fuyait sur l'autre."""
        source = {'scenario': 'Sans batterie'}
        copie = etude_params_pour_copie(source)
        copie['scenario'] = 'Avec batterie'
        self.assertEqual(source['scenario'], 'Sans batterie')


class _SourceAvecEtudeMarquee(TestCase):
    """Un devis résidentiel complet dont l'étude porte des chiffres
    RECONNAISSABLES (Casablanca : la chaîne PVGIS passe par la table de
    référence de la ville, aucun accès réseau)."""

    slug = 'qjr117'

    LIGNES = (
        ('Panneau Canadien Solar 710W', '14', '1166.67'),
        ('Onduleur réseau Huawei 10kW Monophasé', '1', '15000.00'),
        ('Onduleur hybride Deye 10kW Monophasé', '1', '23333.33'),
        ('Batterie Dyness 10 kWh', '1', '25000.00'),
    )

    #: Ce que le COMMERCIAL a saisi — jamais purgé.
    CONFIGURATION = {
        'scenario': 'Les deux (Sans + Avec)',
        'factures_mensuelles_reelles': [1800] * 12,
        'tension_raccordement': 'BT',
        'toiture': {'type': 'tuiles'},
    }

    #: Ce que le MOTEUR avait calculé POUR LE SOURCE — jamais recopié.
    DERIVEES_MARQUEES = {
        'production_annuelle': PROD_SOURCE,
        'economies_annuelles': ECO_SOURCE,
        'payback': 4.2,
        'etude_horaire': {'_marqueur': 'SOURCE'},
        'dimensionnement': {'_marqueur': 'SOURCE'},
        'profils_comparatifs': {'_marqueur': 'SOURCE'},
    }

    def setUp(self):
        from authentication.models import Company
        from apps.crm.models import Client, Lead
        from apps.stock.models import Produit
        from apps.ventes.domain.lignes import creer_ligne
        from apps.ventes.models import Devis

        self.company, _ = Company.objects.get_or_create(
            slug=self.slug, defaults={'nom': self.slug})
        self.user = User.objects.create_user(
            username='qjr117-%s' % self.slug, password='x',
            company=self.company, role_legacy='admin')
        self.client_crm, _ = Client.objects.get_or_create(
            company=self.company, email='qjr117-%s@example.com' % self.slug,
            defaults={'nom': 'QJR117', 'prenom': self.slug,
                      'telephone': '+212600000117'})
        self.lead = Lead.objects.create(
            company=self.company, nom='Lead', prenom=self.slug,
            telephone='+212600000117', ville='Casablanca',
            facture_hiver=1800, ete_differente=False)

        etude = dict(self.CONFIGURATION)
        etude.update(self.DERIVEES_MARQUEES)
        self.devis = Devis.objects.create(
            company=self.company, reference='DEV-QJR117-%s' % self.slug[-4:],
            client=self.client_crm, lead=self.lead,
            statut=Devis.Statut.ENVOYE, taux_tva=Decimal('20'),
            mode_installation='residentiel', etude_params=etude,
            created_by=self.user)
        for rang, (nom, qte, pu) in enumerate(self.LIGNES):
            produit = Produit.objects.create(
                company=self.company, nom=nom,
                # SKU DÉTERMINISTE (rang dans la liste) : un `hash()` de nom
                # varie d'un processus à l'autre (PYTHONHASHSEED).
                sku='QJR117-%d-%s' % (rang, self.company.pk),
                prix_vente=Decimal(pu), prix_achat=Decimal('1'),
                quantite_stock=50)
            creer_ligne(self.devis, produit=produit, designation=nom,
                        quantite=Decimal(qte), prix_unitaire=Decimal(pu),
                        remise=Decimal('0'))

    # ── Les mesures ─────────────────────────────────────────────────────────

    @staticmethod
    def _prod_publiee(devis):
        """Ce que le MOTEUR publierait aujourd'hui pour ce devis."""
        from apps.ventes.quote_engine.builder import build_quote_data
        return build_quote_data(devis, {'pdf_mode': 'full'})['prod_kwh']

    @staticmethod
    def _reduire_le_champ_pv(devis):
        """« un devis dont les lignes changent » — la copie n'a plus le même
        champ PV que le source."""
        ligne = devis.lignes.filter(designation__icontains='Panneau').first()
        assert ligne is not None
        ligne.quantite = Decimal('7')
        ligne.save(update_fields=['quantite'])

    def _verifier_la_copie(self, copie, quoi):
        from apps.ventes.models import Devis

        params = copie.etude_params or {}
        for cle, valeur in self.CONFIGURATION.items():
            self.assertEqual(
                params.get(cle), valeur,
                '%s : la CONFIGURATION saisie par le commercial (« %s ») doit '
                'survivre — aucun serveur ne sait la reconstruire.'
                % (quoi, cle))
        for cle in ('production_annuelle', 'economies_annuelles', 'payback'):
            self.assertNotIn(
                cle, params,
                '%s : « %s » du SOURCE est encore là ; le moteur le prendrait '
                'verbatim et écraserait le ROI calculé sur les lignes de la '
                'copie.' % (quoi, cle))
        for cle in ('etude_horaire', 'dimensionnement', 'profils_comparatifs'):
            bloc = params.get(cle)
            if isinstance(bloc, dict):
                self.assertNotEqual(
                    bloc.get('_marqueur'), 'SOURCE',
                    '%s : le bloc « %s » est celui du SOURCE, pas celui de la '
                    'copie.' % (quoi, cle))

        # Chaîne de statuts INCHANGÉE (règle #4) : une copie repart brouillon.
        self.assertEqual(copie.statut, Devis.Statut.BROUILLON)

        # Le SOURCE, lui, garde son étude et son statut.
        self.devis.refresh_from_db()
        self.assertEqual(
            (self.devis.etude_params or {}).get('production_annuelle'),
            PROD_SOURCE)

        # Et le MOTEUR ne publie plus le chiffre du source sur la copie.
        self._reduire_le_champ_pv(copie)
        copie.refresh_from_db()
        self.assertNotEqual(
            self._prod_publiee(copie), PROD_SOURCE,
            '%s : le moteur publie encore la production annuelle du SOURCE '
            'alors que la copie n\'a plus le même champ PV.' % quoi)


class LeMoteurSertBienLeChiffreStockeSurLeSource(_SourceAvecEtudeMarquee):
    """Le TÉMOIN. Sans lui, les trois tests suivants pourraient passer parce
    que le moteur n'a jamais lu ``production_annuelle``."""

    slug = 'qjr117-temoin'

    def test_le_source_publie_bien_sa_production_stockee(self):
        self.assertEqual(self._prod_publiee(self.devis), PROD_SOURCE)


class LesTroisCopiesNePublientPlusLesChiffresDuSource(_SourceAvecEtudeMarquee):
    """CS4 / CS5 / CS6."""

    slug = 'qjr117-copies'

    def test_dupliquer_devis(self):
        from apps.ventes.domain.creation import dupliquer_devis

        self._verifier_la_copie(
            dupliquer_devis(self.devis, user=self.user), 'duplicata')

    def test_creer_variante_gamme(self):
        from apps.ventes.domain.gammes import creer_variante_gamme

        soeur = creer_variante_gamme(self.devis, 'Premium', user=self.user)
        self._verifier_la_copie(soeur, 'gamme sœur')
        # La sœur garde évidemment son propre libellé de gamme.
        self.assertEqual((soeur.etude_params or {})['gamme']['nom'], 'Premium')

    def test_renouveler_devis(self):
        from apps.ventes.models import Devis
        from apps.ventes.domain.cycle_vie import renouveler_devis

        self.devis.statut = Devis.Statut.ACCEPTE
        self.devis.save(update_fields=['statut'])

        nouveau = renouveler_devis(self.devis, user=self.user)
        self._verifier_la_copie(nouveau, 'renouvellement')
        # La chaîne du SOURCE est intacte : renouveler ne le déclasse pas.
        self.devis.refresh_from_db()
        self.assertEqual(self.devis.statut, Devis.Statut.ACCEPTE)
