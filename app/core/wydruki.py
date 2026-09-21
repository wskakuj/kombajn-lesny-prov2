"""
Kombajn Leśny PRO — moduł WYDRUKI

Generuje wszystkie pliki wydrukowe MIETEKA bezpośrednio z plików DBF mietka
(bez uruchamiania MS-DOS):

  * HALIZNY.TXT  — zestawienie powierzchni niezalesionych (PRZED przeniesieniem)
  * OPTAX.TXT    — opis lasów i gruntów (PO przeniesieniu halizn)
  * TAB_KLW3.TXT — zestawienie wg klas i podklas wieku (PO przeniesieniu)
  * ZEST1.TXT    — skorowidz działek
  * REJESTR1.TXT — rejestr działek wg właścicieli (PO przeniesieniu)
  * WSKAZ1.TXT   — wykaz wskaźników (pusty, gdy brak danych)

Formaty odtworzone 1:1 z wydruków MIETEKA (cp852, CRLF, ramki, sekwencje PCL).
"""

import re
import struct
from pathlib import Path


# ----------------------------------------------------------------------------
# Czytanie DBF / NTX
# ----------------------------------------------------------------------------

def czytaj_dbf(path):
    """Czyta DBF. Zwraca listę słowników {pole: wartość} (cp852)."""
    data = Path(path).read_bytes()
    nrec = struct.unpack('<I', data[4:8])[0]
    hlen = struct.unpack('<H', data[8:10])[0]
    rlen = struct.unpack('<H', data[10:12])[0]
    fields = []
    off = 32
    while off < len(data) and data[off:off + 1] != b'\x0d':
        raw = data[off:off + 32]
        fields.append((
            raw[0:11].split(b'\x00')[0].decode('ascii', errors='replace'),
            chr(raw[11]), raw[16], raw[17],
        ))
        off += 32
    recs = []
    pos = hlen
    for _ in range(nrec):
        row = data[pos:pos + rlen]
        pos += rlen
        if not row or len(row) < rlen or row[0:1] == b'*':
            continue
        rec = {}
        o = 1
        for fname, ftype, flen, fdec in fields:
            raw = row[o:o + flen].replace(b'\x00', b' ').strip()
            o += flen
            s = raw.decode('cp852', errors='replace')
            if ftype == 'N':
                s2 = s.replace(',', '.').strip()
                try:
                    rec[fname] = float(s2) if ('.' in s2 or fdec) else int(s2)
                except ValueError:
                    rec[fname] = None
            elif ftype == 'L':
                rec[fname] = (s == 'T') if s else None
            else:
                rec[fname] = s
        recs.append(rec)
    return recs


def znajdz_dbf(katalog, prefiks):
    """Znajduje (rekurencyjnie) pierwszy plik DBF o danym prefiksie nazwy."""
    katalog = Path(katalog)
    trafienia, seen = [], set()
    for w in (f'{prefiks}*.DBF', f'{prefiks}*.dbf'):
        for p in sorted(katalog.rglob(w)):
            if str(p).upper() not in seen:
                seen.add(str(p).upper())
                trafienia.append(p)
    return trafienia[0] if trafienia else None


def czytaj_ntx_kolejnosc(path_ntx, n_rekordow):
    """Czyta kolejność rekordów z jednopoziomowego indeksu NTX (jak MIETEK).

    Zwraca listę numerów rekordów (1-based) w kolejności indeksu,
    albo None gdy pliku nie ma / nie da się sparsować.
    """
    try:
        d = Path(path_ntx).read_bytes()
    except OSError:
        return None
    # strony 512-bajtowe; szukamy strony-liścia z poprawnymi wpisami
    best = None
    for base in range(512, len(d), 512):
        for pgstart in (base, base + 256 if base + 256 + 32 <= len(d) else -1):
            if pgstart < 0:
                continue
            pg = d[pgstart:pgstart + 1024]
            if len(pg) < 64:
                continue
            try:
                n = struct.unpack('<h', pg[0:2])[0]
            except struct.error:
                continue
            if n <= 0 or n > n_rekordow or 2 + 2 * n >= len(pg):
                continue
            offs = [struct.unpack('<h', pg[2 + 2 * i:4 + 2 * i])[0] for i in range(n)]
            if not offs:
                continue
            stride = offs[1] - offs[0] if len(offs) > 1 else 17
            if stride <= 8 or any(o <= 8 or o + stride > len(pg) for o in offs):
                continue
            recs = []
            ok = True
            for O in offs:
                try:
                    rec = struct.unpack('<i', pg[O + 4:O + 8])[0]
                except struct.error:
                    ok = False
                    break
                if not (1 <= rec <= n_rekordow):
                    ok = False
                    break
                recs.append(rec)
            if ok and len(set(recs)) == len(recs):
                if best is None or len(recs) > len(best):
                    best = recs
    return best


# ----------------------------------------------------------------------------
# DATA.CFG / WSIE.DBF — agencja, obiekt, stan na
# ----------------------------------------------------------------------------

def czytaj_agencje(obreb_dir):
    katalog = Path(obreb_dir)
    cfg = next((c for c in katalog.rglob('DATA.CFG')), None) \
        or next((c for c in katalog.rglob('DATA.cfg')), None)
    if cfg is None:
        return None
    try:
        t = cfg.read_bytes().decode('cp852', errors='replace')
        m = re.search(r'\d{2}-\d{3}', t)
        if not m:
            return None
        nazwa = re.sub(r'^[\d\s]+', '', t[:m.start()]).strip()
        return nazwa or None
    except Exception:
        return None


def czytaj_dane_wsi(obreb_dir):
    wsie_path = znajdz_dbf(obreb_dir, 'WSIE')
    if wsie_path is None:
        return '', ''
    try:
        recs = czytaj_dbf(wsie_path)
        if not recs:
            return '', ''
        nazwa = str(recs[0].get('NAZWA', '') or '').strip()
        stan = str(recs[0].get('STAN_NA', '') or '').strip()
        if re.match(r'^\d{8}$', stan):
            stan = f"{stan[6:8]}-{stan[4:6]}-{stan[0:4]}"
        return nazwa, stan
    except Exception:
        return '', ''


# ----------------------------------------------------------------------------
# Wspólne pomocniki
# ----------------------------------------------------------------------------

_STL = {11: 'Bs', 12: 'Bśw', 13: 'Bw', 14: 'Bb', 21: 'BM', 22: 'BMśw', 23: 'BMw', 24: 'BMb',
        31: 'LM', 32: 'LMśw', 33: 'LMw', 34: 'LMb', 42: 'Lśw', 43: 'Lw',
        44: 'Ol', 45: 'OlJ', 46: 'Lł'}
