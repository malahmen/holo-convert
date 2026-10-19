-- breakable.lua
-- LaTeX/PDF only: let long words, URLs and inline code break across lines.
--
-- header.tex switches hyphenation off, so TeX can only break at spaces. A
-- string longer than a table column - a URL, a path, a long compound word, an
-- identifier in inline code - then runs into the next column or off the page,
-- and the PDF still comes out (exit 0). Inline code is worse: header.tex draws
-- it in a \colorbox, which never breaks at all, not even at its spaces.
--
-- So strings longer than MIN_LEN get break opportunities: after separators
-- (/ . - _ ? & = : and the like; \hcbreak), and every CHUNK characters in a
-- run without one (\hcsplit, dearer). Both cost more than a space, so TeX
-- still prefers breaking between words. Inline code is cut into pieces, each
-- its own box, padded only on its outer edges so the pieces join without a
-- seam (\hccodepart, header.tex).
--
-- Headings are left alone: their text is also the PDF bookmark and the TOC
-- entry, where raw LaTeX does not belong, and a heading is rarely one word.
-- So is anything inside ~~strikeout~~: pandoc writes it as soul's \st, which
-- rebuilds its argument token by token and fails the whole PDF ("Reconstruction
-- failed", "Missing number") on these breaks and boxes. A long string struck
-- through can overflow; it cannot abort the document (Kamino item 101).

if not FORMAT:match("latex") then
  return {}
end

local MIN_LEN = 20
local CHUNK = 10
local SEPARATORS = "[/%.%-_%?&=:;,#\\%+%%@~|]"

-- Split text into pieces, each ending at a separator or after CHUNK characters
-- without one. Returns the pieces, and for each the break to put after it.
local function pieces(text)
  local out, breaks, cur, run = {}, {}, {}, 0
  for _, cp in utf8.codes(text) do
    local ch = utf8.char(cp)
    cur[#cur + 1] = ch
    run = run + 1
    local sep = ch:match(SEPARATORS) or ch == " "
    if sep or run >= CHUNK then
      out[#out + 1] = table.concat(cur)
      breaks[#out] = sep and "\\hcbreak{}" or "\\hcsplit{}"
      cur, run = {}, 0
    end
  end
  if #cur > 0 then out[#out + 1] = table.concat(cur) end
  return out, breaks
end

local function long(text)
  return (utf8.len(text) or #text) > MIN_LEN
end

local function split_str(el)
  if not long(el.text) then return nil end
  local parts, breaks = pieces(el.text)
  local out = {}
  for i, p in ipairs(parts) do
    if i > 1 then out[#out + 1] = pandoc.RawInline("latex", breaks[i - 1]) end
    out[#out + 1] = pandoc.Str(p)
  end
  return out
end

-- pandoc's own escaping for \texttt, so the pieces escape exactly as a whole
-- Code element would.
local function escaped_tt(text)
  local tex = pandoc.write(pandoc.Pandoc({ pandoc.Plain({ pandoc.Code(text) }) }), "latex")
  return (tex:gsub("%s+$", ""):match("^\\texttt{(.*)}$"))
end

local function split_code(el)
  if not long(el.text) then return nil end
  local parts, breaks = pieces(el.text)
  local out = {}
  for i, p in ipairs(parts) do
    local body = escaped_tt(p)
    if not body then return nil end -- pandoc wrote something unexpected: leave it whole
    local left = (i > 1) and "\\kern-\\fboxsep{}" or ""
    local right = (i < #parts) and "\\kern-\\fboxsep{}" or ""
    -- \kern-.25pt: pieces that abut exactly show a hairline in most viewers,
    -- so each overlaps the one before; after a line break the kern is dropped.
    if i > 1 then out[#out + 1] = pandoc.RawInline("latex", breaks[i - 1] .. "\\kern-.25pt{}") end
    out[#out + 1] = pandoc.RawInline("latex", "\\hccodepart{" .. left .. "}{" .. right .. "}{" .. body .. "}")
  end
  return out
end

-- Top-down, so a Strikeout is met before its contents and can stop the walk
-- there (returning false as the second value skips its children).
local inline_filter = {
  traverse = "topdown",
  Strikeout = function(el) return el, false end,
  Str = split_str,
  Code = split_code,
}

local function walk_inlines(el)
  return el:walk(inline_filter)
end

return {
  { Para = walk_inlines, Plain = walk_inlines },
}
