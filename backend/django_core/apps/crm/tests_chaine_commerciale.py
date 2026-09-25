"""Chaîne commerciale — les trois compteurs du cockpit.

Décision fondateur du 25/09/2026 (« regarde aussi le cockpit, que tout soit
bien fait maintenant que la cadence est bien faite ») : la chaîne appel →
visite → devis a trois états intermédiaires que le cockpit ne montrait nulle
part. ``GET crm/relance-etapes/chaine-commerciale/`` — contrat
``contract_samples/chaine_commerciale.json``, source ``selectors.
chaine_commerciale``.

Chaque définition et chaque exclusion est prouvée (perdu, archivé, « ne plus
contacter », signé, froid, devis envoyé, visite passée ou faite, issue
système, dernière issue qui n'est plus « joint »), ainsi que le tri, la
limite avec son total exact, la portée par responsable et le masquage des
téléphones.

Horloge FIXE : mercredi 23/09/2026, 10 h à Casablanca.
"""
import datetime
import json
from decimal import Decimal
from pathlib import Path

from django.contrib.auth import get_user_model
from django.db import connection
from django.test import TestCase
from django.test.utils import CaptureQueriesContext
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from authentication.models import Company
from testkit.time import frozen

from apps.crm import horaires, services, stages
from apps.crm.models import Client, Lead, LeadActivity, RelanceEtape
from apps.crm.selectors import chaine_commerciale
from apps.parametres.models import CompanyProfile
from apps.roles.models import COMMERCIAL_PERMISSIONS, Role
from apps.visites.models import VisiteTerrain

User = get_user_model()

GEL = datetime.datetime(2026, 9, 23, 10, 0, tzinfo=horaires.CASABLANCA)
AUJOURDHUI = GEL.date()
HIER = AUJOURDHUI - datetime.timedelta(days=1)
DEMAIN = AUJOURDHUI + datetime.timedelta(days=1)
URL = '/api/django/crm/relance-etapes/chaine-commerciale/'
CONTRAT = json.loads(
    (Path(__file__).resolve().parent / 'contract_samples'
     / 'chaine_commerciale.json').read_text(encoding='utf-8'))


class _Base(TestCase):
    slug = 'chaine'

    def setUp(self):
        gel = frozen(GEL)
        gel.start()
        self.addCleanup(gel.stop)
        self.company = Company.objects.create(
            nom=f'{self.slug} Solaire', slug=self.slug)
        CompanyProfile.objects.get_or_create(company=self.company)
        self.role = Role.objects.create(
            company=self.company, nom='Commercial',
            permissions=COMMERCIAL_PERMISSIONS, est_systeme=True)
        self.meryem = User.objects.create_user(
            username=f'{self.slug}-meryem', password='x',
            company=self.company, role=self.role)
        self.autre = User.objects.create_user(
            username=f'{self.slug}-autre', password='x',
            company=self.company, role=self.role)
        self.n = 0

    def _api(self, user=None):
        api = APIClient()
        api.credentials(HTTP_AUTHORIZATION=(
            f'Bearer {AccessToken.for_user(user or self.meryem)}'))
        return api

    def _lead(self, nom, *, owner=None, stage=stages.CONTACTED, **champs):
        self.n += 1
        return Lead.objects.create(
            company=self.company, nom=nom, prenom='P',
            owner=owner or self.meryem, stage=stage,
            telephone=f'+2126610{self.n:05d}', **champs)

    def _issue(self, lead, outcome, *, le=GEL, humain=True):
        """Une issue saisie SANS les récepteurs (``bulk_create``) : le test
        pose lui-même l'état des étapes qu'il veut observer."""
        [activite] = LeadActivity.objects.bulk_create([LeadActivity(
            company=self.company, lead=lead,
            user=self.meryem if humain else None,
            kind=LeadActivity.Kind.APPEL, outcome=outcome, body='appel')])
        LeadActivity.objects.filter(pk=activite.pk).update(created_at=le)
        return activite

    def _etape(self, lead, *, jour, libelle='Appel', cle='', cadence=None,
               statut=RelanceEtape.Statut.A_FAIRE):
        due = datetime.datetime.combine(jour, datetime.time(9, 0),
                                        tzinfo=horaires.CASABLANCA)
        return RelanceEtape.objects.create(
            company=self.company, lead=lead,
            cadence=cadence or 'generique', ordre=1,
            canal=RelanceEtape.Canal.APPEL, libelle=libelle, cle=cle,
            due_at=due, due_date=jour, statut=statut)

    def _devis(self, lead, statut):
        from apps.ventes.models import Devis

        self.n += 1
        client = Client.objects.create(
            company=self.company, nom=lead.nom,
            email=f'{self.slug}-{self.n}@example.com')
        return Devis.objects.create(
            company=self.company, reference=f'DEV-{self.slug}-{self.n}',
            client=client, lead=lead, statut=statut,
            taux_tva=Decimal('20.00'))

    def _chaine(self, user=None):
        resp = self._api(user).get(URL)
        self.assertEqual(resp.status_code, 200, resp.data)
        return resp.data

    @staticmethod
    def _ids(bloc):
        return [ligne['id'] for ligne in bloc['leads']]


