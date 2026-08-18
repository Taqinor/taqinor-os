"""GAMMES — offre à DEUX GAMMES paramétrable, envoi à la carte.

Décisions fondateur 2026-08-18 couvertes ici :
  * une gamme = une VARIANTE de devis (devis frère complet, version_parent) —
    jamais un second axe DANS un devis (l'axe batterie reste intact) ;
  * le libellé est une DONNÉE (``etude_params['gamme']``) — aucune marque
    codée en dur, aucun changement de modèle ;
  * ENVOI À LA CARTE : « les_deux » (DÉFAUT) expose la gamme sœur au lien
    client ; « seule » n'en laisse RIEN franchir la frontière publique ;
  * l'acceptation de la gamme choisie auto-refuse l'autre (YDOCF3) ;
  * UN PDF = UNE GAMME : chaque gamme a son propre jeton/PDF, jamais un
    document fusionné ;
  * les garanties du PDF dérivent de la composition réelle (repli constante).

Lancer :
    docker compose exec django_core python manage.py test \
        apps.ventes.tests.test_gammes_offre -v 2
"""
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient

from apps.crm.models import Client
from apps.stock.models import Produit
from apps.ventes.models import Devis, LigneDevis, ShareLink
from apps.ventes.public_views import _gammes_public, _variant_summaries
from apps.ventes.services import (
    GAMME_ENVOI_LES_DEUX, GAMME_ENVOI_SEULE, creer_variante_gamme,
    gamme_envoi, gamme_nom, gamme_soeur, regler_envoi_gamme,
)

User = get_user_model()


# ─── Helpers ───────────────────────────────────────────────────────────────

def make_company(slug='gamme-co'):
    from authentication.models import Company
    return Company.objects.get_or_create(
        slug=slug, defaults={'nom': 'Gamme Co'})[0]


def make_user(company, username=None):
    uname = username or f'u_{company.slug}'
    try:
        return User.objects.get(username=uname)
    except User.DoesNotExist:
        return User.objects.create_user(
            username=uname, password='x',
            role_legacy='responsable', company=company)


def make_client_obj(company):
    return Client.objects.create(
        company=company, nom='Alaoui', prenom='Salma',
        email='salma@gamme.ma', telephone='+212611000020')


def make_produit(company, nom, sku, prix_vente, prix_achat='1'):
    return Produit.objects.create(
        company=company, nom=nom, sku=sku,
        prix_vente=Decimal(str(prix_vente)),
        prix_achat=Decimal(str(prix_achat)),
        quantite_stock=50)


def make_devis(company, user, client_obj, ref, statut='brouillon'):
    return Devis.objects.create(
        company=company, reference=ref, client=client_obj,
        statut=statut, created_by=user)


def add_ligne(devis, produit, qty='6', pu='2000'):
    return LigneDevis.objects.create(
        devis=devis, produit=produit, designation=produit.nom,
        quantite=Decimal(str(qty)), prix_unitaire=Decimal(str(pu)),
        remise=Decimal('0'))


def url_gamme(devis_id):
    return f'/api/django/ventes/devis/{devis_id}/dupliquer-variante-gamme/'


def url_proposal(token):
    return f'/api/django/ventes/proposal/{token}/data/'


def url_accept(token):
    return f'/api/django/ventes/proposal/{token}/accept/'


class GammeBase(TestCase):
    def setUp(self):
        self.company = make_company('gamme-main')
        self.user = make_user(self.company)
        self.api = APIClient()
        self.api.force_authenticate(user=self.user)
        self.client_obj = make_client_obj(self.company)
        self.panneau = make_produit(
            self.company, 'Panneau 550W', 'P550-GAM', '2000', prix_achat='1200')
        self.onduleur = make_produit(
            self.company, 'Onduleur réseau 5kW', 'OND5-GAM', '9000',
            prix_achat='6000')

    def _paire(self, ref='DEV-GAM-001', nom='Premium', recommandee=False):
        source = make_devis(self.company, self.user, self.client_obj, ref)
        add_ligne(source, self.panneau, qty='10')
        add_ligne(source, self.onduleur, qty='1', pu='9000')
        soeur = creer_variante_gamme(
            source, nom, user=self.user, recommandee=recommandee)
        source.refresh_from_db()
        return source, soeur


# ─── 1. Création de la variante de gamme ───────────────────────────────────

