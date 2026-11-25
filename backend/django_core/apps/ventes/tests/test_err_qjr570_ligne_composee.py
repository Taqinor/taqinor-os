"""ERR-QJR570 (D-QJR5-4) — la PROVENANCE d'une ligne (composée par le moteur /
ajoutée à la main) survit à l'enregistrement.

Une recomposition (Auto-remplir / Appliquer cette taille / Recalculer)
remplace les lignes posées par le moteur et garde celles que le vendeur a
ajoutées à la main. Sans marqueur PERSISTANT, un produit ajouté à la main,
enregistré puis rouvert, était pris pour une ligne composée et remplacé.
``LigneDevis.ligne_composee`` : True (moteur) / False (main) / None (inconnue).

Run :
    powershell -File scripts/test-backend.ps1 -RestoreDb \
        -Modules "apps.ventes.tests.test_err_qjr570_ligne_composee"
"""
from decimal import Decimal
from types import SimpleNamespace

from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from apps.stock.models import Produit
from apps.ventes.domain.lignes import CHAMPS_CLONES, CHAMPS_LIGNE
from testkit.factories import (
    CompanyFactory, DevisFactory, ProduitFactory, UserFactory,
)

COMPO_URL = '/api/django/ventes/devis/composition/'

#: Le kit minimal qui compose (même catalogue que STKCAT7).
CATALOGUE = [
    ('Panneau Canadien Solar 710W', '1450'),
    ('Onduleur réseau Huawei 5kW Monophasé', '14000'),
    ('Onduleur hybride Deye 5kW Monophasé', '17000'),
    ('Structures acier', '500'),
    ('Structures aluminium', '850'),
    ('Socles', '80'),
    ('Transport', '1000'),
]


class _Base(TestCase):

    def setUp(self):
        self.company = CompanyFactory()
        self.user = UserFactory(company=self.company, role_legacy='admin')
        self.api = APIClient()
        self.api.credentials(
            HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(self.user)}')
        self.produit = ProduitFactory(company=self.company)
        self.devis = DevisFactory(company=self.company)


class ReplaceLinesPersisteLaProvenance(_Base):

    def _ligne(self, **extra):
        corps = {'produit': self.produit.id, 'quantite': '1',
                 'prix_unitaire': '1000'}
        corps.update(extra)
        return corps

    def _replace(self, lignes):
        return self.api.post(
            f'/api/django/ventes/devis/{self.devis.id}/replace-lines/',
            {'lignes': lignes}, format='json')

    def test_true_false_none_persistent(self):
        r = self._replace([
            self._ligne(ordre=0, ligne_composee=True),
            self._ligne(ordre=1, ligne_composee=False),
            self._ligne(ordre=2),                       # absente ⇒ None
            self._ligne(ordre=3, ligne_composee=None),
        ])
        self.assertEqual(r.status_code, 200, r.content)
        valeurs = list(self.devis.lignes.order_by('ordre')
                       .values_list('ligne_composee', flat=True))
        self.assertEqual(valeurs, [True, False, None, None])

    def test_la_lecture_sert_la_provenance(self):
        r = self._replace([self._ligne(ordre=0, ligne_composee=False)])
        self.assertEqual(r.status_code, 200, r.content)
        lu = self.api.get(f'/api/django/ventes/devis/{self.devis.id}/')
        self.assertEqual(lu.status_code, 200, lu.content)
        self.assertIs(lu.data['lignes'][0]['ligne_composee'], False)

    def test_une_chaine_false_n_est_pas_lue_comme_composee(self):
        r = self._replace([self._ligne(ordre=0, ligne_composee='false')])
        self.assertEqual(r.status_code, 200, r.content)
        self.assertIs(self.devis.lignes.get().ligne_composee, False)

    def test_une_section_reste_sans_provenance(self):
        r = self._replace([
            {'type_ligne': 'section', 'designation': 'Stockage', 'ordre': 0,
             'ligne_composee': None},
            self._ligne(ordre=1, ligne_composee=True),
        ])
        self.assertEqual(r.status_code, 200, r.content)
        section = self.devis.lignes.get(type_ligne='section')
        self.assertIsNone(section.ligne_composee)


