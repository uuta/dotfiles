local lhs = hs
lhs.logger.setGlobalLogLevel("debug")

lhs.loadSpoon("ShiftIt")
spoon.ShiftIt:bindHotkeys({
  left = { { "ctrl", "cmd" }, "left" },
  right = { { "ctrl", "cmd" }, "right" },
  up = { { "ctrl", "cmd" }, "up" },
  down = { { "ctrl", "cmd" }, "down" },
  maximum = { { "ctrl", "cmd" }, "m" },
})

local keys = {
  { { "ctrl" }, "P",     "WezTerm" },
  { { "ctrl" }, "O",     "Brave Browser" },
  { { "ctrl" }, "M",     "DBeaver" },
  { { "ctrl" }, "Y",     "Spotify" },
  { { "ctrl" }, "N",     "Anki" },
  { { "ctrl" }, ";",     "Obsidian" },
  { { "ctrl" }, "space", "Ghostty" },
  { { "ctrl" }, ",",     "Cursor" },
  { { "ctrl" }, "9",     "Kindle" },
  { { "ctrl" }, "I",     "cmux" },
}

for _, key in ipairs(keys) do
  lhs.hotkey.bind(key[1], key[2], function()
    local app = lhs.application.find(key[3])
    if app then
      if app:isFrontmost() then
        app:hide()
      else
        app:activate()
      end
    else
      lhs.application.launchOrFocus(key[3])
    end
  end)
end

local function handleEvent(event)
  local rawFlags = event:rawFlags()
  -- Modify the numbers in conditions to be allocated to your keyboard with HammerSpoon
  -- print(rawFlags)
  if rawFlags == 1974574 then
    lhs.eventtap.keyStroke({ "cmd" }, "[")
    return true
  end
  if rawFlags == 1966389 then
    lhs.eventtap.keyStroke({ "cmd" }, "]")
    return true
  end
  return false
end

-- https://chat.openai.com/share/1aa92488-436c-434c-935b-65e61e458e25
_G.eventtap = lhs.eventtap.new({ lhs.eventtap.event.types.flagsChanged }, handleEvent)
_G.eventtap:start()

----------------------------------------
-- Browser Window Management
----------------------------------------
local browserConfigs = {
  { name = "Google Chrome" },
  { name = "Brave Browser" },
}

local supportedBrowserSet = {}
local browserHotkeys = {}
local browserFilters = {}

local function sendTabKey(direction)
  lhs.eventtap.keyStroke({ "cmd", "option" }, direction, 0)
end

for _, browser in ipairs(browserConfigs) do
  supportedBrowserSet[browser.name] = true

  local toRight = lhs.hotkey.new({ "ctrl" }, "l", function()
    sendTabKey("Right")
  end)

  local toLeft = lhs.hotkey.new({ "ctrl" }, "h", function()
    sendTabKey("Left")
  end)

  browserHotkeys[browser.name] = {
    toLeft = toLeft,
    toRight = toRight,
  }

  local filter = lhs.window.filter.new(browser.name)
  filter:subscribe(lhs.window.filter.windowFocused, function()
    toLeft:enable()
    toRight:enable()
  end):subscribe(lhs.window.filter.windowUnfocused, function()
    toLeft:disable()
    toRight:disable()
  end)

  browserFilters[browser.name] = filter
end

----------------------------------------
-- Directional Keybindings
----------------------------------------
local function getMacKeyRepeatSettings()
  local keyRepeat = tonumber((lhs.execute("defaults read NSGlobalDomain KeyRepeat"))) or 2
  local initialKeyRepeat = tonumber((lhs.execute("defaults read NSGlobalDomain InitialKeyRepeat"))) or 15
  -- Approximately 15ms units converted to seconds
  return {
    interval = keyRepeat * 0.015,
    delay = initialKeyRepeat * 0.015
  }
end

local keyRepeatSettings = getMacKeyRepeatSettings()
local repeatKey = nil
local repeatDelayTimer = nil

local function keyHoldHandler(key)
  -- First, trigger a single keystroke immediately
  lhs.eventtap.keyStroke({}, key, 0)

  -- Stop existing timers
  if repeatDelayTimer then
    repeatDelayTimer:stop()
    repeatDelayTimer = nil
  end
  if repeatKey then
    repeatKey:stop()
    repeatKey = nil
  end

  -- Start key repeat after macOS-configured delay
  repeatDelayTimer = lhs.timer.doAfter(keyRepeatSettings.delay, function()
    repeatKey = lhs.timer.new(keyRepeatSettings.interval, function()
      lhs.eventtap.keyStroke({}, key, 0)
    end)
    repeatKey:start()
  end)
end

local function stopKeyRepeat()
  if repeatDelayTimer then
    repeatDelayTimer:stop()
    repeatDelayTimer = nil
  end
  if repeatKey then
    repeatKey:stop()
    repeatKey = nil
  end
end

