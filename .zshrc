################################
### znap: Zsh plugin manager
################################

# Download Znap, if it's not there yet.
[[ -r ~/.znap/znap.zsh ]] ||
    git clone --depth 1 -- \
        https://github.com/marlonrichert/zsh-snap.git ~/.znap
# Make sure the repos directory exists
# -p: creates the parent directory if it doesn't exist(/aaa/bbb/ccc -> aaa, bbb, ccc ex)
mkdir -p ~/.znap/repos
source ~/.znap/znap.zsh

zstyle ':znap:*' repos-dir ~/.znap/repos
zstyle ':completion:*' list-colors 'di=34' 'ln=35' 'so=32' 'ex=31' 'bd=46;34' 'cd=43;34'

# Load plugins (To install and update plugins, run `znap pull` command)
znap source marlonrichert/zsh-autocomplete
znap source zsh-users/zsh-syntax-highlighting
znap source zsh-users/zsh-autosuggestions
znap source rupa/z
znap source mafredri/zsh-async

################################
### theme
################################
# Enable Powerlevel10k instant prompt. Should stay close to the top of ~/.zshrc.
# Initialization code that may require console input (password prompts, [y/n]
# confirmations, etc.) must go above this block; everything else may go below.
if [[ -r "${XDG_CACHE_HOME:-$HOME/.cache}/p10k-instant-prompt-${(%):-%n}.zsh" ]]; then
  source "${XDG_CACHE_HOME:-$HOME/.cache}/p10k-instant-prompt-${(%):-%n}.zsh"
fi
source /opt/homebrew/share/powerlevel10k/powerlevel10k.zsh-theme

################################
### PATH
export PATH="/usr/local/opt/bison/bin:$PATH"
export PATH="/usr/local/opt/libxml2/bin:$PATH"
export PATH="/usr/local/opt/bzip2/bin:$PATH"
export PATH="/usr/local/opt/curl/bin:$PATH"
export PATH="/usr/local/opt/libiconv/bin:$PATH"
export PATH="/usr/local/opt/krb5/bin:$PATH"
export PATH="/usr/local/opt/openssl@1.1/bin:$PATH"
export PATH="/usr/local/opt/icu4c/bin:$PATH"
export PKG_CONFIG_PATH="/usr/local/opt/krb5/lib/pkgconfig:$PKG_CONFIG_PATH"
export PKG_CONFIG_PATH="/usr/local/opt/openssl@1.1/lib/pkgconfig:$PKG_CONFIG_PATH"
export PKG_CONFIG_PATH="/usr/local/opt/icu4c/lib/pkgconfig:$PKG_CONFIG_PATH"
export PATH="/Users/yutaaoki/.cache/.bun/bin:$PATH"

# Android SDK
export ANDROID_SDK_ROOT="$HOME/Library/Android/sdk"
export ANDROID_HOME="$ANDROID_SDK_ROOT"
export PATH="$PATH:$ANDROID_SDK_ROOT/platform-tools:$ANDROID_SDK_ROOT/cmdline-tools/latest/bin"

# WezTerm
export WEZTERM_CONFIG_FILE="$HOME/dotfiles/.config/WezTerm/wezterm.lua"
export WEZTERM_CONFIG_DIR="$HOME/dotfiles/.config/WezTerm"


### Added by Zinit's installer
if [[ ! -f /opt/homebrew/Cellar/zinit/3.14.0/zinit.zsh ]]; then
    print -P "%F{33}▓▒░ %F{220}Installing %F{33}DHARMA%F{220} Initiative Plugin Manager (%F{33}zdharma/zinit%F{220})…%f"
    command mkdir -p "$HOME/.zinit" && command chmod g-rwX "$HOME/.zinit"
    command git clone https://github.com/zdharma/zinit "$HOME/.zinit/bin" && \
        print -P "%F{33}▓▒░ %F{34}Installation successful.%f%b" || \
        print -P "%F{160}▓▒░ The clone has failed.%f%b"
fi

source "/opt/homebrew/Cellar/zinit/3.14.0/zinit.zsh"
autoload -Uz _zinit
(( ${+_comps} )) && _comps[zinit]=_zinit

### End of Zinit's installer chunk

if (( $+commands[mise] )); then
  eval "$(mise activate zsh)"
fi

### Color configuration
export CLICOLOR=1
export TERM=xterm-256color

#################################
## prompt
PROMPT='%F{red}%d%f$ '

#################################
## alias

# eza (highrighter)
if [[ $(command -v eza) ]]; then
  alias ls='eza --icons --git'
  alias lt='eza -T -L 3 -a -I "node_modules|.git|.cache" --icons'
  alias ltl='eza -T -L 3 -a -I "node_modules|.git|.cache" -l --icons'
  alias ll='eza -l -aa -h -@ -m --icons --git --time-style=long-iso --color=automatic --group-directories-first'
