"""QJR134 — l'aval de l'acceptation devient atomique, verrouillé et rejouable.

Trois constats frères de l'audit du 30/08/2026, traités ensemble parce qu'ils
décrivent le MÊME défaut : la vente n'était pas enregistrée d'un bloc.

  · ES3 — le ``with transaction.atomic()`` se refermait juste après le
    ``save`` du statut : chatter, signature, attribution, effondrement des
    sœurs et ``devis_accepted.send`` s'exécutaient hors transaction et hors
    verrou, sans ``ATOMIC_REQUESTS``. Un échec chez UN abonné (``send()``
    propage la première exception) laissait un devis « accepté » SANS bon de
    commande ni facture — et la garde d'idempotence rendait le rejeu
    impossible : l'état partiel était PERMANENT et SILENCIEUX.
  · ES14 — le verrou ne portait que sur LA ligne du devis accepté ;
    l'effondrement des sœurs s'exécutait hors de lui et sans
    ``select_for_update`` : deux POST concurrents sur deux jetons du même
    groupe de variantes acceptaient les DEUX.
  · ES11 — l'échec de ``_create_esign_record`` est avalé en WARNING, et
    l'email affirmait quand même au client « Votre signature électronique a
    été enregistrée ».

Lancer :
    docker compose exec django_core python manage.py test \
        apps.ventes.tests.test_qjr134_acceptation_atomique -v 2
"""
from decimal import Decimal
from unittest.mock import patch

from django.db import connection
from django.test import TestCase
from django.test.utils import CaptureQueriesContext

from apps.crm.models import Client
from apps.stock.models import Produit
from apps.ventes.domain.lignes import creer_ligne
from apps.ventes.models import Devis, DevisSignature, EmailLog
from apps.ventes.services import AcceptError, accept_devis
from apps.ventes.tests._quote_engine_common import pdf_signe_en_ligne
from authentication.models import Company
from core.events import devis_accepted

PHRASE_SIGNATURE = 'Votre signature électronique a été enregistrée'

RESEAU = 'Onduleur réseau Huawei 10kW Monophasé'
PANNEAU = 'Panneau Canadian Solar 710W'


class _BaseAcceptation(TestCase):
    """Un groupe de VARIANTES : la racine et sa sœur, toutes deux envoyées."""

    slug = 'qjr134'

    def setUp(self):
        self.company, _ = Company.objects.get_or_create(
            slug=self.slug, defaults={'nom': self.slug})
        self.client_obj = Client.objects.create(
            company=self.company, nom='Client', prenom='QJR134',
            email='qjr134-%s@example.com' % self.slug)
        self._sku = 0
        self.racine = self._devis('DEV-QJR134-A')
        self.soeur = self._devis('DEV-QJR134-B', parent=self.racine)

    def _accepter(self, **kwargs):
        """``accept_devis`` + l'après-commit joué en ligne : la confirmation
        part de la tâche « PDF signé » (ERR-ACCEPTATION-PDF-SIGNE-SYNCHRONE)."""
        with pdf_signe_en_ligne(self):
            return accept_devis(**kwargs)

    def _devis(self, ref, *, parent=None):
        devis = Devis.objects.create(
            company=self.company, reference=ref, client=self.client_obj,
            statut=Devis.Statut.ENVOYE, taux_tva=Decimal('20'),
            mode_installation='residentiel', is_active=True,
            version=(parent.version + 1 if parent else 1),
            version_parent=parent)
        for nom, qte, pu in ((PANNEAU, '10', '1166.67'),
                             (RESEAU, '1', '15000.00')):
            self._sku += 1
            produit = Produit.objects.create(
                company=self.company, nom=nom,
                sku='QJR134-%d-%s' % (self._sku, self.company.pk),
                prix_vente=Decimal(pu), prix_achat=Decimal('1'),
                quantite_stock=50)
            creer_ligne(devis, produit=produit, designation=nom,
                        quantite=Decimal(qte), prix_unitaire=Decimal(pu),
                        remise=Decimal('0'))
        return devis


