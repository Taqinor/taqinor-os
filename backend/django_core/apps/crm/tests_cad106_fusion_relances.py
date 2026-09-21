"""CAD106 — la fusion de deux fiches emmène enfin les relances avec elle.

`merge_leads` déplaçait devis, chantiers, activités, pièces jointes et
historique — et pas une seule relance. Les touches ouvertes restaient
accrochées à une fiche ARCHIVÉE, donc invisibles dans la file (qui exclut
`lead__is_archived`), jamais passées en « annulée », et rien ne reposait de
prochaine étape sur la survivante. Le cas est garanti d'arriver : le nouveau
lead venait justement d'être privé de cadence par la garde « doublon ».

Ce qu'on fait, et POURQUOI pas un simple déplacement : la survivante a
souvent DÉJÀ une cadence active, et CADX interdit deux cadences en parallèle.
Les touches ouvertes de l'absorbée sont donc CLOSES en ANNULÉE avec le motif
« fusion » — elles ne comptent alors comme un manquement nulle part (CKP1,
les annulations moteur sortent du dénominateur d'adhérence) — puis le FILET
garantit à la survivante une prochaine étape, exactement comme à la reprise
d'un lead dé-perdu.

L'APERÇU de fusion l'annonce désormais : on confirmait une fusion sans savoir
que des touches ouvertes allaient quitter leur plan.
"""
from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from authentication.models import Company

from apps.crm import services, stages
from apps.crm.models import Lead, LeadActivity, RelanceEtape
from apps.crm.services import merge_leads
from apps.parametres.models import CompanyProfile
from apps.parametres.models_relance import CadenceRelanceEtape

User = get_user_model()

MOBILE = '+212661000002'
DOUBLONS_URL = '/api/django/crm/leads/doublons/'


class _Base(TestCase):
    slug = 'cad106'

    def setUp(self):
        self.company = Company.objects.create(
            nom='CAD106 Solaire', slug=f'{self.slug}-a')
        CompanyProfile.objects.get_or_create(company=self.company)
        CadenceRelanceEtape.seed_defaults(self.company)
        self.acteur = User.objects.create_user(
            username=f'{self.slug}-resp', password='x',
            role_legacy='responsable', company=self.company)
        self.survivant = self._lead('Aziz')
        self.absorbe = self._lead('Aziz')

    def _lead(self, prenom, **kw):
        champs = {'company': self.company, 'nom': 'Benali', 'prenom': prenom,
                  'ville': 'Bouskoura', 'owner': self.acteur,
                  'telephone': MOBILE, 'stage': stages.NEW}
        champs.update(kw)
        return Lead.objects.create(**champs)

    def _touche(self, lead, ordre=1, statut=RelanceEtape.Statut.A_FAIRE):
        from core.dates import aujourd_hui_local
        jour = aujourd_hui_local()
        return RelanceEtape.objects.create(
            company=self.company, lead=lead, cadence='contact', ordre=ordre,
            due_date=jour, canal=RelanceEtape.Canal.WHATSAPP,
            libelle="Message d'identité", statut=statut)

    def _ouvertes(self, lead):
        return lead.relance_etapes.filter(
            statut=RelanceEtape.Statut.A_FAIRE)


class LesRelancesSuiventLeDossierTests(_Base):
    """Le « Done = » : zéro touche ouverte sur l'archivée, au moins une sur
    la survivante."""

    slug = 'cad106-suivent'

    def test_zero_touche_ouverte_sur_la_fiche_archivee(self):
        self._touche(self.absorbe, ordre=1)
        self._touche(self.absorbe, ordre=2)
        merge_leads(self.survivant, [self.absorbe], self.acteur)
        self.assertEqual(self._ouvertes(self.absorbe).count(), 0)

    def test_au_moins_une_etape_ouverte_sur_la_survivante(self):
        self._touche(self.absorbe)
        merge_leads(self.survivant, [self.absorbe], self.acteur)
        self.assertGreater(self._ouvertes(self.survivant).count(), 0)

    def test_les_touches_retirees_sont_ANNULEES_jamais_sautees(self):
        """CKP1 — une annulation MOTEUR n'est pas un saut humain : sans ça,
        la fusion compterait autant de manquements d'adhérence que de
        touches."""
        touche = self._touche(self.absorbe)
        merge_leads(self.survivant, [self.absorbe], self.acteur)
        touche.refresh_from_db()
        self.assertEqual(touche.statut, RelanceEtape.Statut.ANNULEE)
        self.assertIsNone(touche.traite_par)
        self.assertEqual(touche.note, services.FUSION_TOUCHE_NOTE)

    def test_la_fiche_archivee_ne_garde_aucune_echeance_fantome(self):
        self.absorbe.relance_date = self._touche(self.absorbe).due_date
        self.absorbe.save(update_fields=['relance_date'])
        merge_leads(self.survivant, [self.absorbe], self.acteur)
        self.absorbe.refresh_from_db()
        self.assertIsNone(self.absorbe.relance_date)

    def test_le_chatter_dit_combien_de_relances_ont_ete_reprises(self):
        self._touche(self.absorbe, ordre=1)
        self._touche(self.absorbe, ordre=2)
        merge_leads(self.survivant, [self.absorbe], self.acteur)
        notes = [n.body for n in LeadActivity.objects.filter(
            lead=self.survivant)]
        self.assertTrue(
            any('2 relance(s) reprise(s)' in (b or '') for b in notes),
            notes)


