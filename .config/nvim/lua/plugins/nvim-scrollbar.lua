return {
    "petertriho/nvim-scrollbar",
    -- dependencies = "kevinhwang91/nvim-hlslens",
    config = function()
        require("scrollbar").setup({ handle = { color = "#2fe0c5" } })
    end,
}
