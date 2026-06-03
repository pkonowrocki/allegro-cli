# Contributing to allegro-cli

First off, thank you for considering contributing to `allegro-cli`! It's a community-driven project, and help is always welcome.

## 🛠 How to Contribute

### 1. Report Bugs
Found a bug? Open an issue on GitHub. Please include:
- A clear description of the bug.
- Steps to reproduce (commands used).
- Your OS and Python version.

### 2. Suggest Features
Have an idea for a new filter or command? Open a feature request. We are particularly interested in features that make the tool more "Agent-friendly" or improve the power-user experience.

### 3. Submit a Pull Request
1. Fork the repository.
2. Create a feature branch (`git checkout -b feat/amazing-feature`).
3. Commit your changes with clear messages.
4. **Crucial**: Add or update tests in the `tests/` directory. We rely heavily on `pytest` and the `MockAllegroClient` to prevent regressions.
5. Push to the branch and open a PR.

## 📜 Development Guidelines

- **Stability First**: Always verify that your changes don't break existing functionality using `pytest`.
- **Agent-First**: If you add a new output field, consider if it should be included in the `--compact` JSON format.
- **Clean Code**: Follow PEP 8 guidelines.

Happy coding! 🛒
