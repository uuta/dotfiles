local M = {}

local COMPOSE_FILE = "app/docker/local.docker-compose.yaml"
local SERVICE = "banking-app"
local HOST_SRC_PREFIX = "./app/src/"

function M.test_func(opts)
  opts = opts or {}

  local ns = require("go.gotest").get_test_func_name()
  if not ns or not ns.name then
    vim.notify("No test function found at cursor", vim.log.levels.WARN)
    return
  end

  local fpath = require("go.gotest").get_test_path()
  local container_path = fpath
  if vim.startswith(fpath, HOST_SRC_PREFIX) then
    container_path = "./" .. fpath:sub(#HOST_SRC_PREFIX + 1)
  end

  local parts = { "go", "test" }
  if opts.tags then
    table.insert(parts, "-tags=" .. opts.tags)
  end
  table.insert(parts, container_path)
  table.insert(parts, string.format("-run='^%s$'", ns.name))
  local test_cmd = table.concat(parts, " ")

  local cmd = string.format(
    "docker-compose -f %s exec -T %s sh -c '%s'",
    COMPOSE_FILE, SERVICE, test_cmd
  )

  vim.notify("Running: " .. ns.name, vim.log.levels.INFO)
  local output = {}
  vim.fn.jobstart(cmd, {
    cwd = vim.fn.getcwd(),
    stdout_buffered = true,
    stderr_buffered = true,
    on_stdout = function(_, data)
      if data then vim.list_extend(output, data) end
    end,
    on_stderr = function(_, data)
      if data then vim.list_extend(output, data) end
    end,
    on_exit = function(_, code)
      vim.schedule(function()
        local lines = vim.tbl_filter(function(l) return l ~= "" end, output)
        local detail = table.concat(lines, "\n")
        if code == 0 then
          vim.notify("PASS: " .. ns.name, vim.log.levels.INFO)
        else
          vim.notify("FAIL: " .. ns.name .. "\n" .. detail, vim.log.levels.ERROR)
        end
      end)
    end,
  })
end

return M