lhs.hotkey.bind({ "ctrl", "option" }, "l", function()
  keyHoldHandler("Right")
end, stopKeyRepeat)

lhs.hotkey.bind({ "ctrl", "option" }, "h", function()
  keyHoldHandler("Left")
end, stopKeyRepeat)

lhs.hotkey.bind({ "ctrl", "option" }, "j", function()
  keyHoldHandler("Down")
end, stopKeyRepeat)

lhs.hotkey.bind({ "ctrl", "option" }, "k", function()
  keyHoldHandler("Up")
end, stopKeyRepeat)

lhs.hotkey.bind({ "ctrl", "option" }, "'", function()
  lhs.application.launchOrFocus("QuickTime Player")
  lhs.timer.doAfter(1, function()
    local quicktime = lhs.appfinder.appFromName("QuickTime Player")
    if quicktime then
      -- Close the window in Finder
      lhs.eventtap.keyStroke({}, "Escape")
      -- Open a new window to record the current screen
      lhs.eventtap.keyStroke({ "ctrl", "cmd" }, "n")
    end
  end)
end)

----------------------------------------
-- External Display Window Management
----------------------------------------
lhs.hotkey.bind({ "ctrl", "option" }, "u", function()
  local logger = lhs.logger.new("windowManagement", "debug")
  local apps = {
    { name = "Google Chrome",      resize = true },
    { name = "Ghostty",            resize = true },
    { name = "WezTerm",            resize = true },
    { name = "DBeaver",            resize = true },
    { name = "Spotify",            resize = true },
    { name = "Figma",              resize = true },
    { name = "Hammerspoon",        resize = false },
    { name = "Anki",               resize = false },
    { name = "DevToys",            resize = false },
    { name = "DeepL",              resize = false },
    { name = "Finder",             resize = false },
    { name = "OrbStack",           resize = false },
    { name = "Slack",              resize = false },
    { name = "ovice",              resize = false },
    { name = "Obsidian",           resize = true },
    { name = "Visual Studio Code", resize = true },
    { name = "Brave",              resize = true },
  }
  local screens = lhs.screen.allScreens()
  if #screens < 2 then
    lhs.alert.show("External display not found!")
    return
  end
  for _, appInfo in ipairs(apps) do
    local app = lhs.application.find(appInfo.name)
    if app then
      local win = app:mainWindow()
      if win then
        -- Specify display (1: main display, 2: external display)
        local mainScreen = screens[1]
        local externalScreen = screens[2]

        local winFrame = win:frame()
        local winScreen = lhs.screen.find(winFrame)
        local frame = externalScreen:frame()

        logger.d(string.format("appName: %s", appInfo.name))
        logger.d(
          string.format(
            "Window position: x=%d, y=%d, w=%d, h=%d",
            winFrame.x,
            winFrame.y,
            winFrame.w,
            winFrame.h
          )
        )
        logger.d(string.format("external position: x=%d, y=%d, w=%d, h=%d", frame.x, frame.y, frame.w, frame.h))

        if appInfo.resize then
          -- Set the window frame to the external display
          win:setFrame(frame)
          -- if application has already been in external display
        elseif winScreen == mainScreen then
          -- Set the window frame to the external display without resizing
          local newFrame = hs.geometry.rect(frame.x / 2, winFrame.y, winFrame.w, winFrame.h)
          win:setFrame(newFrame)
        end
      end
    else
      logger.ef("%s not found!", appInfo.name)
    end
  end
end)

-- Logger for debugging
local log = lhs.logger.new("windowManager", "debug")

-- Define the hyper key combination
local hyper = { "ctrl", "option" }

local function cycleBrowserWindows()
  local frontApp = lhs.application.frontmostApplication()
  if not frontApp then
    lhs.alert.show("No active application to cycle")
    return
  end

  local appName = frontApp:name()
  if not supportedBrowserSet[appName] then
    lhs.alert.show("Cycle works only in Chrome or Brave")
    return
  end

  local allWindows = frontApp:allWindows()
  if not allWindows or #allWindows == 0 then
    lhs.alert.show(string.format("No %s windows to cycle through!", appName))
    return
  end

  local focusedWindow = frontApp:focusedWindow()
  local currentIndex = 0

  if focusedWindow then
    for index, window in ipairs(allWindows) do
      if window:id() == focusedWindow:id() then
        currentIndex = index
        break
      end
    end
  end

  local nextIndex = currentIndex + 1
  if nextIndex > #allWindows then
    nextIndex = 1
  end

  local nextWindow = allWindows[nextIndex]
  if nextWindow then
    nextWindow:focus()
    log.i(string.format("Cycling %s window #%d", appName, nextIndex))
  else
    log.e(string.format("Failed to focus %s window #%d", appName, nextIndex))
  end
end

-- Bind the hyper + m key to cycle windows in the active browser
lhs.hotkey.bind(hyper, "m", cycleBrowserWindows)
