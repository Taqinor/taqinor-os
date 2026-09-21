"""Tests ARC22 — régression DC34 : ``gestion_projet.SousTraitant`` re-pointé
sur le master unifié (``stock.Fournisseur`` type=service).

Constat : le carnet ``gestion_projet.SousTraitant`` (PROJ38) est un 3e
référentiel sous-traitant parallèle à ``stock.Fournisseur`` +
``SousTraitantProfile`` (DC34) — une régression vis-à-vis de l'intention
d'unification DC34. ARC22 reste ADDITIF :

* FK nullable ``fournisseur`` (string-FK ``'stock.Fournisseur'``) ;
* chemin de création ``services.creer_sous_traitant_via_master`` qui passe
  PAR les services ``stock`` (jamais d'import de ``apps.stock.models``) ;
* backfill idempotent (``backfill_sous_traitant_fournisseur``) qui rattache
  les lignes EXISTANTES par correspondance nom/téléphone, sans fusionner ni
  geler les colonnes dupliquées (hors scope ARC22, propriété de DC34).

Couvre : création via le master pose le lien + crée le Fournisseur/profil
correspondant ; le backfill apparie nom+téléphone puis nom seul, saute les
lignes déjà liées, laisse intactes les lignes non-appariées ; idempotence
(deux exécutions ne changent rien à la deuxième) ; isolation multi-société.

Run :
    docker compose exec django_core python manage.py test apps.gestion_projet.tests.test_arc22_soustraitant_master -v 2
"""
from io import StringIO

from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.test import TestCase

from authentication.models import Company

from apps.gestion_projet import services
from apps.gestion_projet.models import SousTraitant
from apps.stock.models import Fournisseur, SousTraitantProfile

User = get_user_model()


def make_company(slug, nom):
    company, _ = Company.objects.get_or_create(slug=slug, defaults={'nom': nom})
    return company


def make_user(company, username, role='admin'):
    return User.objects.create_user(
        username=username, password='x', company=company, role_legacy=role)


class Arc22CreationViaMasterTests(TestCase):
    def setUp(self):
        self.company = make_company('arc22', 'ARC22 Co')
        self.user = make_user(self.company, 'arc22-admin')

    def test_creation_via_master_pose_le_lien_fournisseur(self):
        st = services.creer_sous_traitant_via_master(
            company=self.company, user=self.user, nom='Terrassement Atlas',
            specialite='terrassement', telephone='0600000001',
            email='atlas@example.invalid')
        self.assertIsNotNone(st.fournisseur_id)
        fournisseur = Fournisseur.objects.get(pk=st.fournisseur_id)
        self.assertEqual(fournisseur.type, Fournisseur.Type.SERVICE)
        self.assertEqual(fournisseur.nom, 'Terrassement Atlas')
        profil = SousTraitantProfile.objects.get(fournisseur=fournisseur)
        self.assertEqual(profil.metier, SousTraitantProfile.Metier.TERRASSEMENT)

    def test_creation_via_master_specialite_inconnue_replie_sur_autre(self):
        st = services.creer_sous_traitant_via_master(
            company=self.company, user=self.user, nom='Menuiserie Fes',
            specialite='menuiserie fine')
        profil = SousTraitantProfile.objects.get(fournisseur_id=st.fournisseur_id)
        self.assertEqual(profil.metier, SousTraitantProfile.Metier.AUTRE)

    def test_ancien_chemin_de_creation_directe_reste_sans_lien(self):
        """Compat ascendante : créer un SousTraitant SANS passer par le
        master (ancien chemin, ex. via le viewset) laisse fournisseur=NULL."""
        st = SousTraitant.objects.create(
            company=self.company, nom='Direct SARL')
        self.assertIsNone(st.fournisseur_id)


