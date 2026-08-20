#!/bin/bash
set -e

rm -rf phase5_empirical
mkdir phase5_empirical
cd phase5_empirical

# 1. Initialize Git repository
git init > /dev/null 2>&1
git config user.email "test@google.com"
git config user.name "Test Agent"

# 2. Create Base State
cat << 'EOF' > src_server.rs
pub struct Server {
    is_running: bool,
}

impl Server {
    pub fn new() -> Self {
        Server { is_running: false }
    }
    // Agents will insert methods here
}
EOF

git add src_server.rs
git commit -m "Initial commit" > /dev/null 2>&1

BASE_BRANCH=$(git symbolic-ref --short HEAD)

# 3. Agent A modifies on Branch A
git checkout -b agent_a > /dev/null 2>&1
sed -i.bak 's/    \/\/ Agents will insert methods here/    pub fn start(\&mut self) {\n        self.is_running = true;\n    }\n    \/\/ Agents will insert methods here/' src_server.rs
git commit -am "Agent A adds start()" > /dev/null 2>&1

# 4. Agent B modifies on Branch B
git checkout "$BASE_BRANCH" > /dev/null 2>&1
git checkout -b agent_b > /dev/null 2>&1
sed -i.bak 's/    \/\/ Agents will insert methods here/    pub fn stop(\&mut self) {\n        self.is_running = false;\n    }\n    \/\/ Agents will insert methods here/' src_server.rs
git commit -am "Agent B adds stop()" > /dev/null 2>&1

# 5. The Fatal Merge
git checkout "$BASE_BRANCH" > /dev/null 2>&1
git merge agent_a > /dev/null 2>&1
echo "Merging Agent A into Master: SUCCESS"

set +e
echo "Merging Agent B into Master (Simulating Custom Harness Conflict):"
git merge agent_b
EXIT_CODE=$?
echo ""
echo "Git Merge Exit Code: $EXIT_CODE"

if [ $EXIT_CODE -ne 0 ]; then
    echo ""
    echo "--- RAW GIT CONFLICT DUMP ---"
    cat src_server.rs
fi
