"""Join adjacent whole passages when all linked sources share one physical page."""


def same_page_groups(chunks_and_pages, token_count, limit):
    group, text, page = [], "", None
    for chunk, pages in chunks_and_pages:
        passage = chunk["text"]
        if token_count(passage) > limit:
            raise ValueError("An original chunk exceeds the packing limit")
        chunk_page = next(iter(pages)) if len(pages) == 1 else None
        if group and chunk_page is not None and chunk_page == page:
            combined = text + "\n\n" + passage
            if token_count(combined) <= limit:
                text = combined
                group.append(chunk)
                continue
        if group:
            yield text, group
        group, text, page = [chunk], passage, chunk_page
    if group:
        yield text, group
