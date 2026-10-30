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
from django.test import TestCase, SimpleTestCase

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
from core.electrique.cables import SECTIONS_MM2_CI

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
        # Fondateur 26/10/2026 — câbles chiffrés d'office (devis préliminaire) :
        # câble DC et câbles AC de chaque section du moteur, tarifés.
        Produit.objects.create(company=cls.co, nom='Câble solaire 6 mm² (au mètre)',
                               prix_vente=Decimal('11'), prix_achat=Decimal('5'),
                               role_ci='cable_dc')
        for section in SECTIONS_MM2_CI:
            cable = Produit.objects.create(
                company=cls.co, nom='Câble AC cuivre 5×%g mm² (au mètre)' % section,
                prix_vente=Decimal(str(round(10 * section + 30, 2))),
                prix_achat=Decimal('1'), role_ci='cable_ac')
            FicheTechnique.objects.create(
                company=cls.co, produit=cable, type_fiche='cable', cable_cote='ac',
                cable_section_mm2=float(section), cable_ame='cu')
        cls.disjoncteur = Produit.objects.create(
            company=cls.co, nom='Disjoncteur AC 80 A 4P', prix_vente=Decimal('900'),
            prix_achat=Decimal('400'), role_ci='protection_ac')
        FicheTechnique.objects.create(
            company=cls.co, produit=cls.disjoncteur, type_fiche='protection',
            prot_type='disjoncteur', prot_cote='ac', prot_calibre_a=80, prot_poles=4)
        CompanyProfile.objects.update_or_create(company=cls.co, defaults={'forfaits_ci': {
            cle: {'fixe_ht': '500', 'par_kwc_ht': '50', 'source': 'grille CIQ120 de test'}
            for cle in FORFAITS_TEST}})
        # CORC6 — chaque prestation réglée a son article (rôle = clé du forfait),
        # comme le semis ``seed_catalogue`` (CI-ETUDES…CI-TRANSPORT).
        for cle in FORFAITS_TEST:
            Produit.objects.create(company=cls.co, nom='Prestation %s' % cle, role_ci=cle,
                                   prix_vente=Decimal('0'), prix_achat=Decimal('0'))

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

    # ADEV76 / CORC6 : un refus nommé, rien d'écrit (partagé par les classes).
    def _refus(self, lead, *, reel=False):
        avant = Devis.objects.filter(company=self.co).count()
        with self.assertRaises(AutoDevisError) as ctx:
            if reel:
                build_devis_auto(lead=lead, user=self.user, company=self.co)
            else:
                self._auto(lead)
        self.assertEqual(Devis.objects.filter(company=self.co).count(), avant)
        return ctx.exception


_TARIF_APPLICABLE = tarif_ci.tarif_applicable


def _tarif_grille(tarif_declare, *, tension=None, millesime=2026, **options):
    contrat = 'mt_general' if tension == 'mt' else 'bt_patente'
    return _TARIF_APPLICABLE({'contrat': contrat}, tension=tension, millesime=millesime, **options)


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
        # Fondateur 26/10/2026 — le marqueur interne « C&I » n'est jamais lu
        # par le client (« Coffret DC C&I » → « Coffret DC »).
        self.assertNotIn('c&i', noms)
        self.assertIn('coffret dc', noms)
        etude = devis.etude_params['etude_ci']
        for cle in ('entrees_resolues', 'profil_charge', 'production', 'taille',
                    'bilan', 'alertes', 'hypotheses', 'version', 'empreinte'):
            self.assertIn(cle, etude)
        self.assertIn('production_figee', devis.etude_params)

    def _toit_plat(self):
        Produit.objects.create(company=self.co, nom='Structure toit plat lestée C&I',
                               prix_vente=Decimal('450'), prix_achat=Decimal('200'),
                               role_ci='structure_ci', type_pose='toit_plat_leste')
        FicheTechnique.objects.filter(produit=self.panneau).update(longueur_mm=2384, largeur_mm=1303)

    def test_r1_b1_verdict_toit_calcule_a_la_creation_relu_puis_pdf_commercial(self):
        # R1 (B1, arbitrage coordinatrice 28/10/2026) — cas NON aligné : 220 m²
        # de terrasse béton → contenance rasante 60 panneaux = 42,6 kWc, entre
        # les paliers 40 (57 panneaux = 40,47) et 45 : le balayage retient
        # 40,47 kWc, raison « toit », à 2,13 kWc de la contenance — qu'aucune
        # heuristique « à un panneau près » ne retrouverait. Le verdict CALCULÉ
        # part avec le devis (`taille_creation_ci`), le rafraîchisseur (taille
        # des LIGNES) le relit, le builder le sert, le gabarit COMMERCIAL l'imprime.
        from apps.ventes.quote_engine.builder import build_quote_data
        from apps.ventes.quote_engine.commercial import render as c_render
        from apps.ventes.quote_engine.commercial import renderer as c_renderer
        self._toit_plat()
        lead = self._lead(conso_mensuelle_kwh=Decimal('10000'), type_toiture='terrasse_beton',
                          surface_toiture_m2=Decimal('220'))
        devis = self._auto(lead)
        verdict = devis.etude_params[etude_ci.CLE_TAILLE_CREATION]
        self.assertEqual((verdict['raison_arret'], verdict['inclinaison_retenue_deg']), ('toit', 10))
        self.assertEqual((verdict['retenue_kwc'], verdict['nb_panneaux']), (40.47, 57))
        self.assertEqual((verdict['toit']['kwc_30'], verdict['toit']['kwc_10']), (21.3, 42.6))
        phrase = 'taille limitée par le toit : 220 m² déclarés → 40.47 kWc en pose rasante'
        self.assertEqual(verdict['taille_limitee_toit'], phrase)
        taille = devis.etude_params['etude_ci']['taille']
        self.assertEqual((taille['raison_arret'], taille['retenue_kwc'], taille['nb_panneaux']),
                         ('taille_explicite', 40.47, 57))
        self.assertEqual((taille['inclinaison_retenue_deg'], taille['taille_limitee_toit']), (10, phrase))
        self.assertEqual(devis.etude_params['etude_ci']['production']['inclinaison_deg'], 10)
        data = build_quote_data(devis, {})
        self.assertEqual(data['etude']['etude_ci']['taille']['taille_limitee_toit'], phrase)
        html = c_render.build_html(c_renderer._augment(data))
        self.assertIn('Taille limitée par le toit', html)
        self.assertIn('220&#160;m² déclarés → 40,47&#160;kWc en pose rasante', html)
        self.assertNotIn('prix_achat', html)
        # Les lignes changent (50 panneaux) : le verdict ne décrit plus les
        # lignes → la phrase disparaît, la taille suit les lignes.
        ligne = devis.lignes.get(produit=self.panneau)
        ligne.quantite = Decimal('50')
        ligne.save()
        etude_ci.rafraichir_etude_ci_devis(devis, force=True)
        devis.refresh_from_db()
        taille = devis.etude_params['etude_ci']['taille']
        self.assertEqual((taille['retenue_kwc'], taille['taille_limitee_toit']), (35.5, None))
        self.assertIn(etude_ci.CLE_TAILLE_CREATION, devis.etude_params)   # jamais effacé, juste inerte

    def test_r1_b1_taille_souhaitee_egale_a_la_contenance_jamais_limitee_par_le_toit(self):
        # B1 — une taille SAISIE (lead : 35 kWc → 50 panneaux = 35,5 kWc, pile
        # la contenance rasante de 200 m²) : l'économie n'a pas été balayée →
        # aucun verdict stocké, jamais « limitée par le toit ».
        self._toit_plat()
        lead = self._lead(conso_mensuelle_kwh=Decimal('10000'), type_toiture='terrasse_beton',
                          surface_toiture_m2=Decimal('200'), taille_souhaitee_kwc=Decimal('35'))
        devis = self._auto(lead)
        self.assertNotIn(etude_ci.CLE_TAILLE_CREATION, devis.etude_params)
        taille = devis.etude_params['etude_ci']['taille']
        self.assertEqual((taille['retenue_kwc'], taille['nb_panneaux'], taille['inclinaison_retenue_deg']),
                         (35.5, 50, 10))
        self.assertIsNone(taille['taille_limitee_toit'])
        self.assertEqual(taille['bornes']['toit']['kwc_10'], 35.5)

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

    def test_type_de_toit_inconnu_structure_et_cables_chiffres_d_office(self):
        # Fondateur 26/10/2026 — jamais de prix vide : toit inconnu ⇒ structure
        # chiffrée (toit plat lesté, sinon la structure tarifée du catalogue),
        # câbles DC/AC estimés ; aucun poste « à chiffrer après la visite ».
        lead = self._lead(conso_mensuelle_kwh=Decimal('6000'), type_toiture=None)
        with mock.patch.object(tarif_ci, 'tarif_applicable', side_effect=_tarif_grille):
            devis = build_devis_auto(lead=lead, user=self.user, company=self.co)
        produits = set(devis.lignes.values_list('produit_id', flat=True))
        self.assertIn(self.structure.id, produits)
        self.assertIn(self.panneau.id, produits)
        noms = ' '.join(devis.lignes.values_list('designation', flat=True)).lower()
        self.assertIn('câble solaire', noms)
        self.assertIn('câble ac', noms)
        etude = devis.etude_params['etude_ci']
        self.assertEqual(etude['composition']['a_chiffrer_visite'], [])

    def test_agricole_tunnel_toujours_refuse(self):
        # AGR124 — l'agricole est ouvert au bouton (origine « auto ») ; le
        # tunnel du site, lui, reste refusé.
        lead = self._lead(type_installation='agricole', conso_mensuelle_kwh=Decimal('6000'))
        with self.assertRaises(AutoDevisError) as ctx:
            build_devis_auto(lead=lead, user=self.user, company=self.co,
                             origine='tunnel')
        self.assertEqual(ctx.exception.field, 'type_installation')


