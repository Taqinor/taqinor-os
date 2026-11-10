"""ADEV30 (C-ADEV-041, D-ASTK-1) — un devis ENVOYÉ ne suit plus le barème du
jour sur une retouche qui ne change pas son nombre de panneaux : seules les
lignes d'un BROUILLON suivent le catalogue.

Rejoue la sonde VB r3 : envoyé, barème « par panneau » relevé, PATCH de la
seule désignation d'une AUTRE ligne → la ligne forfait était re-tarifée
(TTC +1 200).

Test-du-test : remettre l'appel inconditionnel de la re-tarification dans
``views/ligne_devis.py`` ⇒ ``test_retouche_sans_rapport_ttc_inchange``
échoue ; retirer le test de statut dans ``domain/lignes.py`` ⇒
``test_catalogue_event_ignore_envoye`` échoue. Source réelle (aucun mock).
"""
from decimal import Decimal

from rest_framework.test import APIClient

from apps.ventes.domain.catalogue import prix_forfait_ht
from apps.ventes.domain.lignes import retarifer_forfaits_par_panneau
from apps.ventes.models import Devis, DevisActivity
from apps.ventes.services import sync_devis_from_layout
from apps.ventes.tests import test_qjr220_retarification_reconcilier as q220
from apps.ventes.tests.test_pv18_sync_layout import layout

URL = '/api/django/ventes/devis-lignes/'


class EnvoyeNeSuitPasCatalogueTests(q220._Base):

    def setUp(self):
        super().setUp()
        self.api = APIClient()
        self.api.force_authenticate(user=self.user)

    def _devis_envoye(self):
        devis = self._devis(9, pose_a=9)
        Devis.objects.filter(pk=devis.pk).update(statut=Devis.Statut.ENVOYE)
        devis.refresh_from_db()
        return devis

    def _relever_bareme(self):
        self.pose.prix_par_panneau_ht += Decimal('100')
        self.pose.save(update_fields=['prix_par_panneau_ht'])

    def test_retouche_sans_rapport_ttc_inchange(self):
        devis = self._devis_envoye()
        fige = self._prix_pose(devis)
        self._relever_bareme()
        onduleur = devis.lignes.get(designation=q220.RESEAU)
        resp = self.api.patch('%s%s/' % (URL, onduleur.pk),
                              {'designation': 'Onduleur réseau 5 kW'},
                              format='json')
        self.assertEqual(resp.status_code, 200, getattr(resp, 'data', resp))
        # CLAUSE PERSISTANCE — relu en base.
        self.assertEqual(self._prix_pose(devis), fige)

    def test_resync_envoye_bareme_fige(self):
        devis = self._devis_envoye()
        fige = self._prix_pose(devis)
        self._relever_bareme()
        # Même nombre de panneaux : aucune re-tarification.
        sync_devis_from_layout(devis, layout(panels=9, kwc=4.95),
                               user=self.user)
        self.assertEqual(self._prix_pose(devis), fige)

    def test_envoye_compte_change_retarife(self):
        devis = self._devis_envoye()
        panneau = devis.lignes.get(designation=q220.PANNEAU)
        resp = self.api.patch('%s%s/' % (URL, panneau.pk),
                              {'quantite': '20'}, format='json')
        self.assertEqual(resp.status_code, 200, getattr(resp, 'data', resp))
        self.assertEqual(self._prix_pose(devis),
                         prix_forfait_ht(self.pose, 20))
        self.assertTrue(DevisActivity.objects.filter(
            devis=devis, field='correction_apres_envoi').exists())

    def test_catalogue_event_ignore_envoye(self):
        devis = self._devis_envoye()
        fige = self._prix_pose(devis)
        self._relever_bareme()
        # Un événement catalogue (aucun compte « avant » : le nombre de
        # panneaux ne change pas) ne re-tarife jamais un envoyé.
        retarifer_forfaits_par_panneau(devis)
        self.assertEqual(self._prix_pose(devis), fige)

    def test_brouillon_suit_catalogue(self):
        devis = self._devis(9, pose_a=9)
        self._relever_bareme()
        onduleur = devis.lignes.get(designation=q220.RESEAU)
        resp = self.api.patch('%s%s/' % (URL, onduleur.pk),
                              {'designation': 'Onduleur réseau 5 kW'},
                              format='json')
        self.assertEqual(resp.status_code, 200)
        self.pose.refresh_from_db()
        self.assertEqual(self._prix_pose(devis),
                         prix_forfait_ht(self.pose, 9))