class LaCopieReprendLaProvenance(_Base):

    def test_le_champ_est_dans_les_jeux_de_champs(self):
        self.assertIn('ligne_composee', CHAMPS_LIGNE)
        self.assertIn('ligne_composee', CHAMPS_CLONES)

    def test_cloner_devis_copie_le_champ(self):
        from apps.ventes.domain.creation_clone import cloner_devis
        from apps.ventes.domain.lignes import creer_ligne

        for ordre, provenance in enumerate((True, False, None)):
            creer_ligne(
                self.devis, produit=self.produit, designation='L%d' % ordre,
                quantite=Decimal('1'), prix_unitaire=Decimal('1000'),
                remise=Decimal('0'), ordre=ordre, ligne_composee=provenance)
        copie = cloner_devis(self.devis, user=self.user)
        self.assertEqual(
            list(copie.lignes.order_by('ordre')
                 .values_list('ligne_composee', flat=True)),
            [True, False, None])

    def test_le_modele_de_devis_capture_le_champ(self):
        from apps.ventes.domain.creation_clone import save_devis_as_preset
        from apps.ventes.domain.lignes import creer_ligne

        creer_ligne(
            self.devis, produit=self.produit, designation='Ajout main',
            quantite=Decimal('1'), prix_unitaire=Decimal('1000'),
            remise=Decimal('0'), ordre=0, ligne_composee=False)
        preset = save_devis_as_preset(self.devis, 'Provenance')
        self.assertIs(preset.lignes_snapshot[0]['ligne_composee'], False)


class LeMoteurPoseTrue(_Base):

    def test_ecrire_lignes_d_une_composition_pose_true(self):
        from apps.ventes.domain.pipeline import ecrire_lignes

        spec = SimpleNamespace(
            produit=self.produit, designation=self.produit.nom,
            quantite=Decimal('1'), prix_unitaire=Decimal('1000'),
            variante='')
        ecrire_lignes(self.devis, [spec], company=self.company)
        self.assertIs(self.devis.lignes.get().ligne_composee, True)

    def test_ecrire_lignes_d_un_dict_ecran_garde_sa_provenance(self):
        from apps.ventes.domain.pipeline import ecrire_lignes

        ecrire_lignes(self.devis, [{
            'produit': self.produit.id, 'quantite': '1',
            'prix_unitaire': '1000', 'ligne_composee': False,
        }], company=self.company)
        self.assertIs(self.devis.lignes.get().ligne_composee, False)

    def test_le_dry_run_de_composition_rend_true(self):
        for nom, prix in CATALOGUE:
            Produit.objects.create(
                company=self.company, nom=nom, prix_vente=Decimal(prix),
                prix_achat=Decimal('1'), quantite_stock=1000)
        r = self.api.post(COMPO_URL, {
            'kwc': 5, 'panel_watt': 710, 'scenario': 'sans',
        }, format='json')
        self.assertEqual(r.status_code, 200, r.data)
        self.assertTrue(r.data['lignes'])
        for ligne in r.data['lignes']:
            self.assertIs(ligne['ligne_composee'], True, ligne)


# ── T4-X6-012 — des lignes COMPOSÉES enregistrées depuis l'écran sont une retouche ──

def _lignes_de_l_option(devis, option):
    """Les lignes d'UNE option (désignation, quantité, prix, produit), dans l'ordre."""
    return [(li.designation, li.quantite, li.prix_unitaire, li.produit_id)
            for li in devis.lignes.filter(variante=option).order_by('ordre', 'pk')]


