"""Unit tests for the deterministic pieces of the DoclingParser image-OCR
composition (decisions.md #36).

These cover the two silent-failure-mode helpers — the Devanagari script filter
and the picture-crop coordinate flip — WITHOUT needing Docling, an OCR engine,
or a PDF, so they run in the fast suite. The end-to-end recovery (that a real
chart/diagram/facsimile becomes retrievable) is proven separately against the
real stress corpus; these lock in the logic that a coordinate or threshold
regression would silently break.
"""

from __future__ import annotations

from datum.writepath.policies.docling_parser import (
    DoclingParser,
    _is_devanagari_line,
)
from datum.writepath.policies.document import DocumentInput


# --- Devanagari script filter ---------------------------------------------

# Genuine Hindi sentence fragments from the stress corpus's Sec 7.5 facsimile
# (as EasyOCR read them): long, majority-Devanagari.
_REAL_HINDI = [
    "मानसून अवधि (जून-सितम्बर) के दौरान सतही पुनःआपूर्ति हर छह सप्ताह में केवल एक बार संभव होती है| इस कारण स्टेशन",
    "पर खाद्य एवं ईंधन का भंडार न्यूनतम बारह सप्ताह के स्तर पर रखा जाता है| आपूर्ति पोत का संचालन चेन्नई स्थित साझेदार",
    "संस्था द्वारा किया जाता है|",
]

# EasyOCR's two false-Devanagari modes, observed on non-Hindi pages:
# long mostly-Latin misreads, and tiny 2–4-glyph garble.
_JUNK = [
    "X#टir #1# #+=ड् |=}श1F#/:=1# Talt=1 raY-Y7AEI#Li +iJ=lA=t ड् # cकD",
    "hands well. (signed) E. Grunwald ARCHIVE COPY - BOX I2 c्oाtpeagट",
    "ड्ढै &्ँै",
    "&्ँै",
    "ड्लै",
    "ड्ढै",
]


def test_devanagari_filter_keeps_real_sentence_lines():
    assert all(_is_devanagari_line(ln) for ln in _REAL_HINDI)


def test_devanagari_filter_drops_easyocr_false_positives():
    # Every observed junk line must be rejected — this is what keeps the
    # corpus clean; a regression here re-introduces OCR-garbage chunks.
    kept = [ln for ln in _JUNK if _is_devanagari_line(ln)]
    assert kept == [], f"junk survived the Devanagari filter: {kept!r}"


def test_devanagari_filter_rejects_pure_latin_and_digits():
    assert not _is_devanagari_line("Vessel Operations 35%")
    assert not _is_devanagari_line("Doc MTRC-AR-2025")
    assert not _is_devanagari_line("")


# --- picture-crop coordinate flip -----------------------------------------


def test_crop_box_bottomleft_flip_matches_validated_geometry():
    # pic#1 on stress page 4 (station-layout diagram): bbox l=50 t=675 r=545
    # b=378 in BOTTOMLEFT origin, page height 842 pts, render scale 4. The flip
    # must map it to the middle band of the page (validated: this crop is what
    # recovers "MODULE E" / "22 berths"). top = 842-675 = 167, bot = 842-378 =
    # 464 -> pixels ×4.
    box = DoclingParser._crop_box(50, 675, 545, 378, True, 842, 4.0)
    assert box == (200, 668, 2180, 1856), box


def test_crop_box_topleft_is_not_flipped():
    # Same numbers, top-left origin: no flip, y runs t..b directly.
    box = DoclingParser._crop_box(50, 378, 545, 675, False, 842, 4.0)
    assert box == (200, 1512, 2180, 2700), box


def test_crop_box_never_negative():
    box = DoclingParser._crop_box(-5, 1000, 100, 900, True, 842, 4.0)
    assert box[0] >= 0 and box[1] >= 0


# --- version lineage + guard rails ----------------------------------------


def test_version_encodes_image_ocr_mode():
    # An extraction-changing config must be a detectable producer change in the
    # CI-07 source_version lineage (decisions.md #36), not a silent re-parse.
    off = DoclingParser().version
    on = DoclingParser(image_ocr=True).version
    assert off != on
    assert "imgocr" in on and "imgocr" not in off


def test_image_ocr_is_off_by_default():
    # Additive: nothing that ingested before can regress.
    assert DoclingParser()._image_ocr is False


def test_parse_still_requires_a_source_path():
    import pytest

    with pytest.raises(ValueError):
        DoclingParser(image_ocr=True).parse(
            DocumentInput(source_id="x", policy_id="default-acl", text="hi", content_type="text/plain")
        )


