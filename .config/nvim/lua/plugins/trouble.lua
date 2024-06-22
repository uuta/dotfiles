--- Trouble (show error messages at the bottom of the screen)
--- https://github.com/folke/trouble.nvim
return {
    "folke/trouble.nvim",
    dependencies = "nvim-tree/nvim-web-devicons",
    config = function()
        require("trouble").setup {
            -- your configuration comes here
            auto_open = true,
            auto_close = true,
            auto_preview = true
        }
    end
}