class FormeTests(_Base):
    slug = 'chaine-forme'

    def test_vide_a_la_forme_du_contrat(self):
        self.assertEqual(self._chaine(), CONTRAT['exemple_vide'])

    def test_les_cles_des_lignes_sont_celles_du_contrat(self):
        from apps.ventes.models import Devis

        joint = self._lead('Joint')
        self._issue(joint, 'joint')
        self._etape(joint, jour=AUJOURDHUI, libelle=services.FILET_JOINT_LIBELLE,
                    cle='devis')
        visite = self._lead('Visite',
                            visite_prevue_le=AUJOURDHUI
                            + datetime.timedelta(days=3))
        self._devis(visite, Devis.Statut.ENVOYE)

        donnees = self._chaine()

        exemple = CONTRAT['exemple']
        self.assertEqual(set(donnees), set(exemple))
        for bloc in ('joints_sans_devis', 'visites_a_venir',
                     'devis_a_preparer'):
            with self.subTest(bloc=bloc):
                self.assertEqual(set(donnees[bloc]), {'total', 'leads'})
                self.assertEqual(set(donnees[bloc]['leads'][0]),
                                 set(exemple[bloc]['leads'][0]))
        self.assertEqual(donnees['limite'], 5)


class JointsSansDevisTests(_Base):
    slug = 'chaine-joints'

    def test_definitions_exclusions_et_tri(self):
        from apps.ventes.models import Devis

        # Inclus : joint (un devis BROUILLON ne compte pas), prochaine étape
        # aujourd'hui.
        a_jour = self._lead('AJour')
        self._issue(a_jour, 'joint', le=GEL - datetime.timedelta(days=1))
        self._devis(a_jour, Devis.Statut.BROUILLON)
        self._etape(a_jour, jour=AUJOURDHUI,
                    libelle=services.FILET_JOINT_LIBELLE, cle='devis')
        # Inclus : visite acceptée, prochaine étape EN RETARD.
        en_retard = self._lead('Retard')
        self._issue(en_retard, services.OUTCOME_VISITE_ACCEPTEE)
        self._etape(en_retard, jour=HIER, libelle='Planifier la visite',
                    cle='planifier', cadence='apres_devis')
        # Inclus : intéressé, AUCUNE prochaine étape — un trou, en tête.
        trou = self._lead('Trou')
        self._issue(trou, 'interesse')
        # Exclus.
        exclus = []
        envoye = self._lead('Envoye')
        self._devis(envoye, Devis.Statut.ENVOYE)
        exclus.append(envoye)
        exclus.append(self._lead('Perdu', perdu=True))
        exclus.append(self._lead('Archive', is_archived=True))
        exclus.append(self._lead('Npc', ne_plus_contacter=True))
        exclus.append(self._lead('Signe', stage=stages.SIGNED))
        exclus.append(self._lead('Froid', stage=stages.COLD))
        exclus.append(self._lead('Autre', owner=self.autre))
        for lead in exclus:
            self._issue(lead, 'joint')
        plus_joint = self._lead('PlusJoint')
        self._issue(plus_joint, 'joint', le=GEL - datetime.timedelta(days=2))
        self._issue(plus_joint, 'non_joint')
        systeme = self._lead('Systeme')
        self._issue(systeme, 'joint', humain=False)

        bloc = self._chaine()['joints_sans_devis']

        self.assertEqual(bloc['total'], 3)
        self.assertEqual(self._ids(bloc), [trou.pk, en_retard.pk, a_jour.pk])
        lignes = {ligne['id']: ligne for ligne in bloc['leads']}
        self.assertIsNone(lignes[trou.pk]['prochaine_etape'])
        self.assertIsNone(lignes[trou.pk]['prochaine_le'])
        self.assertFalse(lignes[trou.pk]['en_retard'])
        self.assertEqual(lignes[en_retard.pk]['prochaine_le'], HIER.isoformat())
        self.assertTrue(lignes[en_retard.pk]['en_retard'])
        self.assertEqual(lignes[a_jour.pk]['prochaine_etape'],
                         services.FILET_JOINT_LIBELLE)
        self.assertEqual(lignes[a_jour.pk]['joint_le'], HIER.isoformat())
        self.assertEqual(lignes[en_retard.pk]['joint_le'],
                         AUJOURDHUI.isoformat())
        self.assertEqual(lignes[a_jour.pk]['telephone'], a_jour.telephone)