_PROG_NIEZALESIONE = 240


def _f4(v):
    try:
        return f"{float(v):.4f}"
    except (TypeError, ValueError):
        return '0.0000'


def _klucz_wydz(r):
    oddz = str(r.get('ODDZIAL', '') or '').strip()
    poddz = str(r.get('PODODDZ', '') or '').strip()
    try:
        return (int(float(oddz)), oddz, poddz)
    except ValueError:
        return (9999, oddz, poddz)


def _wczytaj_obreb(obreb_dir):
    """Wczytuje W, D, O, R + metadane obrębu."""
    obreb = Path(obreb_dir)
    w_path = znajdz_dbf(obreb, 'W')
    d_path = znajdz_dbf(obreb, 'D')
    o_path = znajdz_dbf(obreb, 'O')
    r_path = znajdz_dbf(obreb, 'R')
    if o_path is None:
        return None
    dane = {
        'W': czytaj_dbf(w_path) if w_path else [],
        'D': czytaj_dbf(d_path) if d_path else [],
        'O': czytaj_dbf(o_path),
        'R': czytaj_dbf(r_path) if r_path else [],
        'w_path': w_path, 'd_path': d_path, 'o_path': o_path, 'r_path': r_path,
    }
    # indeksy: oddz+poddz -> rekord
    dane['O_by'] = {f"{r.get('ODDZIAL', '')}{r.get('PODODDZ', '')}".strip(): r for r in dane['O']}
    dane['R_by'] = {f"{r.get('ODDZIAL', '')}{r.get('PODODDZ', '')}".strip(): r for r in dane['R']}
    return dane


def _wsks(r):
    """Lista (wsk, pow_wsk, miaz) dla R; pomija puste."""
    out = []
    for i in range(1, 7):
        wsk = str(r.get(f'WSK{i}', '') or '').strip()
        pw = r.get(f'POW_WSK{i}', 0) or 0
        mz = r.get(f'MIAZ{i}', 0) or 0
        if wsk and pw > 0:
            out.append((wsk, float(pw), mz))
    return out


def _miaz_na_ha(wsk, miaz, zasob):
    """Miąższość na hektar dla wskaźnika (0 = brak)."""
    if miaz and miaz > 0:
        return float(miaz)
    if wsk.startswith('Rb'):
        return float(zasob or 0)
    return 0.0


def _zapisz(path, lines, tail='\r\n'):
    Path(path).write_bytes(('\r\n'.join(lines) + tail).encode('cp852'))


# ----------------------------------------------------------------------------
# HALIZNY.TXT — Zestawienie powierzchni leśnych niezalesionych
# ----------------------------------------------------------------------------

_PCL_HAL = '\r\x1b(s16.67H\x1b&l5E\x1b&a14L'
_HAL_TOP = '┌───────┬─────────┬─────────────────────────────┐'
_HAL_H1 = '│       │         │                             │'
_HAL_H2 = '│Oddział│   Pow.  │           Rodzaj            │ '
_HAL_H3 = '│poddz. │   wydz. │         powierzchni         │'
_HAL_H4 = '│       │   [ha]  │                             │'
_HAL_SEP = '├───────┼─────────┼─────────────────────────────┤'
_HAL_NUM = '│   1   │    2    │              3              │'
_HAL_BOT = '└───────┴─────────┴─────────────────────────────┘'
_HAL_TITLE = ' Zestawienie powierzchni leśnych niezalesionych'


def generuj_halizny_txt(obreb_dir, agencja=None):
    """HALIZNY.TXT (przed przeniesieniem halizn w D*.DBF)."""
    obreb = Path(obreb_dir)
    o_dbf = znajdz_dbf(obreb, 'O')
    if o_dbf is None:
        return None, 0
    wydzielenia = czytaj_dbf(o_dbf)
    if agencja is None:
        agencja = czytaj_agencje(obreb) or ''
    obiekt, stan_na = czytaj_dane_wsi(obreb)

    niezalesione = sorted(
        (r for r in wydzielenia
         if (r.get('RODZ_POW') or 0) and (r.get('RODZ_POW') or 0) >= _PROG_NIEZALESIONE),
        key=_klucz_wydz,
    )
    if not niezalesione:
        return None, 0

    lines = [_PCL_HAL + agencja.ljust(114) + f"Strona {1:4d}",
             _HAL_TITLE.ljust(59) + f"Obiekt: {obiekt}".ljust(49) + f"Stan na: {stan_na}",
             _HAL_TOP, _HAL_H1, _HAL_H2, _HAL_H3, _HAL_H4,
             _HAL_SEP, _HAL_NUM, _HAL_SEP]

    suma_calk, biez_oddz, suma_oddz = 0.0, None, 0.0

    def zamknij():
        lines.append(_HAL_SEP)
        lines.append('│R.oddz.│' + _f4(suma_oddz).rjust(9) + '│' + ' ' * 29 + '│')
        lines.append(_HAL_SEP)

    for r in niezalesione:
        oddz = str(r.get('ODDZIAL', '') or '').strip()
        poddz = str(r.get('PODODDZ', '') or '').strip()
        if biez_oddz is not None and oddz != biez_oddz:
            zamknij()
            suma_calk += suma_oddz
            suma_oddz = 0.0
        opis = f"{int(r.get('RODZ_POW') or 0)}-{str(r.get('OP_TAX', '') or '')[:30].strip()}"[:29]
        lines.append('│' + f"{oddz}{poddz}".rjust(7) + '│' +
                     _f4(r.get('POW_WYDZ') or 0).rjust(9) + '│' +
                     opis.ljust(29) + '│')
        biez_oddz = oddz
        suma_oddz += float(r.get('POW_WYDZ') or 0)

    zamknij()
    suma_calk += suma_oddz
    lines.append('│ Razem │' + _f4(suma_calk).rjust(9) + '│' + ' ' * 29 + '│')
    lines.append(_HAL_BOT)
    out = o_dbf.parent / 'HALIZNY.TXT'
    _zapisz(out, lines)
    return out, len(niezalesione)


# ----------------------------------------------------------------------------
# Pozycje rejestru (kolejność wg nazwisk) — używana przez REJESTR1, ZEST1, OPTAX
# ----------------------------------------------------------------------------

