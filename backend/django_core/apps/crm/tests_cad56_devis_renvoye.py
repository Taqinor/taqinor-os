"""CAD56 — un devis corrigé et RENVOYÉ propose de repartir du jour 1.

Constat de l'audit L3 du 21/09/2026 : la branche « déjà en cours » du
récepteur ne touche pas à l'ancre — ``initialiser_plan_relance`` sort par
``ouvertes_deja`` sans modifier ``cadence_depart``, et le compteur continue
depuis le PREMIER envoi. Le client reçoit « je classe ? » deux jours après sa
nouvelle proposition.

Ce que ce module verrouille :
  * le renvoi du MÊME devis ÉMET la proposition (une ligne de chatter) ;
  * « oui » redate l'ancre ET les touches restantes, du MÊME écart ;
  * « non » ne change RIEN — et le dit ;
  * MRY7 intact : aucune seconde cadence après-devis n'est créée, aucune
    touche supprimée ni recréée.

Le temps est GELÉ : « deux jours après » est exactement la question qu'une
horloge vivante rend instable.
"""
import datetime
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase

from authentication.models import Company
from core.events import devis_sent

from apps.crm import horaires
from apps.crm.models import Client, Lead, LeadActivity, RelanceEtape
from apps.crm.services import (
    PROPOSITION_REDATAGE_LIBELLE, redater_cadence_apres_devis,
)
from apps.parametres.models import CompanyProfile
from apps.ventes.models import Devis

User = get_user_model()

#: Lundi 7 septembre 2026, 10 h — premier envoi.
ENVOI = datetime.datetime(2026, 9, 7, 10, 0, tzinfo=horaires.CASABLANCA)
#: Lundi 14 septembre 2026, 10 h — le devis corrigé repart, une semaine après.
RENVOI = datetime.datetime(2026, 9, 14, 10, 0, tzinfo=horaires.CASABLANCA)


class _Base(TestCase):
    slug = 'cad56'

    def setUp(self):
        self.company = Company.objects.create(slug=self.slug, nom=self.slug)
        CompanyProfile.objects.create(company=self.company)
        self.acteur = User.objects.create_user(
            username=f'{self.slug}-u', password='x',
            role_legacy='responsable', company=self.company)
        self.lead = Lead.objects.create(
            company=self.company, nom='Prospect', owner=self.acteur,
            telephone='+212661112233')
        self.client_obj = Client.objects.create(
            company=self.company, nom='Client',
            email=f'{self.slug}@example.com')
        self.devis = Devis.objects.create(
            company=self.company, reference='DEV-CAD56-0001',
            client=self.client_obj, lead=self.lead, statut='envoye',
            taux_tva=Decimal('20.00'), date_envoi=ENVOI)
        devis_sent.send(sender='test', devis=self.devis, user=self.acteur,
                        ancien_statut='brouillon')

    def _ouvertes(self):
        return list(self.lead.relance_etapes.filter(
            cadence='apres_devis',
            statut=RelanceEtape.Statut.A_FAIRE).order_by('ordre'))

    def _renvoyer(self):
        self.devis.date_envoi = RENVOI
        self.devis.save(update_fields=['date_envoi'])
        devis_sent.send(sender='test', devis=self.devis, user=self.acteur,
                        ancien_statut='envoye')

    def _notes(self):
        return list(LeadActivity.objects.filter(
            lead=self.lead, kind=LeadActivity.Kind.NOTE)
            .values_list('body', flat=True))


