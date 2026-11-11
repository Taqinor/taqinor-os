"""Garde-fou anti-écrasement de l'import CSV/XLSX.

Les modes ``maj``/``upsert`` écrivent sur des fiches EXISTANTES, donc sur les
deux seuls jeux de données réels du parc (catalogue ``stock.Produit``, pipeline
``crm.Lead``). Ce module verrouille les trois protections :

1. l'aperçu (``dry-run``) annonce, ligne par ligne et champ par champ, ce qui
   serait écrasé — AVANT toute écriture, et sans rien écrire lui-même ;
2. l'écriture est en REMPLISSAGE SEUL par défaut (un champ déjà rempli n'est
   jamais remplacé sans ``ecraser=true``), tout en laissant la mise à jour en
   masse légitime parfaitement fonctionnelle avec l'opt-in ;
3. chaque valeur remplacée est conservée (``ImportJobRow.modifications`` +
   ``AuditLog`` via la primitive plateforme ``apps.audit.recorder``).

Réutilise le cadre de test de ``tests.py`` (``ImportBase``).
"""
from apps.audit.models import AuditLog
from apps.crm.models import Lead
from apps.stock.models import Produit
from authentication.models import Company

from .models import ImportJob, ImportJobRow
from .tests import ImportBase

COMMIT_URL = '/api/django/imports/commit/'
DRY_RUN_URL = '/api/django/imports/dry-run/'


class EcrasementBase(ImportBase):
    def _lead_reel(self, **extra):
        """Lead « réel » déjà renseigné (le cas que l'import ne doit pas casser)."""
        champs = {
            'nom': 'Bennani', 'email': 'ben@x.ma', 'telephone': '0600000000',
            'ville': 'Rabat',
        }
        champs.update(extra)
        return Lead.objects.create(company=self.company, **champs)

    def _dry_run(self, csv_text, target='leads', **options):
        payload = {'file': self._csv(csv_text), 'target': target}
        payload.update(options)
        return self.api.post(DRY_RUN_URL, payload, format='multipart')

    def _commit(self, csv_text, target='leads', client=None, **options):
        payload = {'file': self._csv(csv_text), 'target': target}
        payload.update(options)
        return (client or self.api).post(COMMIT_URL, payload, format='multipart')