class Arc22BackfillTests(TestCase):
    def setUp(self):
        self.company = make_company('arc22-bf', 'ARC22 BF Co')
        self.autre_co = make_company('arc22-bf2', 'ARC22 BF Co 2')
        self.user = make_user(self.company, 'arc22-bf-admin')

    def _fournisseur(self, company, nom, telephone=''):
        return Fournisseur.objects.create(
            company=company, nom=nom, type=Fournisseur.Type.SERVICE,
            telephone=telephone or None)

    def test_backfill_apparie_par_nom_et_telephone(self):
        self._fournisseur(self.company, 'Electricite Nord', '0611111111')
        st = SousTraitant.objects.create(
            company=self.company, nom='Electricite Nord',
            telephone='0611111111')

        out = StringIO()
        call_command('backfill_sous_traitant_fournisseur', stdout=out)

        st.refresh_from_db()
        self.assertIsNotNone(st.fournisseur_id)
        self.assertIn('1 apparié', out.getvalue())

    def test_backfill_apparie_par_nom_seul_si_telephone_absent(self):
        self._fournisseur(self.company, 'Levage Pro')
        st = SousTraitant.objects.create(
            company=self.company, nom='Levage Pro')

        call_command('backfill_sous_traitant_fournisseur')

        st.refresh_from_db()
        self.assertIsNotNone(st.fournisseur_id)

    def test_backfill_ne_touche_pas_les_lignes_deja_liees(self):
        f1 = self._fournisseur(self.company, 'Transport Rapide')
        f2 = self._fournisseur(self.company, 'Transport Rapide')
        st = SousTraitant.objects.create(
            company=self.company, nom='Transport Rapide', fournisseur=f1)

        call_command('backfill_sous_traitant_fournisseur')

        st.refresh_from_db()
        # Le lien pré-existant n'est jamais réécrit, même s'il y a un f2
        # candidat plus "récent" — idempotence stricte.
        self.assertEqual(st.fournisseur_id, f1.pk)
        self.assertNotEqual(st.fournisseur_id, f2.pk)

    def test_backfill_laisse_intactes_les_lignes_non_appariees(self):
        st = SousTraitant.objects.create(
            company=self.company, nom='Introuvable SARL')

        out = StringIO()
        call_command('backfill_sous_traitant_fournisseur', stdout=out)

        st.refresh_from_db()
        self.assertIsNone(st.fournisseur_id)
        self.assertIn('1 non-apparié', out.getvalue())
        self.assertIn('Introuvable SARL', out.getvalue())

    def test_backfill_idempotent_deuxieme_run_ne_change_rien(self):
        self._fournisseur(self.company, 'Genie Civil Sud', '0622222222')
        st = SousTraitant.objects.create(
            company=self.company, nom='Genie Civil Sud',
            telephone='0622222222')

        call_command('backfill_sous_traitant_fournisseur')
        st.refresh_from_db()
        fournisseur_id_apres_1 = st.fournisseur_id
        self.assertIsNotNone(fournisseur_id_apres_1)

        out2 = StringIO()
        call_command('backfill_sous_traitant_fournisseur', stdout=out2)
        st.refresh_from_db()
        self.assertEqual(st.fournisseur_id, fournisseur_id_apres_1)
        # Deuxième run : plus rien à apparier pour cette société (déjà lié).
        self.assertIn('0 apparié', out2.getvalue())

    def test_backfill_isolation_multi_societe(self):
        """Un Fournisseur de l'AUTRE société ne peut jamais apparier un
        SousTraitant de cette société-ci (scoping strict)."""
        self._fournisseur(self.autre_co, 'Nom Partage', '0699999999')
        st = SousTraitant.objects.create(
            company=self.company, nom='Nom Partage', telephone='0699999999')

        call_command('backfill_sous_traitant_fournisseur')

        st.refresh_from_db()
        self.assertIsNone(st.fournisseur_id)

    def test_backfill_dry_run_ne_persiste_rien(self):
        self._fournisseur(self.company, 'Dry Run Sarl', '0633333333')
        st = SousTraitant.objects.create(
            company=self.company, nom='Dry Run Sarl', telephone='0633333333')

        out = StringIO()
        call_command(
            'backfill_sous_traitant_fournisseur', '--dry-run', stdout=out)

        st.refresh_from_db()
        self.assertIsNone(st.fournisseur_id)
        self.assertIn('DRY-RUN', out.getvalue())
        self.assertIn('1 apparié', out.getvalue())

    def test_backfill_scope_par_company_slug(self):
        self._fournisseur(self.company, 'Scoped Sarl', '0644444444')
        st_scoped = SousTraitant.objects.create(
            company=self.company, nom='Scoped Sarl', telephone='0644444444')
        self._fournisseur(self.autre_co, 'Autre Sarl', '0655555555')
        st_autre = SousTraitant.objects.create(
            company=self.autre_co, nom='Autre Sarl', telephone='0655555555')

        call_command(
            'backfill_sous_traitant_fournisseur', '--company', self.company.slug)

        st_scoped.refresh_from_db()
        st_autre.refresh_from_db()
        self.assertIsNotNone(st_scoped.fournisseur_id)
        self.assertIsNone(st_autre.fournisseur_id)
