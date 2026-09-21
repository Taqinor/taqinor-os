"""CAD134 — la même phrase du client vaut le même score des deux côtés.

Audit L3 du 21/09/2026, section CAD-K. Depuis le site, « je veux démarrer
immédiatement » devenait ``project_timeline='immediat'`` et valait +8 au
score ; depuis un formulaire Meta, « le plus tôt possible » ne devenait
qu'une ``priorite='haute'`` — absente de ``compute_score``, donc ZÉRO point,
aucune remontée dans la file, aucun changement d'heure ni de canal.

Ce fichier verrouille la convergence et ses garde-fous :

  * un formulaire Meta portant une intention de délai écrit
    ``project_timeline``, et le score bouge ;
  * la ``priorite`` reste posée comme avant — c'est le drapeau du commercial,
    rien n'est retiré ;
  * un libellé NON reconnu ne pose RIEN : on ne devine pas un délai, qui
    vaudrait des points ;
  * et un délai déjà saisi (site, ou à la main) n'est jamais écrasé par un
    mot-clé lu sur du texte libre.
"""
from django.test import SimpleTestCase, TestCase

from authentication.models import Company

from apps.crm import services
from apps.crm.models import Lead
from apps.crm.scoring import compute_score


def _champ(nom, valeur):
    return {'name': nom, 'values': [valeur]}


def _delai(valeur):
    return services._parse_meta_form_extras(
        [_champ('quand_souhaitez_vous_commencer_?', valeur)])


class ConversionTests(SimpleTestCase):
    """La table de mots-clés — pure, sans base."""

    def test_le_plus_tot_possible_devient_immediat(self):
        self.assertEqual(_delai('Le plus tôt possible')['project_timeline'],
                         Lead.ProjectTimeline.IMMEDIAT)

    def test_je_me_renseigne_devient_plus_tard(self):
        self.assertEqual(_delai('Je me renseigne')['project_timeline'],
                         Lead.ProjectTimeline.PLUS_TARD)

    def test_dans_trois_mois_est_reconnu(self):
        self.assertEqual(_delai('Dans 3 mois')['project_timeline'],
                         Lead.ProjectTimeline.MOINS_3_MOIS)

    def test_un_libelle_inconnu_ne_pose_rien(self):
        """On ne devine pas un délai : il vaudrait des points au score."""
        self.assertNotIn('project_timeline', _delai('Ça dépend du prix'))

    def test_la_priorite_est_toujours_posee(self):
        """Le drapeau du commercial n'est pas retiré au passage."""
        self.assertEqual(_delai('Le plus tôt possible')['priorite'],
                         Lead.Priorite.HAUTE)
        self.assertEqual(_delai('Je me renseigne')['priorite'],
                         Lead.Priorite.BASSE)
        self.assertEqual(_delai('Ça dépend du prix')['priorite'],
                         Lead.Priorite.NORMALE)

    def test_le_libelle_brut_reste_trace(self):
        """Un humain doit pouvoir relire ce que le client a coché."""
        extras = _delai('Le plus tôt possible')
        self.assertEqual(extras['delai_declare'], 'Le plus tôt possible')
        self.assertIn(('quand_souhaitez_vous_commencer_?',
                       'Le plus tôt possible'), extras['qa'])


class ScoreTests(TestCase):
    def setUp(self):
        self.company = Company.objects.create(
            nom='CAD134', slug='cad134')

    def test_le_score_bouge_sur_le_delai_declare(self):
        sans = Lead.objects.create(
            company=self.company, nom='Sans délai', telephone='0600000071')
        avec = Lead.objects.create(
            company=self.company, nom='Immédiat', telephone='0600000072',
            project_timeline=Lead.ProjectTimeline.IMMEDIAT)
        self.assertGreater(compute_score(avec), compute_score(sans))

    def test_enrichissement_ne_pose_le_delai_que_sil_est_vide(self):
        lead = Lead.objects.create(
            company=self.company, nom='Déjà saisi', telephone='0600000073',
            project_timeline=Lead.ProjectTimeline.MOINS_6_MOIS)
        extras = _delai('Le plus tôt possible')
        changed = services._apply_meta_form_extras(lead, extras)
        self.assertNotIn('project_timeline', changed)
        self.assertEqual(lead.project_timeline,
                         Lead.ProjectTimeline.MOINS_6_MOIS)

    def test_enrichissement_remplit_un_delai_absent(self):
        lead = Lead.objects.create(
            company=self.company, nom='Vide', telephone='0600000074')
        changed = services._apply_meta_form_extras(
            lead, _delai('Le plus tôt possible'))
        self.assertIn('project_timeline', changed)
        self.assertEqual(lead.project_timeline,
                         Lead.ProjectTimeline.IMMEDIAT)

    def test_un_libelle_inconnu_ne_touche_pas_au_lead(self):
        lead = Lead.objects.create(
            company=self.company, nom='Inconnu', telephone='0600000075')
        changed = services._apply_meta_form_extras(
            lead, _delai('Ça dépend du prix'))
        self.assertNotIn('project_timeline', changed)
        self.assertFalse(lead.project_timeline)
