return {
    'nvim-treesitter/nvim-treesitter',
    -- Settings for comment out
    -- https://github.com/JoosepAlviste/nvim-ts-context-commentstring/wiki/Integrations#plugins-with-a-pre-comment-hook
    dependencies = {'JoosepAlviste/nvim-ts-context-commentstring'},
    config = function()
        require('nvim-treesitter.configs').setup {
            highlight = {
                enable = true -- syntax highlightを有効にする
            },
            ensure_installed = 'all', -- :TSInstall allと同じ
            ignore_install = {"phpdoc"},
            -- ensure_installed = 'maintained' とすることもできる
            context_commentstring = {enable = true, enable_autocmd = false}
        }
    end
}
