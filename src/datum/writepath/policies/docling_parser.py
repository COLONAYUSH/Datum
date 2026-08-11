"""DoclingParser: the multi-format `Parser` (L3), lazy-importing Docling.

Where `MarkdownParser` reads `DocumentInput.text` and only understands
markdown, this parser reads `DocumentInput.source_path` and understands every
format Docling does — docx/pptx/xlsx, html, csv, pdf, images, epub, audio, the
XML dialects. It is the format-coverage feeder task #30 calls for, and it is a
drop-in `Parser`: `DocumentPolicy` consumes it exactly like the markdown one,
so nothing downstream (chunking, CAS, retrieval) changes shape per format.

**Design (decisions.md #31): Docling converts the file to markdown, then the
existing `MarkdownParser` sections that markdown.** Docling's strength is
turning any format into clean structured markdown (headings, lists, tables as
pipe-tables); the markdown parser's job is turning markdown into
section-path-keyed `ParsedSection`s, and it is already tested for exactly that.
Composing them means one sectioning implementation, not a second one that
could drift, and tables arrive as inlined markdown text (searchable) under
their heading. The honest v1 limit this draws: structural provenance is the
heading-derived `section_path`; per-item PAGE and BBOX are NOT carried, because
`export_to_markdown` does not preserve them and the only formats that HAVE
pages (pdf, scanned images) need Docling's layout models — which route through
a separate, currently unstaged download path. Page/bbox mapping via
`iterate_items()` is the Phase-1 enrichment that lands with the PDF/image
pipeline, tested against the formats that actually carry it.

**Image-embedded text (decisions.md #36).** Docling reads the OCR of a page
into its document model but `export_to_markdown()` DROPS every text cell that
falls inside a layout-detected Picture cluster (it emits `<!-- image -->` for
the whole cluster). Measured, not assumed: the diagram labels, org-chart names,
and chart-bar values of the stress corpus are all present in `export_to_dict()`
yet absent from the markdown — so a chart/diagram/facsimile's text is
unretrievable no matter how high the OCR resolution. And some raster regions
(a Hindi facsimile pasted mid-page) are never classified as Pictures at all, so
region-based OCR skips them entirely. `image_ocr=True` adds a strictly-additive
pass ON TOP of Docling's clean markdown, appended under a `# Image OCR` anchor
so it is chunked/embedded/retrievable with honest provenance.

A first, naive version OCR'd every page full and appended it — and measurably
BACKFIRED: re-capturing the clean text layer both displaced clean chunks (a URL
chunk fell out of the top-k) and diluted specific facts inside whole-page
blobs. So the pass is a COMPOSITION that adds OCR text ONLY where the clean
layer has nothing (decisions.md #36): each layout-detected Picture is cropped at
high DPI and OCR'd (region); a page with essentially no embedded text layer is
a scan/paste and is OCR'd whole (facsimile); and on ordinary digital pages only
the Devanagari-script lines are kept (a raster Hindi statement pasted into a
text page). Body text is never re-captured. Two engines contribute what each is
good at — Apple Vision for the multilingual Latin/CJK/Cyrillic set (clean,
fast), and EasyOCR for Devanagari (which Vision cannot read on this platform),
from which ONLY lines with real Devanagari letters are kept: a script-identity
filter, so it cannot delete a chart's "149"/"2.4" and it discards EasyOCR's
known Latin corruption ("2025"→"20२5"). The default region-mode Docling text is
never touched, so nothing that ingested before can regress; the only new
content is text that had no other way in.

Lazy import: Docling (and its torch/layout stack), pypdfium2, ocrmac, and
easyocr are the `datum[parse]` extra, imported inside `parse()`/the OCR helpers
on first use, never at module import — the core write path and the markdown
ingest path cost nothing for it.
"""

from __future__ import annotations

import importlib.util
import re
import warnings
from pathlib import Path

from datum.writepath.policies.document import DocumentInput, MarkdownParser, ParsedSection

# Bumped in lockstep with the installed docling; part of the record's
# source_version lineage (the CI-07 tuple), so a docling upgrade that changes
# extraction is a detectable producer change, not a silent re-parse.
_DOCLING_VERSION = "2.118.1"


# Recognition languages we'd LIKE macOS Vision (ocrmac) to read inside images
# — chart labels, diagram/org-chart text, a scanned memo — so image-text is
# read in the languages a corpus uses, not English only. This list is FILTERED
# against what the installed Vision version actually supports at build time
# (see _build_converter): a code Vision doesn't support (e.g. Devanagari/Hindi,
# absent on current macOS) is dropped rather than raising and degrading the
# whole extraction — a lesson from the stress test, where an unsupported
# `hi-IN` in this list silently cut a 48-record parse to 13. ar-SA is included
# because Vision DOES read Arabic (verified on stress corpus #2: the shaped
# RTL partnership statement, incl. Arabic-Indic numerals, reads perfectly at
# high DPI — it was unreadable only while this list omitted the language).
# Scripts Vision lacks (Devanagari, Tamil, Hebrew, Greek, the Indic/SEA/
# Caucasus/Ethiopic set) are handled by SEPARATE engines in the image_ocr
# pass (see _SCRIPT_FAMILIES), not by Vision. The first seven entries are the
# stress-verified core; the tail extends coverage to the other languages
# Vision supports whose SCRIPTS are already in that core (Latin, CJK,
# Cyrillic) — a lexicon hint for diacritics/vocabulary, not a new script,
# so they cannot destabilize the proven reads the way a buried new-script
# entry can (the ar-SA order lesson; new scripts get their own family pass).
_OCR_LANGS_PREFERRED = [
    "en-US", "ja-JP", "de-DE", "fr-FR", "ru-RU", "zh-Hans", "ar-SA",
    "zh-Hant", "uk-UA", "it-IT", "es-ES", "pt-BR", "tr-TR", "vi-VT",
]