class _AbonneEnEchec:
    """Un abonné à ``devis_accepted`` qui lève — connecté le temps du bloc."""

    UID = 'qjr134-abonne-en-echec'

    def __enter__(self):
        devis_accepted.connect(self._boom, dispatch_uid=self.UID, weak=False)
        return self

    def __exit__(self, *exc):
        devis_accepted.disconnect(dispatch_uid=self.UID)
        return False

    @staticmethod
    def _boom(sender, **kwargs):
        raise RuntimeError('abonné en échec (simulé)')


class LAvalEstDansLaMemeTransaction(_BaseAcceptation):
    """ES3 — soit la vente entière est enregistrée, soit RIEN ne l'est."""

    slug = 'qjr134-atomique'

    def test_un_abonne_en_echec_annule_toute_la_vente(self):
        with _AbonneEnEchec():
            with self.assertRaises(RuntimeError):
                accept_devis(devis=self.racine, user=None, nom='M. Client',
                             ip='81.0.0.1')

        self.racine.refresh_from_db()
        self.assertEqual(
            self.racine.statut, Devis.Statut.ENVOYE,
            "le statut a été commité SEUL : c'est exactement l'état partiel "
            'permanent et silencieux que QJR134 ferme.')
        self.assertEqual(self.racine.option_acceptee or '', '')
        self.assertIsNone(self.racine.date_acceptation)

    def test_la_preuve_de_signature_est_annulee_avec_le_reste(self):
        with _AbonneEnEchec():
            with self.assertRaises(RuntimeError):
                accept_devis(devis=self.racine, user=None, nom='M. Client')
        self.assertEqual(
            DevisSignature.objects.filter(devis=self.racine).count(), 0)

    def test_l_effondrement_des_soeurs_est_annule_avec_le_reste(self):
        with _AbonneEnEchec():
            with self.assertRaises(RuntimeError):
                accept_devis(devis=self.racine, user=None, nom='M. Client')
        self.soeur.refresh_from_db()
        self.assertEqual(self.soeur.statut, Devis.Statut.ENVOYE)
        self.assertTrue(self.soeur.is_active)

    def test_aucun_email_ne_part_pour_une_vente_annulee(self):
        """Les entrées-sorties restent APRÈS le commit, donc jamais atteintes
        sur un rollback : un email annonçant une vente annulée serait pire que
        pas d'email du tout."""
        with _AbonneEnEchec():
            with self.assertRaises(RuntimeError):
                accept_devis(devis=self.racine, user=None, nom='M. Client')
        self.assertEqual(EmailLog.objects.filter(devis=self.racine).count(), 0)

    def test_le_chemin_nominal_enregistre_tout(self):
        """Le TÉMOIN : sans abonné en échec, l'acceptation complète passe."""
        accept_devis(devis=self.racine, user=None, nom='M. Client',
                     ip='81.0.0.1')
        self.racine.refresh_from_db()
        self.soeur.refresh_from_db()
        self.assertEqual(self.racine.statut, Devis.Statut.ACCEPTE)
        self.assertEqual(self.racine.accepte_par_nom, 'M. Client')
        self.assertEqual(self.soeur.statut, Devis.Statut.REFUSE)
        self.assertFalse(self.soeur.is_active)
        self.assertEqual(self.soeur.motif_refus, 'variante non retenue')
        self.assertEqual(
            DevisSignature.objects.filter(devis=self.racine).count(), 1)


