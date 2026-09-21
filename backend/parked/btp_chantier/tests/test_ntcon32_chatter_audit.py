"""NTCON32 — chatter générique + piste d'audit sur les objets BTP.

Ce que le test PROUVE :
  * changer le statut d'un RFI, d'une réserve, d'un visa, d'un avenant ou d'un
    DGD laisse UNE entrée de chatter (``records.Activity``, ARC8 — le chatter
    GÉNÉRIQUE du dépôt, jamais une table maison) ET une entrée
    ``audit.AuditLog`` ;
  * l'entrée porte ancien → nouveau statut, en LIBELLÉS français ;
  * une note manuelle est horodatée et attribuée à son auteur, tous deux posés
    CÔTÉ SERVEUR (le corps de requête ne porte que le texte) ;
  * l'historique local NTCON2 de la réserve (``ReserveChantierHistorique``)
    n'est PAS remplacé : les deux traces coexistent ;
  * cross-tenant : la timeline d'une société ne fuit jamais ailleurs.
"""
from django.test import TestCase
from rest_framework import status

from apps.audit.models import AuditLog
from apps.btp_chantier import services
from apps.btp_chantier.models import (
    AvenantChantier, DecompteGeneral, ReserveChantier,
    ReserveChantierHistorique, VisaDocument,
)
from apps.records.models import Activity

from .helpers import attach, auth, make_chantier, make_company, make_user

RACINE = '/api/django/btp-chantier/'


def _chatter(instance):
    from django.contrib.contenttypes.models import ContentType
    ct = ContentType.objects.get_for_model(instance.__class__)
    return Activity.objects.filter(
        content_type=ct, object_id=instance.pk).exclude(kind='')


def _audits(instance):
    from django.contrib.contenttypes.models import ContentType
    ct = ContentType.objects.get_for_model(instance.__class__)
    return AuditLog.objects.filter(content_type=ct, object_id=instance.pk)