def _hybride(co, nom, kw, prix, v_min, v_max, port):
    produit = Produit.objects.create(company=co, nom=nom, prix_vente=Decimal(prix),
                                     prix_achat=Decimal('1000'), role_devis='onduleur_hybride')
    FicheTechnique.objects.create(
        company=co, produit=produit, type_fiche='onduleur', ond_ac_kw=Decimal(kw), ond_phases=3,
        ond_n_mppt=2, ond_mppt_v_min=Decimal('160'), ond_mppt_v_max=Decimal('650'),
        ond_v_max_abs=Decimal('800'), ond_i_max_mppt_a=Decimal('20'),
        ond_bat_v_min=Decimal(v_min), ond_bat_v_max=Decimal(v_max),
        ond_bat_max_charge_kw=Decimal(port))
    return produit


def _batterie(co, nom, utile, prix, charge_kw):
    produit = Produit.objects.create(company=co, nom=nom, prix_vente=Decimal(prix),
                                     prix_achat=Decimal('1000'), role_devis='batterie')
    FicheTechnique.objects.create(
        company=co, produit=produit, type_fiche='batterie', bat_kwh_usable=Decimal(utile),
        bat_v_nominal=Decimal('51.2'), bat_max_charge_kw=Decimal(charge_kw),
        bat_rendement_ar_pct=Decimal('98'))
    return produit


def _semer_batterie(cible):
    """Hybrides Deye BT/HT, batteries Dyness et disjoncteurs de sortie
    (attributs posés sur ``cible`` : classe de test ou instance)."""
    # Prix SEEDÉS (seed_catalogue, TTC → HT 20 %) ; PowerBrick : prix de TEST.
    co = cible.co
    cible.h10 = _hybride(co, 'Onduleur hybride Deye SUN-10K-SG05LP3', '10', '23333.33',
                         '40', '60', '10')
    cible.h15 = _hybride(co, 'Onduleur hybride Deye SUN-15K-SG05LP3', '15', '30000',
                         '40', '60', '14.34')
    cible.h20 = _hybride(co, 'Onduleur hybride Deye SUN-20K-SG05LP3', '20', '40000',
                         '40', '60', '17.92')
    cible.hv = _hybride(co, 'Onduleur hybride Deye SUN-30K-SG02HP3', '30', '20000',
                        '160', '700', '30')
    cible.b5 = _batterie(co, 'Batterie Dyness 5 kWh', '4.60', '11666.67', '3.84')
    cible.b10 = _batterie(co, 'Batterie Dyness 10 kWh', '9.22', '25000', '5.12')
    cible.b16 = _batterie(co, 'Batterie Dyness PowerBrick SC 16 kWh', '15.27', '40000',
                          '7.17')
    # Disjoncteurs de sortie des hybrides (calibres 16 / 20 / 25 / 32 / 40 A 4P).
    for calibre in (16, 20, 25, 32, 40):
        disj = Produit.objects.create(
            company=co, nom='Disjoncteur AC %d A 4P' % calibre, prix_vente=Decimal('400'),
            prix_achat=Decimal('100'), role_ci='protection_ac')
        FicheTechnique.objects.create(
            company=co, produit=disj, type_fiche='protection', prot_type='disjoncteur',
            prot_cote='ac', prot_calibre_a=calibre, prot_poles=4)


