# Contributing to Project JARVIS

Thank you for your interest in contributing to **Project JARVIS: Private Autonomous Operating System**.

## Development Workflow

1. **Fork or Clone**:
   ```bash
   git clone https://github.com/GaneshNair007/Jarvis.git
   cd Jarvis
   ```

2. **Install Dependencies**:
   ```bash
   python -m pip install -r requirements.txt
   python -m pip install -r requirements-ci.txt
   ```

3. **Run Code Quality Checks**:
   ```bash
   python -m ruff check .
   python -m ruff format --check .
   ```

4. **Run Test Suite**:
   ```bash
   python -m pytest tests -q
   ```

5. **Security Gates & Policy**:
   - Never commit API keys or unencrypted credentials.
   - All external powers must pass through PrivacyGate and PolicyGate.
