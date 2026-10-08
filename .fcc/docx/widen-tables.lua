-- widen-tables.lua
-- Two fixes for how pandoc lays out tables in LaTeX/PDF (also run for DOCX,
-- where docx_layout.py then scales the relative widths to the page's text width):
--
--  1. Simple pipe tables (no explicit width markers) arrive with all column
--     widths at 0. LaTeX then renders them at natural width, so a wide table
--     overflows the right margin. We distribute equal widths that sum to 1.0,
--     forcing the table to \linewidth and wrapping long cells instead.
--
--  2. When column 1 is an identifier column (most of its cells are inline
--     code), pandoc's source-character-count heuristic underestimates its
--     monospace width. We widen it to what its longest identifier needs,
--     capped at 0.50, and shrink the other columns in proportion, never
--     pushing one of them below MIN_OTHER.
--
--     Earlier versions widened column 1 to a flat 0.50 as soon as half of its
--     cells merely contained some code. A five-column table with one code
--     cell in two rows then got 0.50 / 0.125 x 4: the first column took half
--     the page while the others wrapped mid-word.

-- A cell is "code" when at least this share of its text is inline code.
local CODE_CELL_SHARE = 0.8
-- Column 1 is an identifier column when MORE than this share of its rows are
-- code cells (strictly more: one code row out of two is not enough).
local CODE_ROW_SHARE = 0.5
-- Monospace characters that fit across the text width at table font size.
-- Converts an identifier length into a width fraction; deliberately
-- conservative (a smaller number widens more).
local LINE_CHARS = 80
-- Never widen column 1 beyond this, nor squeeze any other column below MIN_OTHER.
local MAX_COL1 = 0.50
local MIN_OTHER = 0.10

local function cell_code_stats(cell)
  local code_chars, longest = 0, 0
  for _, block in ipairs(cell.contents) do
    -- Table cells wrap their content in Plain (tight) blocks, not Para.
    if block.t == "Para" or block.t == "Plain" then
      for _, inline in ipairs(block.content) do
        if inline.t == "Code" then
          local n = utf8.len(inline.text) or #inline.text
          code_chars = code_chars + n
          if n > longest then longest = n end
        end
      end
    end
  end
  local text = pandoc.utils.stringify(cell.contents)
  local total = utf8.len(text) or #text
  return code_chars, total, longest
end

function Table(tbl)
  local cols = tbl.colspecs
  local ncols = #cols
  if ncols < 1 then return nil end

  -- Fix 1: no width info at all → force an even fit-to-width layout.
  local width_sum = 0
  for _, spec in ipairs(cols) do
    width_sum = width_sum + (spec[2] or 0)
  end
  if width_sum == 0 then
    local even = 1.0 / ncols
    for i = 1, ncols do cols[i][2] = even end
    tbl.colspecs = cols
    width_sum = 1.0
    -- fall through: an identifier column can still be widened below
  end

  if ncols < 2 then tbl.colspecs = cols; return tbl end

  -- Fix 2: is column 1 an identifier column, and how wide must it be?
  local code_rows, total_rows, longest = 0, 0, 0
  for _, body in ipairs(tbl.bodies) do
    for _, row in ipairs(body.body) do
      local cell = row.cells[1]
      if cell then
        total_rows = total_rows + 1
        local code_chars, total, l = cell_code_stats(cell)
        if total > 0 and code_chars / total >= CODE_CELL_SHARE then
          code_rows = code_rows + 1
          if l > longest then longest = l end
        end
      end
    end
  end
  if total_rows == 0 or code_rows / total_rows <= CODE_ROW_SHARE then
    return tbl          -- not an identifier column: keep the widths as they are
  end

  -- The other columns shrink in proportion to their current widths (evenly if
  -- they were all zero), so share[i] is column i's slice of the remainder.
  local old_col1 = cols[1][2] or 0
  local old_rest = width_sum - old_col1
  local share = {}
  for i = 2, ncols do
    share[i] = old_rest > 0 and (cols[i][2] or 0) / old_rest or 1 / (ncols - 1)
  end

  -- Width the longest identifier needs (+2 chars of cell padding), capped at
  -- MAX_COL1 and so that no other column drops below MIN_OTHER (one that is
  -- already narrower than that is only kept from shrinking further).
  local min_other = MIN_OTHER * width_sum
  local cap = MAX_COL1 * width_sum
  for i = 2, ncols do
    if share[i] > 0 then
      local floor = math.min(min_other, cols[i][2] or 0)
      cap = math.min(cap, width_sum - floor / share[i])
    end
  end
  local new_col1 = math.min((longest + 2) / LINE_CHARS * width_sum, cap)
  if new_col1 <= old_col1 then
    return tbl          -- already wide enough (or no room): never shrink column 1
  end

  local new_rest = width_sum - new_col1
  cols[1][2] = new_col1
  for i = 2, ncols do
    cols[i][2] = new_rest * share[i]
  end
  tbl.colspecs = cols
  return tbl
end
