---
name: build_project
description: Automate project builds, dependency installation, compilation, bundling, and CI/CD execution across multiple ecosystems
---

# Build Project

Automate the full build lifecycle — dependency resolution, compilation, bundling, testing, containerization, and deployment.

## When to Use

- User asks to **build**, **compile**, **bundle**, or **deploy** a project
- Installing or updating project dependencies
- Running build scripts or CI/CD pipelines locally
- Creating Docker images or production bundles
- Setting up a new project from a template

## Workflow

### 1. Detect the Project Ecosystem

Scan the project root to identify the build system:

```
find_by_name(Pattern="package.json|requirements.txt|pyproject.toml|Cargo.toml|go.mod|Makefile|Dockerfile|build.gradle|pom.xml", SearchDirectory="/project")
```

| File               | Ecosystem   | Build Tool        |
| ------------------ | ----------- | ----------------- |
| `package.json`     | Node.js     | npm / yarn / pnpm |
| `requirements.txt` | Python      | pip               |
| `pyproject.toml`   | Python      | uv / pip / poetry |
| `Cargo.toml`       | Rust        | cargo             |
| `go.mod`           | Go          | go build          |
| `Makefile`         | Any         | make              |
| `Dockerfile`       | Container   | docker            |
| `build.gradle`     | Java/Kotlin | gradle            |
| `pom.xml`          | Java        | maven             |

### 2. Install Dependencies

#### Node.js
```bash
# Detect lock file to choose package manager
if [ -f "pnpm-lock.yaml" ]; then pnpm install
elif [ -f "yarn.lock" ]; then yarn install
elif [ -f "bun.lockb" ]; then bun install
else npm install
fi
```

#### Python
```bash
# Prefer uv for speed, fall back to pip
if command -v uv &>/dev/null; then
    uv pip install -r requirements.txt
elif [ -f "pyproject.toml" ]; then
    pip install -e ".[dev]"
else
    pip install -r requirements.txt
fi
```

#### Rust
```bash
cargo build
# or for release
cargo build --release
```

#### Go
```bash
go mod download
go build ./...
```

### 3. Build the Project

#### Node.js
```bash
# Check available scripts first
cat package.json | python3 -c "import sys,json; scripts=json.load(sys.stdin).get('scripts',{}); [print(f'  {k}: {v}') for k,v in scripts.items()]"

# Common build commands
npm run build          # Production build
npm run dev            # Dev server
npm run lint           # Linting
npm run test           # Tests
```

#### Python
```bash
# Run the application
python3 main.py

# Run with module syntax
python3 -m package_name

# Build distribution
python3 -m build
```

#### Docker
```bash
# Build image
docker build -t project-name:latest .

# Build with specific Dockerfile
docker build -f Dockerfile.prod -t project-name:prod .

# Build and run
docker build -t project-name . && docker run -p 8080:8080 project-name
```

#### Make
```bash
# List available targets
make help 2>/dev/null || grep -E '^[a-zA-Z_-]+:' Makefile | cut -d: -f1

# Common targets
make build
make test
make clean
make all
```

### 4. Verify the Build

After building, verify success:

```bash
# Check exit code
echo "Build exit code: $?"

# Check output artifacts exist
ls -la dist/ build/ target/ out/ 2>/dev/null

# Run smoke tests
npm test 2>/dev/null || python3 -m pytest 2>/dev/null || cargo test 2>/dev/null || go test ./... 2>/dev/null

# Check for build warnings/errors in output
# Review the terminal output for any warnings
```

### 5. New Project Scaffolding

When creating a new project from scratch:

```bash
# Node.js / Vite
npx -y create-vite@latest ./ --template react-ts

# Next.js
npx -y create-next-app@latest ./ --typescript --tailwind --app --src-dir

# Python
uv init --name project-name

# Rust
cargo init .

# Go
go mod init github.com/user/project
```

**Rules for scaffolding:**
- Always use `npx -y` to auto-accept installation
- Run `--help` first to check available options
- Initialize in current directory with `./`
- Use non-interactive mode flags

## CI/CD Execution

### GitHub Actions (local testing with `act`)
```bash
# List available workflows
ls .github/workflows/

# Run default workflow locally
act

# Run specific workflow
act -W .github/workflows/build.yml
```

### General CI commands
```bash
# Lint → Test → Build pipeline
npm run lint && npm run test && npm run build
# or
make lint test build
```

## Error Handling

- **Missing dependencies**: Install the package manager first (`npm`, `pip`, `cargo`, etc.)
- **Version conflicts**: Check lock files, try `rm -rf node_modules && npm install`
- **Build failures**: Read error output carefully, check for missing env vars or config
- **Port conflicts**: Check `lsof -i :PORT` before starting dev servers
- **Docker build fails**: Check base image availability, multi-stage build syntax
