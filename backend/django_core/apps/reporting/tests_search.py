"""T5 — recherche globale + notifications in-app (multi-tenant, lecture seule)."""
from datetime import date, timedelta
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from apps.crm.models import Client, Lead
from apps.ventes.models import Facture
from authentication.models import Company

User = get_user_model()


class TestGlobalSearch(TestCase):
    def setUp(self):
        self.company = Company.objects.get_or_create(
            slug='search-co', defaults={'nom': 'Search Co'})[0]
        self.other = Company.objects.create(slug='search-other', nom='Autre')
        self.user = User.objects.create_user(
            username='search_user', password='x', role_legacy='responsable',
            company=self.company)
        self.api = APIClient()
        self.api.credentials(
            HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(self.user)}')

    def test_search_finds_lead_and_is_scoped(self):
        Lead.objects.create(company=self.company, nom='Bennani', prenom='Salma')
        Lead.objects.create(company=self.other, nom='Bennani', prenom='Autre')
        resp = self.api.get('/api/django/reporting/search/?q=Bennani')
        self.assertEqual(resp.status_code, 200)
        lead_group = next(
            (g for g in resp.data['groups'] if g['type'] == 'lead'), None)
        self.assertIsNotNone(lead_group)
        # Seul le lead de NOTRE société est renvoyé (multi-tenant).
        self.assertEqual(len(lead_group['results']), 1)
        self.assertIn('Bennani', lead_group['results'][0]['label'])

    def test_archived_lead_found_and_marked_archive(self):
        # Incident 02/10/2026 — un lead archivé « avait disparu » : la
        # recherche globale le retrouve ET le dit archivé ; un lead actif ne
        # porte jamais la mention.
        Lead.objects.create(company=self.company, nom='Merbahi', ville='Rabat',
                            is_archived=True)
        Lead.objects.create(company=self.company, nom='Merbahiactif', ville='Fes')
        resp = self.api.get('/api/django/reporting/search/?q=Merbahi')
        self.assertEqual(resp.status_code, 200)
        group = next(g for g in resp.data['groups'] if g['type'] == 'lead')
        par_nom = {r['label']: r['sublabel'] for r in group['results']}
        self.assertEqual(par_nom['Merbahi'], 'Archivé · Rabat')
        self.assertEqual(par_nom['Merbahiactif'], 'Fes')

    def test_groupes_et_cloche_bornes_au_droit_et_a_la_portee(self):
        """APFS24 (C-APFS-025) — Admin RH (sans crm_voir/ventes_voir) : aucun
        groupe lead/client/devis/facture, aucune facture dans la cloche ; C2
        (« soi ») : pas le lead de C1 ; sans client_pii_voir : rien par
        téléphone / e-mail, sublabel sans coordonnées ; C1 : inchangé.
        Mutant : retirer le test de droit ⇒ échec."""
        from apps.roles.models import Role
        from apps.roles.permissions_registre import SCOPE_SELF

        def api_de(nom, permissions):
            role = Role.objects.create(company=self.company, nom=nom, permissions=permissions)
            user = User.objects.create_user(username=nom, password='x', company=self.company, role=role)
            api = APIClient()
            api.credentials(HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(user)}')
            return user, api
        c1, api_c1 = api_de('apfs24-c1', ['crm_voir', 'ventes_voir', 'client_pii_voir', SCOPE_SELF])
        _, api_c2 = api_de('apfs24-c2', ['crm_voir', 'ventes_voir', 'client_pii_voir', SCOPE_SELF])
        _, api_rh = api_de('apfs24-rh', ['rh_voir'])
        _, api_sans_pii = api_de('apfs24-sans-pii', ['crm_voir', 'ventes_voir'])
        Lead.objects.create(company=self.company, nom='Apfslead', telephone='0661240024', owner=c1)
        client = Client.objects.create(company=self.company, nom='Apfsclient', email='apfs24@example.com')
        Facture.objects.create(
            company=self.company, reference='FAC-APFS24', client=client, created_by=c1,
            statut=Facture.Statut.EMISE, date_echeance=date.today() - timedelta(days=10),
            taux_tva=Decimal('20'), remise_globale=Decimal('0'))

        def groupes(api, q):
            resp = api.get('/api/django/reporting/search/', {'q': q})
            self.assertEqual(resp.status_code, 200, resp.data)
            return {g['type']: g for g in resp.data['groups']}
        for q in ('0661240024', 'Apfs', 'FAC-APFS24'):
            self.assertFalse({'lead', 'client', 'devis', 'facture'} & set(groupes(api_rh, q)), q)
        self.assertEqual(groupes(api_c1, '0661240024')['lead']['results'][0]['sublabel'], '0661240024')
        self.assertNotIn('lead', groupes(api_c2, 'Apfslead'))
        self.assertNotIn('lead', groupes(api_sans_pii, '0661240024'))
        self.assertNotIn('client', groupes(api_sans_pii, 'apfs24@example.com'))
        par_nom = groupes(api_sans_pii, 'Apfs')
        self.assertNotIn('0661240024', str(par_nom))
        self.assertNotIn('apfs24@example.com', str(par_nom))
        self.assertEqual(api_rh.get('/api/django/reporting/notifications/').data['factures_impayees'], [])
        self.assertEqual(len(api_c1.get('/api/django/reporting/notifications/').data['factures_impayees']), 1)

    def test_short_query_returns_nothing(self):
        resp = self.api.get('/api/django/reporting/search/?q=a')
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.data['groups'], [])

    def test_search_finds_bon_commande_by_reference(self):
        from apps.ventes.models import BonCommande
        client = Client.objects.create(company=self.company, nom='CliBC')
        BonCommande.objects.create(
            company=self.company, reference='BC-2026-007', client=client)
        resp = self.api.get('/api/django/reporting/search/?q=BC-2026-007')
        self.assertEqual(resp.status_code, 200)
        group = next((g for g in resp.data['groups']
                      if g['type'] == 'bon_commande'), None)
        self.assertIsNotNone(group)
        self.assertEqual(group['results'][0]['label'], 'BC-2026-007')

    def test_search_finds_contrat_by_client(self):
        from apps.sav.models import ContratMaintenance
        client = Client.objects.create(company=self.company, nom='MaintCli')
        ContratMaintenance.objects.create(
            company=self.company, client=client, periodicite='annuel',
            date_debut=date.today(), actif=True)
        resp = self.api.get('/api/django/reporting/search/?q=MaintCli')
        self.assertEqual(resp.status_code, 200)
        group = next((g for g in resp.data['groups']
                      if g['type'] == 'contrat'), None)
        self.assertIsNotNone(group)
        self.assertIn('MaintCli', group['results'][0]['sublabel'])


