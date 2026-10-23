# -*- coding: utf-8 -*-
"""CIQ120 — devis automatique commercial / industriel par le serveur.

``build_devis_auto`` accepte commercial et industriel (origine « auto ») :
``etudier_ci`` → taille retenue → composition du moteur → devis brouillon →
étude v2 écrite une fois. PVGIS simulé (table vendorisée de Casablanca).

Run :
    powershell -File scripts/test-backend.ps1 -RestoreDb \\
        -Modules "apps.ventes.tests.test_ciq120_devis_auto_ci"
"""
from decimal import Decimal
from unittest import mock

from django.contrib.auth import get_user_model
from django.test import TestCase

from apps.calepinage.models import ProfilTypeConsommation
from apps.crm.models import Lead
from apps.stock.models import FicheTechnique, Produit
from apps.ventes import tarif_ci
from apps.ventes.domain import etude_ci
from apps.ventes.models import Devis
from apps.ventes.services import AutoDevisError, build_devis_auto
from apps.ventes.tests.test_ciq118_etude_ci_preview import _production_casablanca
from authentication.models import Company

User = get_user_model()


class _Base(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.co = Company.objects.get_or_create(
            slug='ciq120-co', defaults={'nom': 'CIQ120 Co'})[0]
        cls.panneau = Produit.objects.create(
            company=cls.co, nom='Panneau 710W', prix_vente=Decimal('1272.73'),
            prix_achat=Decimal('800'))
        FicheTechnique.objects.create(
            company=cls.co, produit=cls.panneau, type_fiche='module',
            pmax_wc=Decimal('710'), vmp_v=Decimal('40'), voc_v=Decimal('48'),
            isc_a=Decimal('18'), imp_a=Decimal('17'))
        cls.onduleur = Produit.objects.create(
            company=cls.co, nom='Onduleur réseau Huawei 50kW Triphasé',
            prix_vente=Decimal('45833.33'), prix_achat=Decimal('30000'),
            role_devis='onduleur_reseau', garantie='10 ans constructeur')
        FicheTechnique.objects.create(
            company=cls.co, produit=cls.onduleur, type_fiche='onduleur',
            ond_ac_kw=Decimal('50'), ond_phases=3, ond_n_mppt=4,
            ond_mppt_v_min=Decimal('200'), ond_mppt_v_max=Decimal('1000'),
            ond_v_max_abs=Decimal('1100'), ond_i_max_mppt_a=Decimal('30'),
            ond_rendement_euro_pct=Decimal('98.4'))
        cls.structure = Produit.objects.create(
            company=cls.co, nom='Structure bac acier C&I', prix_vente=Decimal('300'),
            prix_achat=Decimal('150'), role_ci='structure_ci', type_pose='bac_acier')

    def setUp(self):
        patcher = mock.patch.object(etude_ci, 'lire_production',
                                    side_effect=_production_casablanca)
        patcher.start()
        self.addCleanup(patcher.stop)
        self.user = User.objects.create_user(
            username='ciq120_user', password='x', role_legacy='responsable',
            company=self.co)

    def _lead(self, **kw):
        kw.setdefault('type_installation', 'commercial')
        kw.setdefault('ville', 'Casablanca')
        kw.setdefault('categorie_commerciale', 'bureau')
        kw.setdefault('tension_raccordement', 'bt')
        kw.setdefault('raccordement', 'triphase')
        kw.setdefault('type_toiture', 'bac_acier')
        return Lead.objects.create(company=self.co, nom='Pro CIQ120', **kw)

    def _auto(self, lead):
        # Le lead ne porte aucune colonne « contrat d'électricité » : sans tarif
        # sourcé, aucune économie n'est chiffrée. Le test fixe la grille
        # officielle (BT patenté, MT général) — jamais un prix plat.
        with mock.patch.object(tarif_ci, 'tarif_applicable', side_effect=_tarif_grille):
            return build_devis_auto(lead=lead, user=self.user, company=self.co)


_TARIF_APPLICABLE = tarif_ci.tarif_applicable


def _tarif_grille(tarif_declare, *, tension=None, millesime=2026):
    contrat = 'mt_general' if tension == 'mt' else 'bt_patente'
    return _TARIF_APPLICABLE({'contrat': contrat}, tension=tension, millesime=millesime)


class DevisAutoCITests(_Base):
    def test_lead_commercial_complet_devis_brouillon(self):
        lead = self._lead(conso_mensuelle_kwh=Decimal('6000'))
        devis = self._auto(lead)
        self.assertEqual(devis.statut, Devis.Statut.BROUILLON)
        self.assertEqual(devis.mode_installation, 'commercial')
        produits = set(devis.lignes.values_list('produit_id', flat=True))
        self.assertIn(self.panneau.id, produits)
        self.assertIn(self.onduleur.id, produits)
        self.assertIn(self.structure.id, produits)
        noms = ' '.join(devis.lignes.values_list('designation', flat=True)).lower()
        self.assertNotIn('hybride', noms)
        self.assertNotIn('batterie', noms)
        etude = devis.etude_params['etude_ci']
        for cle in ('entrees_resolues', 'profil_charge', 'production', 'taille',
                    'bilan', 'alertes', 'hypotheses', 'version', 'empreinte'):
            self.assertIn(cle, etude)
        self.assertIn('production_figee', devis.etude_params)

    def test_lead_mt_tension_stockee(self):
        lead = self._lead(conso_mensuelle_kwh=Decimal('20000'), type_installation='industriel',
                          tension_raccordement='mt', categorie_commerciale=None,
                          jours_ouverture=[1, 2, 3, 4, 5, 6], heure_debut=7, heure_fin=19)
        devis = self._auto(lead)
        self.assertEqual(devis.etude_params['tension'], 'mt')

    def test_lead_sans_consommation_422_nomme_le_champ(self):
        lead = self._lead()
        avant = Devis.objects.filter(company=self.co).count()
        with self.assertRaises(AutoDevisError) as ctx:
            self._auto(lead)
        self.assertEqual(ctx.exception.field, 'conso_mensuelle_kwh')
        self.assertEqual(Devis.objects.filter(company=self.co).count(), avant)

    def test_structure_sans_prix_422_prix_a_renseigner(self):
        Produit.objects.filter(pk=self.structure.pk).update(prix_vente=0)
        lead = self._lead(conso_mensuelle_kwh=Decimal('6000'))
        with self.assertRaises(AutoDevisError) as ctx:
            self._auto(lead)
        self.assertIn('Prix à renseigner', ctx.exception.message)
        self.assertEqual(ctx.exception.field, 'composition')

    def test_type_du_lead_inchange(self):
        lead = self._lead(conso_mensuelle_kwh=Decimal('6000'))
        self._auto(lead)
        lead.refresh_from_db()
        self.assertEqual(lead.type_installation, 'commercial')

    def test_tunnel_refuse_pour_le_ci(self):
        lead = self._lead(conso_mensuelle_kwh=Decimal('6000'))
        with self.assertRaises(AutoDevisError) as ctx:
            build_devis_auto(lead=lead, user=self.user, company=self.co, origine='tunnel')
        self.assertEqual(ctx.exception.field, 'type_installation')

    # ── ADEV76 : les refus nomment un CHAMP DU LEAD ─────────────────────────

    def _refus(self, lead, *, reel=False):
        avant = Devis.objects.filter(company=self.co).count()
        with self.assertRaises(AutoDevisError) as ctx:
            if reel:
                build_devis_auto(lead=lead, user=self.user, company=self.co)
            else:
                self._auto(lead)
        self.assertEqual(Devis.objects.filter(company=self.co).count(), avant)
        return ctx.exception

    def test_lead_1637_sans_rythme_ni_categorie_ni_contrat_nomme_le_contrat(self):
        lead = self._lead(conso_mensuelle_kwh=Decimal('10000'), facture_hiver=Decimal('18000'),
                          categorie_commerciale=None, surface_toiture_m2=Decimal('200'))
        erreur = self._refus(lead, reel=True)
        self.assertEqual(erreur.field, 'contrat_electricite')

    def test_sans_categorie_ni_heures_nomme_les_jours_puis_les_heures(self):
        lead = self._lead(conso_mensuelle_kwh=Decimal('6000'), categorie_commerciale=None)
        self.assertEqual(self._refus(lead).field, 'jours_ouverture')
        lead = self._lead(conso_mensuelle_kwh=Decimal('6000'), categorie_commerciale=None,
                          jours_ouverture=[1, 2, 3, 4, 5])
        erreur = self._refus(lead)
        self.assertEqual(erreur.field, 'heure_debut')
        self.assertIn("Heures d'ouverture", erreur.message)

    def test_facture_mad_seule_sans_contrat_nomme_le_contrat(self):
        lead = self._lead(facture_hiver=Decimal('3500'))
        erreur = self._refus(lead, reel=True)
        self.assertEqual(erreur.field, 'contrat_electricite')
        self.assertIn('Facture en MAD sans contrat', erreur.message)

    def test_profil_societe_dune_autre_categorie_jamais_retenu(self):
        ProfilTypeConsommation.objects.create(
            company=self.co, cle='hotel', libelle='Hôtel relevé', famille='commercial',
            provenance='relevé hôtel 2025', courbe={'annuel': [0] * 8 + [10] * 10 + [0] * 6})
        devis = self._auto(self._lead(conso_mensuelle_kwh=Decimal('6000')))
        archetype = devis.etude_params['etude_ci']['profil_charge']['archetype']
        self.assertEqual(archetype['cle'], 'bureau')
        self.assertNotEqual(archetype['source'], 'relevé hôtel 2025')

    def test_profil_societe_industriel_sur_le_secteur_declare_seulement(self):
        ProfilTypeConsommation.objects.create(
            company=self.co, cle='textile', libelle='Tissage relevé', famille='industriel',
            provenance='relevé tissage 2025', courbe={'annuel': [1] * 6 + [10] * 14 + [1] * 4})
        commun = dict(type_installation='industriel', categorie_commerciale=None,
                      conso_mensuelle_kwh=Decimal('20000'))
        devis = self._auto(self._lead(secteur_industriel='textile', **commun))
        self.assertEqual(devis.etude_params['etude_ci']['profil_charge']['archetype']['cle'],
                         'textile')
        erreur = self._refus(self._lead(secteur_industriel='agroalimentaire',
                                        jours_ouverture=[1, 2, 3, 4, 5, 6], **commun))
        self.assertEqual(erreur.field, 'heure_debut')

    # ── ADEV78 : refus sur toute alerte bloquante, vraie cause nommée ──────

    def test_onduleurs_ineligibles_refus_composition_nommant_les_onduleurs(self):
        lead = self._lead(conso_mensuelle_kwh=Decimal('6000'), raccordement='monophase')
        erreur = self._refus(lead)
        self.assertEqual(erreur.field, 'composition')
        self.assertIn('Aucun onduleur C&I éligible', erreur.message)
        self.assertIn(self.onduleur.nom, erreur.message)
        self.assertNotIn('rentable', erreur.message)

    def test_module_sans_pmax_refus_aucun_devis(self):
        FicheTechnique.objects.filter(produit=self.panneau).update(pmax_wc=None)
        erreur = self._refus(self._lead(conso_mensuelle_kwh=Decimal('6000')))
        self.assertEqual(erreur.field, 'composition')
        self.assertIn('Pmax', erreur.message)

    def test_taille_saisie_onduleurs_infaisables_refusee(self):
        lead = self._lead(conso_mensuelle_kwh=Decimal('6000'), raccordement='monophase',
                          taille_souhaitee_kwc=Decimal('20'))
        self.assertEqual(self._refus(lead).field, 'composition')

    def test_module_a_puissance_publiee_prefere_au_module_tarife_sans_pmax(self):
        Produit.objects.filter(pk=self.panneau.pk).update(prix_vente=0)
        Produit.objects.create(company=self.co, nom='Panneau sans fiche 700W',
                               prix_vente=Decimal('1000'), prix_achat=Decimal('600'),
                               role_devis='panneau')
        module = etude_ci.lire_catalogue_ci(self.co)['module']
        self.assertEqual(module['produit'], self.panneau.id)
        self.assertEqual(module['pmax_wc'], 710)

    def test_agricole_tunnel_toujours_refuse(self):
        # AGR124 — l'agricole est ouvert au bouton (origine « auto ») ; le
        # tunnel du site, lui, reste refusé.
        lead = self._lead(type_installation='agricole', conso_mensuelle_kwh=Decimal('6000'))
        with self.assertRaises(AutoDevisError) as ctx:
            build_devis_auto(lead=lead, user=self.user, company=self.co,
                             origine='tunnel')
        self.assertEqual(ctx.exception.field, 'type_installation')