class LaPropositionTests(_Base):
    slug = 'cad56-proposition'

    def test_le_premier_envoi_ne_propose_rien(self):
        """Anti-faux-vert : c'est bien le RENVOI qui déclenche la question."""
        self.assertFalse(
            any(PROPOSITION_REDATAGE_LIBELLE in n for n in self._notes()))

    def test_le_renvoi_du_MEME_devis_emet_la_proposition(self):
        self._renvoyer()
        self.assertTrue(
            any(PROPOSITION_REDATAGE_LIBELLE in n for n in self._notes()))

    def test_le_renvoi_ne_cree_AUCUNE_seconde_serie(self):
        """MRY7 intact."""
        avant = self.lead.relance_etapes.filter(cadence='apres_devis').count()
        self._renvoyer()
        self.assertEqual(
            self.lead.relance_etapes.filter(cadence='apres_devis').count(),
            avant)

    def test_la_proposition_seule_ne_decale_AUCUNE_date(self):
        avant = {e.pk: e.due_at for e in self._ouvertes()}
        self._renvoyer()
        apres = {e.pk: e.due_at for e in self._ouvertes()}
        self.assertEqual(avant, apres)


class LeChoixOuiTests(_Base):
    slug = 'cad56-oui'

    def test_oui_redate_l_ancre_et_les_touches_restantes(self):
        self._renvoyer()
        avant = {e.pk: (e.due_at, e.cadence_depart) for e in self._ouvertes()}
        self.assertTrue(avant, 'il faut au moins une touche ouverte')

        decalees = redater_cadence_apres_devis(
            self.lead, self.acteur, devis=self.devis, depart=RENVOI,
            accepte=True)

        self.assertEqual(decalees, len(avant))
        ecart = RENVOI - ENVOI
        for etape in self._ouvertes():
            ancienne_due, ancienne_ancre = avant[etape.pk]
            self.assertEqual(etape.due_at, ancienne_due + ecart)
            if ancienne_ancre is not None:
                self.assertEqual(
                    etape.cadence_depart, ancienne_ancre + ecart)

    def test_oui_ne_supprime_ni_ne_recree_aucune_touche(self):
        self._renvoyer()
        avant = sorted(e.pk for e in self.lead.relance_etapes.all())
        redater_cadence_apres_devis(
            self.lead, self.acteur, devis=self.devis, depart=RENVOI)
        self.assertEqual(
            sorted(e.pk for e in self.lead.relance_etapes.all()), avant)

    def test_oui_est_journalise(self):
        self._renvoyer()
        redater_cadence_apres_devis(
            self.lead, self.acteur, devis=self.devis, depart=RENVOI)
        self.assertTrue(any('redaté' in n for n in self._notes()))

    def test_un_ecart_nul_ne_bouge_rien(self):
        self._renvoyer()
        avant = {e.pk: e.due_at for e in self._ouvertes()}
        ancre = self._ouvertes()[0].cadence_depart
        self.assertEqual(
            redater_cadence_apres_devis(
                self.lead, self.acteur, devis=self.devis, depart=ancre), 0)
        self.assertEqual({e.pk: e.due_at for e in self._ouvertes()}, avant)


class LeChoixNonTests(_Base):
    slug = 'cad56-non'

    def test_non_ne_change_RIEN(self):
        """Le choix par défaut : les dates d'origine restent."""
        self._renvoyer()
        avant = {e.pk: (e.due_at, e.cadence_depart) for e in self._ouvertes()}

        self.assertEqual(
            redater_cadence_apres_devis(
                self.lead, self.acteur, devis=self.devis, depart=RENVOI,
                accepte=False), 0)

        apres = {e.pk: (e.due_at, e.cadence_depart) for e in self._ouvertes()}
        self.assertEqual(avant, apres)

    def test_non_est_journalise_aussi(self):
        self._renvoyer()
        redater_cadence_apres_devis(
            self.lead, self.acteur, devis=self.devis, accepte=False)
        self.assertTrue(
            any('GARDE ses dates' in n for n in self._notes()))


class SansSuiviOuvertTests(_Base):
    slug = 'cad56-vide'

    def test_sans_touche_ouverte_il_n_y_a_rien_a_redater(self):
        self.lead.relance_etapes.filter(cadence='apres_devis').update(
            statut=RelanceEtape.Statut.FAIT)
        self.assertEqual(
            redater_cadence_apres_devis(
                self.lead, self.acteur, devis=self.devis, depart=RENVOI), 0)
