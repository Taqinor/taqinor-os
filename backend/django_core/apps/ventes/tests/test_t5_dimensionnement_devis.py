"""T5 (24/08/2026) — ``services.rafraichir_dimensionnement_devis`` pose
``etude_params['dimensionnement']`` sur un devis RÉSIDENTIEL persisté, même
esprit que ``rafraichir_etude_horaire_devis`` (CJ2b) mais pour le TABLEAU de
dimensionnement (``apps.ventes.dimensionnement.recommander_taille``) plutôt
que le bloc horaire d'une taille.

Ce que le moteur PDF (``ETUDE['dimensionnement']``) et le payload public T4
(tranche_tarifaire/batterie_regime) consomment n'existait jusqu'ici que sur
l'aperçu TRANSITOIRE ``/ventes/etude-horaire/preview/`` — jamais persisté sur
un devis enregistré. Fixtures calquées sur
``test_cj2b_economies_publiques._CJ2bBase`` (Casablanca, table de référence
PVGIS, aucun accès réseau)."""
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase

from apps.crm.models import Client, Lead
from apps.stock.models import Produit
from apps.ventes.models import Devis, LigneDevis
from apps.ventes.services import rafraichir_dimensionnement_devis

User = get_user_model()

#: PIN DEPLACE LE 25/08/2026 — trois cles ADDITIVES : la doctrine d'optimum
#: rend ses deux horizons (dix ans pour des panneaux, sept pour du stockage) et
#: sa regle en clair, exactement comme ``regle_onduleur_min`` /
#: ``regle_stockage`` rendaient deja les leurs. Aucune cle n'a disparu : le
#: contrat que le moteur PDF et le payload public consomment est intact.
#:
#: QJR43 (29/08/2026) ajoute UNE clé, ``_empreinte`` : l'estampille des
#: entrées qui décide désormais si le bloc est périmé. Additive — aucun
#: consommateur (PDF, payload public, profils comparatifs) n'itère les clés,
#: tous lisent des clés NOMMÉES.
DIM_TOP_LEVEL_KEYS = {
    'critere', 'criteres_disponibles', 'regle_onduleur_min',
    'max_paliers_stockage', 'regle_stockage', 'tableau', 'recommandation',
    'motivation', 'recommandation_avec', 'motivation_avec', 'falaise',
    'meilleure_falaise',
    'horizon_marginal_pv_annees', 'horizon_marginal_batterie_annees',
    'regle_optimum',
    '_empreinte',
}


class _DimensionnementBase(TestCase):
    def _company(self, slug):
        from authentication.models import Company
        company = Company.objects.get_or_create(
            slug=slug, defaults={'nom': slug})[0]
        User.objects.get_or_create(
            username=f'{slug}-user',
            defaults={'password': 'x', 'company': company})
        return company

    def _devis(self, slug, *, mode='residentiel', avec_lead=True,
               facture_hiver=1800, avec_catalogue=True):
        company = self._company(slug)
        client_obj = Client.objects.get_or_create(
            company=company, nom=f'Client {slug}', defaults={})[0]
        lead = None
        if avec_lead:
            lead = Lead.objects.create(
                company=company, nom='Lead', prenom=slug,
                telephone='+212600000000', ville='Casablanca',
                facture_hiver=facture_hiver, ete_differente=False)
        devis = Devis.objects.create(
            company=company, reference=f'DEV-{slug.upper()}-01',
            client=client_obj, lead=lead, statut='envoye',
            taux_tva=Decimal('20'), mode_installation=mode,
            etude_params={})
        if avec_catalogue:
            produit = Produit.objects.create(
                company=company, nom='Panneau Canadien Solar 710W',
                prix_vente='1166.67', quantite_stock=50)
            LigneDevis.objects.create(
                devis=devis, produit=produit,
                designation='Panneau Canadien Solar 710W',
                quantite=Decimal('14'), prix_unitaire=Decimal('1166.67'),
                remise=Decimal('0'))
        return devis


class GateResidentielTests(_DimensionnementBase):
    def test_devis_non_residentiel_renvoie_none_sans_ecrire(self):
        devis = self._devis('t5-nonres', mode='industriel')
        self.assertIsNone(rafraichir_dimensionnement_devis(devis))
        devis.refresh_from_db()
        self.assertNotIn('dimensionnement', devis.etude_params or {})

    def test_devis_sans_societe_renvoie_none(self):
        devis = self._devis('t5-cosoc')
        devis.company = None
        self.assertIsNone(rafraichir_dimensionnement_devis(devis))


class ProfilNonExploitableTests(_DimensionnementBase):
    def test_sans_lead_ni_facture_renvoie_none_sans_cle(self):
        devis = self._devis('t5-sanslead', avec_lead=False)
        self.assertIsNone(rafraichir_dimensionnement_devis(devis))
        devis.refresh_from_db()
        self.assertNotIn('dimensionnement', devis.etude_params or {})

    def test_cle_devenue_non_exploitable_est_retiree(self):
        """Un bloc déjà posé, puis un profil qui redevient non exploitable
        (ex. lead supprimé) : la clé PÉRIMÉE est retirée plutôt que laissée
        (même règle Z2 que le bloc horaire), quand ``force=True``."""
        devis = self._devis('t5-retire')
        devis.etude_params = {'dimensionnement': {'tableau': []}}
        devis.save(update_fields=['etude_params'])
        devis.lead = None
        devis.save(update_fields=['lead'])
        self.assertIsNone(
            rafraichir_dimensionnement_devis(devis, force=True))
        devis.refresh_from_db()
        self.assertNotIn('dimensionnement', devis.etude_params or {})