class TestCreerVarianteGamme(GammeBase):
    """La gamme réutilise la mécanique de variantes : devis frère complet."""

    def test_soeur_liee_par_version_parent_et_active(self):
        source, soeur = self._paire('DEV-GAM-010')
        self.assertEqual(soeur.version_parent_id, source.pk)
        self.assertTrue(soeur.is_active)
        self.assertEqual(soeur.statut, Devis.Statut.BROUILLON)
        # Règle #4 : la source ne change pas de statut.
        self.assertEqual(source.statut, Devis.Statut.BROUILLON)

    def test_lignes_clonees_a_lidentique(self):
        source, soeur = self._paire('DEV-GAM-011')
        self.assertEqual(soeur.lignes.count(), source.lignes.count())
        qtes = sorted(float(x) for x in
                      soeur.lignes.values_list('quantite', flat=True))
        self.assertEqual(qtes, sorted(float(x) for x in
                                      source.lignes.values_list('quantite',
                                                                flat=True)))

    def test_libelles_poses_des_deux_cotes(self):
        source, soeur = self._paire('DEV-GAM-012', nom='Premium')
        self.assertEqual(gamme_nom(soeur), 'Premium')
        self.assertEqual(gamme_nom(source), 'Essentielle')
        # Par défaut le devis PORTEUR est la gamme recommandée.
        self.assertTrue(source.etude_params['gamme']['recommandee'])
        self.assertFalse(soeur.etude_params['gamme']['recommandee'])

    def test_libelle_libre_aucune_marque_codee_en_dur(self):
        source, soeur = self._paire('DEV-GAM-013', nom='Confort Atlas')
        self.assertEqual(gamme_nom(soeur), 'Confort Atlas')
        self.assertEqual(gamme_nom(source), 'Essentielle')

    def test_recommandee_sur_la_nouvelle_gamme(self):
        source, soeur = self._paire('DEV-GAM-014', recommandee=True)
        self.assertTrue(soeur.etude_params['gamme']['recommandee'])
        self.assertFalse(source.etude_params['gamme']['recommandee'])

    def test_etude_params_non_partages_entre_soeurs(self):
        source, soeur = self._paire('DEV-GAM-015')
        self.assertIsNot(source.etude_params, soeur.etude_params)
        self.assertNotEqual(source.etude_params['gamme']['nom'],
                            soeur.etude_params['gamme']['nom'])

    def test_endpoint_cree_la_paire(self):
        d = make_devis(self.company, self.user, self.client_obj, 'DEV-GAM-016')
        add_ligne(d, self.panneau, qty='8')
        resp = self.api.post(url_gamme(d.id), {'nom': 'Premium'},
                             format='json')
        self.assertEqual(resp.status_code, 201, resp.data)
        self.assertEqual(resp.data['gamme']['statut'], 'brouillon')
        noms = {g['nom'] for g in resp.data['gammes']}
        self.assertEqual(noms, {'Essentielle', 'Premium'})

    def test_endpoint_autre_societe_404(self):
        autre = make_company('gamme-autre')
        etranger = make_devis(autre, make_user(autre, 'u_gamme_autre'),
                              make_client_obj(autre), 'DEV-GAM-X')
        resp = self.api.post(url_gamme(etranger.id), {}, format='json')
        self.assertEqual(resp.status_code, 404)


# ─── 2. Mode d'envoi (à la carte) ──────────────────────────────────────────

class TestModeEnvoi(GammeBase):

    def test_defaut_les_deux(self):
        """DÉFAUT fondateur : les deux gammes (comme l'axe batterie)."""
        source, soeur = self._paire('DEV-GAM-020')
        self.assertEqual(gamme_envoi(source), GAMME_ENVOI_LES_DEUX)
        self.assertEqual(gamme_envoi(soeur), GAMME_ENVOI_LES_DEUX)

    def test_regler_seule_ecrit_des_deux_cotes(self):
        source, soeur = self._paire('DEV-GAM-021')
        regler_envoi_gamme(source, GAMME_ENVOI_SEULE)
        source.refresh_from_db()
        soeur.refresh_from_db()
        self.assertEqual(gamme_envoi(source), GAMME_ENVOI_SEULE)
        self.assertEqual(gamme_envoi(soeur), GAMME_ENVOI_SEULE)

    def test_mode_invalide_est_ignore(self):
        source, _ = self._paire('DEV-GAM-022')
        regler_envoi_gamme(source, 'nimporte_quoi')
        source.refresh_from_db()
        self.assertEqual(gamme_envoi(source), GAMME_ENVOI_LES_DEUX)

    def test_devis_sans_gamme_inchange(self):
        d = make_devis(self.company, self.user, self.client_obj, 'DEV-GAM-023')
        regler_envoi_gamme(d, GAMME_ENVOI_SEULE)
        d.refresh_from_db()
        self.assertEqual(d.etude_params or {}, {})
        self.assertIsNone(gamme_soeur(d))

    def test_envoi_whatsapp_pose_le_mode(self):
        source, soeur = self._paire('DEV-GAM-024')
        self.client_obj.telephone = '+212611000020'
        self.client_obj.save(update_fields=['telephone'])
        resp = self.api.post(
            f'/api/django/ventes/devis/{source.id}/whatsapp/',
            {'gamme_envoi': GAMME_ENVOI_SEULE}, format='json')
        self.assertEqual(resp.status_code, 200, resp.data)
        source.refresh_from_db()
        soeur.refresh_from_db()
        self.assertEqual(gamme_envoi(source), GAMME_ENVOI_SEULE)
        self.assertEqual(gamme_envoi(soeur), GAMME_ENVOI_SEULE)

    def test_share_link_expose_le_bloc_gamme(self):
        source, _ = self._paire('DEV-GAM-025')
        resp = self.api.post(
            f'/api/django/ventes/devis/{source.id}/share-link/',
            {}, format='json')
        self.assertEqual(resp.status_code, 200, resp.data)
        self.assertEqual(resp.data['gamme']['envoi'], GAMME_ENVOI_LES_DEUX)
        self.assertEqual(resp.data['gamme']['recommandee'], 'Essentielle')


