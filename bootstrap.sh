# Install brew to Mac
if !(type "brew" > /dev/null 2>&1); then
	/bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"
fi

# Path to brew
echo 'eval "$(/opt/homebrew/bin/brew shellenv)"' >> ~/.zprofile
eval "$(/opt/homebrew/bin/brew shellenv)"
source ~/.zprofile

# homebrew-bundle
brew bundle --file ./Brewfile

# Initialize Rust via rustup
RUSTUP_BIN="$(brew --prefix rustup)/bin/rustup"
if [ -x "$RUSTUP_BIN" ]; then
	if ! "$RUSTUP_BIN" show active-toolchain > /dev/null 2>&1; then
		"$RUSTUP_BIN" default stable
	fi

	"$RUSTUP_BIN" component add rust-analyzer rust-src rustfmt clippy
fi

# Setup GitHub CLI authentication only if needed
if ! gh auth status > /dev/null 2>&1; then
	echo "Setting up GitHub CLI..."
	gh auth login
else
	echo "GitHub CLI already authenticated; skipping login."
fi

# Create OpenAI key file for LLM usage if it doesn't exist
if [ ! -f ~/.openai_key.zsh ]; then
    cp ~/dotfiles/.openai_key.zsh.template ~/.openai_key.zsh
    echo "Created ~/.openai_key.zsh from template - add your API keys to this file"
fi

./prompts.sh

./gh/gh-bundle.sh