class TestRechercheFtsEntretien(TestCase):
    """NTPLT32 — ``search_vector`` entretenu après validation (signal
    ``post_save``), jamais servi par l'API, reconstruit par lots."""

    def setUp(self):
        self.company = Company.objects.get_or_create(
            slug='fts-co', defaults={'nom': 'FTS Co'})[0]

    def test_signal_indexe_apres_commit_sans_accents(self):
        from core.recherche_fts import requete_prefixe
        lead = Lead.objects.create(company=self.company, nom='Provisoire')
        lead.nom, lead.ville = 'Élodie', 'Fès'
        with self.captureOnCommitCallbacks(execute=True):
            lead.save(update_fields=['nom', 'ville'])
        lead.refresh_from_db()
        self.assertIsNotNone(lead.search_vector)
        for q in ('elodie', 'Élo', 'FES'):
            self.assertTrue(Lead.objects.filter(
                pk=lead.pk, search_vector=requete_prefixe(q)).exists(), q)
        self.assertFalse(Lead.objects.filter(
            pk=lead.pk, search_vector=requete_prefixe('martin')).exists())

    def test_ecriture_bornee_hors_index_ne_recalcule_pas(self):
        lead = Lead.objects.create(company=self.company, nom='Borne')
        Lead.objects.filter(pk=lead.pk).update(search_vector=None)
        with self.captureOnCommitCallbacks(execute=True):
            lead.save(update_fields=['note'])
        lead.refresh_from_db()
        self.assertIsNone(lead.search_vector)
        with self.captureOnCommitCallbacks(execute=True):
            lead.save(update_fields=['nom'])
        lead.refresh_from_db()
        self.assertIsNotNone(lead.search_vector)

    def test_rebuild_search_index_par_lots_et_api_sans_vecteur(self):
        from io import StringIO

        from django.core.management import CommandError, call_command
        # Hors captureOnCommitCallbacks, le signal ne s'exécute pas : lignes NULL.
        leads = [Lead.objects.create(company=self.company, nom=f'Lot{i}')
                 for i in range(3)]
        client = Client.objects.create(company=self.company, nom='Clientlot')
        self.assertEqual(Lead.objects.filter(
            pk__in=[le.pk for le in leads], search_vector__isnull=True).count(), 3)
        call_command('rebuild_search_index', '--app', 'crm', '--lot', '2',
                     '--pause-ms', '0', stdout=StringIO())
        self.assertFalse(Lead.objects.filter(
            pk__in=[le.pk for le in leads], search_vector__isnull=True).exists())
        client.refresh_from_db()
        self.assertIsNotNone(client.search_vector)
        with self.assertRaises(CommandError):
            call_command('rebuild_search_index', '--app', 'inconnue',
                         stdout=StringIO())
        user = User.objects.create_user(
            username='fts_user', password='x', role_legacy='responsable',
            company=self.company)
        api = APIClient()
        api.credentials(HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(user)}')
        resp = api.get(f'/api/django/crm/leads/{leads[0].pk}/')
        self.assertEqual(resp.status_code, 200, resp.data)
        self.assertNotIn('search_vector', resp.data)


