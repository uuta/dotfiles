# dotfiles

Personal macOS development environment configuration.

## Getting Started

```shell
# Initial setup (Homebrew, Rust toolchain, GitHub auth)
./bootstrap.sh

# Sync prompts to ~/.codex and ~/.claude
./prompts.sh

# Install GitHub CLI extensions
./gh/gh-bundle.sh
```

## Repository Structure

```
.config/          XDG configs (nvim, zsh, git, alacritty, ghostty, etc.)
.claude/          Claude AI configuration
.hammerspoon/     macOS automation
agents/           Agent definitions
skills/           Claude skills
prompts/          Prompt templates
gh/               GitHub CLI extensions
hooks/            Dev workflow hooks
docs/             Documentation
```

The `u_agents` runner is maintained in https://github.com/uuta/uuter.

## Managed Tools

**Shell**: Zsh + Znap + Powerlevel10k

**Editor**: Neovim with LSP

**Terminals**: Alacritty, Ghostty, WezTerm

**VCS**: Git, Jujutsu, GitHub CLI

**Languages**: Node.js (nvm), Python (pyenv), Go, PHP

**Dev Tools**: Docker, Terraform, pre-commit

## AI Tools Configuration

Shared configuration for Codex and Claude Code:

```mermaid
graph LR
    subgraph dotfiles
        P[prompts/]
        A[agents/]
        S[skills/]
        H[hooks/]
        D[codex/config.toml]
        E[codex/AGENTS.md]
        C[.claude/settings.json]
    end

    subgraph "~/.codex"
        CP[prompts/]
        CX[config.toml]
        CG[AGENTS.md]
    end

    subgraph "~/.claude"
        CC[commands/]
        CA[agents/]
        CS[skills/]
        CH[hooks/]
        CJ[settings.json]
    end

    P -->|prompts.sh| CP
    P -->|prompts.sh| CC
    A -->|symlink| CA
    S -->|symlink| CS
    H -->|symlink| CH
    D -->|symlink| CX
    E -->|symlink| CG
    C -->|symlink| CJ
```

- `./prompts.sh` symlinks prompts to both `~/.codex` and `~/.claude/commands`
- `codex/config.toml` is the dotfiles-owned Codex user configuration
- `codex/AGENTS.md` is the dotfiles-owned global Codex guidance entrypoint
- `.zshrc` ensures the managed symlinks exist for shared config and agent tooling