class TestApercuEcrasements(EcrasementBase):
    """L'aperçu doit rendre VISIBLE ce qu'un tableur périmé détruirait."""

    def test_apercu_liste_chaque_champ_ecrase_avec_son_ancienne_valeur(self):
        lead = self._lead_reel()
        resp = self._dry_run(
            'Nom,Email,Ville,Whatsapp\n'
            'Bennani,ben@x.ma,Casablanca,0700000000\n',
            mode='upsert')
        self.assertEqual(resp.status_code, 200, resp.data)

        self.assertEqual(resp.data['resume']['mise_a_jour'], 1)
        self.assertEqual(resp.data['ecrasements_total'], 1)
        self.assertEqual(resp.data['lignes_ecrasees'], 1)
        # Défaut = remplissage seul : rien ne serait RÉELLEMENT écrasé.
        self.assertEqual(resp.data['ecrasements_appliques'], 0)

        (conflit,) = resp.data['conflits']
        self.assertEqual(conflit['ligne'], 1)
        self.assertEqual(conflit['action'], 'mise_a_jour')
        self.assertEqual(conflit['cible'], 'crm.lead')
        self.assertEqual(conflit['cible_id'], lead.pk)
        self.assertEqual(conflit['ecrasements'], [
            {'champ': 'ville', 'ancienne': 'Rabat', 'nouvelle': 'Casablanca'},
        ])
        # Le champ vide n'est qu'un remplissage : jamais destructeur.
        self.assertEqual(conflit['remplissages'], ['whatsapp'])

    def test_apercu_avec_ecraser_annonce_ce_qui_sera_reellement_ecrit(self):
        self._lead_reel()
        resp = self._dry_run(
            'Nom,Email,Ville\nBennani,ben@x.ma,Casablanca\n',
            mode='upsert', ecraser='true')
        self.assertEqual(resp.status_code, 200, resp.data)
        self.assertTrue(resp.data['ecraser'])
        self.assertEqual(resp.data['ecrasements_total'], 1)
        self.assertEqual(resp.data['ecrasements_appliques'], 1)

    def test_apercu_n_ecrit_absolument_rien(self):
        lead = self._lead_reel()
        resp = self._dry_run(
            'Nom,Email,Ville\nAUTRE,ben@x.ma,Casablanca\n',
            mode='upsert', ecraser='true')
        self.assertEqual(resp.status_code, 200, resp.data)
        lead.refresh_from_db()
        self.assertEqual(lead.nom, 'Bennani')
        self.assertEqual(lead.ville, 'Rabat')
        self.assertFalse(ImportJob.objects.exists())

    def test_cellule_vide_n_ecrase_ni_ne_vide_jamais_un_champ(self):
        """Colonne présente mais cellule VIDE : ni écrasement ni mise à zéro."""
        lead = self._lead_reel()
        resp = self._dry_run(
            'Nom,Email,Ville\nBennani,ben@x.ma,\n', mode='upsert')
        self.assertEqual(resp.status_code, 200, resp.data)
        self.assertEqual(resp.data['ecrasements_total'], 0)
        self.assertEqual(resp.data['conflits'], [])

        self._commit('Nom,Email,Ville\nBennani,ben@x.ma,\n',
                     mode='upsert', ecraser='true')
        lead.refresh_from_db()
        self.assertEqual(lead.ville, 'Rabat')

    def test_apercu_produits_signale_que_le_catalogue_reel_reste_intact(self):
        """Un tableur périmé sur le catalogue : l'aperçu montre les écarts ET
        dit que la ligne sera IGNORÉE (aucun mode n'écrase un produit)."""
        Produit.objects.create(
            company=self.company, nom='Panneau 550W', sku='SKU-1',
            prix_vente=1200, prix_achat=900)
        resp = self.api_dir.post(
            DRY_RUN_URL,
            {'file': self._csv('Nom,SKU,Prix\nPanneau bradé,SKU-1,10\n'),
             'target': 'products'},
            format='multipart')
        self.assertEqual(resp.status_code, 200, resp.data)
        self.assertEqual(resp.data['resume']['ignoree'], 1)
        # Rien ne sera écrasé : la ligne est ignorée, pas appliquée.
        self.assertEqual(resp.data['ecrasements_total'], 0)

        (conflit,) = resp.data['conflits']
        self.assertEqual(conflit['action'], 'ignoree')
        self.assertEqual(conflit['raison'], 'doublon (SKU existe)')
        self.assertEqual(conflit['cible'], 'stock.produit')
        champs = {e['champ'] for e in conflit['ecrasements']}
        self.assertEqual(champs, {'nom', 'prix_vente'})

    def test_apercu_refuse_le_meme_mode_que_le_commit(self):
        """Un mode refusé à l'écriture doit l'être aussi à l'aperçu (sinon
        l'aperçu promet un rapprochement qui n'aura jamais lieu)."""
        resp = self.api_dir.post(
            DRY_RUN_URL,
            {'file': self._csv('Nom,SKU\nPanneau,SKU-X\n'),
             'target': 'products', 'mode': 'upsert'},
            format='multipart')
        self.assertEqual(resp.status_code, 409, resp.data)


