-- Comment out
-- https://github.com/terrortylor/nvim-comment
-- gcip comment/uncomment a paragraph
-- gc4w comment/uncomment current line
-- gc4j comment/uncomment 4 lines below the current line
-- dic delete comment block
-- gcic uncomment commented block
return {
    "terrortylor/nvim-comment",
    config = function()
        require("nvim_comment").setup({
            hook = function()
                require('ts_context_commentstring.internal').update_commentstring()
            end
        })
    end
}