class CeQueLaFusionNeCassePasTests(_Base):
    """Les garde-fous."""

    slug = 'cad106-gardes'

    def test_les_touches_DEJA_closes_ne_sont_pas_retouchees(self):
        faite = self._touche(self.absorbe, statut=RelanceEtape.Statut.FAIT)
        merge_leads(self.survivant, [self.absorbe], self.acteur)
        faite.refresh_from_db()
        self.assertEqual(faite.statut, RelanceEtape.Statut.FAIT)
        self.assertNotEqual(faite.note, services.FUSION_TOUCHE_NOTE)

    def test_une_survivante_DEJA_suivie_ne_recoit_pas_de_seconde_cadence(self):
        """CADX — jamais deux cadences en parallèle. Le filet est un no-op
        quand une touche ouverte existe déjà."""
        deja = self._touche(self.survivant, ordre=5)
        self._touche(self.absorbe)
        merge_leads(self.survivant, [self.absorbe], self.acteur)
        ouvertes = list(self._ouvertes(self.survivant))
        self.assertEqual([e.pk for e in ouvertes], [deja.pk])

    def test_une_fusion_sans_aucune_relance_ne_dit_rien(self):
        merge_leads(self.survivant, [self.absorbe], self.acteur)
        notes = [n.body for n in LeadActivity.objects.filter(
            lead=self.survivant)]
        self.assertFalse(
            any('relance(s) reprise(s)' in (b or '') for b in notes), notes)

    def test_la_fusion_deplace_toujours_lhistorique(self):
        """Garde négative : on n'a rien cassé de ce que la fusion faisait
        déjà."""
        LeadActivity.objects.create(
            company=self.company, lead=self.absorbe, user=None,
            kind=LeadActivity.Kind.NOTE, body='Note historique.')
        merge_leads(self.survivant, [self.absorbe], self.acteur)
        self.assertTrue(LeadActivity.objects.filter(
            lead=self.survivant, body='Note historique.').exists())
        self.absorbe.refresh_from_db()
        self.assertTrue(self.absorbe.is_archived)


class LApercuAnnonceLeNombreTests(_Base):
    """« L'aperçu annonce le nombre. »"""

    slug = 'cad106-apercu'

    def _api(self):
        api = APIClient()
        api.credentials(
            HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(self.acteur)}')
        return api

    def test_lapercu_de_fusion_porte_le_compte_des_relances(self):
        self._touche(self.survivant, ordre=1)
        self._touche(self.absorbe, ordre=1)
        self._touche(self.absorbe, ordre=2)
        resp = self._api().get(DOUBLONS_URL)
        self.assertEqual(resp.status_code, 200, resp.data)
        self.assertTrue(resp.data)
        apercus = [grappe['merge_preview'] for grappe in resp.data]
        self.assertTrue(all('relances' in a for a in apercus), apercus)
        self.assertTrue(any(a['relances'] > 0 for a in apercus), apercus)

    def test_le_compte_vient_de_la_MEME_definition_que_la_fusion(self):
        """Jamais deux filtres qui dérivent : l'aperçu et la fusion comptent
        `relances_ouvertes_de`."""
        self._touche(self.absorbe, ordre=1)
        self._touche(self.absorbe, statut=RelanceEtape.Statut.FAIT, ordre=2)
        self.assertEqual(
            services.relances_ouvertes_de(self.absorbe).count(), 1)