class TestGlobalSearchFts(TestCase):
    """NTPLT33 — recherche globale en plein-texte : accents, pluriels,
    préfixe ; une ligne pas encore indexée reste trouvée (repli icontains) ;
    enveloppe de résultat inchangée."""

    def setUp(self):
        self.company = Company.objects.get_or_create(
            slug='fts-search-co', defaults={'nom': 'FTS Search Co'})[0]
        self.user = User.objects.create_user(
            username='fts_search_user', password='x', role_legacy='responsable',
            company=self.company)
        self.api = APIClient()
        self.api.credentials(
            HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(self.user)}')

    def _groupe(self, q, type_):
        resp = self.api.get('/api/django/reporting/search/', {'q': q})
        self.assertEqual(resp.status_code, 200, resp.data)
        self.assertEqual(set(resp.data), {'query', 'groups'})
        return next((g for g in resp.data['groups'] if g['type'] == type_), None)

    def test_accents_prefixe_et_repli_non_indexe(self):
        from core.recherche_fts import indexer
        helene = Lead.objects.create(
            company=self.company, nom='Hélène', prenom='Zouhri')
        indexer(Lead, [helene.pk])
        # Jamais indexé (signal non exécuté en TestCase) : repli icontains.
        Lead.objects.create(company=self.company, nom='Zouhrinette')
        # « helene » sans accent : seul le plein-texte la retrouve (ILIKE non).
        groupe = self._groupe('helene', 'lead')
        self.assertIsNotNone(groupe)
        self.assertEqual([r['label'] for r in groupe['results']], ['Hélène Zouhri'])
        self.assertEqual(set(groupe['results'][0]), {'id', 'label', 'sublabel'})
        labels = {r['label'] for r in self._groupe('Zouhri', 'lead')['results']}
        self.assertEqual(labels, {'Hélène Zouhri', 'Zouhrinette'})

    def test_pluriel_francais_et_relation_client(self):
        from apps.sav.models import Ticket
        from core.recherche_fts import indexer
        client = Client.objects.create(company=self.company, nom='Benkirane')
        ticket = Ticket.objects.create(
            company=self.company, reference='SAV-FTS-1', client=client,
            description="Panne de l'onduleur principal")
        facture = Facture.objects.create(
            company=self.company, reference='FAC-FTS-1', client=client,
            taux_tva=Decimal('20'), remise_globale=Decimal('0'))
        for modele, objet in ((Client, client), (Ticket, ticket), (Facture, facture)):
            indexer(modele, [objet.pk])
        # « onduleurs » (pluriel) : absent tel quel du texte, trouvé par racine.
        ticket = self._groupe('onduleurs', 'ticket')
        self.assertIsNotNone(ticket)
        self.assertEqual(ticket['results'][0]['label'], 'SAV-FTS-1')
        # Facture trouvée par le nom de son client (vecteur du client).
        facture = self._groupe('benkir', 'facture')
        self.assertIsNotNone(facture)
        self.assertEqual(facture['results'][0]['label'], 'FAC-FTS-1')


