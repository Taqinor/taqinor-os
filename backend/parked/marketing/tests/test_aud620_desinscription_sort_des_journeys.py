"""AUD620 [CNDP, priorité haute] — se désinscrire doit AUSSI sortir le lead
de ses séquences/journeys actifs.

Constat d'origine : ``desinscrire_via_token`` n'appelait que
``supprimer_destinataire``, qui posait un simple ``SuppressionMarketing``.
Les envois FUTURS étaient bien filtrés, mais une ``InscriptionSequence`` déjà
``ACTIF`` le restait et continuait d'être avancée à chaque tick beat par
``executer_etapes_dues`` (moteur linéaire) et ``executer_journeys_dus``
(moteur graphe) : un contact ayant demandé à ne plus être contacté restait
dans le tunnel. Impact dormant tant que l'envoi réel est no-op (FG31), actif
dès qu'une intégration Brevo/WhatsApp est branchée.

Test ROUGE d'abord : ``test_desinscription_sort_le_lead_de_sa_sequence``
laissait l'inscription ACTIF après la désinscription.
"""
from django.test import TestCase

from authentication.models import Company

from apps.compta import services
from apps.crm.models import Lead
from apps.crm.selectors import lead_ids_by_contact
from apps.marketing.models import (
    InscriptionSequence, SequenceRelance, SuppressionMarketing,
)


class DesinscriptionSortDesJourneysTests(TestCase):
    def setUp(self):
        self.co = Company.objects.create(slug='aud620', nom='AUD620')
        self.sequence = SequenceRelance.objects.create(
            company=self.co, nom='Nurture')
        self.lead = Lead.objects.create(
            company=self.co, nom='Ahmed', email='ahmed@exemple.ma',
            telephone='0612345678')
        self.inscription = InscriptionSequence.objects.create(
            company=self.co, sequence=self.sequence, lead_id=self.lead.id,
            statut=InscriptionSequence.Statut.ACTIF)

    def _statut(self):
        self.inscription.refresh_from_db()
        return self.inscription.statut

    def test_desinscription_sort_le_lead_de_sa_sequence(self):
        """ROUGE avant correctif : l'inscription restait ACTIF."""
        token = services.generer_token_desinscription(
            self.co.id, 'ahmed@exemple.ma')
        ok, destinataire = services.desinscrire_via_token(token)
        self.assertTrue(ok)
        self.assertEqual(destinataire, 'ahmed@exemple.ma')
        self.assertEqual(self._statut(), InscriptionSequence.Statut.SORTI)

    def test_la_suppression_marketing_est_toujours_posee(self):
        """Le comportement XMKT3 d'origine n'est pas remplacé, il est
        complété."""
        token = services.generer_token_desinscription(
            self.co.id, 'ahmed@exemple.ma')
        services.desinscrire_via_token(token)
        self.assertTrue(services.est_supprime(self.co, 'ahmed@exemple.ma'))

    def test_motif_de_sortie_trace_la_cause(self):
        token = services.generer_token_desinscription(
            self.co.id, 'ahmed@exemple.ma')
        services.desinscrire_via_token(token)
        self.inscription.refresh_from_db()
        self.assertIn('suppression_marketing', self.inscription.motif_sortie)

    def test_stop_sms_sort_aussi_le_lead(self):
        """XMKT15 — le STOP entrant passe par le même chokepoint."""
        services.traiter_stop_entrant(self.co, '0612345678')
        self.assertEqual(self._statut(), InscriptionSequence.Statut.SORTI)

    def test_plainte_spam_sort_aussi_le_lead(self):
        """Une plainte est au moins aussi contraignante qu'une
        désinscription."""
        services.supprimer_destinataire(
            self.co, 'ahmed@exemple.ma',
            motif=SuppressionMarketing.Motif.PLAINTE, source='webhook')
        self.assertEqual(self._statut(), InscriptionSequence.Statut.SORTI)

    def test_liste_dopposition_importee_sort_aussi_le_lead(self):
        services.importer_liste_opposition(self.co, ['ahmed@exemple.ma'])
        self.assertEqual(self._statut(), InscriptionSequence.Statut.SORTI)

    def test_une_inscription_dune_autre_societe_nest_pas_touchee(self):
        autre = Company.objects.create(slug='aud620b', nom='AUD620B')
        sequence_autre = SequenceRelance.objects.create(
            company=autre, nom='Nurture B')
        lead_autre = Lead.objects.create(
            company=autre, nom='Ahmed', email='ahmed@exemple.ma')
        inscription_autre = InscriptionSequence.objects.create(
            company=autre, sequence=sequence_autre, lead_id=lead_autre.id,
            statut=InscriptionSequence.Statut.ACTIF)

        token = services.generer_token_desinscription(
            self.co.id, 'ahmed@exemple.ma')
        services.desinscrire_via_token(token)

        inscription_autre.refresh_from_db()
        self.assertEqual(
            inscription_autre.statut, InscriptionSequence.Statut.ACTIF)

    def test_destinataire_sans_lead_ne_casse_rien(self):
        """Un contact inconnu du CRM : la liste de suppression suffit."""
        token = services.generer_token_desinscription(
            self.co.id, 'inconnu@exemple.ma')
        ok, _ = services.desinscrire_via_token(token)
        self.assertTrue(ok)
        self.assertEqual(self._statut(), InscriptionSequence.Statut.ACTIF)

    def test_inscription_deja_sortie_reste_idempotente(self):
        services.sortir_inscription(self.inscription, motif='manuel')
        token = services.generer_token_desinscription(
            self.co.id, 'ahmed@exemple.ma')
        services.desinscrire_via_token(token)
        self.inscription.refresh_from_db()
        self.assertEqual(
            self.inscription.statut, InscriptionSequence.Statut.SORTI)
        self.assertEqual(self.inscription.motif_sortie, 'manuel')


class SelectorLeadIdsByContactTests(TestCase):
    def setUp(self):
        self.co = Company.objects.create(slug='aud620s', nom='AUD620S')
        self.lead = Lead.objects.create(
            company=self.co, nom='Fatima', email='fatima@exemple.ma',
            telephone='0698765432')

    def test_resolution_par_email_et_par_telephone(self):
        self.assertIn(
            self.lead.id,
            lead_ids_by_contact(self.co, email='fatima@exemple.ma'))
        self.assertIn(
            self.lead.id,
            lead_ids_by_contact(self.co, phone='0698765432'))

    def test_sans_critere_renvoie_vide(self):
        self.assertEqual(lead_ids_by_contact(self.co), [])

    def test_scope_societe(self):
        autre = Company.objects.create(slug='aud620s2', nom='AUD620S2')
        self.assertEqual(
            lead_ids_by_contact(autre, email='fatima@exemple.ma'), [])