class LeGroupeDeVariantesEstVerrouille(_BaseAcceptation):
    """ES14 — deux POST concurrents sur deux jetons du même groupe."""

    slug = 'qjr134-verrou'

    def test_le_verrou_porte_sur_le_groupe_entier(self):
        with CaptureQueriesContext(connection) as requetes:
            accept_devis(devis=self.racine, user=None, nom='M. Client')
        verrous_groupe = [
            q['sql'] for q in requetes.captured_queries
            if 'FOR UPDATE' in q['sql'] and 'version_parent_id' in q['sql']]
        self.assertTrue(
            verrous_groupe,
            "aucun SELECT ... FOR UPDATE ne couvre le GROUPE : l'effondrement "
            'des sœurs redevient une course entre deux acceptations.')
        # Ordre DÉTERMINISTE : deux acceptations concurrentes prennent les
        # verrous dans le même ordre, donc l'une attend au lieu de bloquer.
        self.assertIn('ORDER BY', verrous_groupe[0])

    def test_une_soeur_effondree_ne_peut_plus_etre_acceptee(self):
        """Le résultat OBSERVABLE que le verrou garantit : le groupe ne produit
        qu'UNE vente."""
        accept_devis(devis=self.racine, user=None, nom='M. Client')
        with self.assertRaises(AcceptError) as leve:
            accept_devis(devis=self.soeur, user=None, nom='M. Client')
        self.assertTrue(leve.exception.conflict)
        self.racine.refresh_from_db()
        self.soeur.refresh_from_db()
        self.assertEqual(self.racine.statut, Devis.Statut.ACCEPTE)
        self.assertEqual(self.soeur.statut, Devis.Statut.REFUSE)

    def test_le_lien_public_de_la_soeur_effondree_est_revoque(self):
        """E (revue du 24/10/2026) — accepter la variante A révoque le lien
        public de la sœur B (404 sur ``proposal_data``) ; celui de A reste."""
        from rest_framework.test import APIClient
        from apps.ventes.models import ShareLink
        lien_a = ShareLink.for_devis(self.racine)
        lien_b = ShareLink.for_devis(self.soeur)
        accept_devis(devis=self.racine, user=None, nom='M. Client')
        lien_a.refresh_from_db()
        lien_b.refresh_from_db()
        self.assertIsNotNone(lien_b.revoque_le)
        self.assertIsNone(lien_a.revoque_le)
        with patch('apps.ventes.public_views._notify_open'):
            resp = APIClient().get(
                f'/api/django/public/proposal/{lien_b.token}/data/')
        self.assertEqual(resp.status_code, 404)

    def test_un_devis_sans_variante_est_inchange(self):
        """Le groupe d'un devis seul, c'est lui-même : rien à effondrer."""
        seul = self._devis('DEV-QJR134-SEUL')
        accept_devis(devis=seul, user=None, nom='M. Client')
        seul.refresh_from_db()
        self.assertEqual(seul.statut, Devis.Statut.ACCEPTE)
        self.assertTrue(seul.is_active)


class LesRefusPortentUnCodeDuContrat(_BaseAcceptation):
    """D (revue du 24/10/2026) — tout 409 de l'acceptation est
    ``{detail, code}`` avec un code de la liste FERMÉE de
    ``proposal_accept.json`` ; « Seul un devis en cours… » et « Devis
    introuvable » n'en portaient aucun."""

    slug = 'qjr134-codes'

    def test_devis_refuse_lien_vivant_409_statut(self):
        import json
        from pathlib import Path
        from rest_framework.test import APIClient
        from apps.ventes.models import ShareLink
        contrat = json.loads((Path(__file__).resolve().parent.parent
                              / 'contract_samples' / 'proposal_accept.json')
                             .read_text(encoding='utf-8'))
        seul = self._devis('DEV-QJR134-REF')
        link = ShareLink.for_devis(seul)
        # Refusé SANS passer par le service (le lien reste vivant) : la garde
        # sous verrou d'``accept_devis`` dit pourquoi.
        Devis.objects.filter(pk=seul.pk).update(statut=Devis.Statut.REFUSE)
        resp = APIClient().post(
            f'/api/django/public/proposal/{link.token}/accept/',
            {'nom': 'M. Client', 'consent_esign': True,
             'empreinte_contenu': 'x'}, format='json')
        self.assertEqual(resp.status_code, 409, resp.data)
        self.assertEqual(set(resp.data), {'detail', 'code'})
        self.assertEqual(resp.data['code'], 'statut')
        self.assertIn(resp.data['code'], contrat['codes_409'])
        seul.refresh_from_db()
        self.assertEqual(seul.statut, Devis.Statut.REFUSE)
        self.assertFalse(DevisSignature.objects.filter(devis=seul).exists())

    def test_service_statut_et_introuvable_portent_leur_code(self):
        seul = self._devis('DEV-QJR134-REF2')
        Devis.objects.filter(pk=seul.pk).update(statut=Devis.Statut.REFUSE)
        with self.assertRaises(AcceptError) as leve:
            accept_devis(devis=seul, user=None, nom='M. Client')
        self.assertEqual((leve.exception.conflict, leve.exception.code),
                         (True, 'statut'))
        with patch('apps.ventes.selectors.groupe_proposition',
                   return_value=Devis.objects.none()):
            with self.assertRaises(AcceptError) as leve:
                accept_devis(devis=seul, user=None, nom='M. Client')
        self.assertEqual((leve.exception.conflict, leve.exception.code),
                         (True, 'inactive'))


