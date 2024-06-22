return {
    -- Sorter extension for telescope: one of sorter extensions that telescope.nvim recommends using
    -- https://github.com/nvim-telescope/telescope.nvim/wiki/Extensions#sorter
    {
        'nvim-telescope/telescope-fzf-native.nvim',
        build = 'cmake -S. -Bbuild -DCMAKE_BUILD_TYPE=Release && cmake --build build --config Release && cmake --install build --prefix build'
    }, {
        'nvim-telescope/telescope.nvim',
        tag = '0.1.8',
        defaults = {
            vimgrep_arguments = {
                'rg', '--color=never', '--no-heading', '--with-filename',
                '--line-number', '--column', '--smart-case', '--ignore'
            }
        },
        -- Telescope live grep args
        -- Search strings with filters such as a directory
        -- @see https://github.com/nvim-telescope/telescope-live-grep-args.nvim
        dependencies = {{"nvim-telescope/telescope-live-grep-args.nvim"}},
        config = function()
            local lga_actions = require("telescope-live-grep-args.actions")
            require("telescope").setup({
                extensions = {
                    live_grep_args = {
                        auto_quoting = true, -- enable/disable auto-quoting
                        -- define mappings, e.g.
                        mappings = {
                            i = {
                                ["<C-k>"] = lga_actions.quote_prompt(),
                                ["<C-i>"] = lga_actions.quote_prompt({
                                    postfix = " --iglob "
                                }),
                                ["<C-g>"] = lga_actions.quote_prompt({
                                    postfix = " --iglob *go"
                                }),
                                ["<C-r>"] = lga_actions.quote_prompt({
                                    postfix = " --iglob *tsx"
                                }),
                                ["<C-t>"] = lga_actions.quote_prompt({
                                    postfix = " --iglob *ts"
                                }),
                                ["<C-p>"] = lga_actions.quote_prompt({
                                    postfix = " --iglob *php"
                                })
                            }
                        }
                    }
                },
                fzf = {
                    fuzzy = true, -- false will only do exact matching
                    override_generic_sorter = true, -- override the generic sorter
                    override_file_sorter = true, -- override the file sorter
                    case_mode = "smart_case" -- or "ignore_case" or "respect_case"
                    -- the default case_mode is "smart_case"
                }
            })
        end,
        cmd = "Telescope"
    }
}