fi

# git diff function
g_diff() {
  if [[ $# -eq 0 ]]; then
    command git diff
    return
  fi

  if [[ $1 == <-> ]]; then
    local steps=$1
    shift
    case $steps in
      0) command git diff HEAD "$@" ;;
      1) command git diff HEAD^ HEAD "$@" ;;
      *) command git diff HEAD~"$steps" HEAD "$@" ;;
    esac
    return
  fi

  command git diff "$@"
}

## git
alias gs='git status'
alias gaa='git add .'
alias ga='git add'
alias gc='git checkout'
alias gm='git commit -m'
alias gps='git push'
alias gpl='git pull origin'
alias gpm='git pull origin master'
alias gmm='git merge'
alias gr-s='git reset --soft HEAD^'
alias gr-h='git reset --hard HEAD^'
alias gd=g_diff
alias gf='git fetch'
alias gl='git log'
alias grb='git rebase'
alias gb='git branch'

# claude code
alias c='claude'
alias c-d='claude --dangerously-skip-permissions'
alias c-p='claude --permission-mode plan'

# cursor-agent
alias c-a='cursor-agent'

# codex
alias co='codex'
alias co-d='codex --dangerously-bypass-approvals-and-sandbox'

# qwen
alias qw='qwen'

# aicommits (settings)
alias aicd='aicommits config set generate=3 max-length=40 locale=en model=gpt-5-nano'

## shell
dirtouch() {
    mkdir -p "$(dirname $1)"
    touch "$1"
}
alias mkf=dirtouch

## zsh
alias sz='source ~/dotfiles/.zshrc'
alias vz='vi ~/dotfiles/.zshrc'

## vim
alias sv='source ~/.vimrc'
alias vv='vi ~/.vimrc'

## nvim
alias cdnn='cd ~/dotfiles/.config/nvim'

## SocialDog
alias cdss='cd ~/socialdog'
alias cds='cd ~/socialdog/web'

## Trander
alias cdt='cd ~/trander'
alias cdf='cd ~/trander-flutter'
alias cdfm='cd ~/trander-flutter/master'
alias cdfw='cd ~/trander-flutter/.worktrees'
alias cdr='cd ~/trander-rust'

## WezTerm
alias cdw='cd ~/dotfiles/.config/WezTerm'

## dotfiles
alias cdd='cd ~/dotfiles'

## mu
alias cdv='cd ~/mu-muc-vscode'
alias cdg='cd ~/mu-muc-app-service'
alias cdg2='cd ~/mu-muc-app-service2'
alias cdg3='cd ~/mu-muc-app-service3'
alias cdgd='cd ~/mu-copilot-dev'

## Surfingkeys-conf
alias cdm='cd ~/surfingkeys-conf'

## LangUp
alias cdl='cd ~/LangUp'

## Hammerspoon
alias cdh='cd ~/dotfiles/.hammerspoon'

## astro-blog
alias cdb='cd ~/astro-blog'

## gg
alias cdn='cd ~/gg-ai-agent-family'
alias cdna='cd ~/gg-ai-agent-family/app'
alias cdn2='cd ~/gg-ai-agent-family-2'
alias cdna2='cd ~/gg-ai-agent-family-2/app'
alias cdn3='cd ~/gg-ai-agent-family-3'
alias cdna3='cd ~/gg-ai-agent-family-3/app'

# Enliminal
alias cde='cd ~/enliminal'

# zenn
alias cdz='cd ~/zenn'
# ./run-server.sh -f

# Obsidian
alias cdu='cd ~/uuta'

# u
alias cduu='cd ~/u'

## npc
alias cdp='cd ~/npc-qa-bot'
alias cdpn='cd ~/npc-qa-bot/iframe_next'

## .claude
alias cdc='cd ~/.claude'

## key-leap
alias cdk='cd ~/key-leap'

## To parent group-directoris
alias a='cd ../'
alias aa='cd ../../'
alias aaa='cd ../../../'

## gvimrc(vimの見た目)
alias sg='source ~/.gvimrc'
alias vg='vi ~/.gvimrc'

## neovim
alias nn='nvim'
alias nnz='nvim ~/dotfiles/.zshrc'
alias nni='nvim ~/dotfiles/.config/nvim/init.lua'
alias nnb='nvim ~/dotfiles/Brewfile'
alias nng='nvim ~/dotfiles/.config/ghostty/config'
alias nnh='nvim ~/dotfiles/.hammerspoon/init.lua'

# tmux
alias tm-s='tmux new -s'
alias tm-ls='tmux ls'
alias tm-a='tmux attach -t'

## silicon
alias sl='silicon --from-clipboard -l rs --to-clipboard'