class RefusConsigneVendeurCorc3Tests(_Base):
    """CORC3 (27/10/2026) — un lead sans contrat d'électricité : le refus
    nomme le champ du lead et donne une CONSIGNE au vendeur, jamais le
    jargon du moteur (« Tarif non déclaré … économies non chiffrées »)."""

    def test_contrat_absent_consigne_vendeur(self):
        with self.assertRaises(AutoDevisError) as ctx:
            build_devis_auto(lead=self._lead(conso_mensuelle_kwh=Decimal('6000')),
                             user=self.user, company=self.co)
        erreur = ctx.exception
        self.assertEqual(erreur.field, 'contrat_electricite')
        self.assertTrue(erreur.message.startswith("Demandez au client son contrat"))
        self.assertNotIn('Tarif non déclaré', erreur.message)


class OptionBatterieCITests(_Base):
    """Fondateur 26/10/2026 — un devis C&I automatique porte DEUX options
    « sans » / « avec batterie » comme le résidentiel : hybrides Deye BASSE
    tension triphasés à la place des string, banque Dyness homogène ; le
    choix du lead restreint ; un hybride HAUTE tension n'entre jamais."""

    @classmethod
    def setUpTestData(cls):
        super().setUpTestData()
        _semer_batterie(cls)

    def _boulangerie(self, **kw):
        kw.setdefault('conso_mensuelle_kwh', Decimal('6000'))
        return self._lead(categorie_commerciale='boulangerie', jours_ouverture=list(range(1, 8)),
                          heure_debut=7, heure_fin=21, surface_toiture_m2=Decimal('200'), **kw)

    def _ids(self, devis, variante):
        return set(devis.lignes.filter(variante=variante).values_list('produit_id', flat=True))

    def test_boulangerie_deux_options_hybrides_bt_et_banque_dyness(self):
        devis = self._auto(self._boulangerie())
        self.assertEqual(devis.etude_params.get('scenario'), 'Les deux (Sans + Avec)')
        # CORC9 — CIQ302 : l'offre réseau est mise en avant (jamais « avec »).
        self.assertEqual(devis.etude_params.get('recommended_option'), 'Sans batterie')
        from apps.ventes.quote_engine.builder import build_quote_data
        self.assertEqual(build_quote_data(devis)['recommended'], 'Sans batterie')
        sans, avec = self._ids(devis, 'sans'), self._ids(devis, 'avec')
        self.assertIn(self.onduleur.id, sans)
        hybrides = {self.h10.id, self.h15.id, self.h20.id}
        self.assertTrue(avec & hybrides)
        self.assertNotIn(self.hv.id, avec | sans)
        batteries = avec & {self.b5.id, self.b10.id, self.b16.id}
        self.assertEqual(len(batteries), 1)            # banque HOMOGÈNE
        self.assertFalse((sans | self._ids(devis, '')) & (hybrides | batteries))
        option = devis.etude_params['etude_ci']['option_avec']
        self.assertGreater(option['economie_annuelle_mad'], 0)
        self.assertGreater(option['bilan']['batterie']['restitue_kwh_an'], 0)
        self.assertNotIn('prix_achat', str(option))
        from apps.ventes.quote_engine.builder import build_quote_data
        with mock.patch.object(tarif_ci, 'tarif_applicable', side_effect=_tarif_grille):
            data = build_quote_data(devis)
        self.assertTrue(data['deux_options'])
        self.assertEqual(data['option_servie'], 'sans')
        from apps.ventes.quote_engine.ci.mentions import valeur_option_avec
        valeur = valeur_option_avec(data)
        # CPDF2 — le retour imprimé est CELUI servi par l'étude (flux 25 ans,
        # ``option_avec.retour_simple_ans``), jamais un quotient recalculé ;
        # non servi (flux sans passage à zéro) ⇒ omis.
        servi = option.get('retour_simple_ans')
        self.assertEqual(valeur['retour_simple_ans'],
                         servi if servi and servi > 0 else None)
        self.assertIn('kWh utiles', valeur['textes']['fr'])

    def test_r1_b2_option_avec_des_lignes_dans_sa_pose_serie_rasante_figee(self):
        # R1 (B2, arbitrage coordinatrice) — l'option « avec » STOCKÉE (lignes,
        # rafraîchisseur) porte la pose qui LA loge ; quand « sans » reste à 30°
        # et « avec » passe en rasante, la série rasante est FIGÉE avec le devis
        # (`production_figee_rasante`) et un rafraîchissement forcé ne rappelle
        # pas PVGIS ; chaque option est une installation à part.
        Produit.objects.create(company=self.co, nom='Structure toit plat lestée C&I',
                               prix_vente=Decimal('450'), prix_achat=Decimal('200'),
                               role_ci='structure_ci', type_pose='toit_plat_leste')
        FicheTechnique.objects.filter(produit=self.panneau).update(longueur_mm=2384, largeur_mm=1303)
        devis = self._auto(self._lead(
            categorie_commerciale='boulangerie', jours_ouverture=list(range(1, 8)), heure_debut=7,
            heure_fin=21, conso_mensuelle_kwh=Decimal('6000'), type_toiture='terrasse_beton',
            surface_toiture_m2=Decimal('220')))
        params = devis.etude_params
        sans, avec = params['etude_ci']['taille'], params['etude_ci']['option_avec']
        toit = sans['bornes']['toit']
        self.assertEqual((toit['kwc_30'], toit['kwc_10']), (21.3, 42.6))
        self.assertIn(sans['inclinaison_retenue_deg'], (30, 10))
        attendu = 10 if avec['kwc'] > toit['kwc_30'] else 30
        self.assertEqual(avec['inclinaison_retenue_deg'], attendu)
        rasante_figee = sans['inclinaison_retenue_deg'] == 30 and attendu == 10
        self.assertEqual('production_figee_rasante' in params, rasante_figee)
        if rasante_figee:
            self.assertEqual(params['production_figee_rasante']['inclinaison_deg'], 10)
        with mock.patch.object(etude_ci, 'lire_production',
                               side_effect=_production_casablanca) as pvgis:
            etude_ci.rafraichir_etude_ci_devis(devis, force=True)
        pvgis.assert_not_called()
        devis.refresh_from_db()
        apres = devis.etude_params['etude_ci']['option_avec']
        self.assertEqual(apres['inclinaison_retenue_deg'], attendu)
        self.assertEqual(apres['bilan']['production_kwh'], avec['bilan']['production_kwh'])

    def test_choix_avec_du_lead_option_avec_seule(self):
        devis = self._auto(self._boulangerie(batterie_souhaitee='avec'))
        produits = set(devis.lignes.values_list('produit_id', flat=True))
        self.assertNotIn(self.onduleur.id, produits)
        self.assertTrue(produits & {self.b5.id, self.b10.id, self.b16.id})
        self.assertFalse(devis.lignes.exclude(variante='').exists())
        self.assertEqual(devis.etude_params.get('scenario'), 'Avec batterie')

    def test_choix_sans_du_lead_aucune_batterie(self):
        devis = self._auto(self._boulangerie(batterie_souhaitee='sans'))
        produits = set(devis.lignes.values_list('produit_id', flat=True))
        self.assertFalse(produits & {self.h10.id, self.h15.id, self.h20.id, self.b16.id,
                                     self.b10.id, self.b5.id})
        self.assertNotIn('option_avec', devis.etude_params['etude_ci'])

    def test_les_deux_batteries_sans_prix_offre_reseau_seule_alerte_interne(self):
        """Fondateur 27/10/2026 — « les deux » : aucune batterie tarifée ⇒ le
        devis part avec l'offre réseau seule, les batteries nommées en alerte
        interne ; jamais un refus."""
        Produit.objects.filter(pk__in=[self.b5.pk, self.b10.pk, self.b16.pk]).update(
            prix_vente=Decimal('0'))
        journal = {}
        with mock.patch.object(tarif_ci, 'tarif_applicable', side_effect=_tarif_grille):
            devis = build_devis_auto(lead=self._boulangerie(), user=self.user, company=self.co,
                                     journal_auto=journal)
        produits = set(devis.lignes.values_list('produit_id', flat=True))
        self.assertIn(self.onduleur.id, produits)
        self.assertFalse(produits & {self.b5.id, self.b10.id, self.b16.id, self.h10.id,
                                     self.h15.id, self.h20.id})
        self.assertFalse(devis.lignes.exclude(variante='').exists())
        self.assertNotIn('option_avec', devis.etude_params['etude_ci'])
        alerte = next(a for a in journal['alertes']
                      if a['code'] == 'OPTION_BATTERIE_PRIX_A_RENSEIGNER')
        self.assertIn('Batterie Dyness 10 kWh', alerte['message'])
        self.assertTrue(alerte['interne'])

    def test_batteries_sans_prix_refus_prix_a_renseigner_nommant_la_batterie(self):
        Produit.objects.filter(pk__in=[self.b5.pk, self.b10.pk, self.b16.pk]).update(
            prix_vente=Decimal('0'))
        with self.assertRaises(AutoDevisError) as ctx:
            self._auto(self._boulangerie(batterie_souhaitee='avec'))
        self.assertIn('Batterie Dyness 10 kWh', str(ctx.exception))


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
        self.assertEqual(rep.data['postes_apres_visite'], [])
        self.assertEqual(
            rep.data['postes_apres_visite'],
            devis.etude_params['etude_ci']['composition']['a_chiffrer_visite'])
        with mock.patch.object(tarif_ci, 'tarif_applicable', side_effect=_tarif_grille):
            bloc = economie_ci_pour_devis(devis, self.co)
        self.assertEqual(rep.data['economie_an_1_ht'],
                         (bloc.get('economie_annee1') or {}).get('total_mad'))
        # CE2E3 — le retour au dixième du PDF (CPDF7), plus l'entier servi.
        from apps.ventes.quote_engine.ci.couverture import retour_dixieme
        self.assertEqual(rep.data['retour_ans'], retour_dixieme(
            bloc, (bloc.get('indicateurs') or {}).get('retour_ans')))

    def test_retour_ans_egal_au_retour_imprime_du_pdf(self):
        """CE2E3 — la bannière dit le retour au dixième que le PDF imprime
        (``chiffres_cles.payback_ans``), jamais l'entier de l'indicateur."""
        from apps.ventes.quote_engine.builder import build_quote_data
        from apps.ventes.quote_engine.ci.synthese import chiffres_cles, synthese_ci
        rep = self._post(self._lead(conso_mensuelle_kwh=Decimal('15000')))
        self.assertEqual(rep.status_code, 201, rep.data)
        devis = Devis.objects.get(pk=rep.data['id'])
        with mock.patch.object(tarif_ci, 'tarif_applicable', side_effect=_tarif_grille):
            imprime = chiffres_cles(synthese_ci(build_quote_data(devis)))['payback_ans']
        self.assertIsNotNone(imprime)
        self.assertEqual(rep.data['retour_ans'], imprime)

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


