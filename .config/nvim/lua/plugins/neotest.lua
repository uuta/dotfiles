-- https://github.com/nvim-neotest/neotest
-- Plugin for executing tests
return {
    "nvim-neotest/neotest",
    dependencies = {
        "nvim-lua/plenary.nvim", "nvim-treesitter/nvim-treesitter",
        "antoinemadec/FixCursorHold.nvim", 'olimorris/neotest-phpunit',
        "nvim-neotest/nvim-nio"
    },
    config = function()
        require('neotest').setup({
            adapters = {
                require('neotest-phpunit')({
                    phpunit_cmd = function()
                        return "vendor/bin/phpunit"
                    end
                })
            }
        })
    end
}