def _corps_de_l_ecran(devis, *, retouche_panneaux, quantite_manuelle):
    """Le corps de ``replace-lines`` que l'écran envoie (``lignesEcranVersPayload``) pour
    les lignes en base, la ligne panneau de l'option ``retouche_panneaux`` portée à +2 :
    verrou de quantité posé (case tapée) ou non (nombre de panneaux recomposé, provenance
    « composée » gardée)."""
    lignes, retouchee = [], False
    for ordre, li in enumerate(devis.lignes.select_related('produit').order_by('ordre', 'pk')):
        if li.type_ligne != 'produit':
            lignes.append({'type_ligne': li.type_ligne, 'ordre': ordre, 'designation': li.designation,
                           'ligne_composee': None})
            continue
        quantite, manuelle = li.quantite, li.quantite_manuelle
        if not retouchee and li.variante == retouche_panneaux and 'panneau' in li.designation.lower():
            quantite, manuelle, retouchee = li.quantite + 2, quantite_manuelle, True
        lignes.append({
            'produit': li.produit_id, 'designation': li.designation, 'quantite': str(quantite),
            'prix_unitaire': str(li.prix_unitaire), 'remise': str(li.remise or 0), 'taux_tva': str(li.taux_tva),
            'groupe_index': None, 'groupe_label': '', 'optionnelle': li.optionnelle, 'type_ligne': 'produit',
            'ordre': ordre, 'variante': li.variante or '', 'prix_manuel': li.prix_manuel,
            'quantite_manuelle': manuelle, 'role_devis': li.role_devis or '', 'lot': None,
            'ligne_composee': li.ligne_composee, 'tva_base_legale': li.tva_base_legale or ''})
    assert retouchee, "aucune ligne panneau dans l'option %s" % retouche_panneaux
    return {'lignes': lignes}


class EnregistrerUneRetoucheCiTests(TestCase):
    """T4-X6-012 — un brouillon C&I « Les deux » né d'une conception ; la consommation du
    lead change (v2) ; le vendeur retouche le nombre de panneaux à l'écran et « Enregistre »
    (replace-lines, comme l'écran) : l'option avec batterie ne bouge pas, ni après les tâches
    mises en file ni au suivi d'une version rangée plus tard ; la mise à jour est PROPOSÉE.
    Fabriques du module de la conception, empruntées à l'appel (jamais importées au niveau
    du module : le chargeur rejouerait leurs tests)."""

    @staticmethod
    def _tcl():
        from apps.ventes.tests import test_conception_lead as tcl
        return tcl

    def setUp(self):
        from unittest import mock

        from django.core.cache import cache

        from apps.ventes import tasks
        self._tcl().FigeageDevisAutoTests.setUp(self)
        cache.clear()
        self.addCleanup(cache.clear)
        patcher = mock.patch.object(tasks.task_suivre_la_conception, 'apply_async')  # jamais le courtier réel
        self.suivi = patcher.start()
        self.addCleanup(patcher.stop)

    def __getattr__(self, nom):
        # Les fabriques ``_cas`` / ``_ci`` / ``_patcher`` / ``_utilisateur`` / ``_relancer`` / ``_api``.
        tcl = self._tcl()
        for classe in (tcl.FigeageDevisAutoTests, tcl.RelanceConceptionTests, tcl.ServirConceptionTests):
            for porteur in classe.__mro__:
                if nom.startswith('_') and nom in porteur.__dict__ and callable(porteur.__dict__[nom]):
                    return porteur.__dict__[nom].__get__(self)
        raise AttributeError(nom)

    def _enregistrer_une_retouche_ci(self, verrou):
        from apps.crm.models import Lead
        from apps.ventes import tasks
        from apps.ventes.conception.brouillons import brouillons_a_mettre_a_jour, suivre_la_conception
        from apps.ventes.models import Devis
        from apps.ventes.services import build_devis_auto

        tcl = self._tcl()
        company, lead = self._cas('ci_commercial_deux_options')
        tcl._reglages_de_la_societe(company)
        user = self._utilisateur(company)
        with self.captureOnCommitCallbacks(execute=True):
            devis = build_devis_auto(lead=lead, user=user, company=company)
        self.assertEqual(sorted({li.variante for li in devis.lignes.all()} - {''}), ['avec', 'sans'])
        Lead.objects.filter(pk=lead.pk).update(conso_mensuelle_kwh=Decimal('14000'))
        lead.refresh_from_db()
        v2 = self._relancer(lead, company, tcl._declencheur('lead_entrees_modifiees')).conception
        self.assertGreater(v2.version, devis.conception_source['version'])
        avec_avant = _lignes_de_l_option(devis, 'avec')
        corps = _corps_de_l_ecran(devis, retouche_panneaux='sans', quantite_manuelle=verrou)
        self.suivi.reset_mock()
        with self.captureOnCommitCallbacks(execute=True):
            reponse = self._api(user).post('/api/django/ventes/devis/%d/replace-lines/' % devis.pk,
                                           corps, format='json')
        self.assertEqual(reponse.status_code, 200, reponse.content[:300])
        for appel in self.suivi.call_args_list:
            tasks.task_suivre_la_conception(**appel.kwargs['kwargs'])
        # Le suivi qu'une version rangée plus tard met en file (relance de la lecture, autre
        # onglet) : mutant « aucun marqueur à l'enregistrement » : l'option avec recomposée.
        self.assertEqual(suivre_la_conception(v2), [])
        self.assertEqual(_lignes_de_l_option(Devis.objects.get(pk=devis.pk), 'avec'), avec_avant)
        self.assertIn(devis.pk, [b['devis'] for b in brouillons_a_mettre_a_jour(company.pk, lead.pk, v2.version)])

    def test_x6_012_retouche_ci_case_quantite_tapee(self):
        self._enregistrer_une_retouche_ci(True)

    def test_x6_012_retouche_ci_nombre_de_panneaux_recompose(self):
        self._enregistrer_une_retouche_ci(False)


