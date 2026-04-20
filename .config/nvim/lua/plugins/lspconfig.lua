local lsp_servers = {
  "gopls",
  "html",
  "lua_ls",
  "astro",
  "rust_analyzer",
  -- "mypy",
  -- "efm",
  "ts_ls",
  "pyright",
  "ruff",
}

return {
  {
    "williamboman/mason.nvim",
    build = ":MasonUpdate",
    config = function()
      require("mason").setup()
    end,
  },
  {
    "williamboman/mason-lspconfig.nvim",
    dependencies = {
      "williamboman/mason.nvim",
      "neovim/nvim-lspconfig",
      "hrsh7th/cmp-nvim-lsp",
    },
    config = function()
      -- Mason-lspconfigの設定
      require("mason-lspconfig").setup({
        automatic_installation = true,
        ensure_installed = lsp_servers,
      })

      -- 補完の設定
      vim.cmd([[set completeopt+=menuone,noselect,popup]])

      -- LSPサーバーの有効化
      vim.lsp.enable(lsp_servers)
    end,
  },
}