class TestSuggestTrigramme(TestCase):
    """NTPLT34 — ``reporting/search/suggest/`` : tolérant aux fautes
    (pg_trgm), borné société, 10 résultats au plus."""

    URL = '/api/django/reporting/search/suggest/'

    def setUp(self):
        self.company = Company.objects.get_or_create(
            slug='suggest-co', defaults={'nom': 'Suggest Co'})[0]
        self.autre = Company.objects.create(slug='suggest-autre', nom='Autre')
        self.user = User.objects.create_user(
            username='suggest_user', password='x', role_legacy='responsable',
            company=self.company)
        self.api = APIClient()
        self.api.credentials(
            HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(self.user)}')

    def test_faute_de_frappe_bornee_societe_et_plafond(self):
        # ENF23 — jamais sauté : pg_trgm est posée par stock/0148 (base de test
        # CI comprise) ; le repli icontains a son propre test (mock) ci-dessous.
        from core.recherche_fts import trigramme_disponible
        self.assertTrue(trigramme_disponible(), "pg_trgm attendue (stock/0148).")
        Lead.objects.create(company=self.company, nom='Bennani', prenom='Salma')
        Lead.objects.create(company=self.autre, nom='Bennani', prenom='Autre')
        Client.objects.create(company=self.company, nom='Benanni', prenom='Électricité')
        resp = self.api.get(self.URL, {'q': 'Benani'})
        self.assertEqual(resp.status_code, 200, resp.data)
        self.assertEqual(set(resp.data), {'query', 'results'})
        par_type = {(r['type'], r['label']) for r in resp.data['results']}
        self.assertIn(('lead', 'Bennani Salma'), par_type)
        self.assertIn(('client', 'Benanni Électricité'), par_type)
        self.assertNotIn(('lead', 'Bennani Autre'), par_type)
        for r in resp.data['results']:
            self.assertEqual(set(r), {'type', 'id', 'label', 'sublabel', 'score'})
            self.assertGreater(r['score'], 0.3)
        scores = [r['score'] for r in resp.data['results']]
        self.assertEqual(scores, sorted(scores, reverse=True))
        for i in range(12):
            Lead.objects.create(company=self.company, nom=f'Bennani{i}')
        self.assertLessEqual(
            len(self.api.get(self.URL, {'q': 'Bennani'}).data['results']), 10)

    def test_requete_courte_et_repli_sans_trigramme(self):
        from unittest import mock
        resp = self.api.get(self.URL, {'q': 'b'})
        self.assertEqual(resp.data, {'query': 'b', 'results': []})
        Lead.objects.create(company=self.company, nom='Alaoui')
        with mock.patch('apps.reporting.search.trigramme_disponible',
                        return_value=False):
            resp = self.api.get(self.URL, {'q': 'lao'})
        self.assertEqual(resp.status_code, 200, resp.data)
        self.assertEqual([(r['type'], r['label'], r['score'])
                          for r in resp.data['results']],
                         [('lead', 'Alaoui', None)])