def _pozycje_rejestru(dane):
    """Zwraca listę pozycji [(nrrej, [W...], [D...])] w kolejności MIETEKA
    (wg NAZWISKO+IMIE właściciela)."""
    grupy = {}
    for w in dane['W']:
        nr = w.get('NRREJ')
        if nr is None:
            continue
        grupy.setdefault(int(nr), []).append(w)
    pozycje = []
    for nr, ws in grupy.items():
        ws = sorted(ws, key=lambda w: (str(w.get('NAZWISKO', '') or ''),
                                       str(w.get('IMIE', '') or '')))
        ds = [d for d in dane['D'] if int(d.get('NRREJ') or 0) == nr]
        pozycje.append((nr, ws, ds))
    pozycje.sort(key=lambda p: (str(p[1][0].get('NAZWISKO', '') or '') +
                                str(p[1][0].get('IMIE', '') or '')))
    return pozycje


def _lp_pozycji(pozycje):
    return {nr: i + 1 for i, (nr, _, _) in enumerate(pozycje)}


# ----------------------------------------------------------------------------
# ZEST1.TXT — Skorowidz działek
# ----------------------------------------------------------------------------

_ZS_H = ('|---------|-------------------|----------|-------------|',
         '|nr dział.|   nr rejestru     | oddz/pod | pow. dział  |')


def _klucz_dzialki(dz):
    m = re.match(r'^(\d+)(.*)$', dz.strip())
    if not m:
        return (9999, dz.strip(), '')
    return (int(m.group(1)), m.group(2), '')


def generuj_zest1_txt(obreb_dir, dane=None, pozycje=None, agencja=None):
    """ZEST1.TXT — skorowidz działek (sortowanie numeryczne działek)."""
    obreb = Path(obreb_dir)
    if dane is None:
        dane = _wczytaj_obreb(obreb)
    if dane is None or not dane['D']:
        return None
    if pozycje is None:
        pozycje = _pozycje_rejestru(dane)
    lp_map = _lp_pozycji(pozycje)
    obiekt, stan = czytaj_dane_wsi(obreb)

    # kolejność w obrębie działki: wg NR_DZ.NTX (indeks MIETEKA), odwrotnie
    kolej = None
    if dane['d_path'] is not None:
        kolej = czytaj_ntx_kolejnosc(dane['d_path'].with_suffix('.NTX'), len(dane['D']))
        if kolej is None:
            kolej = czytaj_ntx_kolejnosc(
                dane['d_path'].parent / (dane['d_path'].stem + '.NTX'), len(dane['D']))
    recs = dane['D']
    if kolej and len(kolej) == len(recs):
        recs = [recs[i - 1] for i in reversed(kolej)]
        recs = sorted(recs, key=lambda d: _klucz_dzialki(str(d.get('NR_DZIAL', '') or '')))
    else:
        recs = sorted(recs, key=lambda d: (_klucz_dzialki(str(d.get('NR_DZIAL', '') or '')),
                                           -_idx(recs, d)))

    lines = ['\r Skorowidz działek'.ljust(35) + f"Obiekt: {obiekt}".ljust(49) +
             f"Stan na: {stan}", '',
             _ZS_H[0], _ZS_H[1], _ZS_H[0]]
    for d in recs:
        dz = str(d.get('NR_DZIAL', '') or '').strip()
        nr = int(d.get('NRREJ') or 0)
        lp = lp_map.get(nr, 0)
        oddzp = f"{str(d.get('ODDZIAL', '') or '').strip()}{str(d.get('PODODDZ', '') or '').strip()}"
        lines.append('|' + dz.ljust(9) + '|' + f"{lp}/{nr}".rjust(18) + ' ' + '|' +
                     oddzp.center(10) + '|' + _f4(d.get('POW') or 0).rjust(13) + '|' +
                     ' ' * 45 + '|')
    lines.append(_ZS_H[0])
    out = (dane['d_path'].parent if dane['d_path'] else obreb) / 'ZEST1.TXT'
    _zapisz(out, lines)
    return out


def _idx(lst, item):
    for i, x in enumerate(lst):
        if x is item:
            return i
    return 0


# ----------------------------------------------------------------------------
# OPTAX.TXT — Opis lasów i gruntów przeznaczonych do zalesienia
# ----------------------------------------------------------------------------

_OP_PCL = '\x1b(s16.67H\x1b&l5E\x1b&a9L'
_OP_H = (
    '┌───────┬─────────┬───────────────────────────────────┬──────────────────────────────────────┬──────────────────────────┬───────────────────────┐',
    '│       │         │ Opis taksacyjny lasu,             │          Elementy taksacyjne         │   Wskazania gospodarcze  │       Wykonanie       │',
    '│Oddział│  Pow.   │ gruntu przeznaczonego             ├────├────┬─────┬───┬────┬───┬───┬─────┼──────────┬─────────┬─────┼─────────┬───────┬─────┤',
    '│poddz. │  [ha]   │ do zalesienia                     │Gat.│Wiek│Klasa│Wys│Pier│Bon│Zad│Miąż.│Rodzaj    │  Pow.   │Maks.│  Czynn. │ [ha]  │[m3] │',
    '│       │         │                                   │ gł.│    │wieku│[m]│[cm]│   │   │ na  │wskazania │  [ha]   │miąż.│         │       │     │',
    '│       │         │                                   │    │    │     │   │    │   │   │ pow.│          │         │ do  │         │       │     │',
    '│       │         │                                   │    │    │     │   │    │   │   │ [m3]│          │         │pozys│         │       │     │',
    '│       │         │                                   │    │    │     │   │    │   │   │     │          │         │ [m3]│         │       │     │',
    '├───────┼─────────┼───────────────────────────────────┼────┼────┼─────┼───┼────┼───┼───┼─────┼──────────┼─────────┼─────┼─────────┼───────┼─────┤',
    '│   1   │    2    │                3                  │ 4  │ 5  │  6  │ 7 │  8 │ 9 │ 10│ 11  │    12    │    13   │  14 │   15    │  16   │ 17  │',
    '├───────┼─────────┼───────────────────────────────────┼────┼────┼─────┼───┼────┼───┼───┼─────┼──────────┼─────────┼─────┼─────────┼───────┼─────┤',
)
_OP_BOT = '└───────┴─────────┴───────────────────────────────────┴────┴────┴─────┴───┴────┴───┴───┴─────┴──────────┴─────────┴─────┴─────────┴───────┴─────┘'


