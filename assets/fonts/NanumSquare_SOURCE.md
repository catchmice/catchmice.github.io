# Source and verification

## Upstream release

- Typeface: Nanum Square (나눔스퀘어)
- Copyright holder: NAVER Corporation
- Designer: Sandoll Communications Inc.
- Distribution page: <https://hangeul.naver.com/font>
- Archive: <https://hangeul.naver.com/hangeul_static/webfont/zips/nanum-all_new.zip>
- Archive size: 131,407,635 bytes
- Archive SHA-256: `173fd24bf38914f385401f602572dca3481f7669966e91ad289066f719f6cc56`
- Packaged on: 2026-09-17

The eight TTF files are copied byte-for-byte from the official archive paths
under `NanumFontSetup_TTF_SQUARE/` (classic Nanum Square and NanumSquare_ac).
Nanum Square Neo and Nanum Square Round are separate typefaces and are not
included.

## Packaged files

| File | Bytes | SHA-256 | Glyphs | Units/em | Preferred family | Preferred subfamily | PostScript name |
|------|------:|--------|-------:|---------:|------------------|---------------------|-----------------|
| `NanumSquareL.ttf` | 750,932 | `b2f68affc8b5d450fd0cb1b6f1523888a70e236fff942889c30f832727152da4` | 18,155 | 1000 | NanumSquare | Light | NanumSquareL |
| `NanumSquareR.ttf` | 723,640 | `5a51deae5237435d9a0bc0cc6cc30619a914b29801f895698cfdacadcad06e94` | 18,155 | 1000 | NanumSquare | Regular | NanumSquareR |
| `NanumSquareB.ttf` | 733,500 | `f737d58294faec9c632189af3a2a3e48e49c03c0256de09db61e879e2857bfbf` | 18,155 | 1000 | NanumSquare | Bold | NanumSquareB |
| `NanumSquareEB.ttf` | 726,684 | `6608adc320ff8514630d04a53e16cc7a5d54f5cbdbe3769109f311dcb3b48f80` | 18,155 | 1000 | NanumSquare | ExtraBold | NanumSquareEB |
| `NanumSquare_acL.ttf` | 657,488 | `046cb1b1a4666e9a01ec09bc6109d32194351df18668709a3469967e50587372` | 3,566 | 1000 | NanumSquare_ac | Light | NanumSquare_acL |
| `NanumSquare_acR.ttf` | 646,720 | `a8c3aa53d5dbab550e7784281801f71f7af54619ca8d33a6e5e7d34d4f06d7e2` | 3,566 | 1000 | NanumSquare_ac | Regular | NanumSquare_acR |
| `NanumSquare_acB.ttf` | 640,036 | `1a266ecb0450fcdd0c7659090b8be784a2029a2f78a4a9501de3394ee284864d` | 3,566 | 1000 | NanumSquare_ac | Bold | NanumSquare_acB |
| `NanumSquare_acEB.ttf` | 633,248 | `5348d0f43d0b1d01e6ac888aafba2048178adc2304dbc5c8f4b3418438f02554` | 3,566 | 1000 | NanumSquare_ac | ExtraBold | NanumSquare_acEB |

Font version for all eight files: `Version 1.000;PS 1;hotconv 1.0.88;makeotf.lib2.5.647800`.

## Coverage notes

- Classic `NanumSquare*` maps Hangul syllables, Latin, and CJK unified
  ideographs (for example `가` `U+AC00`, `A` `U+0041`, `一` `U+4E00`).
- `NanumSquare_ac*` is the Hangul/Latin-oriented AC companion family; it maps
  Hangul and Latin but does not include CJK unified ideographs such as `一`.

## License

NAVER distributes Nanum fonts under the SIL Open Font License, Version 1.1.
See [`LICENSE`](./LICENSE) and
<https://help.naver.com/service/30016/contents/18088?lang=ko>.
