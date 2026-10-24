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
from apps.parametres.models import CompanyProfile
from apps.stock.models import FicheTechnique, Produit
from apps.ventes import tarif_ci
from apps.ventes.domain import etude_ci
from apps.ventes.models import Devis
from apps.ventes.services import AutoDevisError, build_devis_auto
from apps.ventes.tests.test_ciq118_etude_ci_preview import _production_casablanca
from authentication.models import Company

User = get_user_model()
FORFAITS_TEST = ('etudes_ingenierie', 'pose_structure', 'pose_modules', 'raccordement_ac',
                 'mise_en_service', 'dossier_raccordement', 'levage_acces', 'transport_ci')


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
        # ADEV79 (D-ACI-6=a) — un poste fixe sans prix fait refuser : le cas
        # « complet » porte ses coffrets, protection, comptage, logger et
        # forfaits de prestations TARIFÉS.
        for role, nom, prix in (('coffret_dc', 'Coffret DC C&I', '1500'),
                                ('coffret_ac', 'Coffret AC C&I', '2500'),
                                ('compteur_injection', 'Smart Meter C&I', '1800'),
                                ('logger_supervision', 'Logger C&I', '2200')):
            Produit.objects.create(company=cls.co, nom=nom, prix_vente=Decimal(prix),
                                   prix_achat=Decimal('100'), role_ci=role)
        cls.disjoncteur = Produit.objects.create(
            company=cls.co, nom='Disjoncteur AC 80 A 4P', prix_vente=Decimal('900'),
            prix_achat=Decimal('400'), role_ci='protection_ac')
        FicheTechnique.objects.create(
            company=cls.co, produit=cls.disjoncteur, type_fiche='protection',
            prot_type='disjoncteur', prot_cote='ac', prot_calibre_a=80, prot_poles=4)
        CompanyProfile.objects.update_or_create(company=cls.co, defaults={'forfaits_ci': {
            cle: {'fixe_ht': '500', 'par_kwc_ht': '50', 'source': 'grille CIQ120 de test'}
            for cle in FORFAITS_TEST}})

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
        kw.setdefault('raccordement', 'triphase')  # ADEV89 — phase du site
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

    def test_phase_inconnue_refus_nomme_le_raccordement(self):
        # ADEV89 — la phase du site est un prérequis du moteur C&I : « je ne
        # sais pas » (ou vide) refuse en nommant `raccordement`, rien n'est créé.
        for phase in ('inconnu', ''):
            lead = self._lead(conso_mensuelle_kwh=Decimal('6000'), raccordement=phase)
            avant = Devis.objects.filter(company=self.co).count()
            with self.assertRaises(AutoDevisError) as ctx:
                self._auto(lead)
            self.assertEqual(ctx.exception.field, 'raccordement', phase)
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
        erreur = self._refus(lead)
        self.assertEqual(erreur.field, 'jours_ouverture')
        # ALEA54 — une consigne à la commerciale, pas le jargon du moteur.
        self.assertTrue(erreur.message.startswith('Demandez au client quels jours'))
        lead = self._lead(conso_mensuelle_kwh=Decimal('6000'), categorie_commerciale=None,
                          jours_ouverture=[1, 2, 3, 4, 5])
        erreur = self._refus(lead)
        self.assertEqual(erreur.field, 'heure_debut')
        self.assertIn("heures d'ouverture", erreur.message)
        self.assertTrue(erreur.message.startswith('Demandez au client'))
        for jargon in ('profil', 'archétype', 'sourcé', 'sur le lead'):
            self.assertNotIn(jargon, erreur.message)

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
        # ADEV86 (D-ACI-3=b) — le refus dit la cause de phase.
        self.assertIn('aucun onduleur C&I monophasé éligible', erreur.message)

    # ── ADEV86 (D-ACI-3=b) : le C&I s'ouvre au monophasé ───────────────────

    def _onduleur_mono(self):
        onduleur = Produit.objects.create(
            company=self.co, nom='Onduleur réseau Huawei 10kW Monophasé',
            prix_vente=Decimal('9000'), prix_achat=Decimal('6000'),
            role_devis='onduleur_reseau', garantie='10 ans constructeur')
        FicheTechnique.objects.create(
            company=self.co, produit=onduleur, type_fiche='onduleur',
            ond_ac_kw=Decimal('10'), ond_phases=1, ond_n_mppt=2,
            ond_mppt_v_min=Decimal('90'), ond_mppt_v_max=Decimal('550'),
            ond_v_max_abs=Decimal('600'), ond_i_max_mppt_a=Decimal('20'),
            ond_rendement_euro_pct=Decimal('97.8'))
        disjoncteur = Produit.objects.create(
            company=self.co, nom='Disjoncteur AC 50 A 2P', prix_vente=Decimal('350'),
            prix_achat=Decimal('150'), role_ci='protection_ac')
        FicheTechnique.objects.create(
            company=self.co, produit=disjoncteur, type_fiche='protection',
            prot_type='disjoncteur', prot_cote='ac', prot_calibre_a=50, prot_poles=2)
        return onduleur, disjoncteur

    def test_lead_mono_onduleur_mono_brouillon(self):
        onduleur, disjoncteur = self._onduleur_mono()
        lead = self._lead(conso_mensuelle_kwh=Decimal('1500'), raccordement='monophase')
        devis = self._auto(lead)
        self.assertEqual(devis.statut, Devis.Statut.BROUILLON)
        produits = set(devis.lignes.values_list('produit_id', flat=True))
        self.assertIn(onduleur.id, produits)
        self.assertNotIn(self.onduleur.id, produits)  # jamais un triphasé
        self.assertIn(disjoncteur.id, produits)       # disjoncteur bipolaire
        self.assertNotIn(self.disjoncteur.id, produits)
        noms = ' '.join(devis.lignes.values_list('designation', flat=True)).lower()
        self.assertNotIn('triphas', noms)

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

    # ── ADEV79 : postes fixes sans prix refusés, lignes de visite hors total ─

    def test_forfaits_vides_refus_nommant_les_prestations_et_parametres(self):
        CompanyProfile.objects.filter(company=self.co).update(forfaits_ci={})
        erreur = self._refus(self._lead(conso_mensuelle_kwh=Decimal('6000')))
        self.assertEqual(erreur.field, 'composition')
        self.assertIn('Études et ingénierie C&I', erreur.message)
        self.assertIn('Pose des modules C&I', erreur.message)
        self.assertIn('Paramètres › Devis › Prestations C&I', erreur.message)

    def test_coffret_ac_sans_prix_refus(self):
        Produit.objects.filter(company=self.co, role_ci='coffret_ac').update(prix_vente=0)
        erreur = self._refus(self._lead(conso_mensuelle_kwh=Decimal('6000')))
        self.assertEqual(erreur.field, 'composition')
        self.assertIn('Coffret AC C&I', erreur.message)

    def test_type_de_toit_inconnu_brouillon_sous_reserve_sans_structure(self):
        lead = self._lead(conso_mensuelle_kwh=Decimal('6000'), type_toiture=None)
        journal = {}
        with mock.patch.object(tarif_ci, 'tarif_applicable', side_effect=_tarif_grille):
            devis = build_devis_auto(lead=lead, user=self.user, company=self.co,
                                     journal_auto=journal)
        produits = set(devis.lignes.values_list('produit_id', flat=True))
        self.assertNotIn(self.structure.id, produits)
        self.assertIn(self.panneau.id, produits)
        etude = devis.etude_params['etude_ci']
        self.assertIn('Structure C&I', etude['composition']['a_chiffrer_visite'])
        self.assertIn('Câble solaire DC', etude['composition']['a_chiffrer_visite'])
        self.assertEqual(etude['taille']['statut'], 'estimation')
        self.assertTrue(journal['alertes'])
        self.assertIn('Structure C&I', ' '.join(a['message'] for a in journal['alertes']))
        # Persistance : rouvert, le brouillon relit la même liste.
        relu = Devis.objects.get(pk=devis.pk).etude_params['etude_ci']['composition']
        self.assertEqual(relu['a_chiffrer_visite'], etude['composition']['a_chiffrer_visite'])

    def test_agricole_tunnel_toujours_refuse(self):
        # AGR124 — l'agricole est ouvert au bouton (origine « auto ») ; le
        # tunnel du site, lui, reste refusé.
        lead = self._lead(type_installation='agricole', conso_mensuelle_kwh=Decimal('6000'))
        with self.assertRaises(AutoDevisError) as ctx:
            build_devis_auto(lead=lead, user=self.user, company=self.co,
                             origine='tunnel')
        self.assertEqual(ctx.exception.field, 'type_installation')


