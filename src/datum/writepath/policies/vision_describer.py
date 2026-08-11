"""VisionDescriber: the picture-understanding slot in the image-OCR pass
(decisions.md #43).

OCR reads TEXT in images; it cannot read a colour-coded Gantt bar, a trend in
a line chart's pixels, or a diagram's spatial relationships. That class of
understanding needs a vision-language model — and which VLM is a deployment
choice (a frontier API for an enterprise, a local model for an air-gapped
site, none at all for a text corpus). So, like the Embedder and Reranker
before it, it is a versioned Protocol slot: `DoclingParser(vision_describer=…)`
accepts anything with `name`, `version`, and `describe(image) -> str`, and the
description lands in the SAME section as the picture's OCR text, explicitly
labeled with the producing model — a reader always knows those words are a
model's interpretation, not document text (the same honest-provenance pattern
as the NLLB gloss).

The default is None: no model, no silent behavior, zero cost. The reference
adapter below (granite-docling-258M via mlx, Apple-Silicon-only) proves the
slot end to end on this machine; its output quality is what a 258M model
gives — an enterprise plugs a frontier VLM into the same three-member
Protocol and every downstream layer (chunking, embedding, BM25, rerank,
provenance) benefits unchanged.
"""

from __future__ import annotations

from typing import Any, Protocol


class VisionDescriber(Protocol):
    """What the image-OCR pass requires of a picture-understanding model.
    `name`/`version` are stamped into the description's in-text label (the
    CI-07 lineage discipline: a model swap must be visible in the corpus, not
    a silent change of interpretation)."""

    name: str
    version: str

    def describe(self, image: Any) -> str:
        """A natural-language description of a PIL image: what the figure
        shows, including information carried by colour, position, or shape
        that OCR cannot read. Return "" for images with nothing to say."""
        ...


_DEFAULT_PROMPT = (
    "Describe this figure for a search index: what it shows, the values or "
    "categories it encodes (including anything encoded only by colour or "
    "position), and any legend. Be factual and complete; do not speculate."
)


class MLXVisionDescriber:
    """Reference adapter: granite-docling-258M via mlx_vlm (Apple Silicon,
    fully local). Small-model quality — measured, and honestly documented in
    decisions.md #43 — but it proves the slot with a real model; a deployment
    with a frontier VLM implements the same Protocol against its API."""

    def __init__(self, model_name: str = "ibm-granite/granite-docling-258M-mlx", prompt: str = _DEFAULT_PROMPT) -> None:
        self.name = model_name
        self.version = "mlx-vlm"
        self._prompt = prompt
        self._model = None
        self._processor = None
        self._config = None

    def _load(self):
        if self._model is None:
            from mlx_vlm import load  # lazy: Apple-Silicon extra
            from mlx_vlm.utils import load_config

            self._model, self._processor = load(self.name)
            self._config = load_config(self.name)
        return self._model, self._processor, self._config

    def describe(self, image: Any) -> str:
        import tempfile

        from mlx_vlm import generate
        from mlx_vlm.prompt_utils import apply_chat_template

        model, processor, config = self._load()
        with tempfile.NamedTemporaryFile(suffix=".png") as f:
            image.save(f.name)
            prompt = apply_chat_template(processor, config, self._prompt, num_images=1)
            out = generate(model, processor, prompt, image=[f.name], max_tokens=300, verbose=False)
        text = out.text if hasattr(out, "text") else str(out)
        return text.strip()
