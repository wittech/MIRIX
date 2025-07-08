![Mirix Logo](assets/logo.png)

## MIRIX - Multi-Agent Personal Assistant with an Advanced Memory System

Your personal AI that builds memory through screen observation and natural conversation

| 🌐 [Website](https://mirix.io) | 📚 [Documentation](https://docs.mirix.io) | 📄 [Paper](https://arxiv.org/abs/2409.13265) |
<!-- | [Twitter/X](https://twitter.com/mirix_ai) | [Discord](https://discord.gg/mirix) | -->

---

### Key Features 🔥

- **Multi-Agent Memory System:** Six specialized memory components (Core, Episodic, Semantic, Procedural, Resource, Knowledge Vault) managed by dedicated agents
- **Screen Activity Tracking:** Continuous visual data capture and intelligent consolidation into structured memories  
- **Privacy-First Design:** All long-term data stored locally with user-controlled privacy settings
- **Advanced Search:** PostgreSQL-native BM25 full-text search with vector similarity support
- **Multi-Modal Input:** Text, images, voice, and screen captures processed seamlessly

### Build the App from the source code
First set up a clean python environment:
```
# Create a clean virtual environment (recommended to avoid dependency conflicts)
python -m venv mirix_env

# Activate the environment
# On macOS/Linux:
source mirix_env/bin/activate
# On Windows:
# mirix_env\Scripts\activate
```

Then install dependencies:
```
# Install Python dependencies
pip install -r requirements.txt

# Install PyInstaller in the clean environment
pip install pyinstaller

# Install frontend dependencies
cd frontend
npm install
cd ..
```

Then build the backend and desktop app:
```
# Make sure you're in the clean environment
source mirix_env/bin/activate

# Build the backend executable
pyinstaller main.spec --clean

# Build the complete desktop application
cd frontend
npm run electron-pack
```

This will create a self-contained desktop application with:
- Embedded PGlite database (no external PostgreSQL needed)
- Pre-built Python backend executable
- React frontend in Electron wrapper

The final application will be available in `frontend/dist/`.


## License

Mirix is released under the MIT License. See the [LICENSE](LICENSE) file for more details.

## Contact

For questions, suggestions, or issues, please open an issue on the GitHub repository or contact us at `yuw164@ucsd.edu`

## Acknowledgement
We would like to thank [Letta](https://github.com/letta-ai/letta) for open-sourcing their framework, which served as the foundation for the memory system in this project.
