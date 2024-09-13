local vim = vim
local g = vim.g
local keymap = vim.keymap.set

g.mapleader = ";"

-- Set keymap
keymap("n", "<Leader>d", "<cmd>:HopWord<cr>")
keymap("n", "<Leader>q", "<cmd>:q<cr>")
keymap("n", "<Leader>Q", "<cmd>:q!<cr>")
keymap("n", "<Leader>w", "<cmd>:w<cr>")
keymap("n", "<Leader>wq", "<cmd>:wq<cr>")
keymap("n", "<Leader>i", "<cmd>tabnew<cr>")
keymap("n", "<Leader>cc", "<cmd>CpPath<cr>")
keymap("n", "<Leader>cf", "<cmd>CpFileName<cr>")
-- keymap('n', '<Leader>aa', '<Plug>(YankyNextEntry)')

-- buffers
keymap("n", "<Leader>ls", "<cmd>ls<cr>")
keymap("n", "<Leader>bd", "<cmd>Bdelete<cr>")

-- buffer line
keymap("n", "<C-l>", "<cmd>BufferLineCycleNext<cr>")
keymap("n", "<C-h>", "<cmd>BufferLineCyclePrev<cr>")
keymap("n", "<C-p>", "<cmd>BufferLineTogglePin<cr>")
keymap("n", "<C-i>", "<cmd>BufferLinePick<cr>")
keymap("n", "<C-k>", "<cmd>BufferLineMoveNext<cr>")
keymap("n", "<C-j>", "<cmd>BufferLineMovePrev<cr>")
keymap("n", "<Leader>1", "<cmd>BufferLineGoToBuffer 1<cr>")
keymap("n", "<Leader>2", "<cmd>BufferLineGoToBuffer 2<cr>")
keymap("n", "<Leader>3", "<cmd>BufferLineGoToBuffer 3<cr>")
keymap("n", "<Leader>4", "<cmd>BufferLineGoToBuffer 4<cr>")
keymap("n", "<Leader>5", "<cmd>BufferLineGoToBuffer 5<cr>")
keymap("n", "<Leader>6", "<cmd>BufferLineGoToBuffer 6<cr>")
keymap("n", "<Leader>7", "<cmd>BufferLineGoToBuffer 7<cr>")
keymap("n", "<Leader>8", "<cmd>BufferLineGoToBuffer 8<cr>")
keymap("n", "<Leader>9", "<cmd>BufferLineGoToBuffer -1<cr>")
keymap("n", "<Leader>ba", "<cmd>BufferLineCloseOthers<cr>")

--- Split screen
keymap("n", "<Leader>t", "<C-w>v<cr>")
keymap("n", "<Leader>ml", "<C-w>l<cr>")
keymap("n", "<Leader>mh", "<C-w>h<cr>")
keymap("n", "<Leader>mk", "<C-w>k<cr>")
keymap("n", "<Leader>mm", "<C-w>j<cr>")

--- LSP
keymap("n", "<Leader>s", "<cmd>lua vim.lsp.buf.format()<CR>")
keymap("n", "<Leader>kk", "<cmd>Lspsaga hover_doc<CR>")
keymap("n", "<Leader>kf", "<cmd>Lspsaga goto_definition<CR>")
keymap("n", "<Leader>kt", "<cmd>Lspsaga goto_type_definition<CR>")
keymap("n", "<Leader>ka", "<cmd>Lspsaga code_action<CR>")
keymap("n", "<Leader>kj", "<cmd>Lspsaga finder<CR>")
-- Change to mode=n
keymap("n", "<Leader>kr", "<cmd>Lspsaga rename<CR>")
keymap("n", "<Leader>kp", "<cmd>Lspsaga project_replace old_name new_name<CR>")

-- Move to a directory
keymap("n", "<Leader>cdt", "<cmd>cd ~/trander<CR>")
keymap("n", "<Leader>cds", "<cmd>cd ~/socialdog/web<CR>")
keymap("n", "<Leader>cdg", "<cmd>cd ~/socialdog/web/application_go<CR>")

--- Diagnostics
keymap("n", "<Leader>e", "<cmd>:Lspsaga show_line_diagnostics<CR>")
keymap("n", "<Leader>el", "<cmd>:Lspsaga diagnostic_jump_next<CR>")
keymap("n", "<Leader>eh", "<cmd>:Lspsaga diagnostic_jump_prev<CR>")