class TestNotifications(TestCase):
    def setUp(self):
        self.company = Company.objects.get_or_create(
            slug='notif-co', defaults={'nom': 'Notif Co'})[0]
        self.user = User.objects.create_user(
            username='notif_user', password='x', role_legacy='responsable',
            company=self.company)
        self.api = APIClient()
        self.api.credentials(
            HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(self.user)}')

    def test_overdue_invoice_flagged(self):
        client = Client.objects.create(company=self.company, nom='C')
        Facture.objects.create(
            company=self.company, reference='FAC-NOTIF-1', client=client,
            statut=Facture.Statut.EN_RETARD,
            date_echeance=date.today() - timedelta(days=10),
            taux_tva=Decimal('20'), remise_globale=Decimal('0'))
        resp = self.api.get('/api/django/reporting/notifications/')
        self.assertEqual(resp.status_code, 200)
        self.assertGreaterEqual(resp.data['total'], 1)
        fac = resp.data['factures_impayees']
        self.assertEqual(len(fac), 1)
        self.assertTrue(fac[0]['overdue'])

    def test_structure_keys_present(self):
        resp = self.api.get('/api/django/reporting/notifications/')
        self.assertEqual(resp.status_code, 200)
        for key in ('total', 'activites_en_retard', 'garanties_expirantes',
                    'factures_impayees', 'contrats_a_renouveler',
                    'visites_dues'):
            self.assertIn(key, resp.data)

    def test_contract_renewal_and_due_visit_flagged(self):
        # N83 — signaux maintenance dans la cloche : renouvellement ≤ 90 j et
        # visite due (calculée à la lecture).
        from apps.sav.models import ContratMaintenance
        client = Client.objects.create(company=self.company, nom='MaintCli')
        # Renouvellement dans 30 jours → doit apparaître.
        ContratMaintenance.objects.create(
            company=self.company, client=client, periodicite='annuel',
            date_debut=date.today() - timedelta(days=400), actif=True,
            date_renouvellement=date.today() + timedelta(days=30))
        # Contrat dont la dernière visite est très ancienne → visite due.
        ContratMaintenance.objects.create(
            company=self.company, client=client, periodicite='mensuel',
            date_debut=date.today() - timedelta(days=200),
            derniere_visite=date.today() - timedelta(days=200), actif=True)
        resp = self.api.get('/api/django/reporting/notifications/')
        self.assertEqual(resp.status_code, 200)
        self.assertGreaterEqual(len(resp.data['contrats_a_renouveler']), 1)
        self.assertGreaterEqual(len(resp.data['visites_dues']), 1)
        # Le compteur total inclut bien ces nouveaux signaux.
        self.assertGreaterEqual(resp.data['total'], 2)

    def test_overdue_activity_scoped_to_assigned_user(self):
        # VX84 — la cloche ne doit PAS compter les activités en retard d'un
        # COLLÈGUE : avant le fix ce groupe était company-wide (**co sans
        # assigned_to), contredisant « Ma file » qui filtre déjà par
        # assigned_to=request.user.
        from apps.records.models import Activity
        colleague = User.objects.create_user(
            username='notif_colleague', password='x', role_legacy='commercial',
            company=self.company)
        # Activité en retard assignée à MOI → doit apparaître.
        Activity.objects.create(
            company=self.company, assigned_to=self.user, done=False,
            due_date=date.today() - timedelta(days=3), summary='Ma tâche')
        # Activité en retard assignée à un COLLÈGUE → doit être exclue.
        Activity.objects.create(
            company=self.company, assigned_to=colleague, done=False,
            due_date=date.today() - timedelta(days=5), summary='Tâche collègue')
        resp = self.api.get('/api/django/reporting/notifications/')
        self.assertEqual(resp.status_code, 200)
        activites = resp.data['activites_en_retard']
        self.assertEqual(len(activites), 1)
        self.assertEqual(activites[0]['label'], 'Ma tâche')

    def test_inactive_contract_not_signalled(self):
        from apps.sav.models import ContratMaintenance
        client = Client.objects.create(company=self.company, nom='Inactif')
        ContratMaintenance.objects.create(
            company=self.company, client=client, periodicite='mensuel',
            date_debut=date.today() - timedelta(days=200),
            derniere_visite=date.today() - timedelta(days=200), actif=False,
            date_renouvellement=date.today() + timedelta(days=10))
        resp = self.api.get('/api/django/reporting/notifications/')
        self.assertEqual(len(resp.data['contrats_a_renouveler']), 0)
        self.assertEqual(len(resp.data['visites_dues']), 0)


class TestSearchMore(TestCase):
    """N83 — lien « voir tout / +N autres » quand un groupe dépasse PER=6."""
    def setUp(self):
        self.company = Company.objects.get_or_create(
            slug='more-co', defaults={'nom': 'More Co'})[0]
        self.user = User.objects.create_user(
            username='more_user', password='x', role_legacy='responsable',
            company=self.company)
        self.api = APIClient()
        self.api.credentials(
            HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(self.user)}')

    def test_more_flag_when_over_per(self):
        # 8 leads correspondant à la requête → groupe plein (6) + more_count 2.
        for i in range(8):
            Lead.objects.create(company=self.company, nom=f'Dupont{i}')
        resp = self.api.get('/api/django/reporting/search/?q=Dupont')
        self.assertEqual(resp.status_code, 200)
        grp = next((g for g in resp.data['groups'] if g['type'] == 'lead'), None)
        self.assertIsNotNone(grp)
        self.assertEqual(len(grp['results']), 6)
        self.assertTrue(grp.get('more'))
        self.assertEqual(grp.get('more_count'), 2)

    def test_no_more_flag_under_per(self):
        for i in range(3):
            Lead.objects.create(company=self.company, nom=f'Martin{i}')
        resp = self.api.get('/api/django/reporting/search/?q=Martin')
        grp = next((g for g in resp.data['groups'] if g['type'] == 'lead'), None)
        self.assertIsNotNone(grp)
        self.assertEqual(len(grp['results']), 3)
        self.assertNotIn('more', grp)