def _seg_optax(row1, desc, wsk, pow_wydz=0.0):
    """Wiersz OPTAX.

    row1 – None (wiersz kontynuacji) albo 12-elementowa krotka:
           (oddzp, pow_str, gat, wiek, klasa, wys, pier, bon, zad, miaz_pow)
    desc  – tekst opisu (kolumna 3)
    wsk   – None albo (wskaznik, pow_wsk_proc, miaz_na_ha)
    """
    def c(v, w, just='>'):
        v = '' if v is None else str(v)
        return v.ljust(w) if just == '<' else v.rjust(w)

    if row1 is None:
        s = ('│' + ' ' * 7 + '│' + ' ' * 9 + '│' + c(desc, 35, '<') +
             '│    │    │     │   │    │   │   │     ')
    else:
        r = row1
        s = ('│' + c(r[0], 7) + '│' + c(r[1], 9) + '│' + c(desc, 35, '<') +
             '│' + c(r[2], 4, '<') + '│' + c(r[3], 4) + '│' + ' ' + c(r[4], 4, '<') +
             '│' + c(r[5], 3) + '│' + c(r[6], 4) + '│' + c(r[7], 3, '<') +
             '│' + c(r[8], 3, '<') + '│' + c(r[9], 5))
    if wsk is None:
        s += ('│' + ' ' * 10 + '│' + ' ' * 9 + '│' + ' ' * 5 +
              '│' + ' ' * 9 + '│' + ' ' * 7 + '│' + ' ' * 5 + '│')
    else:
        w, pw, mh = wsk
        pow_w = pw / 100.0 * pow_wydz
        maks = round(mh * pow_w) if mh > 0 else ''
        s += ('│' + c(w, 10, '<') + '│' + c(_f4(pow_w), 9) + '│' + c(maks, 5) +
              '│' + ' ' * 9 + '│' + ' ' * 7 + '│' + ' ' * 5 + '│')
    return s


def generuj_optax_txt(obreb_dir, dane=None, pozycje=None, agencja=None):
    """OPTAX.TXT — opis lasów i gruntów (po przeniesieniu halizn)."""
    obreb = Path(obreb_dir)
    if dane is None:
        dane = _wczytaj_obreb(obreb)
    if dane is None:
        return None
    if pozycje is None:
        pozycje = _pozycje_rejestru(dane)
    lp_map = _lp_pozycji(pozycje)
    if agencja is None:
        agencja = czytaj_agencje(obreb) or ''
    obiekt, stan = czytaj_dane_wsi(obreb)

    wydzs = sorted(dane['O'], key=_klucz_wydz)

    # bloki: (wiersze) per wydzielenie
    bloki = []
    suma_pow = 0.0
    suma_miaz = 0.0
    suma_maks = 0.0
    for o in wydzs:
        key = f"{o.get('ODDZIAL', '')}{o.get('PODODDZ', '')}".strip()
        r = dane['R_by'].get(key, {})
        pow_w = float(o.get('POW_WYDZ') or 0)
        zasob = float(r.get('ZASOB') or 0)
        suma_pow += pow_w
        suma_miaz += round(zasob * pow_w)
        # opis: siedlisko + gatunki, potem segmenty OP_TAX (po 35 znaków)
        stl = _STL.get(int(o.get('TYP_SIED') or 0), '')
        op_t = str(o.get('OP_TAX', '') or '')
        segs = [op_t[i * 35:(i + 1) * 35].strip() for i in range(7)]
        segs = [s for s in segs if s]
        # nr-y rejestrów właścicieli tego wydzielenia
        nrs, lp_strs = [], []
        for d in dane['D']:
            if (f"{d.get('ODDZIAL', '')}{d.get('PODODDZ', '')}".strip() == key
                    and d.get('NRREJ') not in nrs):
                nrs.append(d.get('NRREJ'))
                lp_strs.append(f"{lp_map.get(int(d.get('NRREJ') or 0), 0)}/{int(d.get('NRREJ') or 0)}")
        nry = 'nr-y.Rej. ' + ','.join(lp_strs) + ',' if lp_strs else ''
        desc = [f"{stl:<7}{str(o.get('GTD1', '') or ''):<4}{str(o.get('GTD2', '') or ''):<4}"
                f"{str(o.get('GTD3', '') or '')}".rstrip()] + segs + ([nry] if nry else [])

        # elementy taksacyjne
        def nn(v):
            return '' if not v else v

        wiek = r.get('WIEK')
        miaz_pow = round(zasob * pow_w)
        if r.get('PRZES'):
            miaz_pow = round(zasob)
        row1_tail = [
            str(r.get('GATUNEK', '') or '').strip(),          # 4 Gat. gł
            str(wiek) if wiek else '',                        # 5 Wiek
            str(r.get('KL_WIEK', '') or '').strip(),         # 6 Klasa
            str(r.get('WYS') or '') if r.get('WYS') else '',  # 7 Wys
            str(r.get('PIERS') or '') if r.get('PIERS') else '',  # 8 Pier
            str(r.get('BONIT', '') or '').strip(),            # 9 Bon
            f"{r.get('ZADRZEW', 0) or 0:.1f}" if wiek else '',  # 10 Zad
            str(miaz_pow) if miaz_pow else '',                # 11 Miąż na pow
        ]

        wsks = [(w, pw, _miaz_na_ha(w, mz, zasob)) for w, pw, mz in _wsks(r)]
        for w, pw, mh in wsks:
            if mh > 0:
                suma_maks += round(mh * (pw / 100.0) * pow_w)
                break

        # zbuduj wiersze bloku
        rows = []
        wsk_i = 0
        for di, dline in enumerate(desc):
            if di == 0:
                wsk = wsks[0] if wsks else None
                wsk_i = 1
                rows.append(_seg_optax(
                    (f"{o.get('ODDZIAL', '')}{o.get('PODODDZ', '')}".strip(),
                     _f4(pow_w)) + tuple(row1_tail), dline, wsk, pow_w))
            else:
                wsk = wsks[wsk_i] if wsk_i < len(wsks) else None
                wsk_i += 1
                rows.append(_seg_optax(None, dline, wsk, pow_w))
        # dodatkowe wskaźniki bez linii opisu
        while wsk_i < len(wsks):
            rows.append(_seg_optax(None, '', wsks[wsk_i], pow_w))
            wsk_i += 1
        bloki.append(rows)

    # --- składanie stron (budżet 24 wiersze blokowe; SEP przed blokiem) ---
    lines = []
    pages, cur, used = [], [], 0

    def eject():
        nonlocal cur, used
        if cur:
            pages.append(cur)
        cur, used = [], 0

    for rows in bloki:
        if used and used + len(rows) > 24:
            eject()
        if used:
            cur.append(_OP_H[-1])
        cur.extend(rows)
        used += len(rows)

    def tot_row(name):
        return ('│' + f"{name}".ljust(7) + '│' + _f4(suma_pow).rjust(9) + '│' + ' ' * 35 +
                '│    │    │     │   │    │   │   │' + str(int(suma_miaz)).rjust(5) + '│' +
                ' ' * 10 + '│' + ' ' * 9 + '│' + str(int(suma_maks)).rjust(5) +
                '│' + ' ' * 9 + '│' + ' ' * 7 + '│' + ' ' * 5 + '│')

    if cur:
        cur.append(_OP_H[-1])
        cur.append(tot_row('R.oddz.'))
        cur.append(_OP_H[-1])
        cur.append(tot_row(' Razem '))

    _bot_last = _OP_BOT[:59] + '┼' + _OP_BOT[60:]
    pageno = 1
    all_pages = pages + [cur] if cur else pages
    last_page = all_pages[-1] if all_pages else None
    for pg in all_pages:
        pcl = _OP_PCL if pageno <= 4 else ''
        hdr = ('\r' if pageno == 1 else '\f\r') + pcl + agencja.ljust(114) + f"Strona {pageno:4d}"
        lines.append(hdr)
        lines.append(' Opis lasów i gruntów przeznaczonych do zalesienia'.ljust(56) +
                     f"Obiekt: {obiekt}".ljust(49) + f"Stan na: {stan}")
        lines.extend(_OP_H)
        lines.extend(pg)
        lines.append(_bot_last if pg is last_page else _OP_BOT)
        pageno += 1
    lines.append('\f')

    if not all_pages:
        return None, 0
    out = dane['o_path'].parent / 'OPTAX.TXT'
    _zapisz(out, lines, tail='')
    return out, pageno - 1


