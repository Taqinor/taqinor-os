"""AOF168 — rétention, DSR et purge des données d'appels d'offres.

Quatre promesses, et le test qui les tient :

  1. **Rien n'est purgé par défaut.** Chaque fenêtre vaut 0 = OFF. Une purge
     qui s'activerait toute seule à une mise à jour serait la pire régression
     possible de ce module.
  2. **Seuls les AO clos** (perdu / abandonné) voient leurs artefacts partir.
     Un marché GAGNÉ est en exécution : purger ses pièces, ce serait détruire
     les pièces d'un chantier en cours.
  3. **Aucune ligne métier ne disparaît** : le relevé garde sa date et son
     caractère contradictoire, la question garde son impact et sa décision, le
     plan source garde son calibrage. Seuls les FICHIERS partent.
  4. **L'effacement DSR ANONYMISE, il ne supprime pas** — et il ne touche
     jamais un chiffre : ni géométrie, ni compte, ni montant. Un droit à
     l'effacement n'est pas un droit de réécrire une offre.

Run :
    python manage.py test apps.ao.tests.test_retention_ao -v2
"""
from datetime import datetime, timedelta, timezone as tz_utc
from decimal import Decimal

from django.test import SimpleTestCase, TestCase, override_settings
from django.utils import timezone

from apps.ao import dsr as ao_dsr
from apps.ao import retention
from apps.ao.models import (
    AppelOffre, BatimentAO, PlanSource, QuestionAO, ReleveAO, SerieQuestions,
    ToitureAO,
)
from apps.records.models import Attachment
from authentication.models import Company


#: Instant FIXE : ces politiques reçoivent "maintenant" en paramètre et leur
#: fenêtre vaut 0, donc la valeur ne change rien au résultat attendu. On évite
#:  pour que le test ne dépende jamais de l'horloge (WOW/EZ).
INSTANT_FIXE = datetime(2026, 8, 1, 12, 0, tzinfo=tz_utc.utc)


def _company(slug):
    co, _ = Company.objects.get_or_create(slug=slug, defaults={'nom': slug})
    return co


class _Base(TestCase):
    def setUp(self):
        self.company = _company('aof168-co')
        self.now = timezone.now()
        self.vieux = self.now - timedelta(days=400)

    def _ao(self, reference, statut, *, ancien=True):
        ao = AppelOffre.objects.create(
            company=self.company, reference=reference, objet='PV',
            statut=statut)
        if ancien:
            AppelOffre.objects.filter(pk=ao.pk).update(
                date_creation=self.vieux)
            ao.refresh_from_db()
        return ao

    def _attachment(self, nom, cible=None):
        """Une pièce jointe ``records`` réelle (content_type + object_id)."""
        from django.contrib.contenttypes.models import ContentType

        cible = cible or AppelOffre.objects.filter(
            company=self.company).first()
        return Attachment.objects.create(
            company=self.company,
            content_type=ContentType.objects.get_for_model(type(cible)),
            object_id=cible.pk, file_key='ao/%s' % nom, filename=nom)


class RienNEstPurgeParDefaut(SimpleTestCase):
    def test_les_trois_fenetres_valent_zero(self):
        self.assertEqual(retention.DEFAULT_PHOTOS_RELEVE_PURGE_DAYS, 0)
        self.assertEqual(retention.DEFAULT_IMAGES_QUESTIONS_PURGE_DAYS, 0)
        self.assertEqual(retention.DEFAULT_PLANS_SOURCE_PURGE_DAYS, 0)

    def test_une_fenetre_a_zero_ne_purge_rien(self):
        for _nom, fonction, _reglage, _defaut in retention.POLITIQUES:
            self.assertEqual(fonction(INSTANT_FIXE, 0, apply_=True), 0)

    def test_un_marche_gagne_n_est_jamais_purgeable(self):
        self.assertNotIn('gagne', retention.STATUTS_PURGEABLES)
        self.assertEqual(sorted(retention.STATUTS_PURGEABLES),
                         ['abandonne', 'perdu'])


