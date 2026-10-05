"""VEIL19 — Conservation des textes des pubs vues et sortie d'un client."""
import datetime
from io import StringIO

from django.core.management import call_command
from django.test import TestCase, override_settings
from django.utils import timezone

from authentication.models import Company

from apps.adsengine import veille_conservation as vc
from apps.adsengine.models import (
    VeilleAnnonceur, VeilleDecouverte, VeillePubVue, VeilleRequete,
    VeilleVerdict,
)

MAINTENANT = timezone.make_aware(datetime.datetime(2026, 10, 5, 12, 0))


def peupler(company, prefixe, nb_vieilles, nb_recentes):
    dec = VeilleDecouverte.objects.create(
        company=company, plafond_appels=5, plafond_pages_par_requete=5)
    req = VeilleRequete.objects.create(company=company, decouverte=dec,
                                       mot_cle='robe', pays='FR')
    ann = VeilleAnnonceur.objects.create(
        company=company, page_id=f'{prefixe}-p', nb_pubs_vues=3,
        extraits=[{'texte': 'gardé', 'ad_archive_id': '1'}])
    verdict = VeilleVerdict.objects.create(
        company=company, annonceur=ann, classe='vendeur', decide_par='regle')
    ann.verdict_courant = verdict
    ann.save()
    for i in range(nb_vieilles + nb_recentes):
        pv = VeillePubVue.objects.create(
            company=company, requete=req, annonceur=ann,
            ad_archive_id=f'{prefixe}{i}', extrait='texte de pub',
            legende='boutique.fr', titres=['Titre'])
        if i < nb_vieilles:
            VeillePubVue.objects.filter(pk=pv.pk).update(
                created_at=MAINTENANT - datetime.timedelta(days=120))
        else:
            VeillePubVue.objects.filter(pk=pv.pk).update(
                created_at=MAINTENANT - datetime.timedelta(days=10))
    return ann


@override_settings(VEILLE_CONSERVATION_PUBS_JOURS=90)
class PurgeExtraitsTests(TestCase):
    def setUp(self):
        self.a = Company.objects.create(nom='A', slug='cons-a')
        self.b = Company.objects.create(nom='B', slug='cons-b')
        self.ann_a = peupler(self.a, 'a', nb_vieilles=3, nb_recentes=2)
        self.ann_b = peupler(self.b, 'b', nb_vieilles=4, nb_recentes=1)

    def test_simulation_rien_supprime_compte_exact(self):
        self.assertEqual(vc.purger_extraits(MAINTENANT, apply_=False), 7)
        self.assertEqual(
            VeillePubVue.objects.exclude(extrait='').count(), 10)

    def test_reel_seules_les_vieilles_de_la_societe_visee(self):
        n = vc.purger_extraits(MAINTENANT, apply_=True, company=self.a)
        self.assertEqual(n, 3)
        vides = VeillePubVue.objects.filter(extrait='', legende='')
        self.assertEqual(vides.count(), 3)
        self.assertEqual(set(vides.values_list('company_id', flat=True)),
                         {self.a.id})
        # agrégats et verdicts gardés
        self.ann_a.refresh_from_db()
        self.assertEqual(self.ann_a.extraits[0]['texte'], 'gardé')
        self.assertIsNotNone(self.ann_a.verdict_courant_id)
        # second passage : plus rien à purger pour A
        self.assertEqual(
            vc.purger_extraits(MAINTENANT, apply_=False, company=self.a), 0)

    def test_politique_enregistree_dans_core_retention(self):
        from core.retention import list_retention_policies
        self.assertIn(vc.NOM_POLITIQUE, list_retention_policies())
        self.assertEqual(vc.politique_retention(MAINTENANT, False), 7)


class VeillePurgerCommandeTests(TestCase):
    def setUp(self):
        self.a = Company.objects.create(nom='A', slug='purg-a')
        self.b = Company.objects.create(nom='B', slug='purg-b')
        peupler(self.a, 'a', 1, 1)
        peupler(self.b, 'b', 2, 0)

    def test_simulation_comptes_sans_suppression(self):
        sortie = StringIO()
        call_command('veille_purger', '--company', str(self.a.id),
                     '--simulation', stdout=sortie)
        self.assertIn('pubs_vues : 2 → 2', sortie.getvalue())
        self.assertEqual(VeillePubVue.objects.filter(company=self.a).count(),
                         2)

    def test_reel_efface_tout_de_la_societe_autre_intacte(self):
        avant_b = vc.compter_societe(self.b.id)
        sortie = StringIO()
        call_command('veille_purger', '--company', str(self.a.id),
                     stdout=sortie)
        self.assertIn('pubs_vues : 2 → 0', sortie.getvalue())
        self.assertEqual(vc.compter_societe(self.a.id), {
            'decouvertes': 0, 'requetes': 0, 'pubs_vues': 0,
            'annonceurs': 0, 'verdicts': 0})
        self.assertEqual(vc.compter_societe(self.b.id), avant_b)
