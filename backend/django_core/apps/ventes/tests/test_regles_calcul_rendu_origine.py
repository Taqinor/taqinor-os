"""Décision fondateur 08/10/2026 — « nouveaux rendus seulement » : PREUVE
qu'un devis aux règles d'origine (``Devis.regles_calcul = 1``) est rendu
EXACTEMENT comme avant les correctifs moteur de #898 (AMOT8…AMOT59, AMOT70).

Golden ``golden/regles_calcul_origine.json`` : sha256 du dict masqué de
``build_quote_data`` rendu par le code du merge-base ``02700c0fb`` (AVANT
#898) pour 18 fixtures × 9 jeux d'options (les 13 fixtures SPL160 + TVA 0 %,
onduleur réseau + batterie, étude saisie, variante d'un devis signé,
échéancier à deux tranches, remise 2,5 % ; options dont ``variante_option``).
Ce test rend les MÊMES fixtures avec ``regles_calcul = 1`` sur le code
courant et compare. Seules quatre clés sont retirées des deux côtés : trois
ajouts sans chiffre (``entreprise.capital_social`` / ``forme_juridique``,
APDF21 ; le libellé ``agr_base_besoin_agronomique``, AMOT44) et le drapeau
``regles_calcul_origine`` lui-même.

Temps figé, réseau coupé (PVGIS hors-ligne), transaction annulée par cas —
même harnais que SPL160. Un futur correctif de chiffres qui change ce
golden n'est PAS passé par ``domain.regles_calcul.calcul_corrige``.
"""
import datetime
import decimal
import hashlib
import json
import re
import uuid
from decimal import Decimal
from pathlib import Path
from unittest import mock

from django.db import transaction
from django.test import TestCase
from freezegun import freeze_time

from apps.ventes.models import Devis, LigneDevis, ShareLink
from apps.ventes.tests._quote_engine_common import (
    DEUX_OPTIONS, make_client, make_company, make_devis, make_produit,
    make_user,
)

INSTANT = '2026-10-01T10:00:00+01:00'
CLES_IDS = {
    'id', 'pk', 'uuid', 'token', 'jeton', 'share_token', 'payment_token',
    'created_at', 'updated_at', 'date_creation', 'date_modification',
    'produit', 'produit_id', 'client', 'client_id', 'devis', 'devis_id',
    'lead', 'lead_id', 'ligne_id', 'company', 'company_id', 'user',
    'user_id', 'created_by', 'updated_by', '_company_id'}
_RE_UUID = re.compile(
    r'[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}')


def normaliser(obj):
    if isinstance(obj, dict):
        return {str(k): ('<id>' if str(k) in CLES_IDS and v is not None
                         else normaliser(v)) for k, v in obj.items()}
    if isinstance(obj, (list, tuple)):
        return [normaliser(v) for v in obj]
    if isinstance(obj, (datetime.datetime, datetime.date, datetime.time)):
        return '<date>'
    if isinstance(obj, uuid.UUID):
        return '<uuid>'
    if isinstance(obj, decimal.Decimal):
        return str(obj)
    if isinstance(obj, str) and _RE_UUID.search(obj):
        return _RE_UUID.sub('<uuid>', obj)
    return obj