class PostesNonChiffresUniques(SimpleTestCase):
    """C-L3-MOT-02 (24/10/2026) — les postes « après visite » et « prix à
    renseigner » sont listés UNE fois chacun : un câble AC ajouté au devis sous
    le nom de l'onduleur qu'il dessert multipliait la liste (une entrée par
    mètre de câble pris pour un onduleur)."""

    def test_designations_uniques_ordre_garde(self):
        from apps.ventes.moteur_ci.composition import postes_non_chiffres
        lignes = [{'designation': 'Câble AC X - TGBT', 'a_chiffrer_visite': True}] * 200
        lignes += [{'designation': 'Structure C&I', 'a_chiffrer_visite': True},
                   {'designation': 'Coffret DC', 'prix_connu': False},
                   {'designation': 'Coffret DC', 'prix_connu': False}]
        a_renseigner, visite = postes_non_chiffres(lignes)
        self.assertEqual(visite, ['Câble AC X - TGBT', 'Structure C&I'])
        self.assertEqual(a_renseigner, ['Coffret DC'])

    def test_un_cable_nomme_d_apres_l_onduleur_n_est_pas_un_onduleur(self):
        from apps.ventes.domain.catalogue import classer_produit
        from apps.stock.selectors import _role_ci_par_nom

        class _P:
            nom = 'Câble AC Onduleur réseau Huawei 150kW Triphasé - TGBT'
        self.assertEqual(classer_produit(_P.nom), 'cable_dc')
        self.assertIsNone(_role_ci_par_nom(_P()))
        self.assertEqual(classer_produit('Onduleur réseau Huawei 150kW Triphasé'), 'onduleur_reseau')


class DesignationOptionAvecTests(SimpleTestCase):
    """Le découpage des deux options du document lit les mots de la famille :
    un hybride ou une batterie nommés par leur seule référence la reçoivent."""

    def test_famille_ajoutee_au_nom_qui_ne_la_dit_pas(self):
        from apps.ventes.domain.etude_ci_batterie import designation_option_avec
        self.assertEqual(designation_option_avec('SUN-12K-SG05LP3', 'onduleur_hybride'),
                         'Onduleur hybride SUN-12K-SG05LP3')
        self.assertEqual(designation_option_avec('Onduleur hybride Deye 20kW', 'onduleur_hybride'),
                         'Onduleur hybride Deye 20kW')
        self.assertEqual(designation_option_avec('Dyness PowerBrick SC 16 kWh', 'batterie'),
                         'Batterie Dyness PowerBrick SC 16 kWh')


