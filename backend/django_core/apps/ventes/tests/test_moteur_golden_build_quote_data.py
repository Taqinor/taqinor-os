"""SPL160 (a) — golden de ``build_quote_data`` AVANT toute scission du moteur
(capture seule, aucun déplacement).

Chaque fixture (résidentiel deux options, mono sans, mono avec, variantes
divergentes, panneaux divergents SANS deux options, industriel avec étude,
commercial, pompage agricole, multi-villas ×3, accepté/signé, sections +
notes + lignes optionnelles, remise globale, TVA 10/20 % mixte) est rendue
pour chaque jeu d'options (``{}``, une-page, ``include_etude``,
``include_annexe_technique``, ``include_calepinage`` + drapeaux serveur
``_embed_roof_render``/``_embed_calepinage_planche``, ``devis_final`` +
``show_monthly``, langue en, langue ar). UN json PAR CAS sous
``golden/moteur/build_quote_data/`` : sha256 du ``data`` masqué, liste
ORDONNÉE des clés (ordre = JSON public proposal-data) et nombre de lignes
``ShareLink`` du devis (E3 en crée une). Une tâche AGR/CIQ qui change un
chiffre re-capture SES cas seulement ; une tâche SPL ne re-capture JAMAIS.

Temps figé (freezegun) au 2026-10-01 10:00 Africa/Casablanca ; seules les
deux lectures d'images MinIO sont neutralisées
(``coherence.contexte.rendu_sans_reseau``) — jamais ``build_quote_data``.
Chaque cas tourne dans une transaction ANNULÉE : un ShareLink créé par un cas
ne change pas le suivant. Masque : jetons ShareLink du devis, clés
d'identifiant (``split_golden.normaliser``), pk en segment de chemin.

Capture (une fois, sur la pointe de main au démarrage de la lane) :
    UPDATE_GOLDEN=1 powershell -File scripts/test-backend.ps1 -RestoreDb \\
        -Modules "apps.ventes.tests.test_moteur_golden_build_quote_data"
Golden absent ⇒ rouge ; deux exécutions consécutives sans UPDATE_GOLDEN
donnent les mêmes hachages (déterminisme).
"""
import hashlib
import json
import os
import re
from decimal import Decimal
from pathlib import Path

from django.db import transaction
from django.test import TestCase
from freezegun import freeze_time

from apps.ventes.models import Devis, LigneDevis, ShareLink
from apps.ventes.tests import split_golden as sg
from apps.ventes.tests._quote_engine_common import (
    DEUX_OPTIONS, make_client, make_company, make_devis, make_produit,
    make_user,
)

DOSSIER = (Path(__file__).resolve().parent / 'golden' / 'moteur'
           / 'build_quote_data')
INSTANT = '2026-10-01T10:00:00+01:00'

CLES_IDS = sg.CLES_IDS_PAR_DEFAUT | {
    'produit', 'produit_id', 'client', 'client_id', 'devis', 'devis_id',
    'lead', 'lead_id', 'ligne_id', 'company', 'company_id', 'user',
    'user_id', 'created_by', 'updated_by'}

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

#: Jeux d'options (nom → pdf_options). Les drapeaux ``_embed_*`` sont SERVEUR
#: (hors liste blanche) : passés ici comme le fait ``generate_premium_devis_pdf``.
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


