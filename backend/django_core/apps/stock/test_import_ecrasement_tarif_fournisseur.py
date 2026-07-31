"""Garde-fou anti-écrasement de l'import de tarif fournisseur (XPUR14).

Le catalogue est le SEUL jeu de données réel et non reconstructible du parc :
les prix d'ACHAT fournisseur y sont saisis à la main. Cet import écrit
directement dessus (``PrixFournisseur.prix_achat`` + les paliers de quantité) —
il porte donc les trois mêmes protections que l'import générique
``apps.dataimport``, dont il RÉUTILISE les primitives :

1. l'aperçu (``apercu=True``) annonce, ligne par ligne et champ par champ, ce
   qui serait remplacé — AVANT toute écriture, et sans rien écrire lui-même ;
2. l'écriture est en REMPLISSAGE SEUL par défaut (un prix déjà saisi n'est
   jamais remplacé sans ``ecraser=True``), la mise à jour de masse légitime
   restant parfaitement fonctionnelle avec l'opt-in ;
3. chaque valeur remplacée est conservée (``ImportJobRow.modifications`` +
   ``AuditLog`` via la primitive plateforme ``apps.audit.recorder``).

Run:
    python manage.py test apps.stock.test_import_ecrasement_tarif_fournisseur -v 2
"""
import datetime
import io
from decimal import Decimal

from django.core.files.uploadedfile import SimpleUploadedFile

from apps.audit.models import AuditLog
from apps.dataimport.models import ImportJob, ImportJobRow
from apps.stock.models import (
    Fournisseur, PalierPrixFournisseur, PrixFournisseur, Produit,
)
from apps.stock.services import import_prix_fournisseur_xlsx
from authentication.models import Company

from .test_xpur14_prix_fournisseur_enrichi import Xpur14Base

IMPORT_URL = '/api/django/stock/prix-fournisseurs/import-xlsx/'
ENTETES = ['sku', 'produit', 'ref_produit_fournisseur', 'prix_achat',
           'date_debut', 'date_fin', 'paliers']


def _xlsx(rows):
    from openpyxl import Workbook
    wb = Workbook()
    ws = wb.active
    ws.append(ENTETES)
    for row in rows:
        ws.append(row)
    buf = io.BytesIO()
    wb.save(buf)
    return buf.getvalue()


class EcrasementTarifBase(Xpur14Base):
    def _tarif_reel(self, **extra):
        """Tarif « réel » déjà négocié — exactement ce qu'un tableur périmé
        ne doit pas pouvoir détruire en silence."""
        champs = {
            'company': self.company, 'produit': self.produit,
            'fournisseur': self.fournisseur,
            'prix_achat': Decimal('1000'),
            'ref_produit_fournisseur': 'REF-REELLE',
            'date_debut': datetime.date(2026, 1, 1),
        }
        champs.update(extra)
        return PrixFournisseur.objects.create(**champs)

    def _import(self, rows, **options):
        return import_prix_fournisseur_xlsx(
            self.company, self.fournisseur, _xlsx(rows),
            filename='tarif.xlsx', user=self.user, **options)


