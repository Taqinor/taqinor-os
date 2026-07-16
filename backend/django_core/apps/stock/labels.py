"""N20 — Étiquettes QR/code-barres pour SKU stock & systèmes installés.

OBJECTIF : produire des étiquettes imprimables (HTML → PDF WeasyPrint) portant
un code SCANNABLE qui encode un jeton stable (`PRODUIT:<id>` / `SYSTEME:<id>`)
plus un texte lisible (nom + référence). Le code scanné est ensuite résolu
côté serveur (voir `views.resolve_code`).

CONTRAINTE : aucune nouvelle dépendance pip (un ajout serait bloquant). On
génère donc le QR « maison » en SVG inline — un encodeur QR autonome (mode
octet, niveau de correction M, version choisie automatiquement) implémenté
ici, sans bibliothèque externe. WeasyPrint (déjà présent) rend le SVG dans le
PDF. Un repli code-barres CODE128 (également SVG maison) reste disponible si
l'on veut un format linéaire.

Aucune donnée sensible n'est encodée (jamais de prix d'achat / marge) : le
jeton ne contient qu'un préfixe + un identifiant interne.
"""
from __future__ import annotations

# ─────────────────────────────────────────────────────────────────────────────
# Encodeur QR autonome (mode octet, EC niveau M). Sans dépendance externe.
#
# Couvre les versions 1..10 (jusqu'à ~ 213 octets en niveau M) — largement
# suffisant pour des jetons courts type « PRODUIT:1234 ». L'implémentation
# applique : encodage octet, correction d'erreur Reed-Solomon, placement des
# modules (finders, timing, alignment, format), masque (on évalue les 8 et on
# garde le meilleur score) et renvoie une matrice booléenne.
# ─────────────────────────────────────────────────────────────────────────────

# Galois field tables (GF(256), primitive 0x11d) pour Reed-Solomon.
_GF_EXP = [0] * 512
_GF_LOG = [0] * 256


def _init_gf():
    x = 1
    for i in range(255):
        _GF_EXP[i] = x
        _GF_LOG[x] = i
        x <<= 1
        if x & 0x100:
            x ^= 0x11d
    for i in range(255, 512):
        _GF_EXP[i] = _GF_EXP[i - 255]


_init_gf()


def _gf_mul(a, b):
    if a == 0 or b == 0:
        return 0
    return _GF_EXP[_GF_LOG[a] + _GF_LOG[b]]


def _rs_generator_poly(nsym):
    g = [1]
    for i in range(nsym):
        g2 = [0] * (len(g) + 1)
        for j in range(len(g)):
            g2[j] ^= _gf_mul(g[j], 1)
            g2[j + 1] ^= _gf_mul(g[j], _GF_EXP[i])
        g = g2
    return g


def _rs_encode(data, nsym):
    gen = _rs_generator_poly(nsym)
    res = list(data) + [0] * nsym
    for i in range(len(data)):
        coef = res[i]
        if coef != 0:
            for j in range(len(gen)):
                res[i + j] ^= _gf_mul(gen[j], coef)
    return res[len(data):]


# Nombre total de codewords de DONNÉES par version, niveau M (versions 1..10).
_DATA_CODEWORDS_M = {
    1: 16, 2: 28, 3: 44, 4: 64, 5: 86, 6: 108, 7: 124, 8: 154, 9: 182, 10: 216,
}
# Nombre de codewords de correction par bloc, niveau M (versions 1..10).
_EC_PER_BLOCK_M = {
    1: 10, 2: 16, 3: 26, 4: 18, 5: 24, 6: 16, 7: 18, 8: 22, 9: 22, 10: 26,
}
# Nombre de blocs, niveau M (versions 1..10).
_BLOCKS_M = {
    1: 1, 2: 1, 3: 1, 4: 2, 5: 2, 6: 4, 7: 4, 8: 4, 9: 5, 10: 5,
}
# Centres des patterns d'alignement par version (versions 1..10).
_ALIGN_POS = {
    1: [], 2: [6, 18], 3: [6, 22], 4: [6, 26], 5: [6, 30], 6: [6, 34],
    7: [6, 22, 38], 8: [6, 24, 42], 9: [6, 26, 46], 10: [6, 28, 50],
}


def _choose_version(nbytes):
    for v in range(1, 11):
        # En-tête = 4 bits mode + 8/16 bits compteur. On réserve ~2 octets.
        capacity = _DATA_CODEWORDS_M[v] - 3
        if nbytes <= capacity:
            return v
    raise ValueError('Jeton trop long pour un QR version ≤ 10.')


