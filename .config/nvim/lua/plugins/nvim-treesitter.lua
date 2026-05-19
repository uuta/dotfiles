-- @see: https://blog.atusy.net/2025/08/10/nvim-treesitter-main-branch/
return {
  "nvim-treesitter/nvim-treesitter",
  branch = "main",
  lazy = false,
  build = ":TSUpdate | TSInstall markdown markdown_inline python lua bash json yaml go rust dart",
  dependencies = { "JoosepAlviste/nvim-ts-context-commentstring" },
  config = function()
    ---@diagnostic disable-next-line: missing-fields
    require("ts_context_commentstring").setup({
      enable_autocmd = false,
    })

    -- Enable treesitter highlighting for all filetypes
    vim.api.nvim_create_autocmd("FileType", {
      callback = function()
        pcall(vim.treesitter.start)
      end,
    })
  end,
}
