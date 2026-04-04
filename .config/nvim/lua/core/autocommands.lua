local api = vim.api

-- Copy related path
api.nvim_create_user_command("CpPath", function()
  local path = vim.fn.expand("%:p:.")
  vim.fn.setreg("+", path)
  vim.notify('Copied "' .. path .. '" to the clipboard!')
end, {})

-- Copy absolute path
api.nvim_create_user_command("CpAbPath", function()
  local path = vim.fn.expand("%:p")
  vim.fn.setreg("+", path)
  vim.notify('Copied "' .. path .. '" to the clipboard!')
end, {})

-- Copy file name
api.nvim_create_user_command("CpFileName", function()
  local path = vim.fn.expand("%:t:r")
  vim.fn.setreg("+", path)
  vim.notify('Copied "' .. path .. '" to the clipboard!')
end, {})

-- Clipboard substitution
api.nvim_create_user_command("SubClipboard", function()
  local text = vim.fn.input("Input replacing text:")
  local clipboard = vim.fn.getreg("*")
  vim.fn.execute(":%s/" .. clipboard .. "/" .. text .. "/g")
  vim.notify('Substituted with "' .. text .. '"!')
end, {})

-- Store the cursor point at last
api.nvim_create_autocmd({ "BufReadPost" }, {
  pattern = { "*" },
  callback = function()
    -- 非推奨の nvim_exec を nvim_exec2 に置き換え
    vim.api.nvim_exec2('silent! normal! g`"zv', {})
  end,
})

-- Obtain the current line
api.nvim_create_user_command("CpCurrentLine", function()
  local path = vim.fn.expand("%:p:.")
  local line = vim.api.nvim_win_get_cursor(0)[1]
  local copied = "at " .. line .. " in " .. path
  vim.fn.setreg("+", copied)
  vim.notify('Copied "' .. copied .. '" to the clipboard!')
end, {})

-- Obtain the selected lines
api.nvim_create_user_command("CpSelectedLines", function()
  local path = vim.fn.expand("%:p:.")
  local s, e = vim.fn.line("."), vim.fn.line("v")
  --vim.fn.line("."): the current line in visual mode
  --vim.fn.line("v"): the another end of the line in visual mode
  --swap if s is greater than e
  if s > e then s, e = e, s end
  local lines = s .. "-" .. e
  local copied = "at " .. lines .. " in " .. path
  vim.fn.setreg("+", copied)
  vim.notify('Copied "' .. copied .. '" to the clipboard!')
end, { range = true })

-- Obtain the selected lines
api.nvim_create_user_command("CpError", function()
  local diags = vim.diagnostic.get(0, { lnum = vim.fn.line(".") - 1 })
  if #diags == 0 then return vim.notify("No diagnostics") end
  local path = vim.fn.expand("%:p:.")
  local line = vim.api.nvim_win_get_cursor(0)[1]
  local copied = "Do you know why the following error occurs at " ..
      line .. " in " .. path .. "?\n\n" .. diags[1].message
  vim.fn.setreg("+", copied)
  vim.notify('Copied error messages to the clipboard!')
end, { range = true })

-- To stop beginning from insert mode
-- https://github.com/nvim-telescope/telescope.nvim/issues/2027#issuecomment-1561836585
api.nvim_create_autocmd("WinLeave", {
  callback = function()
    if vim.bo.ft == "TelescopePrompt" and vim.fn.mode() == "i" then
      vim.api.nvim_feedkeys(vim.api.nvim_replace_termcodes("<Esc>", true, false, true), "i", false)
    end
  end,
})

vim.cmd([[
hi NotifyBackground guibg = #000000
]])