# The languages the supplementary image_ocr pass reads by default: the Vision
# set PLUS one language per script family (see _SCRIPT_FAMILIES), so every
# supported script is on by default — "multilingual" means the default
# configuration, not a hidden knob. A family's engine only runs when one of
# its languages is requested AND the engine is available (loud warning
# otherwise), and the crop sparse-gate keeps the large roster cheap on
# Latin-heavy documents.
_IMAGE_OCR_LANGS_DEFAULT = [
    *_OCR_LANGS_PREFERRED,
    "hi-IN", "ta-IN", "th-TH", "ko-KR", "he-IL", "el-GR", "bn-IN", "te-IN",
    "kn-IN", "ml-IN", "gu-IN", "pa-IN", "si-LK", "my-MM", "km-KH", "lo-LA",
    "ka-GE", "hy-AM", "am-ET",
]

# Raster page-bearing inputs worth a supplementary full-page OCR pass. Other
# Docling formats (docx/pptx/xlsx/html/csv) have no raster page to OCR — their
# text is already structured — so the pass is skipped for them even when
# image_ocr is on.
_PAGE_IMAGE_SUFFIXES = {".pdf", ".png", ".jpg", ".jpeg", ".tif", ".tiff", ".bmp", ".gif", ".webp"}

# A PDF page whose embedded text layer is shorter than this (in characters) is
# treated as a FACSIMILE — a scanned/pasted image page with no real text — and
# gets a full-page OCR, because the clean pipeline extracted nothing to
# duplicate. Above it, the page is digital and only its PICTURE regions +
# Devanagari lines are OCR'd, so body text is never re-captured (that
# duplication is what displaced clean chunks and diluted specific facts —
# decisions.md #36). Measured, not tuned: on the stress corpus the one
# facsimile page had 0 chars and the next-smallest digital page had 328, so any
# constant inside that gap classifies identically. 150 sits in the middle and
# reclassifies neither the 0-char facsimile nor the 328-char digital page.
_FACSIMILE_TEXT_LAYER_MAX = 150

# Cap the longest side of the image handed to EasyOCR (Devanagari). The high
# DPI render (scale 4) is needed for Vision's small in-figure text, but EasyOCR
# is CPU-bound and Devanagari stays legible at ~3x; capping bounds ingest time
# without costing the read (verified: the Sec 7.5 facsimile reads at this cap).
_EASYOCR_MAX_SIDE = 2600

# --- script families: non-Latin scripts routed to a non-Vision engine -------
#
# Each family names a script Vision cannot read on this platform, the OCR
# engine that CAN read it, and a LETTER regex (digits excluded on purpose) for
# the script-identity line filter. A line from the family's engine is kept
# only if it carries at least _MIN_SCRIPT_LETTERS script letters AND they are
# at least _MIN_SCRIPT_FRACTION of the line's non-space characters — never a
# string-overlap filter, so it cannot delete a chart's "149"/"2.4", and it
# drops the engines' two false-positive modes (long mostly-Latin misreads —
# the FRACTION kills those — and tiny 2–4-glyph garble — the COUNT kills
# those). Bounds fixed against real OCR output on the stress corpora: genuine
# Hindi sentence lines carry 22–91 Devanagari letters at ~0.9 fraction
# (largest observed junk: 7), and the Tamil statement lines are of the same
# shape; 8 / 0.6 keeps every real line with wide margin.
#
# Engines, each what it is good at (measured, decisions.md #36/#39):
#   arabic     -> Vision itself, but with ar-SA FIRST in its own short
#                 language list. Vision's language_preference is ORDER-
#                 SENSITIVE: with ar-SA last after six Latin/CJK codes it
#                 returned ZERO characters on the (perfectly legible) Arabic
#                 statement crop; ar-SA first reads it flawlessly, shaped RTL
#                 and Arabic-Indic numerals included. So Arabic gets its own
#                 Vision pass, script-filtered — never rely on one long list.
#   devanagari -> EasyOCR ('hi'): reads the script well; mangles Latin (the
#                 filter discards that).
#   tamil      -> Tesseract ('tam'): this EasyOCR release's Tamil model is
#                 broken (checkpoint/charset mismatch, upstream bug), while
#                 tesseract+tam.traineddata reads the shaped statement
#                 perfectly. Requires the `tam` traineddata to be installed;
#                 missing engine = a loud warning, never a silent skip.
_MIN_SCRIPT_LETTERS = 8
_MIN_SCRIPT_FRACTION = 0.6


def _fam(name, prefixes, letters, engine, langs, full_page=False, nllb=None):
    return {
        "name": name,
        "lang_prefixes": set(prefixes),
        "letter_re": re.compile(letters),
        "engine": engine,
        "engine_langs": langs,
        "full_page": full_page,
        "nllb": nllb,  # NLLB-200 source code for the ingest-time English gloss
    }