class VisitesAVenirTests(_Base):
    slug = 'chaine-visites'

    def test_definitions_exclusions_et_tri(self):
        from apps.ventes.models import Devis

        karim = User.objects.create_user(
            username=f'{self.slug}-karim', password='x',
            company=self.company, first_name='Karim', last_name='Alami')
        loin = self._lead('Loin', visite_prevue_le=AUJOURDHUI
                          + datetime.timedelta(days=6))
        VisiteTerrain.objects.create(
            company=self.company, lead=loin, commercial=karim,
            date_prevue=loin.visite_prevue_le)
        proche = self._lead('Proche', visite_prevue_le=DEMAIN)
        self._devis(proche, Devis.Statut.ENVOYE)
        self._lead('Passee', visite_prevue_le=HIER)
        self._lead('Faite', visite_prevue_le=DEMAIN, visite_effectuee=True)
        self._lead('Perdue', visite_prevue_le=DEMAIN, perdu=True)
        self._lead('AutreVisite', owner=self.autre, visite_prevue_le=DEMAIN)

        bloc = self._chaine()['visites_a_venir']

        self.assertEqual(bloc['total'], 2)
        self.assertEqual(self._ids(bloc), [proche.pk, loin.pk])
        lignes = {ligne['id']: ligne for ligne in bloc['leads']}
        self.assertFalse(lignes[proche.pk]['sans_devis'])
        self.assertTrue(lignes[loin.pk]['sans_devis'])
        self.assertEqual(lignes[loin.pk]['assignee'], 'Karim Alami')
        self.assertEqual(lignes[loin.pk]['visite_prevue_le'],
                         loin.visite_prevue_le.isoformat())
        self.assertEqual(lignes[proche.pk]['assignee'], '')


class DevisAPreparerTests(_Base):
    slug = 'chaine-devis'

    def test_definitions_exclusions_et_tri(self):
        retard = self._lead('Retard', visite_effectuee=True)
        self._etape(retard, jour=HIER, libelle=services.FILET_JOINT_LIBELLE,
                    cle='devis')
        ancienne = self._lead('Ancienne')
        self._etape(ancienne, jour=DEMAIN,
                    libelle=services._FILET_JOINT_LIBELLE_ANCIEN)
        renommee = self._lead('Renommee')
        self._etape(renommee, jour=AUJOURDHUI, libelle='Faire le devis',
                    cle='devis')
        # Exclus : étape faite, autre étape, lead d'un autre, lead archivé,
        # libellé renommé SANS clé (jamais reconnu).
        faite = self._lead('Faite')
        self._etape(faite, jour=HIER, libelle=services.FILET_JOINT_LIBELLE,
                    cle='devis', statut=RelanceEtape.Statut.FAIT)
        self._etape(self._lead('Autre etape'), jour=HIER,
                    libelle=services.FILET_REFUS_LIBELLE, cle='decider_suite')
        self._etape(self._lead('Autre', owner=self.autre), jour=HIER,
                    libelle=services.FILET_JOINT_LIBELLE, cle='devis')
        self._etape(self._lead('Archive', is_archived=True), jour=HIER,
                    libelle=services.FILET_JOINT_LIBELLE, cle='devis')
        self._etape(self._lead('SansCle'), jour=HIER,
                    libelle='Faire le devis')

        bloc = self._chaine()['devis_a_preparer']

        self.assertEqual(bloc['total'], 3)
        self.assertEqual(self._ids(bloc),
                         [retard.pk, renommee.pk, ancienne.pk])
        lignes = {ligne['id']: ligne for ligne in bloc['leads']}
        self.assertTrue(lignes[retard.pk]['en_retard'])
        self.assertTrue(lignes[retard.pk]['apres_visite'])
        self.assertFalse(lignes[ancienne.pk]['en_retard'])
        self.assertFalse(lignes[ancienne.pk]['apres_visite'])
        self.assertEqual(lignes[ancienne.pk]['prochaine_le'],
                         DEMAIN.isoformat())


