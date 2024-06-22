-- text-case.nvim
-- There are methods that convert a specific text to the specified case
-- Example: Upper case, Lower case, Snake case and Camel case
-- @see https://github.com/johmsalas/text-case.nvim
return {
    "johmsalas/text-case.nvim",
    config = function() require('textcase').setup {} end
}
