"""CAD105 — [TRANCHÉ 21/09/2026] la synchronisation Odoo démarre la cadence
des leads NEUFS.

Tout lead de source Odoo était écarté de la cadence automatique. C'est juste
pour le RATTRAPAGE historique (930 fiches rapatriées en une fois) et faux
pour un lead créé dans Odoo APRÈS la mise en service : Odoo reste le cockpit
où la commerciale travaille, et un dossier né là-bas mérite le même protocole
qu'un dossier né sur le site.

Décision fondateur : la synchronisation démarre la cadence pour les leads
NEUFS, **avec exactement les mêmes gardes que le site** — numéro exploitable,
pas de doublon, pas de « ne plus contacter », étape « Nouveau ». Le
rattrapage historique reste manuel, et son refus est tracé (CAD104).

GARDE-FOU, et c'est LE point : « neuf » se juge sur la date de création DANS
ODOO (`Lead.date_creation_origine`, CAD119), JAMAIS sur la date de
synchronisation — qui vaudrait « neuf » pour les 930 fiches du miroir.
Aucune cadence rétroactive.

La DATE DE BASCULE n'est pas choisie : c'est le jour où la synchronisation
Odoo→ERP est passée en production (01/09/2026), déjà daté dans l'en-tête de
`apps/crm/odoo_sync.py` et dans le libellé du modèle.
"""
import datetime

from django.contrib.auth import get_user_model
from django.test import TestCase

from authentication.models import Company

from apps.crm import odoo_sync, services, stages
from apps.crm.models import Lead, LeadActivity, RelanceEtape
from apps.crm.services import demarrer_cadence_contact
from apps.parametres.models import CompanyProfile
from apps.parametres.models_relance import CadenceRelanceEtape

User = get_user_model()

MOBILE = '+212661000002'
CASA = datetime.timezone(datetime.timedelta(hours=1))


def _le(jour, heure=10):
    """Un instant AWARE au jour dit (le fuseau exact n'a pas d'importance
    ici : la bascule se juge au JOUR local)."""
    return datetime.datetime(jour.year, jour.month, jour.day, heure, 0,
                             tzinfo=CASA)


class _Base(TestCase):
    slug = 'cad105'

    def setUp(self):
        self.company = Company.objects.create(
            nom='CAD105 Solaire', slug=f'{self.slug}-a')
        CompanyProfile.objects.get_or_create(company=self.company)
        CadenceRelanceEtape.seed_defaults(self.company)
        self.acteur = User.objects.create_user(
            username=f'{self.slug}-resp', password='x',
            role_legacy='responsable', company=self.company)

    def _lead_odoo(self, origine=None, **kw):
        champs = {'company': self.company, 'nom': 'Benali', 'prenom': 'Aziz',
                  'ville': 'Bouskoura', 'owner': self.acteur,
                  'telephone': MOBILE, 'stage': stages.NEW,
                  'source': Lead.Source.ODOO_IMPORT_TEST,
                  'date_creation_origine': origine}
        champs.update(kw)
        return Lead.objects.create(**champs)

    def _touches(self, lead):
        return RelanceEtape.objects.filter(lead=lead, cadence='contact')

    def _refus(self, lead):
        return [n for n in LeadActivity.objects.filter(lead=lead)
                if 'non initialisée' in (n.body or '')]


class UnLeadOdooNEUFDemarreTests(_Base):
    """Première moitié du « Done = »."""

    slug = 'cad105-neuf'

    def test_un_lead_ne_APRES_la_bascule_demarre_sa_cadence(self):
        lead = self._lead_odoo(origine=_le(
            odoo_sync.BASCULE_MIROIR + datetime.timedelta(days=10)))
        self.assertTrue(demarrer_cadence_contact(lead, user=self.acteur))
        self.assertGreater(self._touches(lead).count(), 0)
        self.assertFalse(self._refus(lead))

    def test_le_JOUR_de_la_bascule_compte_comme_neuf(self):
        lead = self._lead_odoo(origine=_le(odoo_sync.BASCULE_MIROIR))
        self.assertTrue(demarrer_cadence_contact(lead, user=self.acteur))

    def test_il_recoit_le_MEME_protocole_quun_lead_du_site(self):
        odoo = self._lead_odoo(origine=_le(
            odoo_sync.BASCULE_MIROIR + datetime.timedelta(days=10)))
        site = Lead.objects.create(
            company=self.company, nom='Site', prenom='Karim',
            ville='Bouskoura', owner=self.acteur, telephone='+212661000003',
            stage=stages.NEW, source=Lead.Source.SITE_WEB)
        demarrer_cadence_contact(odoo, user=self.acteur)
        demarrer_cadence_contact(site, user=self.acteur)
        self.assertEqual(self._touches(odoo).count(),
                         self._touches(site).count())