LIGNES_DEUX = [
    ('Panneau Canadien Solar 710W', '14', '1272.73', '10'),
    ('Onduleur réseau Huawei 10kW Triphasé', '1', '16666.67', '20'),
    ('Onduleur hybride Deye 10kW Triphasé', '1', '23333.33', '20'),
    ('Batterie Dyness 10 kWh', '1', '25000', '20'),
    ('Installation', '1', '4000', '20'),
]
LIGNES_SANS = [
    ('Panneau Canadien Solar 710W', '10', '1272.73', '10'),
    ('Onduleur réseau Huawei 8kW', '1', '14000', '20'),
    ('Installation', '1', '3000', '20'),
]
LIGNES_AVEC = [
    ('Panneau Canadien Solar 710W', '10', '1272.73', '10'),
    ('Onduleur hybride Deye 8kW', '1', '21000', '20'),
    ('Batterie Dyness 10 kWh', '1', '25000', '20'),
]
# AMOT8 : onduleur réseau + batterie sans hybride.
LIGNES_RESEAU_BATTERIE = [
    ('Panneau Canadien Solar 710W', '10', '1272.73', '10'),
    ('Onduleur réseau Huawei 8kW', '1', '14000', '20'),
    ('Batterie Dyness 10 kWh', '1', '25000', '20'),
]
ETUDE_INDUSTRIEL = {
    'kwc': 49.7, 'production_annuelle': 79520, 'conso_annuelle': 120000,
    'taux_autoconso': 92, 'taux_couverture': 61,
    'economies_annuelles': 98000, 'payback': 3.4, 'prix_kwc': 6100,
    'prod_mensuelle': [6627] * 12, 'conso_mensuelle': [10000] * 12,
}
LIGNES_CI = [
    ('Onduleur réseau Huawei 50kW Triphasé', '1', '60000', '20'),
    ('Panneau mono 550W', '100', '1100', '20'),
]
LIGNES_AGRICOLE = [
    ('Pompe immergée OSP 30/8 10 CV', '1', '18000', '20'),
    ('Variateur VEICHI 7,5 kW', '1', '9000', '20'),
    ('Panneau mono 550W', '20', '1100', '20'),
]
ETUDE_AGRICOLE = {
    'pompe_cv': '10', 'pompe_kw': 7.5, 'type_pompe': 'immergee',
    'alim': 'tri', 'hmt_m': '60', 'debit_hmt_m3h': 30,
    'heures_pompage': 7, 'm3_jour': 210, 'champ_kwc': 10.65,
}
OPTIONS = {
    'defaut': {},
    'onepage': {'pdf_mode': 'onepage'},
    'include_etude': {'include_etude': True},
    'include_annexe_technique': {'include_annexe_technique': True},
    'include_calepinage': {'include_calepinage': True,
                           '_embed_roof_render': True,
                           '_embed_calepinage_planche': True},
    'devis_final_mensuel': {'devis_final': True, 'show_monthly': True},
    'langue_en': {'langue_sortie': 'en'},
    'langue_ar': {'langue_sortie': 'ar'},
    'variante_sans': {'variante_option': 'sans'},
}


def _lignes_variantees(devis, company, lignes):
    for desig, qte, pu, taux, variante in lignes:
        LigneDevis.objects.create(
            devis=devis,
            produit=make_produit(company, desig,
                                 f'{devis.reference[-6:]}-{desig[:8]}-{variante}',
                                 pu),
            designation=desig, quantite=Decimal(qte),
            prix_unitaire=Decimal(pu), remise=Decimal('0'),
            taux_tva=Decimal(taux), variante=variante)


GOLDEN = Path(__file__).resolve().parent / 'golden' / 'regles_calcul_origine.json'
#: Clés sans chiffre ajoutées après le merge-base, retirées des deux côtés.
CLES_HORS_RENDU_ORIGINE = (
    ('entreprise', 'capital_social'), ('entreprise', 'forme_juridique'),
    ('regles_calcul_origine',),
    ('libelles_document', 'agr_base_besoin_agronomique'))


def _empreinte(test, devis, data):
    """Même masque que le golden (ids, dates, jetons, pk en chemin), puis
    sha256 sans les clés hors rendu d'origine."""
    jetons = list(ShareLink.objects.filter(devis=devis)
                  .values_list('token', flat=True))
    texte = json.dumps(normaliser(data), sort_keys=True, default=str,
                       ensure_ascii=False, indent=1)
    for j in jetons:
        if j:
            texte = texte.replace(str(j), '<jeton>')
    pks = {devis.pk, devis.client_id, test.company.pk, test.user.pk}
    pks |= set(devis.lignes.values_list('pk', flat=True))
    pks |= set(devis.lignes.exclude(produit=None)
               .values_list('produit_id', flat=True))
    for pk in sorted(pks, reverse=True):
        texte = re.sub(r'(?<![0-9])/%d(?=[/._?#"])' % pk, '/<pk>', texte)
    d = json.loads(texte)
    for chemin in CLES_HORS_RENDU_ORIGINE:
        cible = d
        for k in chemin[:-1]:
            cible = cible.get(k) if isinstance(cible, dict) else None
        if isinstance(cible, dict):
            cible.pop(chemin[-1], None)
    return hashlib.sha256(json.dumps(d, sort_keys=True, ensure_ascii=False)
                          .encode('utf-8')).hexdigest()


