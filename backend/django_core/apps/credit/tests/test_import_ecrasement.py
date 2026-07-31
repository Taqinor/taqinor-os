"""Garde-fou écrasement de ``importer_limites_csv`` (audit : l'import de
limites de crédit écrasait des fiches EXISTANTES sans aperçu ni journal).

Réutilise la primitive PLATEFORME ``apps.dataimport.services``
(``diff_import``/``appliquer_maj_import``/``enregistrer_job``) — ces tests
vérifient le CONTRAT vu depuis ``apps.credit`` (aperçu, remplissage seul par
défaut, opt-in ``ecraser``, cellule vide jamais destructrice, isolation
société), pas la primitive elle-même (déjà testée dans
``apps/dataimport/test_import_ecrasement.py``)."""
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.contrib.contenttypes.models import ContentType
from django.test import TestCase

from authentication.models import Company
from apps.audit.models import AuditLog
from apps.credit.models import LimiteCredit
from apps.credit.services import importer_limites_csv
from apps.crm.models import Client
from apps.dataimport.models import ImportJob, ImportJobRow

User = get_user_model()


def make_company(slug, nom):
    company, _ = Company.objects.get_or_create(slug=slug, defaults={'nom': nom})
    return company


class ImportLimitesEcrasementTests(TestCase):
    def setUp(self):
        self.company = make_company('imp-ecr-co', 'Import Écrasement Co')
        self.user = User.objects.create_user(
            username='imp_ecr_user', password='x', role_legacy='admin',
            company=self.company)
        # Fiche RÉELLE déjà saisie à la main : c'est celle-ci qu'un fichier
        # périmé ne doit jamais écraser en silence.
        self.c1 = Client.objects.create(
            company=self.company, nom='Un', email='c1@imp-ecr.com')
        self.limite_c1 = LimiteCredit.objects.create(
            company=self.company, client=self.c1,
            montant_limite=Decimal('50000'), mode_hold='blocage')
        # Client sans limite définie (champ vide) : sert la mise à jour
        # légitime « remplissage de champ vide ».
        self.c2 = Client.objects.create(
            company=self.company, nom='Deux', email='c2@imp-ecr.com')
        self.limite_c2 = LimiteCredit.objects.create(
            company=self.company, client=self.c2, montant_limite=None)

    # -- 1. Aperçu : signale l'écrasement, n'écrit rien ---------------------

    def test_apercu_signale_ecrasement_sans_rien_ecrire(self):
        """Un aperçu sur une ligne qui REMPLACERAIT une valeur réelle liste le
        champ, l'ancienne et la nouvelle valeur — et n'écrit rien du tout."""
        csv = b'client,montant_limite\nc1@imp-ecr.com,99000\n'
        rapport = importer_limites_csv(
            self.company, csv, 'l.csv', user=self.user, apercu=True)

        self.assertTrue(rapport['apercu'])
        self.assertEqual(rapport['maj'], 1)
        self.assertEqual(rapport['creations'], 0)
        self.assertEqual(len(rapport['conflits']), 1)
        conflit = rapport['conflits'][0]
        self.assertEqual(conflit['client_id'], self.c1.pk)
        # Les deux côtés sont la forme TEXTE d'un ``DecimalField(
        # decimal_places=2)`` : la valeur STOCKÉE revient de la base avec ses
        # 2 décimales fixes, et la valeur du FICHIER est quantifiée à la même
        # précision par le service — sinon « 50000 » et « 50000.00 »
        # passeraient pour un écrasement alors que c'est la même somme.
        self.assertEqual(conflit['ecrasements'], [
            {'champ': 'montant_limite', 'ancienne': '50000.00',
             'nouvelle': '99000.00'},
        ])

        # Rien n'a été écrit : ni la fiche, ni un ImportJob.
        self.limite_c1.refresh_from_db()
        self.assertEqual(self.limite_c1.montant_limite, Decimal('50000'))
        self.assertEqual(ImportJob.objects.filter(company=self.company).count(), 0)

    # -- 2. Remplissage seul par défaut : préserve, renvoie le refus --------

    def test_remplissage_seul_par_defaut_preserve_champ_rempli(self):
        """Sans ``ecraser=True``, un champ déjà rempli reste intact et la
        valeur entrante repart dans ``refuses`` (rien n'est avalé en silence)."""
        csv = b'client,montant_limite\nc1@imp-ecr.com,99000\n'
        rapport = importer_limites_csv(
            self.company, csv, 'l.csv', user=self.user)

        self.limite_c1.refresh_from_db()
        self.assertEqual(self.limite_c1.montant_limite, Decimal('50000'))
        self.assertEqual(rapport['crees'], 0)
        self.assertEqual(len(rapport['ecrasements']), 0)
        self.assertEqual(len(rapport['refuses']), 1)
        refus = rapport['refuses'][0]
        self.assertEqual(refus['champ'], 'montant_limite')
        self.assertEqual(refus['ancienne'], '50000.00')
        self.assertEqual(refus['nouvelle'], '99000.00')
        self.assertEqual(refus['client_id'], self.c1.pk)

    # -- 3. ecraser=True : applique ET journalise la valeur précédente ------

    def test_ecraser_true_applique_et_journalise_valeur_precedente(self):
        """Avec l'opt-in explicite ``ecraser=True``, le remplacement s'applique
        réellement — et la valeur PRÉCÉDENTE est tracée sur l'``ImportJobRow``
        et dans une ligne ``AuditLog`` (réversible)."""
        csv = b'client,montant_limite\nc1@imp-ecr.com,99000\n'
        rapport = importer_limites_csv(
            self.company, csv, 'l.csv', user=self.user, ecraser=True)

        self.limite_c1.refresh_from_db()
        self.assertEqual(self.limite_c1.montant_limite, Decimal('99000'))
        self.assertEqual(rapport['maj'], 1)
        self.assertEqual(len(rapport['ecrasements']), 1)
        ecr = rapport['ecrasements'][0]
        self.assertEqual(ecr['champ'], 'montant_limite')
        self.assertEqual(ecr['ancienne'], '50000.00')
        self.assertEqual(ecr['nouvelle'], '99000.00')

        job = ImportJob.objects.get(pk=rapport['job_id'])
        self.assertEqual(job.company_id, self.company.id)
        row = ImportJobRow.objects.get(job=job, cible_id=self.limite_c1.pk)
        self.assertEqual(row.modifications, [{
            'champ': 'montant_limite', 'ancienne': '50000.00',
            'nouvelle': '99000.00', 'ecrasement': True,
        }])

        ct = ContentType.objects.get_for_model(LimiteCredit)
        audit = AuditLog.objects.filter(
            company=self.company, content_type=ct,
            object_id=str(self.limite_c1.pk)).first()
        self.assertIsNotNone(audit)
        self.assertIn('50000', audit.detail)
        self.assertIn('99000', audit.detail)

    # -- 4. Mise à jour légitime : remplir un champ VIDE ne demande rien ----

    def test_remplissage_champ_vide_fonctionne_sans_opt_in(self):
        """Une vraie mise à jour en masse — RENSEIGNER un champ jusque-là vide
        — reste possible sans ``ecraser`` : ce n'est jamais destructeur."""
        csv = b'client,montant_limite\nc2@imp-ecr.com,20000\n'
        rapport = importer_limites_csv(
            self.company, csv, 'l.csv', user=self.user)

        self.limite_c2.refresh_from_db()
        self.assertEqual(self.limite_c2.montant_limite, Decimal('20000'))
        self.assertEqual(rapport['maj'], 1)
        self.assertEqual(len(rapport['refuses']), 0)
        self.assertEqual(len(rapport['ecrasements']), 0)

    # -- 5. Cellule vide : ne vide jamais un champ déjà rempli --------------

    def test_cellule_vide_ne_vide_jamais_un_champ_rempli(self):
        """Une colonne ``montant_limite`` VIDE sur la ligne ne doit JAMAIS
        vider la valeur déjà saisie — même avec ``ecraser=True`` (la cellule
        vide n'entre jamais dans le diff)."""
        csv = b'client,montant_limite,mode_hold\nc1@imp-ecr.com,,avertissement\n'
        rapport = importer_limites_csv(
            self.company, csv, 'l.csv', user=self.user, ecraser=True)

        self.limite_c1.refresh_from_db()
        self.assertEqual(self.limite_c1.montant_limite, Decimal('50000'))
        # mode_hold, lui, était différent ('blocage' -> 'avertissement') et
        # FOURNI : celui-là s'applique bien avec ecraser=True.
        self.assertEqual(self.limite_c1.mode_hold, 'avertissement')
        self.assertEqual(len(rapport['ecrasements']), 1)
        self.assertEqual(rapport['ecrasements'][0]['champ'], 'mode_hold')

    def test_reimport_de_la_meme_valeur_n_est_jamais_un_ecrasement(self):
        """Rejouer le MÊME fichier ne doit rien signaler : « 50000 » écrit
        sans décimale revient de la base en « 50000.00 » — sans quantification
        à la précision du champ, le garde-fou verrait un faux écrasement et
        refuserait une ligne pourtant identique."""
        csv = b'client,montant_limite\nc1@imp-ecr.com,50000\n'
        rapport = importer_limites_csv(
            self.company, csv, 'l.csv', user=self.user)

        self.assertEqual(rapport['refuses'], [])
        self.assertEqual(rapport['ecrasements'], [])
        apercu = importer_limites_csv(
            self.company, csv, 'l.csv', user=self.user, apercu=True)
        self.assertEqual(apercu['conflits'], [])

    # -- 6. Isolation société : jamais de rapprochement inter-société -------

    def test_rapprochement_ne_traverse_jamais_les_societes(self):
        """Un email valide mais appartenant à un client d'une AUTRE société
        n'est jamais rapproché — la ligne part en erreur, la fiche de l'autre
        société n'est jamais touchée."""
        autre_co = make_company('imp-ecr-autre', 'Autre Co')
        autre_client = Client.objects.create(
            company=autre_co, nom='Externe', email='externe@imp-ecr.com')
        autre_limite = LimiteCredit.objects.create(
            company=autre_co, client=autre_client, montant_limite=Decimal('1000'))

        csv = b'client,montant_limite\nexterne@imp-ecr.com,50\n'
        rapport = importer_limites_csv(
            self.company, csv, 'l.csv', user=self.user, ecraser=True)

        self.assertEqual(rapport['crees'], 0)
        self.assertEqual(rapport['maj'], 0)
        self.assertEqual(len(rapport['erreurs']), 1)
        self.assertIn('introuvable', rapport['erreurs'][0]['motif'])

        autre_limite.refresh_from_db()
        self.assertEqual(autre_limite.montant_limite, Decimal('1000'))
