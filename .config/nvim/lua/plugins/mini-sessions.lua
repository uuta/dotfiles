return {
  "nvim-mini/mini.nvim",
  lazy = false,
  config = function()
    local sessions_dir = vim.fn.stdpath("data") .. "/sessions"
    vim.fn.mkdir(sessions_dir, "p")
    require("mini.sessions").setup({
      autoread = false,
      autowrite = true,
      directory = sessions_dir,
      file = "Session.vim",
    })
  end,
}