# ─── 3. Charge utile publique ──────────────────────────────────────────────

class TestPayloadPublic(GammeBase):

    def test_les_deux_expose_la_soeur(self):
        source, soeur = self._paire('DEV-GAM-030', nom='Premium')
        bloc = _gammes_public(source, 50000.0)
        self.assertIsNotNone(bloc)
        self.assertEqual(bloc['envoi'], GAMME_ENVOI_LES_DEUX)
        self.assertEqual(bloc['courante']['nom'], 'Essentielle')
        self.assertTrue(bloc['courante']['recommandee'])
        self.assertEqual(bloc['soeur']['nom'], 'Premium')
        self.assertEqual(bloc['soeur']['reference'], soeur.reference)
        self.assertIn('/proposition/', bloc['soeur']['proposition_path'])

    def test_ecart_en_mad_absolus_signe(self):
        """L'écart est un MONTANT signé en MAD (sœur − gamme affichée), jamais
        un pourcentage : la page l'affiche « + X MAD » / « − X MAD »."""
        from apps.ventes.quote_engine.builder import display_totals
        source, soeur = self._paire('DEV-GAM-031')
        total_source = display_totals(source)['total']
        # La sœur est renchérie : son écart doit être POSITIF.
        for ligne in soeur.lignes.all():
            ligne.prix_unitaire = ligne.prix_unitaire + Decimal('1000')
            ligne.save(update_fields=['prix_unitaire'])
        bloc = _gammes_public(source, total_source)
        self.assertIsNotNone(bloc['soeur']['ecart_ttc'])
        self.assertGreater(bloc['soeur']['ecart_ttc'], 0)
        self.assertAlmostEqual(
            bloc['soeur']['ecart_ttc'],
            bloc['soeur']['total_ttc'] - bloc['courante']['total_ttc'], places=2)

    def test_comparatif_ne_garde_que_les_lignes_qui_different(self):
        source, soeur = self._paire('DEV-GAM-032')
        ligne = soeur.lignes.filter(designation='Panneau 550W').first()
        ligne.quantite = Decimal('14')
        ligne.save(update_fields=['quantite'])
        bloc = _gammes_public(source, 50000.0)
        designations = [r['designation'] for r in bloc['comparatif']]
        self.assertEqual(designations, ['Panneau 550W'])
        self.assertEqual(bloc['comparatif'][0]['quantite'], 10.0)
        self.assertEqual(bloc['comparatif'][0]['quantite_soeur'], 14.0)

    def test_comparatif_couvre_une_ligne_absente_dune_gamme(self):
        source, soeur = self._paire('DEV-GAM-033')
        batterie = make_produit(self.company, 'Batterie 5 kWh', 'BAT-GAM',
                                '12000')
        add_ligne(soeur, batterie, qty='1', pu='12000')
        bloc = _gammes_public(source, 50000.0)
        rows = {r['designation']: r for r in bloc['comparatif']}
        self.assertIn('Batterie 5 kWh', rows)
        self.assertNotIn('quantite', rows['Batterie 5 kWh'])
        self.assertEqual(rows['Batterie 5 kWh']['quantite_soeur'], 1.0)

    def test_mode_seule_ne_laisse_rien_passer(self):
        source, soeur = self._paire('DEV-GAM-034', nom='Premium')
        regler_envoi_gamme(source, GAMME_ENVOI_SEULE)
        source.refresh_from_db()
        self.assertIsNone(_gammes_public(source, 50000.0))
        # ... et la sœur ne réapparaît pas non plus par la bande
        # « Autres tailles proposées ».
        refs = [v['reference'] for v in _variant_summaries(source)]
        self.assertNotIn(soeur.reference, refs)

    def test_soeur_de_gamme_exclue_des_autres_tailles(self):
        """Même en mode « les_deux » : jamais de doublon avec le bloc gammes."""
        source, soeur = self._paire('DEV-GAM-035')
        refs = [v['reference'] for v in _variant_summaries(source)]
        self.assertNotIn(soeur.reference, refs)

    def test_payload_public_expose_gammes_et_jamais_prix_achat(self):
        source, soeur = self._paire('DEV-GAM-036', nom='Premium')
        link = ShareLink.for_devis(source)
        anon = APIClient()
        resp = anon.get(url_proposal(link.token))
        self.assertEqual(resp.status_code, 200, resp.data)
        self.assertIsNotNone(resp.data.get('gammes'))
        self.assertEqual(resp.data['gammes']['soeur']['nom'], 'Premium')
        brut = str(resp.data)
        self.assertNotIn('prix_achat', brut)
        self.assertNotIn('marge', brut)

    def test_payload_public_mode_seule_sans_gammes(self):
        source, _ = self._paire('DEV-GAM-037')
        regler_envoi_gamme(source, GAMME_ENVOI_SEULE)
        link = ShareLink.for_devis(source)
        resp = APIClient().get(url_proposal(link.token))
        self.assertEqual(resp.status_code, 200)
        self.assertIsNone(resp.data.get('gammes'))

    def test_devis_sans_gamme_payload_inchange(self):
        d = make_devis(self.company, self.user, self.client_obj, 'DEV-GAM-038')
        add_ligne(d, self.panneau, qty='6')
        link = ShareLink.for_devis(d)
        resp = APIClient().get(url_proposal(link.token))
        self.assertEqual(resp.status_code, 200)
        self.assertIsNone(resp.data.get('gammes'))