class TestApercuTarifFournisseur(EcrasementTarifBase):
    """L'aperçu doit rendre VISIBLE ce qu'un tableur périmé détruirait."""

    def test_apercu_liste_chaque_champ_ecrase_avec_son_ancienne_valeur(self):
        tarif = self._tarif_reel()
        rapport = self._import(
            [[self.produit.sku, self.produit.nom, 'REF-FICHIER', 1100,
              None, None, '']],
            apercu=True)

        self.assertTrue(rapport['apercu'])
        self.assertEqual(rapport['updated'], 1)
        self.assertEqual(rapport['ecrasements_total'], 2)
        # Défaut = remplissage seul : rien ne serait RÉELLEMENT écrasé.
        self.assertEqual(rapport['ecrasements_appliques'], 0)

        (conflit,) = rapport['conflits']
        self.assertEqual(conflit['ligne'], 2)
        self.assertEqual(conflit['action'], 'mise_a_jour')
        self.assertEqual(conflit['cible'], 'achats.prixfournisseur')
        self.assertEqual(conflit['cible_id'], tarif.pk)
        ecrases = {e['champ']: e for e in conflit['ecrasements']}
        self.assertEqual(ecrases['prix_achat']['ancienne'], '1000.00')
        self.assertEqual(ecrases['prix_achat']['nouvelle'], '1100.00')
        self.assertEqual(
            ecrases['ref_produit_fournisseur']['ancienne'], 'REF-REELLE')
        self.assertEqual(
            ecrases['ref_produit_fournisseur']['nouvelle'], 'REF-FICHIER')

    def test_apercu_signale_aussi_les_paliers_ecrases(self):
        tarif = self._tarif_reel()
        PalierPrixFournisseur.objects.create(
            prix_fournisseur=tarif, qte_min=10, prix=Decimal('950'))
        rapport = self._import(
            [[self.produit.sku, self.produit.nom, 'REF-REELLE', 1000,
              None, None, '10:800;50:700']],
            apercu=True)

        (conflit,) = rapport['conflits']
        ecrases = {e['champ']: e for e in conflit['ecrasements']}
        self.assertEqual(ecrases['palier 10']['ancienne'], '950.00')
        self.assertEqual(ecrases['palier 10']['nouvelle'], '800.00')
        # Le palier 50 n'existe pas : c'est un simple remplissage.
        self.assertIn('palier 50', conflit['remplissages'])

    def test_apercu_n_ecrit_absolument_rien(self):
        tarif = self._tarif_reel()
        self._import(
            [[self.produit.sku, self.produit.nom, 'REF-FICHIER', 1100,
              None, None, '10:800']],
            apercu=True, ecraser=True)

        tarif.refresh_from_db()
        self.assertEqual(tarif.prix_achat, Decimal('1000.00'))
        self.assertEqual(tarif.ref_produit_fournisseur, 'REF-REELLE')
        self.assertFalse(tarif.paliers.exists())
        self.assertFalse(ImportJob.objects.exists())

    def test_apercu_avec_ecraser_annonce_ce_qui_sera_reellement_ecrit(self):
        self._tarif_reel()
        rapport = self._import(
            [[self.produit.sku, self.produit.nom, 'REF-REELLE', 1100,
              None, None, '']],
            apercu=True, ecraser=True)
        self.assertEqual(rapport['ecrasements_total'], 1)
        self.assertEqual(rapport['ecrasements_appliques'], 1)