class LesPolitiquesSontEnregistreesDansLeRegistrePartage(TestCase):
    def test_les_trois_politiques_sont_dans_le_registre(self):
        from core.retention import list_retention_policies

        retention.register()
        enregistrees = list_retention_policies()
        for nom, _f, _r, _d in retention.POLITIQUES:
            self.assertIn(nom, enregistrees, nom)

    def test_l_enregistrement_est_idempotent(self):
        from core.retention import list_retention_policies

        retention.register()
        premier = list_retention_policies()
        retention.register()
        self.assertEqual(premier, list_retention_policies())

    def test_chaque_politique_respecte_le_contrat_du_registre(self):
        """``sweep(now, apply_) -> int``, dry-run par défaut."""
        from core.retention import _REGISTRY

        retention.register()
        for nom, _f, _r, _d in retention.POLITIQUES:
            self.assertEqual(_REGISTRY[nom](INSTANT_FIXE, False), 0)


class LesPhotosDeReleveNePartentQueSurUnAOClos(_Base):
    def _releve(self, ao, nb_photos=1):
        releve = ReleveAO.objects.create(
            company=self.company, appel_offre=ao,
            date_visite=self.vieux.date(), contradictoire=True,
            participants='M. Alami\nMme Bennani')
        for i in range(nb_photos):
            releve.photos.add(self._attachment('photo%d.jpg' % i))
        return releve

    def test_un_ao_perdu_voit_ses_photos_purgees(self):
        releve = self._releve(self._ao('AO-P', AppelOffre.Statut.PERDU))
        compte = retention.purger_photos_releve(self.now, 30, apply_=True)
        self.assertEqual(compte, 1)
        releve.refresh_from_db()
        self.assertEqual(releve.photos.count(), 0)
        self.assertEqual(Attachment.objects.count(), 0)

    def test_un_ao_gagne_garde_ses_photos(self):
        self._releve(self._ao('AO-G', AppelOffre.Statut.GAGNE))
        self.assertEqual(
            retention.purger_photos_releve(self.now, 30, apply_=True), 0)
        self.assertEqual(Attachment.objects.count(), 1)

    def test_un_ao_en_cours_garde_ses_photos(self):
        self._releve(self._ao('AO-E', AppelOffre.Statut.ETUDE))
        self.assertEqual(
            retention.purger_photos_releve(self.now, 30, apply_=True), 0)

    def test_un_ao_perdu_RECENT_garde_ses_photos(self):
        self._releve(self._ao('AO-R', AppelOffre.Statut.PERDU, ancien=False))
        self.assertEqual(
            retention.purger_photos_releve(self.now, 30, apply_=True), 0)

    def test_le_dry_run_compte_sans_rien_supprimer(self):
        releve = self._releve(self._ao('AO-D', AppelOffre.Statut.PERDU))
        self.assertEqual(
            retention.purger_photos_releve(self.now, 30, apply_=False), 1)
        releve.refresh_from_db()
        self.assertEqual(releve.photos.count(), 1)
        self.assertEqual(Attachment.objects.count(), 1)

    def test_le_releve_lui_meme_survit_a_la_purge(self):
        releve = self._releve(self._ao('AO-S', AppelOffre.Statut.PERDU))
        retention.purger_photos_releve(self.now, 30, apply_=True)
        releve.refresh_from_db()
        self.assertTrue(releve.contradictoire)
        self.assertEqual(releve.date_visite, self.vieux.date())
        self.assertIn('base : relevé contradictoire',
                      releve.mention_cartouche)


