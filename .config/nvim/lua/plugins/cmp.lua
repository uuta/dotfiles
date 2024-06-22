-- https://github.com/hrsh7th/nvim-cmp
-- It didn't work when adding cmp to config in this file so separated it into core/cmp.lua
return {
    {'hrsh7th/nvim-cmp', event = {'InsertEnter', 'CmdlineEnter'}},
    {'hrsh7th/cmp-nvim-lsp', event = 'InsertEnter'},
    {'hrsh7th/cmp-buffer', event = 'InsertEnter'},
    {'hrsh7th/cmp-path', event = 'InsertEnter'},
    {'hrsh7th/cmp-vsnip', event = 'InsertEnter'},
    {'hrsh7th/cmp-cmdline', event = 'ModeChanged'}, -- これだけは'ModeChanged'でなければまともに動かなかった。
    {'hrsh7th/cmp-nvim-lsp-signature-help', event = 'InsertEnter'},
    {'hrsh7th/cmp-nvim-lsp-document-symbol', event = 'InsertEnter'},
    {'hrsh7th/cmp-calc', event = 'InsertEnter'},
    {'onsails/lspkind.nvim', event = 'InsertEnter'},
    {'hrsh7th/vim-vsnip', event = 'InsertEnter'},
    {'hrsh7th/vim-vsnip-integ', event = 'InsertEnter'},
    {'rafamadriz/friendly-snippets', event = 'InsertEnter'},
    {'onsails/lspkind.nvim'}
}