class LeRejeuDeLAval(_BaseAcceptation):
    """Le drapeau de complétion : « accepté » signifie désormais que l'aval a
    été commité — et l'aval d'un devis accepté AVANT ce lot reste rejouable."""

    slug = 'qjr134-rejeu'

    def setUp(self):
        super().setUp()
        self.publications = []
        devis_accepted.connect(self._compter, dispatch_uid='qjr134-compteur',
                               weak=False)
        self.addCleanup(devis_accepted.disconnect,
                        dispatch_uid='qjr134-compteur')

    def _compter(self, sender, devis, **kwargs):
        self.publications.append(devis.pk)

    def test_le_resubmit_reste_un_no_op_par_defaut(self):
        accept_devis(devis=self.racine, user=None, nom='M. Client')
        self.assertEqual(len(self.publications), 1)
        accept_devis(devis=self.racine, user=None, nom='M. Client')
        self.assertEqual(len(self.publications), 1,
                         'un double envoi ne re-publie pas la vente')

    def test_rejouer_aval_republie_et_reeffondre(self):
        accept_devis(devis=self.racine, user=None, nom='M. Client')
        # On reconstitue l'état PARTIEL d'un devis accepté avant ce lot : le
        # statut est là, l'aval n'a pas été fait.
        Devis.objects.filter(pk=self.soeur.pk).update(
            statut=Devis.Statut.ENVOYE, is_active=True, motif_refus='')

        accept_devis(devis=self.racine, user=None, rejouer_aval=True)

        self.assertEqual(len(self.publications), 2)
        self.soeur.refresh_from_db()
        self.assertEqual(self.soeur.statut, Devis.Statut.REFUSE)
        self.assertFalse(self.soeur.is_active)

    def test_rejouer_aval_ne_retouche_ni_le_statut_ni_le_tampon(self):
        accept_devis(devis=self.racine, user=None, nom='M. Client')
        self.racine.refresh_from_db()
        avant = (self.racine.statut, self.racine.accepte_par_nom,
                 self.racine.date_acceptation, self.racine.option_acceptee)

        accept_devis(devis=self.racine, user=None, nom='QUELQU_UN_D_AUTRE',
                     rejouer_aval=True)

        self.racine.refresh_from_db()
        self.assertEqual(
            (self.racine.statut, self.racine.accepte_par_nom,
             self.racine.date_acceptation, self.racine.option_acceptee), avant)
        self.assertEqual(
            DevisSignature.objects.filter(devis=self.racine).count(), 1)


class LEmailNePromentQueLaPreuveQuiExiste(_BaseAcceptation):
    """ES11 — « Votre signature électronique a été enregistrée », affirmé
    inconditionnellement alors que l'enregistrement pouvait ne pas exister."""

    slug = 'qjr134-email'

    def _corps_email(self, devis):
        log = EmailLog.objects.filter(devis=devis).order_by('-id').first()
        self.assertIsNotNone(log, 'aucun email de confirmation envoyé')
        return log.corps or ''

    def test_avec_enregistrement_la_phrase_est_servie(self):
        self._accepter(devis=self.racine, user=None, nom='M. Client')
        self.assertIn(PHRASE_SIGNATURE, self._corps_email(self.racine))

    def test_sans_enregistrement_la_phrase_disparait(self):
        """``_create_esign_record`` est best-effort : son échec est avalé en
        WARNING. L'email ne doit alors plus rien affirmer."""
        with patch('apps.ventes.domain.cycle_vie._create_esign_record',
                   return_value=None):
            self._accepter(devis=self.racine, user=None, nom='M. Client')
        self.assertEqual(
            DevisSignature.objects.filter(devis=self.racine).count(), 0)
        corps = self._corps_email(self.racine)
        self.assertNotIn(PHRASE_SIGNATURE, corps)
        self.assertNotIn('exemplaire signé', corps)
        # Le reste de l'email — l'accusé de réception — part comme avant.
        self.assertIn('Nous avons bien reçu votre acceptation', corps)


