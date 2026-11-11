"""CRX32 — le DSR (loi 09-08) efface EXACTEMENT ce que l'action ``anonymize``
efface, et sa recherche par téléphone passe par la colonne indexée.

CE QUI ÉTAIT FAUX. ``ClientViewSet.anonymize`` (FG26) purge depuis longtemps
les identifiants fiscaux et administratifs d'un client — ``cin``, ``ice``,
``if_fiscal``, ``rc`` — et ses champs personnalisés ``custom_data``. Le chemin
``dsr_provider.erase_crm``, LUI — le seul qui réponde à une demande LÉGALE
d'effacement — ne les touchait pas : un client « effacé » gardait son numéro
de carte d'identité nationale. Côté Lead, ``custom_data`` (JSON libre où une
société range ce qu'elle veut) survivait aussi. Enfin, la BRANCHE CLIENT du
fournisseur n'avait AUCUN test : rien n'aurait signalé la divergence.

Deuxième volet : ``_matcher`` scannait en Python TOUS les leads de la société
pour comparer un téléphone normalisé, alors que ``Lead.phone_normalise``
existe, est maintenu à chaque ``save()`` (QW10) et porte un index
``(company, phone_normalise)``.

Lancer :
    docker compose exec django_core python manage.py test \
        apps.crm.tests_crx32_dsr_complet -v 2
"""
from django.db import connection
from django.test import TestCase
from django.test.utils import CaptureQueriesContext

from apps.crm.dsr_provider import _matcher, erase_crm
from apps.crm.models import Client, Lead
from authentication.models import Company