class LesMEMESGardesQueLeSiteTests(_Base):
    """« Avec exactement les mêmes gardes que le site. »"""

    slug = 'cad105-gardes'

    def _neuf(self, **kw):
        return self._lead_odoo(
            origine=_le(odoo_sync.BASCULE_MIROIR
                        + datetime.timedelta(days=10)), **kw)

    def test_sans_numero_exploitable_la_cadence_ne_part_pas(self):
        lead = self._neuf(telephone='', whatsapp='')
        self.assertEqual(demarrer_cadence_contact(lead, user=self.acteur), [])
        self.assertEqual(self._touches(lead).count(), 0)

    def test_un_lead_quon_ne_relance_plus_ne_part_pas(self):
        lead = self._neuf(ne_plus_contacter=True)
        self.assertEqual(demarrer_cadence_contact(lead, user=self.acteur), [])

    def test_un_lead_hors_etape_NOUVEAU_ne_part_pas(self):
        lead = self._neuf(stage=stages.CONTACTED)
        self.assertEqual(demarrer_cadence_contact(lead, user=self.acteur), [])

    def test_un_doublon_vivant_ne_part_pas(self):
        self._neuf(nom='Premier')
        double = self._neuf(nom='Second')
        self.assertEqual(demarrer_cadence_contact(double, user=self.acteur),
                         [])


class AucuneCadenceRETROACTIVETests(_Base):
    """Seconde moitié du « Done = », et le garde-fou de la décision."""

    slug = 'cad105-retro'

    def test_un_lead_ANTERIEUR_ne_demarre_pas_et_son_refus_est_TRACE(self):
        lead = self._lead_odoo(origine=_le(
            odoo_sync.BASCULE_MIROIR - datetime.timedelta(days=1)))
        self.assertEqual(demarrer_cadence_contact(lead, user=self.acteur), [])
        self.assertEqual(self._touches(lead).count(), 0)
        refus = self._refus(lead)
        self.assertEqual(len(refus), 1, [n.body for n in refus])
        self.assertIn('miroir Odoo', refus[0].body)

    def test_une_fiche_SANS_date_dorigine_nest_jamais_neuve(self):
        """On ne devine pas : sans date d'origine connue, c'est du
        rattrapage historique, et le placement manuel décide."""
        lead = self._lead_odoo(origine=None)
        self.assertFalse(odoo_sync.lead_odoo_neuf(lead))
        self.assertEqual(demarrer_cadence_contact(lead, user=self.acteur), [])

    def test_la_bascule_se_juge_sur_la_date_ODOO_jamais_sur_la_SYNCHRO(self):
        """LE garde-fou : `date_creation` est l'instant de synchronisation —
        il vaut « aujourd'hui » pour les 930 fiches du miroir. Une fiche née
        AVANT la bascule et synchronisée aujourd'hui reste historique."""
        lead = self._lead_odoo(origine=_le(
            odoo_sync.BASCULE_MIROIR - datetime.timedelta(days=200)))
        # Les deux dates DISENT deux choses différentes : `date_creation` est
        # l'instant de l'insertion ici (auto_now_add), `date_creation_origine`
        # celui de la naissance dans Odoo.
        self.assertNotEqual(lead.date_creation.date(),
                            lead.date_creation_origine.date())
        # C'est la SECONDE qui décide — et le lead n'est donc PAS neuf.
        self.assertFalse(odoo_sync.lead_odoo_neuf(lead))

    def test_la_garde_PURE_rend_le_bon_verdict_sans_ecrire(self):
        ancien = self._lead_odoo(origine=_le(
            odoo_sync.BASCULE_MIROIR - datetime.timedelta(days=1)))
        code, motif = services._garde_cadence_contact(ancien)
        self.assertEqual(code, 'miroir')
        self.assertIn('rattrapage historique', motif)
        self.assertFalse(self._refus(ancien))
        neuf = self._lead_odoo(
            nom='Neuf', telephone='+212661000004',
            origine=_le(odoo_sync.BASCULE_MIROIR
                        + datetime.timedelta(days=10)))
        self.assertIsNone(services._garde_cadence_contact(neuf))


class LaBasculeEstDateeTests(_Base):
    """Zéro chiffre inventé : la date vient de la mise en service."""

    slug = 'cad105-date'

    def test_la_bascule_est_le_jour_de_la_mise_en_service(self):
        self.assertEqual(odoo_sync.BASCULE_MIROIR,
                         datetime.date(2026, 9, 1))

    def test_une_source_qui_nest_pas_le_miroir_nest_jamais_neuve_par_ici(self):
        """`lead_odoo_neuf` ne parle QUE du miroir : un lead du site n'a pas
        besoin de cette porte, il passe par les gardes ordinaires."""
        site = Lead.objects.create(
            company=self.company, nom='Site', ville='Bouskoura',
            owner=self.acteur, telephone='+212661000005',
            stage=stages.NEW, source=Lead.Source.SITE_WEB,
            date_creation_origine=_le(
                odoo_sync.BASCULE_MIROIR + datetime.timedelta(days=10)))
        self.assertFalse(odoo_sync.lead_odoo_neuf(site))
        self.assertIsNone(services._garde_cadence_contact(site))