class RetourOptionAvecFluxTests(SimpleTestCase):
    """CMP6 — ``option_avec.retour_simple_ans`` est le retour lu sur le flux
    25 ans de ``flux_option_avec`` (dégradation, remplacement des hybrides et de
    la batterie), comparable à celui de l'option « sans » — plus le quotient
    coût ÷ économie an 1."""

    ECONOMIE_AN1 = 40000.0

    class _Valoriseur:
        def __init__(self, statut='calcule'):
            self.statut = statut

        def complet(self, bilan):
            return {'statut': self.statut, 'economie_annee1': {
                'total_mad': 40000.0, 'total_mad_ttc': 48000.0,
                'par_poste': [{'kwh_evites': 30000.0}]}}

    def _evaluation(self, incomplet=False):
        return {
            'kwc': 50, 'puissance_ac': 30, 'batterie': {'produit': 1},
            'cout': 540000.0, 'economie': self.ECONOMIE_AN1,
            'bilan': {'production_kwh': 80000.0},
            'onduleurs': {'combinaison': [], 'prix_vente_total_ht': '60000.00'},
            'composition': {'incomplet': incomplet, 'lignes': [
                {'role': 'panneau', 'designation': 'Panneau', 'quantite': 80,
                 'prix_connu': True, 'prix_unitaire_ht': '3000'},
                {'role': 'batterie_ci', 'designation': 'Dyness 16 kWh', 'quantite': 4,
                 'prix_connu': True, 'prix_unitaire_ht': '60000'}]}}

    def _ctx(self):
        return {'taux_tva_pct': 20, 'batterie': {'garantie_mois': 120}}

    def test_retour_lu_sur_le_flux_pas_sur_le_quotient(self):
        from apps.ventes import economie_ci as eco
        from apps.ventes.domain.etude_ci_batterie import _bloc
        from apps.ventes.economie_ci_options import (
            annee_remplacement_batterie, flux_option_avec,
        )
        bloc = _bloc(self._evaluation(), self._Valoriseur(), self._ctx())
        base = eco.base_economique(
            None, investissement={'ht': 540000.0, 'ttc': 648000.0},
            economie_annee1=self._Valoriseur().complet(None)['economie_annee1'])
        attendu = flux_option_avec(
            base, lignes=[
                {'designation': 'Onduleur(s) hybride(s)', 'ht': 60000.0, 'ttc': 72000.0,
                 'onduleur': True, 'optionnelle': False},
                {'designation': 'Panneau', 'ht': 240000.0, 'ttc': 288000.0,
                 'optionnelle': False},
                {'designation': 'Batterie Dyness 16 kWh', 'ht': 240000.0, 'ttc': 288000.0,
                 'optionnelle': False}],
            batterie=annee_remplacement_batterie(120, None),
            production_annee1_kwh=80000.0, kwh_evites_an=30000.0)
        retour = attendu['indicateurs']['retour_dixieme_ans']
        self.assertEqual(bloc['retour_simple_ans'], retour)
        self.assertEqual(bloc['economie_flux']['indicateurs']['retour_dixieme_ans'], retour)
        # L'ancien quotient (540 000 / 40 000 = 13,5) ignorait dégradation et remplacements.
        self.assertEqual(round(540000.0 / self.ECONOMIE_AN1, 1), 13.5)
        self.assertNotEqual(bloc['retour_simple_ans'], 13.5)
        self.assertGreater(bloc['retour_simple_ans'], 13.5)
        composants = {r['composant'] for r in bloc['economie_flux']['remplacements']}
        self.assertEqual(composants, {'onduleur', 'batterie'})

    def test_aucune_entree_aucun_quotient(self):
        from apps.ventes.domain.etude_ci_batterie import _bloc
        # composition incomplète (prix à renseigner / après visite)
        self.assertIsNone(_bloc(self._evaluation(incomplet=True), self._Valoriseur(),
                                self._ctx())['retour_simple_ans'])
        # économie omise par le valoriseur
        omis = _bloc(self._evaluation(), self._Valoriseur('omis'), self._ctx())
        self.assertIsNone(omis['retour_simple_ans'])
        self.assertIsNone(omis['economie_flux'])
        # pas de valoriseur : le bloc se sert, sans retour
        self.assertIsNone(_bloc(self._evaluation(), None, self._ctx())['retour_simple_ans'])

    def test_tva_suit_le_lead_et_la_base_du_flux(self):
        from types import SimpleNamespace as L

        from apps.ventes.domain.etude_ci_batterie import _bloc, option_avec_de_l_etude
        vus = {}

        def espion(imposee, contexte):
            vus.update(contexte)
            return {}
        with mock.patch('apps.ventes.domain.etude_ci_batterie._option_imposee', espion):
            option_avec_de_l_etude({}, None, choix='avec', lead=L(tva_recuperable='non'),
                                   imposee={'x': 1}, taux_tva_pct=20)
        self.assertEqual(vus['tva_recuperable']['valeur'], 'non')
        self.assertEqual(vus['tva_recuperable']['provenance'], 'lead')
        with mock.patch('apps.ventes.domain.etude_ci_batterie._option_imposee', espion):
            option_avec_de_l_etude({}, None, choix='avec', lead=None, imposee={'x': 1})
        self.assertEqual(vus['tva_recuperable']['valeur'], 'inconnu')
        for valeur, base in (('oui', 'ht'), ('non', 'ttc'), ('inconnu', 'deux')):
            ctx = dict(self._ctx(), tva_recuperable=valeur)
            bloc = _bloc(self._evaluation(), self._Valoriseur(), ctx)
            self.assertEqual(bloc['economie_flux']['base'], base)

    def test_sans_tva_standard_le_remplacement_onduleur_reste(self):
        from apps.ventes.domain.etude_ci_batterie import _bloc, _investissement_composition
        avec_tva = _bloc(self._evaluation(), self._Valoriseur(), self._ctx())
        ctx = {'taux_tva_pct': None, 'batterie': {'garantie_mois': 120}}
        invest = _investissement_composition(self._evaluation(), None)
        self.assertIsNone(invest['ttc'])
        self.assertTrue(all(x['ttc'] == x['ht'] for x in invest['lignes']))
        sans_tva = _bloc(self._evaluation(), self._Valoriseur(), ctx)
        self.assertEqual({r['composant'] for r in sans_tva['economie_flux']['remplacements']},
                         {'onduleur', 'batterie'})
        self.assertEqual(sans_tva['retour_simple_ans'], avec_tva['retour_simple_ans'])

    def test_option_des_lignes_lue_comme_l_option_sans(self):
        import contextlib
        from types import SimpleNamespace

        from apps.ventes.domain.etude_ci_batterie import _bloc, _investissement_des_lignes
        devis = object()
        detail = [
            {'designation': 'Onduleur hybride', 'ht': 54000.0, 'ttc': 64800.0,
             'optionnelle': False, 'onduleur': True, 'role_ci': None},
            {'designation': 'Batterie Dyness', 'ht': 216000.0, 'ttc': 259200.0,
             'optionnelle': False, 'onduleur': False, 'role_ci': None},
            {'designation': 'Panneaux', 'ht': 216000.0, 'ttc': 237600.0,
             'optionnelle': False, 'onduleur': False, 'role_ci': None},
            {'designation': 'O&M', 'ht': 2000.0, 'ttc': 2400.0,
             'optionnelle': False, 'onduleur': False, 'role_ci': 'om_ci'}]
        # totaux NETS (remise globale de 10 % déjà déduite) : jamais la somme brute des lignes
        cibles = {'apps.ventes.utils.options.option_effective': {'return_value': ''},
                  'apps.ventes.utils.options.option_totaux':
                  {'return_value': {'ht': 488000.0, 'ttc': 564000.0}},
                  'apps.ventes.economie_ci.lignes_pour_economie_ci': {'return_value': detail}}
        with contextlib.ExitStack() as pile:
            for cible, options in cibles.items():
                pile.enter_context(mock.patch(cible, **options))
            invest = _investissement_des_lignes([], devis)
            # #1094 — devis envoyé aux règles du 08/10 (niveau 2) : O&M gardée en an 0
            envoye = _investissement_des_lignes([], SimpleNamespace(regles_calcul=2))
        self.assertEqual(invest['ht'], 486000.0)       # O&M sortie de l'année 0 (CEC1)
        self.assertEqual(invest['ttc'], 561600.0)
        self.assertEqual((envoye['ht'], envoye['ttc']), (488000.0, 564000.0))
        self.assertIs(invest['lignes'], detail)
        evaluation = dict(self._evaluation(), cout=None, composition=None,
                          onduleurs={'combinaison': []})
        bloc = _bloc(evaluation, self._Valoriseur(), self._ctx(), investissement=invest)
        self.assertGreater(bloc['retour_simple_ans'], 486000.0 / self.ECONOMIE_AN1)
        # l'argent du devis suit l'option « sans » (accepté) : pas de retour de l'option « avec »
        self.assertIsNone(_investissement_des_lignes([], SimpleNamespace(option_acceptee='sans_batterie')))
        # ERR-CEC6-RETOUR-AVEC-BATTERIE-PERDU — C&I à deux options NON accepté (CIQ302 : l'offre
        # réseau est mise en avant) : l'option « avec » garde le retour de SON investissement,
        # lu sur les totaux et les lignes de l'option « avec » ; un devis envoyé avant le niveau 5
        # (niveau 4 compris, en production le 30/10) garde l'option que suit son argent
        # (nouveaux rendus seulement).
        cibles['apps.ventes.utils.options.option_effective'] = {'return_value': 'sans_batterie'}
        with contextlib.ExitStack() as pile:
            mocks = {c: pile.enter_context(mock.patch(c, **o)) for c, o in cibles.items()}
            neuf = _investissement_des_lignes([], SimpleNamespace(regles_calcul=5, option_acceptee=''))
            envoye_4 = _investissement_des_lignes([], SimpleNamespace(regles_calcul=4, option_acceptee=''))
            envoye_3 = _investissement_des_lignes([], SimpleNamespace(regles_calcul=3, option_acceptee=''))
        self.assertEqual((neuf['ht'], neuf['cout_vente_ht']), (486000.0, 488000.0))
        self.assertEqual(mocks['apps.ventes.utils.options.option_totaux'].call_args.args[1], 'avec_batterie')
        self.assertEqual(mocks['apps.ventes.economie_ci.lignes_pour_economie_ci'].call_args.args[1],
                         'avec_batterie')
        self.assertIsNone(envoye_4)
        self.assertIsNone(envoye_3)
        bloc = _bloc(evaluation, self._Valoriseur(), self._ctx(), investissement=neuf)
        self.assertIsNotNone(bloc['retour_simple_ans'])
        self.assertIsNotNone(bloc['economie_flux'])
        self.assertEqual(bloc['cout_vente_ht'], 488000.0)
        # sans devis (ni ``ligne.devis``) : rien
        self.assertIsNone(_investissement_des_lignes([], None))

    def test_composition_garde_l_om_en_an0_sur_un_devis_envoye_niveau_2(self):
        """Audit Fable L3 — le chemin « composition » de l'option « avec »
        (devis « sans » / « les deux » : aucune ligne d'option « avec »)
        suit le niveau de règles : CEC1 (O&M hors de l'année 0) au niveau 3
        seulement ; un devis envoyé ≤ 2 recalculé garde l'ancien investissement."""
        from apps.ventes.domain import etude_ci_batterie as m
        evaluation = self._evaluation()
        evaluation['composition']['lignes'].append(
            {'role': 'om_ci', 'designation': 'O&M', 'quantite': 1,
             'prix_connu': True, 'prix_unitaire_ht': '1000'})
        courant = m._investissement_composition(evaluation, 20)
        envoye = m._investissement_composition(evaluation, 20, regles_2710=False)
        self.assertEqual((envoye['ht'], envoye['ttc']), (540000.0, 649200.0))
        self.assertEqual((courant['ht'], courant['ttc']), (539000.0, 648000.0))
        retours = {}
        for niveau in (True, False):
            bloc = m._bloc(evaluation, self._Valoriseur(), dict(self._ctx(), regles_2710=niveau))
            retours[niveau] = bloc['retour_simple_ans']
        self.assertGreater(retours[False], retours[True])
        # le niveau passé à ``option_avec_de_l_etude`` atteint le ctx des DEUX chemins
        vus = []
        resultat = {'evaluation': evaluation, 'prix_a_renseigner': [], 'hypotheses': [],
                    'alertes': [], 'motif': None}
        catalogue = {'batterie': {'hybrides': [1], 'batteries': [{'produit': 1}]}}
        with mock.patch.object(m, 'batteries_compatibles', return_value=[1]), \
                mock.patch.object(m, '_dimensionner', return_value=resultat), \
                mock.patch.object(m, '_option_dominee', return_value=False), \
                mock.patch.object(m, '_bloc', lambda ev, val, ctx, **k: vus.append(ctx) or {}), \
                mock.patch.object(m, '_option_imposee', lambda imp, ctx: vus.append(ctx) or {}):
            for imposee in (None, {'x': 1}):
                m.option_avec_de_l_etude(catalogue, {'kwc': 1}, choix='avec', lead=None,
                                         imposee=imposee, regles_2710=False,
                                         tva_recuperable={'valeur': 'inconnu'})
            m.option_avec_de_l_etude(catalogue, {'kwc': 1}, choix='avec', lead=None,
                                     tva_recuperable={'valeur': 'inconnu'})
        self.assertEqual([c['regles_2710'] for c in vus], [False, False, True])

    def test_pack_publie_sans_quantite_ne_borne_pas_a_zero(self):
        from apps.ventes.moteur_ci.batterie import puissance_decharge_kw
        self.assertIsNone(puissance_decharge_kw({'max_decharge_kw': 5.0, 'quantite': 0}, None, []))
        self.assertEqual(puissance_decharge_kw({'max_decharge_kw': 5.0, 'quantite': 3}, None, []), 15.0)


