"""CAD56 / QJR660 (décision fondateur 01/10/2026) — un devis corrigé sur
place et RENVOYÉ garde la cadence après-devis d'ORIGINE.

Le fondateur a tranché « garder » : la paire « répondez oui / non »
(``proposer_redatage_apres_devis`` / ``redater_cadence_apres_devis``) restée
sans bouton est SUPPRIMÉE. Ce module verrouille :
  * le renvoi du MÊME devis n'écrit AUCUNE proposition de redatage ;
  * aucune date ne bouge (ancre et touches restantes inchangées) ;
  * MRY7 intact : aucune seconde cadence après-devis, aucune touche
    supprimée ni recréée ;
  * la paire de fonctions n'existe plus dans ``apps.crm.services``.

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
from apps.crm import services as crm_services
from apps.crm.models import Client, Lead, LeadActivity, RelanceEtape
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


class LaCadenceDOrigineEstGardeeTests(_Base):
    slug = 'cad56-garde'

    def test_le_renvoi_n_ecrit_aucune_proposition(self):
        self._renvoyer()
        self.assertFalse(
            any('repartir du jour 1' in n or 'répondez' in n
                for n in self._notes()))

    def test_le_renvoi_ne_decale_AUCUNE_date(self):
        avant = {e.pk: (e.due_at, e.cadence_depart) for e in self._ouvertes()}
        self.assertTrue(avant, 'il faut au moins une touche ouverte')
        self._renvoyer()
        apres = {e.pk: (e.due_at, e.cadence_depart) for e in self._ouvertes()}
        self.assertEqual(avant, apres)

    def test_le_renvoi_ne_cree_AUCUNE_seconde_serie(self):
        """MRY7 intact."""
        avant = sorted(e.pk for e in self.lead.relance_etapes.all())
        self._renvoyer()
        self.assertEqual(
            sorted(e.pk for e in self.lead.relance_etapes.all()), avant)

    def test_la_paire_oui_non_est_supprimee(self):
        for nom in ('proposer_redatage_apres_devis',
                    'redater_cadence_apres_devis',
                    'PROPOSITION_REDATAGE_LIBELLE'):
            self.assertFalse(hasattr(crm_services, nom), nom)
