"""QJR42 — ``EntreesMoteur`` : un dataclass, deux adaptateurs (lead / devis).

CE QUE CES TESTS TIENNENT. Avant QJR42 la MÊME fiche client était traduite en
entrées du moteur par DEUX codes différents : ``entrees_dimensionnement_du_devis``
(chemin devis) et le corps de ``_panneaux_dimensionnement_horaire`` (chemin
auto-devis / tunnel, qui part d'un lead). Deux lectures ⇒ deux dimensionnements
possibles pour le même client. Ces tests affirment que les deux adaptateurs
rendent la MÊME forme, clé pour clé, et les MÊMES valeurs pour un lead et le
devis qui en découle.

Fixtures calquées sur ``test_t5_dimensionnement_devis._DimensionnementBase``
(Casablanca, aucun accès réseau).

Lancer :
    docker compose exec django_core python manage.py test \
        apps.ventes.tests.test_qjr_entrees_moteur -v 2
"""
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase

from apps.crm.models import Client, Lead
from apps.ventes.domain.entrees import (
    EntreesMoteur, entrees_depuis_devis, entrees_depuis_lead,
)
from apps.ventes.models import Devis
from apps.ventes.services import entrees_dimensionnement_du_devis

User = get_user_model()

#: Les onze champs CANONIQUES du contrat QJR42 + les deux champs de contexte du
#: chemin devis. Ce pin rend visible tout élargissement de la forme.
CHAMPS_ATTENDUS = (
    'company', 'mode', 'etude_params',
    'conso_kwh_mensuelles', 'source_conso',
    'ville', 'lat', 'lon', 'occupation', 'equipements',
    'tranches', 'charges_fixes_mad', 'jour_reference',
)


class _EntreesBase(TestCase):
    def _company(self, slug):
        from authentication.models import Company
        company = Company.objects.get_or_create(
            slug=slug, defaults={'nom': slug})[0]
        User.objects.get_or_create(
            username=f'{slug}-user',
            defaults={'password': 'x', 'company': company})
        return company

    def _lead_et_devis(self, slug, *, mode='residentiel', facture_hiver=1800,
                       **champs_lead):
        company = self._company(slug)
        client_obj = Client.objects.get_or_create(
            company=company, nom=f'Client {slug}', defaults={})[0]
        lead = Lead.objects.create(
            company=company, nom='Lead', prenom=slug,
            telephone='+212600000000', ville='Casablanca',
            facture_hiver=facture_hiver, ete_differente=False, **champs_lead)
        devis = Devis.objects.create(
            company=company, reference=f'DEV-{slug.upper()}-01',
            client=client_obj, lead=lead, statut='brouillon',
            taux_tva=Decimal('20'), mode_installation=mode, etude_params={})
        return company, lead, devis


class FormeDuDataclassTests(_EntreesBase):
    """La forme est UNE, et elle est gelée."""

    def test_les_champs_sont_ceux_du_contrat(self):
        self.assertEqual(EntreesMoteur().keys(), CHAMPS_ATTENDUS)

    def test_le_dataclass_est_gele(self):
        entrees = EntreesMoteur(ville='Casablanca')
        with self.assertRaises(Exception):
            entrees.ville = 'Rabat'

    def test_acces_mapping_en_lecture(self):
        """Le pont de déplacement : les appelants historiques lisent par
        indice (``entrees['ville']``) — ils ne doivent pas être touchés."""
        entrees = EntreesMoteur(ville='Casablanca')
        self.assertEqual(entrees['ville'], 'Casablanca')
        self.assertEqual(entrees.get('lat'), None)
        self.assertEqual(entrees.get('inconnu', 'defaut'), 'defaut')
        self.assertIn('equipements', entrees)
        self.assertNotIn('inconnu', entrees)
        with self.assertRaises(KeyError):
            entrees['inconnu']

    def test_une_entree_reste_vraie_meme_vide(self):
        """``(entrees or {}).get(...)`` chez les appelants : un dataclass sans
        ``__len__`` est TOUJOURS vrai — ne jamais introduire ``__len__``."""
        self.assertTrue(EntreesMoteur())