class TestRemplissageSeulParDefaut(EcrasementTarifBase):
    """Défaut sûr : remplir les vides, ne jamais remplacer le prix négocié."""

    def test_defaut_ne_remplace_aucun_prix_deja_saisi(self):
        tarif = self._tarif_reel()
        rapport = self._import(
            [[self.produit.sku, self.produit.nom, 'REF-FICHIER', 1100,
              None, '2026-12-31', '']])

        self.assertEqual(rapport['updated'], 1)
        self.assertEqual(rapport['ecrasements_appliques'], 0)

        tarif.refresh_from_db()
        self.assertEqual(tarif.prix_achat, Decimal('1000.00'))
        self.assertEqual(tarif.ref_produit_fournisseur, 'REF-REELLE')
        # Champ vide : rempli (jamais destructeur).
        self.assertEqual(tarif.date_fin, datetime.date(2026, 12, 31))

        refuses = {r['champ']: r for r in rapport['refuses']}
        self.assertEqual(set(refuses), {'prix_achat', 'ref_produit_fournisseur'})
        self.assertEqual(refuses['prix_achat']['ancienne'], '1000.00')
        self.assertEqual(refuses['prix_achat']['nouvelle'], '1100.00')

    def test_un_palier_deja_saisi_est_protege_de_la_meme_facon(self):
        tarif = self._tarif_reel()
        PalierPrixFournisseur.objects.create(
            prix_fournisseur=tarif, qte_min=10, prix=Decimal('950'))
        rapport = self._import(
            [[self.produit.sku, self.produit.nom, 'REF-REELLE', 1000,
              None, None, '10:800;50:700']])

        palier = PalierPrixFournisseur.objects.get(
            prix_fournisseur=tarif, qte_min=10)
        self.assertEqual(palier.prix, Decimal('950.00'))
        nouveau = PalierPrixFournisseur.objects.get(
            prix_fournisseur=tarif, qte_min=50)
        self.assertEqual(nouveau.prix, Decimal('700.00'))
        self.assertEqual([r['champ'] for r in rapport['refuses']],
                         ['palier 10'])

    def test_les_refus_sont_journalises_ligne_par_ligne(self):
        self._tarif_reel()
        rapport = self._import(
            [[self.produit.sku, self.produit.nom, 'REF-FICHIER', 1100,
              None, None, '']])

        job = ImportJob.objects.get(pk=rapport['job_id'])
        self.assertEqual(job.target, 'prix_fournisseur')
        self.assertEqual(job.company, self.company)
        self.assertFalse(job.ecraser)
        self.assertEqual(job.ecrasement_count, 0)
        self.assertEqual(job.refus_count, 2)

        row = ImportJobRow.objects.get(job=job, ligne=2)
        self.assertEqual(row.cible_type, 'achats.prixfournisseur')
        self.assertEqual({r['champ'] for r in row.refuses},
                         {'prix_achat', 'ref_produit_fournisseur'})

    def test_maj_en_masse_legitime_fonctionne_sans_opt_in(self):
        """Non-régression : remplir en masse des champs VIDES (et créer les
        tarifs manquants) ne demande aucun opt-in."""
        autre = Produit.objects.create(
            company=self.company, nom='Panneau 550W', sku='PAN-ECR',
            prix_vente=Decimal('900'), prix_achat=Decimal('500'))
        PrixFournisseur.objects.create(
            company=self.company, produit=autre, fournisseur=self.fournisseur,
            prix_achat=Decimal('0'))

        rapport = self._import([
            [self.produit.sku, self.produit.nom, 'REF-A', 1500, None, None, ''],
            [autre.sku, autre.nom, 'REF-B', 550, None, None, '10:500'],
        ])
        self.assertEqual(rapport['created'], 1)
        self.assertEqual(rapport['updated'], 1)
        self.assertEqual(rapport['refuses'], [])

        pf = PrixFournisseur.objects.get(
            produit=autre, fournisseur=self.fournisseur)
        self.assertEqual(pf.ref_produit_fournisseur, 'REF-B')
        self.assertEqual(pf.paliers.get(qte_min=10).prix, Decimal('500.00'))

    def test_reimport_du_meme_fichier_n_est_jamais_un_ecrasement(self):
        """Rejouer le MÊME tarif ne doit rien signaler : « 1000 » écrit sans
        décimale revient de la base en « 1000.00 » — sans quantification à la
        précision du champ, le garde-fou verrait un faux écrasement et
        refuserait une ligne pourtant identique."""
        tarif = self._tarif_reel()
        PalierPrixFournisseur.objects.create(
            prix_fournisseur=tarif, qte_min=10, prix=Decimal('950'))
        rows = [[self.produit.sku, self.produit.nom, 'REF-REELLE', 1000,
                 '2026-01-01', None, '10:950']]

        apercu = self._import(rows, apercu=True)
        self.assertEqual(apercu['ecrasements_total'], 0)
        self.assertEqual(apercu['conflits'], [])

        rapport = self._import(rows)
        self.assertEqual(rapport['refuses'], [])
        self.assertEqual(rapport['ecrasements_appliques'], 0)

    def test_cellule_vide_n_ecrase_ni_ne_vide_jamais_un_champ(self):
        """Colonne présente mais cellule VIDE : ni écrasement ni mise à zéro —
        c'était le trou de l'ancienne version (``or None`` / ``or ''``)."""
        tarif = self._tarif_reel()
        self._import(
            [[self.produit.sku, self.produit.nom, '', 1000, None, None, '']],
            ecraser=True)

        tarif.refresh_from_db()
        self.assertEqual(tarif.ref_produit_fournisseur, 'REF-REELLE')
        self.assertEqual(tarif.date_debut, datetime.date(2026, 1, 1))


class TestOptInEcraserJournalise(EcrasementTarifBase):
    """Avec l'opt-in explicite, l'écrasement est autorisé — mais tracé."""

    def test_ecraser_applique_et_conserve_chaque_valeur_precedente(self):
        tarif = self._tarif_reel()
        rapport = self._import(
            [[self.produit.sku, self.produit.nom, 'REF-FICHIER', 1100,
              None, None, '']],
            ecraser=True)

        self.assertEqual(rapport['ecrasements_appliques'], 2)
        self.assertEqual(rapport['refuses'], [])

        tarif.refresh_from_db()
        self.assertEqual(tarif.prix_achat, Decimal('1100.00'))
        self.assertEqual(tarif.ref_produit_fournisseur, 'REF-FICHIER')

        job = ImportJob.objects.get(pk=rapport['job_id'])
        self.assertTrue(job.ecraser)
        self.assertEqual(job.ecrasement_count, 2)

        row = ImportJobRow.objects.get(job=job, ligne=2)
        anciennes = {m['champ']: m['ancienne'] for m in row.modifications}
        self.assertEqual(anciennes['prix_achat'], '1000.00')
        self.assertEqual(anciennes['ref_produit_fournisseur'], 'REF-REELLE')
        self.assertTrue(all(m['ecrasement'] for m in row.modifications))

    def test_audit_log_porte_le_diff_structure_et_la_societe(self):
        tarif = self._tarif_reel()
        self._import(
            [[self.produit.sku, self.produit.nom, 'REF-REELLE', 1100,
              None, None, '']],
            ecraser=True)

        entree = AuditLog.objects.filter(
            company=self.company, action=AuditLog.Action.UPDATE,
            object_id=str(tarif.pk),
            detail__startswith='Import').order_by('-id').first()
        self.assertIsNotNone(entree, 'aucune ligne d’audit pour l’écrasement')
        diff = {c['field']: c for c in (entree.changes or [])}
        self.assertEqual(diff['prix_achat']['old'], '1000.00')
        self.assertEqual(diff['prix_achat']['new'], '1100.00')
        self.assertEqual(entree.user, self.user)


