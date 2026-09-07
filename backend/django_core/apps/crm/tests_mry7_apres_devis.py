"""MRY7 — La cadence « après devis », et sa paix avec la relance vendeur QJ4.

Deux moteurs de relance existent désormais sur le même objet : celui de Meryem
(cadence MRY, 10 touches datées depuis l'envoi) et le nudge vendeur QJ4
(j+2/j+5/j+10, `DevisNudgeLog`). Laisser les deux tourner enverrait DEUX
messages au même client, le même jour, depuis deux systèmes qui s'ignorent.
QJ4 est donc SUPPRIMÉ — jamais supprimé « en général », seulement pour les
devis effectivement suivis par une cadence MRY ouverte ; les sociétés qui n'en
ont pas gardent QJ4 strictement inchangé.

Ce fichier verrouille aussi les trois nuances du basculement :
  * la prise de contact s'ARRÊTE à l'envoi (son but est atteint) ;
  * un même lead n'a qu'UNE cadence après-devis à la fois — deux devis envoyés
    ensemble ne donnent pas deux séries de messages parallèles ;
  * un devis REFUSÉ arrête sa cadence même quand le lead n'est PAS perdu.
"""
import datetime
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.utils import timezone

from authentication.models import Company
from core.events import devis_refused, devis_sent

from apps.crm import horaires
from apps.crm.models import Client, Lead, LeadActivity, RelanceEtape
from apps.crm.selectors import devis_a_cadence_active
from apps.crm.services import initialiser_plan_relance
from apps.parametres.models import CompanyProfile
from apps.ventes.models import Devis

User = get_user_model()

ENVOI = datetime.datetime(2026, 9, 7, 10, 0, tzinfo=horaires.CASABLANCA)


def _company(slug):
    company, _ = Company.objects.get_or_create(
        slug=slug, defaults={'nom': slug})
    CompanyProfile.objects.get_or_create(company=company)
    return company


class _Base(TestCase):
    slug = 'mry7'

    def setUp(self):
        self.company = _company(self.slug)
        self.acteur = User.objects.create_user(
            username=f'{self.slug}-u', password='x',
            role_legacy='responsable', company=self.company)
        self.lead = Lead.objects.create(
            company=self.company, nom='Prospect', owner=self.acteur,
            telephone='+212661112233')
        self.client_obj = Client.objects.create(
            company=self.company, nom='Client',
            email=f'{self.slug}@example.com')

    def _devis(self, reference, date_envoi=ENVOI):
        return Devis.objects.create(
            company=self.company, reference=reference, client=self.client_obj,
            lead=self.lead, statut='envoye', taux_tva=Decimal('20.00'),
            date_envoi=date_envoi)

    def _envoyer(self, devis):
        devis_sent.send(sender='test', devis=devis, user=self.acteur,
                        ancien_statut='brouillon')

    def _touches(self, cadence, **kw):
        return self.lead.relance_etapes.filter(cadence=cadence, **kw)