class MemeFormeLeadEtDevisTests(_EntreesBase):
    """Les deux adaptateurs rendent la même forme ET les mêmes valeurs."""

    def test_les_deux_adaptateurs_rendent_les_memes_cles(self):
        company, lead, devis = self._lead_et_devis('qjr42-cles')
        depuis_lead = entrees_depuis_lead(lead, company)
        depuis_devis = entrees_depuis_devis(devis)
        self.assertEqual(depuis_lead.keys(), depuis_devis.keys())

    def test_memes_valeurs_pour_un_lead_et_son_devis(self):
        company, lead, devis = self._lead_et_devis('qjr42-valeurs')
        depuis_lead = entrees_depuis_lead(lead, company)
        depuis_devis = entrees_depuis_devis(devis)
        for champ in ('conso_kwh_mensuelles', 'source_conso', 'ville',
                      'lat', 'lon', 'occupation', 'equipements'):
            with self.subTest(champ=champ):
                self.assertEqual(depuis_lead[champ], depuis_devis[champ])
        self.assertEqual(depuis_lead.company, depuis_devis.company)
        self.assertEqual(depuis_lead.mode, depuis_devis.mode)

    def test_les_quinze_champs_equipement_arrivent_par_les_deux_chemins(self):
        """QJR9 — une grandeur L-BACK posée sur le lead compose une couche des
        DEUX côtés (c'est ce que la lecture unique garantit)."""
        company, lead, devis = self._lead_et_devis(
            'qjr42-equip', equip_chauffe_eau_electrique=True,
            equip_chauffe_eau_kw=Decimal('2'),
            equip_chauffe_eau_creneau='soir')
        depuis_lead = entrees_depuis_lead(lead, company)
        depuis_devis = entrees_depuis_devis(devis)
        self.assertEqual(depuis_lead.equipements, depuis_devis.equipements)
        self.assertIn('chauffe_eau', depuis_lead.equipements or {})

    def test_occupation_du_lead_prime_des_deux_cotes(self):
        company, lead, devis = self._lead_et_devis(
            'qjr42-occ', occupation_jour='absent')
        self.assertEqual(entrees_depuis_lead(lead, company).occupation,
                         entrees_depuis_devis(devis).occupation)


class GardesTests(_EntreesBase):
    """Les refus sont ceux d'avant, mot pour mot."""

    def test_devis_non_residentiel_rend_none(self):
        _company, _lead, devis = self._lead_et_devis(
            'qjr42-industriel', mode='industriel')
        self.assertIsNone(entrees_depuis_devis(devis))

    def test_devis_sans_societe_rend_none(self):
        _company, _lead, devis = self._lead_et_devis('qjr42-nosoc')
        devis.company = None
        self.assertIsNone(entrees_depuis_devis(devis))

    def test_lead_sans_societe_rend_none(self):
        _company, lead, _devis = self._lead_et_devis('qjr42-leadnosoc')
        self.assertIsNone(entrees_depuis_lead(lead, None))
        self.assertIsNone(entrees_depuis_lead(None, _company))

    def test_sans_facture_le_profil_est_none_mais_la_garde_passe(self):
        company, lead, devis = self._lead_et_devis(
            'qjr42-nofact', facture_hiver=None)
        depuis_devis = entrees_depuis_devis(devis)
        self.assertIsNotNone(depuis_devis)
        self.assertFalse(depuis_devis.conso_kwh_mensuelles)
        depuis_lead = entrees_depuis_lead(lead, company)
        self.assertIsNotNone(depuis_lead)
        self.assertFalse(depuis_lead.conso_kwh_mensuelles)


class ContexteFalseTests(_EntreesBase):
    """``contexte=False`` est CONSERVÉ : il saute les lectures de contexte."""

    def test_contexte_false_ne_lit_ni_localisation_ni_occupation(self):
        company, lead, devis = self._lead_et_devis('qjr42-ctx')
        garde = entrees_depuis_devis(devis, contexte=False)
        self.assertTrue(garde.conso_kwh_mensuelles)
        self.assertIsNone(garde.ville)
        self.assertIsNone(garde.occupation)
        self.assertIsNone(garde.equipements)
        garde_lead = entrees_depuis_lead(lead, company, contexte=False)
        self.assertIsNone(garde_lead.ville)
        self.assertIsNone(garde_lead.occupation)

    def test_contexte_true_les_lit(self):
        _company, _lead, devis = self._lead_et_devis('qjr42-ctx2')
        entrees = entrees_depuis_devis(devis)
        self.assertEqual(entrees.ville, 'Casablanca')
        self.assertIsNotNone(entrees.occupation)


class ReExportServicesTests(_EntreesBase):
    """``services.entrees_dimensionnement_du_devis`` reste le nom public."""

    def test_le_re_export_rend_la_meme_chose(self):
        _company, _lead, devis = self._lead_et_devis('qjr42-reexport')
        self.assertEqual(entrees_dimensionnement_du_devis(devis),
                         entrees_depuis_devis(devis))
        self.assertEqual(
            entrees_dimensionnement_du_devis(devis, contexte=False),
            entrees_depuis_devis(devis, contexte=False))

    def test_les_champs_tarifaires_sont_declares_mais_vides(self):
        """QJR46 les branchera : ici ils EXISTENT et valent None, pour que la
        forme ne change plus au milieu de la vague. ``jour_reference``, lui,
        est POSÉ dès QJR45 (frontière du pipeline = aujourd'hui)."""
        _company, _lead, devis = self._lead_et_devis('qjr42-tarif')
        entrees = entrees_depuis_devis(devis)
        self.assertIsNone(entrees.tranches)
        self.assertIsNone(entrees.charges_fixes_mad)
        self.assertIsNotNone(entrees.jour_reference)
