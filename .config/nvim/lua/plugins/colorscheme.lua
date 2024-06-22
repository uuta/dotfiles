return {
    {
        "Tsuzat/NeoSolarized.nvim",
        config = function()
            -- https://github.com/Tsuzat/NeoSolarized.nvim/blob/208e65a3ede945b8a1d00104a4441217c5e23509/lua/NeoSolarized/theme.lua#L1-L11
            local neosolarized = require('NeoSolarized')
            local cls = require("NeoSolarized.colors")
            local config = require("NeoSolarized.config")
            local options = config.options
            local theme = {config = options, colors = cls.setup()}

            local c = theme.colors
            c.green = '#40f7d2'
            c.yellow = '#eaea8a'
            c.red = '#ea4481'
            c.blue = '#2bb3d8'
            c.fg0 = '#dde8d5'
            c.orange = '#dd9f4d'
            neosolarized.setup {
                transparent = true,
                -- https://github.com/Tsuzat/NeoSolarized.nvim/blob/208e65a3ede945b8a1d00104a4441217c5e23509/lua/NeoSolarized/theme.lua#L748
                styles = {
                    comments = {italic = false},
                    keywords = {italic = false, bold = true},
                    string = {italic = false}
                },
                on_highlights = function(highlights, colors)
                    -- highlights.Include.fg = colors.red -- Using `red` foreground for Includes
                end
            }
        end
    }
}
