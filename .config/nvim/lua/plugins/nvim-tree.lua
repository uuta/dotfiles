-- File explorer
-- https://github.com/nvim-tree/nvim-tree.lua
return {
    "nvim-tree/nvim-tree.lua",
    dependencies = { "nvim-tree/nvim-web-devicons" },
    config = function()
        require("nvim-tree").setup({
            sort_by = "case_sensitive",
            renderer = { group_empty = true },
            filters = { dotfiles = true },
            view = { adaptive_size = false, width = { min = 50 } },
        })
    end,
}