class LimiteEtPorteeTests(_Base):
    slug = 'chaine-limite'

    def test_la_limite_garde_un_total_exact(self):
        for i in range(7):
            lead = self._lead(f'Devis {i}')
            self._etape(lead, jour=AUJOURDHUI + datetime.timedelta(days=i),
                        libelle=services.FILET_JOINT_LIBELLE, cle='devis')
        donnees = self._chaine()
        self.assertEqual(donnees['devis_a_preparer']['total'], 7)
        self.assertEqual(len(donnees['devis_a_preparer']['leads']), 5)
        self.assertEqual(donnees['limite'], 5)

        petit = chaine_commerciale(self.meryem, self.company, limite=2)
        self.assertEqual(petit['devis_a_preparer']['total'], 7)
        self.assertEqual(len(petit['devis_a_preparer']['leads']), 2)

    def test_chacun_sa_chaine(self):
        a_moi = self._lead('Moi')
        self._etape(a_moi, jour=AUJOURDHUI,
                    libelle=services.FILET_JOINT_LIBELLE, cle='devis')
        a_lui = self._lead('Lui', owner=self.autre)
        self._etape(a_lui, jour=AUJOURDHUI,
                    libelle=services.FILET_JOINT_LIBELLE, cle='devis')
        self.assertEqual(
            self._ids(self._chaine()['devis_a_preparer']), [a_moi.pk])
        self.assertEqual(
            self._ids(self._chaine(self.autre)['devis_a_preparer']),
            [a_lui.pk])

    def test_une_autre_societe_ne_fuit_jamais(self):
        autre = Company.objects.create(nom='Voisine', slug=f'{self.slug}-b')
        voisin = User.objects.create_user(
            username=f'{self.slug}-voisin', password='x', company=autre,
            role_legacy='responsable')
        lead = Lead.objects.create(company=autre, nom='Voisin',
                                   owner=voisin, stage=stages.CONTACTED)
        RelanceEtape.objects.create(
            company=autre, lead=lead, cadence='generique', ordre=1,
            canal=RelanceEtape.Canal.APPEL,
            libelle=services.FILET_JOINT_LIBELLE, cle='devis',
            due_at=GEL, due_date=AUJOURDHUI)
        self.assertEqual(self._chaine()['devis_a_preparer']['total'], 0)


class PiiMasqueeTests(_Base):
    slug = 'chaine-pii'

    def test_le_telephone_est_masque_sans_le_droit(self):
        role_sans_pii = Role.objects.create(
            company=self.company, nom='Commercial sans PII',
            permissions=[p for p in COMMERCIAL_PERMISSIONS
                         if p != 'client_pii_voir'])
        masque = User.objects.create_user(
            username=f'{self.slug}-masque', password='x',
            company=self.company, role=role_sans_pii)
        lead = self._lead('Masque', owner=masque)
        self._etape(lead, jour=AUJOURDHUI,
                    libelle=services.FILET_JOINT_LIBELLE, cle='devis')

        [ligne] = self._chaine(masque)['devis_a_preparer']['leads']

        self.assertEqual(ligne['telephone'], '')
        self.assertEqual(ligne['nom'], 'Masque')


class CoutTests(_Base):
    """Jamais une requête PAR LEAD : une par compteur, une pour les
    prochaines étapes, une par lot de devis (seul l'assigné des ``limite``
    visites servies est lu dossier par dossier)."""

    slug = 'chaine-cout'

    def _cout(self):
        api = self._api()
        with CaptureQueriesContext(connection) as ctx:
            api.get(URL)
        return len(ctx)

    def _dossiers(self, n, depart):
        for i in range(depart, depart + n):
            joint = self._lead(f'Joint {i}')
            self._issue(joint, 'joint')
            self._etape(joint, jour=AUJOURDHUI,
                        libelle=services.FILET_JOINT_LIBELLE, cle='devis')

    def test_le_cout_ne_grimpe_pas_avec_les_dossiers(self):
        self._dossiers(1, 0)
        un = self._cout()
        self._dossiers(6, 1)
        # Signature d'un N+1 : +1 requête PAR dossier (ici +6). Toléré : +1
        # constant (premier accès paresseux), jamais linéaire.
        self.assertLessEqual(self._cout() - un, 1)