class OptionAvecDomineeTests(SimpleTestCase):
    """CMP9 (D-CMP-5) — une option « avec » plus chère ET moins économe que
    l'option « sans » n'est pas proposée (alerte interne ; bloquante si le
    lead a choisi « avec »)."""

    SANS = {'kwc': 260, 'cout': 928317.0, 'economie': 233192.0}

    def _avec(self, cout, economie):
        return {'kwc': 199, 'cout': cout, 'economie': economie, 'batterie': {'produit': 1},
                'bilan': {}, 'composition': {'lignes': []}, 'onduleurs': {'combinaison': []}}

    def _lancer(self, avec, choix='les_deux', alertes=()):
        from apps.ventes.domain import etude_ci_batterie as m
        resultat = {'evaluation': avec, 'prix_a_renseigner': [], 'hypotheses': [],
                    'alertes': list(alertes), 'motif': None}
        catalogue = {'batterie': {'hybrides': [1], 'batteries': [{'produit': 1}]}}
        with mock.patch.object(m, 'batteries_compatibles', return_value=[1]), \
                mock.patch.object(m, '_dimensionner', return_value=resultat), \
                mock.patch.object(m, '_bloc', return_value={'kwc': 199}):
            return m.option_avec_de_l_etude(catalogue, dict(self.SANS), choix=choix, lead=None,
                                            tva_recuperable={'valeur': 'inconnu'})

    def test_option_dominee_aucun_bloc_alerte_interne_nommant_la_cause(self):
        borne = {'code': 'HYBRIDES_PARALLELE_MAX', 'message': 'x'}
        sortie = self._lancer(self._avec(1140483.0, 229971.0), alertes=[borne])
        self.assertIsNone(sortie['bloc'])
        alerte = next(a for a in sortie['alertes'] if a['code'] == 'OPTION_BATTERIE_DOMINEE')
        self.assertEqual(alerte['niveau'], 'alerte')
        self.assertTrue(alerte['interne'])
        for texte in ('1140483', '928317', '229971', '233192', 'parallèle'):
            self.assertIn(texte, alerte['message'])

    def test_choix_avec_du_lead_refus_bloquant(self):
        sortie = self._lancer(self._avec(1140483.0, 229971.0), choix='avec')
        self.assertIsNone(sortie['bloc'])
        alerte = next(a for a in sortie['alertes'] if a['code'] == 'OPTION_BATTERIE_DOMINEE')
        self.assertEqual(alerte['niveau'], 'bloquant')

    def test_option_non_dominee_inchangee(self):
        sortie = self._lancer(self._avec(1140483.0, 260000.0))
        self.assertEqual(sortie['bloc'], {'kwc': 199})
        self.assertFalse([a for a in sortie['alertes'] if a['code'] == 'OPTION_BATTERIE_DOMINEE'])

    def test_cout_ou_economie_manquant_aucun_verdict(self):
        for avec in (self._avec(None, 100.0), self._avec(2e6, None)):
            self.assertIsNotNone(self._lancer(avec)['bloc'])
        from apps.ventes.domain.etude_ci_batterie import _option_dominee
        self.assertFalse(_option_dominee({'cout': None, 'economie': 1.0}, self._avec(2e6, 0.5)))