class LesImagesDeQuestionNePartentQueSurUnAOClos(_Base):
    def _question(self, ao):
        serie = SerieQuestions.objects.create(
            company=self.company, appel_offre=ao, numero=1,
            destinataire='M. Alami <alami@acheteur.ma>')
        return QuestionAO.objects.create(
            company=self.company, serie=serie, repere='A',
            texte='Le grand rectangle NÉANT est-il posable ?',
            image=self._attachment('annotee.png'),
            impact_min_modules=8, impact_max_modules=14,
            decision='Confirmé posable')

    def test_un_ao_perdu_voit_ses_images_purgees(self):
        question = self._question(self._ao('AO-QP', AppelOffre.Statut.PERDU))
        self.assertEqual(
            retention.purger_images_questions(self.now, 30, apply_=True), 1)
        question.refresh_from_db()
        self.assertIsNone(question.image_id)

    def test_la_question_garde_son_impact_et_sa_decision(self):
        question = self._question(self._ao('AO-QI', AppelOffre.Statut.PERDU))
        retention.purger_images_questions(self.now, 30, apply_=True)
        question.refresh_from_db()
        self.assertEqual(question.impact_min_modules, 8)
        self.assertEqual(question.impact_max_modules, 14)
        self.assertEqual(question.decision, 'Confirmé posable')

    def test_un_ao_gagne_garde_ses_images(self):
        self._question(self._ao('AO-QG', AppelOffre.Statut.GAGNE))
        self.assertEqual(
            retention.purger_images_questions(self.now, 30, apply_=True), 0)


class LesPlansSourcesRemontentParLesDeuxChemins(_Base):
    def _plan(self, ao, *, par_toiture):
        batiment = BatimentAO.objects.create(
            company=self.company, appel_offre=ao, code='A')
        if par_toiture:
            toiture = ToitureAO.objects.create(
                company=self.company, batiment=batiment, code_document='05H')
            return PlanSource.objects.create(
                company=self.company, toiture=toiture,
                attachment=self._attachment('plan.pdf'))
        return PlanSource.objects.create(
            company=self.company, batiment=batiment,
            attachment=self._attachment('plan.pdf'))

    def test_un_plan_rattache_par_la_toiture_est_purge(self):
        plan = self._plan(self._ao('AO-PT', AppelOffre.Statut.PERDU),
                          par_toiture=True)
        self.assertEqual(
            retention.purger_plans_source(self.now, 30, apply_=True), 1)
        plan.refresh_from_db()
        self.assertIsNone(plan.attachment_id)

    def test_un_plan_rattache_par_le_SEUL_batiment_est_purge_aussi(self):
        """Le piège : ``PlanSource`` n'a pas de FK vers l'appel d'offres."""
        plan = self._plan(self._ao('AO-PB', AppelOffre.Statut.ABANDONNE),
                          par_toiture=False)
        self.assertEqual(
            retention.purger_plans_source(self.now, 30, apply_=True), 1)
        plan.refresh_from_db()
        self.assertIsNone(plan.attachment_id)

    def test_le_plan_garde_son_empreinte_et_son_calibrage(self):
        plan = self._plan(self._ao('AO-PC', AppelOffre.Statut.PERDU),
                          par_toiture=True)
        PlanSource.objects.filter(pk=plan.pk).update(
            empreinte_sha256='abc123', echelle_m_par_px=Decimal('0.010000'))
        retention.purger_plans_source(self.now, 30, apply_=True)
        plan.refresh_from_db()
        self.assertEqual(plan.empreinte_sha256, 'abc123')