def _encode_data_bits(data: bytes, version: int):
    bits = []

    def put(value, length):
        for i in range(length - 1, -1, -1):
            bits.append((value >> i) & 1)

    put(0b0100, 4)                          # mode octet
    put(len(data), 16 if version >= 10 else 8)   # compteur
    for byte in data:
        put(byte, 8)
    total = _DATA_CODEWORDS_M[version] * 8
    put(0, min(4, total - len(bits)))       # terminateur
    while len(bits) % 8 != 0:
        bits.append(0)
    # Pad bytes alternés.
    pad = [0xEC, 0x11]
    i = 0
    while len(bits) < total:
        for b in range(7, -1, -1):
            bits.append((pad[i % 2] >> b) & 1)
        i += 1
    # bits → codewords.
    codewords = []
    for k in range(0, len(bits), 8):
        byte = 0
        for b in range(8):
            byte = (byte << 1) | bits[k + b]
        codewords.append(byte)
    return codewords


def _interleave(codewords, version):
    nblocks = _BLOCKS_M[version]
    total_data = _DATA_CODEWORDS_M[version]
    ec_per = _EC_PER_BLOCK_M[version]
    base = total_data // nblocks
    extra = total_data % nblocks
    blocks = []
    idx = 0
    for b in range(nblocks):
        size = base + (1 if b >= nblocks - extra else 0)
        data = codewords[idx:idx + size]
        idx += size
        ec = _rs_encode(data, ec_per)
        blocks.append((data, ec))
    # Interleave data, puis EC.
    result = []
    maxd = max(len(d) for d, _ in blocks)
    for i in range(maxd):
        for d, _ in blocks:
            if i < len(d):
                result.append(d[i])
    for i in range(ec_per):
        for _, ec in blocks:
            result.append(ec[i])
    return result


def _make_matrix(version):
    size = version * 4 + 17
    m = [[None] * size for _ in range(size)]
    return m, size


def _place_finder(m, size, r, c):
    for dr in range(-1, 8):
        for dc in range(-1, 8):
            rr, cc = r + dr, c + dc
            if 0 <= rr < size and 0 <= cc < size:
                if dr in (0, 6) and 0 <= dc <= 6:
                    m[rr][cc] = 1
                elif dc in (0, 6) and 0 <= dr <= 6:
                    m[rr][cc] = 1
                elif 2 <= dr <= 4 and 2 <= dc <= 4:
                    m[rr][cc] = 1
                else:
                    m[rr][cc] = 0


def _place_patterns(m, size, version):
    _place_finder(m, size, 0, 0)
    _place_finder(m, size, 0, size - 7)
    _place_finder(m, size, size - 7, 0)
    # Timing.
    for i in range(8, size - 8):
        bit = 1 if i % 2 == 0 else 0
        if m[6][i] is None:
            m[6][i] = bit
        if m[i][6] is None:
            m[i][6] = bit
    # Alignment.
    centers = _ALIGN_POS[version]
    for r in centers:
        for c in centers:
            if (r, c) in ((6, 6), (6, size - 7), (size - 7, 6)):
                continue
            # Évite le chevauchement avec les finders.
            if (r <= 7 and c <= 7) or (r <= 7 and c >= size - 8) or \
               (r >= size - 8 and c <= 7):
                continue
            for dr in range(-2, 3):
                for dc in range(-2, 3):
                    rr, cc = r + dr, c + dc
                    if max(abs(dr), abs(dc)) == 2 or (dr == 0 and dc == 0):
                        m[rr][cc] = 1
                    else:
                        m[rr][cc] = 0
    # Dark module.
    m[size - 8][8] = 1


def _reserve_format(m, size):
    reserved = set()
    for i in range(9):
        reserved.add((8, i))
        reserved.add((i, 8))
    for i in range(8):
        reserved.add((8, size - 1 - i))
        reserved.add((size - 1 - i, 8))
    return reserved


def _place_data(m, size, data_cw, reserved):
    bits = []
    for cw in data_cw:
        for b in range(7, -1, -1):
            bits.append((cw >> b) & 1)
    idx = 0
    col = size - 1
    upward = True
    while col > 0:
        if col == 6:
            col -= 1
        rng = range(size - 1, -1, -1) if upward else range(size)
        for row in rng:
            for c in (col, col - 1):
                if m[row][c] is None and (row, c) not in reserved:
                    bit = bits[idx] if idx < len(bits) else 0
                    m[row][c] = bit
                    idx += 1
        upward = not upward
        col -= 2