# --- script families (decisions.md #39) -------------------------------------


def test_families_resolve_from_requested_languages():
    from datum.writepath.policies.docling_parser import _families_for

    names = [f["name"] for f in _families_for(["en-US", "hi-IN", "ta-IN", "ar-SA"])]
    # Arabic gets its own Vision pass (ar-SA FIRST — Vision's language list is
    # order-sensitive: ar-SA buried after six Latin/CJK codes read ZERO chars
    # off a legible Arabic statement, measured); Devanagari and Tamil each
    # need a non-Vision engine.
    assert names == ["arabic", "devanagari", "tamil"]
    assert _families_for(["en-US", "de-DE"]) == []  # Latin-only corpus: no family runs


def test_full_roster_covers_twenty_scripts_and_defaults_request_all():
    from datum.writepath.policies.docling_parser import (
        _IMAGE_OCR_LANGS_DEFAULT,
        _SCRIPT_FAMILIES,
        _families_for,
    )

    # The roster (decisions.md #40): 20 script families, each with an engine
    # that was render→OCR→readback-verified on this platform (18 strong, 2
    # weak — gujarati/myanmar — kept as best-available and documented).
    assert len(_SCRIPT_FAMILIES) == 20
    # The DEFAULT language list must activate every family — "multilingual"
    # means the default configuration, not a hidden knob.
    active = {f["name"] for f in _families_for(_IMAGE_OCR_LANGS_DEFAULT)}
    assert active == {f["name"] for f in _SCRIPT_FAMILIES}


def test_script_letter_ranges_are_disjoint_across_families():
    # A char matching two families' letter regexes would make plurality
    # arbitration ambiguous. Probe each family's own sample letters against
    # every other family's regex.
    from datum.writepath.policies.docling_parser import _SCRIPT_FAMILIES

    samples = {
        "arabic": "المحطة", "thai": "สถานี", "korean": "관측소",
        "devanagari": "गहराई", "tamil": "நிலையம்", "hebrew": "התחנה",
        "greek": "σταθμός", "bengali": "সমুদ্রের", "telugu": "సముద్రం",
        "kannada": "ನಿಲ್ದಾಣ", "malayalam": "ആഴത്തിൽ", "gujarati": "દરિયાની",
        "gurmukhi": "ਸਮੁੰਦਰ", "sinhala": "මුහුද", "myanmar": "ပင်လယ်",
        "khmer": "ជម្រៅ", "lao": "ສະຖານີ", "georgian": "სადგური",
        "armenian": "Կայանը", "ethiopic": "ጣቢያው",
    }
    for fam in _SCRIPT_FAMILIES:
        for other_name, text in samples.items():
            hits = len(fam["letter_re"].findall(text))
            if other_name == fam["name"]:
                assert hits >= 3, f"{fam['name']} regex misses its own script"
            else:
                assert hits == 0, f"{fam['name']} regex matches {other_name} text"


def test_crop_arbitration_keeps_plurality_script_only():
    # An engine fed a foreign script HALLUCINATES its own (measured: Tesseract
    # emitted plausible Tamil from the Arabic statement crop, and it passed
    # the per-line filter because it IS Tamil script). On one crop, only the
    # family with the most script letters survives.
    from datum.writepath.policies.docling_parser import DoclingParser, _SCRIPT_FAMILIES

    p = DoclingParser(image_ocr=True, translation_gloss=False)  # gloss off: arbitration is the unit
    arabic = next(f for f in _SCRIPT_FAMILIES if f["name"] == "arabic")
    tamil = next(f for f in _SCRIPT_FAMILIES if f["name"] == "tamil")
    outs = {
        "arabic": "يقع مرصد ميراج ١ على الحافة الجنوبية لكثبان القصر عند انخفاض مدى الرؤية",
        "tamil": "பவம் பதி வி பேதி இம புத்கேயி",  # short hallucinated junk
    }
    p._family_text = lambda fam, pil: outs[fam["name"]]  # engines stubbed; arbitration is the unit
    # vision_chars=0: the crop read sparse, so non-vision engines run too.
    kept = p._families_texts_arbitrated([arabic, tamil], pil=None, vision_chars=0)
    assert kept == [outs["arabic"]], "plurality must keep the true (Arabic) reading only"


