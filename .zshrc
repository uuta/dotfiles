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
source /opt/homebrew/opt/powerlevel10k/powerlevel10k.zsh-theme

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

# Flutter
export PATH="$PATH:`pwd`/flutter/bin"
export PATH="$PATH:~/flutter/bin"

# platform-tools
export ANDROID_HOME=/Users/$USER/Library/Android/sdk
export PATH="$PATH:$ANDROID_HOME/tools:$ANDROID_HOME/platform-tools"

# WezTerm
export WEZTERM_CONFIG_FILE="$HOME/dotfiles/.config/wezterm/wezterm.lua"

### Added by Zinit's installer
if [[ ! -f /opt/homebrew/Cellar/zinit/3.7/zinit.zsh ]]; then
    print -P "%F{33}▓▒░ %F{220}Installing %F{33}DHARMA%F{220} Initiative Plugin Manager (%F{33}zdharma/zinit%F{220})…%f"
    command mkdir -p "$HOME/.zinit" && command chmod g-rwX "$HOME/.zinit"
    command git clone https://github.com/zdharma/zinit "$HOME/.zinit/bin" && \
        print -P "%F{33}▓▒░ %F{34}Installation successful.%f%b" || \
        print -P "%F{160}▓▒░ The clone has failed.%f%b"
fi

source "/opt/homebrew/Cellar/zinit/3.7/zinit.zsh"
# source "/opt/homebrew/Cellar/zsh-autosuggestions/0.7.0/share/zsh-autosuggestions/zsh-autosuggestions.zsh"
autoload -Uz _zinit
(( ${+_comps} )) && _comps[zinit]=_zinit

### End of Zinit's installer chunk

### Color configuration
export CLICOLOR=1
export TERM=xterm-256color
# source "/opt/homebrew/Cellar/zsh-syntax-highlighting/0.7.1/share/zsh-syntax-highlighting/zsh-syntax-highlighting.zsh"

#################################
## prompt
PROMPT='%F{red}%d%f$ '

#################################
## alias

# exa (highrighter)
if [[ $(command -v exa) ]]; then
  alias ls='exa --icons --git'
  alias lt='exa -T -L 3 -a -I "node_modules|.git|.cache" --icons'
  alias ltl='exa -T -L 3 -a -I "node_modules|.git|.cache" -l --icons'
  alias ll='exa -l -aa -h -@ -m --icons --git --time-style=long-iso --color=automatic --group-directories-first'
fi

## git
alias gs='git status'
alias gaa='git add .'
alias ga='git add'
alias gc='git checkout'
alias gm='git commit -m'
alias gps='git push'
alias gpl='git pull origin'
alias gpm='git pull origin master'
alias gmm='git merge origin/master'
alias gr-s='git reset --soft HEAD^'
alias gr-h='git reset --hard HEAD^'
alias gd='git diff'
alias gf='git fetch'
alias gl='git log'
alias grb='git rebase'
alias gb='git branch'

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
alias cdsg='cd ~/socialdog/web/application_go'
alias cdaa='cd ~/autoscale-probot'

## Trander
alias cdt='cd ~/trander'
alias cdf='cd ~/trander_flutter'
alias cdr='cd ~/trander-rust'

## Aftgr-Clean-Install
alias cda='cd ~/after-clean-install'

## WezTerm
alias cdw='cd ~/.config/WezTerm'

## dotfiles
alias cdd='cd ~/dotfiles'

## gas
alias cdg='cd ~/gas-workout-logs'

## Surfingkeys-conf
alias cdl='cd ~/surfingkeys-conf'

## Hammerspoon
alias cdh='cd ~/.hammerspoon'

## astro-blog
alias cdb='cd ~/astro-blog'

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
alias nni='nvim ~/.config/nvim/init.lua'
alias nnb='nvim ~/after-clean-install/Brewfile'

## php
alias php7.0='/Applications/MAMP/bin/php/php7.0.33/bin/php'

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

# ssh config
alias dev-car="source ~/.dev-car.sh "
alias car-u="source ~/.car-u.sh "
alias car-a="source ~/.car-a.sh "
alias car-gw="source ~/.car-gw.sh"

# medis
alias medis="source ~/bin/medis"

# To customize prompt, run `p10k configure` or edit ~/.p10k.zsh.
[[ ! -f ~/.p10k.zsh ]] || source ~/.p10k.zsh

## lsのカラー
autoload -U compinit
compinit

export LSCOLORS=exfxcxdxbxegedabagacad
export LS_COLORS='di=34:ln=35:so=32:pi=33:ex=31:bd=46;34:cd=43;34:su=41;30:sg=46;30:tw=42;30:ow=43;30'

alias ls="ls -GF"
alias gls="gls --color"

alias f="fvm flutter"

export LDFLAGS="-L/usr/local/opt/zlib/lib"
export CPPFLAGS="-I/usr/local/opt/zlib/include"

# ChatGPT
source "$HOME/.openai_key.zsh"

# Embulk
export PATH="$HOME/.embulk/bin:$PATH"

# cloud_sql
export PATH="$HOME/cloud_sql_proxy:$PATH"

export NVIM_LOG_FILE="$HOME/.config/nvim/logs.log"
export NVIM_LOG_LEVEL="DEBUG"

# Docker
# Buildツールを使うかどうか
# export DOCKER_BUILDKIT=1

# GitHub CLI
eval "$(gh completion -s zsh)"
export PATH="/usr/local/opt/node@14/bin:$PATH"

# Git diff highlight
export PATH="$PATH:/opt/homebrew/share/git-core/contrib/diff-highlight"
### End of Zinit's installer chunk

# python
# export PATH="/opt/homebrew/Cellar/python@3.10/3.10.11/bin:$PATH"
export PATH=/opt/homebrew/bin:$PATH
# Changed path for python@3.8
export PATH="/opt/homebrew/opt/python@3.8/libexec/bin:$PATH"
export PATH="/opt/homebrew/bin/conda:$PATH"

eval "$(direnv hook zsh)"

# go
export PATH=$PATH:$GOPATH/bin

# surfingkeys gulp
export PATH=$PATH:$HOME/surfingkeys-conf/node_modules/.bin

# mecab for SocialDog
export CGO_LDFLAGS="`mecab-config --libs`"
export CGO_CFLAGS="-I`mecab-config --inc-dir`"
export MECAB_DIC_PATH=$(mecab-config --dicdir)/mecab-ipadic-neologd

# nvm
export NVM_DIR="$HOME/.nvm"
  [ -s "/opt/homebrew/opt/nvm/nvm.sh" ] && \. "/opt/homebrew/opt/nvm/nvm.sh"  # This loads nvm
  [ -s "/opt/homebrew/opt/nvm/etc/bash_completion.d/nvm" ] && \. "/opt/homebrew/opt/nvm/etc/bash_completion.d/nvm"  # This loads nvm bash_completion

# >>> conda initialize >>>
# !! Contents within this block are managed by 'conda init' !!
__conda_setup="$('/opt/homebrew/Caskroom/miniforge/base/bin/conda' 'shell.zsh' 'hook' 2> /dev/null)"
if [ $? -eq 0 ]; then
    eval "$__conda_setup"
else
    if [ -f "/opt/homebrew/Caskroom/miniforge/base/etc/profile.d/conda.sh" ]; then
        . "/opt/homebrew/Caskroom/miniforge/base/etc/profile.d/conda.sh"
    else
        export PATH="/opt/homebrew/Caskroom/miniforge/base/bin:$PATH"
    fi
fi
unset __conda_setup
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



