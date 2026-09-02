"""CRX24 — ``resolve_client_for_lead`` ne fabrique plus de doublons.

Deux trous relevés par l'audit L3 :

1. **Casse de l'e-mail.** ``Client.Meta.unique_together`` est SENSIBLE à la
   casse alors que la résolution lit en ``email__iexact`` : « A@x.ma » et
   « a@x.ma » étaient deux lignes en base que le code traitait comme une
   seule. La contrainte fonctionnelle ``crx24_client_email_unique_ci``
   (migration 0086) ferme le trou côté base.
2. **Chemin SANS e-mail.** Le repli téléphone (QX17) n'a aucune contrainte
   d'unicité pour l'arbitrer : deux résolutions concurrentes pour le même
   prospect sans e-mail créaient DEUX fiches. Un verrou consultatif par
   (société, téléphone normalisé) sérialise le « chercher puis créer ».
"""
import contextlib
import importlib
from unittest.mock import patch

from django.db import IntegrityError, connection, transaction
from django.test import TestCase

from apps.crm import services
from apps.crm.models import Client, Lead
from authentication.models import Company

# Le module de migration commence par un chiffre : pas importable par `import`.
_migration_0086 = importlib.import_module(
    'apps.crm.migrations.0086_crx24_client_email_unique_ci')


class UniciteEmailInsensibleALaCasseTests(TestCase):
    def setUp(self):
        self.company = Company.objects.create(
            nom='Taqinor CRX24 casse', slug='taqinor-crx24-casse')

    def test_meme_email_casse_differente_refuse(self):
        Client.objects.create(
            company=self.company, nom='Bennani', email='a@exemple.ma')
        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                Client.objects.create(
                    company=self.company, nom='Bennani bis',
                    email='A@EXEMPLE.MA')

    def test_meme_email_dans_une_autre_societe_autorise(self):
        autre = Company.objects.create(
            nom='Autre CRX24', slug='taqinor-crx24-autre')
        Client.objects.create(
            company=self.company, nom='Bennani', email='a@exemple.ma')
        jumeau = Client.objects.create(
            company=autre, nom='Bennani', email='A@EXEMPLE.MA')
        self.assertIsNotNone(jumeau.pk)

    def test_plusieurs_clients_sans_email_autorises(self):
        """Un client sans e-mail est légitime et fréquent : la contrainte est
        PARTIELLE, elle ne doit jamais les sérialiser."""
        premier = Client.objects.create(
            company=self.company, nom='Sans e-mail 1', email=None)
        second = Client.objects.create(
            company=self.company, nom='Sans e-mail 2', email=None)
        self.assertNotEqual(premier.pk, second.pk)


class ResolutionParEmailTests(TestCase):
    def setUp(self):
        self.company = Company.objects.create(
            nom='Taqinor CRX24 email', slug='taqinor-crx24-email')

    def test_email_de_casse_differente_reutilise_le_client(self):
        client = Client.objects.create(
            company=self.company, nom='Alaoui', email='contact@exemple.ma')
        lead = Lead.objects.create(
            company=self.company, nom='Alaoui', email='CONTACT@EXEMPLE.MA')

        resolu = services.resolve_client_for_lead(lead)

        self.assertEqual(resolu.pk, client.pk)
        self.assertEqual(Client.objects.filter(company=self.company).count(), 1)

    def test_email_present_ne_prend_pas_le_verrou_telephone(self):
        """Le chemin e-mail est arbitré par la BASE : le verrou y est un
        no-op (clé vide), sinon il sérialiserait inutilement."""
        lead = Lead.objects.create(
            company=self.company, nom='Idrissi', email='i@exemple.ma',
            telephone='0612345678')
        appels = _espionner_verrou(self, lead)
        self.assertEqual(appels, [(self.company.pk, '')])


