local o = vim.o
local opt = vim.opt
local g = vim.g
local wo = vim.wo

o.number = true
o.clipboard = "unnamedplus"
o.termguicolors = true
o.hidden = true
o.tabstop = 4
o.softtabstop = 4
o.shiftwidth = 4
o.laststatus = 3
-- o.completeopt = "menu,menuone,noselect"
o.list = true
opt.listchars:append "space:⋅"
opt.listchars:append "eol:↴"
o.termguicolors = true
wo.relativenumber = true
opt.cursorline = true

-- NeoVide configuration
g.neovide_transparency = 0.8
g.neovide_cursor_vfx_mode = "ripple"

vim.cmd [[
  highlight CursorLineNr term=bold cterm=bold gui=bold
]]