class TestRemplissageSeulParDefaut(EcrasementBase):
    """Défaut sûr : remplir les vides, ne jamais remplacer le saisi."""

    def test_defaut_ne_remplace_aucune_valeur_deja_saisie(self):
        lead = self._lead_reel()
        resp = self._commit(
            'Nom,Email,Telephone,Ville,Whatsapp\n'
            'ECRASE,ben@x.ma,0600000000,Casablanca,0700000000\n',
            mode='upsert')
        self.assertEqual(resp.status_code, 200, resp.data)
        self.assertEqual(resp.data['updated'], 1)
        self.assertEqual(resp.data['ecrasements'], 0)

        lead.refresh_from_db()
        self.assertEqual(lead.nom, 'Bennani')      # valeur réelle préservée
        self.assertEqual(lead.ville, 'Rabat')      # valeur réelle préservée
        self.assertEqual(lead.whatsapp, '0700000000')  # champ vide : rempli

        refuses = {r['champ']: r for r in resp.data['refuses']}
        self.assertEqual(set(refuses), {'nom', 'ville'})
        self.assertEqual(refuses['ville']['ancienne'], 'Rabat')
        self.assertEqual(refuses['ville']['nouvelle'], 'Casablanca')

    def test_un_champ_vide_par_un_humain_n_est_pas_rempli(self):
        # ACVI91 — `saisies_humaines` tient face au remplissage de l'import.
        from apps.records.models import Activity
        from apps.records.provenance import MESSAGE_REFUS

        lead = self._lead_reel(email='', saisies_humaines=['email'])
        resp = self._commit(
            'Telephone,Email\n0600000000,x@exemple.ma\n', mode='maj')

        self.assertEqual(resp.status_code, 200, resp.data)
        lead.refresh_from_db()
        self.assertFalse(lead.email)
        self.assertIn('email', {r['champ'] for r in resp.data['refuses']})
        self.assertTrue(Activity.objects.filter(
            company=self.company, field='email', body=MESSAGE_REFUS).exists())

    def test_les_refus_sont_journalises_ligne_par_ligne(self):
        self._lead_reel()
        resp = self._commit(
            'Nom,Email,Ville\nECRASE,ben@x.ma,Casablanca\n', mode='upsert')
        job = ImportJob.objects.get(pk=resp.data['job_id'])
        self.assertFalse(job.ecraser)
        self.assertEqual(job.ecrasement_count, 0)
        self.assertEqual(job.refus_count, 2)

        row = ImportJobRow.objects.get(job=job, ligne=1)
        self.assertEqual({r['champ'] for r in row.refuses}, {'nom', 'ville'})
        self.assertEqual([m['champ'] for m in row.modifications], [])

    def test_maj_en_masse_legitime_fonctionne_toujours(self):
        """Non-régression : remplir en masse des champs VIDES ne demande aucun
        opt-in (c'est le cas d'usage normal, il ne doit pas être bridé)."""
        for i in range(3):
            Lead.objects.create(
                company=self.company, nom=f'Lead {i}', email=f'l{i}@x.ma')
        resp = self._commit(
            'Nom,Email,Ville,Whatsapp\n'
            'Lead 0,l0@x.ma,Rabat,0700000000\n'
            'Lead 1,l1@x.ma,Fès,0700000001\n'
            'Lead 2,l2@x.ma,Agadir,0700000002\n',
            mode='maj')
        self.assertEqual(resp.status_code, 200, resp.data)
        self.assertEqual(resp.data['updated'], 3)
        self.assertEqual(resp.data['refuses'], [])
        self.assertEqual(
            sorted(Lead.objects.filter(company=self.company)
                   .values_list('ville', flat=True)),
            ['Agadir', 'Fès', 'Rabat'])


class TestOptInEcraserJournalise(EcrasementBase):
    """Avec l'opt-in explicite, l'écrasement est autorisé — mais tracé."""

    def test_ecraser_applique_et_conserve_chaque_valeur_precedente(self):
        lead = self._lead_reel()
        resp = self._commit(
            'Nom,Email,Ville\nNouveauNom,ben@x.ma,Casablanca\n',
            mode='upsert', ecraser='true')
        self.assertEqual(resp.status_code, 200, resp.data)
        self.assertEqual(resp.data['ecrasements'], 2)
        self.assertEqual(resp.data['refuses'], [])

        lead.refresh_from_db()
        self.assertEqual(lead.nom, 'NouveauNom')
        self.assertEqual(lead.ville, 'Casablanca')

        job = ImportJob.objects.get(pk=resp.data['job_id'])
        self.assertTrue(job.ecraser)
        self.assertEqual(job.ecrasement_count, 2)

        row = ImportJobRow.objects.get(job=job, ligne=1)
        self.assertEqual(row.cible_type, 'crm.lead')
        self.assertEqual(row.cible_id, lead.pk)
        anciennes = {m['champ']: m['ancienne'] for m in row.modifications}
        self.assertEqual(anciennes['nom'], 'Bennani')
        self.assertEqual(anciennes['ville'], 'Rabat')
        self.assertTrue(all(m['ecrasement'] for m in row.modifications))

    def test_audit_log_porte_le_diff_structure_et_la_societe(self):
        lead = self._lead_reel()
        self._commit('Nom,Email,Ville\nNouveauNom,ben@x.ma,Casablanca\n',
                     mode='upsert', ecraser='true')

        entree = AuditLog.objects.filter(
            company=self.company, action=AuditLog.Action.UPDATE,
            object_id=str(lead.pk),
            detail__startswith='Import').order_by('-id').first()
        self.assertIsNotNone(entree, 'aucune ligne d’audit pour l’écrasement')
        diff = {c['field']: c for c in (entree.changes or [])}
        self.assertEqual(diff['ville']['old'], 'Rabat')
        self.assertEqual(diff['ville']['new'], 'Casablanca')
        self.assertEqual(entree.user, self.user)

    def test_remplissage_seul_est_aussi_journalise(self):
        """Même sans écrasement, la valeur précédente (vide) est conservée :
        toute modification faite par un import reste réversible."""
        self._lead_reel()
        resp = self._commit('Nom,Email,Whatsapp\nBennani,ben@x.ma,0700000000\n',
                            mode='upsert')
        job = ImportJob.objects.get(pk=resp.data['job_id'])
        row = ImportJobRow.objects.get(job=job, ligne=1)
        self.assertEqual(row.modifications, [
            {'champ': 'whatsapp', 'ancienne': '', 'nouvelle': '0700000000',
             'ecrasement': False},
        ])
        self.assertEqual(job.ecrasement_count, 0)