## pbcopy
## with global aliases expand anywhere
alias -g PB='| pbcopy'

### symlink the nvim folder when it doesn't exist yet
if [ ! -e "$HOME/.config/nvim" ]; then
    ln -s "$HOME/dotfiles/.config/nvim" "$HOME/.config/nvim"
fi

### symlink for Hammerspoon
if [ ! -e "$HOME/.hammerspoon" ]; then
    ln -s "$HOME/dotfiles/.hammerspoon" "$HOME/.hammerspoon"
fi

if [ ! -e "$HOME/Library/Application Support/bottom/bottom.toml" ]; then
    ln -s "$XDG_CONFIG_HOME/bottom/bottom.toml" "$HOME/Library/Application Support/bottom/bottom.toml"
fi

## peco
# search command
function peco-history-selection() {
    BUFFER=`history -n 1 | tail -r  | awk '!a[$0]++' | peco`
    CURSOR=$#BUFFER
    zle reset-prompt
}

zle -N peco-history-selection
bindkey ';e' peco-history-selection

# search git derectory
alias g='cd $(ghq root)/$(ghq list | peco)'

# find_cd
function find_cd() {
    cd "$(find . -type d | peco)"
}
alias fc="find_cd"

# medis
alias medis="source ~/bin/medis"

# To customize prompt, run `p10k configure` or edit ~/.p10k.zsh.
[[ ! -f ~/.p10k.zsh ]] || source ~/.p10k.zsh

## lsのカラー
autoload -U compinit
compinit

export LSCOLORS=exfxcxdxbxegedabagacad
export LS_COLORS='di=34:ln=35:so=32:pi=33:ex=31:bd=46;34:cd=43;34:su=41;30:sg=46;30:tw=42;30:ow=43;30'

export XDG_CONFIG_HOME=~/dotfiles/.config

if [ -L "$HOME/.zshrc" ] || [ ! -e "$HOME/.zshrc" ]; then
    ln -sfn "$HOME/dotfiles/.zshrc" "$HOME/.zshrc"
fi

if [ -L "$HOME/.config" ] || [ ! -e "$HOME/.config" ]; then
    ln -sfn "$HOME/dotfiles/.config" "$HOME/.config"
fi

alias ls="ls -GF"
alias gls="gls --color"

alias f="flutter"

export LDFLAGS="-L/usr/local/opt/zlib/lib"
export CPPFLAGS="-I/usr/local/opt/zlib/include"

# ChatGPT
source "$HOME/.openai_key.zsh"

# u-agents runner env (U_AGENTS_DATABASE_URL / RUNNER_ID / MACHINE_ID).
# Copy .u_agents_env.zsh.template to ~/.u_agents_env.zsh and fill it in so the
# tmux PM pane and launcher/watchdog share the same runtime identity. Guarded
# so shells without the local file are unaffected. See docs/u-agents.md.
[[ -f "$HOME/.u_agents_env.zsh" ]] && source "$HOME/.u_agents_env.zsh"

# Embulk
export PATH="$HOME/.embulk/bin:$PATH"

# cloud_sql
export PATH="$HOME/cloud_sql_proxy:$PATH"

export NVIM_LOG_FILE="$HOME/.config/nvim/logs.log"
export NVIM_LOG_LEVEL="DEBUG"

# Docker
# Buildツールを使うかどうか
# export DOCKER_BUILDKIT=1

# yarn
export PATH="$(yarn global bin):$PATH"

# GitHub CLI
eval "$(gh completion -s zsh)"
export PATH="/usr/local/opt/node@14/bin:$PATH"

# symbolic link for Claude MCP servers
if [ -f "$HOME/dotfiles/.claude/settings.json" ]; then
    mkdir -p "$HOME/.claude"
    ln -sf "$HOME/dotfiles/.claude/settings.json" "$HOME/.claude/settings.json"
fi

# symbolic link for Claude agents and skills
if [ ! -e "$HOME/.claude/skills" ]; then
    ln -s "$HOME/dotfiles/skills" "$HOME/.claude/skills"
fi

if [ ! -e "$HOME/.claude/hooks" ]; then
    ln -s "$HOME/dotfiles/hooks" "$HOME/.claude/hooks"
fi

# symbolic link for Codex/ChatGPT skills
mkdir -p "$HOME/.agents"
if [ -L "$HOME/.agents/skills" ]; then
    ln -sfn "$HOME/dotfiles/skills" "$HOME/.agents/skills"
fi
if [ ! -e "$HOME/.agents/skills" ]; then
    ln -s "$HOME/dotfiles/skills" "$HOME/.agents/skills"
fi

if [ ! -e "$HOME/.mcp.json" ]; then
    ln -sf "$HOME/dotfiles/.mcp.json" "$HOME/.mcp.json"