# ----------------------------------------------------------------------------
# TAB_KLW3.TXT — Zestawienie wg klas i podklas wieku (+ siedliska, ochrona, przebudowa)
# ----------------------------------------------------------------------------

_TK_PCL = '\r\x1b(s16.67H\x1b&l5E\x1b&a0L'
_TK_H = (
    '┌───────┬──────┬───────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────┐',
    '│Gatunek│Przes.│                                                     Powierzchnia w ha / miąższośc w m3                                                                                    │',
    '│panuj. │i nas.├─────────┬───────────────────────────────────────────────────────────────────────────────────────────────────────────────────────┬─────────┬─────────┬──────────┬──────────┤',
    '│       │      │  Pow.   │                                                 Klasy, podklasy wieku                                                 │         │         │          │          │',
    '│       │      │ leśna   ├───────────────────┬───────────────────┬───────────────────┬───────────────────┬───────────────────┬─────────┬─────────┤         │         │   Razem  │  Ogółem  │',
    '│       │      │  nie    │         I         │        II         │        III        │        IV         │         V         │   VI    │   VII   │ K.D.O.  │   K.O.  │   kol.   │   kol.   │',
    '│       │      │zalesiona├─────────┬─────────┼─────────┬─────────┼─────────┬─────────┼─────────┬─────────┼─────────┬─────────┤         │    i    │         │         │   4-17   │   3-17   │',
    '│       │      │         │    a    │    b    │    a    │    b    │    a    │    b    │    a    │    b    │    a    │    b    │         │   wyż.  │         │         │          │          │',
    '├───────┼──────┼─────────┼─────────┼─────────┼─────────┼─────────┼─────────┼─────────┼─────────┼─────────┼─────────┼─────────┼─────────┼─────────┼─────────┼─────────┼──────────┼──────────┤',
    '│   1   │  2   │    3    │    4    │    5    │    6    │    7    │    8    │    9    │   10    │   11    │   12    │   13    │   14    │   15    │   16    │   17    │    18    │    19    │',
    '├───────┼──────┼─────────┼─────────┼─────────┼─────────┼─────────┼─────────┼─────────┼─────────┼─────────┼─────────┼─────────┼─────────┼─────────┼─────────┼─────────┼──────────┼──────────┤',
)
_TK_BOT = '└───────┴──────┴─────────┴─────────┴─────────┴─────────┴─────────┴─────────┴─────────┴─────────┴─────────┴─────────┴─────────┴─────────┴─────────┴─────────┴─────────┴──────────┴──────────┘'
_TK_KLASY = ['Ia', 'Ib', 'IIa', 'IIb', 'IIIa', 'IIIb', 'IVa', 'IVb', 'Va', 'Vb', 'VI', 'VII',
             'KDO', 'KO']

_OCHR = {0: '0-brak ochronności', 1: '1-wod.', 2: '2-pow. gleb.', 3: '3-nieuż.roln.',
         4: '4-poz. przyg.', 5: '5-nauk.', 6: '6-pow. pojar.', 7: '7-uzdrow.',
         8: '8-stref. ost.', 9: '9-gosp. chełm.'}


