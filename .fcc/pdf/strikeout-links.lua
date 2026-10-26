-- strikeout-links.lua
-- LaTeX/PDF only: what soul's \st cannot take inside ~~strikeout~~.
--
-- pandoc writes ~~text~~ as soul's \st{...}, and soul cannot take an \href in
-- its argument: "Argument of \hyper@n@rmalise has an extra }", and the whole
-- PDF fails, not just that line. Kamino's own todo.md and review-2026-10-10.md
-- both strike through text that links to another report (Kamino item 82).
--
-- So inside a struck-through span the strike is pushed inside each link -
-- \href{...}{\st{...}} reads the same, and \href is never inside \st. The text
-- around a link keeps one \st per run, so the line is not broken word by word;
-- a link nested deeper (bold inside the strike, say) is reached through its
-- container.
--
-- A strike already inside the struck span (~~a [b ~~c~~ d](x) e~~, or
-- ~~a **b ~~c~~ d** e~~) is dissolved first: soul cannot nest \st either
-- ("Reconstruction failed"), and striking struck text again changes nothing on
-- the page (Kamino item 101).
--
-- Two more things soul cannot take apart letter by letter go into an \mbox,
-- which soul strikes through whole (Kamino item 205):
--   - inline math: soul splits \(x^2\) and fails "Extra }, or forgotten $";
--   - a run of characters fallback.tex sets in DejaVu (Greek, Cyrillic,
--     arrows, symbols - FALLBACK_LETTERS/FALLBACK_SYMBOLS in holo/fonts.py,
--     kept in step below): the font switch XeTeX inserts between characters
--     breaks soul's "Reconstruction failed".
-- The strike stays on them. Spans with none of this - no link, no strike
-- inside, no math, no such character - are left exactly as pandoc writes them.

if not FORMAT:match("latex") then
  return {}
end

-- holo/fonts.py FALLBACK_LETTERS + FALLBACK_SYMBOLS.
local FALLBACK = {
  { 0x0370, 0x03FF }, { 0x1F00, 0x1FFF }, { 0x0400, 0x052F },
  { 0x2196, 0x21FF }, { 0x2200, 0x22FF }, { 0x2300, 0x23FF }, { 0x2460, 0x24FF },
  { 0x2500, 0x257F }, { 0x2580, 0x259F }, { 0x25A0, 0x25FF }, { 0x2600, 0x26FF },
  { 0x2700, 0x27BF }, { 0x27F0, 0x27FF }, { 0x2900, 0x297F }, { 0x2980, 0x29FF },
  { 0x2A00, 0x2AFF }, { 0x2B00, 0x2BFF },
}

local function is_fallback(cp)
  for _, r in ipairs(FALLBACK) do
    if cp >= r[1] and cp <= r[2] then
      return true
    end
  end
  return false
end

local function has_fallback(text)
  for _, cp in utf8.codes(text) do
    if is_fallback(cp) then
      return true
    end
  end
  return false
end

local function mbox(inlines)
  local out = pandoc.Inlines({ pandoc.RawInline("latex", "\\mbox{") })
  out:extend(inlines)
  out:insert(pandoc.RawInline("latex", "}"))
  return out
end

-- A Str as inlines, each run of fallback characters in its own \mbox.
local function box_fallback(str)
  local out, run, boxed = pandoc.Inlines({}), {}, nil
  local function flush()
    if #run > 0 then
      local s = pandoc.Str(table.concat(run))
      if boxed then out:extend(mbox({ s })) else out:insert(s) end
      run = {}
    end
  end
  for _, cp in utf8.codes(str.text) do
    local fb = is_fallback(cp)
    if fb ~= boxed then
      flush()
      boxed = fb
    end
    run[#run + 1] = utf8.char(cp)
  end
  flush()
  return out
end

local function has_link(inlines)
  local found = false
  pandoc.Inlines(inlines):walk({ Link = function() found = true end })
  return found
end

-- Anything in the inlines soul's \st cannot take (but a link, handled apart)?
local function has_fragile(inlines)
  local found = false
  pandoc.Inlines(inlines):walk({
    Strikeout = function() found = true end,
    Math = function(m) if m.mathtype == "InlineMath" then found = true end end,
    Str = function(s) if has_fallback(s.text) then found = true end end,
  })
  return found
end

-- The inlines made safe for \st: every Strikeout inside them dissolved into
-- its contents, inline math and fallback-font runs each in an \mbox. A
-- footnote's text is left alone (soul hands \footnote's argument on whole).
local function soul_safe(inlines)
  local out = pandoc.Inlines({})
  for _, el in ipairs(inlines) do
    if el.t == "Strikeout" then
      out:extend(soul_safe(el.content))
    elseif el.t == "Math" and el.mathtype == "InlineMath" then
      out:extend(mbox({ el }))
    elseif el.t == "Str" and has_fallback(el.text) then
      out:extend(box_fallback(el))
    else
      if el.t ~= "Note" and type(el.content) == "table" then
        el.content = soul_safe(el.content)
      end
      out:insert(el)
    end
  end
  return out
end

-- The inlines struck through, with every link holding its own strike.
local function strike(inlines)
  local out, run = pandoc.Inlines({}), pandoc.Inlines({})
  local function flush()
    if #run > 0 then
      out:insert(pandoc.Strikeout(run))
      run = pandoc.Inlines({})
    end
  end
  for _, el in ipairs(inlines) do
    if el.t == "Link" then
      flush()
      el.content = pandoc.Inlines({ pandoc.Strikeout(soul_safe(el.content)) })
      out:insert(el)
    elseif el.t ~= "Note" and type(el.content) == "table" and has_link(el.content) then
      flush()
      el.content = strike(el.content)
      out:insert(el)
    else
      run:extend(soul_safe({ el }))
    end
  end
  flush()
  return out
end

-- Top-down, and nothing below a strike is visited again: a strike inside one
-- is the outer one's to dissolve, and nothing is boxed twice.
return {
  {
    traverse = "topdown",
    Strikeout = function(el)
      if not (has_link(el.content) or has_fragile(el.content)) then
        return nil
      end
      return strike(el.content), false
    end,
  },
}
