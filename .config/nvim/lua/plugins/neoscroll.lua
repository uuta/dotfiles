-- Neoscroll: a smooth scrolling neovim plugin written in lua
-- https://github.com/karb94/neoscroll.nvim
return {
    "karb94/neoscroll.nvim",
    config = function()
        require("neoscroll").setup({easing_function = "quadratic"})
    end
}