class BasculementTests(_Base):
    slug = 'mry7-bascule'

    def test_lenvoi_cree_la_cadence_apres_devis(self):
        devis = self._devis('DEV-MRY7-0001')
        self._envoyer(devis)
        touches = self._touches('apres_devis')
        self.assertGreater(touches.count(), 0)
        self.assertTrue(all(t.devis_id == devis.pk for t in touches))

    def test_les_touches_partent_de_la_DATE_DENVOI(self):
        """Dater depuis « maintenant » décalerait tout le suivi d'un devis
        envoyé la veille au soir."""
        devis = self._devis('DEV-MRY7-0002')
        self._envoyer(devis)
        premiere = self._touches('apres_devis').order_by('ordre').first()
        # Touche 1 = J+1 après l'envoi (lundi 07/09 → mardi 08/09).
        self.assertEqual(
            premiere.due_at.astimezone(horaires.CASABLANCA).date(),
            datetime.date(2026, 9, 8))

    def test_la_prise_de_contact_sarrete(self):
        initialiser_plan_relance(
            self.lead, self.acteur, depart=ENVOI, cadence='contact')
        self._envoyer(self._devis('DEV-MRY7-0003'))
        self.assertEqual(
            self._touches('contact',
                          statut=RelanceEtape.Statut.A_FAIRE).count(), 0)

    def test_second_envoi_du_MEME_devis_ne_cree_rien(self):
        devis = self._devis('DEV-MRY7-0004')
        self._envoyer(devis)
        attendu = self._touches('apres_devis').count()
        self._envoyer(devis)
        self.assertEqual(self._touches('apres_devis').count(), attendu)

    def test_deux_devis_du_meme_lead_ne_donnent_quUNE_cadence(self):
        """`whatsapp_devis` boucle sur la sélection : sans cette garde, le
        client recevrait deux séries de messages parallèles pour un dossier."""
        premier = self._devis('DEV-MRY7-0005')
        self._envoyer(premier)
        attendu = self._touches('apres_devis').count()
        second = self._devis('DEV-MRY7-0006')
        self._envoyer(second)
        self.assertEqual(self._touches('apres_devis').count(), attendu)
        self.assertTrue(any(
            'déjà en cours' in (n.body or '')
            for n in LeadActivity.objects.filter(lead=self.lead)))

    def test_un_devis_sans_lead_ne_casse_rien(self):
        orphelin = Devis.objects.create(
            company=self.company, reference='DEV-MRY7-0007',
            client=self.client_obj, statut='envoye',
            taux_tva=Decimal('20.00'), date_envoi=ENVOI)
        self._envoyer(orphelin)  # ne doit pas lever
        self.assertEqual(self._touches('apres_devis').count(), 0)


class DimancheFamilleTests(_Base):
    """MRY4 — « Dimanche famille » est RÉSERVÉE aux dossiers étiquetés
    « Décision à plusieurs ».

    Posée sur tous, elle envoyait un message dominical « parlez-en en
    famille » à des prospects qui décident seuls — le dimanche, hors de toute
    fenêtre d'appel ouvrée.
    """

    slug = 'mry7-dimanche'

    def _dimanche_famille(self):
        return self._touches('apres_devis').filter(
            template_cle='dimanche_famille')

    def test_sans_letiquette_la_touche_nest_pas_posee(self):
        self._envoyer(self._devis('DEV-MRY7-0300'))
        self.assertEqual(self._dimanche_famille().count(), 0)
        self.assertEqual(self._touches('apres_devis').count(), 9)

    def test_avec_letiquette_la_touche_est_posee(self):
        self.lead.tags = 'Décision à plusieurs'
        self.lead.save(update_fields=['tags'])
        self._envoyer(self._devis('DEV-MRY7-0301'))
        self.assertEqual(self._dimanche_famille().count(), 1)
        self.assertEqual(self._touches('apres_devis').count(), 10)

    def test_letiquette_est_reconnue_sans_accent_ni_casse(self):
        """`Lead.tags` est un champ LIBRE saisi à la main : « decision a
        plusieurs » désigne la même chose."""
        self.lead.tags = 'Compare les devis, DECISION A PLUSIEURS'
        self.lead.save(update_fields=['tags'])
        self._envoyer(self._devis('DEV-MRY7-0302'))
        self.assertEqual(self._dimanche_famille().count(), 1)

    def test_la_touche_tombe_bien_un_dimanche_dans_sa_fenetre(self):
        self.lead.tags = 'Décision à plusieurs'
        self.lead.save(update_fields=['tags'])
        self._envoyer(self._devis('DEV-MRY7-0303'))
        touche = self._dimanche_famille().get()
        locale = touche.due_at.astimezone(horaires.CASABLANCA)
        self.assertEqual(locale.weekday(), 6)
        self.assertGreaterEqual(locale.time(), horaires.DIMANCHE_DEBUT)
        self.assertLess(locale.time(), horaires.DIMANCHE_FIN)

    def test_la_numerotation_du_gabarit_garde_son_trou(self):
        """Les `ordre` viennent du gabarit de la société, jamais d'un
        compteur local : écarter un barreau ne renumérote pas les autres."""
        self._envoyer(self._devis('DEV-MRY7-0304'))
        ordres = sorted(
            self._touches('apres_devis').values_list('ordre', flat=True))
        self.assertNotIn(3, ordres)
        self.assertEqual(ordres, [1, 2, 4, 5, 6, 7, 8, 9, 10])