class LaConfirmationVaAuxDeuxParties(_BaseAcceptation):
    """ADEV99 — signataire ET contact du lead, copie PDF au vendeur ; raison
    sociale / ICE / horodatage Casablanca / empreinte dans le corps ; anglais
    quand la page était lue en anglais."""

    slug = 'adev99-email'

    ENTREPRISE = {'raison_sociale': 'Hôtel Exemple SARL',
                  'signataire_qualite': 'Directeur général',
                  'ice': '000000000000000',
                  'signataire_email': 'dg@hotel-exemple.test',
                  'pouvoir_engager': True}

    def _avec_lead_et_vendeur(self):
        from django.contrib.auth import get_user_model
        from apps.crm.models import Lead
        vendeur = get_user_model().objects.create_user(
            username='adev99-vendeur', password='x', company=self.company,
            email='vendeur@adev99.test', role_legacy='commercial')
        lead = Lead.objects.create(company=self.company, nom='Contact',
                                   email='contact@hotel-exemple.test',
                                   owner=vendeur)
        Devis.objects.filter(pk=self.racine.pk).update(lead=lead)
        self.racine.refresh_from_db()

    def test_signataire_contact_et_copie_vendeur(self):
        self._avec_lead_et_vendeur()
        self._accepter(devis=self.racine, user=None, nom='Karim Exemple',
                       entreprise=dict(self.ENTREPRISE))
        logs = {log.to_email: log for log in EmailLog.objects.filter(
            devis=self.racine)}
        self.assertEqual(set(logs), {'dg@hotel-exemple.test',
                                     'contact@hotel-exemple.test',
                                     'vendeur@adev99.test'})
        corps = logs['dg@hotel-exemple.test'].corps
        self.assertIn(PHRASE_SIGNATURE, corps)
        self.assertIn('Société : Hôtel Exemple SARL — ICE : 000000000000000', corps)
        self.assertIn('(heure de Casablanca)', corps)
        sig = DevisSignature.objects.get(devis=self.racine)
        self.assertIn(sig.content_hash, corps)
        copie = logs['vendeur@adev99.test']
        self.assertTrue(copie.sujet.startswith('Copie'))
        self.assertIn('dg@hotel-exemple.test', copie.corps)

    def test_un_destinataire_en_echec_n_arrete_pas_l_autre(self):
        """G (revue du 24/10/2026) — l'envoi au signataire lève : le contact
        du lead reçoit QUAND MÊME sa confirmation (outbox), l'acceptation
        tient."""
        from django.core import mail
        from apps.ventes import email_service
        self._avec_lead_et_vendeur()
        vrai_envoi = email_service.send_document_email

        def envoi(devis, *, to_email, **kwargs):
            if to_email == 'dg@hotel-exemple.test':
                raise RuntimeError('SMTP refuse ce destinataire (simulé)')
            return vrai_envoi(devis, to_email=to_email, **kwargs)

        mail.outbox = []
        with patch.object(email_service, 'send_document_email',
                          side_effect=envoi):
            self._accepter(devis=self.racine, user=None, nom='Karim Exemple',
                           entreprise=dict(self.ENTREPRISE))
        destinataires = {to for m in mail.outbox for to in m.to}
        self.assertIn('contact@hotel-exemple.test', destinataires)
        self.assertNotIn('dg@hotel-exemple.test', destinataires)
        self.racine.refresh_from_db()
        self.assertEqual(self.racine.statut, Devis.Statut.ACCEPTE)

    def test_confirmation_en_anglais_quand_la_page_l_etait(self):
        self._accepter(devis=self.racine, user=None, nom='Mr Client',
                       langue='en')
        log = EmailLog.objects.filter(devis=self.racine).order_by('-id').first()
        self.assertTrue(log.sujet.startswith('Proposal accepted'), log.sujet)
        self.assertIn('Fingerprint of the signed content (SHA-256)', log.corps)
        self.assertIn('(Casablanca time)', log.corps)
        self.assertEqual(
            DevisSignature.objects.get(devis=self.racine).langue_page, 'en')