class BlocPersisteTests(_DimensionnementBase):
    """Profil exploitable (lead + facture d'hiver réelle, Casablanca) : le
    tableau se calcule et se RANGE sur le devis — structure uniquement
    (le contenu exact du catalogue n'est pas le sujet de ce test)."""

    def test_bloc_pose_porte_les_cles_du_contrat_recommander_taille(self):
        devis = self._devis('t5-pose')
        resultat = rafraichir_dimensionnement_devis(devis)
        self.assertIsNotNone(resultat)
        self.assertEqual(set(resultat), DIM_TOP_LEVEL_KEYS)
        devis.refresh_from_db()
        self.assertEqual(
            devis.etude_params.get('dimensionnement'), resultat)

    def test_avec_force_un_bloc_deja_pose_est_recalcule(self):
        devis = self._devis('t5-force')
        devis.etude_params = {'dimensionnement': {'sentinelle': True}}
        devis.save(update_fields=['etude_params'])
        resultat = rafraichir_dimensionnement_devis(devis, force=True)
        self.assertNotEqual(resultat, {'sentinelle': True})
        self.assertEqual(set(resultat), DIM_TOP_LEVEL_KEYS)

    def test_ne_leve_jamais_meme_si_le_moteur_echoue(self):
        """Best-effort : une exception interne (catalogue/localisation
        indisponible) ne remonte jamais — ``None``, jamais une 500."""
        devis = self._devis('t5-echoue', avec_lead=True,
                            facture_hiver=None)
        # facture_hiver=None ⇒ profil_depuis_factures ne renvoie rien.
        self.assertIsNone(rafraichir_dimensionnement_devis(devis))


class EmpreinteEntreesTests(_DimensionnementBase):
    """QJR43 — le bloc est périmé par une ENTRÉE qui bouge, plus par rien.

    Avant, le test de fraîcheur était ``'dimensionnement' in etude_params`` :
    corriger la facture d'hiver du lead ne périmait RIEN et le commercial
    continuait de lire le tableau de la toute première lecture.
    """

    def _compteur_moteur(self):
        """Compte les appels RÉELS à ``recommander_taille`` (le balayage)."""
        from unittest import mock
        from apps.ventes import dimensionnement as module_dim
        vrai = module_dim.recommander_taille
        appels = []

        def espion(*args, **kwargs):
            appels.append(1)
            return vrai(*args, **kwargs)

        return mock.patch.object(module_dim, 'recommander_taille', espion), appels

    def test_facture_dhiver_modifiee_le_tableau_se_recalcule(self):
        """ROUGE avant QJR43 : la clé présente suffisait à servir l'ancien."""
        devis = self._devis('t5-empr-facture')
        premier = rafraichir_dimensionnement_devis(devis)
        self.assertIsNotNone(premier)
        empreinte_1 = premier['_empreinte']

        devis.lead.facture_hiver = 3200
        devis.lead.save(update_fields=['facture_hiver'])
        devis.refresh_from_db()

        second = rafraichir_dimensionnement_devis(devis)
        self.assertIsNotNone(second)
        self.assertNotEqual(second['_empreinte'], empreinte_1)
        devis.refresh_from_db()
        self.assertEqual(devis.etude_params['dimensionnement']['_empreinte'],
                         second['_empreinte'])

    def test_rien_n_a_bouge_aucun_balayage(self):
        devis = self._devis('t5-empr-stable')
        premier = rafraichir_dimensionnement_devis(devis)
        self.assertIsNotNone(premier)
        devis.refresh_from_db()

        patch, appels = self._compteur_moteur()
        with patch:
            second = rafraichir_dimensionnement_devis(devis)
        self.assertEqual(appels, [],
                         'aucune entrée n\'a bougé : le balayage ne doit pas '
                         'être rejoué')
        self.assertEqual(second['_empreinte'], premier['_empreinte'])

    def test_un_bloc_sans_empreinte_est_perime(self):
        """Rétro-compat : tout devis antérieur à QJR43 se recalcule UNE fois."""
        devis = self._devis('t5-empr-legacy')
        devis.etude_params = {'dimensionnement': {'sentinelle': True}}
        devis.save(update_fields=['etude_params'])

        resultat = rafraichir_dimensionnement_devis(devis, force=False)
        self.assertNotEqual(resultat, {'sentinelle': True})
        self.assertEqual(set(resultat), DIM_TOP_LEVEL_KEYS)

    def test_force_recalcule_meme_avec_une_empreinte_concordante(self):
        devis = self._devis('t5-empr-force')
        rafraichir_dimensionnement_devis(devis)
        devis.refresh_from_db()

        patch, appels = self._compteur_moteur()
        with patch:
            rafraichir_dimensionnement_devis(devis, force=True)
        self.assertEqual(len(appels), 1)