--- Telescope
keymap("n", "<Leader>p", "<cmd>Telescope find_files hidden=true theme=get_ivy<CR>")
-- keymap('n', '<Leader>;p', '<cmd>Telescope find_files theme=get_ivy<CR>')
keymap(
    "n",
    "<Leader>ff",
    '<cmd>lua require("telescope").extensions.live_grep_args.' .. 'live_grep_args({ theme="ivy" })<CR>'
)
keymap("n", "<Leader>bf", "<cmd>Telescope buffers hidden=true theme=get_ivy<CR>")
keymap("n", "<Leader>H", "<cmd>Telescope oldfiles hidden=true theme=get_ivy<CR>")
keymap("n", "<Leader>hh", "<cmd>Telescope search_history hidden=true theme=get_ivy<CR>")
keymap("n", "<Leader>hs", "<cmd>Telescope spell_suggest hidden=true theme=get_ivy<CR>")
keymap("n", "<Leader>ha", "<cmd>Telescope resume hidden=true theme=get_ivy<CR>")
keymap("n", "<Leader>hd", "<cmd>Telescope pickers hidden=true theme=get_ivy<CR>")
keymap("n", "<Leader>gb", "<cmd>Telescope git_branches theme=get_ivy<CR>")
keymap("n", "<Leader>gs", "<cmd>Telescope git_status theme=get_ivy<CR>")
keymap("n", "<Leader>fk", "<cmd>Telescope lsp_document_symbols theme=get_ivy<CR>")
keymap("n", "<Leader>fc", "<cmd>Telescope current_buffer_fuzzy_find<CR>")

-- text-case.nvim
keymap("n", "gau", "<cmd>:lua require('textcase').current_word('to_upper_case')<CR>")
keymap("n", "gal", "<cmd>:lua require('textcase').current_word('to_lower_case')<CR>")
keymap("n", "gas", "<cmd>:lua require('textcase').current_word('to_snake_case')<CR>")
keymap("n", "gac", "<cmd>:lua require('textcase').current_word('to_camel_case')<CR>")
keymap("n", "gap", "<cmd>:lua require('textcase').current_word('to_pascal_case')<CR>")
keymap("n", "gah", "<cmd>:lua require('textcase').current_word('to_phrase_case')<CR>")

--- Go
keymap("n", "<Leader>;c", "<cmd>GoCmt<CR>")
keymap("n", "<Leader>;aj", "<cmd>GoAddTag json<CR>")
keymap("n", "<Leader>;ad", "<cmd>GoAddTag db<CR>")
keymap("n", "<Leader>;ax", "<cmd>GoAddTag xml<CR>")
keymap("n", "<Leader>;rj", "<cmd>GoRmTag json<CR>")
keymap("n", "<Leader>;rd", "<cmd>GoRmTag db<CR>")
keymap("n", "<Leader>;rx", "<cmd>GoRmTag xml<CR>")
-- https://github.com/ray-x/go.nvim#unit-test-with-gotests-and-testify
keymap("n", "<Leader>;t", "<cmd>GoTestFunc<CR>")
keymap("n", "<Leader>;s", "<cmd>GoTestFunc -s<CR>")
keymap("n", "<Leader>;e", "<cmd>GoIfErr<CR>")
keymap("n", "<Leader>;i", "<cmd>GoImports<CR>")
keymap("n", "<Leader>;at", "<cmd>GoAddTest<CR>")

--- Mason
keymap("n", "<Leader>M", "<cmd>:Mason<cr>")

--- treesitter
keymap("n", "<Leader>vu", "<cmd>:TSUpdate all<cr>")

--- File explorer
keymap("n", "<Leader>F", "<cmd>:NvimTreeFindFile<cr>")

--- Trouble
keymap("n", "<Leader>n", "<cmd>:TroubleToggle<cr>")

--- Twilight
keymap("n", "<Leader>z", "<cmd>:ZenMode<cr>")

--- Substitution
keymap("n", "<leader>jj", "<cmd>lua require('substitute').line()<cr>", { noremap = true })
keymap("n", "<leader>je", "<cmd>lua require('substitute').eol()<cr>", { noremap = true })
keymap("n", "<leader>jf", "<cmd>lua require('substitute.range').operator()<cr>", { noremap = true })
keymap("n", "<Leader>jk", "<cmd>SubClipboard<cr>")

--- Execute a nearest test
keymap("n", "<leader>;j", "<cmd>lua require('neotest').run.run()<cr>")

--- GitConflict
keymap("n", "co", "<cmd>GitConflictChooseOurs<CR>")
keymap("n", "ct", "<cmd>GitConflictChooseTheirs<CR>")
keymap("n", "cb", "<cmd>GitConflictChooseBoth<CR>")
keymap("n", "c0", "<cmd>GitConflictChooseNone<CR>")
keymap("n", "cl", "<cmd>GitConflictNextConflict<CR>")
keymap("n", "ch", "<cmd>GitConflictPrevConflict<CR>")
keymap("n", "cm", "<cmd>GitConflictListQf<CR>")

--- Git
keymap("n", "gf", "<cmd>GitBlameOpenFileURL<CR>")
keymap("n", "gc", "<cmd>GitBlameOpenCommitURL<CR>")
keymap("n", "gh", "<cmd>Gitsigns prev_hunk<CR>")
keymap("n", "gl", "<cmd>Gitsigns next_hunk<CR>")
keymap("n", "gd", "<cmd>Gitsigns diffthis<CR>")
keymap("n", "gv", "<cmd>DiffviewFileHistory %<CR>")

-- Gyazo
keymap("n", "<Leader>b", "<cmd>GyazoUpload<CR>")
