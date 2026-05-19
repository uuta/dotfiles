return {
  "nvim-flutter/flutter-tools.nvim",
  dependencies = {
    "nvim-lua/plenary.nvim",
    "stevearc/dressing.nvim",
    "hrsh7th/cmp-nvim-lsp",
  },
  lazy = false,
  config = function()
    local capabilities = vim.lsp.protocol.make_client_capabilities()
    local ok, cmp_nvim_lsp = pcall(require, "cmp_nvim_lsp")
    if ok then
      capabilities = cmp_nvim_lsp.default_capabilities(capabilities)
    end

    require("flutter-tools").setup({
      flutter_lookup_cmd = "mise where flutter",
      widget_guides = {
        enabled = true,
      },
      closing_tags = {
        enabled = true,
      },
      lsp = {
        capabilities = capabilities,
        settings = {
          showTodos = true,
          completeFunctionCalls = true,
          renameFilesWithClasses = "prompt",
          updateImportsOnRename = true,
        },
      },
    })
  end,
}
