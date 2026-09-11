-- render-mermaid.lua
-- Detects fenced mermaid code blocks, renders them to PNG via mmdc,
-- and replaces the code block with an image node pandoc can pass to XeLaTeX.
--
-- Requires: mmdc (Mermaid CLI) — https://github.com/mermaid-js/mermaid-cli
--   holo-convert.sh --with-optional      (installs it via npm), or
--   npm install -g @mermaid-js/mermaid-cli
--
-- mmdc is called with an absolute path to avoid $PATH issues in subprocess.
-- Rendered PNGs go to a per-run directory under the system temp location
-- (os.tmpname). The filter cannot remove it itself: pandoc's writer reads the
-- images only after all filters have finished, so the directory is left for
-- the OS's temp cleanup.
--
-- Usage:
--   pandoc input.md --lua-filter=render-mermaid.lua -o output.pdf

-- Resolve mmdc path at filter load time.
-- Checks mise shims first (consistent across macOS and Linux when installed
-- via mise), then falls back to whatever is on PATH.
local function find_mmdc()
    -- mise shim path is consistent regardless of OS or Node install method.
    -- HOME can be unset (cron, containers) — skip the shim check then.
    local home = os.getenv("HOME")
    if home and home ~= "" then
        local mise_shim = home .. "/.local/share/mise/shims/mmdc"
        local f = io.open(mise_shim, "r")
        if f then
            f:close()
            return mise_shim
        end
    end
    -- Fall back to PATH resolution
    local handle = io.popen("command -v mmdc 2>/dev/null")
    if not handle then return nil end
    local path = handle:read("*a"):gsub("%s+$", "")
    handle:close()
    return path ~= "" and path or nil
end

local MMDC = find_mmdc()
local IMG_DIR = nil   -- initialised once on first use

-- ---------------------------------------------------------------------------
-- Initialise temp directory for rendered images (once per run).
-- ---------------------------------------------------------------------------

local function ensure_img_dir()
    if IMG_DIR then return IMG_DIR end

    -- os.tmpname gives a unique filename — use its stem as a directory name
    local tmp = os.tmpname()
    os.remove(tmp)
    IMG_DIR = tmp .. "_mermaid"
    os.execute("mkdir -p " .. IMG_DIR)
    return IMG_DIR
end

-- ---------------------------------------------------------------------------
-- Render a mermaid diagram string to a PNG file.
-- Returns the output PNG path on success, nil + error message on failure.
-- ---------------------------------------------------------------------------

local function render_mermaid(diagram_src, index)
    if not MMDC then
        return nil, "mmdc not found — run 'holo-convert.sh --with-optional' (installs mermaid-cli via npm), or: npm install -g @mermaid-js/mermaid-cli"
    end

    local dir = ensure_img_dir()
    local src_file = dir .. "/diagram_" .. index .. ".mmd"
    local out_file = dir .. "/diagram_" .. index .. ".png"

    -- Write diagram source to temp file
    local f = io.open(src_file, "w")
    if not f then
        return nil, "Could not write temp file: " .. src_file
    end
    f:write(diagram_src)
    f:close()

    -- Call mmdc
    local cmd = MMDC
        .. " -i " .. src_file
        .. " -o " .. out_file
        .. " -b transparent"
        .. " --scale 2"
        .. " 2>&1"

    local handle = io.popen(cmd)
    if not handle then
        return nil, "could not run mmdc for diagram " .. index
    end
    local output = handle:read("*a") or ""
    local ok = handle:close()

    -- Probe for the output file and close the handle (it used to leak).
    local probe = io.open(out_file, "r")
    if probe then probe:close() end
    if not ok or not probe then
        return nil, "mmdc failed for diagram " .. index .. ": " .. output
    end

    return out_file, nil
end

-- ---------------------------------------------------------------------------
-- Filter: replace mermaid CodeBlock nodes with Image nodes.
-- ---------------------------------------------------------------------------

local diagram_count = 0

function CodeBlock(block)
    -- Only process blocks explicitly tagged as mermaid
    local is_mermaid = false
    for _, cls in ipairs(block.classes) do
        if cls == "mermaid" then
            is_mermaid = true
            break
        end
    end

    if not is_mermaid then return nil end

    diagram_count = diagram_count + 1

    local img_path, err = render_mermaid(block.text, diagram_count)

    if not img_path then
        -- Rendering failed — warn and leave the block as-is so the document
        -- still compiles, just with the source shown instead of the diagram.
        io.stderr:write("[render-mermaid] WARNING: " .. err .. "\n")
        return nil
    end

    -- Build a pandoc Image node wrapped in a Para so it renders as a block.
    -- Caption is empty; alt text identifies the diagram for accessibility.
    local img = pandoc.Image(
        { pandoc.Str("Mermaid diagram " .. diagram_count) },
        img_path,
        ""
    )

    return pandoc.Para({ img })
end