def test_sparse_gate_skips_expensive_engines_on_well_read_crops():
    # A crop the main Vision pass already read well (>= the sparse threshold)
    # is Latin/CJK/Cyrillic content a foreign-script engine can only
    # hallucinate over — tesseract/easyocr families are skipped there, while
    # Vision-engine families (cheap, order-fixed) still run.
    from datum.writepath.policies.docling_parser import (
        _CROP_VISION_SPARSE_MAX,
        _SCRIPT_FAMILIES,
        DoclingParser,
    )

    p = DoclingParser(image_ocr=True, translation_gloss=False)
    ran = []
    arabic = next(f for f in _SCRIPT_FAMILIES if f["name"] == "arabic")     # vision engine
    tamil = next(f for f in _SCRIPT_FAMILIES if f["name"] == "tamil")       # tesseract engine
    p._family_text = lambda fam, pil: (ran.append(fam["name"]), "")[1]
    p._families_texts_arbitrated([arabic, tamil], pil=None, vision_chars=_CROP_VISION_SPARSE_MAX)
    assert ran == ["arabic"], f"expected only the vision family to run, got {ran}"


def test_tamil_script_filter_keeps_real_lines_and_drops_latin():
    from datum.writepath.policies.docling_parser import _SCRIPT_FAMILIES, _is_script_line

    tamil = next(f for f in _SCRIPT_FAMILIES if f["name"] == "tamil")
    # Real lines as Tesseract read them off the stress-2 statement crop.
    real = [
        "காவேரி டெல்டா நிலையத்தின்‌ கடல்‌ நங்கூரங்கள்‌ மணிக்கு 180 கிலோமீட்டர்‌ வேகக்‌",
        "தானியங்கு முறையில்‌ குறைந்த ஆற்றல்‌ நிலைக்கு மாறும்‌.",
    ]
    junk = [
        "Oct 15 - Nov 30 Twice weekly Cooperative boats (Nagapattinam)",  # Latin body text
        "J F M A M J J A 5 ௦ N D",  # axis labels with one stray Tamil glyph
        "௪88 : 2 1991 « NOILNEIYLSIG",  # garbled misread, 1 Tamil letter
    ]
    assert all(_is_script_line(ln, tamil["letter_re"]) for ln in real)
    assert not any(_is_script_line(ln, tamil["letter_re"]) for ln in junk)


def test_image_object_area_floor_is_pure_math():
    # Tiny rasters (logos, bullets) are skipped; statement-sized ones kept.
    # 0.015 of a 595x842pt page = ~7,516 pt^2; the stress-2 Tamil statement
    # box (479 x 102 pt = ~48,858) clears it, a 40x40 logo does not.
    page_area = 595.0 * 842.0
    assert (537 - 58) * (157 - 55) > 0.015 * page_area
    assert 40 * 40 < 0.015 * page_area


def test_version_encodes_script_families_and_metadata():
    on = DoclingParser(image_ocr=True).version
    assert "+scr20@" in on and "+obj" in on  # 20-family roster + image-object pass
    assert "+meta" in on  # metadata ingestion is on by default
    no_meta = DoclingParser(doc_metadata=False).version
    assert "+meta" not in no_meta


def test_metadata_markdown_is_fenced_and_pdf_only(tmp_path):
    p = DoclingParser()
    # Non-PDF: no metadata section, ever.
    assert p._metadata_markdown(str(tmp_path / "x.docx")) == ""
    # Unreadable/nonexistent PDF: empty string, never a raised parse failure.
    assert p._metadata_markdown(str(tmp_path / "missing.pdf")) == ""


# --- VisionDescriber slot (decisions.md #43) ---------------------------------


def test_vision_describer_output_is_labeled_with_model_identity():
    class Scripted:
        name = "acme-vlm"
        version = "2026-01"

        def describe(self, image):
            return "A Gantt chart; green bars mark programme-office rotations May-October."

    p = DoclingParser(image_ocr=True, vision_describer=Scripted())
    out = p._describe(None)
    # The description is IN-TEXT labeled with the producing model (CI-07
    # lineage): a reader can always tell interpretation from document text.
    assert out.startswith("Vision description (acme-vlm@2026-01):")
    assert "green bars" in out
    # ...and the parser version advertises the configured describer.
    assert "+vlm(acme-vlm@2026-01)" in p.version


def test_broken_describer_warns_but_never_fails_the_parse():
    import warnings as w

    class Broken:
        name = "broken"
        version = "v0"

        def describe(self, image):
            raise RuntimeError("VLM API down")

    p = DoclingParser(image_ocr=True, vision_describer=Broken())
    with w.catch_warnings(record=True) as caught:
        w.simplefilter("always")
        assert p._describe(None) == ""  # figure still ingests, OCR-only
    assert any("vision describer" in str(c.message) for c in caught)


def test_no_describer_means_no_output_and_no_version_tag():
    p = DoclingParser(image_ocr=True)
    assert p._describe(None) == ""
    assert "+vlm" not in p.version
