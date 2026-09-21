"""CAD128 — un ancien client SIGNÉ qui redemande un devis n'est plus refusé.

Constat de l'audit L3 du 21/09/2026 : la garde doublon retient tout lead
partageant le téléphone ou l'e-mail et n'écarte que les archivés et les
perdus — une fiche SIGNÉE est donc un « doublon vivant », et le meilleur lead
du portefeuille (il a déjà acheté) repart sans protocole, avec une simple
ligne « doublon possible de #… ».

Version RÉDUITE du round 2, verrouillée ici : SIGNED sort de la garde
**uniquement couplé** à une cadence courte « deuxième affaire » — jamais le
protocole contact, six appels sur quatorze jours sur un client acquis.

Garde-fou : les deux fiches sont LIÉES par une note d'historique, JAMAIS
fusionnées d'office.
"""
import datetime

from django.contrib.auth import get_user_model
from django.test import SimpleTestCase, TestCase

from authentication.models import Company

from apps.crm import horaires, stages
from apps.crm.models import Lead, LeadActivity, RelanceEtape
from apps.crm.services import (
    CADENCE_DEUXIEME_AFFAIRE, demarrer_cadence_contact, homonymes_signes,
)
from apps.parametres.models import CompanyProfile
from apps.parametres.models_messages import MESSAGE_TEMPLATE_DEFAULTS
from apps.parametres.models_relance import (
    CADENCE_CONTACT_DEFAUT, CADENCE_DEUXIEME_AFFAIRE_DEFAUT, Cadence,
)

User = get_user_model()

#: Lundi 21 septembre 2026, 10 h à Casablanca.
MAINTENANT = datetime.datetime(2026, 9, 21, 10, 0, tzinfo=horaires.CASABLANCA)

TELEPHONE = '+212661112233'


class LaCadenceCourteTests(SimpleTestCase):
    """Ce que le gabarit PROMET — lisible sans base."""

    def test_elle_est_COURTE(self):
        self.assertEqual(len(CADENCE_DEUXIEME_AFFAIRE_DEFAUT), 2)
        self.assertLess(len(CADENCE_DEUXIEME_AFFAIRE_DEFAUT),
                        len(CADENCE_CONTACT_DEFAUT))

    def test_ses_deux_barreaux_ne_sont_pas_INVENTES(self):
        """Ce sont les deux premiers du protocole validé, arrêtés là — seule
        la clé de message du premier change."""
        for rang, barreau in enumerate(CADENCE_DEUXIEME_AFFAIRE_DEFAUT):
            source = CADENCE_CONTACT_DEFAUT[rang]
            with self.subTest(rang=rang):
                self.assertEqual(barreau['delai_jours'],
                                 source['delai_jours'])
                self.assertEqual(barreau['delai_minutes'],
                                 source['delai_minutes'])
                self.assertEqual(barreau['canal'], source['canal'])

    def test_le_premier_barreau_porte_le_texte_du_client_acquis(self):
        self.assertEqual(CADENCE_DEUXIEME_AFFAIRE_DEFAUT[0]['template_cle'],
                         'deuxieme_affaire')
        self.assertIn('deuxieme_affaire', MESSAGE_TEMPLATE_DEFAULTS)

    def test_le_protocole_contact_n_est_PAS_modifie(self):
        """Le nombre, l'ordre et les J+N des touches ne changent pas."""
        self.assertEqual(len(CADENCE_CONTACT_DEFAUT), 11)
        self.assertEqual(CADENCE_CONTACT_DEFAUT[0]['template_cle'],
                         'identite')

    def test_le_texte_ne_cite_AUCUN_mois_ni_chiffre(self):
        """Rien ne relie encore les deux fiches en base : plutôt qu'une date
        approximative, le mois est OMIS."""
        texte = MESSAGE_TEMPLATE_DEFAULTS['deuxieme_affaire']
        self.assertEqual([c for c in texte if c.isdigit()], [])
        self.assertNotIn('{mois', texte)

    def test_la_cadence_est_une_valeur_declaree(self):
        self.assertEqual(Cadence.DEUXIEME_AFFAIRE, CADENCE_DEUXIEME_AFFAIRE)


class _Base(TestCase):
    slug = 'cad128'

    def setUp(self):
        from testkit.time import frozen

        gel = frozen(MAINTENANT)
        gel.start()
        self.addCleanup(gel.stop)
        self.company = Company.objects.create(slug=self.slug, nom=self.slug)
        CompanyProfile.objects.create(company=self.company)
        self.acteur = User.objects.create_user(
            username=f'{self.slug}-u', password='x',
            role_legacy='responsable', company=self.company)

    def _lead(self, nom, *, stage=stages.NEW, telephone=TELEPHONE,
              perdu=False, archive=False):
        return Lead.objects.create(
            company=self.company, nom=nom, prenom='Aziz', owner=self.acteur,
            stage=stage, telephone=telephone, perdu=perdu,
            is_archived=archive, canal='telephone')

    def _cadences(self, lead):
        return set(lead.relance_etapes.values_list('cadence', flat=True))


