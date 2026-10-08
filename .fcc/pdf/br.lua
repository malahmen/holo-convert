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

-- `text <br> text` leaves a Space on each side of the break. LaTeX ignores
-- them, but Word keeps the one after it, so the second line started with a
-- blank (" text"). Drop spaces that touch a line break. Inlines runs after the
-- RawInline pass above, so it sees the new LineBreaks.
function Inlines(inls)
  for i = #inls, 1, -1 do
    if inls[i] and inls[i].t == "LineBreak" then
      if inls[i + 1] and inls[i + 1].t == "Space" then inls:remove(i + 1) end
      if inls[i - 1] and inls[i - 1].t == "Space" then inls:remove(i - 1) end
    end
  end
  return inls
end
