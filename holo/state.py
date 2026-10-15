"""The engine's run state - holo-convert.sh's globals, in one place.

Names keep the bash spelling, lower-cased, so the port can be read side by
side with the script.
"""
import os

# The repository root: the canonical .fcc/ bundle lives there, next to holo/.
REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CANONICAL_FCC = os.path.join(REPO, ".fcc")

FCC_DIR = ".fcc"
TITLE_PAGES_DIR = ".fcc/title-pages"
PANDOC_MIN = "2.10"
# + lists_without_preceding_blankline: a list right after a paragraph line, as
# GitHub reads it (see holo-convert.sh).
MD_INPUT_FORMAT = "markdown+gfm_auto_identifiers+lists_without_preceding_blankline"
DOCX_DEFAULT_REFERENCE = ".fcc/docx/reference.docx"
DOCX_PLAIN_REFERENCE = ".fcc/docx/reference-plain.docx"
DOCX_CONFIG = ".fcc/docx/config"
TOC_TITLE = "Contents"


class State:
    def __init__(self):
        self.output_dir = "./output"
        self.source_format = ""
        self.output_format = ""
        self.selected_files = []
        self.pandoc_version = ""
        self.setup_deps = False
        self.with_optional = False
        self.md_variant = "gfm"
        self.check_links = True
        self.fix_links = False
        self.engine_font = ""
        self.engine_reference = ""
        self.docx_letterhead = False
        self.docx_author = ""
        self.docx_classification = ""
        self.docx_version = ""
        self.docx_date = ""
        self.docx_logo = ""
        self.title_img_cache = ""
        self.use_title_page = False
        self.tp_header = ""
        self.tp_footer = ""
        self.tp_pagenum = ""
        self.toc_placed_in_title = False
        self.apply_substitutions = False
        self.strip_rules = False
        self.unwrap_wikilinks = False
        self.raster_svg = False
        self.concat = False
        self.concat_pagebreak = True
        self.docx_page_size = "a4"
        self.use_toc = False
        self.toc_depth = "3"
        self.pdf_engine = ""
        self.pdf_font = ""
        self.available_engines = []
        self.monofont_tex = ""
        self.header_tex = ""
        self.docx_font = ""
        self.docx_mono = ""
        self.docx_reference_doc = ""
        self.output_file = ""

    def is_latex_engine(self) -> bool:
        return self.pdf_engine in ("xelatex", "lualatex", "pdflatex")

    def is_builtin_docx_ref(self) -> bool:
        return self.docx_reference_doc in (DOCX_DEFAULT_REFERENCE, DOCX_PLAIN_REFERENCE)


S = State()