class LaBrancheClientEstEffaceeCompletement(TestCase):
    """LE PREMIER TEST de la branche Client du fournisseur DSR."""

    def setUp(self):
        self.company = Company.objects.create(
            nom='Taqinor CRX32', slug='taqinor-crx32')
        self.client_obj = Client.objects.create(
            company=self.company, nom='Benali', prenom='Amina',
            email='amina.crx32@example.ma', telephone='+212600000032',
            adresse='12 rue des Palmiers, Casablanca',
            cin='AB123456', ice='001234567000089',
            if_fiscal='12345678', rc='RC-98765',
            custom_data={'numero_compteur': '4412-778',
                         'note': 'Voisin de M. X'})

    def test_les_pii_classiques_partent(self):
        self.assertEqual(
            erase_crm(self.company, 'amina.crx32@example.ma'), 1)
        self.client_obj.refresh_from_db()
        self.assertEqual(self.client_obj.nom, 'Anonymisé')
        self.assertIsNone(self.client_obj.prenom)
        self.assertIsNone(self.client_obj.email)
        self.assertIsNone(self.client_obj.telephone)
        self.assertIsNone(self.client_obj.adresse)
        self.assertTrue(self.client_obj.is_anonymized)
        self.assertIsNotNone(self.client_obj.anonymized_at)

    def test_les_identifiants_fiscaux_et_administratifs_partent(self):
        """LE TEST ROUGE — aujourd'hui le CIN survit à un effacement légal."""
        erase_crm(self.company, 'amina.crx32@example.ma')
        self.client_obj.refresh_from_db()
        for champ in ('cin', 'ice', 'if_fiscal', 'rc'):
            with self.subTest(champ=champ):
                self.assertIsNone(
                    getattr(self.client_obj, champ),
                    "%s survit à l'effacement DSR alors que l'action "
                    'anonymize le purge : les deux chemins doivent scruber '
                    'le même ensemble.' % champ)

    def test_les_champs_personnalises_partent(self):
        erase_crm(self.company, 'amina.crx32@example.ma')
        self.client_obj.refresh_from_db()
        self.assertIsNone(
            self.client_obj.custom_data,
            'custom_data est un JSON libre où une société range des PII '
            '(CIN, numéro de compteur, notes nominatives).')

    def test_l_effacement_par_telephone_trouve_aussi_le_client(self):
        self.assertEqual(erase_crm(self.company, '+212600000032'), 1)
        self.client_obj.refresh_from_db()
        self.assertTrue(self.client_obj.is_anonymized)

    def _site_et_lead(self):
        from decimal import Decimal

        from apps.crm.models import SiteProfile
        site = SiteProfile.objects.create(
            company=self.company, client=self.client_obj,
            gps_lat=Decimal('33.573100'), gps_lng=Decimal('-7.589800'),
            ombrage_notes='Palmier du voisin Mme Alaoui')
        lead = Lead.objects.create(
            company=self.company, nom='Alaoui', client=self.client_obj,
            email='amina.crx32@example.ma', ville='Casablanca',
            gps_lat=Decimal('33.573100'), gps_lng=Decimal('-7.589800'),
            contact_secondaire_nom='Karim Alaoui',
            contact_secondaire_telephone='0661000061',
            contact_secondaire_email='karim061@example.ma',
            contact_secondaire_fonction='Époux',
            note='Sara rappelle après 18h, villa 12 lot Riad',
            visite_notes='Code portail 4512, chien',
            ombrage_notes='Antenne sur le toit Alaoui',
            lien_maps='https://maps.google.com/?q=33.5731,-7.5898')
        return site, lead

    def test_gps_contact_secondaire_et_notes_partent(self):
        """ASOC61 (C-ASOC-061) — GPS, contact secondaire, notes libres et
        lien Maps du lead, GPS et notes d'ombrage du profil de site."""
        site, lead = self._site_et_lead()
        self.assertEqual(erase_crm(self.company, 'amina.crx32@example.ma'), 2)
        lead.refresh_from_db()
        for champ in ('gps_lat', 'gps_lng', 'contact_secondaire_nom',
                      'contact_secondaire_telephone',
                      'contact_secondaire_email',
                      'contact_secondaire_fonction', 'note', 'visite_notes',
                      'ombrage_notes'):
            with self.subTest(champ=champ):
                self.assertIsNone(getattr(lead, champ))
        self.assertEqual(lead.lien_maps, '')
        self.assertEqual(lead.ville, 'Casablanca')
        site.refresh_from_db()
        self.assertIsNone(site.gps_lat)
        self.assertIsNone(site.gps_lng)
        self.assertIsNone(site.ombrage_notes)

    def test_l_action_anonymize_scrube_aussi_le_profil_de_site(self):
        """ASOC61 — ``anonymize`` délègue au scrub unique du DSR."""
        from django.contrib.auth import get_user_model
        from rest_framework.test import APIClient
        from rest_framework_simplejwt.tokens import AccessToken

        site, _ = self._site_et_lead()
        admin = get_user_model().objects.create_user(
            username='asoc61-admin', password='x', role_legacy='admin',
            company=self.company)
        api = APIClient()
        api.credentials(
            HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(admin)}')
        r = api.post(
            f'/api/django/crm/clients/{self.client_obj.id}/anonymize/')
        self.assertEqual(r.status_code, 200, r.data)
        self.client_obj.refresh_from_db()
        self.assertEqual(self.client_obj.nom,
                         f'Client anonymisé #{self.client_obj.id}')
        self.assertIsNone(self.client_obj.cin)
        site.refresh_from_db()
        self.assertIsNone(site.gps_lat)
        self.assertIsNone(site.ombrage_notes)

    def _api_admin(self, username):
        from django.contrib.auth import get_user_model
        from rest_framework.test import APIClient
        admin = get_user_model().objects.create_user(
            username=username, password='x', role_legacy='admin',
            company=self.company)
        api = APIClient()
        api.force_authenticate(admin)
        return api

    def test_l_action_anonymize_scrube_aussi_les_leads_lies(self):
        """AMSG4 (C-AMSG-004) — « Anonymiser » efface aussi les leads du
        client (identité, cadence) ; le WhatsApp du devis n'a plus de numéro ;
        le lead d'un autre client est intact."""
        from django.utils import timezone

        from apps.crm.models import RelanceEtape
        from apps.ventes.models import Devis
        from apps.ventes.utils.whatsapp import devis_recipient_phone
        lead = Lead.objects.create(
            company=self.company, nom='Benali', client=self.client_obj,
            email='lead.amsg4@example.ma', telephone='+212600000044',
            whatsapp='+212600000045')
        touche = RelanceEtape.objects.create(
            company=self.company, lead=lead, cadence='contact', ordre=1,
            canal=RelanceEtape.Canal.APPEL, libelle='Appeler',
            due_date=timezone.localdate())
        devis = Devis.objects.create(
            company=self.company, reference='DEV-AMSG4-0001',
            client=self.client_obj, lead=lead, statut='envoye')
        autre_client = Client.objects.create(company=self.company, nom='Autre')
        autre = Lead.objects.create(
            company=self.company, nom='Témoin', client=autre_client,
            telephone='+212600000046')
        api = self._api_admin('amsg4-admin')
        url = f'/api/django/crm/clients/{self.client_obj.id}/anonymize/'
        r = api.post(url)
        self.assertEqual(r.status_code, 200, r.data)
        lead.refresh_from_db()
        self.assertEqual(lead.nom, 'Anonymisé')
        for champ in ('email', 'telephone', 'whatsapp'):
            with self.subTest(champ=champ):
                self.assertIsNone(getattr(lead, champ))
        touche.refresh_from_db()
        self.assertEqual(touche.statut, RelanceEtape.Statut.ANNULEE)
        self.assertEqual(devis_recipient_phone(
            Devis.objects.select_related('client', 'lead').get(pk=devis.pk)), '')
        autre.refresh_from_db()
        self.assertEqual(autre.nom, 'Témoin')
        self.assertTrue(autre.telephone)
        self.assertEqual(api.post(url).status_code, 409)

    def test_le_tiers_miroir_est_vide(self):
        """ASOC100 (C-ASOC-060) — l'effacement traverse le Tiers miroir :
        identité vide, rôle client gardé, recherche par téléphone → rien."""
        from apps.tiers.models import Tiers
        self.client_obj.refresh_from_db()
        tiers_id = self.client_obj.tiers_id
        self.assertIsNotNone(tiers_id, 'miroir ARC18 attendu')
        erase_crm(self.company, 'amina.crx32@example.ma')
        # Re-save du client ANONYMISÉ (relu, pas l'instance d'avant
        # l'effacement qui ré-écrirait l'identité) : ne re-remplit rien.
        self.client_obj.refresh_from_db()
        self.client_obj.save()
        tiers = Tiers.objects.get(pk=tiers_id)
        self.assertEqual(tiers.nom, 'Anonymisé')
        for champ in ('prenom', 'email', 'telephone', 'adresse', 'cin', 'ice',
                      'rc', 'identifiant_fiscal'):
            with self.subTest(champ=champ):
                self.assertIn(getattr(tiers, champ), ('', None))
        self.assertTrue(tiers.is_client)
        self.assertFalse(Tiers.objects.filter(
            company=self.company, telephone__contains='600000032').exists())

    def test_une_autre_societe_n_est_jamais_touchee(self):
        autre = Company.objects.create(
            nom='Autre CRX32', slug='autre-crx32')
        voisin = Client.objects.create(
            company=autre, nom='Benali', prenom='Amina',
            email='amina.crx32@example.ma', cin='AB123456')
        erase_crm(self.company, 'amina.crx32@example.ma')
        voisin.refresh_from_db()
        self.assertEqual(voisin.nom, 'Benali')
        self.assertEqual(voisin.cin, 'AB123456')