class ResolutionParTelephoneTests(TestCase):
    def setUp(self):
        self.company = Company.objects.create(
            nom='Taqinor CRX24 tel', slug='taqinor-crx24-tel')

    def test_verrou_pris_sur_le_telephone_normalise(self):
        lead = Lead.objects.create(
            company=self.company, nom='Sans e-mail', telephone='+212 612-34-56-78')
        appels = _espionner_verrou(self, lead)
        self.assertEqual(
            appels, [(self.company.pk, services.normalize_phone('0612345678'))])

    def test_sans_email_ni_telephone_le_verrou_est_un_no_op(self):
        lead = Lead.objects.create(company=self.company, nom='Anonyme')
        appels = _espionner_verrou(self, lead)
        self.assertEqual(appels, [(self.company.pk, '')])

    def test_deux_leads_meme_telephone_partagent_le_client(self):
        premier = Lead.objects.create(
            company=self.company, nom='Rachid', telephone='0612345678')
        second = Lead.objects.create(
            company=self.company, nom='Rachid', telephone='+212612345678')

        client_1 = services.resolve_client_for_lead(premier)
        client_2 = services.resolve_client_for_lead(second)

        self.assertEqual(client_1.pk, client_2.pk)
        self.assertEqual(Client.objects.filter(company=self.company).count(), 1)


class VerrouConsultatifTests(TestCase):
    def setUp(self):
        self.company = Company.objects.create(
            nom='Taqinor CRX24 verrou', slug='taqinor-crx24-verrou')

    def test_cle_vide_est_un_no_op(self):
        with services._verrou_client_par_telephone(self.company.pk, '') as pris:
            self.assertFalse(pris)

    def test_cle_renseignee_prend_le_verrou_sur_postgres(self):
        attendu = connection.vendor == 'postgresql'
        with services._verrou_client_par_telephone(
                self.company.pk, '612345678') as pris:
            self.assertEqual(pris, attendu)

    def test_verrou_reentrant_dans_la_meme_transaction(self):
        """``pg_advisory_xact_lock`` est ré-entrant pour la MÊME transaction :
        deux résolutions successives dans la même requête ne se bloquent
        jamais l'une l'autre."""
        for _ in range(2):
            with services._verrou_client_par_telephone(
                    self.company.pk, '612345678'):
                pass


class MigrationDoublonsDeCasseTests(TestCase):
    """La migration 0086 promet un chemin de données RÉVERSIBLE : on le
    vérifie sur la fonction inverse, la seule des deux exécutable sur un
    schéma qui porte DÉJÀ la contrainte."""

    def setUp(self):
        self.company = Company.objects.create(
            nom='Taqinor CRX24 mig', slug='taqinor-crx24-mig')

    def test_aucun_groupe_en_doublon_sur_des_emails_distincts(self):
        Client.objects.create(
            company=self.company, nom='A', email='a@exemple.ma')
        Client.objects.create(
            company=self.company, nom='B', email='b@exemple.ma')
        Client.objects.create(company=self.company, nom='C', email=None)
        self.assertEqual(
            _migration_0086._groupes_en_doublon_de_casse(Client), [])

    def test_restauration_remet_l_email_conserve(self):
        client = Client.objects.create(
            company=self.company, nom='Perdant', email=None,
            custom_data={_migration_0086.CLE_SAUVEGARDE: 'a@exemple.ma',
                         'autre': 'intact'})

        _migration_0086.restaurer_doublons_de_casse(
            _FauxApps({'Client': Client}), None)

        client.refresh_from_db()
        self.assertEqual(client.email, 'a@exemple.ma')
        self.assertEqual(client.custom_data, {'autre': 'intact'})

    def test_restauration_ignore_les_clients_intacts(self):
        client = Client.objects.create(
            company=self.company, nom='Intact', email='intact@exemple.ma')
        _migration_0086.restaurer_doublons_de_casse(
            _FauxApps({'Client': Client}), None)
        client.refresh_from_db()
        self.assertEqual(client.email, 'intact@exemple.ma')


class _FauxApps:
    """Registre minimal façon ``apps`` de migration, branché sur les modèles
    RÉELS (la fonction testée ne lit que ``get_model``)."""

    def __init__(self, modeles):
        self._modeles = modeles

    def get_model(self, app_label, model_name):
        return self._modeles[model_name]


def _espionner_verrou(test_case, lead):
    """Exécute ``resolve_client_for_lead`` en enregistrant les arguments reçus
    par le verrou CRX24 (le vrai verrou est bien pris — on l'enveloppe, on ne
    le remplace pas)."""
    appels = []
    vrai_verrou = services._verrou_client_par_telephone

    @contextlib.contextmanager
    def _espion(company_id, cle):
        appels.append((company_id, cle))
        with vrai_verrou(company_id, cle) as pris:
            yield pris

    with patch.object(services, '_verrou_client_par_telephone', _espion):
        services.resolve_client_for_lead(lead)
    return appels