class TestIsolationTenantTarif(EcrasementTarifBase):
    """Le rapprochement ne doit JAMAIS traverser les sociétés."""

    def test_le_tarif_d_une_autre_societe_reste_intact(self):
        autre = Company.objects.create(slug='xpur14-co-b', nom='Xpur14 Co B')
        produit_b = Produit.objects.create(
            company=autre, nom='Onduleur X14', sku=self.produit.sku,
            prix_vente=Decimal('2000'), prix_achat=Decimal('1200'))
        fournisseur_b = Fournisseur.objects.create(
            company=autre, nom='Fournisseur Tarif')
        tarif_b = PrixFournisseur.objects.create(
            company=autre, produit=produit_b, fournisseur=fournisseur_b,
            prix_achat=Decimal('777'))

        self._import(
            [[self.produit.sku, self.produit.nom, 'REF-FICHIER', 1100,
              None, None, '']],
            ecraser=True)

        tarif_b.refresh_from_db()
        self.assertEqual(tarif_b.prix_achat, Decimal('777.00'))


class TestEndpointGardeFou(EcrasementTarifBase):
    """L'API expose l'aperçu et exige l'opt-in explicite pour écraser."""

    def _post(self, rows, **payload):
        upload = SimpleUploadedFile(
            'tarif.xlsx', _xlsx(rows),
            content_type=('application/vnd.openxmlformats-officedocument'
                          '.spreadsheetml.sheet'))
        corps = {'fournisseur': self.fournisseur.id, 'file': upload}
        corps.update(payload)
        return self.api.post(IMPORT_URL, corps, format='multipart')

    def test_apercu_par_l_api_n_ecrit_rien(self):
        tarif = self._tarif_reel()
        resp = self._post(
            [[self.produit.sku, self.produit.nom, 'REF-FICHIER', 1100,
              None, None, '']],
            apercu='true')
        self.assertEqual(resp.status_code, 200, resp.data)
        self.assertEqual(resp.data['ecrasements_total'], 2)
        tarif.refresh_from_db()
        self.assertEqual(tarif.prix_achat, Decimal('1000.00'))

    def test_sans_ecraser_l_api_preserve_le_prix_reel(self):
        tarif = self._tarif_reel()
        resp = self._post(
            [[self.produit.sku, self.produit.nom, 'REF-FICHIER', 1100,
              None, None, '']])
        self.assertEqual(resp.status_code, 200, resp.data)
        self.assertEqual(len(resp.data['refuses']), 2)
        tarif.refresh_from_db()
        self.assertEqual(tarif.prix_achat, Decimal('1000.00'))

    def test_une_valeur_ambigue_n_active_jamais_l_ecrasement(self):
        """Seul un « vrai » explicite ouvre l'écrasement : un drapeau mal
        formé laisse le garde-fou en place."""
        tarif = self._tarif_reel()
        resp = self._post(
            [[self.produit.sku, self.produit.nom, 'REF-FICHIER', 1100,
              None, None, '']],
            ecraser='peut-etre')
        self.assertEqual(resp.status_code, 200, resp.data)
        self.assertFalse(resp.data['ecraser'])
        tarif.refresh_from_db()
        self.assertEqual(tarif.prix_achat, Decimal('1000.00'))

    def test_avec_ecraser_l_api_applique_et_trace(self):
        tarif = self._tarif_reel()
        resp = self._post(
            [[self.produit.sku, self.produit.nom, 'REF-FICHIER', 1100,
              None, None, '']],
            ecraser='true')
        self.assertEqual(resp.status_code, 200, resp.data)
        tarif.refresh_from_db()
        self.assertEqual(tarif.prix_achat, Decimal('1100.00'))
        job = ImportJob.objects.get(pk=resp.data['job_id'])
        self.assertEqual(job.ecrasement_count, 2)