class LeFournisseurDSRExporteEtAnonymise(_Base):
    def setUp(self):
        super().setUp()
        self.ao = self._ao('AO-DSR', AppelOffre.Statut.DEPOSE, ancien=False)
        self.releve = ReleveAO.objects.create(
            company=self.company, appel_offre=self.ao,
            date_visite=self.now.date(), contradictoire=True,
            participants='M. Alami\nMme Bennani')
        self.serie = SerieQuestions.objects.create(
            company=self.company, appel_offre=self.ao, numero=1,
            destinataire='M. Alami <alami@acheteur.ma>')

    def test_l_export_retrouve_la_personne_par_son_nom(self):
        donnees = ao_dsr.export_ao(self.company, 'M. Alami')
        self.assertEqual(len(donnees['participations_releve']), 1)
        self.assertEqual(donnees['participations_releve'][0]['appel_offre'],
                         'AO-DSR')

    def test_l_export_retrouve_la_personne_par_son_email(self):
        donnees = ao_dsr.export_ao(self.company, 'alami@acheteur.ma')
        self.assertEqual(len(donnees['destinataire_de_series']), 1)

    def test_un_sujet_vide_ne_retourne_rien(self):
        """Un filtre absent ne doit jamais se muer en absence de filtre."""
        donnees = ao_dsr.export_ao(self.company, '')
        self.assertEqual(donnees['participations_releve'], [])
        self.assertEqual(donnees['destinataire_de_series'], [])

    def test_l_effacement_anonymise_sans_supprimer(self):
        compte = ao_dsr.erase_ao(self.company, 'M. Alami')
        self.assertEqual(compte, 2)
        self.releve.refresh_from_db()
        self.serie.refresh_from_db()
        self.assertEqual(ReleveAO.objects.count(), 1)
        self.assertEqual(SerieQuestions.objects.count(), 1)
        self.assertEqual(self.serie.destinataire, 'Anonymisé')
        self.assertIn('Anonymisé', self.releve.participants)

    def test_l_effacement_ne_touche_pas_les_autres_participants(self):
        ao_dsr.erase_ao(self.company, 'M. Alami')
        self.releve.refresh_from_db()
        self.assertIn('Mme Bennani', self.releve.participants)

    def test_l_effacement_garde_les_faits_opposables(self):
        ao_dsr.erase_ao(self.company, 'M. Alami')
        self.releve.refresh_from_db()
        self.serie.refresh_from_db()
        self.assertTrue(self.releve.contradictoire)
        self.assertEqual(self.releve.date_visite, self.now.date())
        self.assertEqual(self.serie.numero, 1)

    def test_l_effacement_ne_touche_aucun_montant(self):
        AppelOffre.objects.filter(pk=self.ao.pk).update(
            montant_offre_ht=Decimal('1250000.00'))
        ao_dsr.erase_ao(self.company, 'M. Alami')
        self.ao.refresh_from_db()
        self.assertEqual(self.ao.montant_offre_ht, Decimal('1250000.00'))

    def test_le_fournisseur_est_borne_a_la_societe(self):
        autre = _company('aof168-autre')
        self.assertEqual(ao_dsr.erase_ao(autre, 'M. Alami'), 0)
        self.serie.refresh_from_db()
        self.assertEqual(self.serie.destinataire,
                         'M. Alami <alami@acheteur.ma>')

    def test_le_fournisseur_est_enregistre_dans_le_registre_core(self):
        from core.dsr import list_dsr_providers

        ao_dsr.register()
        self.assertIn(ao_dsr.PROVIDER_NAME, list_dsr_providers())

    def test_le_lead_crm_n_est_pas_duplique_ici(self):
        """Deux effacements concurrents pour la même personne = un bug."""
        donnees = ao_dsr.export_ao(self.company, 'M. Alami')
        self.assertNotIn('leads', donnees)
        self.assertIn('crm', donnees['note_lead'])


class LePipelineDeSweepPasseSurLesPolitiquesAO(_Base):
    @override_settings(AO_PHOTOS_RELEVE_PURGE_DAYS=30)
    def test_le_reglage_fondateur_active_la_purge(self):
        from core.retention import _REGISTRY

        ao = self._ao('AO-SW', AppelOffre.Statut.PERDU)
        releve = ReleveAO.objects.create(
            company=self.company, appel_offre=ao,
            date_visite=self.vieux.date())
        releve.photos.add(self._attachment('p.jpg'))
        retention.register()
        self.assertEqual(_REGISTRY['ao_photos_releve'](self.now, True), 1)

    def test_sans_reglage_le_sweep_ne_supprime_rien(self):
        from core.retention import _REGISTRY

        ao = self._ao('AO-SW2', AppelOffre.Statut.PERDU)
        releve = ReleveAO.objects.create(
            company=self.company, appel_offre=ao,
            date_visite=self.vieux.date())
        releve.photos.add(self._attachment('p.jpg'))
        retention.register()
        self.assertEqual(_REGISTRY['ao_photos_releve'](self.now, True), 0)
        self.assertEqual(Attachment.objects.count(), 1)