class RevisionApresVisiteCorc2Tests(_Base):
    """CORC2 (27/10/2026) — le devis C&I préliminaire est RECOMPOSÉ avec les
    mesures de la visite C&I validée : brouillon sur place, sinon V+1 ;
    aucun statut écrit ; contrat ``devis_revise_visite.json``."""

    def _visite(self, lead, dc=10, ac=45):
        from apps.visites.models import VisiteTerrain
        return VisiteTerrain.objects.create(
            company=self.co, lead=lead, gabarit='ci', statut=VisiteTerrain.Statut.VALIDEE,
            mesures={'cheminement': {'trajets': [
                {'libelle': 'a', 'longueur_dc_m': dc, 'longueur_ac_m': ac}]}})

    def _reviser(self, devis):
        from apps.ventes.domain.revision_visite_ci import reviser_devis_apres_visite
        with mock.patch.object(tarif_ci, 'tarif_applicable', side_effect=_tarif_grille):
            return reviser_devis_apres_visite(devis, user=self.user)

    def _quantite(self, devis, role_nom):
        return sum(ligne.quantite for ligne in devis.lignes.all()
                   if role_nom in ligne.designation)

    def test_sans_visite_validee_refus_nomme(self):
        from apps.ventes.domain.revision_visite_ci import RevisionVisiteError
        devis = self._auto(self._lead(conso_mensuelle_kwh=Decimal('6000')))
        with self.assertRaises(RevisionVisiteError) as ctx:
            self._reviser(devis)
        self.assertEqual(ctx.exception.champ, 'visite')

    def test_brouillon_recompose_sur_place_avec_les_mesures(self):
        lead = self._lead(conso_mensuelle_kwh=Decimal('6000'))
        devis = self._auto(lead)
        ac_avant = self._quantite(devis, 'Câble AC')
        self._visite(lead)
        resultat = self._reviser(devis)
        self.assertFalse(resultat['cree'])
        self.assertEqual(resultat['devis'].pk, devis.pk)
        self.assertEqual(resultat['devis'].statut, Devis.Statut.BROUILLON)
        self.assertNotEqual(self._quantite(resultat['devis'], 'Câble AC'), ac_avant)
        self.assertIn('longueur_ac_m', [m['cle'] for m in resultat['mesures_utilisees']])
        self.assertTrue(resultat['lignes_changees'])

    def test_taille_vendue_gardee(self):
        from apps.ventes.domain.etudes import puissances_etude_horaire
        lead = self._lead(conso_mensuelle_kwh=Decimal('6000'))
        devis = self._auto(lead)
        avant = puissances_etude_horaire(devis)
        self._visite(lead)
        apres = puissances_etude_horaire(self._reviser(devis)['devis'])
        self.assertEqual(apres, avant)

    def test_avec_seule_taille_gardee(self):
        """CORC10 — un devis « avec batterie » SEULE est recomposé avec les
        mesures à la taille de SES lignes (panneaux ajoutés pour la batterie
        compris) et avec sa banque, jamais redimensionné en offre réseau."""
        from apps.ventes.domain.etudes import puissances_etude_horaire
        _semer_batterie(self)
        lead = self._lead(conso_mensuelle_kwh=Decimal('6000'), batterie_souhaitee='avec',
                          categorie_commerciale='boulangerie',
                          jours_ouverture=list(range(1, 8)), heure_debut=7, heure_fin=21,
                          surface_toiture_m2=Decimal('200'))
        devis = self._auto(lead)
        self.assertEqual(devis.etude_params.get('scenario'), 'Avec batterie')
        batteries = {self.b5.id, self.b10.id, self.b16.id}
        banque_avant = sorted(devis.lignes.filter(produit_id__in=batteries)
                              .values_list('produit_id', 'quantite'))
        avant = puissances_etude_horaire(devis)
        ac_avant = self._quantite(devis, 'Câble AC')
        self._visite(lead)
        resultat = self._reviser(devis)
        self.assertFalse(resultat['cree'])
        self.assertEqual(puissances_etude_horaire(resultat['devis']), avant)
        self.assertNotEqual(self._quantite(resultat['devis'], 'Câble AC'), ac_avant)
        # Persistance : le devis relu porte les mêmes lignes et le même kWc.
        relu = Devis.objects.get(pk=devis.pk)
        self.assertEqual(puissances_etude_horaire(relu), avant)
        self.assertEqual(relu.etude_params.get('scenario'), 'Avec batterie')
        self.assertEqual(sorted(relu.lignes.filter(produit_id__in=batteries)
                                .values_list('produit_id', 'quantite')), banque_avant)
        self.assertNotIn(self.onduleur.id, set(relu.lignes.values_list('produit_id', flat=True)))
        self.assertFalse(relu.lignes.exclude(variante='').exists())

    def test_refus_apres_revision_rien_ecrit(self):
        # Fable pré-merge : un refus (ici prestations non réglées) après la
        # révision d'un envoyé ne laisse ni V1 remplacée ni V2 orpheline.
        from apps.ventes.domain.revision_visite_ci import RevisionVisiteError
        lead = self._lead(conso_mensuelle_kwh=Decimal('6000'))
        devis = self._auto(lead)
        Devis.objects.filter(pk=devis.pk).update(statut=Devis.Statut.ENVOYE)
        devis.refresh_from_db()
        self._visite(lead)
        CompanyProfile.objects.filter(company=self.co).update(forfaits_ci={})
        avant = Devis.objects.filter(company=self.co).count()
        with self.assertRaises(RevisionVisiteError):
            self._reviser(devis)
        devis.refresh_from_db()
        self.assertTrue(devis.is_active)
        self.assertIsNone(devis.superseded_by_id)
        self.assertEqual(Devis.objects.filter(company=self.co).count(), avant)

    def test_devis_envoye_v2_creee_v1_intacte(self):
        lead = self._lead(conso_mensuelle_kwh=Decimal('6000'))
        devis = self._auto(lead)
        Devis.objects.filter(pk=devis.pk).update(statut=Devis.Statut.ENVOYE)
        devis.refresh_from_db()
        lignes_v1 = list(devis.lignes.values_list('designation', 'quantite'))
        self._visite(lead)
        resultat = self._reviser(devis)
        self.assertTrue(resultat['cree'])
        self.assertNotEqual(resultat['devis'].pk, devis.pk)
        self.assertEqual(resultat['devis'].version, devis.version + 1)
        devis.refresh_from_db()
        self.assertEqual(devis.statut, Devis.Statut.ENVOYE)  # règle #4
        self.assertEqual(list(devis.lignes.values_list('designation', 'quantite')), lignes_v1)


