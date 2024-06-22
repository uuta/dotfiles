-- See the following for more information
-- @see https://github.com/akinsho/bufferline.nvim/blob/main/doc/bufferline.txt
return {
    "akinsho/bufferline.nvim",
    dependencies = "nvim-tree/nvim-web-devicons",
    config = function()
        require("bufferline").setup({
            options = {
                separator_style = "thick",
                diagnostics = "nvim_lsp",
                hover = { enabled = true, delay = 200, reveal = { "close" } },
            },
            groups = {
                {
                    options = {
                        toggle_hidden_on_enter = true, -- when you re-enter a hidden group this options re-opens
                    },
                    items = {
                        {
                            name = "Tests", -- Mandatory
                            highlight = { underline = true, sp = "blue" }, -- Optional
                            priority = 2, -- determines where it will appear relative to other groups (Optional)
                            icon = "", -- Optional
                            matcher = function(buf) -- Mandatory
                                return buf.filename:match("%_test%") or buf.filename:match("%_spec%")
                            end,
                        },
                        {
                            name = "Docs",
                            highlight = { undercurl = true, sp = "green" },
                            auto_close = false, -- close this group if it doesn't contain the current buffer
                            matcher = function(buf)
                                return buf.filename:match("%.md") or buf.filename:match("%.txt")
                            end,
                            separator = { -- Optional
                                style = require("bufferline.groups").separator.tab,
                            },
                        },
                    },
                },
            },
        })
    end,
}
