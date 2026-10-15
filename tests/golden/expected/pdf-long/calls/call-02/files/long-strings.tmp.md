# Long strings

Text, URLs and code wider than their space. Hyphenation is off in the PDF, so
none of these could break before.

| Setting | Value | Notes |
| --- | --- | --- |
| endpoint | https://registry.example.internal/v2/projects/platform-engineering/repositories/holo-convert/artifacts?page_size=100 | a bare URL |
| link | [the registry](https://registry.example.internal/v2/projects/platform-engineering/repositories/holo-convert) | a link with text |
| word | Donaudampfschifffahrtselektrizitätenhauptbetriebswerkbauunterbeamtengesellschaft | no separator at all |
| `a_very_long_configuration_key_name_that_never_ends` | short | code in a cell |

In prose, a path such as /var/lib/holo-convert/cache/rendered/diagrams/2026/october/report-final.svg
and a command such as `holo-convert.sh --engine container --from md --to pdf --title-page --toc docs/report.md`
must wrap at the margin too, while short `code` and ordinary words wrap as before.

LaTeX's special characters survive the split: `a_b{c}%d#e&f$g~h^i\j_and_more_text`.

## A heading with averyveryverylongwordthatstaysuntouched

Headings are left alone: their text is also the bookmark and the TOC entry.