class ChatterAuditBtpTests(TestCase):
    def setUp(self):
        self.co = make_company()
        self.chantier = make_chantier(self.co)
        self.user = make_user(self.co, role='responsable')
        self.api = auth(self.user)

    def _reserve(self):
        return ReserveChantier.objects.create(
            company=self.co, chantier=self.chantier, lot='électricité',
            localisation_plan={'document_ged_id': 1, 'x': 0.1, 'y': 0.1},
            description='Tableau non conforme', gravite='majeure',
            created_by=self.user)

    def _rfi(self):
        return services.creer_rfi(
            company=self.co, chantier=self.chantier, pose_par=self.user,
            question='Section de câble ?')

    def _visa(self):
        return VisaDocument.objects.create(
            company=self.co, chantier=self.chantier, document_ged_id=9,
            reference='VIS-1', statut=VisaDocument.Statut.SOUMIS,
            soumis_par=self.user, delai_revue_jours=7)

    def _avenant(self):
        return AvenantChantier.objects.create(
            company=self.co, chantier=self.chantier, reference='AV-1',
            description='Reprise VRD', montant_ht=1000,
            statut=AvenantChantier.Statut.SOUMIS_CLIENT, cree_par=self.user,
            impact_budget=True)

    def _dgd(self):
        return DecompteGeneral.objects.create(
            company=self.co, chantier=self.chantier, reference='DGD-1',
            montant_marche_initial_ht=100000,
            statut=DecompteGeneral.Statut.NOTIFIE, cree_par=self.user)

    # ── journal AUTOMATIQUE ancien → nouveau ───────────────────────────────
    def test_rfi_repondu_laisse_chatter_et_audit(self):
        rfi = self._rfi()
        services.repondre_rfi(rfi, auteur=self.user, texte='3G2,5')

        entrees = _chatter(rfi)
        self.assertEqual(entrees.count(), 1)
        entree = entrees.first()
        self.assertEqual(entree.kind, Activity.Kind.MODIFICATION)
        self.assertEqual(entree.field, 'statut')
        self.assertEqual(entree.old_value, 'Ouvert')
        self.assertEqual(entree.new_value, 'Répondu')
        self.assertEqual(entree.created_by_id, self.user.id)
        self.assertEqual(entree.company_id, self.co.id)

        audits = _audits(rfi)
        self.assertEqual(audits.count(), 1)
        self.assertEqual(audits.first().company_id, self.co.id)
        self.assertEqual(audits.first().user_id, self.user.id)

    def test_reserve_levee_laisse_chatter_et_audit(self):
        reserve = self._reserve()
        attach(self.co, self.user, reserve, 'apres')
        services.lever_reserve(
            reserve, user=self.user, signature_nom='A. Benali')

        entree = _chatter(reserve).first()
        self.assertIsNotNone(entree)
        self.assertEqual(entree.old_value, 'Ouverte')
        self.assertEqual(entree.new_value, 'Levée')
        self.assertEqual(_audits(reserve).count(), 1)

    def test_historique_local_ntcon2_toujours_ecrit(self):
        """Le chatter S'AJOUTE : il ne remplace pas la trace métier NTCON2."""
        reserve = self._reserve()
        attach(self.co, self.user, reserve, 'apres')
        services.lever_reserve(
            reserve, user=self.user, signature_nom='A. Benali')
        self.assertTrue(
            ReserveChantierHistorique.objects.filter(
                reserve=reserve, nouveau_statut='levee').exists())

    def test_visa_approuve_laisse_chatter_et_audit(self):
        visa = self._visa()
        services.approuver_visa(visa, user=self.user)
        entree = _chatter(visa).first()
        self.assertEqual(entree.old_value, 'Soumis')
        self.assertIn('Approuvé', entree.new_value)
        self.assertEqual(_audits(visa).count(), 1)

    def test_avenant_refuse_porte_le_motif(self):
        avenant = self._avenant()
        services.refuser_avenant(
            avenant, user=self.user, motif='hors budget')
        entree = _chatter(avenant).first()
        self.assertEqual(entree.new_value, 'Refusé')
        self.assertIn('hors budget', entree.body)
        self.assertIn('hors budget', _audits(avenant).first().detail)

    def test_dgd_finalise_laisse_chatter_et_audit(self):
        dgd = self._dgd()
        services.finaliser_dgd(dgd, user=self.user)
        entree = _chatter(dgd).first()
        self.assertEqual(entree.old_value, 'Notifié')
        self.assertEqual(entree.new_value, 'Définitif')
        self.assertEqual(_audits(dgd).count(), 1)

    def test_transition_sans_changement_ne_journalise_rien(self):
        rfi = self._rfi()
        services.journaliser_transition(
            rfi, ancien='ouvert', nouveau='ouvert', user=self.user)
        self.assertEqual(_chatter(rfi).count(), 0)

    # ── notes MANUELLES ────────────────────────────────────────────────────
    def test_note_manuelle_par_l_api(self):
        rfi = self._rfi()
        resp = self.api.post(f'{RACINE}rfi/{rfi.id}/noter/',
                             {'body': 'Relancé le BE par téléphone.'},
                             format='json')
        self.assertEqual(resp.status_code, status.HTTP_201_CREATED,
                         resp.content)
        note = _chatter(rfi).get(kind=Activity.Kind.NOTE)
        self.assertEqual(note.body, 'Relancé le BE par téléphone.')
        # Auteur + société posés CÔTÉ SERVEUR.
        self.assertEqual(note.created_by_id, self.user.id)
        self.assertEqual(note.company_id, self.co.id)
        self.assertIsNotNone(note.created_at)

    def test_note_vide_refusee(self):
        rfi = self._rfi()
        resp = self.api.post(f'{RACINE}rfi/{rfi.id}/noter/', {'body': '  '},
                             format='json')
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(_chatter(rfi).count(), 0)

    def test_note_sur_les_cinq_objets(self):
        cibles = {
            'reserves-chantier': self._reserve(),
            'rfi': self._rfi(),
            'visas': self._visa(),
            'avenants-chantier': self._avenant(),
            'decomptes-generaux': self._dgd(),
        }
        for route, cible in cibles.items():
            with self.subTest(route=route):
                resp = self.api.post(f'{RACINE}{route}/{cible.id}/noter/',
                                     {'body': 'note'}, format='json')
                self.assertEqual(resp.status_code,
                                 status.HTTP_201_CREATED, resp.content)
                self.assertEqual(
                    _chatter(cible).filter(kind=Activity.Kind.NOTE).count(), 1)

    # ── timeline ───────────────────────────────────────────────────────────
    def test_historique_expose_auto_et_notes(self):
        rfi = self._rfi()
        services.repondre_rfi(rfi, auteur=self.user, texte='3G2,5')
        self.api.post(f'{RACINE}rfi/{rfi.id}/noter/', {'body': 'vu'},
                      format='json')
        resp = self.api.get(f'{RACINE}rfi/{rfi.id}/historique/')
        self.assertEqual(resp.status_code, status.HTTP_200_OK, resp.content)
        genres = {ligne['kind'] for ligne in resp.data}
        self.assertEqual(
            genres, {Activity.Kind.MODIFICATION, Activity.Kind.NOTE})
        # Forme commune ChatterActivitySerializer (le front n'a qu'UN composant).
        for cle in ('kind', 'field', 'old_value', 'new_value', 'body',
                    'user_username', 'created_at'):
            self.assertIn(cle, resp.data[0])

    def test_historique_cross_tenant_404(self):
        autre = make_company()
        autre_chantier = make_chantier(autre)
        rfi_voisin = services.creer_rfi(
            company=autre, chantier=autre_chantier, pose_par=None,
            question='Chez le voisin')
        resp = self.api.get(f'{RACINE}rfi/{rfi_voisin.id}/historique/')
        self.assertEqual(resp.status_code, status.HTTP_404_NOT_FOUND)