class BaremeGeleEnvoiTests(q220._Base):
    """ADEV30 — sur un ENVOYÉ dont le nombre de panneaux change, le forfait
    est recalculé avec le barème GELÉ à l'envoi (``mark_devis_sent``), jamais
    avec le barème du jour. Test-du-test : retirer
    ``figer_baremes_forfaits(devis)`` de ``mark_devis_sent`` ⇒
    ``test_compte_change_bareme_fige`` échoue."""

    def setUp(self):
        super().setUp()
        self.api = APIClient()
        self.api.force_authenticate(user=self.user)

    def _envoyer(self, devis):
        from apps.ventes.domain.envoi import mark_devis_sent
        mark_devis_sent(devis=devis, user=self.user)
        devis.refresh_from_db()
        self.assertEqual(devis.statut, Devis.Statut.ENVOYE)
        return devis

    def test_gel_pose_a_l_envoi(self):
        from apps.ventes.domain.envoi import baremes_forfaits_geles
        devis = self._envoyer(self._devis(9, pose_a=9))
        # Le gel lit le barème EN BASE (DecimalField → '2000.00') : relire
        # la fixture, créée en mémoire avec Decimal('2000').
        self.pose.refresh_from_db()
        self.assertEqual(
            baremes_forfaits_geles(devis),
            {str(self.pose.pk): {
                'prix_fixe_ht': str(self.pose.prix_fixe_ht),
                'prix_par_panneau_ht': str(self.pose.prix_par_panneau_ht)}})

    def test_compte_change_bareme_fige(self):
        from types import SimpleNamespace
        devis = self._envoyer(self._devis(9, pose_a=9))
        ancien = SimpleNamespace(
            prix_fixe_ht=self.pose.prix_fixe_ht,
            prix_par_panneau_ht=self.pose.prix_par_panneau_ht)
        self.pose.prix_par_panneau_ht += Decimal('100')
        self.pose.save(update_fields=['prix_par_panneau_ht'])
        panneau = devis.lignes.get(designation=q220.PANNEAU)
        resp = self.api.patch('%s%s/' % (URL, panneau.pk),
                              {'quantite': '20'}, format='json')
        self.assertEqual(resp.status_code, 200, getattr(resp, 'data', resp))
        # CLAUSE PERSISTANCE — relu en base : barème GELÉ, pas celui du jour.
        self.assertEqual(self._prix_pose(devis), prix_forfait_ht(ancien, 20))
        self.assertNotEqual(self._prix_pose(devis),
                            prix_forfait_ht(self.pose, 20))

    def test_gel_jamais_imprime_comme_clause(self):
        from apps.ventes.quote_engine.builder import build_quote_data
        devis = self._envoyer(self._devis(9, pose_a=9))
        data = build_quote_data(devis)
        self.assertFalse(data.get('clauses_cgv'))

    def _devis_a_figer(self):
        from apps.parametres.models import CompanyProfile
        from apps.parametres.models_tariff import TariffSettings
        profil = CompanyProfile.get(self.company)
        profil.productible_kwh_kwc = None
        profil.save()
        tarif = TariffSettings.get(company=self.company)
        tarif.redevance_compteur_mad_mois = Decimal('95')
        tarif.save()
        self.panneau.garantie = '25 ans'
        self.panneau.garantie_mois = 300
        self.panneau.save()
        return self._devis(9, pose_a=9), profil, tarif

    def test_reglages_et_fiches_figes_a_l_envoi(self):
        """ADVS2 — rouge sans l'appel dans ``geler_document_engage``."""
        import json
        from pathlib import Path

        from apps.ventes.domain.reglages_figes_lecture import reglages_figes
        devis, profil, tarif = self._devis_a_figer()
        self.assertEqual(reglages_figes(devis), {})
        devis = self._envoyer(devis)
        fige = reglages_figes(devis)
        exemple = json.loads(
            (Path(__file__).resolve().parents[1] / 'contract_samples'
             / 'reglages_figes_envoi.json').read_text(encoding='utf-8')
        )['exemple']
        self.assertEqual(set(fige), set(exemple))
        self.assertEqual(set(fige['tarif']), set(exemple['tarif']))
        self.assertIsNone(fige['tarif']['productible_kwh_kwc'])
        self.assertEqual(fige['redevance_compteur_mad_mois'], 95.0)
        fiche = fige['produits'][str(self.panneau.pk)]
        self.assertEqual(set(fiche), set(exemple['produits']['412']))
        self.assertEqual(fiche['garantie'], '25 ans')
        self.assertEqual(fiche['garantie_mois'], 300)

        profil.productible_kwh_kwc = 1200
        profil.save()
        tarif.redevance_compteur_mad_mois = Decimal('120')
        tarif.save()
        self.panneau.garantie = '10 ans'
        self.panneau.garantie_mois = 120
        self.panneau.save()
        # CLAUSE PERSISTANCE — relu en base : l'instantané de l'envoi.
        devis.refresh_from_db()
        self.assertEqual(reglages_figes(devis), fige)
        # Gel interne : jamais imprimé comme clause particulière.
        from apps.ventes.quote_engine.builder import build_quote_data
        self.assertFalse(build_quote_data(devis).get('clauses_cgv'))

    def test_echeancier_fige_a_l_envoi(self):
        """ASOC95 (C-ASOC-040, D-ASOC-1) — jalons société 30/60/10 figés à
        l'envoi : passés à 40/50/10 ensuite, le devis lit encore 30 % ; un
        échéancier négocié reste tel quel ; un renouvellement n'hérite pas du
        gel automatique. Mutant : retirer l'appel ⇒ 40 %."""
        from apps.parametres.models import CompanyProfile
        from apps.ventes.domain.revision import renouveler_devis
        from apps.ventes.utils.echeancier import tranches_normalisees
        profil = CompanyProfile.get(self.company)
        mode = 'residentiel'
        profil.payment_terms = {mode: {'acompte': 30, 'materiel': 60, 'solde': 10}}
        profil.save(update_fields=['payment_terms'])
        devis = self._devis(9, pose_a=9)
        devis.mode_installation = mode
        devis.save(update_fields=['mode_installation'])
        devis = self._envoyer(devis)
        self.assertTrue(devis.echeancier)
        self.assertTrue(all(e.get('fige_le') for e in devis.echeancier))
        profil.payment_terms = {mode: {'acompte': 40, 'materiel': 50, 'solde': 10}}
        profil.save(update_fields=['payment_terms'])
        devis.refresh_from_db()  # CLAUSE PERSISTANCE
        self.assertEqual([float(t['valeur']) for t in tranches_normalisees(devis)], [30.0, 60.0, 10.0])
        Devis.objects.filter(pk=devis.pk).update(statut=Devis.Statut.EXPIRE)
        devis.refresh_from_db()  # seul un expiré se renouvelle (NTCPQ13)
        copie = renouveler_devis(devis, user=self.user)
        copie.refresh_from_db()
        self.assertFalse(copie.echeancier)
        negocie = [{'libelle': 'Acompte', 'type': 'acompte', 'pct_or_montant': 50},
                   {'libelle': 'Solde', 'type': 'solde', 'pct_or_montant': 50}]
        autre = self._devis(9, pose_a=9)
        autre.echeancier = negocie
        autre.save(update_fields=['echeancier'])
        self.assertEqual(self._envoyer(autre).echeancier, negocie)

    def test_identite_vendeur_figee_a_l_envoi(self):
        """ASOC42 (C-ASOC-042) — raison sociale et ICE changés après l'envoi :
        la page publique sert encore l'émetteur de l'envoi ; un brouillon lit le
        profil du jour. Mutant : lire ``company_identity`` vivant ⇒ ICE v2."""
        from apps.parametres.models import CompanyProfile
        from apps.ventes.domain.reglages_figes_lecture import reglages_figes
        from apps.ventes.models import ShareLink
        from apps.ventes.public_views import _emetteur_public

        from .test_adev50_cumul_25_ans_servi import lire
        profil = CompanyProfile.get(self.company)
        profil.nom, profil.ice = 'SOLAIRE ANCIEN SARL', '001111111000011'
        profil.save()
        devis = self._envoyer(self._devis(9, pose_a=9))
        brouillon = self._devis(9, pose_a=9)
        profil.nom, profil.ice = 'SOLAIRE NOUVEAU SA', '002222222000022'
        profil.save()
        devis.refresh_from_db()  # CLAUSE PERSISTANCE — l'instantané v1
        self.assertEqual(reglages_figes(devis)['identite']['ice'], '001111111000011')
        lien = ShareLink.objects.create(company=self.company, devis=devis)
        resp = lire(lien.token)
        self.assertEqual(resp.status_code, 200, resp.content[:300])
        self.assertEqual((resp.json()['emetteur']['nom'], resp.json()['emetteur']['ice']),
                         ('SOLAIRE ANCIEN SARL', '001111111000011'))
        self.assertEqual(_emetteur_public(brouillon)['ice'], '002222222000022')

    def test_v2_refigee_a_son_propre_envoi(self):
        from apps.ventes.domain.reglages_figes_lecture import (
            TYPE_REGLAGES_FIGES, reglages_figes)
        devis, _profil, tarif = self._devis_a_figer()
        devis = self._envoyer(devis)
        # V2 : brouillon qui a hérité de l'entrée de la V1.
        v2 = self._devis(9, pose_a=9)
        v2.clauses_appliquees = list(devis.clauses_appliquees)
        v2.save(update_fields=['clauses_appliquees'])
        self.assertEqual(reglages_figes(v2), {})
        tarif.redevance_compteur_mad_mois = Decimal('120')
        tarif.save()
        v2 = self._envoyer(v2)
        self.assertEqual(
            reglages_figes(v2)['redevance_compteur_mad_mois'], 120.0)
        self.assertEqual(
            [c.get('type') for c in v2.clauses_appliquees].count(
                TYPE_REGLAGES_FIGES), 1)

    def test_page_publique_garde_sa_conso_apres_nouveaux_reglages(self):
        """ADVS45 (D-ADVS-1, C-ADVS-VER1-101) — la page publique d'un envoyé
        lit les tranches et la redevance de SON envoi, comme ``/proposal``.
        Mutant : remettre ``_reglages_tarifaires`` dans
        ``conso_publique_du_devis`` ⇒ échec (838 → 465 à la sonde)."""
        from apps.crm.models import Lead
        from apps.parametres.models_tariff import TariffSettings
        from apps.ventes.models import ShareLink
        from apps.ventes.public.payload_horaire import conso_publique_du_devis

        from .test_adev50_cumul_25_ans_servi import lire

        lead = Lead.objects.create(
            company=self.company, nom='Public', prenom='Fige',
            telephone='+212600450045', ville='Casablanca',
            type_installation='residentiel', facture_hiver=Decimal('1500'))
        devis = self._devis(9, pose_a=9)
        devis.lead = lead
        devis.save(update_fields=['lead'])
        brouillon = self._devis(9, pose_a=9)
        brouillon.lead = lead
        brouillon.save(update_fields=['lead'])
        devis = self._envoyer(devis)
        lien = ShareLink.objects.create(company=self.company, devis=devis)

        avant = lire(lien.token)
        self.assertEqual(avant.status_code, 200, avant.content[:300])
        avant = avant.json()
        self.assertTrue(avant['monthly_consumption'])
        conso_brouillon = conso_publique_du_devis(brouillon)

        tarif = TariffSettings.get(company=self.company)
        tarif.redevance_compteur_mad_mois = Decimal('120')
        tarif.residential_tiers = [
            {'max_kwh': 100, 'prix_kwh_ttc': '1.50'},
            {'max_kwh': 200, 'prix_kwh_ttc': '1.90'},
            {'max_kwh': None, 'prix_kwh_ttc': '2.80'}]
        tarif.save()

        apres = lire(lien.token)
        self.assertEqual(apres.status_code, 200, apres.content[:300])
        apres = apres.json()
        self.assertEqual(apres['monthly_consumption'],
                         avant['monthly_consumption'])
        self.assertEqual(apres.get('courbes_journalieres'),
                         avant.get('courbes_journalieres'))
        # Brouillon : pas d'instantané, les réglages du jour.
        self.assertNotEqual(conso_publique_du_devis(brouillon), conso_brouillon)