def generuj_tab_klw3_txt(obreb_dir, dane=None, agencja=None, strona_start=1):
    """TAB_KLW3.TXT (po przeniesieniu halizn)."""
    obreb = Path(obreb_dir)
    if dane is None:
        dane = _wczytaj_obreb(obreb)
    if dane is None:
        return None
    if agencja is None:
        agencja = czytaj_agencje(obreb) or ''
    obiekt, _ = czytaj_dane_wsi(obreb)

    # --- agregacja po gatunkach i klasach wieku (z pominięciem PRZES) ---
    gat_order, gat_pow, gat_m3 = [], {}, {}
    for rr in dane['R']:
        g = str(rr.get('GATUNEK', '') or '').strip()
        if g and g not in gat_order:
            gat_order.append(g)
            gat_pow[g] = [0.0] * 15
            gat_m3[g] = [0.0] * 15
    for d in dane['D']:
        key = f"{d.get('ODDZIAL', '')}{d.get('PODODDZ', '')}".strip()
        r = dane['R_by'].get(key, {})
        if r.get('PRZES'):
            continue
        gat = str(r.get('GATUNEK', '') or '').strip() or '??'
        if gat not in gat_pow:
            gat_order.append(gat)
            gat_pow[gat] = [0.0] * 15   # niezalesiona + 14 kolumn klas
            gat_m3[gat] = [0.0] * 15
        # (gatunki z R już są w gat_order)
        zasob = float(r.get('ZASOB') or 0)
        lz = float(d.get('POW_L_ZAL') or 0)
        lnz = float(d.get('POW_L_NZAL') or 0)
        kl = str(r.get('KL_WIEK', '') or '').strip()
        try:
            kidx = _TK_KLASY.index(kl) if kl else -1
        except ValueError:
            kidx = -1
        if lnz > 0:
            gat_pow[gat][0] += lnz
        if lz > 0 and kidx >= 0:
            gat_pow[gat][1 + kidx] += lz
            gat_m3[gat][1 + kidx] += zasob * lz

    def wiersz(gat, m3):
        if m3:
            # komórki m3 zaokrąglone per gatunek; Razem sumuje zaokrąglone
            cells = [round(v) for v in gat_m3[gat]]
            razem = sum(cells[1:])
            ogolem = razem + cells[0]
            s = ('│' + ' ' * 7 + '│' + '0'.rjust(6) + '│' +
                 '│'.join(f"{v}".rjust(9) for v in cells) + '│' +
                 f"{razem}".rjust(10) + '│' + f"{ogolem}".rjust(10) + '│')
        else:
            cells = gat_pow[gat]
            razem = sum(cells[1:])
            ogolem = razem + cells[0]
            s = ('│' + ' ' * 7 + '│' + ' ' * 6 + '│' +
                 '│'.join(_f4(v).rjust(9) for v in cells) + '│' +
                 _f4(razem).rjust(10) + '│' + _f4(ogolem).rjust(10) + '│')
        return s

    lines = [_TK_PCL + agencja.ljust(125) + f"Strona {strona_start:2d}",
             (' Zestawienie powierzchni gruntów i miąższości drzewostanu wg gatunków'
              ' panujących (głównych) wg klas i podklas wieku.'.ljust(118) +
              f"Obiekt: {obiekt}").ljust(166)]
    lines.extend(_TK_H)

    # wiersze gatunków
    for gat in gat_order + ['__razem__']:
        if gat == '__razem__':
            gat_pow[gat] = [sum(gat_pow[g][i] for g in gat_order) for i in range(15)]
            gat_m3[gat] = [sum(round(gat_m3[g][i]) for g in gat_order) for i in range(15)]
            name = ' Razem '
        else:
            pad = 7 - len(gat)
            name = ' ' * (pad // 2) + gat + ' ' * (pad - pad // 2)
        lines.append(wiersz(gat, m3=False))
        part = '│' + name + '│      ├---------┼---------┼---------┼---------┼---------┼---------┼---------┼---------┼---------┼---------┼---------┼---------┼---------┼---------┼---------┼----------┼----------┤'
        lines.append(part)
        lines.append(wiersz(gat, m3=True))
        lines.append(_TK_H[-1])
    lines[-1] = _TK_BOT

    # stopki części 1
    inne = sum(float(o.get('POW_WYDZ') or 0) for o in dane['O']
               if 301 <= (o.get('RODZ_POW') or 0) <= 399)
    dozal = sum(float(o.get('POW_WYDZ') or 0) for o in dane['O']
                if 400 <= (o.get('RODZ_POW') or 0) <= 409)
    lasy = sum(gat_pow['__razem__'])
    for label, v in (('inne grunty (staw, jez.)', inne), ('grunty do zal.', dozal),
                     ('Razem lasy', lasy)):
        lines.append(' ' * 146 + label.ljust(26) + '-' + _f4(v).rjust(10))

    # --- część 2: siedliskowe typy lasu ---
    stl_pow = {}
    for o in dane['O']:
        kod = int(o.get('TYP_SIED') or 0)
        stl_pow[kod] = stl_pow.get(kod, 0.0) + float(o.get('POW_WYDZ') or 0)
    kody = sorted(stl_pow)
    nazwy = [_STL.get(k, str(k)) for k in kody]
    ncol = len(kody) + 1
    lines.append('\f\r\x1b(s16.67H\x1b&l9E\x1b&a8L 2. Zestawienie powierzchni siedliskowych typów lasu - ' + obiekt)
    lines.append('┌──────────────────┬' + '─' * 39 + '┐')
    lines.append('│ Wyszczególnienie │' + 'Siedliskowe typy lasu'.center(39) + '│')
    lines.append('│                  ├' + '┬'.join(['─' * 9] * ncol) + '┤')
    cells = ['  ' + n.ljust(7) for n in nazwy] + ['  Razem  ']
    lines.append('│                  │' + '│'.join(cells) + '│')
    lines.append('├──────────────────┼' + '┼'.join(['─' * 9] * ncol) + '┤')
    vals = [_f4(stl_pow[k]).rjust(9) for k in kody] + [_f4(sum(stl_pow.values())).rjust(9)]
    lines.append('│ Powierzchnia ha  │' + '│'.join(vals) + '│')
    lines.append('└──────────────────┴' + '┴'.join(['─' * 9] * ncol) + '┘')
    lines.append('')
    lines.append('  powierzchnie inne = ' + _f4(inne).rjust(9) + ' ha')
    lines.append('')
    lines.append('')

    # --- część 3: lasy ochronne ---
    ochr_pow = {}
    for o in dane['O']:
        k = int(o.get('KAT_OCH') or 0)
        ochr_pow[k] = ochr_pow.get(k, 0.0) + float(o.get('POW_WYDZ') or 0)
    kody = sorted(ochr_pow)
    lines.append('3. Zestawienie powierzchni lasów ochronnych')
    cat_w = 20 * len(kody) + max(0, len(kody) - 1) + 1 + 9
    inner = '┬'.join(['─' * 20] * len(kody) + ['─' * 9])
    lines.append('┌──────────────────┬' + '─' * cat_w + '┐')
    lines.append('│ Wyszczególnienie │' +
                 'Kategoria ochronnosci'.center(cat_w) + '│')
    lines.append('│                  ├' + inner + '┤')
    lines.append('│                  │' + '│'.join(
        _OCHR.get(k, str(k)).ljust(20) for k in kody) + '│  Razem  ' + '│')
    lines.append('├──────────────────┼' + inner.replace('┬', '┼') + '┤')
    lines.append('│ Powierzchnia ha  │' + '│'.join(
        [_f4(ochr_pow[k]).rjust(14).ljust(20) for k in kody] +
        [_f4(sum(ochr_pow.values())).rjust(9)]) + '│')
    lines.append('└──────────────────┴' + inner.replace('┬', '┴') + '┘')
    lines.append('')
    lines.append('')

    # --- część 4: drzewostany do przebudowy (JAKOSC=1) ---
    przebud_pow, przebud_zasob = 0.0, 0.0
    for o in dane['O']:
        key = f"{o.get('ODDZIAL', '')}{o.get('PODODDZ', '')}".strip()
        r = dane['R_by'].get(key, {})
        if (r.get('JAKOSC') or 0) == 1:
            p = float(o.get('POW_WYDZ') or 0)
            przebud_pow += p
            przebud_zasob += float(r.get('ZASOB') or 0) * p
    lines.append('4. Zestawienie powierzchni dla drzewostanów do przebudowy')
    lines.append('')
    lines.append(f"      Razem  pow:{_f4(przebud_pow).rjust(10)} ha        "
                 f"Zasobność:{round(przebud_zasob):>5} m3")
    lines.append('\f')

    out = dane['o_path'].parent / 'TAB_KLW3.TXT'
    _zapisz(out, lines, tail='')
    return out


# ----------------------------------------------------------------------------
# REJESTR1.TXT — Rejestr działek wg właścicieli
# ----------------------------------------------------------------------------

_RJ_PCL = '\x1b(s16.67H\x1b&l4E\x1b&a1L'
_RJ_H = (
    '┌────────┬──────────────────────────────────────────────────┬───────┬──────┬──────────────────────────────────────────────────────────────┬─────────┬──┬───────────────────────────┬───────┐',
    '│        │                                                  │       │      │                  Opis i powierzchnia lasów                   │  Pow.   │ O│   Wskazania godspodarcze  │       │',
    '│   nr   │  Nazwisko i imię                                 │   Nr  │Oddz. ├──────────────────────┬───────────────────┬─────────┬─────────┤ gruntów │ c├──────────┬─────────┬──────┤ Wykon.│',
    '│rejestru│  Adres właściciela                               │działki│poddz.│       zalesiona      │   nie zalesiona   │  inne   │  razem  │   do    │ h│  Rodzaj  │  Pow.   │ Miąż.│       │',
    '│        │  Współwłaściciele                                │       │      ├────┬───┬───┬─────────┼─────────┬─────────┤ grunty  │  lasy   │  zal.   │ r│  zabiegu │  [ha]   │  m3  │       │',
    '│        │                                                  │       │      │gat.│ W │Bon│   Pow.  │ do odn. │ pozost. │         │         │         │ .│          │         │      │       │',
    '├────────┼──────────────────────────────────────────────────┼───────┼──────┼────┼───┼───┼─────────┼─────────┼─────────┼─────────┼─────────┼─────────┼──┼──────────┼─────────┼──────┼───────┤',
    '│   1    │                    2                             │   3   │  4   │ 5  │ 6 │ 7 │    8    │    9    │   10    │   11    │   12    │   13    │14│    15    │    16   │  17  │  18   │',
    '├────────┼──────────────────────────────────────────────────┼───────┼──────┼────┼───┼───┼─────────┼─────────┼─────────┼─────────┼─────────┼─────────┼──┼──────────┼─────────┼──────┼───────┤',
)
_RJ_BOT = '└────────┴──────────────────────────────────────────────────┴───────┴──────┴────┴───┴───┴─────────┴─────────┴─────────┴─────────┴─────────┴─────────┴──┴──────────┴─────────┴──────┴───────┘'


def _rj_row(nr_poz, nazwa, d_item, wsk_item, dane):
    """Wiersz danych REJESTR1 (16 segmentów, kolumny 3-18)."""
    seg = [''] * 16
    if d_item is not None:
        d, r, o = d_item
        lz = float(d.get('POW_L_ZAL') or 0)
        lnz = float(d.get('POW_L_NZAL') or 0)
        hal = lnz > 0
        gat = 'hal.' if hal else (str(r.get('GATUNEK', '') or '').strip() if r else '')
        wiek = '' if (hal or not r or not r.get('WIEK')) else str(r.get('WIEK'))
        bon = str(r.get('BONIT', '') or '').strip() if r else ''
        seg = [
            str(d.get('NR_DZIAL', '') or '').strip(),
            f"{str(d.get('ODDZIAL', '') or '').strip()}{str(d.get('PODODDZ', '') or '').strip()}",
            gat, wiek, bon,
            _f4(lz) if lz > 0 else '',
            _f4(lnz) if lnz > 0 else '',
            _f4(d.get('POW_N_ZAL') or 0) if (d.get('POW_N_ZAL') or 0) > 0 else '',
            _f4(d.get('POW_INNE') or 0) if (d.get('POW_INNE') or 0) > 0 else '',
            _f4(d.get('POW') or 0),
            '', '',
        ] + [''] * 4
    if wsk_item is not None:
        w, pw, mh, d = wsk_item
        pow_z = pw / 100.0 * float(d.get('POW') or 0)
        miaz = f"{mh * pow_z:.1f}" if mh > 0 else ''
        seg[12:16] = [w.split('-')[0], _f4(pow_z), miaz, '']
    c1 = (f"{nr_poz}".rjust(7) + ' ') if nr_poz else ' ' * 8
    row = '│' + c1 + '│' + f"{nazwa}".ljust(50)
    widths = [7, 6, 4, 3, 3, 9, 9, 9, 9, 9, 9, 2, 10, 9, 6, 7]
    for k, (v, wd) in enumerate(zip(seg, widths)):
        v = '' if v is None else str(v)
        row += '│' + (v.ljust(wd) if k in (2, 4, 12) else v.rjust(wd))
    return row + '│'


def generuj_rejestr1_txt(obreb_dir, dane=None, agencja=None):
    """REJESTR1.TXT (po przeniesieniu halizn w D*.DBF)."""
    obreb = Path(obreb_dir)
    if dane is None:
        dane = _wczytaj_obreb(obreb)
    if dane is None:
        return None
    if agencja is None:
        agencja = czytaj_agencje(obreb) or ''
    obiekt, _ = czytaj_dane_wsi(obreb)
    pozycje = _pozycje_rejestru(dane)

    els = []          # ('sep',) | ('row',...,is_pool) | ('dash',) | ('razem', label, sums)
    tot_obj = [0.0] * 5
    for lp, (nrrej, ws, ds) in enumerate(pozycje, start=1):
        els.append(('sep',))
        # strumień: każdy D + jego WSK1, potem jego WSK2..WSK6
        stream = []
        for d in ds:
            key = f"{d.get('ODDZIAL', '')}{d.get('PODODDZ', '')}".strip()
            r = dane['R_by'].get(key, {})
            o = dane['O_by'].get(key, {})
            zasob = float(r.get('ZASOB') or 0)
            wsks = _wsks(r)
            if wsks:
                w, pw, mz = wsks[0]
                stream.append(('D', d, r, o, (w, pw, _miaz_na_ha(w, mz, zasob), d)))
            else:
                stream.append(('D', d, r, o, None))
            for w, pw, mz in wsks[1:]:
                stream.append(('Z', d, r, o, (w, pw, _miaz_na_ha(w, mz, zasob), d)))
        # wylewanie na pulę wierszy właścicieli (nazwisko/adres), potem dopisywane
        pool = []
        for w in ws:
            pool.append((w, 'name'))
            pool.append((w, 'addr'))
        for i, item in enumerate(stream):
            if i < len(pool):
                w, kind = pool[i]
                if kind == 'name':
                    nazwa = f"{str(w.get('NAZWISKO', '') or '').strip()} " \
                            f"{str(w.get('IMIE', '') or '').strip()} " \
                            f"{str(w.get('RODZICE', '') or '').strip()}".strip()
                    nr_poz = f"{lp}/{nrrej}"
                else:
                    nazwa = str(w.get('ADRES', '') or '').strip()
                    nr_poz = ''
                is_pool = True
            else:
                nazwa, nr_poz, is_pool = '', '', False
            if item[0] == 'D':
                els.append(('row', nr_poz, nazwa, (item[1], item[2], item[3]),
                            item[4], is_pool))
            else:
                els.append(('row', nr_poz, nazwa, None, item[4], is_pool))
        # blok "Razem"
        seen_dz, dz_sum, poz_sums = [], {}, [0.0] * 5
        for d in ds:
            dz = str(d.get('NR_DZIAL', '') or '').strip()
            if dz not in dz_sum:
                dz_sum[dz] = 0.0
                seen_dz.append(dz)
            dz_sum[dz] += float(d.get('POW') or 0)
            for k, f in enumerate(('POW_L_ZAL', 'POW_L_NZAL', 'POW_N_ZAL', 'POW_INNE')):
                poz_sums[k] += float(d.get(f) or 0)
            poz_sums[4] += float(d.get('POW') or 0)
        els.append(('dash',))
        for dz in seen_dz:
            els.append(('razem', f" Razem dzialka {dz}".ljust(28) +
                        _f4(dz_sum[dz]) + ' ha', None))
        els.append(('razem', f" Razem pozycja {f'{lp}/{nrrej}':>6}".ljust(28) +
                    _f4(poz_sums[4]) + ' ha', poz_sums))
        for k in range(5):
            tot_obj[k] += poz_sums[k]
    els.append(('sep',))
    els.append(('razem', " Razem obiekt".ljust(22) + _f4(tot_obj[4]) + ' ha', tot_obj))

    # ---- paginacja: łamanie po wierszach puli (>=24) i przed pozycjami ----
    def _row_out(el):
        typ = el[0]
        if typ == 'sep':
            return _RJ_H[-1]
        if typ == 'dash':
            return ('│' + ' ' * 8 + '│' + ' ' * 50 + '│' + ' ' * 7 + '│' + ' ' * 6 +
                    '│    │   │   │' + '---------│' * 6 + '  │' + ' ' * 10 + '│' +
                    ' ' * 9 + '│' + ' ' * 6 + '│' + ' ' * 7 + '│')
        if typ == 'razem':
            _, label, sums = el
            s = ('│' + ' ' * 8 + '│' + label.ljust(50) + '│' + ' ' * 7 + '│' + ' ' * 6 +
                 '│    │   │   │')
            if sums is None:
                s += '---------│' * 6
            else:
                s += ''.join(_f4(v).rjust(9) + '│' for v in sums)
                s += '0.0000'.rjust(9) + '│'
            s += '  │' + ' ' * 10 + '│' + ' ' * 9 + '│' + ' ' * 6 + '│' + ' ' * 7 + '│'
            return s
        _, nr_poz, nazwa, d_item, wsk_item, is_pool = el
        return _rj_row(nr_poz, nazwa, d_item, wsk_item, dane)

    pages, cur, rows = [], [], 0

    def eject():
        nonlocal cur, rows
        if cur:
            pages.append(cur)
        cur, rows = [], 0

    for el in els:
        if el[0] == 'sep':
            if rows >= 24:
                eject()
            if rows == 0:
                continue          # nagłówek strony już kończy się SEP
            cur.append(_row_out(el))
            rows += 1
            continue
        cur.append(_row_out(el))
        rows += 1
        if el[0] == 'row' and el[5] and rows >= 24:
            eject()

    out_lines = []
    for pageno, pg in enumerate(pages + [cur] if cur else pages, start=1):
        out_lines.extend(_strona_rej(pg, pageno, agencja, obiekt))
    out_lines.append('\f\x1bE')

    out = dane['d_path'].parent / 'REJESTR1.TXT' if dane['d_path'] else obreb / 'REJESTR1.TXT'
    _zapisz(out, out_lines, tail='')
    return out


def _strona_rej(rows, pageno, agencja, obiekt):
    hdr = ('\r' if pageno == 1 else '\f\r') + _RJ_PCL + agencja.ljust(134) + f"Strona {pageno:5d}"
    return [hdr,
            (' Rejestr działek leśnych i gruntów do zalesienia wg. właścicieli'.ljust(75) +
             f"Obiekt: {obiekt}").ljust(123)] + list(_RJ_H) + list(rows) + [_RJ_BOT]


# ----------------------------------------------------------------------------
# WSKAZ1.TXT — wykaz wskaźników (pusty przy braku danych)
# ----------------------------------------------------------------------------

def generuj_wskaz1_txt(obreb_dir, dane=None, agencja=None):
    obreb = Path(obreb_dir)
    if dane is None:
        dane = _wczytaj_obreb(obreb)
    if dane is None:
        return None
    o_path = dane['o_path']
    out = o_path.parent / 'WSKAZ1.TXT' if o_path else obreb / 'WSKAZ1.TXT'
    out.write_bytes(b'')
    return out


# ----------------------------------------------------------------------------
# Generowanie całości
# ----------------------------------------------------------------------------

def generuj_wszystkie_po_przeniesieniu(obreb_dir, agencja=None):
    """Generuje OPTAX, TAB_KLW3, ZEST1, REJESTR1, WSKAZ1 (po przeniesieniu halizn).

    Numeracja stron TAB_KLW3 kontynuuje OPTAX (jak w MIETEKU).
    Zwraca słownik {nazwa: ścieżka}.
    """
    dane = _wczytaj_obreb(obreb_dir)
    if dane is None:
        return {}
    pozycje = _pozycje_rejestru(dane)
    out = {}
    optax_stron = 0
    try:
        p, optax_stron = generuj_optax_txt(obreb_dir, dane=dane, pozycje=pozycje,
                                           agencja=agencja)
        if p:
            out['OPTAX.TXT'] = p
    except Exception:
        import traceback
        traceback.print_exc()
    for fn, gen, kw in (
        ('TAB_KLW3.TXT', generuj_tab_klw3_txt, dict(strona_start=optax_stron or 1)),
        ('ZEST1.TXT', generuj_zest1_txt, dict(pozycje=pozycje)),
        ('REJESTR1.TXT', generuj_rejestr1_txt, dict()),
        ('WSKAZ1.TXT', generuj_wskaz1_txt, dict()),
    ):
        try:
            p = gen(obreb_dir, dane=dane, agencja=agencja, **kw)
            if p:
                out[fn] = p
        except Exception:
            import traceback
            traceback.print_exc()
    return out