class BrouillonsMultiplesCorc7Tests(_Base):
    """CORC7 (27/10/2026) — un 2ᵉ devis automatique C&I sur le même lead
    NOMME au vendeur le brouillon précédent ; rien n'est archivé (un devis
    archivé ne se réactive plus)."""

    def test_second_devis_auto_nomme_le_premier_sans_rien_archiver(self):
        lead = self._lead(conso_mensuelle_kwh=Decimal('6000'))
        premier = self._auto(lead)
        journal = {}
        with mock.patch.object(tarif_ci, 'tarif_applicable', side_effect=_tarif_grille):
            second = build_devis_auto(lead=lead, user=self.user, company=self.co,
                                      journal_auto=journal)
        alerte = next(a for a in journal['alertes'] if a['code'] == 'brouillons_ci_multiples')
        self.assertIn(premier.reference, alerte['message'])
        self.assertNotIn(second.reference, alerte['message'])
        premier.refresh_from_db()
        self.assertTrue(premier.is_active)

    def test_premier_devis_auto_aucune_alerte(self):
        journal = {}
        with mock.patch.object(tarif_ci, 'tarif_applicable', side_effect=_tarif_grille):
            build_devis_auto(lead=self._lead(conso_mensuelle_kwh=Decimal('6000')),
                             user=self.user, company=self.co, journal_auto=journal)
        self.assertNotIn('brouillons_ci_multiples', [a['code'] for a in journal['alertes']])


class PrestationSansArticleCorc6Tests(_Base):
    """CORC6 (27/10/2026, constat CCAT) — une prestation réglée SANS article
    au catalogue fait refuser le devis automatique en la NOMMANT ; jamais un
    total d'étude qui diverge du devis écrit."""

    def test_prestation_sans_article_refus_nomme(self):
        Produit.objects.filter(company=self.co, role_ci='transport_ci').delete()
        erreur = self._refus(self._lead(conso_mensuelle_kwh=Decimal('6000')))
        self.assertEqual(erreur.field, 'composition')
        self.assertIn('Article manquant au catalogue', erreur.message)
        self.assertIn('Transport', erreur.message)