class EmailExemplaireSigneTests(_BaseAcceptation):
    """ADEV38 (C-ADEV-055) — « votre exemplaire signé ci-joint » n'est écrit
    que si le PDF signé est stocké (``signed_pdf_key``) et joint. Code réel de
    bout en bout (``accept_devis`` → ``envoyer_confirmations``, backend locmem) ;
    seules les bornes du stockage (rendu + MinIO) sont simulées, pour fixer l'état
    ``signed_pdf_key`` vide (échec de stockage) ou rempli."""

    slug = 'adev38-email'

    def _message_au_client(self):
        from django.core import mail
        messages = [m for m in mail.outbox
                    if self.client_obj.email in m.to
                    and m.subject.startswith(('Proposition acceptée',
                                              'Proposal accepted'))]
        self.assertEqual(len(messages), 1, [(m.to, m.subject) for m in mail.outbox])
        return messages[0]

    def test_sans_pdf_signe_pas_de_promesse(self):
        """Stockage du PDF signé en échec ⇒ ``signed_pdf_key`` vide : le corps
        n'annonce aucune pièce signée."""
        from django.core import mail
        mail.outbox = []
        with patch('apps.ventes.domain.cycle_vie._store_signed_pdf'):
            self._accepter(devis=self.racine, user=None, nom='M. Client')
        sig = DevisSignature.objects.get(devis=self.racine)
        self.assertFalse(sig.signed_pdf_key)  # None ou '' : rien de stocké
        corps = self._message_au_client().body
        self.assertIn(PHRASE_SIGNATURE, corps)  # la preuve, elle, existe
        self.assertNotIn('exemplaire signé', corps)
        self.assertNotIn('ci-joint', corps)

    def test_sans_pdf_signe_pas_de_promesse_en_anglais(self):
        from django.core import mail
        mail.outbox = []
        with patch('apps.ventes.domain.cycle_vie._store_signed_pdf'):
            self._accepter(devis=self.racine, user=None, nom='Mr Client',
                           langue='en')
        corps = self._message_au_client().body
        self.assertIn('Fingerprint of the signed content', corps)
        self.assertNotIn('signed copy', corps)
        self.assertNotIn('attached', corps)

    def test_avec_pdf_signe_joint_et_annonce(self):
        """Stockage réussi ⇒ ``signed_pdf_key`` rempli : l'exemplaire signé
        (la copie figée ``…__signe.pdf``) est joint ET annoncé."""
        from django.core import mail
        octets = b'%PDF-1.7 exemplaire signe ADEV38'
        mail.outbox = []
        with patch('apps.ventes.quote_engine.generate_premium_devis_pdf',
                   return_value='devis/adev38/DEV-QJR134-A.pdf'), \
                patch('apps.ventes.utils.pdf._upload_pdf'), \
                patch('apps.ventes.utils.pdf.download_pdf',
                      return_value=octets) as telechargement:
            self._accepter(devis=self.racine, user=None, nom='M. Client')
        sig = DevisSignature.objects.get(devis=self.racine)
        self.assertEqual(sig.signed_pdf_key,
                         'devis/adev38/DEV-QJR134-A__signe.pdf')
        message = self._message_au_client()
        self.assertIn('exemplaire signé', message.body)
        self.assertIn('ci-joint', message.body)
        self.assertEqual(
            [(nom, contenu) for nom, contenu, _ in message.attachments],
            [('DEV-QJR134-A.pdf', octets)])
        # La pièce jointe vient bien de la clé du PDF SIGNÉ.
        telechargement.assert_any_call(sig.signed_pdf_key)
