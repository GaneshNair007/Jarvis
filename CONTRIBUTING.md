# 🤝 Contributing to JARVIS

Thank you for your interest in contributing to JARVIS! We welcome contributions from the community.

## 🏆 Achievement Badges

By contributing to JARVIS, you can earn GitHub achievement badges:
- **Pair Extraordinaire**: Co-author commits (use `Co-authored-by:` in commit messages)
- **Pull Shark**: Merge pull requests (Bronze: 2, Silver: 16, Gold: 128)
- **Quickdraw**: Respond to issues/PRs within 5 minutes

## 🚀 Quick Start

1. **Fork the repository**
2. **Clone your fork**
   ```bash
   git clone https://github.com/YOUR_USERNAME/Jarvis.git
   cd Jarvis
   ```

3. **Create a feature branch**
   ```bash
   git checkout -b feature/amazing-feature
   ```

4. **Make your changes**
   - Follow the code style (Black, isort)
   - Add tests for new features
   - Update documentation

5. **Run tests**
   ```bash
   pytest -v
   python -m black .
   python -m isort .
   ```

6. **Commit your changes**
   ```bash
   git commit -m "✨ Add amazing feature"
   ```
   
   For co-authored commits (earns Pair Extraordinaire badge):
   ```bash
   git commit -m "✨ Add amazing feature
   
   Co-authored-by: Partner Name <partner@email.com>"
   ```

7. **Push and create PR**
   ```bash
   git push origin feature/amazing-feature
   ```

## 📋 Commit Message Convention

We use emoji prefixes for clarity:

- ✨ `:sparkles:` - New feature
- 🐛 `:bug:` - Bug fix
- 📚 `:books:` - Documentation
- 🎨 `:art:` - Code style/formatting
- ⚡ `:zap:` - Performance improvement
- 🔒 `:lock:` - Security fix
- ✅ `:white_check_mark:` - Tests
- 🔧 `:wrench:` - Configuration
- ♻️ `:recycle:` - Refactoring
- 🚀 `:rocket:` - Deployment
- 🔄 `:arrows_counterclockwise:` - Dependencies

## 🧪 Testing Guidelines

- Write tests for all new features
- Ensure 80%+ code coverage
- Run full test suite before submitting PR
- Test on multiple Python versions if possible (3.9-3.12)

## 📝 Code Style

We use:
- **Black** for formatting
- **isort** for import sorting
- **Flake8** for linting
- **Type hints** where appropriate

Run formatting:
```bash
black .
isort .
flake8 .
```

## 🔍 Pull Request Process

1. Update the README.md with details of changes if needed
2. Update tests and ensure they pass
3. The PR will be reviewed by maintainers
4. Address any review comments
5. Once approved, it will be merged!

## 🎯 Areas for Contribution

- 🧠 **New Agents**: Planner, Researcher, Executor extensions
- 🔌 **Integrations**: Calendar, Home Assistant, Finance APIs
- 🧪 **Tests**: Increase coverage, add edge cases
- 📚 **Documentation**: Tutorials, examples, API docs
- ⚡ **Performance**: Optimize graph execution, reduce latency
- 🎨 **UI/UX**: Dashboard improvements, new visualizations
- 🔒 **Security**: Policy improvements, DLP enhancements

## 💬 Questions?

- Open an issue with the `question` label
- Check existing issues and discussions
- Review the documentation

## 🏆 Recognition

All contributors will be:
- Listed in the README
- Credited in release notes
- Part of the JARVIS community!

Thank you for contributing! 🚀