class LeClientQuiRevientTests(_Base):
    slug = 'cad128-retour'

    def test_le_seul_homonyme_SIGNED_demarre_la_cadence_COURTE(self):
        """LE Done."""
        self._lead('Benali', stage=stages.SIGNED)
        nouveau = self._lead('Benali')

        touches = demarrer_cadence_contact(nouveau, user=self.acteur)

        self.assertTrue(touches)
        self.assertEqual(self._cadences(nouveau), {CADENCE_DEUXIEME_AFFAIRE})
        self.assertNotIn('contact', self._cadences(nouveau))

    def test_la_premiere_touche_porte_le_texte_du_client_acquis(self):
        self._lead('Benali', stage=stages.SIGNED)
        nouveau = self._lead('Benali')
        demarrer_cadence_contact(nouveau, user=self.acteur)
        premiere = nouveau.relance_etapes.order_by('ordre').first()
        self.assertEqual(premiere.template_cle, 'deuxieme_affaire')

    def test_les_deux_fiches_sont_LIEES_jamais_fusionnees(self):
        ancien = self._lead('Benali', stage=stages.SIGNED)
        nouveau = self._lead('Benali')

        demarrer_cadence_contact(nouveau, user=self.acteur)

        notes_nouveau = list(LeadActivity.objects.filter(
            lead=nouveau).values_list('body', flat=True))
        notes_ancien = list(LeadActivity.objects.filter(
            lead=ancien).values_list('body', flat=True))
        self.assertTrue(
            any(f'#{ancien.pk}' in n for n in notes_nouveau), notes_nouveau)
        self.assertTrue(
            any(f'#{nouveau.pk}' in n for n in notes_ancien), notes_ancien)
        # Aucune fusion : les deux fiches existent toujours, distinctes.
        ancien.refresh_from_db()
        nouveau.refresh_from_db()
        self.assertFalse(ancien.is_archived)
        self.assertEqual(ancien.stage, stages.SIGNED)

    def test_le_selecteur_d_homonymes_ne_retient_que_les_SIGNES(self):
        self._lead('Benali', stage=stages.SIGNED)
        self._lead('Autre', stage=stages.CONTACTED, telephone='+212600000001')
        nouveau = self._lead('Benali')
        signes = homonymes_signes(nouveau)
        self.assertEqual(len(signes), 1)
        self.assertEqual(signes[0].stage, stages.SIGNED)


class LesAutresDoublonsRestentRefusesTests(_Base):
    slug = 'cad128-doublon'

    def test_un_homonyme_VIVANT_non_signe_refuse_toujours_la_cadence(self):
        """Anti-régression : la garde doublon n'est pas désactivée."""
        self._lead('Benali', stage=stages.CONTACTED)
        nouveau = self._lead('Benali')

        touches = demarrer_cadence_contact(nouveau, user=self.acteur)

        self.assertEqual(touches, [])
        self.assertEqual(self._cadences(nouveau), set())
        self.assertTrue(LeadActivity.objects.filter(
            lead=nouveau, body__icontains='doublon possible').exists())

    def test_un_melange_signe_et_vivant_reste_un_DOUBLON(self):
        """La sortie de garde exige que TOUS les homonymes soient signés."""
        self._lead('Benali', stage=stages.SIGNED)
        self._lead('Benali2', stage=stages.QUOTE_SENT)
        nouveau = self._lead('Benali')

        self.assertEqual(
            demarrer_cadence_contact(nouveau, user=self.acteur), [])
        self.assertEqual(self._cadences(nouveau), set())

    def test_sans_aucun_homonyme_le_protocole_CONTACT_part_normalement(self):
        """Anti-faux-vert : le cas majoritaire n'est pas détourné."""
        nouveau = self._lead('Seul', telephone='+212600000009')
        touches = demarrer_cadence_contact(nouveau, user=self.acteur)
        self.assertTrue(touches)
        self.assertEqual(self._cadences(nouveau), {'contact'})

    def test_un_homonyme_signe_mais_ARCHIVE_ne_compte_pas(self):
        self._lead('Benali', stage=stages.SIGNED, archive=True)
        nouveau = self._lead('Benali')
        demarrer_cadence_contact(nouveau, user=self.acteur)
        self.assertEqual(self._cadences(nouveau), {'contact'})

    def test_une_societe_ne_voit_pas_les_signes_d_une_autre(self):
        voisine = Company.objects.create(
            slug=f'{self.slug}-voisine', nom='voisine')
        CompanyProfile.objects.create(company=voisine)
        Lead.objects.create(
            company=voisine, nom='Benali', stage=stages.SIGNED,
            telephone=TELEPHONE)
        nouveau = self._lead('Benali')
        demarrer_cadence_contact(nouveau, user=self.acteur)
        self.assertEqual(self._cadences(nouveau), {'contact'})


class AucunProtocoleSurUnClientAcquisTests(_Base):
    slug = 'cad128-court'

    def test_la_cadence_courte_ne_pose_JAMAIS_six_appels(self):
        self._lead('Benali', stage=stages.SIGNED)
        nouveau = self._lead('Benali')
        demarrer_cadence_contact(nouveau, user=self.acteur)
        appels = nouveau.relance_etapes.filter(
            canal=RelanceEtape.Canal.APPEL).count()
        self.assertLessEqual(appels, 1)