# ─── 4. Acceptation de la gamme choisie ────────────────────────────────────

class TestAcceptationGamme(GammeBase):

    def test_signer_la_soeur_auto_refuse_la_gamme_non_retenue(self):
        """Le jeton de la gamme choisie signe SON devis (loi 53-05) et
        effondre l'autre gamme (« variante non retenue », YDOCF3)."""
        source, soeur = self._paire('DEV-GAM-040', nom='Premium')
        lien_soeur = ShareLink.for_devis(soeur)
        resp = APIClient().post(url_accept(lien_soeur.token), {
            'nom': 'Salma Alaoui',
            'consent_esign': True,
        }, format='json')
        self.assertEqual(resp.status_code, 200, resp.data)
        soeur.refresh_from_db()
        source.refresh_from_db()
        self.assertEqual(soeur.statut, Devis.Statut.ACCEPTE)
        self.assertEqual(soeur.accepte_par_nom, 'Salma Alaoui')
        self.assertEqual(source.statut, Devis.Statut.REFUSE)
        self.assertEqual(source.motif_refus, 'variante non retenue')
        self.assertFalse(source.is_active)

    def test_signature_referencee_sur_la_gamme_choisie(self):
        from apps.ventes.models import DevisSignature
        source, soeur = self._paire('DEV-GAM-041')
        lien_soeur = ShareLink.for_devis(soeur)
        APIClient().post(url_accept(lien_soeur.token), {
            'nom': 'Salma Alaoui', 'consent_esign': True,
        }, format='json')
        sig = DevisSignature.objects.filter(devis=soeur).first()
        self.assertIsNotNone(sig)
        self.assertFalse(DevisSignature.objects.filter(devis=source).exists())

    def test_gamme_refusee_disparait_du_choix(self):
        source, soeur = self._paire('DEV-GAM-042')
        lien_soeur = ShareLink.for_devis(soeur)
        APIClient().post(url_accept(lien_soeur.token), {
            'nom': 'Salma Alaoui', 'consent_esign': True,
        }, format='json')
        soeur.refresh_from_db()
        self.assertIsNone(gamme_soeur(soeur))
        self.assertIsNone(_gammes_public(soeur, 50000.0))


# ─── 5. UN PDF = UNE GAMME ─────────────────────────────────────────────────