class MoteurGoldenBuildQuoteDataTests(TestCase):

    def setUp(self):
        self.freezer = freeze_time(INSTANT)
        self.freezer.start()
        self.addCleanup(self.freezer.stop)
        self.company = make_company('spl160-golden', 'SPL160 Golden SARL')
        self.user = make_user(self.company)
        self.client_obj = make_client(self.company)

    # ── fixtures ────────────────────────────────────────────────────────────
    def _d(self, ref, lignes, **kw):
        etude = kw.pop('etude_params', None)
        devis = make_devis(self.company, self.user, self.client_obj, lignes,
                           remise_globale=kw.pop('remise_globale', '0'),
                           reference=ref, etude_params=etude)
        if kw:
            Devis.objects.filter(pk=devis.pk).update(**kw)
            devis.refresh_from_db()
        return devis

    def _fixtures(self):
        fx = {}
        fx['residentiel_deux_options'] = self._d(
            'DEV-SPL160-001', LIGNES_DEUX, etude_params=dict(DEUX_OPTIONS))
        fx['mono_sans'] = self._d('DEV-SPL160-002', LIGNES_SANS)
        fx['mono_avec'] = self._d('DEV-SPL160-003', LIGNES_AVEC)
        var = self._d('DEV-SPL160-004', [],
                      etude_params=dict(DEUX_OPTIONS))
        _lignes_variantees(var, self.company, [
            ('Panneau Canadien Solar 710W', '6', '1272.73', '10', 'sans'),
            ('Panneau Canadien Solar 710W', '8', '1272.73', '10', 'avec'),
            ('Onduleur réseau Huawei 5kW', '1', '9000', '20', 'sans'),
            ('Onduleur hybride Deye 6kW', '1', '15000', '20', 'avec'),
            ('Batterie Dyness 5 kWh', '1', '14000', '20', 'avec'),
        ])
        fx['variantes_divergentes'] = var
        div = self._d('DEV-SPL160-005', [])
        _lignes_variantees(div, self.company, [
            ('Panneau Canadien Solar 710W', '6', '1272.73', '10', 'sans'),
            ('Panneau Canadien Solar 710W', '8', '1272.73', '10', 'avec'),
            ('Onduleur réseau Huawei 5kW', '1', '9000', '20', ''),
        ])
        fx['panneaux_divergents_sans_deux_options'] = div
        fx['industriel_etude'] = self._d(
            'DEV-SPL160-006', LIGNES_CI, etude_params=dict(ETUDE_INDUSTRIEL),
            mode_installation='industriel')
        fx['commercial'] = self._d('DEV-SPL160-007', LIGNES_CI,
                                   etude_params={},
                                   mode_installation='commercial')
        fx['agricole'] = self._d('DEV-SPL160-008', LIGNES_AGRICOLE,
                                 etude_params=dict(ETUDE_AGRICOLE),
                                 mode_installation='agricole')
        fx['multivillas_x3'] = self._d(
            'DEV-SPL160-009', LIGNES_SANS,
            etude_params={'nombre_proprietes': 3})
        fx['accepte_signe'] = self._d(
            'DEV-SPL160-010', LIGNES_DEUX, etude_params=dict(DEUX_OPTIONS),
            statut='accepte', accepte_par_nom='Karim Alaoui',
            option_acceptee='avec_batterie')
        sec = self._d('DEV-SPL160-011', LIGNES_SANS)
        LigneDevis.objects.create(devis=sec, type_ligne='section',
                                  designation='Lot toiture', quantite=0,
                                  prix_unitaire=Decimal('0'), ordre=0)
        LigneDevis.objects.create(devis=sec, type_ligne='note',
                                  designation='Pose sous 3 semaines.',
                                  quantite=0, prix_unitaire=Decimal('0'),
                                  ordre=99)
        LigneDevis.objects.create(
            devis=sec, produit=make_produit(self.company, 'Monitoring 5 ans',
                                            'SPL160-OPT', '1500'),
            designation='Monitoring 5 ans', quantite=Decimal('1'),
            prix_unitaire=Decimal('1500'), remise=Decimal('0'),
            optionnelle=True)
        fx['sections_notes_optionnelles'] = sec
        fx['remise_globale'] = self._d('DEV-SPL160-012', LIGNES_SANS,
                                       remise_globale='5')
        fx['tva_mixte'] = self._d('DEV-SPL160-013', [
            ('Panneau Canadien Solar 710W', '10', '1272.73', '10'),
            ('Onduleur réseau Huawei 8kW', '1', '14000', '20'),
        ])
        return fx

    # ── masque + empreinte ──────────────────────────────────────────────────
    def _empreinte(self, devis, data):
        jetons = list(ShareLink.objects.filter(devis=devis)
                      .values_list('token', flat=True))
        texte = json.dumps(sg.normaliser(data, CLES_IDS), sort_keys=True,
                           default=str, ensure_ascii=False)
        for jeton in jetons:
            if jeton:
                texte = texte.replace(str(jeton), '<jeton>')
        pks = {devis.pk, devis.client_id, self.company.pk, self.user.pk}
        pks |= set(devis.lignes.values_list('pk', flat=True))
        pks |= set(devis.lignes.exclude(produit=None)
                   .values_list('produit_id', flat=True))
        # Un pk n'est masqué que comme SEGMENT DE CHEMIN : jamais précédé
        # d'un chiffre. Sans ``(?<![0-9])``, une base ``--keepdb`` dont un
        # pk vaut 2026 masquait aussi l'année des dates « 01/10/2026 »
        # (``date``, ``valid_until``) — le golden variait d'une exécution à
        # l'autre selon la valeur des séquences.
        for pk in sorted(pks, reverse=True):
            texte = re.sub(r'(?<![0-9])/%d(?=[/._?#"])' % pk, '/<pk>', texte)
        return {
            'sha256': hashlib.sha256(texte.encode('utf-8')).hexdigest(),
            'cles': list(data.keys()),
            'sharelinks': len(jetons),
        }

    def _cas(self):
        from apps.ventes.coherence.contexte import rendu_sans_reseau
        from apps.ventes.quote_engine.builder import build_quote_data
        resultats = {}
        for nom_fx, devis in self._fixtures().items():
            for nom_opt, opts in OPTIONS.items():
                cle = f'{nom_fx}__{nom_opt}'
                with transaction.atomic():
                    devis_frais = Devis.objects.get(pk=devis.pk)
                    try:
                        with rendu_sans_reseau():
                            data = build_quote_data(devis_frais, dict(opts))
                        resultats[cle] = self._empreinte(devis_frais, data)
                    except Exception as exc:  # noqa: BLE001 — caractérisation
                        resultats[cle] = {'exception': type(exc).__name__}
                    transaction.set_rollback(True)
        return resultats

    def test_build_quote_data_identique_au_golden(self):
        resultats = self._cas()
        maj = os.environ.get('UPDATE_GOLDEN') == '1'
        if maj:
            DOSSIER.mkdir(parents=True, exist_ok=True)
        ecarts, manquants = [], []
        for cle, reel in sorted(resultats.items()):
            fichier = DOSSIER / f'{cle}.json'
            if maj:
                fichier.write_text(json.dumps(reel, indent=2,
                                              ensure_ascii=False) + '\n',
                                   encoding='utf-8')
            if not fichier.is_file():
                manquants.append(cle)
                continue
            if json.loads(fichier.read_text(encoding='utf-8')) != reel:
                ecarts.append(cle)
        self.assertEqual(manquants, [],
                         'golden non capturé : lancer une fois '
                         'UPDATE_GOLDEN=1 (voir la docstring)')
        self.assertEqual(ecarts, [], 'sortie de build_quote_data changée '
                                     'pour : %s' % ecarts)
        # Aucun cas n'est une exception silencieuse non capturée.
        self.assertEqual(len(resultats), 13 * len(OPTIONS))