class RenduReglesOrigineTests(TestCase):
    def setUp(self):
        self.freezer = freeze_time(INSTANT)
        self.freezer.start()
        self.addCleanup(self.freezer.stop)
        coupure = mock.patch('urllib.request.urlopen',
                             side_effect=OSError('hors réseau'))
        coupure.start()
        self.addCleanup(coupure.stop)
        self.company = make_company('diag-origine', 'Diag Origine SARL')
        self.user = make_user(self.company)
        self.client_obj = make_client(self.company)

    def _d(self, ref, lignes, **kw):
        etude = kw.pop('etude_params', None)
        devis = make_devis(self.company, self.user, self.client_obj, lignes,
                           remise_globale=kw.pop('remise_globale', '0'),
                           reference=ref, etude_params=etude)
        kw['regles_calcul'] = 1  # devis envoyé avant les correctifs
        if kw:
            Devis.objects.filter(pk=devis.pk).update(**kw)
            devis.refresh_from_db()
        return devis

    def _fixtures(self):
        fx = {}
        fx['residentiel_deux_options'] = self._d(
            'DEV-DIAG-001', LIGNES_DEUX, etude_params=dict(DEUX_OPTIONS))
        fx['mono_sans'] = self._d('DEV-DIAG-002', LIGNES_SANS)
        fx['mono_avec'] = self._d('DEV-DIAG-003', LIGNES_AVEC)
        var = self._d('DEV-DIAG-004', [], etude_params=dict(DEUX_OPTIONS))
        _lignes_variantees(var, self.company, [
            ('Panneau Canadien Solar 710W', '6', '1272.73', '10', 'sans'),
            ('Panneau Canadien Solar 710W', '8', '1272.73', '10', 'avec'),
            ('Onduleur réseau Huawei 5kW', '1', '9000', '20', 'sans'),
            ('Onduleur hybride Deye 6kW', '1', '15000', '20', 'avec'),
            ('Batterie Dyness 5 kWh', '1', '14000', '20', 'avec'),
        ])
        fx['variantes_divergentes'] = var
        div = self._d('DEV-DIAG-005', [])
        _lignes_variantees(div, self.company, [
            ('Panneau Canadien Solar 710W', '6', '1272.73', '10', 'sans'),
            ('Panneau Canadien Solar 710W', '8', '1272.73', '10', 'avec'),
            ('Onduleur réseau Huawei 5kW', '1', '9000', '20', ''),
        ])
        fx['panneaux_divergents_sans_deux_options'] = div
        fx['industriel_etude'] = self._d(
            'DEV-DIAG-006', LIGNES_CI, etude_params=dict(ETUDE_INDUSTRIEL),
            mode_installation='industriel')
        fx['commercial'] = self._d('DEV-DIAG-007', LIGNES_CI, etude_params={},
                                   mode_installation='commercial')
        fx['agricole'] = self._d('DEV-DIAG-008', LIGNES_AGRICOLE,
                                 etude_params=dict(ETUDE_AGRICOLE),
                                 mode_installation='agricole')
        fx['multivillas_x3'] = self._d(
            'DEV-DIAG-009', LIGNES_SANS, etude_params={'nombre_proprietes': 3})
        fx['accepte_signe'] = self._d(
            'DEV-DIAG-010', LIGNES_DEUX, etude_params=dict(DEUX_OPTIONS),
            statut='accepte', accepte_par_nom='Karim Alaoui',
            option_acceptee='avec_batterie')
        sec = self._d('DEV-DIAG-011', LIGNES_SANS)
        LigneDevis.objects.create(devis=sec, type_ligne='section',
                                  designation='Lot toiture', quantite=0,
                                  prix_unitaire=Decimal('0'), ordre=0)
        LigneDevis.objects.create(devis=sec, type_ligne='note',
                                  designation='Pose sous 3 semaines.',
                                  quantite=0, prix_unitaire=Decimal('0'),
                                  ordre=99)
        LigneDevis.objects.create(
            devis=sec, produit=make_produit(self.company, 'Monitoring 5 ans',
                                            'DIAG-OPT', '1500'),
            designation='Monitoring 5 ans', quantite=Decimal('1'),
            prix_unitaire=Decimal('1500'), remise=Decimal('0'),
            optionnelle=True)
        fx['sections_notes_optionnelles'] = sec
        fx['remise_globale'] = self._d('DEV-DIAG-012', LIGNES_SANS,
                                       remise_globale='2.5')
        fx['tva_mixte'] = self._d('DEV-DIAG-013', [
            ('Panneau Canadien Solar 710W', '10', '1272.73', '10'),
            ('Onduleur réseau Huawei 8kW', '1', '14000', '20'),
        ])
        # Cas ciblés des correctifs « nouveaux rendus seulement ».
        fx['tva_zero'] = self._d('DEV-DIAG-014', LIGNES_SANS,
                                 taux_tva=Decimal('0'))
        fx['reseau_batterie'] = self._d('DEV-DIAG-015',
                                        LIGNES_RESEAU_BATTERIE)
        fx['etude_saisie'] = self._d(
            'DEV-DIAG-016', LIGNES_DEUX, etude_params=dict(
                DEUX_OPTIONS, production_annuelle=14500,
                economies_annuelles=9800))
        fx['variante_signee'] = self._d(
            'DEV-DIAG-017', [], etude_params=dict(DEUX_OPTIONS),
            statut='accepte', accepte_par_nom='Karim Alaoui',
            option_acceptee='avec_batterie')
        _lignes_variantees(fx['variante_signee'], self.company, [
            ('Panneau Canadien Solar 710W', '8', '1272.73', '10', ''),
            ('Onduleur réseau Huawei 5kW', '1', '9000', '20', 'sans'),
            ('Onduleur hybride Deye 6kW', '1', '15000', '20', 'avec'),
            ('Batterie Dyness 5 kWh', '1', '14000', '20', 'avec'),
        ])
        fx['echeancier_deux_tranches'] = self._d(
            'DEV-DIAG-018', LIGNES_SANS, echeancier=[
                {'libelle': 'Acompte', 'type': 'pourcentage',
                 'pct_or_montant': 45},
                {'libelle': 'Solde', 'type': 'pourcentage',
                 'pct_or_montant': 55}])
        return fx

    def test_devis_envoye_rendu_comme_avant_les_correctifs(self):
        from apps.ventes.coherence.contexte import rendu_sans_reseau
        from apps.ventes.quote_engine.builder import build_quote_data
        golden = json.loads(GOLDEN.read_text(encoding='utf-8'))['cas']
        ecarts = []
        for nom_fx, devis in self._fixtures().items():
            for nom_opt, opts in OPTIONS.items():
                cle = f'{nom_fx}__{nom_opt}'
                with transaction.atomic():
                    frais = Devis.objects.get(pk=devis.pk)
                    self.assertEqual(frais.regles_calcul, 1)
                    with rendu_sans_reseau():
                        data = build_quote_data(frais, dict(opts))
                    if _empreinte(self, frais, data) != golden.get(cle):
                        ecarts.append(cle)
                    transaction.set_rollback(True)
        self.assertEqual(len(golden), 18 * len(OPTIONS))
        self.assertEqual(ecarts, [], 'devis aux règles d\'origine rendu '
                                     'autrement qu\'avant #898 : %s' % ecarts)

    def test_nouveau_rendu_prend_les_correctifs(self):
        """Test-du-test : aux règles CORRIGÉES (2), les cas ciblés des
        correctifs (TVA 0 % AMOT11, réseau + batterie AMOT8, étude saisie
        AMOT15) ne rendent PLUS le dict d'avant #898."""
        from apps.ventes.coherence.contexte import rendu_sans_reseau
        from apps.ventes.quote_engine.builder import build_quote_data
        golden = json.loads(GOLDEN.read_text(encoding='utf-8'))['cas']
        fixtures = self._fixtures()
        for nom_fx in ('tva_zero', 'reseau_batterie', 'etude_saisie'):
            with transaction.atomic():
                Devis.objects.filter(pk=fixtures[nom_fx].pk).update(
                    regles_calcul=2)
                frais = Devis.objects.get(pk=fixtures[nom_fx].pk)
                with rendu_sans_reseau():
                    data = build_quote_data(frais, {})
                self.assertNotEqual(_empreinte(self, frais, data),
                                    golden[f'{nom_fx}__defaut'], nom_fx)
                transaction.set_rollback(True)
