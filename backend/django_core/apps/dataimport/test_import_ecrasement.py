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
        self.assertEqual(resp.status_code, 400, resp.data)


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
