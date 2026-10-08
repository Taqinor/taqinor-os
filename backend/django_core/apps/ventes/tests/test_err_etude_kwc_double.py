"""ERR-ETUDE-KWC-DOUBLE — l'étude horaire d'un devis aux panneaux VARIANTÉS à
comptes ÉGAUX portait EXACTEMENT LE DOUBLE du kWc de ses lignes.

Constat (copie anonymisée de prod du 05/10/2026, dry-run fondateur du lot 5) :
7 devis dont l'étude horaire portait un kWc ≠ celui des lignes, 5 avec
étude = 2 × lignes. Cause reproduite : ``domain.etudes.puissances_etude_horaire``
ne traitait par option que les devis DIVERGENTS (comptes « sans » ≠ « avec ») ;
à comptes égaux (8 « sans » + 8 « avec »), ``divergents`` est faux et la
lecture sur TOUTES les lignes additionnait les deux paniers (16 × 710 W). Le
builder avait été corrigé pour le même cas (ACAL-NB2OPT, 06/10/2026), pas le
bloc horaire.

Rouge d'abord : sur l'arbre d'avant le correctif,
``puissances_etude_horaire`` rendait ``(11.36, None)`` et le bloc rangé
``kwc == 11.36``.

Réparation des devis existants : aucune dans ce commit — un dry-run des devis
ENVOYÉS touchés est exigé avant toute réparation
(``docs/claude-memory/reconfirm-client-visible-repairs.md``) ; le bloc se
recalcule de lui-même à la prochaine sauvegarde du devis (empreinte/kWc périmé).
"""
from apps.ventes.domain.etudes import puissances_etude_horaire
from apps.ventes.tests.test_etude_horaire_par_option import (
    KWC_AVEC, PANNEAU, _Base,
)

#: 8 « sans » + 8 « avec » : deux options au même champ PV.
LIGNES_EGALES = (
    (PANNEAU, '8', '1166.67', 'sans'),
    (PANNEAU, '8', '1166.67', 'avec'),
    ('Onduleur réseau Huawei 5kW Monophasé', '1', '12000.00', ''),
    ('Onduleur hybride Deye 5kW Monophasé', '1', '17000.00', ''),
    ('Batterie Dyness 5 kWh', '1', '16000.00', ''),
    ('Installation', '1', '4000.00', ''),
)
#: 16 × 710 W — la SOMME des deux paniers (le double).
KWC_DOUBLE = 11.36


class EtudeKwcDoubleTests(_Base):
    def test_puissance_d_une_option_jamais_la_somme(self):
        devis = self._devis('err-kwc-double-p', lignes=LIGNES_EGALES)
        kwc, kwc_sans = puissances_etude_horaire(devis)
        self.assertNotEqual(kwc, KWC_DOUBLE)
        self.assertEqual(kwc, KWC_AVEC)
        self.assertIsNone(kwc_sans)

    def test_le_bloc_range_porte_le_kwc_des_lignes(self):
        devis = self._rafraichir(
            self._devis('err-kwc-double-b', lignes=LIGNES_EGALES), force=True)
        bloc = devis.etude_params.get('etude_horaire')
        self.assertIsInstance(bloc, dict, 'étude horaire non calculée')
        self.assertEqual(bloc['kwc'], KWC_AVEC)
        self.assertNotIn('etude_horaire_sans', devis.etude_params)