class MarquerRetoucheSousVerrouTests(TestCase):
    """T4-X6-012 / check_read_modify_write — ``marquer_retouche_ecran`` relit le statut
    sous le verrou de la ligne : un devis parti (envoyé en base) alors que l'instance
    en mémoire dit encore « brouillon » n'est ni marqué ni dit marqué."""

    def _devis(self):
        return DevisFactory(company=CompanyFactory(), conception_source={'version': 1})

    def test_brouillon_marque(self):
        from apps.ventes.conception.brouillons import CLE_RETOUCHE_ECRAN, marquer_retouche_ecran
        devis = self._devis()
        self.assertTrue(marquer_retouche_ecran(devis, [('autre',)]))
        devis.refresh_from_db()
        self.assertIs(devis.conception_source.get(CLE_RETOUCHE_ECRAN), True)
        self.assertEqual(devis.statut, 'brouillon')

    def test_devis_parti_en_base_jamais_marque(self):
        from apps.ventes.conception.brouillons import CLE_RETOUCHE_ECRAN, marquer_retouche_ecran
        from apps.ventes.models import Devis
        devis = self._devis()
        Devis.objects.filter(pk=devis.pk).update(statut='envoye')
        self.assertEqual(devis.statut, 'brouillon')  # l'instance périmée
        self.assertFalse(marquer_retouche_ecran(devis, [('autre',)]))
        self.assertNotIn(CLE_RETOUCHE_ECRAN, devis.conception_source)
        devis.refresh_from_db()
        self.assertEqual((devis.statut, devis.conception_source), ('envoye', {'version': 1}))

    def test_pointeur_change_entre_temps_jamais_ecrase(self):
        """Un suivi de la conception committe un nouveau pointeur (v2) après la lecture
        de l'instance (encore v1) : le marquage garde v2, jamais l'ancien pointeur."""
        from apps.ventes.conception.brouillons import CLE_RETOUCHE_ECRAN, marquer_retouche_ecran
        from apps.ventes.models import Devis
        devis = self._devis()
        Devis.objects.filter(pk=devis.pk).update(conception_source={'version': 2})
        self.assertEqual(devis.conception_source, {'version': 1})  # l'instance périmée
        self.assertTrue(marquer_retouche_ecran(devis, [('autre',)]))
        attendu = {'version': 2, CLE_RETOUCHE_ECRAN: True}
        self.assertEqual(devis.conception_source, attendu)
        devis.refresh_from_db()
        self.assertEqual(devis.conception_source, attendu)