class RefusTests(_Base):
    slug = 'mry7-refus'

    def test_le_refus_arrete_la_cadence_sans_marquer_perdu(self):
        devis = self._devis('DEV-MRY7-0100')
        self._envoyer(devis)
        self.assertGreater(
            self._touches('apres_devis',
                          statut=RelanceEtape.Statut.A_FAIRE).count(), 0)
        devis_refused.send(
            sender='test', devis=devis, user=self.acteur,
            motif_refus='Trop cher')
        self.assertEqual(
            self._touches('apres_devis',
                          statut=RelanceEtape.Statut.A_FAIRE).count(), 0)
        self.lead.refresh_from_db()
        self.assertFalse(self.lead.perdu)

    def test_un_refus_sans_cadence_ouverte_pose_l_etape_de_decision(self):
        """QJ-INVARIANT (revue Fable m5, 07/09/2026) — même sans cadence
        active, un devis refusé laisse une étape « décider la suite » (le
        dossier ne disparaît pas) ; un événement REJOUÉ n'ajoute rien (le
        filet no-op sur une étape déjà ouverte — anti-spam conservé)."""
        from apps.crm.services import FILET_REFUS_LIBELLE
        devis = self._devis('DEV-MRY7-0101')
        devis_refused.send(sender='test', devis=devis, user=self.acteur,
                           motif_refus='Trop cher')
        decisions = self.lead.relance_etapes.filter(
            cadence='generique', libelle=FILET_REFUS_LIBELLE,
            statut=RelanceEtape.Statut.A_FAIRE)
        self.assertEqual(decisions.count(), 1)
        avant = LeadActivity.objects.filter(lead=self.lead).count()
        devis_refused.send(sender='test', devis=devis, user=self.acteur,
                           motif_refus='Trop cher')
        self.assertEqual(decisions.count(), 1)
        self.assertEqual(
            LeadActivity.objects.filter(lead=self.lead).count(), avant)


class SuppressionQJ4Tests(_Base):
    slug = 'mry7-qj4'

    def test_un_devis_a_cadence_active_supprime_le_nudge(self):
        from apps.ventes.domain.recouvrement import _nudge_suppressed
        devis = self._devis('DEV-MRY7-0200')
        self._envoyer(devis)
        self.assertTrue(devis_a_cadence_active(devis.pk))
        self.assertTrue(_nudge_suppressed(devis, timezone.localdate()))

    def test_sans_cadence_le_comportement_QJ4_est_inchange(self):
        from apps.ventes.domain.recouvrement import _nudge_suppressed
        devis = self._devis('DEV-MRY7-0201')
        self.assertFalse(devis_a_cadence_active(devis.pk))
        # Aucune relance planifiée, aucun contact récent : QJ4 passe.
        self.assertFalse(_nudge_suppressed(devis, timezone.localdate()))

    def test_une_cadence_entierement_traitee_rend_la_main_a_QJ4(self):
        from apps.ventes.domain.recouvrement import _nudge_suppressed
        devis = self._devis('DEV-MRY7-0202')
        self._envoyer(devis)
        RelanceEtape.objects.filter(devis_id=devis.pk).update(
            statut=RelanceEtape.Statut.FAIT)
        self.assertFalse(devis_a_cadence_active(devis.pk))
        self.lead.relance_date = None
        self.lead.save(update_fields=['relance_date'])
        self.assertFalse(_nudge_suppressed(devis, timezone.localdate()))