fi

# Git diff highlight
export PATH="$PATH:/opt/homebrew/share/git-core/contrib/diff-highlight"
### End of Zinit's installer chunk

# pyenv
# export PATH="$HOME/.pyenv/bin:$PATH"
# eval "$(pyenv init --path)"

# python
# Changed path for rye
export PATH="$HOME/.local/share/uv/bin:$PATH"
export PATH="$HOME/.rye/shims:$PATH"

# pyenv
# export PYENV_ROOT="$HOME/.pyenv"
# export PATH="$PYENV_ROOT/bin:$PATH"

export PATH="/opt/homebrew/opt/rustup/bin:$HOME/.cargo/bin:/opt/homebrew/bin:$PATH"
# export PATH="/opt/homebrew/opt/python@3.8/libexec/bin:$PATH"
# export PATH="/opt/homebrew/Cellar/python@3.10/3.10.11/bin:$PATH"
#
# export PATH="/opt/homebrew/bin/conda:$PATH"

eval "$(direnv hook zsh)"

# go
export PATH=$PATH:$GOPATH/bin

# surfingkeys gulp
export PATH=$PATH:$HOME/surfingkeys-conf/node_modules/.bin

# LangUp
export PYTHONPATH="$HOME/LangUp/project"

# nvm
export NVM_DIR="$HOME/.nvm"
  [ -s "/opt/homebrew/opt/nvm/nvm.sh" ] && \. "/opt/homebrew/opt/nvm/nvm.sh"  # This loads nvm
  [ -s "/opt/homebrew/opt/nvm/etc/bash_completion.d/nvm" ] && \. "/opt/homebrew/opt/nvm/etc/bash_completion.d/nvm"  # This loads nvm bash_completion

# openjdk
# export PATH=$(brew --prefix)/opt/openjdk@17/bin:$PATH
# export JAVA_HOME=$(brew --prefix)/opt/openjdk@17
export PATH=$(brew --prefix)/opt/openjdk/bin:$PATH
export JAVA_HOME=$(brew --prefix)/opt/openjdk

# neo4j
export NEO4J_HOME=/usr/local/neo4j-community-5.26.0
export PATH=$NEO4J_HOME/bin:$PATH

# WezTerm
export WEZTERM_CONFIG_FILE="$HOME/dotfiles/.config/WezTerm/wezterm.lua"
export WEZTERM_CONFIG_DIR="$HOME/dotfiles/.config/WezTerm"

# INFO: Commented out conda initialization block due to potential conflicts with another Python environment manager (like pyenv or rye).
# >>> conda initialize >>>
# !! Contents within this block are managed by 'conda init' !!
# __conda_setup="$('/opt/homebrew/Caskroom/miniforge/base/bin/conda' 'shell.zsh' 'hook' 2> /dev/null)"
# if [ $? -eq 0 ]; then
#     eval "$__conda_setup"
# else
#     if [ -f "/opt/homebrew/Caskroom/miniforge/base/etc/profile.d/conda.sh" ]; then
#         . "/opt/homebrew/Caskroom/miniforge/base/etc/profile.d/conda.sh"
#     else
#         export PATH="/opt/homebrew/Caskroom/miniforge/base/bin:$PATH"
#     fi
# fi
# unset __conda_setup
# <<< conda initialize <<<



# function() link() {
#   [ -f $HOME/$1 ] && { 
#     echo "relinking $HOME/$1" && rm $HOME/$1
#   } || {
#     echo "linking $HOME/$1"
#   }
#   ln -sf $SCRIPT_DIR/$1 $HOME/$1
# }
#
# link dotfiles/.config/wezterm/.wezterm.lua



export PATH="/opt/homebrew/opt/php@8.2/bin:$PATH"
export PATH="/opt/homebrew/opt/php@8.2/sbin:$PATH"


typeset -g POWERLEVEL9K_INSTANT_PROMPT=quiet
# export PATH="$HOME/.jenv/bin:$PATH"
# eval "$(jenv init -)"

#THIS MUST BE AT THE END OF THE FILE FOR SDKMAN TO WORK!!!
export SDKMAN_DIR="$HOME/.sdkman"
[[ -s "$HOME/.sdkman/bin/sdkman-init.sh" ]] && source "$HOME/.sdkman/bin/sdkman-init.sh"

# Added by Windsurf
export PATH="/Users/yutaaoki/.codeium/windsurf/bin:$PATH"

# alias claude="/Users/yutaaoki/.claude/local/claude"
export PATH="$HOME/.local/bin:$PATH"
export PATH="/opt/homebrew/opt/mysql-client/bin:$PATH"

# Added by Antigravity
export PATH="/Users/yutaaoki/.antigravity/antigravity/bin:$PATH"
