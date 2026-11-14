"""Prepare one complete chunk plan from saved, immutable Docling evidence."""

import hashlib
import warnings
from importlib.metadata import version


class ChunkingError(ValueError):
    def __init__(self, code, detail):
        super().__init__(detail)
        self.code = code
        self.detail = detail


def prepare_chunks(raw, sources, *, token_limit=512):
    import tiktoken
    from docling_core.transforms.chunker import HybridChunker
    from docling_core.transforms.chunker.tokenizer.openai import OpenAITokenizer
    from docling_core.types.doc import ContentLayer, DoclingDocument, SectionHeaderItem, TitleItem

    class DocumentTokenizer(OpenAITokenizer):
        def count_tokens(self, text):
            return len(self.tokenizer.encode_ordinary(text))

        def get_tokenizer(self):
            # Docling's text splitter accepts this counter as well as encodings.
            return self.count_tokens

    if type(token_limit) is not int or not 32 <= token_limit <= 8192:
        raise ChunkingError(
            "INVALID_CHUNK_LIMIT", "The chunk limit must be between 32 and 8192 tokens."
        )
    try:
        document = DoclingDocument.model_validate(raw)
    except ValueError as exc:
        raise ChunkingError(
            "INVALID_CHUNK_SOURCE", "The saved parser artifact is invalid."
        ) from exc
    encoding = tiktoken.get_encoding("cl100k_base")
    by_ref = {source["provider_ref"]: source for source in sources}
    available_refs = {
        item.self_ref for item in [*document.texts, *document.tables, *document.pictures]
    }
    if (
        len(by_ref) != len(sources)
        or len({source["element_id"] for source in sources}) != len(sources)
        or not set(by_ref).issubset(available_refs)
    ):
        raise ChunkingError(
            "CHUNK_SOURCE_UNAVAILABLE", "Source identities do not match the parser artifact."
        )
    items = [
        item
        for item, _ in document.iterate_items(
            included_content_layers={ContentLayer.BODY}, traverse_pictures=False
        )
    ]
    by_item_ref = {item.self_ref: item for item in items}
    headings, context = {}, {}
    for item in items:
        if isinstance(item, TitleItem | SectionHeaderItem):
            level = item.level if isinstance(item, SectionHeaderItem) else 0
            headings = {key: value for key, value in headings.items() if key < level}
            headings[level] = item
        context[item.self_ref] = list(headings.values())
        # Docling serializes attached footnotes even when figure children aren't traversed.
        for footnote in getattr(item, "footnotes", []):
            context[footnote.cref] = list(headings.values())

    chunker = HybridChunker(
        tokenizer=DocumentTokenizer(tokenizer=encoding, max_tokens=token_limit),
        merge_peers=True,
        always_emit_headings=True,
    )
    with warnings.catch_warnings(record=True) as observed:
        warnings.simplefilter("always")
        try:
            raw_chunks = list(chunker.chunk(dl_doc=document))
        except ValueError as exc:
            raise ChunkingError(
                "CHUNKING_FAILED", "The source could not be divided into chunks."
            ) from exc
    chunks = []
    for chunk in raw_chunks:
        refs, context_refs = [], set()
        if chunk.meta.model_dump(include={"captions"})["captions"]:
            raise ChunkingError("CHUNK_CONTEXT_LOST", "Caption source mapping is unsupported.")
        if not chunk.text and [
            getattr(by_item_ref.get(item.self_ref), "text", None) for item in chunk.meta.doc_items
        ] != (chunk.meta.headings or []):
            raise ChunkingError(
                "CHUNK_CONTEXT_LOST", "A heading-only chunk lost its source context."
            )
        for item in chunk.meta.doc_items:
            if chunk.text:
                active = context.get(item.self_ref, [])
                if [heading.text for heading in active] != (chunk.meta.headings or []):
                    raise ChunkingError(
                        "CHUNK_CONTEXT_LOST",
                        "The chunker changed or omitted source heading context.",
                    )
                refs.extend(heading.self_ref for heading in active)
                context_refs.update(heading.self_ref for heading in active)
            refs.append(item.self_ref)
        links = []
        for ref in dict.fromkeys(refs):
            source = by_ref.get(ref)
            if source is None or not source["locations"]:
                raise ChunkingError(
                    "CHUNK_SOURCE_UNAVAILABLE", "Chunk content has no located source element."
                )
            links.append(
                {
                    "element_id": source["element_id"],
                    "role": "context" if ref in context_refs else "body",
                }
            )
        text = chunker.contextualize(chunk)
        tokens = len(encoding.encode_ordinary(text))
        if not text.strip() or not links or tokens > token_limit:
            raise ChunkingError(
                "INVALID_CHUNK", "A chunk is empty, unlocated or exceeds its token limit."
            )
        chunks.append(
            {
                "ordinal": len(chunks) + 1,
                "text": text,
                "tokens": tokens,
                "sha256": hashlib.sha256(text.encode()).hexdigest(),
                "sources": links,
            }
        )
    referenced = {source["element_id"] for chunk in chunks for source in chunk["sources"]}
    if not chunks:
        raise ChunkingError("NO_INDEXABLE_CONTENT", "No source-linked body content can be indexed.")
    body_refs = {item.self_ref for item in items}
    if any(
        source["provider_ref"] in body_refs and source["element_id"] not in referenced
        for source in sources
    ):
        raise ChunkingError(
            "CHUNK_BODY_OMITTED", "The chunker omitted a located body source element."
        )
    return {
        "chunks": chunks,
        "exclusions": [
            {"element_id": source["element_id"], "reason": "outside_body"}
            for source in sources
            if source["element_id"] not in referenced
        ],
        "warnings": [{"code": "CHUNKER_WARNING", "count": len(observed)}] if observed else [],
        "manifest": {
            "chunker": "docling_hybrid",
            "docling_version": version("docling"),
            "docling_core_version": version("docling-core"),
            "tokenizer": "cl100k_base",
            "token_limit": token_limit,
            "merge_peers": True,
            "always_emit_headings": True,
            "preparation_version": 2,
        },
    }
