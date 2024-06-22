-- fidget (beautiful UI for LSP)
return {
    'j-hui/fidget.nvim',
    tag = "legacy",
    config = function()
        require('fidget').setup {
            -- config
        }
    end,
    event = 'LspAttach'
}