class TestIsolationTenantEcrasement(EcrasementBase):
    """Le rapprochement de l'aperçu ne doit JAMAIS traverser les sociétés."""

    def test_apercu_ignore_les_fiches_d_une_autre_societe(self):
        autre = Company.objects.create(slug='imp-co-ecr', nom='Imp Co Ecr')
        etranger = Lead.objects.create(
            company=autre, nom='Autre', email='ben@x.ma', ville='Tanger')

        resp = self._dry_run(
            'Nom,Email,Ville\nBennani,ben@x.ma,Casablanca\n', mode='upsert')
        self.assertEqual(resp.status_code, 200, resp.data)
        self.assertEqual(resp.data['conflits'], [])
        self.assertEqual(resp.data['ecrasements_total'], 0)
        self.assertEqual(resp.data['resume']['creation'], 1)

        self._commit('Nom,Email,Ville\nBennani,ben@x.ma,Casablanca\n',
                     mode='upsert', ecraser='true')
        etranger.refresh_from_db()
        self.assertEqual(etranger.nom, 'Autre')
        self.assertEqual(etranger.ville, 'Tanger')

    def test_apercu_creer_doublon_hors_portee_sans_nommer_la_fiche(self):
        """ERR-W33-IMPORT-PORTEE — en mode ``creer``, le doublon d'un collègue
        est une ligne de refus : ni id, ni nom, ni valeur ; son propriétaire,
        lui, voit la fiche qu'il a déjà. Le commit ne crée rien."""
        from django.contrib.auth import get_user_model
        from rest_framework.test import APIClient

        from apps.roles.models import Role
        from apps.roles.permissions_registre import COMMERCIAL_PERMISSIONS

        role = Role.objects.create(
            company=self.company, nom='Commercial portee',
            permissions=list(COMMERCIAL_PERMISSIONS))

        def compte(nom):
            client = APIClient()
            utilisateur = get_user_model().objects.create_user(
                username=f'portee-{nom}', password='x', company=self.company,
                role=role)
            client.force_authenticate(utilisateur)
            return utilisateur, client

        c1, api_c1 = compte('c1')
        _c2, api_c2 = compte('c2')
        lead = Lead.objects.create(
            company=self.company, nom='Alaoui Secret', owner=c1,
            telephone='0600000009', email='secret@x.ma', ville='Agadir')
        csv_text = 'nom,telephone,ville\nAutre,0600000009,Rabat\n'
        options = {'target': 'leads', 'mode': 'creer'}

        apercu = api_c2.post(
            DRY_RUN_URL, {'file': self._csv(csv_text), **options},
            format='multipart')
        self.assertEqual(apercu.status_code, 200, apercu.data)
        self.assertEqual(apercu.data['resume']['ignoree'], 1)
        ligne = apercu.data['conflits'][0]
        self.assertEqual(ligne['action'], 'ignoree')
        self.assertIsNone(ligne['cible_id'])
        self.assertEqual(ligne['cible_libelle'], '')
        self.assertEqual(ligne['ecrasements'], [])
        self.assertEqual(ligne['remplissages'], [])
        self.assertEqual(ligne['raison'], 'doublon (fiche hors de votre portée)')
        for valeur in ('Alaoui', 'Secret', 'secret@x.ma', 'Agadir'):
            self.assertNotIn(valeur, str(apercu.data))

        commit = api_c2.post(
            COMMIT_URL, {'file': self._csv(csv_text), **options},
            format='multipart')
        self.assertEqual(commit.status_code, 200, commit.data)
        self.assertFalse(Lead.objects.filter(nom='Autre').exists())

        propre = api_c1.post(
            DRY_RUN_URL, {'file': self._csv(csv_text), **options},
            format='multipart')
        self.assertEqual(propre.status_code, 200, propre.data)
        self.assertEqual(propre.data['conflits'][0]['cible_id'], lead.pk)

    def test_cible_lead_hors_droit_ou_hors_portee(self):
        """ACVI1 — droit `crm_modifier` et portée de l'appelant : ni lecture
        (aperçu) ni réécriture (commit) du lead d'un collègue."""
        from django.contrib.auth import get_user_model
        from rest_framework.test import APIClient

        from apps.roles.models import Role
        from apps.roles.permissions_registre import (
            ADMIN_RH_PERMISSIONS, COMMERCIAL_PERMISSIONS,
            TECHNICIEN_PERMISSIONS)

        def compte(nom, permissions):
            role = Role.objects.create(
                company=self.company, nom=f'{nom} ACVI1',
                permissions=list(permissions))
            return get_user_model().objects.create_user(
                username=f'acvi1-{nom}', password='x', company=self.company,
                role=role)

        def api(utilisateur):
            client = APIClient()
            client.force_authenticate(utilisateur)
            return client

        c1 = compte('c1', COMMERCIAL_PERMISSIONS)
        c2 = compte('c2', COMMERCIAL_PERMISSIONS)
        lead = Lead.objects.create(
            company=self.company, nom='Alaoui', owner=c1,
            telephone='0600000001', email='a@x.ma')
        csv_text = 'telephone,email\n0600000001,b@y.ma\n'
        options = {'target': 'leads', 'mode': 'maj', 'ecraser': 'true'}

        for nom, permissions in (('rh', ADMIN_RH_PERMISSIONS),
                                 ('tech', TECHNICIEN_PERMISSIONS)):
            client = api(compte(nom, permissions))
            for url in (DRY_RUN_URL, COMMIT_URL):
                resp = client.post(
                    url, {'file': self._csv(csv_text), **options},
                    format='multipart')
                self.assertEqual(resp.status_code, 403, resp.data)
                self.assertEqual(resp.data.get('code'), 'droit_manquant')

        client = api(c2)
        apercu = client.post(
            DRY_RUN_URL, {'file': self._csv(csv_text), **options},
            format='multipart')
        self.assertEqual(apercu.status_code, 200, apercu.data)
        self.assertFalse(
            [c for c in apercu.data['conflits'] if c.get('cible_id')])
        self.assertNotIn('a@x.ma', str(apercu.data))
        commit = client.post(
            COMMIT_URL, {'file': self._csv(csv_text), **options},
            format='multipart')
        self.assertEqual(commit.status_code, 200, commit.data)
        self.assertEqual(commit.data['updated'], 0)
        lead.refresh_from_db()
        self.assertEqual(lead.email, 'a@x.ma')

        # Le propriétaire, lui, garde son geste.
        propre = api(c1).post(
            COMMIT_URL, {'file': self._csv(csv_text), **options},
            format='multipart')
        self.assertEqual(propre.status_code, 200, propre.data)
        lead.refresh_from_db()
        self.assertEqual(lead.email, 'b@y.ma')

    def _api_role(self, nom, permissions):
        """Client authentifié d'un compte au rôle LIVRÉ ``permissions``."""
        from django.contrib.auth import get_user_model
        from rest_framework.test import APIClient

        from apps.roles.models import Role
        role = Role.objects.create(
            company=self.company, nom=f'{nom} ADRG', permissions=list(permissions))
        client = APIClient()
        client.force_authenticate(get_user_model().objects.create_user(
            username=f'adrg-{nom}', password='x', company=self.company, role=role))
        return client

    def test_import_factures_exige_ventes_creer(self):
        """ADRG61 — un Technicien n'importe aucune facture (série légale)."""
        from apps.crm.models import Client
        from apps.facturation.models import Facture
        from apps.roles.permissions_registre import (
            COMMERCIAL_PERMISSIONS, TECHNICIEN_PERMISSIONS)
        Client.objects.create(company=self.company, nom='Alaoui', email='a@x.ma')
        csv_text = 'client_email,statut\na@x.ma,emise\n'
        tech = self._api_role('tech61', TECHNICIEN_PERMISSIONS)
        for url in (DRY_RUN_URL, COMMIT_URL):
            resp = tech.post(url, {'file': self._csv(csv_text), 'target': 'factures'},
                             format='multipart')
            self.assertEqual(resp.status_code, 403, resp.data)
            self.assertEqual(resp.data['code'], 'droit_manquant')
            self.assertIn('ventes_creer', resp.data['detail'])
        self.assertFalse(Facture.objects.filter(company=self.company).exists())
        resp = self._commit(csv_text, target='factures',
                            client=self._api_role('com61', COMMERCIAL_PERMISSIONS))
        self.assertEqual(resp.status_code, 200, resp.data)
        self.assertEqual(resp.data['created'], 1)

    def test_upsert_contact_hors_portee_jamais_cree(self):
        """ERR-W33-IMPORT-DOUBLON — en ``upsert``, le contact d'un lead hors de
        portée n'est ni réécrit ni recréé : la ligne est ignorée, avec son motif,
        sans nommer la fiche ; l'aperçu annonce la même chose que le commit."""
        from django.contrib.auth import get_user_model
        from rest_framework.test import APIClient

        from apps.roles.models import Role
        from apps.roles.permissions_registre import COMMERCIAL_PERMISSIONS

        role = Role.objects.create(
            company=self.company, nom='Commercial doublon',
            permissions=list(COMMERCIAL_PERMISSIONS))

        def compte(nom):
            return get_user_model().objects.create_user(
                username=f'doublon-{nom}', password='x', company=self.company,
                role=role)
        lead = Lead.objects.create(
            company=self.company, nom='Alaoui', owner=compte('c1'),
            telephone='0600000001', email='a@x.ma')
        client = APIClient()
        client.force_authenticate(compte('c2'))
        csv_text = 'nom,telephone\nDoublon,+212600000001\nNeuf,0600000002\n'
        options = {'target': 'leads', 'mode': 'upsert'}

        apercu = client.post(
            DRY_RUN_URL, {'file': self._csv(csv_text), **options},
            format='multipart')
        self.assertEqual(apercu.status_code, 200, apercu.data)
        self.assertEqual(apercu.data['resume']['creation'], 1)
        self.assertEqual(apercu.data['resume']['ignoree'], 1)
        self.assertIn('hors de votre portée', apercu.data['conflits'][0]['raison'])
        self.assertIsNone(apercu.data['conflits'][0]['cible_id'])
        self.assertNotIn('Alaoui', str(apercu.data))

        commit = client.post(
            COMMIT_URL, {'file': self._csv(csv_text), **options},
            format='multipart')
        self.assertEqual(commit.status_code, 200, commit.data)
        self.assertEqual(commit.data['created'], 1)
        self.assertEqual(commit.data['updated'], 0)
        self.assertEqual(
            Lead.objects.filter(company=self.company, nom='Doublon').count(), 0)
        self.assertEqual(
            Lead.objects.filter(company=self.company, nom='Neuf').count(), 1)
        lead.refresh_from_db()
        self.assertEqual(lead.nom, 'Alaoui')

    def test_apercu_reserve_aux_roles_autorises(self):
        """L'aperçu expose des valeurs internes (dont ``prix_achat`` pour le
        catalogue) : il reste derrière la même garde que le commit, jamais
        accessible publiquement."""
        from rest_framework.test import APIClient
        anonyme = APIClient()
        resp = anonyme.post(
            DRY_RUN_URL,
            {'file': self._csv('Nom,Email\nX,x@x.ma\n'), 'target': 'leads'},
            format='multipart')
        self.assertIn(resp.status_code, (401, 403))
