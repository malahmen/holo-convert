-- strikeout-links.lua
-- LaTeX/PDF only: a link inside ~~strikeout~~.
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
-- container. Spans with no link are left exactly as pandoc writes them.
--
-- A strike already inside the struck span (~~a [b ~~c~~ d](x) e~~) is
-- dissolved first: soul cannot nest \st either ("Reconstruction failed"), and
-- striking struck text again changes nothing on the page (Kamino item 101).

if not FORMAT:match("latex") then
  return {}
end

local function has_link(inlines)
  local found = false
  pandoc.Inlines(inlines):walk({ Link = function() found = true end })
  return found
end

-- The inlines with every Strikeout inside them dissolved into its contents.
local function unstrike(inlines)
  return pandoc.Inlines(inlines):walk({ Strikeout = function(s) return s.content end })
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
      el.content = pandoc.Inlines({ pandoc.Strikeout(unstrike(el.content)) })
      out:insert(el)
    elseif el.t ~= "Note" and type(el.content) == "table" and has_link(el.content) then
      flush()
      el.content = strike(el.content)
      out:insert(el)
    elseif el.t == "Strikeout" then
      run:extend(unstrike(el.content))
    else
      run:insert(el)
    end
  end
  flush()
  return out
end

function Strikeout(el)
  if not has_link(el.content) then
    return nil
  end
  return strike(el.content)
end