class LesChampsPersonnalisesDuLeadPartent(TestCase):
    def setUp(self):
        self.company = Company.objects.create(
            nom='Taqinor CRX32 Lead', slug='taqinor-crx32-lead')
        self.lead = Lead.objects.create(
            company=self.company, nom='Benali', prenom='Amina',
            email='lead.crx32@example.ma', telephone='+212611000032',
            custom_data={'cin_saisi': 'AB123456'})

    def test_custom_data_du_lead_est_purge(self):
        self.assertEqual(erase_crm(self.company, 'lead.crx32@example.ma'), 1)
        self.lead.refresh_from_db()
        self.assertEqual(self.lead.nom, 'Anonymisé')
        self.assertIsNone(self.lead.custom_data)

    def test_les_cles_de_dedup_normalisees_restent_purgees(self):
        """Acquis QW10 préservé : rien ne doit régresser au passage."""
        erase_crm(self.company, 'lead.crx32@example.ma')
        self.lead.refresh_from_db()
        self.assertEqual(self.lead.email_normalise, '')
        self.assertEqual(self.lead.phone_normalise, '')


class LaRechercheParTelephoneEstIndexee(TestCase):
    def setUp(self):
        self.company = Company.objects.create(
            nom='Taqinor CRX32 Tel', slug='taqinor-crx32-tel')
        self.lead_tel = Lead.objects.create(
            company=self.company, nom='Par téléphone',
            telephone='+212622000032')
        self.lead_wa = Lead.objects.create(
            company=self.company, nom='Par WhatsApp',
            telephone='+212633000099', whatsapp='+212644000032')
        self.autre = Lead.objects.create(
            company=self.company, nom='Sans rapport',
            telephone='+212655000001')

    def test_le_telephone_passe_par_la_colonne_normalisee(self):
        leads, _ = _matcher(self.company, '+212622000032')
        self.assertEqual([le.pk for le in leads], [self.lead_tel.pk])
        # La colonne indexée est bien renseignée par ``save()`` (QW10).
        self.lead_tel.refresh_from_db()
        self.assertTrue(self.lead_tel.phone_normalise)

    def test_la_couverture_whatsapp_est_conservee(self):
        leads, _ = _matcher(self.company, '+212644000032')
        self.assertEqual([le.pk for le in leads], [self.lead_wa.pk])

    def test_un_numero_inconnu_ne_ramene_personne(self):
        leads, clients = _matcher(self.company, '+212699999999')
        self.assertEqual(list(leads), [])
        self.assertEqual(list(clients), [])

    def test_le_predicat_telephone_est_porte_par_la_requete(self):
        """LE TEST ROUGE du second volet : aujourd'hui le téléphone est
        comparé côté Python après avoir chargé TOUS les leads de la société ;
        la colonne indexée n'apparaît nulle part dans la requête."""
        leads, _ = _matcher(self.company, '+212622000032')
        sql = str(leads.query)
        self.assertIn(
            'phone_normalise', sql,
            'le téléphone du lead est encore filtré côté Python : la colonne '
            "indexée n'apparaît pas dans la requête émise.")

    def test_la_lecture_whatsapp_est_bornee_en_base(self):
        """La couverture WhatsApp est conservée sans redevenir un scan total :
        la lecture est restreinte EN BASE aux leads qui en portent un."""
        for i in range(5):
            Lead.objects.create(
                company=self.company, nom='Sans WhatsApp %d' % i,
                telephone='+2126770000%02d' % i)
        with CaptureQueriesContext(connection) as requetes:
            leads, _ = _matcher(self.company, '+212644000032')
            resultat = list(leads)

        self.assertEqual([le.pk for le in resultat], [self.lead_wa.pk])
        lectures = [q['sql'] for q in requetes.captured_queries
                    if 'whatsapp' in q['sql'].lower()]
        self.assertTrue(
            lectures, 'aucune lecture WhatsApp — la couverture est perdue.')
        self.assertTrue(
            any('NOT' in sql.upper() for sql in lectures),
            'la lecture WhatsApp ne porte aucune restriction : elle relit '
            'toute la table au lieu des seuls leads qui en ont un. SQL : %r'
            % lectures)
