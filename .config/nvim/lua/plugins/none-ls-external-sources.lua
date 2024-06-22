-- TODO: This is a tentatively alternative to the situation where none-ls has removed the sources
-- Fix codes if a better solution is found
-- https://github.com/nvimtools/none-ls.nvim/issues/58
-- https://github.com/Zeioth/none-ls-external-sources.nvim
return {
    "zeioth/none-ls-autoload.nvim",
    event = "BufEnter",
    dependencies = {
        "williamboman/mason.nvim",
        "zeioth/none-ls-external-sources.nvim",
    },
    opts = {
        -- Here you can add support for sources not oficially suppored by none-ls.
        external_sources = {
            -- diagnostics
            "none-ls-external-sources.diagnostics.eslint",
            "none-ls-external-sources.diagnostics.eslint_d",
            "none-ls-external-sources.diagnostics.yamllint",

            -- formatting
            "none-ls-external-sources.formatting.eslint_d",
            "none-ls-external-sources.formatting.rustfmt",

            -- code actions
            "none-ls-external-sources.code_actions.eslint",
            "none-ls-external-sources.code_actions.eslint_d",
            "none-ls-external-sources.code_actions.shellcheck",
        },
    },
}