# The roster. Vision families put their script's language FIRST in a short
# dedicated list (the order lesson above). Tesseract families use
# tessdata_best traineddata ("<code>+eng" so mixed crops keep their Latin
# tokens); each was verified by a render→OCR→readback probe on this machine
# (scripts whose probe fails or whose traineddata is absent warn loudly and
# are skipped, never silently). Letter ranges EXCLUDE each script's native
# digit block where one exists — engines sprinkle native digits into Latin
# lines (the "Marz २०२५" lesson), so digits alone must never qualify a line.
# full_page=True only where a vector-drawn (non-raster) facsimile is a real
# shape for that script's engine to catch: the two measured cases (doc-1
# Hindi, the Arabic statement) plus Vision-engine families, whose full-page
# pass costs ~0.5 s. Tesseract families are crop+facsimile only — measured:
# tesseract's auto segmentation misses dark statement boxes on full pages.
_SCRIPT_FAMILIES: tuple[dict, ...] = (
    # -- scripts Vision reads natively (own pass, own order) --
    _fam("arabic", {"ar", "ars", "fa", "ur"}, "[؀-ۿݐ-ݿ]", "vision", ("ar-SA", "en-US"), full_page=True, nllb="arb_Arab"),
    _fam("thai", {"th"}, "[ก-๏๚-๛]", "vision", ("th-TH", "en-US"), full_page=True, nllb="tha_Thai"),
    _fam("korean", {"ko"}, "[가-힯ᄀ-ᇿ]", "vision", ("ko-KR", "en-US"), full_page=True, nllb="kor_Hang"),
    # -- scripts needing EasyOCR --
    _fam("devanagari", {"hi", "mr", "ne", "sa"}, "[ऀ-॥॰-ॿ]", "easyocr", ("en", "hi"), full_page=True, nllb="hin_Deva"),
    # -- scripts needing Tesseract (Vision lacks them; EasyOCR's Tamil model
    #    is broken upstream and these are the same engine path) --
    _fam("tamil", {"ta"}, "[஀-௿]", "tesseract", "tam+eng", nllb="tam_Taml"),
    _fam("hebrew", {"he", "iw", "yi"}, "[֐-׿]", "tesseract", "heb+eng", nllb="heb_Hebr"),
    _fam("greek", {"el"}, "[Ͱ-Ͽἀ-῿]", "tesseract", "ell+eng", nllb="ell_Grek"),
    _fam("bengali", {"bn", "as"}, "[ঀ-৥ৰ-৿]", "tesseract", "ben+eng", nllb="ben_Beng"),
    _fam("telugu", {"te"}, "[ఀ-౥౰-౿]", "tesseract", "tel+eng", nllb="tel_Telu"),
    _fam("kannada", {"kn"}, "[ಀ-೥೰-೿]", "tesseract", "kan+eng", nllb="kan_Knda"),
    _fam("malayalam", {"ml"}, "[ഀ-൥൰-ൿ]", "tesseract", "mal+eng", nllb="mal_Mlym"),
    _fam("gujarati", {"gu"}, "[઀-૥૰-૿]", "tesseract", "guj+eng", nllb="guj_Gujr"),
    _fam("gurmukhi", {"pa"}, "[਀-੥ੰ-੿]", "tesseract", "pan+eng", nllb="pan_Guru"),
    _fam("sinhala", {"si"}, "[඀-෿]", "tesseract", "sin+eng", nllb="sin_Sinh"),
    _fam("myanmar", {"my"}, "[က-ဿ၊-႟]", "tesseract", "mya+eng", nllb="mya_Mymr"),
    _fam("khmer", {"km"}, "[ក-៟៪-៿]", "tesseract", "khm+eng", nllb="khm_Khmr"),
    _fam("lao", {"lo"}, "[ກ-໏໚-໿]", "tesseract", "lao+eng", nllb="lao_Laoo"),
    _fam("georgian", {"ka"}, "[Ⴀ-ჿ]", "tesseract", "kat+eng", nllb="kat_Geor"),
    _fam("armenian", {"hy"}, "[԰-֏]", "tesseract", "hye+eng", nllb="hye_Armn"),
    _fam("ethiopic", {"am", "ti"}, "[ሀ-፿]", "tesseract", "amh+eng", nllb="amh_Ethi"),
)

# Expensive engines (easyocr/tesseract) run on a cropped image OR a facsimile
# page only when the main Vision pass read essentially nothing there (< this
# many chars): content Vision reads well is Latin/CJK/Cyrillic where a
# foreign-script engine can only HALLUCINATE its own script. Measured, not
# assumed: on a degraded 1-bit fax page whose memo Vision read fine (464
# chars), ten blind tesseract families each emitted hundreds of chars of
# plausible-looking junk in their own scripts, every line passing its own
# per-line filter — the gate is what keeps a 20-family default roster safe.
# The accepted trade, documented: a raster mixing >40 chars of Latin with a
# non-Latin statement relies on the full-page sweeps (devanagari/arabic/thai/
# korean) to catch the non-Latin part; tesseract-family scripts in that mixed
# shape are a known gap.
_CROP_VISION_SPARSE_MAX = 40

# A crop-arbitration winner must carry at least this many script letters, or
# the crop is treated as having no genuine non-Latin script at all. Measured
# floor: every real statement crop read 100–460 script letters; every
# observed hallucinated winner (engines fed noise or a foreign script)
# carried ≤ 25. The cost, documented: a crop whose genuine non-Latin content
# is a very short caption (< 24 letters) is below the noise floor and is
# dropped — full-page sweeps still catch full-size statements.
_MIN_CROP_SCRIPT_LETTERS = 24

# Backwards-compatible aliases (unit-tested names; the devanagari family is
# the same filter it always was).
_DEVANAGARI_LETTER = next(f for f in _SCRIPT_FAMILIES if f["name"] == "devanagari")["letter_re"]


def _families_for(langs: list[str]) -> list[dict]:
    prefixes = {code.split("-")[0].lower() for code in langs}
    return [f for f in _SCRIPT_FAMILIES if f["lang_prefixes"] & prefixes]


def _is_script_line(line: str, letter_re: re.Pattern) -> bool:
    """Script-identity line filter (see _SCRIPT_FAMILIES). Pure logic —
    unit-tested without an OCR engine (tests/writepath/test_image_ocr.py)."""
    letters = len(letter_re.findall(line))
    nonspace = sum(1 for c in line if not c.isspace())
    return (
        letters >= _MIN_SCRIPT_LETTERS
        and nonspace > 0
        and letters >= _MIN_SCRIPT_FRACTION * nonspace
    )


def _is_devanagari_line(line: str) -> bool:
    return _is_script_line(line, _DEVANAGARI_LETTER)