_MASK_FUNCS = [
    lambda r, c: (r + c) % 2 == 0,
    lambda r, c: r % 2 == 0,
    lambda r, c: c % 3 == 0,
    lambda r, c: (r + c) % 3 == 0,
    lambda r, c: (r // 2 + c // 3) % 2 == 0,
    lambda r, c: (r * c) % 2 + (r * c) % 3 == 0,
    lambda r, c: ((r * c) % 2 + (r * c) % 3) % 2 == 0,
    lambda r, c: ((r + c) % 2 + (r * c) % 3) % 2 == 0,
]


def _format_bits(mask_id):
    # Niveau M = 00 ; format info = 5 bits (EC level 2 bits + mask 3 bits).
    ec = 0b00  # M
    data = (ec << 3) | mask_id
    g = 0b10100110111
    v = data << 10
    for i in range(14, 9, -1):
        if (v >> i) & 1:
            v ^= g << (i - 10)
    fmt = ((data << 10) | v) ^ 0b101010000010010
    return [(fmt >> i) & 1 for i in range(14, -1, -1)]


def _place_format(m, size, mask_id):
    bits = _format_bits(mask_id)
    # Positions standard du format autour des finders.
    coords1 = [(8, 0), (8, 1), (8, 2), (8, 3), (8, 4), (8, 5), (8, 7),
               (8, 8), (7, 8), (5, 8), (4, 8), (3, 8), (2, 8), (1, 8), (0, 8)]
    for bit, (r, c) in zip(bits, coords1):
        m[r][c] = bit
    coords2 = [(size - 1, 8), (size - 2, 8), (size - 3, 8), (size - 4, 8),
               (size - 5, 8), (size - 6, 8), (size - 7, 8),
               (8, size - 8), (8, size - 7), (8, size - 6), (8, size - 5),
               (8, size - 4), (8, size - 3), (8, size - 2), (8, size - 1)]
    for bit, (r, c) in zip(bits, coords2):
        m[r][c] = bit


def _penalty(m, size):
    score = 0
    # Règle 1 — runs de 5+ même couleur (lignes & colonnes).
    cols = [[m[r][c] for r in range(size)] for c in range(size)]
    for line in list(m) + cols:
        run = 1
        for i in range(1, size):
            if line[i] == line[i - 1]:
                run += 1
            else:
                if run >= 5:
                    score += 3 + (run - 5)
                run = 1
        if run >= 5:
            score += 3 + (run - 5)
    # Règle 2 — blocs 2x2.
    for r in range(size - 1):
        for c in range(size - 1):
            v = m[r][c]
            if v == m[r][c + 1] == m[r + 1][c] == m[r + 1][c + 1]:
                score += 3
    return score


def _is_data_module(size, r, c, version):
    """Vrai si (r,c) est un module de données/EC (pas un pattern fonctionnel)."""
    # Finders + séparateurs.
    if (r <= 8 and c <= 8) or (r <= 8 and c >= size - 8) or \
       (r >= size - 8 and c <= 8):
        return False
    # Timing.
    if r == 6 or c == 6:
        return False
    # Alignment.
    centers = _ALIGN_POS[version]
    for ar in centers:
        for ac in centers:
            if (ar, ac) in ((6, 6), (6, size - 7), (size - 7, 6)):
                continue
            if abs(r - ar) <= 2 and abs(c - ac) <= 2:
                return False
    return True


def qr_matrix(text: str):
    """Renvoie la matrice booléenne d'un QR encodant `text` (mode octet, M)."""
    data = text.encode('utf-8')
    version = _choose_version(len(data))
    codewords = _encode_data_bits(data, version)
    final_cw = _interleave(codewords, version)

    base, size = _make_matrix(version)
    _place_patterns(base, size, version)
    reserved = _reserve_format(base, size)
    _place_data(base, size, final_cw, reserved)

    # Choisit le meilleur masque.
    best = None
    best_score = None
    for mask_id in range(8):
        cand = [row[:] for row in base]
        fn = _MASK_FUNCS[mask_id]
        for r in range(size):
            for c in range(size):
                if (r, c) in reserved:
                    continue
                if _is_data_module(size, r, c, version):
                    if fn(r, c):
                        cand[r][c] ^= 1
        _place_format(cand, size, mask_id)
        sc = _penalty(cand, size)
        if best_score is None or sc < best_score:
            best_score = sc
            best = cand
    return [[bool(v) for v in row] for row in best]


def qr_svg(text: str, box: int = 4, quiet: int = 4) -> str:
    """Rend un QR (matrice → SVG inline) ; modules noirs sur fond blanc."""
    matrix = qr_matrix(text)
    n = len(matrix)
    dim = (n + quiet * 2) * box
    rects = []
    for r in range(n):
        for c in range(n):
            if matrix[r][c]:
                x = (c + quiet) * box
                y = (r + quiet) * box
                rects.append(
                    f'<rect x="{x}" y="{y}" width="{box}" height="{box}"/>')
    return (
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{dim}" '
        f'height="{dim}" viewBox="0 0 {dim} {dim}" shape-rendering="crispEdges">'
        f'<rect width="{dim}" height="{dim}" fill="#fff"/>'
        f'<g fill="#000">{"".join(rects)}</g></svg>'
    )


# ─────────────────────────────────────────────────────────────────────────────
# Repli code-barres CODE128 (SVG maison, sans dépendance). Encode le même jeton
# sous forme linéaire si l'on préfère un code-barres à un QR.
# ─────────────────────────────────────────────────────────────────────────────

# Largeurs des 107 symboles CODE128 (chaque symbole = motif de barres/espaces).
_CODE128_PATTERNS = [
    "212222", "222122", "222221", "121223", "121322", "131222", "122213",
    "122312", "132212", "221213", "221312", "231212", "112232", "122132",
    "122231", "113222", "123122", "123221", "223211", "221132", "221231",
    "213212", "223112", "312131", "311222", "321122", "321221", "312212",
    "322112", "322211", "212123", "212321", "232121", "111323", "131123",
    "131321", "112313", "132113", "132311", "211313", "231113", "231311",
    "112133", "112331", "132131", "113123", "113321", "133121", "313121",
    "211331", "231131", "213113", "213311", "213131", "311123", "311321",
    "331121", "312113", "312311", "332111", "314111", "221411", "431111",
    "111224", "111422", "121124", "121421", "141122", "141221", "112214",
    "112412", "122114", "122411", "142112", "142211", "241211", "221114",
    "413111", "241112", "134111", "111242", "121142", "121241", "114212",
    "124112", "124211", "411212", "421112", "421211", "212141", "214121",
    "412121", "111143", "111341", "131141", "114113", "114311", "411113",
    "411311", "113141", "114131", "311141", "411131", "211412", "211214",
    "211232",
]
_CODE128_STOP = "2331112"


def code128b_svg(text: str, bar: int = 2, height: int = 60) -> str:
    """Rend un code-barres CODE128 (jeu B) en SVG inline. ASCII imprimable."""
    # Restreint aux caractères ASCII imprimables (32..126) du jeu B.
    cleaned = ''.join(ch for ch in text if 32 <= ord(ch) <= 126)
    start_b = 104
    values = [start_b]
    for ch in cleaned:
        values.append(ord(ch) - 32)
    checksum = start_b
    for i, v in enumerate(values[1:], start=1):
        checksum += v * i
    checksum %= 103
    values.append(checksum)
    patterns = [_CODE128_PATTERNS[v] for v in values] + [_CODE128_STOP]

    x = 10
    bars = []
    for pat in patterns:
        dark = True
        for w in pat:
            width = int(w) * bar
            if dark:
                bars.append(
                    f'<rect x="{x}" y="0" width="{width}" '
                    f'height="{height}"/>')
            x += width
            dark = not dark
    total = x + 10
    return (
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{total}" '
        f'height="{height}" viewBox="0 0 {total} {height}">'
        f'<rect width="{total}" height="{height}" fill="#fff"/>'
        f'<g fill="#000">{"".join(bars)}</g></svg>'
    )


# ─────────────────────────────────────────────────────────────────────────────
# Jetons & rendu HTML des étiquettes.
# ─────────────────────────────────────────────────────────────────────────────

PRODUIT_PREFIX = 'PRODUIT'
SYSTEME_PREFIX = 'SYSTEME'
# F23 — jeton d'intervention : scanner une étiquette chantier/matériel résout
# vers l'intervention concernée, réutilisant ce même encodeur + résolveur.
INTERVENTION_PREFIX = 'INTERV'
# FG85 — jeton d'équipement SAV : EQUIP:<equipement_id>
EQUIP_PREFIX = 'EQUIP'
# ZSTK6 — jetons lot/série scannables : `SERIE:<produit_id>:<valeur>` /
# `LOT:<produit_id>:<valeur>` (le produit est nécessaire pour désambiguïser —
# deux produits différents peuvent partager un n° de série/lot).
SERIE_PREFIX = 'SERIE'
LOT_PREFIX = 'LOT'
# XSTK20 — jeton « carte kanban » deux-bacs : `KANBAN:<produit_id>:
# <emplacement_id>` (l'emplacement est celui qui se recomplète — la carte est
# collée sur le bac vide de CET emplacement). Scanner cette carte crée une
# DemandeTransfert préremplie depuis le dépôt principal.
KANBAN_PREFIX = 'KANBAN'
# ZSTK5 — jeton « étiquette de colis » : `COLIS:<colis_id>` (2 segments, comme
# PRODUIT:/SYSTEME:/INTERVENTION:/EQUIP: ci-dessus). Scanner un colis résout
# vers son contenu (installations.Colis, FG322) — jamais de prix affiché.
COLIS_PREFIX = 'COLIS'


def produit_token(produit_id) -> str:
    return f'{PRODUIT_PREFIX}:{produit_id}'


def systeme_token(installation_id) -> str:
    return f'{SYSTEME_PREFIX}:{installation_id}'


def intervention_token(intervention_id) -> str:
    return f'{INTERVENTION_PREFIX}:{intervention_id}'


def equip_token(equipement_id) -> str:
    return f'{EQUIP_PREFIX}:{equipement_id}'


def serie_token(produit_id, numero_serie) -> str:
    return f'{SERIE_PREFIX}:{produit_id}:{numero_serie}'


def lot_token(produit_id, numero_lot) -> str:
    return f'{LOT_PREFIX}:{produit_id}:{numero_lot}'


def kanban_token(produit_id, emplacement_id) -> str:
    return f'{KANBAN_PREFIX}:{produit_id}:{emplacement_id}'


def colis_token(colis_id) -> str:
    return f'{COLIS_PREFIX}:{colis_id}'


def showroom_url(base_url, catalogue_token, produit_id) -> str:
    """XPOS17 — URL publique encodée par le QR d'une étiquette « showroom » :
    la fiche produit PUBLIQUE de l'e-catalogue tokenisé (FG214). Le client
    scanne en magasin et atterrit sur la fiche (specs, prix TTC, garantie,
    disponibilité indicative — JAMAIS de prix d'achat) avec les CTA
    « Demander un devis » (XPOS14) et « Être rappelé » (QJ27)."""
    base = (base_url or '').rstrip('/')
    return (f'{base}/api/django/public/stock/showroom/'
            f'{catalogue_token}/produit/{produit_id}/')


def _esc(value) -> str:
    return (str(value or '')
            .replace('&', '&amp;')
            .replace('<', '&lt;')
            .replace('>', '&gt;'))


def _label_card(token, titre, sous_titre, code_svg):
    return (
        '<div class="label">'
        f'<div class="code">{code_svg}</div>'
        '<div class="meta">'
        f'<div class="titre">{_esc(titre)}</div>'
        f'<div class="sous">{_esc(sous_titre)}</div>'
        f'<div class="token">{_esc(token)}</div>'
        '</div></div>'
    )


def render_labels_html(items, symbology='qr'):
    """`items` = liste de dicts {token, titre, sous_titre}. Rend une planche
    d'étiquettes (grille) prête pour WeasyPrint. `symbology` = 'qr' | 'code128'.
    """
    cards = []
    for it in items:
        token = it['token']
        if symbology == 'code128':
            svg = code128b_svg(token)
        else:
            svg = qr_svg(token)
        cards.append(_label_card(
            token, it.get('titre', ''), it.get('sous_titre', ''), svg))
    style = (
        '@page { size: A4; margin: 10mm; }'
        'body { font-family: Helvetica, Arial, sans-serif; }'
        '.sheet { display: flex; flex-wrap: wrap; gap: 6mm; }'
        '.label { width: 58mm; border: 1px solid #ccc; border-radius: 3mm;'
        ' padding: 3mm; display: flex; align-items: center; gap: 3mm;'
        ' box-sizing: border-box; page-break-inside: avoid; }'
        '.code svg { display: block; }'
        '.code { flex-shrink: 0; }'
        '.meta { min-width: 0; }'
        '.titre { font-size: 10pt; font-weight: 700; }'
        '.sous { font-size: 8pt; color: #444; }'
        '.token { font-size: 7pt; color: #888; font-family: monospace;'
        ' margin-top: 1mm; }'
    )
    return (
        '<!DOCTYPE html><html><head><meta charset="utf-8">'
        f'<style>{style}</style></head><body>'
        f'<div class="sheet">{"".join(cards)}</div>'
        '</body></html>'
    )
