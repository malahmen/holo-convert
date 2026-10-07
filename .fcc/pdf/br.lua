-- br.lua
-- Turns an inline HTML line break into a real line break, so a cell like
--
--   | text | text <br> text |
--
-- renders on two lines instead of losing the break. pandoc keeps `<br>` as
-- raw HTML, which the LaTeX and DOCX writers drop: the cell came out as
-- "text  text" (and "one<br>two" as "onetwo").
--
-- Recognised (any case, alone in the raw inline): <br>  <br/>  <br />
--
-- Emits a pandoc LineBreak, which each writer renders natively:
--   LaTeX → \\ (pandoc wraps a table cell that has one in a minipage/\vtop,
--           so it breaks the line, not the table row)
--   DOCX  → a Word line break (<w:br/>)
--   HTML  → <br /> (the HTML PDF engines)
-- Works the same outside tables: a <br> in a paragraph becomes a line break.

function RawInline(el)
  if el.format == "html" and el.text:lower():match("^<br%s*/?>$") then
    return pandoc.LineBreak()
  end
end