class DoclingParser:
    """Converts a file at `DocumentInput.source_path` to markdown via Docling,
    then delegates sectioning to `MarkdownParser`. Requires `source_path`;
    a DoclingParser fed a text-only DocumentInput is a caller error (route
    plain text/markdown through MarkdownParser instead).

    OCR: on macOS the converter uses `ocrmac` (Apple Vision) with a
    multilingual recognition set (decisions.md #35) — region-based, NOT
    full-page, so a digital PDF's clean embedded text layer is kept and OCR
    is applied only to the image regions (charts, diagrams, scans, non-Latin
    facsimiles) that have no text layer. `use_ocrmac=False` falls back to
    Docling's default engine (for non-macOS or a deployment that prefers it).

    `image_ocr=True` adds the supplementary high-DPI OCR composition described
    in the module docstring (decisions.md #36) — region crops + facsimile pages
    + Devanagari-script lines, additive and off by default. It is the only way
    image-embedded text (chart values, diagram/org-chart labels, a raster
    facsimile) becomes retrievable, because Docling's markdown export drops it.
    """

    version = f"docling-{_DOCLING_VERSION}/md-sections/ocrmac"

    def __init__(
        self,
        use_ocrmac: bool = True,
        force_full_page_ocr: bool = False,
        *,
        image_ocr: bool = False,
        image_ocr_scale: float = 4.0,
        image_ocr_langs: list[str] | None = None,
        doc_metadata: bool = True,
        translation_gloss: bool = True,
        vision_describer=None,
    ) -> None:
        self._use_ocrmac = use_ocrmac
        # Region-based OCR (default) reads text regions that lack a text layer
        # but SKIPS picture regions, so text embedded in diagrams/org-charts/
        # charts stays unread. force_full_page_ocr OCRs the entire page image,
        # reading picture-embedded text too — at the cost of slower ingest and
        # some degradation of an otherwise-clean digital text layer. Opt-in for
        # picture-heavy corpora; measured, not assumed (decisions.md #35).
        # NOTE: even with force_full_page_ocr, Docling's markdown export still
        # drops picture-cluster text (decisions.md #36) — image_ocr is the
        # mechanism that actually recovers it.
        self._force_full_page_ocr = force_full_page_ocr
        self._image_ocr = image_ocr
        self._image_ocr_scale = image_ocr_scale
        self._image_ocr_langs = list(image_ocr_langs) if image_ocr_langs is not None else list(_IMAGE_OCR_LANGS_DEFAULT)
        # PDF document-info metadata (Title/Author/Subject/Keywords) ingested
        # as a small `# Document Metadata` section (decisions.md #39): the
        # fields are real, searchable document properties (a title or keyword
        # tag often exists ONLY there), and nothing else in the pipeline reads
        # them. Cheap (no OCR), so on by default.
        self._doc_metadata = doc_metadata
        # Ingest-time English gloss (decisions.md #41): non-Latin script-family
        # OCR text gets a clearly-labeled NLLB-200 machine translation appended
        # in the same section, so an English (or any-language) query can reach
        # it through every channel — dense, BM25, grep, and the reranker. The
        # gloss is LABELED as machine translation in the text itself: provenance
        # stays honest, and the original script text is always kept first.
        # The picture-understanding slot (decisions.md #43): anything with
        # name/version/describe(image)->str. None (default) = no VLM, no cost.
        # A description is appended to the picture's own section, labeled with
        # the producing model — interpretation, visibly distinct from document
        # text (the same honest-provenance pattern as the NLLB gloss).
        self._vision_describer = vision_describer
        self._translation_gloss = translation_gloss
        self._nllb_model = None  # lazy: ~600M params, loaded on first gloss
        self._nllb_tokenizers: dict[str, object] = {}
        self._nllb_warned = False
        self._converter = None  # lazy: built on first parse()
        self._easy_readers: dict[str, object] = {}  # per-script-family, lazy
        self._family_warned: set[str] = set()  # warn once per missing engine
        self._markdown = MarkdownParser()

        # Encode the extraction mode in the version so a config that changes
        # output is a detectable producer change in the CI-07 lineage, not a
        # silent re-parse.
        mode = "ocrmac" if use_ocrmac else "default"
        if force_full_page_ocr:
            mode += "+fullpage"
        if image_ocr:
            # region (picture crops) + obj (embedded raster objects the layout
            # model missed) + facsimile (full page where no text layer) +
            # script families (script-filtered lines) — the composition, not a
            # blanket full-page pass.
            # scrN = script-family roster size: growing the roster changes
            # extraction output, so it must be a detectable producer change.
            mode += f"+imgocr-rgn+obj+fac+scr{len(_SCRIPT_FAMILIES)}@{image_ocr_scale:g}"
        if doc_metadata:
            mode += "+meta"
        if image_ocr and translation_gloss:
            mode += "+gloss"
        if image_ocr and vision_describer is not None:
            mode += f"+vlm({getattr(vision_describer, 'name', '?')}@{getattr(vision_describer, 'version', '?')})"
        self.version = f"docling-{_DOCLING_VERSION}/md-sections/{mode}"

    def _build_converter(self):
        from docling.document_converter import DocumentConverter  # lazy: datum[parse]

        if not self._use_ocrmac:
            return DocumentConverter()
        try:
            from docling.datamodel.base_models import InputFormat
            from docling.datamodel.pipeline_options import OcrMacOptions, PdfPipelineOptions
            from docling.document_converter import PdfFormatOption

            langs = self._supported_langs(_OCR_LANGS_PREFERRED)
            if not langs:
                return DocumentConverter()  # Vision unavailable -> default engine
            opts = PdfPipelineOptions()
            opts.do_ocr = True  # region-based; the text layer is still used where present
            opts.ocr_options = OcrMacOptions(lang=langs, force_full_page_ocr=self._force_full_page_ocr)
            fmt = PdfFormatOption(pipeline_options=opts)
            return DocumentConverter(format_options={InputFormat.PDF: fmt, InputFormat.IMAGE: fmt})
        except Exception:
            # ocrmac/Vision unavailable (non-macOS): fall back to the default
            # OCR engine rather than fail the whole parse.
            return DocumentConverter()

    def _supported_langs(self, desired: list[str]) -> list[str]:
        """The `desired` OCR languages that the installed macOS Vision version
        actually supports — an unsupported code (Vision validates strictly and
        raises) is dropped here so it can never degrade a parse. Empty list =
        Vision not queryable (non-macOS) or none of `desired` supported.
        Devanagari codes never survive this (Vision lacks them) — they are
        handled by the EasyOCR sub-pass instead."""
        try:
            import Vision  # pyobjc, present with the ocrmac stack on macOS

            req = Vision.VNRecognizeTextRequest.alloc().init()
            supported = set(req.supportedRecognitionLanguagesAndReturnError_(None)[0] or [])
            return [l for l in desired if l in supported]
        except Exception:
            return []

    def _convert(self, source_path: str):
        """Return (markdown, docling_document). The document is kept (not just
        the markdown) so the image-OCR pass can read its picture regions and
        page sizes."""
        if self._converter is None:
            self._converter = self._build_converter()
        result = self._converter.convert(source_path)
        doc = result.document
        return doc.export_to_markdown(), doc

    # --- supplementary image-OCR pass (decisions.md #36) ---
    #
    # Composition, chosen because a blanket full-page pass duplicated the clean
    # text layer and that duplication both DISPLACED clean chunks (a URL chunk
    # fell out of the top-k, a measured regression) and DILUTED specific facts
    # inside whole-page blobs. OCR text now enters the corpus ONLY where the
    # clean layer offers nothing:
    #   • REGION  — each layout-detected Picture is cropped at high DPI and
    #     Vision-OCR'd (chart bars, diagram/org-chart labels). No body text.
    #   • FACSIMILE — a page with essentially no embedded text layer is a
    #     scanned/pasted image; its whole page is OCR'd (nothing to duplicate).
    #   • DEVANAGARI — on digital pages, only the Devanagari-script lines are
    #     kept (a raster Hindi facsimile pasted into an otherwise-text page);
    #     Vision cannot read Devanagari here, EasyOCR can.

    def _vision_text(self, pil, langs: list[str]) -> str:
        from ocrmac import ocrmac  # lazy: datum[parse]

        res = ocrmac.OCR(
            pil, recognition_level="accurate", language_preference=langs or None
        ).recognize()
        return "\n".join(text.strip() for (text, *_rest) in res if text.strip())

    def _describe(self, crop) -> str:
        """The configured VisionDescriber's labeled description of a cropped
        figure, or "" when no describer is configured / it has nothing to say
        / it fails (a broken VLM must never fail the parse — the OCR text of
        the figure still ingests)."""
        if self._vision_describer is None:
            return ""
        try:
            text = self._vision_describer.describe(crop)
        except Exception:
            warnings.warn(
                f"datum: vision describer {getattr(self._vision_describer, 'name', '?')!r} "
                "raised while describing a figure; the figure ingests with OCR text only.",
                UserWarning,
                stacklevel=2,
            )
            return ""
        if not text or not text.strip():
            return ""
        label = f"{getattr(self._vision_describer, 'name', '?')}@{getattr(self._vision_describer, 'version', '?')}"
        return f"Vision description ({label}): {text.strip()}"

    def _gloss(self, family: dict, text: str) -> str:
        """`text` plus a labeled English machine translation (NLLB-200), or
        `text` unchanged when glossing is off/unavailable. Measured need: the
        Arabic statement was fully extracted yet unreachable — an English
        query's dense similarity to pure-Arabic text ranked it 20-33, below
        every retrieval pool. The gloss gives every channel an English handle
        while the original script text stays first and the translation is
        explicitly labeled IN the text as machine output (honest provenance:
        a reader always knows which words the document actually contains)."""
        if not self._translation_gloss or not family.get("nllb") or not text.strip():
            return text
        translated = self._nllb_translate(text, family["nllb"])
        if not translated:
            return text
        return f"{text}\n\nMachine gloss (NLLB-200, {family['nllb']}\u2192eng): {translated}"

    def _nllb_translate(self, text: str, src_lang: str) -> str:
        try:
            if self._nllb_model is None:
                from transformers import AutoModelForSeq2SeqLM  # lazy: heavy

                self._nllb_model = AutoModelForSeq2SeqLM.from_pretrained(
                    "facebook/nllb-200-distilled-600M"
                )
            tok = self._nllb_tokenizers.get(src_lang)
            if tok is None:
                from transformers import AutoTokenizer

                tok = AutoTokenizer.from_pretrained(
                    "facebook/nllb-200-distilled-600M", src_lang=src_lang
                )
                self._nllb_tokenizers[src_lang] = tok
            inputs = tok(text, return_tensors="pt", truncation=True, max_length=512)
            out = self._nllb_model.generate(
                **inputs,
                forced_bos_token_id=tok.convert_tokens_to_ids("eng_Latn"),
                max_length=512,
            )
            return tok.decode(out[0], skip_special_tokens=True).strip()
        except Exception:
            if not self._nllb_warned:
                self._nllb_warned = True
                warnings.warn(
                    "datum: translation_gloss=True but the NLLB-200 model is not "
                    "available (not cached and not downloadable here). Non-Latin "
                    "image-OCR text will be ingested WITHOUT an English gloss — "
                    "retrievable in its own script, weaker for cross-language "
                    "queries.",
                    UserWarning,
                    stacklevel=2,
                )
            return ""

    def _family_available(self, family: dict) -> bool:
        """Is this script family's engine actually usable here? Missing engine
        = a loud warning naming what to install (once per parser), never a
        silent skip — a corpus owner who requested Tamil must not silently get
        no Tamil (§11's no-silent-downscope rule)."""
        name = family["name"]
        if name in self._family_warned:
            return False
        if family["engine"] == "vision":
            ok = bool(self._supported_langs(list(family["engine_langs"])))
            what = f"macOS Vision with {family['engine_langs'][0]}"
        elif family["engine"] == "easyocr":
            ok = importlib.util.find_spec("easyocr") is not None
            what = "the easyocr package"
        else:  # tesseract
            import shutil
            import subprocess

            exe = shutil.which("tesseract")
            ok = False
            if exe:
                try:
                    out = subprocess.run(
                        [exe, "--list-langs"], capture_output=True, text=True, timeout=20
                    )
                    wanted = str(family["engine_langs"]).split("+")[0]
                    ok = wanted in out.stdout
                except (OSError, subprocess.TimeoutExpired):
                    ok = False
            what = f"tesseract with the '{str(family['engine_langs']).split('+')[0]}' traineddata"
        if not ok:
            self._family_warned.add(name)
            warnings.warn(
                f"datum: image_ocr requested the {name} script but {what} is not "
                f"available — {name} text in images will NOT be recovered. Install it "
                "to restore coverage.",
                UserWarning,
                stacklevel=4,
            )
        return ok

    def _family_text(self, family: dict, pil) -> str:
        """OCR `pil` with this family's engine and keep ONLY the lines that
        are genuinely this family's script (see _SCRIPT_FAMILIES). Engines
        mangle other scripts; the filter keeps their wins and drops the
        corruption."""
        if family["engine"] == "vision":
            lines = self._vision_text(pil, list(family["engine_langs"])).splitlines()
        elif family["engine"] == "easyocr":
            lines = self._easyocr_lines(family, pil)
        else:
            lines = self._tesseract_lines(family, pil)
        kept = [ln.strip() for ln in lines if _is_script_line(ln, family["letter_re"]) and ln.strip()]
        return "\n".join(kept)

    def _families_texts_arbitrated(self, families: list[dict], pil, vision_chars: int) -> list[str]:
        """Run the requested families on ONE cropped image and keep only the
        family whose script has the most letters in its (already script-
        filtered) output. A small crop is almost certainly one script, and an
        engine fed a script it cannot read HALLUCINATES its own — measured:
        Tesseract-Tamil emitted plausible-looking Tamil from the Arabic
        statement crop, and that junk passed the per-line filter because it
        genuinely IS Tamil script. Plurality across families kills it: the
        true script's reading always carries far more letters than a
        hallucinated one (237 Arabic vs ~40 junk Tamil on the measured crop).
        Full pages are NOT arbitrated — a page can host two genuine scripts.

        `vision_chars` is how much the main Vision pass read from this crop:
        expensive engines (easyocr/tesseract) are SKIPPED when Vision already
        read it well (>= _CROP_VISION_SPARSE_MAX chars — the crop is Latin/
        CJK/Cyrillic content their scripts can only hallucinate over); Vision-
        engine families are always cheap enough to run."""
        outputs = []
        for family in families:
            if family["engine"] != "vision" and vision_chars >= _CROP_VISION_SPARSE_MAX:
                continue
            text = self._family_text(family, pil)
            if text.strip():
                outputs.append((len(family["letter_re"].findall(text)), family, text))
        if not outputs:
            return []
        outputs.sort(key=lambda triple: -triple[0])
        # The winner must clear the measured junk-noise floor: engines fed
        # noise or a foreign script produce SOME self-script output, and when
        # every candidate is junk, plurality alone would happily crown the
        # biggest junk (measured: 'incest பலவாறு கறு' won a chart crop).
        if outputs[0][0] < _MIN_CROP_SCRIPT_LETTERS:
            return []
        _, family, text = outputs[0]
        return [self._gloss(family, text)]

    def _easyocr_lines(self, family: dict, pil) -> list[str]:
        import numpy as np  # lazy: datum[parse]

        reader = self._easy_readers.get(family["name"])
        if reader is None:
            import easyocr  # lazy: datum[parse]

            reader = easyocr.Reader(list(family["engine_langs"]), gpu=False, verbose=False)
            self._easy_readers[family["name"]] = reader
        img = pil
        longest = max(img.size)
        if longest > _EASYOCR_MAX_SIDE:
            ratio = _EASYOCR_MAX_SIDE / longest
            img = img.resize((max(1, int(img.size[0] * ratio)), max(1, int(img.size[1] * ratio))))
        return list(reader.readtext(np.asarray(img), detail=0))

    def _tesseract_lines(self, family: dict, pil) -> list[str]:
        """Tesseract via stdin/stdout, --psm 6 (a uniform block: these inputs
        are cropped statement boxes, where auto segmentation measurably fails
        on dark backgrounds while the block mode reads them perfectly)."""
        import io
        import subprocess

        # Upsample 2x: the scale-4 render is ~288 DPI; tesseract's accuracy on
        # shaped scripts measurably improves at ~2x that (verified on the
        # Tamil statement crop).
        img = pil.resize((pil.width * 2, pil.height * 2))
        buf = io.BytesIO()
        img.save(buf, format="PNG")
        try:
            out = subprocess.run(
                ["tesseract", "stdin", "stdout", "-l", str(family["engine_langs"]), "--psm", "6"],
                input=buf.getvalue(),
                capture_output=True,
                timeout=120,
            )
        except (OSError, subprocess.TimeoutExpired):
            return []
        if out.returncode != 0:
            return []
        return out.stdout.decode("utf-8", "replace").splitlines()

    @staticmethod
    def _crop_box(l, t, r, b, bottomleft: bool, page_height_pts: float, scale: float):
        """The pixel crop box for a Picture bbox. Docling picture bboxes are
        BOTTOMLEFT-origin (validated on the stress corpus); flip to the top-left
        pixel space pypdfium2 renders in. A silent top-left assumption would
        crop the wrong band and yield empty OCR that looks like 'no image text
        here'. Pure math — unit-tested (tests/writepath/test_image_ocr.py)."""
        if bottomleft:
            top = page_height_pts - t
            bot = page_height_pts - b
        else:
            top, bot = t, b
        return (
            max(0, int(l * scale)),
            max(0, int(min(top, bot) * scale)),
            int(r * scale),
            int(max(top, bot) * scale),
        )

    @classmethod
    def _crop_picture(cls, page_pil, bbox, page_height_pts: float, scale: float):
        from docling_core.types.doc import CoordOrigin  # lazy: datum[parse]

        box = cls._crop_box(
            bbox.l, bbox.t, bbox.r, bbox.b,
            bbox.coord_origin == CoordOrigin.BOTTOMLEFT,
            page_height_pts, scale,
        )
        return page_pil.crop(box)

    @staticmethod
    def _fence(text: str) -> str:
        return "```\n" + text.replace("```", "'''") + "\n```\n"

    def _pictures_by_page(self, doc) -> dict[int, list]:
        by_page: dict[int, list] = {}
        for pic in getattr(doc, "pictures", []) or []:
            if not pic.prov:
                continue
            prov = pic.prov[0]
            by_page.setdefault(prov.page_no, []).append(prov.bbox)
        return by_page

    @staticmethod
    def _image_object_bounds(pdf_page) -> list[tuple[float, float, float, float]]:
        """Bounds (l, b, r, t in points, BOTTOMLEFT origin) of each embedded
        raster image object on the page, from pypdfium2's object list — ground
        truth about "a raster is pasted here", independent of Docling's layout
        model. This is how a facsimile statement pasted mid-page is found even
        when the layout model does not classify it as a Picture (measured on
        stress corpus #2: the Tamil statement was exactly this). Tiny rasters
        (< ~1.5% of page area — logos, bullets) are skipped."""
        page_area = pdf_page.get_width() * pdf_page.get_height()
        out = []
        for obj in pdf_page.get_objects():
            if obj.type != 3:  # FPDF_PAGEOBJ_IMAGE
                continue
            try:
                l, b, r, t = obj.get_bounds()
            except Exception:
                continue
            if (r - l) * (t - b) < 0.015 * page_area:
                continue
            out.append((l, b, r, t))
        return out

    @staticmethod
    def _overlaps_picture(obj_bounds, pic_bboxes, page_height_pts: float) -> bool:
        """True if an image object substantially overlaps a Docling-detected
        Picture (the region pass already OCR'd it; OCRing it again would put
        the same text in two chunks). Both are normalized to BOTTOMLEFT here;
        'substantial' = >50% of the object's own area."""
        from docling_core.types.doc import CoordOrigin  # lazy: datum[parse]

        l, b, r, t = obj_bounds
        area = max(1e-6, (r - l) * (t - b))
        for bbox in pic_bboxes:
            if bbox.coord_origin == CoordOrigin.BOTTOMLEFT:
                pl, pb, pr, pt = bbox.l, bbox.b, bbox.r, bbox.t
            else:
                pl, pb, pr, pt = bbox.l, page_height_pts - bbox.b, bbox.r, page_height_pts - bbox.t
            pb, pt = min(pb, pt), max(pb, pt)
            ix = max(0.0, min(r, pr) - max(l, pl))
            iy = max(0.0, min(t, pt) - max(b, pb))
            if ix * iy > 0.5 * area:
                return True
        return False

    def _image_ocr_markdown(self, source_path: str, doc) -> str:
        """Build the `# Image OCR` block per the composition above. Empty string
        when no engine is available or nothing image-only was found. Each block
        is fenced so stray '#'/'|' in OCR output cannot forge headings/tables."""
        vision_langs = self._supported_langs(self._image_ocr_langs)
        families = [f for f in _families_for(self._image_ocr_langs) if self._family_available(f)]

        if not vision_langs and not families:
            warnings.warn(
                "datum: image_ocr=True but no OCR engine is available (macOS Vision "
                "is not reachable and no requested script family has a usable engine). "
                "Image-embedded text (charts, diagrams, facsimiles) will NOT be "
                "recovered for this file. Install the datum[parse] extra on macOS.",
                UserWarning,
                stacklevel=3,
            )
            return ""

        suffix = Path(source_path).suffix.lower()
        if suffix != ".pdf":
            # A single image file IS the facsimile: full-page OCR, one section.
            from PIL import Image  # lazy: datum[parse]

            pil = Image.open(source_path).convert("RGB")
            parts = []
            if vision_langs:
                parts.append(self._vision_text(pil, vision_langs))
            for family in families:
                ftext = self._family_text(family, pil)
                parts.append(self._gloss(family, ftext) if ftext.strip() else ftext)
            text = "\n".join(p for p in parts if p)
            return f"\n\n# Image OCR\n\n## Image (facsimile)\n\n{self._fence(text)}" if text.strip() else ""

        import pypdfium2 as pdfium  # lazy: datum[parse]

        pics_by_page = self._pictures_by_page(doc)
        pages = getattr(doc, "pages", {}) or {}
        pdf = pdfium.PdfDocument(source_path)
        blocks: list[str] = []
        try:
            for i in range(len(pdf)):
                page_no = i + 1
                page = pdf[i]
                text_layer_len = len(page.get_textpage().get_text_bounded())
                pil = page.render(scale=self._image_ocr_scale).to_pil()
                page_h = page.get_height()

                # REGION: crop + OCR each layout-detected Picture on this page.
                pic_bboxes = pics_by_page.get(page_no, []) if page_no in pages else []
                if vision_langs and pic_bboxes:
                    ph = pages[page_no].size.height
                    for k, bbox in enumerate(pic_bboxes):
                        crop = self._crop_picture(pil, bbox, ph, self._image_ocr_scale)
                        vision_read = self._vision_text(crop, vision_langs)
                        parts = [vision_read]
                        # A detected Picture can itself BE a non-Latin
                        # facsimile: give the requested families a look at the
                        # crop too — script-filtered AND plurality-arbitrated,
                        # so a chart crop contributes nothing and a foreign-
                        # script hallucination loses to the true reading.
                        parts.extend(self._families_texts_arbitrated(families, crop, len(vision_read)))
                        parts.append(self._describe(crop))
                        fig_text = "\n".join(p for p in parts if p)
                        if fig_text.strip():
                            blocks.append(f"## Figure page {page_no} #{k}\n\n{self._fence(fig_text)}")

                is_facsimile = text_layer_len < _FACSIMILE_TEXT_LAYER_MAX

                # OBJECT: embedded raster objects the layout model did NOT
                # classify as Pictures (a pasted facsimile statement). Vision
                # text is kept whole — a raster's text is never in the clean
                # text layer, so it cannot duplicate body text. Skipped on
                # facsimile pages: the full-page pass below covers the whole
                # page, and OCRing the page's one big raster AGAIN just
                # duplicates it into a second chunk (measured on the fax page).
                if not is_facsimile:
                    for k, obj_bounds in enumerate(self._image_object_bounds(page)):
                        if self._overlaps_picture(obj_bounds, pic_bboxes, page_h):
                            continue
                        l, b, r, t = obj_bounds
                        crop = pil.crop(self._crop_box(l, t, r, b, True, page_h, self._image_ocr_scale))
                        vision_read = self._vision_text(crop, vision_langs) if vision_langs else ""
                        parts = [vision_read] if vision_read else []
                        parts.extend(self._families_texts_arbitrated(families, crop, len(vision_read)))
                        parts.append(self._describe(crop))
                        obj_text = "\n".join(p for p in parts if p)
                        if obj_text.strip():
                            blocks.append(f"## Image page {page_no} #{k}\n\n{self._fence(obj_text)}")

                if is_facsimile:
                    # FACSIMILE: no text layer to duplicate — OCR the whole
                    # page. Non-Vision families are sparse-gated here exactly
                    # like crops: when Vision already read the scan well, the
                    # page is a script Vision knows and blind engines can only
                    # hallucinate over it (the ten-junk-families lesson);
                    # when Vision reads ~nothing, the scan is in a script it
                    # lacks — precisely when the families must run.
                    vision_read = self._vision_text(pil, vision_langs) if vision_langs else ""
                    parts = [vision_read] if vision_read else []
                    for family in families:
                        # Vision families always run (cheap, self-filtering —
                        # an Arabic fax reads as ~nothing under the main list,
                        # so the sparse signal alone can't route to them);
                        # expensive engines only when Vision read ~nothing.
                        if family["engine"] == "vision" or len(vision_read) < _CROP_VISION_SPARSE_MAX:
                            text = self._family_text(family, pil)
                            parts.append(self._gloss(family, text) if text.strip() else text)
                    text = "\n".join(p for p in parts if p)
                    if text.strip():
                        blocks.append(f"## Page {page_no} (facsimile)\n\n{self._fence(text)}")
                else:
                    # DIGITAL page: full-page sweep only for families that
                    # need it (a vector-drawn facsimile has no image object to
                    # crop — the doc-1 Hindi statement is one). Script-filtered,
                    # so the Latin/CJK body is never re-captured.
                    for family in families:
                        if not family["full_page"]:
                            continue
                        text = self._family_text(family, pil)
                        if text.strip():
                            text = self._gloss(family, text)
                            blocks.append(f"## Page {page_no} ({family['name']})\n\n{self._fence(text)}")
        finally:
            pdf.close()

        if not blocks:
            return ""
        return "\n\n# Image OCR\n\n" + "\n".join(blocks)

    def _metadata_markdown(self, source_path: str) -> str:
        """PDF document-info metadata as a small `# Document Metadata` section
        (fenced — a metadata string must not be able to forge a heading).
        Title/Author/Subject/Keywords are real, searchable document properties
        that often exist ONLY in the info dictionary; nothing else in the
        pipeline surfaces them (decisions.md #39)."""
        if Path(source_path).suffix.lower() != ".pdf":
            return ""
        try:
            import pypdfium2 as pdfium  # lazy: datum[parse]

            pdf = pdfium.PdfDocument(source_path)
            try:
                fields = []
                for key in ("Title", "Author", "Subject", "Keywords", "Creator", "Producer"):
                    value = pdf.get_metadata_value(key)
                    if value and value.strip():
                        fields.append(f"{key}: {value.strip()}")
            finally:
                pdf.close()
        except Exception:
            return ""  # unreadable info dict = no metadata section, not a failed parse
        if not fields:
            return ""
        return "\n\n# Document Metadata\n\n" + self._fence("\n".join(fields))

    def parse(self, raw: DocumentInput) -> list[ParsedSection]:
        if not raw.source_path:
            raise ValueError(
                "DoclingParser needs DocumentInput.source_path (a file to convert); "
                "route plain text through MarkdownParser instead."
            )
        markdown, doc = self._convert(raw.source_path)
        if self._doc_metadata:
            markdown = markdown + self._metadata_markdown(raw.source_path)
        if self._image_ocr and Path(raw.source_path).suffix.lower() in _PAGE_IMAGE_SUFFIXES:
            supplement = self._image_ocr_markdown(raw.source_path, doc)
            if supplement:
                markdown = markdown + supplement
        # Reuse the markdown sectioner on Docling's output, keyed by the same
        # source_id so section paths match the text-ingest convention.
        as_markdown = DocumentInput(
            source_id=raw.source_id,
            policy_id=raw.policy_id,
            text=markdown,
            content_type="text/markdown",
            observed_at=raw.observed_at,
        )
        return self._markdown.parse(as_markdown)