class ReponseAutoALEA51Tests(_Base):
    """ALEA51 — ``POST /ventes/devis/auto/`` rend de quoi dire le SUCCÈS :
    ``total_ttc``, ``economie_an_1_ht``, ``retour_ans`` (null si
    l'investissement est incomplet) et ``postes_apres_visite`` — lus du devis
    créé (aucun recalcul, aucun statut touché)."""

    URL = '/api/django/ventes/devis/auto/'

    def _post(self, lead):
        from rest_framework.test import APIClient
        api = APIClient()
        api.force_authenticate(user=self.user)
        with mock.patch.object(tarif_ci, 'tarif_applicable', side_effect=_tarif_grille):
            return api.post(self.URL, {'lead': lead.id}, format='json')

    def test_reponse_dit_total_economie_retour_et_postes_apres_visite(self):
        from apps.ventes.economie_ci import economie_ci_pour_devis
        lead = self._lead(conso_mensuelle_kwh=Decimal('6000'), type_toiture=None)
        rep = self._post(lead)
        self.assertEqual(rep.status_code, 201, rep.data)
        devis = Devis.objects.get(pk=rep.data['id'])
        self.assertEqual(devis.statut, Devis.Statut.BROUILLON)
        self.assertEqual(rep.data['total_ttc'], float(devis.total_ttc))
        self.assertGreater(rep.data['total_ttc'], 0)
        self.assertIn('Structure C&I', rep.data['postes_apres_visite'])
        self.assertEqual(
            rep.data['postes_apres_visite'],
            devis.etude_params['etude_ci']['composition']['a_chiffrer_visite'])
        with mock.patch.object(tarif_ci, 'tarif_applicable', side_effect=_tarif_grille):
            bloc = economie_ci_pour_devis(devis, self.co)
        self.assertEqual(rep.data['economie_an_1_ht'],
                         (bloc.get('economie_annee1') or {}).get('total_mad'))
        self.assertEqual(rep.data['retour_ans'],
                         (bloc.get('indicateurs') or {}).get('retour_ans'))

    def test_rejeu_200_porte_les_memes_champs(self):
        lead = self._lead(conso_mensuelle_kwh=Decimal('6000'))
        premiere = self._post(lead)
        rejeu = self._post(lead)
        self.assertEqual(premiere.status_code, 201, premiere.data)
        self.assertEqual(rejeu.status_code, 200, rejeu.data)
        for cle in ('total_ttc', 'economie_an_1_ht', 'retour_ans',
                    'postes_apres_visite'):
            self.assertIn(cle, rejeu.data)
            self.assertEqual(rejeu.data[cle], premiere.data[cle])