class TestPdfParGamme(GammeBase):

    def test_chaque_gamme_a_son_propre_jeton(self):
        source, soeur = self._paire('DEV-GAM-050')
        t_source = ShareLink.for_devis(source).token
        t_soeur = ShareLink.for_devis(soeur).token
        self.assertNotEqual(t_source, t_soeur)

    def test_le_lien_de_la_carte_pointe_le_jeton_de_la_soeur(self):
        """Chaque carte de gamme ouvre le document ET le PDF de SA gamme —
        jamais un PDF fusionné des deux gammes."""
        source, soeur = self._paire('DEV-GAM-051')
        bloc = _gammes_public(source, 50000.0)
        t_soeur = ShareLink.objects.filter(devis=soeur).first().token
        self.assertIn(t_soeur, bloc['soeur']['proposition_path'])

    def test_le_payload_du_jeton_soeur_rend_la_soeur(self):
        source, soeur = self._paire('DEV-GAM-052', nom='Premium')
        lien = ShareLink.for_devis(soeur)
        resp = APIClient().get(url_proposal(lien.token))
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.data['reference'], soeur.reference)
        self.assertEqual(resp.data['gammes']['courante']['nom'], 'Premium')
        self.assertEqual(resp.data['gammes']['soeur']['nom'], 'Essentielle')


# ─── 6. Garanties du PDF dérivées de la composition ────────────────────────

class TestGarantiesDerivees(TestCase):
    """La bande « Nos garanties » lit les durées CATALOGUE des produits du
    devis rendu ; sans donnée produit, la constante d'aujourd'hui ; sans
    composant reconnu ni constante, OMISSION (jamais un chiffre inventé)."""

    def _labels(self, rows):
        from apps.ventes.quote_engine.residential import theme
        return {label: n for n, _u, label, _sub in
                theme.warranties_for({'sans_items': rows})}

    def test_sans_donnee_produit_repli_sur_la_constante(self):
        from apps.ventes.quote_engine.residential import theme
        rows = [
            {'designation': 'Panneau Canadian Solar 710W'},
            {'designation': 'Onduleur réseau Huawei 5kW'},
        ]
        self.assertEqual(theme.warranties_for({'sans_items': rows}),
                         list(theme.WARRANTIES))

    def test_durees_produit_prises_en_compte(self):
        labels = self._labels([
            {'designation': 'Panneau Trina 600W', 'garantie_mois': 300,
             'garantie_production_mois': 360},
            {'designation': 'Onduleur réseau Deye 5kW', 'garantie_mois': 144},
        ])
        self.assertEqual(labels['Panneaux'], '25')
        self.assertEqual(labels['Performance'], '30')
        self.assertEqual(labels['Onduleur'], '12')
        self.assertEqual(labels['Installation'], '2')

    def test_composant_absent_est_omis(self):
        labels = self._labels([{'designation': 'Pompe solaire OSP 30-12'}])
        self.assertNotIn('Panneaux', labels)
        self.assertNotIn('Onduleur', labels)
        self.assertIn('Installation', labels)

    def test_batterie_sans_duree_produit_est_omise(self):
        labels = self._labels([
            {'designation': 'Panneau Trina 600W'},
            {'designation': 'Batterie Lithium 5 kWh'},
        ])
        self.assertNotIn('Batterie', labels)

    def test_batterie_avec_duree_produit_apparait(self):
        labels = self._labels([
            {'designation': 'Batterie Lithium 5 kWh', 'garantie_mois': 120},
        ])
        self.assertEqual(labels['Batterie'], '10')

    def test_performance_derivee_ne_reprend_pas_le_sous_libelle_chiffre(self):
        from apps.ventes.quote_engine.residential import theme
        rows = [{'designation': 'Panneau Trina 600W',
                 'garantie_production_mois': 300}]
        subs = {label: sub for _n, _u, label, sub in
                theme.warranties_for({'sans_items': rows})}
        self.assertEqual(subs['Performance'], 'performance linéaire')

    def test_ligne_de_devis_porte_les_durees_catalogue(self):
        """``builder._line_to_item`` injecte les durées structurées (elles
        alimentent la dérivation ci-dessus)."""
        from apps.ventes.quote_engine.builder import _line_to_item
        company = make_company('gamme-gar')
        user = make_user(company, 'u_gamme_gar')
        client_obj = make_client_obj(company)
        produit = Produit.objects.create(
            company=company, nom='Panneau Trina 600W', sku='PAN-GAR',
            prix_vente=Decimal('2000'), prix_achat=Decimal('1000'),
            quantite_stock=10, garantie_mois=300,
            garantie_production_mois=360)
        devis = make_devis(company, user, client_obj, 'DEV-GAM-060')
        ligne = add_ligne(devis, produit, qty='10')
        item = _line_to_item(ligne, Decimal('20'))
        self.assertEqual(item['garantie_mois'], 300)
        self.assertEqual(item['garantie_production_mois'], 360)
