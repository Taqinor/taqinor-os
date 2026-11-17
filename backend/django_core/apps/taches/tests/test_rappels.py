"""TCH35 — Rappels : poser (jour/heure ou ancre), retirer, répéter, recalcul d'ancre, annulés à la
clôture, ≤ 5 par tâche, ≤ 100 par compte, drapeau `hors_fenetre` (invariant 19).

Base requise (`TestCase`) : joué par la CI. Les jours sont relatifs à aujourd'hui (`timezone.localdate()`,
lu à la frontière des services).
"""
import datetime

from django.http import Http404
from django.test import TestCase
from django.utils import timezone
from rest_framework import serializers

from apps.taches.choix import SourceRappel, StatutRappel, StatutTache
from apps.taches.models.taches import Rappel
from apps.taches.services.gestes import annuler_geste
from apps.taches.services.planification import planifier
from apps.taches.services.rappels import (
    annuler_rappels,
    poser_rappel,
    recalculer_ancres,
    repeter_rappel,
    retirer_rappel,
)
from apps.taches.tests import fabriques

NEUF_H = datetime.time(9, 0)


def _j(delta):
    return timezone.localdate() + datetime.timedelta(days=delta)


class RappelTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.a, cls.b = fabriques.societe('a'), fabriques.societe('b')
        cls.u1 = fabriques.compte(cls.a, nom='u1')
        cls.voisin = fabriques.compte(cls.a, nom='u2')
        cls.ailleurs = fabriques.compte(cls.b, nom='u1')

    def _rappel(self, tache, **champs):
        champs.setdefault('jour', _j(1))
        champs.setdefault('heure', NEUF_H)
        return Rappel.objects.create(company=tache.company, proprietaire=tache.proprietaire, tache=tache, **champs)

    # --- Poser ----------------------------------------------------------------------------

    def test_poser_un_rappel_absolu(self):
        tache = fabriques.tache(self.u1)
        resultat = poser_rappel(tache, acteur=self.u1, jour=_j(1), heure='09:00')
        rappel = Rappel.objects.get(pk=resultat.rappel.pk)
        self.assertEqual((rappel.jour, rappel.heure, rappel.statut, rappel.source, rappel.ancre),
                         (_j(1), NEUF_H, StatutRappel.EN_ATTENTE, SourceRappel.MANUEL, ''))
        self.assertEqual((rappel.company_id, rappel.proprietaire_id, rappel.tache_id),
                         (self.a.pk, self.u1.pk, tache.pk))
        self.assertEqual((resultat.geste.type, resultat.geste.message), ('rappel', 'Rappel posé demain à 09:00'))

    def test_poser_un_rappel_ancre_sur_l_echeance(self):
        tache = fabriques.tache(self.u1, echeance=_j(5))
        resultat = poser_rappel(tache, acteur=self.u1, ancre='echeance', decalage_jours=-1, heure='18:00')
        rappel = Rappel.objects.get(pk=resultat.rappel.pk)
        self.assertEqual((rappel.jour, rappel.ancre, rappel.decalage_jours), (_j(4), 'echeance', -1))

    def test_ancre_sans_date_refusee(self):
        tache = fabriques.tache(self.u1)
        with self.assertRaises(serializers.ValidationError):
            poser_rappel(tache, acteur=self.u1, ancre='echeance', heure='18:00')
        with self.assertRaises(serializers.ValidationError):
            poser_rappel(tache, acteur=self.u1, ancre='echeance', decalage_jours=-8, heure='18:00')
        self.assertFalse(Rappel.objects.exists())

    def test_question_titres_au_premier_rappel(self):
        tache = fabriques.tache(self.u1)
        self.assertTrue(poser_rappel(tache, acteur=self.u1, jour=_j(1), heure=NEUF_H).question_titres)
        fabriques.reglages(self.u1, titres_notifications_demande_le=timezone.now())
        self.assertFalse(poser_rappel(tache, acteur=self.u1, jour=_j(2), heure=NEUF_H).question_titres)

    def test_hors_fenetre_a_23_h(self):
        tache = fabriques.tache(self.u1)
        resultat = poser_rappel(tache, acteur=self.u1, jour=_j(1), heure=datetime.time(23, 0))
        self.assertTrue(resultat.hors_fenetre)

    def test_collecte_sans_geste(self):
        tache = fabriques.tache(self.u1)
        collecte = []
        resultat = poser_rappel(tache, acteur=self.u1, jour=_j(1), heure=NEUF_H, collecte=collecte)
        self.assertIsNone(resultat.geste)
        self.assertEqual(collecte, [{'op': 'creation', 'objet': 'rappel', 'id': resultat.rappel.pk}])

    def test_tache_d_un_autre_404_et_tache_close_refusee(self):
        a_lui = fabriques.tache(self.voisin)
        for acteur in (self.u1, self.ailleurs):
            with self.assertRaises(Http404):
                poser_rappel(a_lui, acteur=acteur, jour=_j(1), heure=NEUF_H)
        faite = fabriques.tache(self.u1, statut=StatutTache.FAIT, fait_le=timezone.now())
        with self.assertRaises(serializers.ValidationError):
            poser_rappel(faite, acteur=self.u1, jour=_j(1), heure=NEUF_H)
        self.assertFalse(Rappel.objects.exists())

    # --- Plafonds (invariant 19) ----------------------------------------------------------

    def test_cinq_au_plus_par_tache(self):
        tache = fabriques.tache(self.u1)
        self._rappel(tache, statut=StatutRappel.ANNULE)  # un annulé ne compte pas
        for n in range(5):
            poser_rappel(tache, acteur=self.u1, jour=_j(n + 1), heure=NEUF_H)
        with self.assertRaises(serializers.ValidationError) as ctx:
            poser_rappel(tache, acteur=self.u1, jour=_j(9), heure=NEUF_H)
        self.assertIn('rappel', ctx.exception.detail)
        self.assertEqual(Rappel.objects.filter(statut=StatutRappel.EN_ATTENTE).count(), 5)

    def test_cent_au_plus_par_compte(self):
        taches = [fabriques.tache(self.u1) for _ in range(20)]
        Rappel.objects.bulk_create([
            Rappel(company=self.a, proprietaire=self.u1, tache=tache, jour=_j(1), heure=NEUF_H)
            for tache in taches for _ in range(5)])
        nouvelle = fabriques.tache(self.u1)
        with self.assertRaises(serializers.ValidationError):
            poser_rappel(nouvelle, acteur=self.u1, jour=_j(1), heure=NEUF_H)
        autre = fabriques.tache(self.voisin)
        poser_rappel(autre, acteur=self.voisin, jour=_j(1), heure=NEUF_H)  # plafond par compte

    # --- Ancres ---------------------------------------------------------------------------

    def test_ancre_qui_bouge_recalcule_le_jour(self):
        tache = fabriques.tache(self.u1, jour_prevu=_j(2))
        rappel = poser_rappel(tache, acteur=self.u1, ancre='jour_prevu', heure=NEUF_H).rappel
        resultat = planifier(tache, acteur=self.u1, jour_prevu=_j(4))
        rappel.refresh_from_db()
        self.assertEqual((rappel.jour, rappel.statut), (_j(4), StatutRappel.EN_ATTENTE))
        annuler_geste(self.u1, resultat.geste.pk)
        rappel.refresh_from_db()
        self.assertEqual(rappel.jour, _j(2))

    def test_ancre_effacee_annule(self):
        tache = fabriques.tache(self.u1, jour_prevu=_j(2))
        ancre = poser_rappel(tache, acteur=self.u1, ancre='jour_prevu', heure=NEUF_H).rappel
        absolu = poser_rappel(tache, acteur=self.u1, jour=_j(3), heure=NEUF_H).rappel
        planifier(tache, acteur=self.u1, jour_prevu=None)
        ancre.refresh_from_db()
        absolu.refresh_from_db()
        self.assertEqual((ancre.statut, absolu.statut), (StatutRappel.ANNULE, StatutRappel.EN_ATTENTE))

    def test_recalculer_ancres_sur_l_echeance(self):
        tache = fabriques.tache(self.u1, echeance=_j(5))
        rappel = poser_rappel(tache, acteur=self.u1, ancre='echeance', decalage_jours=-2, heure=NEUF_H).rappel
        tache.echeance = _j(10)
        tache.save()
        collecte = []
        ops = recalculer_ancres(tache, collecte)
        rappel.refresh_from_db()
        self.assertEqual(rappel.jour, _j(8))
        self.assertEqual(ops, collecte)

    # --- Clôture, retirer, répéter -----------------------------------------------------------

    def test_cloture_annule_les_rappels_en_attente(self):
        tache = fabriques.tache(self.u1)
        en_attente = self._rappel(tache)
        envoye = self._rappel(tache, statut=StatutRappel.ENVOYE)
        ops = annuler_rappels(tache)
        en_attente.refresh_from_db()
        envoye.refresh_from_db()
        self.assertEqual((en_attente.statut, envoye.statut), (StatutRappel.ANNULE, StatutRappel.ENVOYE))
        self.assertEqual(len(ops), 1)

    def test_retirer_puis_annuler_le_retrait(self):
        tache = fabriques.tache(self.u1)
        rappel = self._rappel(tache)
        geste = retirer_rappel(self.u1, rappel.pk)
        rappel.refresh_from_db()
        self.assertEqual(rappel.statut, StatutRappel.ANNULE)
        self.assertIsNone(retirer_rappel(self.u1, rappel.pk))  # idempotent
        annuler_geste(self.u1, geste.pk)
        rappel.refresh_from_db()
        self.assertEqual(rappel.statut, StatutRappel.EN_ATTENTE)

    def test_rappel_d_un_autre_404(self):
        rappel = self._rappel(fabriques.tache(self.voisin))
        with self.assertRaises(Http404):
            retirer_rappel(self.u1, rappel.pk)
        with self.assertRaises(Http404):
            repeter_rappel(self.ailleurs, rappel.pk, dans_minutes=10)

    def test_repeter_a_un_jour_et_une_heure(self):
        tache = fabriques.tache(self.u1)
        envoye = self._rappel(tache, statut=StatutRappel.ENVOYE)
        resultat = repeter_rappel(self.u1, envoye.pk, jour=_j(1), heure='09:00')
        nouveau = Rappel.objects.get(pk=resultat.rappel.pk)
        self.assertEqual((nouveau.jour, nouveau.heure, nouveau.source, nouveau.tache_id),
                         (_j(1), NEUF_H, SourceRappel.REPETITION, tache.pk))
        self.assertEqual(resultat.geste.type, 'rappel')

    def test_repeter_dans_une_heure(self):
        tache = fabriques.tache(self.u1)
        envoye = self._rappel(tache, statut=StatutRappel.ENVOYE)
        avant = timezone.localtime().replace(tzinfo=None)
        resultat = repeter_rappel(self.u1, envoye.pk, dans_minutes=60)
        apres = timezone.localtime().replace(tzinfo=None)
        sonne = datetime.datetime.combine(resultat.rappel.jour, resultat.rappel.heure)
        self.assertLessEqual(avant + datetime.timedelta(minutes=59), sonne)
        self.assertLessEqual(sonne, apres + datetime.timedelta(minutes=60))
        self.assertEqual(resultat.geste.message, 'Rappel dans 1 h')
