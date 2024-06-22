-- 条件が真の時のみ読み込みます。条件は起動時に毎回判定されます。
return {
    'thinca/vim-fontzoom',
    cond = [[vim.fn.has'gui' == 1]] -- GUI の時のみ読み込む。
    -- 関数も指定できます。
    -- conf = function() return vim.fn.has'gui' == 1 end,
}
